"""规则注册表：把规则库与派别策略组合成可查询对象（规则层）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .calibers import CaliberRegistry, load_caliber_sets
from .loader import RuleSet, load_ruleset
from .models import Rule
from .policy import (
    RequiredRuleSet,
    SchoolPolicy,
    TaskKindSpec,
    load_required_rules,
    load_school_policy,
    load_task_kinds,
)

__all__ = ["RuleRegistry", "default_registry", "RULES_DIR", "CONFIG_DIR"]


RULES_DIR = Path(__file__).resolve().parents[2] / "rules"
CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


@dataclass(frozen=True)
class RuleRegistry:
    """规则库 + 派别策略 + 事项模板 + 口径注册表。"""

    ruleset: RuleSet
    policy: SchoolPolicy
    task_kinds: dict[str, TaskKindSpec]
    calibers: CaliberRegistry = field(default_factory=CaliberRegistry)
    required_rules: RequiredRuleSet = field(default_factory=RequiredRuleSet)

    def rules_for(
        self,
        *,
        task_kind: str | None,
        node_kind: str | None = None,
        strictness: str = "normal",
        schools: Iterable[str] | None = None,
        include_unverified: bool = False,
    ) -> tuple[Rule, ...]:
        route = tuple(schools) if schools is not None else self.policy.route(task_kind)
        return self.ruleset.select(
            schools=route,
            task_kind=task_kind,
            node_kind=node_kind,
            strictness=strictness,
            include_unverified=include_unverified,
        )

    def school_of(self, rule_id: str) -> str:
        return self.ruleset.by_id[rule_id].school

    def task_spec(self, kind: str) -> TaskKindSpec | None:
        return self.task_kinds.get(kind)

    def stats(self) -> dict[str, object]:
        return {
            **self.ruleset.stats(),
            "schools": self.policy.to_dict()["schools"],
            "calibers": self.calibers.to_manifest()["selection"],
        }

    def with_calibers(self, selection: dict[str, str]) -> "RuleRegistry":
        """返回选用指定口径的新注册表（不可变，不污染全局）。"""
        return RuleRegistry(
            ruleset=self.ruleset,
            policy=self.policy,
            task_kinds=self.task_kinds,
            calibers=self.calibers.with_selection(selection),
            required_rules=self.required_rules,
        )

    def required_for(self, task_kind: str, *, person_provided: bool = False) -> tuple[str, ...]:
        return self.required_rules.for_task(task_kind, person_provided=person_provided)


def default_registry(
    rules_dir: Path | str | None = None,
    config_dir: Path | str | None = None,
) -> RuleRegistry:
    """加载仓库内置规则库与配置。"""
    rules_path = Path(rules_dir) if rules_dir else RULES_DIR
    config_path = Path(config_dir) if config_dir else CONFIG_DIR
    return RuleRegistry(
        ruleset=load_ruleset(rules_path),
        policy=load_school_policy(config_path / "school_policy.yaml"),
        task_kinds=load_task_kinds(config_path / "task_kinds.yaml"),
        calibers=load_caliber_sets(config_path / "calibers"),
        required_rules=load_required_rules(config_path / "required_rules.yaml"),
    )
