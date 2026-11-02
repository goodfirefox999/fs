"""规则数据模型与枚举（规则层）。

状态与严重度取值严格对齐 docs/DEVELOPMENT.md 第 5.1 节，不得擅自增删。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from .provenance import Citation

__all__ = [
    "RuleStatus",
    "Severity",
    "Target",
    "Strictness",
    "AppliesTo",
    "Rule",
    "SEVERITY_ORDER",
    "DEFINITIONAL_SEVERITY",
    "ASSERTION_SEVERITIES",
]

RuleStatus = Literal["draft", "待考证", "定义级", "已考证", "有争议", "弃用"]
#: 严重度枚举。
#:
#: ``记录`` 是**定义级专用**的中性值：只陈述"结构是什么"，不表达"好不好"。
#: 它不进 vetoes / cautions / positives，**不影响 tier**（ADR-0009）。
Severity = Literal["禁用", "慎用", "可用", "推荐", "记录"]
Target = Literal["mountain", "facing", "day", "hour", "person", "node"]
Strictness = Literal["normal", "strict"]

#: 状态语义：
#: - ``draft``     草稿，未提交
#: - ``待考证``   口诀常见但原文未核（断言级）
#: - ``定义级``   干支系统的**算术推论**，出处为内核规格而非古籍（见 ADR-0007）
#: - ``已考证``   有古籍原文 + 人类签名
#: - ``有争议``   存在两种以上通行口径，需裁定
#: - ``弃用``     不再使用
RULE_STATUSES: tuple[str, ...] = ("draft", "待考证", "定义级", "已考证", "有争议", "弃用")
SEVERITIES: tuple[str, ...] = ("禁用", "慎用", "可用", "推荐", "记录")

#: 定义级规则唯一允许的严重度
DEFINITIONAL_SEVERITY = "记录"

#: 吉凶断言类严重度（定义级不得使用）
ASSERTION_SEVERITIES: tuple[str, ...] = ("禁用", "慎用", "可用", "推荐")
TARGETS: tuple[str, ...] = ("mountain", "facing", "day", "hour", "person", "node")
STRICTNESS_ORDER: dict[str, int] = {"normal": 0, "strict": 1}

#: 严重度强弱（用于聚合，不用于"加减分"）。``记录`` 不在吉凶序列内，置为 -1。
SEVERITY_ORDER: dict[str, int] = {"禁用": 3, "慎用": 2, "可用": 1, "推荐": 0, "记录": -1}


class StatusEnum(str, Enum):
    """仅供外部工具使用；内部一律用字符串字面量。"""

    DRAFT = "draft"
    PENDING = "待考证"
    VERIFIED = "已考证"
    DISPUTED = "有争议"
    DEPRECATED = "弃用"


@dataclass(frozen=True)
class AppliesTo:
    """规则的适用范围。空元组表示"不限"。"""

    task_kinds: tuple[str, ...] = ()
    node_kinds: tuple[str, ...] = ()
    strictness_min: Strictness = "normal"

    def matches(self, *, task_kind: str, node_kind: str | None, strictness: str) -> bool:
        if self.task_kinds and task_kind not in self.task_kinds:
            return False
        if self.node_kinds and node_kind not in self.node_kinds:
            return False
        if STRICTNESS_ORDER.get(strictness, 0) < STRICTNESS_ORDER.get(self.strictness_min, 0):
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_kinds": list(self.task_kinds),
            "node_kinds": list(self.node_kinds),
            "strictness_min": self.strictness_min,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AppliesTo":
        data = data or {}
        return cls(
            task_kinds=tuple(data.get("task_kinds") or ()),
            node_kinds=tuple(data.get("node_kinds") or ()),
            strictness_min=data.get("strictness_min") or "normal",
        )


@dataclass(frozen=True)
class Rule:
    """一条规则。不可变对象，便于缓存与哈希。"""

    rule_id: str
    version: int
    school: str
    category: str
    status: RuleStatus
    hard_veto: bool
    severity: Severity
    target: Target
    applies_to: AppliesTo
    condition: dict[str, Any]
    citation: Citation
    explanation: str
    tests: tuple[str, ...] = ()
    score_weight: float | None = None
    #: 起例未实现/口径未定的规则标 false：保留在规则库（完整性）但**排除出评估集**——
    # 避免 (provided=True, value=None) 事实经 exists 算子渲染成"确定无此禁忌"的假阴性
    # （Q-014；评审第十三/十四轮）。裁定+起例实现后改回 true 走正常考证流程。
    evaluable: bool = True
    #: C 第一批（2026-11-02）：判定类型。
    #: ``gate`` = 闸门（否决/过滤，不参与打分）；``vote`` = 投票（正负证据，进分层向量）；
    #: ``reference`` = 只展示不判定。``None`` = 尚未标注（迁移期允许，lint 计数不阻断）。
    verdict_type: str | None = None
    #: 所属层；``reference`` 表示参考层（与 school_policy.layer 同义，规则级覆盖）
    layer: str | None = None
    #: 是否允许进入结论强度（state/tier/positives）。False = 只渲染，不进任何强度桶。
    #: 与 ``evaluable=False`` 的区别：evaluable 是"不评估"，本项是"评估但不计分"。
    engine_eligible: bool = True
    #: engine_eligible=False 的理由（机器可读枚举，如 ``day_yuan_undecided``）
    ineligible_reason: str | None = None
    supersedes: str | None = None
    api_version: int = 1
    notes: str | None = None
    #: 按派别覆盖严重度（{school: severity}）。用于"同一条规则在严格派是否决、在宽派是强忌"
    severity_overrides: dict[str, str] = field(default_factory=dict)
    source_path: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    # ---- 派生属性 ----
    @property
    def is_veto(self) -> bool:
        """是否构成否决（硬禁）。只有 ``hard_veto`` 且 ``severity=禁用`` 才算。"""
        return self.hard_veto and self.severity == "禁用"

    @property
    def is_caution(self) -> bool:
        return self.severity == "慎用"

    @property
    def is_definitional(self) -> bool:
        """是否为**定义级**规则（干支算术推论，出处为内核规格而非古籍）。

        定义级规则参与正式判定，但其结论只描述"结构是什么"，不描述"好不好"。
        """
        return self.status == "定义级"

    @property
    def effective_verdict_type(self) -> str:
        """生效判定类型；**未标注返回 ``unspecified``，不猜 ``vote``**。

        为什么不再兜底成 vote（2026-11-03）：
        兜底会让"没人管过"与"明确设计为投票"在报告上无法区分——前者是待办，
        后者是结论。把未决伪装成已分类，比留空更难发现。

        ``gate`` 的推断保留：``hard_veto=True + severity=禁用`` 在语义上只能是闸门，
        属定义级推断；而 ``vote`` 不是（可用/推荐/慎用都可能只是暂未归类）。
        """
        if self.verdict_type:
            return self.verdict_type
        if self.hard_veto and self.severity == "禁用":
            return "gate"
        return "unspecified"

    @property
    def is_participating(self) -> bool:
        """是否可参与正式判定。

        ``已考证``（有古籍原文）与 ``定义级``（有内核规格）可直接参与；
        ``待考证/有争议`` 需 ``--allow-unverified`` 显式放行。
        """
        return self.status in ("已考证", "定义级")

    @property
    def needs_signature(self) -> bool:
        """该规则的状态变更是否需要人类签名。"""
        return self.status in ("已考证", "有争议", "弃用")

    def severity_for(self, school: str) -> Severity:
        """返回该规则在指定派别下的严重度（支持 ``severity_overrides``）。"""
        override = self.severity_overrides.get(school)
        return override if override in SEVERITIES else self.severity  # type: ignore[return-value]

    def key(self) -> tuple[str, int]:
        return (self.rule_id, self.version)

    def to_dict(self) -> dict[str, Any]:
        return {
            "api_version": self.api_version,
            "rule_id": self.rule_id,
            "version": self.version,
            "school": self.school,
            "category": self.category,
            "status": self.status,
            "hard_veto": self.hard_veto,
            "severity": self.severity,
            "target": self.target,
            "applies_to": self.applies_to.to_dict(),
            "condition": self.condition,
            "score_weight": self.score_weight,
            "citation": self.citation.to_dict(),
            "tests": list(self.tests),
            "explanation": self.explanation,
            "supersedes": self.supersedes,
            "notes": self.notes,
            "severity_overrides": dict(self.severity_overrides),
            "verdict_type": self.verdict_type,
            "layer": self.layer,
            "engine_eligible": self.engine_eligible,
            "ineligible_reason": self.ineligible_reason,
        }
