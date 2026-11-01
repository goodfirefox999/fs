"""判定引擎（判定层）。

流水线（严格按 docs/DEVELOPMENT.md 第 7 节顺序）
----------------------------------------------
1. 输入校验与规范化（由调用方 ``app-zeri`` 完成，本层只接收已规范化的 ctx）
2. 候选枚举（``app-zeri/generator``）
3. 事实展开（``core_symbol.derive_facts``）
4. 规则匹配（本模块）
5. 三态判定（本模块，唯一权威定义见下）
6. 派别并列（``per_school``，**不合并分数**）
7. 共识集与排序（``ranker``）
8. 分歧度（``disagreement``）
9. 敏感性分析（``sensitivity``）
10. 报告与 manifest

三态判定（唯一权威定义，不得改写口径）
------------------------------------
- 任一 ``severity=禁用`` 且 ``hard_veto=true`` 命中 → ``不可用``
- 否则存在 ``慎用`` 命中（断言级或定义级结构）→ ``存疑``
- 否则 → ``可用``

规则状态与参与方式（ADR-0007）
------------------------------
- ``定义级``：干支算术推论，出处为内核规格。**直接参与**，结论进 ``structural``，
  只描述"结构是什么"；其中 ``severity=慎用`` 者计入 ``strong_avoid``。
- ``已考证``：有古籍原文 + 人类签名。**直接参与**，进 veto/caution/positive。
- ``待考证``/``有争议``：默认**不参与**，命中登记为 ``unknown``（reason=unverified_rule）；
  仅 ``allow_unverified=True`` 时进入判定并标 warning。

unknown 三分类（评审要求，报告必须分开统计）
------------------------------------------
- ``missing_input``：缺输入（如命主未提供、分金为空）→ 补输入即可判定
- ``caliber_undecided``：口径未裁定（如坐山纳音体系、月五黄起法）→ 需先定口径
- ``unverified_rule``：规则未考证 → 需补原文并签名

禁止：把三态压成单一总分；跨派别合成"综合吉凶分"。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from core_rule.dsl import eval_condition, resolve_path
from core_rule.models import SEVERITIES, Rule
from core_rule.provenance import Provenance, stable_hash
from core_rule.registry import RuleRegistry
from core_rule.severity_cap import cap_severity, participates_in_tier  # ADR-0014 单一来源
from core_time.hashing import stable_cache_key  # C19：统一缓存键

__all__ = [
    "STATE_BLOCKED",
    "STATE_OK",
    "STATE_UNSURE",
    "TIER_REJECTED",
    "TIER_NEEDS_REVIEW",
    "TIER_ACCEPTABLE",
    "TIER_PREFERRED",
    "STRICTNESS_STRICT",
    "STRICTNESS_NORMAL",
    "STRICTNESS_LOOSE",
    "UNKNOWN_MISSING_INPUT",
    "UNKNOWN_CALIBER",
    "UNKNOWN_UNVERIFIED",
    "Judgment",
    "SchoolResult",
    "Evaluation",
    "EvalConfig",
    "evaluate",
    "render_explanation",
    "classify_unknown",
    "ENGINE_VERSION",
]

STATE_BLOCKED = "不可用"
STATE_OK = "可用"
STATE_UNSURE = "存疑"

TIER_REJECTED = "REJECTED"
TIER_NEEDS_REVIEW = "NEEDS_REVIEW"
TIER_ACCEPTABLE = "ACCEPTABLE"
TIER_PREFERRED = "PREFERRED"

STRICTNESS_STRICT = "strict"
STRICTNESS_NORMAL = "normal"
STRICTNESS_LOOSE = "loose"

ENGINE_VERSION = "0.2.0"

_STATE_RANK = {STATE_OK: 0, STATE_UNSURE: 1, STATE_BLOCKED: 2}

#: 规则选择缓存（key 含 ruleset.version，规则库一变即失效）。
#: 4380 候选 × N 派 × 44 规则 = 数十万次 applies_to 匹配，缓存后可省掉大半。
_SELECT_CACHE: dict[tuple[Any, ...], tuple[Rule, ...]] = {}


#: 规则选择缓存（key 含 ruleset.version，规则库一变即失效）。
#: 4380 候选 × N 派 × 44 规则 = 数十万次 applies_to 匹配，缓存后可省掉大半。
_SELECT_CACHE: dict[tuple[Any, ...], tuple[Rule, ...]] = {}
#: C19：select 键的 per-ruleset 重前缀记忆化（fingerprint→prefix）。
#: fingerprint 已是内容哈希，可作映射键；逐调用只哈希小尾部，
#: 否则 4380 候选 × 7 派 × 全量 rule_ids 的 json 序列化 ≈ +1.5s（实测回归）。
_SELECT_KEY_PREFIX: dict[str, str] = {}


def _select_cached(
    ruleset: Any,
    *,
    schools: tuple[str, ...],
    task_kind: str,
    node_kind: str | None,
    strictness: str,
    include_unverified: bool,
) -> tuple[Rule, ...]:
    # key 必须覆盖"规则集内容"，不能只用 version ——
    # 动态构造的 RuleSet（测试 fixture、未来热加载）可能复用同一 version，
    # 只用 version 会导致缓存串味：合成规则被带到后续评估里（已踩过）。
    # C19：复合缓存键统一经 stable_cache_key 构造，禁止手写组合键；
    # 重前缀按 fingerprint 记忆化（fingerprint 即内容身份，映射键安全）。
    fingerprint = ruleset.fingerprint
    prefix = _SELECT_KEY_PREFIX.get(fingerprint)
    if prefix is None:
        prefix = stable_cache_key(
            "select_rules",
            fingerprint,  # ADR-0014：内容身份（同 id 同 version 改内容不再串味，第三次实证后引入）
            ENGINE_VERSION,  # 评估/cap 语义版本——改动引擎语义必须 bump（持久化缓存防跨语义投毒）
            ruleset.version,
            ruleset.rule_ids or tuple(r.rule_id for r in ruleset.rules),
        )
        if len(_SELECT_KEY_PREFIX) > 256:  # pragma: no cover - 防御性上限
            _SELECT_KEY_PREFIX.clear()
        _SELECT_KEY_PREFIX[fingerprint] = prefix
    key = stable_cache_key(
        prefix,
        schools,
        task_kind,
        node_kind,
        strictness,
        include_unverified,
    )
    cached = _SELECT_CACHE.get(key)
    if cached is None:
        cached = ruleset.select(
            schools=schools,
            task_kind=task_kind,
            node_kind=node_kind,
            strictness=strictness,
            include_unverified=include_unverified,
        )
        if len(_SELECT_CACHE) > 4096:  # pragma: no cover - 防御性上限
            _SELECT_CACHE.clear()
        _SELECT_CACHE[key] = cached
    return cached

#: unknown 三分类（评审要求）
UNKNOWN_MISSING_INPUT = "missing_input"
UNKNOWN_CALIBER = "caliber_undecided"
UNKNOWN_UNVERIFIED = "unverified_rule"

#: 事实注册表里"本系统不提供"的根（用于把 unknown 归到 caliber_undecided）
_CALIBER_ROOTS = (
    "facts.wuhuang.month",
    "facts.yinfu",
    "facts.dutiansha",
    "facts.fubing_dahuo",
    "facts.tianguan_difu",
    "facts.damonthly_jian",
    "facts.yangongji",
    "facts.sang",
    "facts.jiaqu",
    "facts.xiujiu",
)


@dataclass(frozen=True)
class EvalConfig:
    """一次评估的配置。

    ``strictness`` 语义（ADR-0008）：

    - ``strict``：断言级 ``慎用`` 命中即判 ``不可用``（tier=REJECTED），并启用
      ``strictness_min=strict`` 的加严规则。
    - ``normal``：断言级 ``慎用`` 命中判 ``存疑``（tier=NEEDS_REVIEW）。
    - ``loose``：断言级 ``慎用`` 仅记提示，不改变 state（tier 最多 ACCEPTABLE）。
    """

    task_kind: str
    node_kind: str | None = None
    strictness: str = STRICTNESS_NORMAL
    schools: tuple[str, ...] | None = None
    allow_unverified: bool = False
    #: ADR-0014 决策 3：演示命中计入 state/tier 的联调开关（默认 False=只渲染不计入；
    #: 须与 allow_unverified 同用，CLI 层做依赖校验）
    demo_veto: bool = False
    granularity: str = "day_hour"
    max_depth: int = 4
    #: 该事项的必需规则 id（决定 publishable 的判定范围）。为空时由 registry 注入。
    required_rule_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_kind": self.task_kind,
            "node_kind": self.node_kind,
            "strictness": self.strictness,
            "schools": list(self.schools) if self.schools else None,
            "allow_unverified": self.allow_unverified,
            "demo_veto": self.demo_veto,
            "granularity": self.granularity,
            "required_rule_ids": list(self.required_rule_ids),
        }


@dataclass(frozen=True)
class Judgment:
    """单条判定。

    ``participation`` 说明该条是否进入正式判定：
    ``判定``（已考证/定义级）｜``仅登记``（命中但未考证）｜``输入不足``。
    """

    rule_id: str
    rule_version: int
    school: str
    category: str
    status: str
    severity: str
    target: str
    matched: bool
    participation: str
    hit_detail: str
    explanation: str
    citation: dict[str, Any]
    params_hash: str
    unknown_paths: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    score_weight: float | None = None
    #: 该判定是否来自定义级规则（结构事实，非吉凶断言）
    definitional: bool = False
    #: unknown 三分类（仅 participation != 判定 时有值）
    unknown_reason: str | None = None
    #: 解除条件提示（告诉用户"补什么就能判定"）
    remedy: str | None = None
    #: ADR-0014 决策 2：证据来源的结构化标记（verified/controversial/unverified/definitional）。
    #: 可行动性必须结构化——warning 中文文案只是它的渲染，不是替代。
    source_status: str | None = None
    #: ADR-0014 决策 0：判定（存疑）——有争议规则默认参与评估，但不入任何结论强度桶
    doubt: bool = False
    #: ADR-0014 决策 1：声明严重度（severity 字段存生效值；审计链要求声明/生效双显示）
    declared_severity: str | None = None

    @property
    def is_demo(self) -> bool:
        """演示命中：规则未考证，仅在 ``--allow-unverified`` 下参与链路，**不作为排除依据**。"""
        return self.participation == "演示"

    @property
    def is_effective(self) -> bool:
        """是否真正参与判定（含演示）。仅 ``判定`` 才算"确定"。"""
        return self.participation in ("判定", "演示")

    @property
    def is_veto(self) -> bool:
        return self.is_effective and self.severity == "禁用"

    @property
    def is_caution(self) -> bool:
        return self.is_effective and self.severity == "慎用"

    @property
    def is_positive(self) -> bool:
        return (
            self.is_effective
            and not self.definitional
            and self.severity in ("推荐", "可用")
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "school": self.school,
            "category": self.category,
            "status": self.status,
            "severity": self.severity,
            "target": self.target,
            "matched": self.matched,
            "participation": self.participation,
            "definitional": self.definitional,
            "hit_detail": self.hit_detail,
            "explanation": self.explanation,
            "citation": self.citation,
            "params_hash": self.params_hash,
            "unknown_paths": list(self.unknown_paths),
            "unknown_reason": self.unknown_reason,
            "remedy": self.remedy,
            "source_status": self.source_status,
            "doubt": self.doubt,
            "declared_severity": self.declared_severity,
            "warnings": list(self.warnings),
            "score_weight": self.score_weight,
        }


@dataclass
class SchoolResult:
    """单个派别的评估结果。**不得与其他派别合并成分数。**"""

    school: str
    state: str
    vetoes: list[Judgment] = field(default_factory=list)
    cautions: list[Judgment] = field(default_factory=list)
    notes: list[Judgment] = field(default_factory=list)
    positives: list[Judgment] = field(default_factory=list)
    unknowns: list[Judgment] = field(default_factory=list)
    #: 定义级结构命中（含"慎用"与"中性"两类；慎用者同时计入 strong_avoid）
    structural: list[Judgment] = field(default_factory=list)
    #: ADR-0014 决策 0：存疑命中（有争议规则默认参与评估；只渲染，不入结论强度桶）
    controversial: list[Judgment] = field(default_factory=list)
    #: ADR-0014 决策 3：演示命中（demo_veto=False 时只渲染不计入；True 时按声明严重度路由）
    demo_hits: list[Judgment] = field(default_factory=list)
    rank_score: float | None = None
    rules_evaluated: int = 0
    #: 该派看到的输入事实哈希（用于验证"各派 fact 完全一致"）
    fact_hash: str = ""

    @property
    def structural_cautions(self) -> list[Judgment]:
        return [j for j in self.structural if j.severity == "慎用"]

    @property
    def counts(self) -> dict[str, int]:
        return {
            "hard_fail_count": len(self.vetoes),
            "strong_avoid_count": len(self.cautions) + len(self.structural_cautions),
            "assertion_caution_count": len(self.cautions),
            "structural_caution_count": len(self.structural_cautions),
            "structural_neutral_count": len(self.structural) - len(self.structural_cautions),
            "note_count": len(self.notes),
            "positive_count": len(self.positives),
            "unknown_count": len(self.unknowns),
            # ADR-0014：存疑/演示命中单列，不入 strong_avoid（决策 0/3）
            "controversial_count": len(self.controversial),
            "demo_hit_count": len(self.demo_hits),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "school": self.school,
            "state": self.state,
            "fact_hash": self.fact_hash,
            "counts": self.counts,
            "rank_score": self.rank_score,
            "rules_evaluated": self.rules_evaluated,
            "vetoes": [j.to_dict() for j in self.vetoes],
            "cautions": [j.to_dict() for j in self.cautions],
            "structural": [j.to_dict() for j in self.structural],
            "notes": [j.to_dict() for j in self.notes],
            "positives": [j.to_dict() for j in self.positives],
            "unknowns": [j.to_dict() for j in self.unknowns],
            "controversial": [j.to_dict() for j in self.controversial],
            "demo_hits": [j.to_dict() for j in self.demo_hits],
        }


@dataclass
class Evaluation:
    """一次评估的完整结果。"""

    candidate: str
    per_school: dict[str, SchoolResult]
    state: str
    tier: str
    vectors: dict[str, Any]
    conflicts: list[dict[str, Any]]
    unknowns: list[dict[str, Any]]
    manifest: dict[str, Any]
    config: EvalConfig
    #: 全局结构判定（定义级，去重后按规则 id 排序）
    structural: list[Judgment] = field(default_factory=list)
    #: 本次评估生效的必需规则集（决定 publishable 范围）
    required_rule_ids: tuple[str, ...] = ()
    #: 必需集里尚不可判定的规则（engine 预计算，避免 Evaluation 反查 ruleset）
    blocked_required: list[dict[str, Any]] = field(default_factory=list)

    @property
    def judgments(self) -> list[Judgment]:
        out: list[Judgment] = []
        for res in self.per_school.values():
            out.extend(res.vetoes + res.cautions + res.notes + res.positives + res.unknowns)
        return out

    @property
    def publishable(self) -> bool:
        """是否可对外发布。

        判定口径（ADR-0010，评审要求）：

        - **有必需集时**：只看该事项的必需规则是否**全部可判定**
          （participation == "判定"，且无输入不足）。非必需规则待考证只降级为
          「参考层缺失」，不阻塞发布 —— 否则 publishable 会永久 false，考证失去验收信号。
        - **无必需集时**：退回严格口径（任何未考证命中/争议/冲突都阻塞）。
        - 两种情况都要求 tier ∈ {ACCEPTABLE, PREFERRED} 且无冲突。
        """
        if self.vectors.get("conflict_count", 0) > 0:
            return False
        required = set(self.required_rule_ids)
        if required:
            # 有必需集：只要求"必需规则全部可判定 + 无硬否决"。
            # 非必需规则的 unknown / 待考证只降级为「参考层缺失」，**不阻塞发布** ——
            # 否则 publishable 会永久 false，考证失去验收信号（ADR-0010）。
            if self.tier == TIER_REJECTED:
                return False
            if self.blocked_required:
                return False
            return True
        # 无必需集：退回严格口径
        if self.tier not in (TIER_PREFERRED, TIER_ACCEPTABLE):
            return False
        if self.vectors.get("unverified_hit_count", 0) > 0:
            return False
        if self.vectors.get("disputed_count", 0) > 0:
            return False
        return True

    @property
    def required_blockers(self) -> list[dict[str, Any]]:
        """必需集里尚未可判定的规则（用于报告"还差什么才能发布"）。

        阻塞有两种来源（都在 engine 预计算）：

        1. **规则本身未考证**（status ∉ {已考证, 定义级}）——
           此时即使求值为 False，"不犯"这个结论也是基于未考证的条件得出的，
           不能作为"确认不犯"的发布依据；
        2. **输入不足**（该规则求值为 unknown）。
        """
        return list(self.blocked_required)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "schema_version": 2,  # v2 = ADR-0014（source_status/doubt/declared_severity/controversial/demo_hits）；v1 = 此前
            "state": self.state,
            "tier": self.tier,
            "publishable": self.publishable,
            "vectors": self.vectors,
            "per_school": {k: v.to_dict() for k, v in self.per_school.items()},
            "structural": [j.to_dict() for j in self.structural],
            "required_rule_ids": list(self.required_rule_ids),
            "required_blockers": self.required_blockers,
            "required_satisfied_count": len(self.required_rule_ids) - len(self.blocked_required),
            "conflicts": self.conflicts,
            "unknowns": self.unknowns,
            "manifest": self.manifest,
        }


# --------------------------------------------------------------------------- #
# 解释渲染（模板化，禁止自由生成）
# --------------------------------------------------------------------------- #
def render_explanation(template: str, ctx: dict[str, Any]) -> str:
    """把 ``{path}`` 占位符替换为 ctx 中的值；找不到时标注"未提供"，不编造。"""
    import re

    def repl(match: "re.Match[str]") -> str:
        path = match.group(1)
        found, value = resolve_path(ctx, path)
        if not found or value is None:
            return "（未提供）"
        if isinstance(value, (list, tuple)):
            return "/".join(str(v) for v in value)
        if isinstance(value, dict):
            return "（复合值）"
        return str(value)

    return re.sub(r"\{([a-zA-Z0-9_.]+)\}", repl, template)


# --------------------------------------------------------------------------- #
# unknown 三分类
# --------------------------------------------------------------------------- #
def classify_unknown(
    rule: Rule,
    *,
    participation: str,
    unknown_paths: tuple[str, ...],
) -> tuple[str, str]:
    """返回 ``(reason, remedy)``。

    - 规则本身未考证（命中但仅登记）→ ``unverified_rule``
    - 缺失的事实属于"口径未裁定"→ ``caliber_undecided``
    - 其余缺失 → ``missing_input``
    """
    if participation == "仅登记":
        return (
            UNKNOWN_UNVERIFIED,
            f"需补《{rule.citation.source}》原文与卷次，由考证者签名后升级为已考证",
        )

    for path in unknown_paths:
        if any(path.startswith(root) for root in _CALIBER_ROOTS):
            return (
                UNKNOWN_CALIBER,
                f"需先裁定 `{path}` 所属口径（见 docs/QUESTIONS.md Q-005/Q-006）",
            )

    if unknown_paths:
        return UNKNOWN_MISSING_INPUT, "补输入即可判定：" + "、".join(unknown_paths)
    return UNKNOWN_MISSING_INPUT, "补输入即可判定"


#: ADR-0014 决策 2：status → source_status 结构化标记
_SOURCE_STATUS = {
    "已考证": "verified",
    "定义级": "definitional",
    "有争议": "controversial",
    "待考证": "unverified",
}


def _make_judgment(
    rule: Rule,
    *,
    ctx: dict[str, Any],
    rule_lib_version: str,
    participation: str,
    input_hash: str,
    school: str,
    severity: str,
    unknown_paths: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    doubt: bool = False,
    declared_severity: str | None = None,
) -> Judgment:
    prov = Provenance(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        school=rule.school,
        rule_lib_version=rule_lib_version,
        citation=rule.citation,
        params_snapshot={
            "condition": rule.condition,
            "target": rule.target,
            "severity": severity,
            "input_hash": input_hash,
        },
    )
    reason: str | None = None
    remedy: str | None = None
    if participation != "判定":
        reason, remedy = classify_unknown(
            rule, participation=participation, unknown_paths=unknown_paths
        )
    return Judgment(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        school=school,
        category=rule.category,
        status=rule.status,
        severity=severity,
        target=rule.target,
        matched=participation in ("判定", "仅登记"),
        participation=participation,
        hit_detail=render_explanation(rule.explanation, ctx),
        explanation=rule.explanation,
        citation=rule.citation.to_dict(),
        params_hash=prov.params_hash,
        unknown_paths=unknown_paths,
        warnings=warnings,
        score_weight=rule.score_weight,
        definitional=rule.is_definitional,
        unknown_reason=reason,
        remedy=remedy,
        source_status=_SOURCE_STATUS.get(rule.status),
        doubt=doubt,
        declared_severity=declared_severity if declared_severity is not None else rule.severity,
    )


# --------------------------------------------------------------------------- #
# 单派评估
# --------------------------------------------------------------------------- #
def _evaluate_school(
    rules: tuple[Rule, ...],
    ctx: dict[str, Any],
    cfg: EvalConfig,
    *,
    school: str,
    rule_lib_version: str,
    veto_enabled: bool,
    input_hash: str,
    fact_hash: str,
) -> SchoolResult:
    vetoes: list[Judgment] = []
    cautions: list[Judgment] = []
    notes: list[Judgment] = []
    positives: list[Judgment] = []
    unknowns: list[Judgment] = []
    structural: list[Judgment] = []
    # ADR-0014 决策 0：存疑命中（有争议规则默认参与评估，只渲染，不入结论强度桶）
    controversial: list[Judgment] = []
    # ADR-0014 决策 3：demo_veto=False 时演示命中只渲染不计入
    demo_hits: list[Judgment] = []
    evaluated = 0

    strict = cfg.strictness == STRICTNESS_STRICT
    loose = cfg.strictness == STRICTNESS_LOOSE

    for rule in rules:
        if rule.status == "弃用":
            continue
        # day 粒度下不评估时级规则（文档 7.2：day 粒度时 hour 取 null）
        if cfg.granularity == "day" and rule.target == "hour":
            continue
        if not rule.applies_to.matches(
            task_kind=cfg.task_kind, node_kind=cfg.node_kind, strictness=cfg.strictness
        ):
            continue
        evaluated += 1
        outcome = eval_condition(rule.condition, ctx)

        if outcome.value is None:
            unknowns.append(
                _make_judgment(
                    rule,
                    ctx=ctx,
                    rule_lib_version=rule_lib_version,
                    participation="输入不足",
                    input_hash=input_hash,
                    school=school,
                    severity=cap_severity(rule.severity, rule.status),
                    declared_severity=rule.severity,
                    unknown_paths=tuple(outcome.unknown_paths),
                    warnings=("输入不足，该规则无法判定",),
                )
            )
            continue

        if outcome.value is False:
            continue

        # ---- 命中 ----
        declared = rule.severity_for(school)
        severity = cap_severity(declared, rule.status)  # ADR-0014 决策 1：单一来源 cap
        is_verified = rule.status in ("已考证", "定义级")
        is_controversial = rule.status == "有争议"
        # ADR-0014 C12：有争议规则默认参与评估（判定（存疑））；待考证仍需 --allow-unverified
        participating = is_verified or cfg.allow_unverified or is_controversial
        if not participating:
            unknowns.append(
                _make_judgment(
                    rule,
                    ctx=ctx,
                    rule_lib_version=rule_lib_version,
                    participation="仅登记",
                    input_hash=input_hash,
                    school=school,
                    severity=severity,
                    declared_severity=declared,
                    warnings=(f"规则命中但依据为「{rule.status}」，未参与正式判定",),
                )
            )
            continue

        warnings: tuple[str, ...] = ()
        participation = "判定"
        doubt = False
        if is_controversial:
            # ADR-0014 决策 0/2：存疑判定——参与评估、结构化标记，不入任何结论强度桶
            doubt = True
        elif not is_verified:
            # 演示命中：规则未考证，链路可跑通，但**不作为排除依据**
            # （渲染恒开；是否计入 state/tier 由 demo_veto 控制——决策 3 三态）
            participation = "演示"
            warnings = (f"依据为「{rule.status}」，属演示命中，不作为排除依据，不得对外发布",)

        is_demo = participation == "演示"
        # demo_veto=True 为显式联调例外：演示路由按**声明** severity（恢复"不可用"渲染路径）
        route_severity = declared if (is_demo and cfg.demo_veto) else severity
        judgment = _make_judgment(
            rule,
            ctx=ctx,
            rule_lib_version=rule_lib_version,
            participation=participation,
            input_hash=input_hash,
            school=school,
            severity=route_severity,
            warnings=warnings,
            doubt=doubt,
            declared_severity=declared,
        )

        # 定义级：结构事实。进 structural；"慎用"由 state 计算与 strong_avoid 统一处理
        if rule.is_definitional:
            structural.append(judgment)
            continue

        # ADR-0014 决策 0（甲案不变式）：存疑规则的证据强度不足以支撑任何结论强度
        # —— 只渲染，不入 vetoes/cautions/positives，不影响 state/tier/publishable
        if doubt:
            controversial.append(judgment)
            continue

        # ADR-0014 决策 3（三态）：demo_veto=False 时演示命中只渲染不路由
        if is_demo and not cfg.demo_veto:
            demo_hits.append(judgment)
            continue

        if route_severity == "禁用" and rule.hard_veto:
            if veto_enabled:
                vetoes.append(judgment)
            else:
                notes.append(judgment)
            continue
        if route_severity == "慎用":
            if loose:
                notes.append(judgment)
            elif strict and (is_demo or participates_in_tier(rule)):
                # ADR-0014 不变式：strict 只强化"已确定"的判断（升级要求 status=已考证）。
                # demo_veto=True 的演示路径是显式联调例外（恢复旧渲染视图，participation=演示）。
                vetoes.append(judgment)
            else:
                cautions.append(judgment)
            continue
        if route_severity in ("推荐", "可用"):
            positives.append(judgment)
        else:
            notes.append(judgment)

    # ---- 三态 ----
    # 定义级结构（severity=记录）**一律不影响 state**（ADR-0009）。
    # 结构事实回答"是什么"，不回答"好不好"；若让它影响 tier，等于给断言披上"已确定"的外衣。
    if vetoes:
        state = STATE_BLOCKED
    elif cautions:
        state = STATE_UNSURE
    else:
        state = STATE_OK

    rank_score: float | None = None
    if state == STATE_OK:
        rank_score = sum((r.score_weight or 0.0) for r in positives) if positives else 0.0

    return SchoolResult(
        school=school,
        state=state,
        vetoes=vetoes,
        cautions=cautions,
        notes=notes,
        positives=positives,
        unknowns=unknowns,
        structural=structural,
        controversial=controversial,
        demo_hits=demo_hits,
        rank_score=rank_score,
        rules_evaluated=evaluated,
        fact_hash=fact_hash,
    )


# --------------------------------------------------------------------------- #
# 冲突检测（四类，只登记不裁定）
# --------------------------------------------------------------------------- #
def _sub_rule_payload(j: Judgment) -> dict[str, Any]:
    """单条子规则 → spec §2 sub_rules 条目。

    ``verdict`` 取**生效严重度**（证据封顶后；ADR-0014）；``score_delta`` 仅对
    参与评分的桶给值（可用 +1 / 慎用 -1），否决与 unknown/记录不给分——
    否决日期已退出评分环节，unknown 不得伪装成分数。
    """
    return {
        "rule_id": j.rule_id,
        "verdict": j.severity,
        "status": j.status,
        "participation": j.participation,
        "declared_severity": j.declared_severity,
        "source_ref": {
            "source": (j.citation or {}).get("source"),
            "entry": (j.citation or {}).get("entry"),
        },
    }


def _school_payload(
    name: str,
    res: SchoolResult,
    layer: str,
    tendency: str,
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    """SchoolResult → spec §2 school_results 条目（五派并列，互不覆盖）。"""
    sub_rules: list[dict[str, Any]] = []
    for bucket, delta in (("vetoes", None), ("cautions", -1), ("positives", 1)):
        for j in getattr(res, bucket):
            entry = _sub_rule_payload(j)
            entry["score_delta"] = delta
            entry["bucket"] = bucket
            sub_rules.append(entry)
    for j in res.unknowns:
        entry = _sub_rule_payload(j)
        entry["score_delta"] = None
        entry["bucket"] = "unknowns"
        sub_rules.append(entry)
    return {
        "school": name,
        "overall_tendency": tendency,
        "score_delta": len(res.positives) - len(res.vetoes) - len(res.cautions),
        "layer": layer,
        "sub_rules": sub_rules,
        "conflict_flags": [
            {"schools": c["schools"], "issue": c["issue"]}
            for c in conflicts
            if name in c["schools"]
        ],
    }


def _detect_conflicts(per_school: dict[str, SchoolResult]) -> list[dict[str, Any]]:
    """检测冲突。

    1. ``rule_conflict``：**同一派内**两条规则对同一 target 给出互斥结论
       （一条判禁用、一条判推荐/可用）—— 这是"规则互相抵消"，与派别分歧不同。
    2. ``verdict_conflict``：派别间结论互斥（一派不可用、一派可用）。
    3. ``state_divergence``：派别间三态不一致（非互斥）。
    4. ``policy_divergence``：同一 category 在不同派别下 severity 不同。
    """
    conflicts: list[dict[str, Any]] = []

    # 1. 规则级冲突（同一派内）
    for name, res in per_school.items():
        by_target: dict[str, list[Judgment]] = {}
        for j in res.vetoes + res.cautions + res.positives + res.structural:
            by_target.setdefault(j.target, []).append(j)
        for target, items in by_target.items():
            negative = [j for j in items if j.severity == "禁用"]
            positive = [j for j in items if j.severity in ("推荐", "可用") and not j.definitional]
            if negative and positive:
                conflicts.append(
                    {
                        "type": "rule_conflict",
                        "scope": "school",
                        "school": name,
                        "target": target,
                        "detail": "同一派内两条规则对同一目标给出互斥结论（一条判禁用、一条判正向）",
                        "rule_a": negative[0].rule_id,
                        "rule_b": positive[0].rule_id,
                        "severities": {
                            negative[0].rule_id: "禁用",
                            positive[0].rule_id: positive[0].severity,
                        },
                        "citations": {
                            negative[0].rule_id: negative[0].citation.get("source"),
                            positive[0].rule_id: positive[0].citation.get("source"),
                        },
                    }
                )

    # 2/3. 派别级
    states = {name: res.state for name, res in per_school.items()}
    if STATE_BLOCKED in states.values() and STATE_OK in states.values():
        conflicts.append(
            {
                "type": "verdict_conflict",
                "scope": "school",
                "detail": "同一候选在不同派别下结论互斥（一派判不可用，一派判可用）",
                "states": dict(states),
            }
        )
    elif len(set(states.values())) > 1:
        conflicts.append(
            {
                "type": "state_divergence",
                "scope": "school",
                "detail": "同一候选在不同派别下三态不一致（非互斥，但必须并列呈现）",
                "states": dict(states),
            }
        )

    # 4. 口径分歧
    by_category: dict[str, dict[str, str]] = {}
    for name, res in per_school.items():
        for j in res.vetoes + res.cautions + res.positives:
            by_category.setdefault(j.category, {})[name] = j.severity
    for category, severities in by_category.items():
        if len(set(severities.values())) > 1:
            conflicts.append(
                {
                    "type": "policy_divergence",
                    "scope": "school",
                    "category": category,
                    "detail": "同一类别规则在不同派别下严重度不同",
                    "severities": severities,
                }
            )
    return conflicts


# --------------------------------------------------------------------------- #
# 主入口
# --------------------------------------------------------------------------- #
def evaluate(
    ctx: dict[str, Any],
    registry: RuleRegistry,
    cfg: EvalConfig,
) -> Evaluation:
    """对单个候选（ctx 已含四柱与 facts）执行全派评估。"""
    schools = cfg.schools if cfg.schools is not None else registry.policy.route(cfg.task_kind)
    if not schools:
        raise ValueError(f"没有可用派别（task_kind={cfg.task_kind}）")

    rule_lib_version = registry.ruleset.version
    # 必需规则集：未显式指定时由 registry 按 task_kind 注入（ADR-0010）
    person_provided = bool((ctx.get("person") or {}).get("year_zhi"))
    required_ids = cfg.required_rule_ids or registry.required_for(
        cfg.task_kind, person_provided=person_provided
    )
    if required_ids != cfg.required_rule_ids:
        cfg = replace(cfg, required_rule_ids=tuple(required_ids))
    # 输入哈希每个候选只算一次（曾因逐规则计算导致 4380 候选超时）
    input_hash = ctx.get("_meta", {}).get("input_hash") or stable_hash(
        {k: v for k, v in ctx.items() if k != "facts"}
    )
    # fact_hash 必须包含**完整约定**（day_boundary / 时间基准 / 口径），
    # 否则"同 fact 不同口径"会被误判为一致（ADR-0011）。
    # 注意：不同约定下 hash 不同是**预期**的；若两派约定不同，应通过多次 evaluate 对比，
    # 而不是在同一 evaluate 内混合（那才是 bug，故下面仍做一致性断言）。
    fact_hash = _convention_hash(ctx)

    per_school: dict[str, SchoolResult] = {}
    for school in schools:
        spec = registry.policy.schools.get(school)
        if spec is None:
            raise ValueError(f"未声明的派别: {school}")
        if not spec.enabled and cfg.schools is None:
            continue
        rules = _select_cached(
            registry.ruleset,
            schools=(school,),
            task_kind=cfg.task_kind,
            node_kind=cfg.node_kind,
            strictness=cfg.strictness,
            include_unverified=True,  # 全量取回，由 status 决定是否参与
        )
        per_school[school] = _evaluate_school(
            rules,
            ctx,
            cfg,
            school=school,
            rule_lib_version=rule_lib_version,
            veto_enabled=spec.participates_in_veto,
            input_hash=input_hash,
            fact_hash=fact_hash,
        )

    if not per_school:
        raise ValueError("没有启用的派别可评估")

    # 各派必须看到完全相同的输入事实，否则分歧度指标被污染
    fact_hashes = {res.fact_hash for res in per_school.values()}
    if len(fact_hashes) > 1:  # pragma: no cover - 结构性断言
        raise AssertionError(f"各派 fact_hash 不一致，分歧度不可比: {fact_hashes}")

    # 综合三态 = 各派最严（不合并分数，只取最严状态）
    overall = max((r.state for r in per_school.values()), key=lambda s: _STATE_RANK[s])
    conflicts = _detect_conflicts(per_school)

    # ---- 全局结构判定（定义级，按 rule_id 去重）----
    structural_map: dict[str, Judgment] = {}
    for res in per_school.values():
        for j in res.structural:
            structural_map.setdefault(j.rule_id, j)
    structural = sorted(structural_map.values(), key=lambda j: j.rule_id)

    # ---- unknown 三分类统计 ----
    unknown_items: list[dict[str, Any]] = []
    for res in per_school.values():
        for j in res.unknowns:
            unknown_items.append(
                {
                    "rule_id": j.rule_id,
                    "school": j.school,
                    "category": j.category,
                    "status": j.status,
                    "reason": j.participation,
                    "unknown_reason": j.unknown_reason,
                    "remedy": j.remedy,
                    "unknown_paths": list(j.unknown_paths),
                    "warnings": list(j.warnings),
                }
            )

    by_reason: dict[str, int] = {}
    for item in unknown_items:
        key = item["unknown_reason"] or "unknown"
        by_reason[key] = by_reason.get(key, 0) + 1

    hard_fail = sum(len(r.vetoes) for r in per_school.values())
    assertion_caution = sum(len(r.cautions) for r in per_school.values())
    # 定义级结构不进 strong_avoid（ADR-0009）：它们只回答"是什么"
    strong_avoid = assertion_caution
    positive = sum(len(r.positives) for r in per_school.values())
    conflict_count = len(conflicts)
    unknown_count = len(unknown_items)
    note_count = sum(len(r.notes) for r in per_school.values())

    vectors = {
        "hard_fail_count": hard_fail,
        "strong_avoid_count": strong_avoid,
        "assertion_caution_count": assertion_caution,
        "structural_count": len(structural),
        "structural_record_count": len([j for j in structural if j.severity == "记录"]),
        "conflict_count": conflict_count,
        "unknown_count": unknown_count,
        "unknown_by_reason": by_reason,
        "unverified_hit_count": by_reason.get(UNKNOWN_UNVERIFIED, 0),
        "disputed_count": sum(1 for j in structural if j.status == "有争议"),
        "missing_input_count": by_reason.get(UNKNOWN_MISSING_INPUT, 0),
        "caliber_undecided_count": by_reason.get(UNKNOWN_CALIBER, 0),
        "note_count": note_count,
        "positive_count": positive,
        "demo_hit_count": sum(
            len(r.demo_hits)
            + sum(1 for j in r.vetoes + r.cautions + r.positives if j.is_demo)
            for r in per_school.values()
        ),
        # ADR-0014 决策 0：存疑命中计数（渲染层；不入 strong_avoid/tier）
        "controversial_count": sum(len(r.controversial) for r in per_school.values()),
        # ADR-0014 决策 1：声明/生效差异规则（load 期预计算，审计链双显示）
        "cap_applied_ids": sorted(registry.ruleset.cap_applied_ids),
        "verified_veto_count": sum(
            1 for r in per_school.values() for j in r.vetoes if not j.is_demo
        ),
        "demo_veto_count": sum(
            1 for r in per_school.values() for j in r.vetoes if j.is_demo
        ),
        "positive_vector": {
            name: [j.rule_id for j in res.positives] for name, res in per_school.items()
        },
        "feasibility_vector": ctx.get("task", {}).get("feasibility", {}),
    }

    if hard_fail > 0:
        tier = TIER_REJECTED
    elif strong_avoid > 0 or conflict_count > 0 or unknown_count > 0:
        tier = TIER_NEEDS_REVIEW
    elif positive >= 2 or (positive >= 1 and _total_rank(per_school) >= 1.0):
        tier = TIER_PREFERRED
    else:
        tier = TIER_ACCEPTABLE

    # ---- 必需集阻塞预计算（ADR-0012）----
    blocked_required: list[dict[str, Any]] = []
    seen_blocked: set[str] = set()
    for rid in required_ids:
        rule = registry.ruleset.by_id.get(rid)
        if rule is None:  # pragma: no cover - lint 已校验
            continue
        if rule.status not in ("已考证", "定义级"):
            blocked_required.append(
                {
                    "rule_id": rid,
                    "status": rule.status,
                    "reason": "规则未考证（其「不犯」结论不可作为发布依据）",
                }
            )
            seen_blocked.add(rid)
    for u in unknown_items:
        if u["rule_id"] in required_ids and u["rule_id"] not in seen_blocked:
            blocked_required.append(
                {
                    "rule_id": u["rule_id"],
                    "status": u["status"],
                    "reason": f"输入不足（{u.get('unknown_reason')}）",
                }
            )
            seen_blocked.add(u["rule_id"])

    # ---- 五派并列输出 schema（spec §4 仲裁层）----
    # tendency 先行：spec §4 冲突 = 两派 tendency 相反 → {schools, issue}，不裁决
    def _tendency_of(res: SchoolResult) -> str:
        if res.vetoes:
            return "unfavorable"
        if res.cautions:
            return "neutral"
        if res.positives:
            return "favorable"
        return "neutral"

    tendencies = {name: _tendency_of(res) for name, res in per_school.items()}
    conflicted = [n for n, t in tendencies.items() if t in ("favorable", "unfavorable")]
    conflicts_fso: list[dict[str, Any]] = []
    for i, s1 in enumerate(conflicted):
        for s2 in conflicted[i + 1:]:
            t1, t2 = tendencies[s1], tendencies[s2]
            if {t1, t2} == {"favorable", "unfavorable"}:
                conflicts_fso.append({"schools": [s1, s2], "issue": f"{s1}={t1} vs {s2}={t2}"})

    five_school_output = {}
    for school_name, school_spec in registry.policy.schools.items():
        if school_name in per_school:
            five_school_output[school_name] = _school_payload(
                school_name,
                per_school[school_name],
                registry.policy.schools[school_name].layer,
                tendencies[school_name],
                conflicts_fso,
            )
    tendency_list = [
        (name, d["overall_tendency"]) for name, d in five_school_output.items()
        if d["overall_tendency"] in ("favorable", "unfavorable")
    ]
    for i, (s1, t1) in enumerate(tendency_list):
        for s2, t2 in tendency_list[i+1:]:
            if (t1 == "favorable" and t2 == "unfavorable") or (t1 == "unfavorable" and t2 == "favorable"):
                conflicts_fso.append({"schools": [s1, s2], "issue": f"{s1}={t1} vs {s2}={t2}"})
    favorable_count = sum(1 for _, t in tendency_list if t == "favorable")
    unfavorable_count = sum(1 for _, t in tendency_list if t == "unfavorable")
    if unfavorable_count > 0:
        consensus = "unfavorable"
    elif favorable_count >= 3:
        consensus = "favorable"
    elif favorable_count > 0:
        consensus = "mixed"
    else:
        consensus = "neutral"
    five_school_output["_consensus"] = consensus
    five_school_output["_conflicts"] = conflicts_fso

    manifest = {
        "input_hash": input_hash,
        "facts_hash": fact_hash,
        "rule_lib_version": rule_lib_version,
        "engine_version": ENGINE_VERSION,
        "config": cfg.to_dict(),
        "five_school_output": five_school_output,
        "schools": list(per_school),
        "rule_counts": {name: res.rules_evaluated for name, res in per_school.items()},
    }


    return Evaluation(
        candidate=str(
            ctx.get("time", {}).get("datetime") or ctx.get("course", {}).get("datetime") or ""
        ),
        per_school=per_school,
        state=overall,
        tier=tier,
        vectors=vectors,
        conflicts=conflicts,
        unknowns=unknown_items,
        manifest=manifest,
        config=cfg,
        structural=structural,
        required_rule_ids=tuple(required_ids),
        blocked_required=blocked_required,
    )


def _convention_hash(ctx: dict[str, Any]) -> str:
    """事实哈希 = facts + **完整约定**（日界 / 时间基准 / 口径）。

    为什么必须含约定：若只哈希 facts，两套口径下算出的四柱可能相同（碰巧），
    但"同 fact 不同口径"被误判为一致，分歧度指标就失去意义。
    反之，不同约定下 hash 不同是**预期**的，不是错误。
    """
    time_ctx = ctx.get("time", {})
    return stable_hash(
        {
            "facts": ctx.get("facts", {}),
            "convention": {
                "day_boundary": time_ctx.get("day_boundary"),
                "use_true_solar_time": time_ctx.get("use_true_solar_time"),
                "ym_time_ref": time_ctx.get("ym_time_ref"),
                "hour_time_ref": time_ctx.get("hour_time_ref"),
                "calibers": (ctx.get("facts", {}) or {}).get("_calibers"),
            },
        }
    )


def _total_rank(per_school: dict[str, SchoolResult]) -> float:
    scores = [r.rank_score for r in per_school.values() if r.rank_score is not None]
    return sum(scores) / len(scores) if scores else 0.0


_ = SEVERITIES
