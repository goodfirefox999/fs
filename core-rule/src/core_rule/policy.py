"""派别策略与事项模板（规则层，配置即数据）。

铁律：``task_kind → 参与派别列表`` 的路由必须是数据，**禁止**在代码里写 if-else 分支。
争议大的派（斗首、玄空大卦）默认 ``participates_in_veto: false``，只进参考层。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import DSLValidationError

__all__ = [
    "SchoolPolicy",
    "SchoolSpec",
    "TaskKindSpec",
    "RequiredRuleSet",
    "ConsensusSpec",
    "ConsensusPolicy",
    "load_school_policy",
    "load_task_kinds",
    "load_required_rules",
    "load_consensus_config",
    "SchoolPolicy.route",
]


@dataclass(frozen=True)
class SchoolSpec:
    """一个派别的策略。

    layer 字段（评审扩展版 spec §1 + Phase 9）：
    - reject：共享前置大煞层——触达即 rejected_dates，不进五派评分
    - scoring：五派评分层——并列输出，互不覆盖
    - reference：参考层——**默认不入路由**，仅用户显式勾选时评估；
      输出与五派并列但明确标注「参考层」，不参与 veto、不改 tier。
      用于吉凶强度尚未考证的派别（如斗首），避免未考证口径进入发布判据。
    """

    name: str
    enabled: bool = True
    participates_in_veto: bool = True
    weight: float = 1.0
    description: str = ""
    layer: str = "scoring"  # reject | scoring | reference

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "layer": self.layer,
            "participates_in_veto": self.participates_in_veto,
            "weight": self.weight,
            "description": self.description,
        }


@dataclass(frozen=True)
class SchoolPolicy:
    """派别总策略：启用集合 + 场景路由 + 事件权重排序。

    event_weights（评审扩展版 spec §4）：事件类型 → 五派评分优先序。
    仲裁层读取此表决定各派 score_delta 的展示排序；不合并分数。
    """

    schools: dict[str, SchoolSpec]
    routing: dict[str, tuple[str, ...]] = field(default_factory=dict)
    default_route: tuple[str, ...] = ()
    event_weights: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def enabled_schools(self) -> tuple[str, ...]:
        return tuple(sorted(n for n, s in self.schools.items() if s.enabled))

    def route(self, task_kind: str | None) -> tuple[str, ...]:
        """``task_kind`` → 参与派别列表（数据驱动）。"""
        if task_kind and task_kind in self.routing:
            route = self.routing[task_kind]
        else:
            route = self.default_route or self.enabled_schools()
        return tuple(s for s in route if s in self.schools and self.schools[s].enabled)

    def veto_schools(self, task_kind: str | None) -> tuple[str, ...]:
        """参与否决的派别（``participates_in_veto`` 为真者）。"""
        return tuple(s for s in self.route(task_kind) if self.schools[s].participates_in_veto)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schools": {k: v.to_dict() for k, v in self.schools.items()},
            "routing": {k: list(v) for k, v in self.routing.items()},
            "default_route": list(self.default_route),
        }


def load_school_policy(path: Path | str) -> SchoolPolicy:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "schools" not in data:
        raise DSLValidationError(f"school_policy 缺少 schools 段: {path}")
    schools: dict[str, SchoolSpec] = {}
    for name, spec in (data["schools"] or {}).items():
        spec = spec or {}
        layer = str(spec.get("layer", "scoring"))
        if layer not in ("reject", "scoring", "reference"):
            raise DSLValidationError(
                f"{name} 的 layer 非法（reject|scoring|reference）: {layer}"
            )
        schools[name] = SchoolSpec(
            name=name,
            enabled=bool(spec.get("enabled", True)),
            participates_in_veto=bool(spec.get("participates_in_veto", True)),
            weight=float(spec.get("weight", 1.0)),
            description=str(spec.get("description", "")),
            layer=layer,
        )
    routing_raw = data.get("routing") or {}
    routing = {k: tuple(v or ()) for k, v in routing_raw.items()}
    default_route = tuple(data.get("default_route") or ())
    for target in list(routing.values()) + ([default_route] if default_route else []):
        for name in target:
            if name not in schools:
                raise DSLValidationError(f"路由引用了未声明的派别: {name}", path=str(path))
    ew = {}
    for ek, ev in (data.get("event_weights") or {}).items():
        ew[ek] = tuple(ev)
    return SchoolPolicy(schools=schools, routing=routing, default_route=default_route, event_weights=ew)


@dataclass(frozen=True)
class TaskKindSpec:
    """事项模板。"""

    kind: str
    required_nodes: tuple[str, ...] = ()
    applicable_rule_tags: tuple[str, ...] = ()
    forbidden_rule_tags: tuple[str, ...] = ()
    default_strictness: str = "normal"
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "required_nodes": list(self.required_nodes),
            "applicable_rule_tags": list(self.applicable_rule_tags),
            "forbidden_rule_tags": list(self.forbidden_rule_tags),
            "default_strictness": self.default_strictness,
            "description": self.description,
        }


def load_task_kinds(path: Path | str) -> dict[str, TaskKindSpec]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "task_kinds" not in data:
        raise DSLValidationError(f"task_kinds 缺少 task_kinds 段: {path}")
    out: dict[str, TaskKindSpec] = {}
    for kind, spec in (data["task_kinds"] or {}).items():
        spec = spec or {}
        strictness = spec.get("default_strictness", "normal")
        if strictness not in ("normal", "strict"):
            raise DSLValidationError(f"{kind} 的 default_strictness 非法: {strictness}")
        out[kind] = TaskKindSpec(
            kind=kind,
            required_nodes=tuple(spec.get("required_nodes") or ()),
            applicable_rule_tags=tuple(spec.get("applicable_rule_tags") or ()),
            forbidden_rule_tags=tuple(spec.get("forbidden_rule_tags") or ()),
            default_strictness=strictness,
            description=str(spec.get("description", "")),
        )
    return out


@dataclass(frozen=True)
class RequiredRuleSet:
    """事项 → 必需规则 id 列表（ADR-0012）。

    结构：``default.core``（无输入依赖）+ ``default.person_dependent``（依赖命主）
    + ``overrides[task_kind]``（``add`` / ``remove``）。

    **语义边界**：必需集满足只代表"安全底线"——这些规则覆盖的风险不会漏判；
    **不代表**规则集完备，也不代表该日期可用。
    """

    core: tuple[str, ...] = ()
    person_dependent: tuple[str, ...] = ()
    overrides: dict[str, dict[str, tuple[str, ...]]] = field(default_factory=dict)
    criteria: dict[str, Any] = field(default_factory=dict)

    def for_task(self, task_kind: str, *, person_provided: bool = False) -> tuple[str, ...]:
        """返回该事项**实际生效**的必需规则（已按条件过滤）。

        ``person_provided=False`` 时不包含 ``person_dependent`` ——
        否则用户不填命主就会永久 unknown，publishable 恒 false（Q-011 元规则）。
        """
        base: list[str] = list(self.core)
        if person_provided:
            base.extend(self.person_dependent)
        ov = self.overrides.get(task_kind) or {}
        remove = set(ov.get("remove") or ())
        base = [rid for rid in base if rid not in remove]
        base.extend(ov.get("add") or ())
        # 去重保序
        seen: set[str] = set()
        out: list[str] = []
        for rid in base:
            if rid not in seen:
                seen.add(rid)
                out.append(rid)
        return tuple(out)

    def all_rule_ids(self) -> set[str]:
        out: set[str] = set(self.core) | set(self.person_dependent)
        for ov in self.overrides.values():
            out.update(ov.get("add") or ())
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "core": list(self.core),
            "person_dependent": list(self.person_dependent),
            "overrides": {k: {kk: list(vv) for kk, vv in v.items()} for k, v in self.overrides.items()},
            "criteria": dict(self.criteria),
        }


def load_required_rules(path: Path | str) -> RequiredRuleSet:
    """加载 ``required_rules.yaml``（ADR-0012 的 core/person_dependent/overrides 结构）。"""
    p = Path(path)
    if not p.exists():
        return RequiredRuleSet()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise DSLValidationError(f"{p}: 顶层必须是映射")
    default = data.get("default") or {}
    overrides: dict[str, dict[str, tuple[str, ...]]] = {}
    for task_kind, spec in (data.get("overrides") or {}).items():
        spec = spec or {}
        overrides[task_kind] = {
            "add": tuple(spec.get("add") or ()),
            "remove": tuple(spec.get("remove") or ()),
        }
    return RequiredRuleSet(
        core=tuple(default.get("core") or ()),
        person_dependent=tuple(default.get("person_dependent") or ()),
        overrides=overrides,
        criteria=dict(data.get("admission_criteria") or {}),
    )


@dataclass(frozen=True)
class ConsensusSpec:
    """共识阈值：**整数比** ``min_agree_num / min_agree_den``（ADR-0015）。

    为什么是整数比而不是 0.6：
    浮点阈值一旦出现在门禁路径上，下游就会顺手拿它去乘权重、算"综合分"。
    整数比只能做交叉相乘比较，从类型上堵死加权求和。
    """

    min_agree_num: int = 3
    min_agree_den: int = 5
    description: str = ""

    def reached(self, favorable: int, voters: int) -> bool:
        """``favorable/voters >= num/den``，全程整数运算。

        ``voters == 0`` 时返回 False —— 无人表态不构成共识，
        由调用方输出 ``insufficient`` 语义，不得默认通过。
        """
        if voters <= 0 or self.min_agree_den <= 0:
            return False
        return favorable * self.min_agree_den >= self.min_agree_num * voters

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_agree_num": self.min_agree_num,
            "min_agree_den": self.min_agree_den,
            "description": self.description,
        }


@dataclass(frozen=True)
class ConsensusPolicy:
    """共识口径：缺省 + 按事项覆写（覆写为空是有意的，见 consensus.yaml 注释）。"""

    default: ConsensusSpec = field(default_factory=ConsensusSpec)
    overrides: dict[str, ConsensusSpec] = field(default_factory=dict)

    def for_task(self, task_kind: str | None) -> ConsensusSpec:
        if task_kind and task_kind in self.overrides:
            return self.overrides[task_kind]
        return self.default

    def to_dict(self) -> dict[str, Any]:
        return {
            "default": self.default.to_dict(),
            "overrides": {k: v.to_dict() for k, v in self.overrides.items()},
        }


def _load_consensus_spec(raw: dict[str, Any], where: str) -> ConsensusSpec:
    num = raw.get("min_agree_num", 3)
    den = raw.get("min_agree_den", 5)
    # bool 是 int 的子类，必须显式排除，否则 True 会被当成 1
    for field_name, value in (("min_agree_num", num), ("min_agree_den", den)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise DSLValidationError(
                f"{where} 的 {field_name} 必须是整数（禁止浮点阈值）: {value!r}"
            )
    if num <= 0 or den <= 0:
        raise DSLValidationError(f"{where} 的阈值必须为正: {num}/{den}")
    if num > den:
        raise DSLValidationError(f"{where} 的阈值不得大于 1: {num}/{den}")
    return ConsensusSpec(
        min_agree_num=num,
        min_agree_den=den,
        description=str(raw.get("description", "")),
    )


def load_consensus_config(path: Path | str) -> ConsensusPolicy:
    """加载 ``consensus.yaml``；文件缺失时退回缺省 3/5（不静默放行，只退回缺省）。"""
    p = Path(path)
    if not p.exists():
        return ConsensusPolicy()
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise DSLValidationError(f"{p}: 顶层必须是映射")
    default = _load_consensus_spec(data.get("default") or {}, f"{p}: default")
    overrides: dict[str, ConsensusSpec] = {}
    for task_kind, spec in (data.get("overrides") or {}).items():
        overrides[task_kind] = _load_consensus_spec(spec or {}, f"{p}: overrides.{task_kind}")
    return ConsensusPolicy(default=default, overrides=overrides)

