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
    "load_school_policy",
    "load_task_kinds",
    "load_required_rules",
    "SchoolPolicy.route",
]


@dataclass(frozen=True)
class SchoolSpec:
    """一个派别的策略。

    layer 字段（评审扩展版 spec §1）：
    - reject：共享前置大煞层——触达即 rejected_dates，不进五派评分
    - scoring：五派评分层——并列输出，互不覆盖
    """

    name: str
    enabled: bool = True
    participates_in_veto: bool = True
    weight: float = 1.0
    description: str = ""
    layer: str = "scoring"  # reject | scoring

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
        schools[name] = SchoolSpec(
            name=name,
            enabled=bool(spec.get("enabled", True)),
            participates_in_veto=bool(spec.get("participates_in_veto", True)),
            weight=float(spec.get("weight", 1.0)),
            description=str(spec.get("description", "")),
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
