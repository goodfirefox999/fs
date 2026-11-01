"""复核器（应用层）：输入已有日课 → 输出命中明细、三态结论、派别分歧。

只做组合与编排；任何天文量都经 ``core-time``，任何判定都经 ``core-eval``。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core_eval import EvalConfig, Evaluation, StructureReport, detect_structure, evaluate
from core_eval.disagreement import disagreement_of_evaluation
from core_rule.registry import RuleRegistry, default_registry

from .schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context

__all__ = ["VerifyResult", "verify", "verify_context"]


@dataclass
class VerifyResult:
    """复核结果。"""

    evaluation: Evaluation
    context: dict[str, Any]
    structure: StructureReport

    @property
    def disagreement(self) -> float:
        return disagreement_of_evaluation(self.evaluation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluation": self.evaluation.to_dict(),
            "structure": self.structure.to_dict(),
            "disagreement": round(self.disagreement, 4),
            "context": {
                "course": self.context["course"],
                "site": self.context["site"],
                "person": self.context.get("person", {}),
                "task": self.context["task"],
                "time": self.context["time"],
            },
        }


def verify_context(
    ctx: dict[str, Any],
    *,
    registry: RuleRegistry | None = None,
    schools: tuple[str, ...] | None = None,
    allow_unverified: bool = False,
    demo_veto: bool = False,
) -> VerifyResult:
    """对已构建的 ctx 执行复核（供敏感性分析/批量场景复用）。"""
    reg = registry or default_registry()
    task = ctx.get("task", {})
    cfg = EvalConfig(
        task_kind=task.get("kind", ""),
        node_kind=task.get("node"),
        strictness=task.get("strictness", "normal"),
        schools=schools,
        allow_unverified=allow_unverified,
        demo_veto=demo_veto,
        granularity=task.get("granularity", "day_hour"),
    )
    evaluation = evaluate(ctx, reg, cfg)
    structure = detect_structure(
        zhis=_zhis(ctx),
        gans=_gans(ctx),
        shan_jia_zhi=ctx["site"].get("shan_jia_zhi"),
    )
    return VerifyResult(evaluation=evaluation, context=ctx, structure=structure)


def _zhis(ctx: dict[str, Any]) -> list[str]:
    return [
        ctx["course"]["year"]["zhi"],
        ctx["course"]["month"]["zhi"],
        ctx["course"]["day"]["zhi"],
        ctx["course"]["hour"]["zhi"],
    ]


def _gans(ctx: dict[str, Any]) -> list[str]:
    return [
        ctx["course"]["year"]["gan"],
        ctx["course"]["month"]["gan"],
        ctx["course"]["day"]["gan"],
        ctx["course"]["hour"]["gan"],
    ]


def verify(
    *,
    dt: datetime,
    site: SiteSpec,
    task: TaskSpec,
    person: PersonSpec | None = None,
    node: str | None = None,
    cal: Any = None,
    registry: RuleRegistry | None = None,
    schools: tuple[str, ...] | None = None,
    allow_unverified: bool = False,
    demo_veto: bool = False,
) -> VerifyResult:
    """复核一个日课候选。"""
    reg = registry or default_registry()
    ctx = build_context(
        CourseSpec(dt=dt, node=node),
        site,
        task,
        person=person,
        cal=cal,
        calibers=reg.calibers,
    )
    return verify_context(
        ctx, registry=registry, schools=schools,
        allow_unverified=allow_unverified, demo_veto=demo_veto,
    )
