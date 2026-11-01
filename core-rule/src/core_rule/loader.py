"""规则加载与校验（规则层）。

加载期即完成全部结构校验：字段、枚举、条件树、白名单、引文完整性、``tests`` 数量。
**不允许**把非法规则带进运行期 —— 这是"规则污染"红线的第一道闸门。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from .dsl import collect_fact_paths, condition_depth, validate_condition
from .errors import DSLValidationError
from .severity_cap import effective_severity
from .models import (
    ASSERTION_SEVERITIES,
    DEFINITIONAL_SEVERITY,
    RULE_STATUSES,
    SEVERITIES,
    STRICTNESS_ORDER,
    TARGETS,
    AppliesTo,
    Rule,
)
from .provenance import Citation, stable_hash

__all__ = ["RuleSet", "load_rule", "load_ruleset", "RULE_ID_PATTERN"]

#: 规则 id 格式：派别缩写-类别（可多段）-三位序号，如 PUB-SANSHA-001 / PUB-MING-SANSHA-001
RULE_ID_PATTERN = re.compile(r"^[A-Z]{2,8}(?:-[A-Z0-9]+)+-\d{3}$")

_REQUIRED_FIELDS = (
    "rule_id",
    "version",
    "school",
    "category",
    "status",
    "severity",
    "target",
    "condition",
    "citation",
    "explanation",
    "tests",
)


@dataclass(frozen=True)
class RuleSet:
    """一次加载得到的规则库快照。``version`` 由内容哈希决定，可复现。"""

    rules: tuple[Rule, ...]
    version: str
    by_id: dict[str, Rule]
    by_school: dict[str, tuple[Rule, ...]]
    #: 规则 id 元组（预计算，供缓存 key 使用；每次现算会有 456k 次字符串操作开销）
    rule_ids: tuple[str, ...] = ()
    #: ADR-0014 决策 1：声明>上限的规则 id 集（load 期预计算；cap 警告按 run 聚合，
    #: 不进 per-candidate 循环）。__post_init__ 派生，dc_replace 也会重算。
    cap_applied_ids: frozenset[str] = frozenset()
    #: 规则库**内容指纹**（ADR-0012 教训的机制化，第三次串味实证后引入）：
    #: version 只是 (rule_id, version) 哈希——同 id 同 version 改内容/状态不改变 version。
    #: fingerprint 覆盖 (id, version, status, severity, hard_veto, condition 内容哈希)，
    #: 所有缓存 key 必须含它；手写 key 的路径由评审要求逐步收拢到本字段。
    fingerprint: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "cap_applied_ids",
            frozenset(
                r.rule_id for r in self.rules if effective_severity(r) != r.severity
            ),
        )
        object.__setattr__(
            self,
            "fingerprint",
            # 结构性穷举（评审第十四轮：反射测试连续抓到 school/category 缺口后的本质修法）：
            # 直接哈希每条规则的 **raw YAML 全量 dict**——天然覆盖现有与未来的一切字段
            # （含 school/category/applies_to/citation.book_authenticity/evaluable…），
            # 反射穷举测试从此作为守卫而非依赖清单
            stable_hash(
                sorted((r.rule_id, stable_hash(r.raw)) for r in self.rules)
            ),
        )

    def get(self, rule_id: str) -> Rule:
        return self.by_id[rule_id]

    def schools(self) -> tuple[str, ...]:
        return tuple(sorted(self.by_school))

    def select(
        self,
        *,
        schools: Iterable[str] | None = None,
        task_kind: str | None = None,
        node_kind: str | None = None,
        strictness: str = "normal",
        include_unverified: bool = False,
    ) -> tuple[Rule, ...]:
        """按适用范围筛选规则。

        ``include_unverified=False`` 时，``待考证``/``draft`` 规则不进入判定
        （但仍会在 engine 中作为 unknown 登记，见 4.3 节与"未知必须暴露"要求）。
        ADR-0014 C12：``有争议`` 规则默认参与评估（判定（存疑）），故随 ``已考证`` 放行。
        """
        allowed_schools = set(schools) if schools is not None else None
        out: list[Rule] = []
        for rule in self.rules:
            if rule.status == "弃用" or not rule.evaluable:
                continue  # 弃用 / 起例未实现排除出评估集（Q-014，ADR-0014 后续）
            if allowed_schools is not None and rule.school not in allowed_schools:
                continue
            if not include_unverified and rule.status not in ("已考证", "有争议"):
                continue
            if task_kind is not None and not rule.applies_to.matches(
                task_kind=task_kind, node_kind=node_kind, strictness=strictness
            ):
                continue
            out.append(rule)
        return tuple(out)

    def stats(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        by_school: dict[str, int] = {}
        for rule in self.rules:
            by_status[rule.status] = by_status.get(rule.status, 0) + 1
            by_school[rule.school] = by_school.get(rule.school, 0) + 1
        return {
            "total": len(self.rules),
            "by_status": by_status,
            "by_school": by_school,
            "version": self.version,
        }


def _require(data: dict[str, Any], key: str, path: Path) -> Any:
    if key not in data or data[key] is None:
        raise DSLValidationError(f"缺少必填字段 {key}", path=str(path))
    return data[key]


def load_rule(path: Path) -> Rule:
    """加载单条规则文件并完成全部校验。"""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:  # pragma: no cover - YAML 语法错误
        raise DSLValidationError(f"YAML 解析失败: {exc}", path=str(path)) from exc
    if not isinstance(raw, dict):
        raise DSLValidationError("规则文件顶层必须是映射", path=str(path))

    api_version = raw.get("api_version", 1)
    if api_version != 1:
        raise DSLValidationError(f"不支持的 api_version: {api_version}", path=str(path))

    for key in _REQUIRED_FIELDS:
        _require(raw, key, path)

    rule_id = str(raw["rule_id"])
    if not RULE_ID_PATTERN.match(rule_id):
        raise DSLValidationError(
            f"rule_id 格式非法: {rule_id}（应形如 PUB-SANSHA-001）", rule_id=rule_id, path=str(path)
        )

    version = raw["version"]
    if not isinstance(version, int) or version < 1:
        raise DSLValidationError("version 必须是 >=1 的整数", rule_id=rule_id)

    status = raw["status"]
    if status not in RULE_STATUSES:
        raise DSLValidationError(f"非法 status: {status}", rule_id=rule_id)

    severity = raw["severity"]
    if severity not in SEVERITIES:
        raise DSLValidationError(f"非法 severity: {severity}", rule_id=rule_id)

    target = raw["target"]
    if target not in TARGETS:
        raise DSLValidationError(f"非法 target: {target}", rule_id=rule_id)

    hard_veto = bool(raw.get("hard_veto", False))
    if hard_veto and severity not in ("禁用", "慎用"):
        raise DSLValidationError(
            f"hard_veto=true 时 severity 只能是 禁用/慎用，得到 {severity}", rule_id=rule_id
        )

    score_weight = raw.get("score_weight")
    if hard_veto and score_weight is not None:
        raise DSLValidationError(
            "veto 规则的 score_weight 必须为 null（禁止把硬伤折算成分数）", rule_id=rule_id
        )
    if score_weight is not None and not isinstance(score_weight, (int, float)):
        raise DSLValidationError("score_weight 必须是数值或 null", rule_id=rule_id)

    applies_raw = raw.get("applies_to") or {}
    if not isinstance(applies_raw, dict):
        raise DSLValidationError("applies_to 必须是映射", rule_id=rule_id)
    strictness_min = applies_raw.get("strictness_min", "normal")
    if strictness_min not in STRICTNESS_ORDER:
        raise DSLValidationError(f"非法 strictness_min: {strictness_min}", rule_id=rule_id)
    applies_to = AppliesTo.from_dict(applies_raw)

    condition = raw["condition"]
    validate_condition(condition, rule_id=rule_id)
    depth = condition_depth(condition)
    if depth > 4:  # pragma: no cover - validate_condition 已保证
        raise DSLValidationError(f"条件树深度 {depth} 超过上限 4", rule_id=rule_id)

    citation_raw = raw["citation"]
    if not isinstance(citation_raw, dict):
        raise DSLValidationError("citation 必须是映射", rule_id=rule_id)
    citation = Citation.from_dict(citation_raw)
    if not citation.source:
        raise DSLValidationError("citation.source 不得为空（至少写明书名）", rule_id=rule_id)

    if status == "已考证":
        if citation.kind != "classic":
            raise DSLValidationError(
                "status=已考证 时 citation.kind 必须为 classic（古籍原文）", rule_id=rule_id
            )
        if not citation.has_quote:
            raise DSLValidationError(
                "status=已考证 时 citation.quote 不得为空（禁止无原文的已考证）", rule_id=rule_id
            )
        if not citation.verified_by:
            raise DSLValidationError(
                "status=已考证 时 citation.verified_by 不得为空（须人类签名）", rule_id=rule_id
            )
        # 最大风险：把「通行口径」当「原文」录（评审 2026-11-01 第四轮）
        if citation.quote_kind != "原文":
            raise DSLValidationError(
                "status=已考证 时 citation.quote_kind 必须为「原文」（不得用白话转述/通行口径冒充）",
                rule_id=rule_id,
            )
        if not citation.pian and not citation.juan:
            raise DSLValidationError(
                "status=已考证 时必须至少给出 pian（篇次）或 juan（卷次）", rule_id=rule_id
            )

    if status == "定义级":
        # 定义级 = 干支算术推论，出处是内核规格而非古籍（ADR-0007）。
        # 四条硬约束防止"把吉凶断言伪装成定义级"（ADR-0009 加严）：
        if citation.kind != "spec":
            raise DSLValidationError(
                "status=定义级 时 citation.kind 必须为 spec（内核规格条款）", rule_id=rule_id
            )
        if not citation.has_quote:
            raise DSLValidationError(
                "status=定义级 时 citation.quote 必须写明规格条款原文（如关系表内容）", rule_id=rule_id
            )
        if hard_veto:
            raise DSLValidationError(
                "定义级规则不得为硬否决 —— 否决是吉凶断言，必须走 待考证→已考证", rule_id=rule_id
            )
        # ★ 核心约束：定义级只能"记录"，不得携带任何吉凶严重度
        if severity != DEFINITIONAL_SEVERITY:
            raise DSLValidationError(
                f"定义级规则的 severity 只能是「{DEFINITIONAL_SEVERITY}」，得到「{severity}」。"
                "吉凶判断（禁用/慎用/可用/推荐）一律归断言级规则，见 ADR-0009",
                rule_id=rule_id,
            )
    elif severity == DEFINITIONAL_SEVERITY:
        raise DSLValidationError(
            f"severity=「{DEFINITIONAL_SEVERITY}」仅限 status=定义级 使用，得到 status={status}",
            rule_id=rule_id,
        )

    tests = raw["tests"]
    if not isinstance(tests, list) or len(tests) < 2:
        raise DSLValidationError(
            "tests 至少需要 2 项（≥1 命中 + ≥1 不命中）", rule_id=rule_id
        )
    if not all(isinstance(t, str) and t for t in tests):
        raise DSLValidationError("tests 元素必须是非空字符串（case_id）", rule_id=rule_id)
    if len(set(tests)) != len(tests):
        raise DSLValidationError("tests 中存在重复 case_id", rule_id=rule_id)

    explanation = raw["explanation"]
    if not isinstance(explanation, str) or not explanation.strip():
        raise DSLValidationError("explanation 不得为空（模板化解释）", rule_id=rule_id)

    severity_overrides_raw = raw.get("severity_overrides") or {}
    if not isinstance(severity_overrides_raw, dict):
        raise DSLValidationError("severity_overrides 必须是映射 {school: severity}", rule_id=rule_id)
    for school_name, sev in severity_overrides_raw.items():
        if sev not in SEVERITIES:
            raise DSLValidationError(
                f"severity_overrides[{school_name}] 非法严重度: {sev}", rule_id=rule_id
            )
        if status == "定义级" and sev != DEFINITIONAL_SEVERITY:
            raise DSLValidationError(
                f"定义级规则不得用 severity_overrides 引入吉凶严重度（{school_name}={sev}）",
                rule_id=rule_id,
            )
        if status != "定义级" and sev == DEFINITIONAL_SEVERITY:
            raise DSLValidationError(
                f"severity_overrides 不得把断言级规则降为「{DEFINITIONAL_SEVERITY}」", rule_id=rule_id
            )
        if hard_veto and sev not in ("禁用", "慎用"):
            raise DSLValidationError(
                f"veto 规则的 severity_overrides[{school_name}] 只能是 禁用/慎用", rule_id=rule_id
            )

    # evaluable=false：起例未实现/口径未定的规则保留在库但排除出评估集（Q-014；
    # 评审第十三/十四轮）——仅限待考证（已考证/定义级规则必须可评估）
    evaluable = bool(raw.get("evaluable", True))
    if not evaluable and status != "待考证":
        raise DSLValidationError(
            f"evaluable=false 仅限 status=待考证（当前 {status}）", rule_id=rule_id
        )

    return Rule(
        rule_id=rule_id,
        version=version,
        school=str(raw["school"]),
        category=str(raw["category"]),
        status=status,
        hard_veto=hard_veto,
        severity=severity,
        target=target,
        applies_to=applies_to,
        condition=condition,
        citation=citation,
        explanation=explanation,
        tests=tuple(tests),
        score_weight=score_weight,
        supersedes=raw.get("supersedes"),
        api_version=api_version,
        notes=raw.get("notes"),
        severity_overrides={k: str(v) for k, v in severity_overrides_raw.items()},
        source_path=str(path),
        raw=raw,
        evaluable=evaluable,
    )


def load_ruleset(root: Path | str, *, version: str | None = None) -> RuleSet:
    """递归加载目录下全部 ``*.yaml`` 规则。重复 ``rule_id`` 直接报错。"""
    root = Path(root)
    if not root.exists():
        raise FileNotFoundError(f"规则目录不存在: {root}")
    files = sorted(p for p in root.rglob("*.yaml") if p.is_file())
    rules: list[Rule] = []
    seen: dict[str, Path] = {}
    for path in files:
        rule = load_rule(path)
        if rule.rule_id in seen:
            raise DSLValidationError(
                f"rule_id 重复: {rule.rule_id}（{seen[rule.rule_id]} 与 {path}）", rule_id=rule.rule_id
            )
        seen[rule.rule_id] = path
        rules.append(rule)

    rules.sort(key=lambda r: (r.school, r.rule_id))
    by_id = {r.rule_id: r for r in rules}
    by_school: dict[str, list[Rule]] = {}
    for rule in rules:
        by_school.setdefault(rule.school, []).append(rule)

    lib_version = version or "rl-" + stable_hash([(r.rule_id, r.version) for r in rules])
    return RuleSet(
        rules=tuple(rules),
        version=lib_version,
        by_id=by_id,
        by_school={k: tuple(v) for k, v in by_school.items()},
        rule_ids=tuple(r.rule_id for r in rules),
    )


def all_fact_paths(rules: Iterable[Rule]) -> set[str]:
    """规则库引用的全部 fact 路径（供 lint 与文档生成）。"""
    paths: set[str] = set()
    for rule in rules:
        paths.update(collect_fact_paths(rule.condition))
    return paths
