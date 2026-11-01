"""稳健性评估（应用层）：区分「稳健集」与「敏感集」。

为什么需要
----------
罗盘读数、磁偏角、图纸都有误差（``SiteSpec.angle_uncertainty_deg``），
真太阳时开关、日界口径也会改结论。如果 Top-K 里一半候选是"角度差 2° 就作废"的日子，
那比不给结论更危险。

因此生成器主输出分两层：

- **稳健集**：在所有扰动下 ``state`` 均不变 → 可作为推荐主体
- **敏感集**：任一扰动下翻转 → 单独列出并标注翻转原因与触发扰动

``robustness_radius`` 给出"在多大坐向误差内结论不变"的量化值。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable

from core_eval import EvalConfig, Evaluation, Perturbation, evaluate
from core_rule.registry import RuleRegistry
from core_time import CalendarConfig

from .schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
from .verifier import VerifyResult

__all__ = ["RobustnessReport", "assess", "default_perturbations"]


@dataclass
class RobustnessReport:
    """稳健性报告。"""

    perturbations: list[str] = field(default_factory=list)
    robust: list[str] = field(default_factory=list)
    sensitive: list[dict[str, Any]] = field(default_factory=list)
    stable_ratio: float = 0.0
    radius_deg: float | None = None
    errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def is_fully_robust(self) -> bool:
        return not self.sensitive

    def to_dict(self) -> dict[str, Any]:
        return {
            "perturbations": self.perturbations,
            "robust": self.robust,
            "sensitive": self.sensitive,
            "stable_ratio": round(self.stable_ratio, 4),
            "radius_deg": self.radius_deg,
            "is_fully_robust": self.is_fully_robust,
            "errors": self.errors,
            "note": (
                "稳健集 = 所有扰动下 state 不变；敏感集 = 任一扰动下翻转。"
                "radius_deg 为「坐向误差在此范围内结论不变」的量化值（None 表示未测）。"
            ),
        }


def default_perturbations(radius: float) -> tuple[Perturbation, ...]:
    """默认扰动集：口径开关 + 坐向 ±radius。"""
    return (
        Perturbation("真太阳时开关", "use_true_solar_time", True, "经度时差 + 均时差可致时辰跨界"),
        Perturbation("日界口径", "day_boundary", "early", "子初换日 vs 子正换日"),
        Perturbation(f"坐向 +{radius:g}°", "azimuth_delta", radius, "罗盘/磁偏角误差上限"),
        Perturbation(f"坐向 -{radius:g}°", "azimuth_delta", -radius, "罗盘/磁偏角误差上限"),
    )


def _rebuild(
    moment: datetime,
    site: SiteSpec,
    task: TaskSpec,
    person: PersonSpec | None,
    node: str | None,
    cal: CalendarConfig,
    reg: RuleRegistry,
    cfg: EvalConfig,
    *,
    azimuth_delta: float = 0.0,
    cal_override: CalendarConfig | None = None,
) -> Evaluation:
    new_site = site
    if azimuth_delta:
        new_site = SiteSpec(
            azimuth_deg=(site.azimuth_deg + azimuth_delta) % 360.0,
            lat=site.lat,
            lon=site.lon,
            mountain=site.mountain,
            facing=site.facing,
            fenjin=site.fenjin,
            measure_method=site.measure_method,
            angle_uncertainty_deg=site.angle_uncertainty_deg,
        )
    ctx = build_context(
        CourseSpec(dt=moment, node=node),
        new_site,
        task,
        person=person,
        cal=cal_override or cal,
        calibers=reg.calibers,
    )
    return evaluate(ctx, reg, cfg)


def assess(
    candidates: Iterable[VerifyResult],
    *,
    site: SiteSpec,
    task: TaskSpec,
    person: PersonSpec | None,
    node: str | None,
    cal: CalendarConfig,
    registry: RuleRegistry,
    cfg: EvalConfig,
    radius_deg: float | None = None,
) -> RobustnessReport:
    """对候选集做扰动矩阵，输出稳健集 / 敏感集。"""
    items = list(candidates)
    radius = radius_deg if radius_deg is not None else (site.angle_uncertainty_deg or 1.0)
    perturbations = default_perturbations(radius)
    report = RobustnessReport(
        perturbations=[p.name for p in perturbations],
        radius_deg=radius,
    )
    if not items:
        return report

    for result in items:
        base_state = result.evaluation.state
        moment = datetime.fromisoformat(result.context["time"]["datetime"])
        flips: list[dict[str, Any]] = []
        for pert in perturbations:
            try:
                if pert.param == "azimuth_delta":
                    ev = _rebuild(
                        moment, site, task, person, node, cal, registry, cfg,
                        azimuth_delta=float(pert.value),
                    )
                elif pert.param in ("use_true_solar_time", "day_boundary", "year_boundary"):
                    ev = _rebuild(
                        moment, site, task, person, node, cal, registry, cfg,
                        cal_override=cal.with_overrides(**{pert.param: pert.value}),
                    )
                else:  # pragma: no cover
                    continue
            except Exception as exc:  # noqa: BLE001 - 扰动失败必须记录
                report.errors.append(
                    {"candidate": result.evaluation.candidate, "perturbation": pert.name,
                     "error": f"{type(exc).__name__}: {exc}"}
                )
                continue
            if ev.state != base_state:
                flips.append(
                    {
                        "perturbation": pert.name,
                        "param": pert.param,
                        "from": base_state,
                        "to": ev.state,
                        "from_tier": result.evaluation.tier,
                        "to_tier": ev.tier,
                    }
                )
        if flips:
            report.sensitive.append(
                {"candidate": result.evaluation.candidate, "base_state": base_state, "flips": flips}
            )
        else:
            report.robust.append(result.evaluation.candidate)

    total = len(items)
    report.stable_ratio = len(report.robust) / total if total else 0.0
    return report


_ = Callable
