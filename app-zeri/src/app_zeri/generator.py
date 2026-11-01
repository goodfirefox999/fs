"""生成器（应用层）：时间窗内穷举候选 → 全量评估 → 分层排序 → Top-K。

铁律
----
1. 剪枝**不得改变结果集**（用暴力对照验证，见 tests/golden）。
2. 可用集为空时输出"无解说明"（被否决原因直方图），**不得放宽硬约束凑答案**。
   放宽必须显式 ``relax=True`` 并在报告中大字标注。
3. 排序不是 ``sum(score)``，而是分层向量 + Pareto（见 ``core_eval.ranker``）。
"""

from __future__ import annotations

from collections import Counter
from enum import Enum
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Callable, Iterable

from core_eval import (
    TIER_ACCEPTABLE,
    TIER_NEEDS_REVIEW,
    TIER_PREFERRED,
    TIER_REJECTED,
    EvalConfig,
    Evaluation,
    Perturbation,
    SensitivityReport,
    evaluate,
    pareto_front,
    rank,
)
from core_eval.arbitration import build_spec_output
from core_eval.disagreement import aggregate_disagreement, disagreement_of_evaluation
from core_eval.sensitivity import analyze as analyze_sensitivity
from core_rule.registry import RuleRegistry, default_registry

from .robustness import RobustnessReport, assess as assess_robustness
from .schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
from .verifier import VerifyResult

__all__ = [
    "GenResult",
    "NoSolution",
    "NoSolutionReason",
    "generate",
    "candidate_datetimes",
    "iter_candidates",
    "HOUR_SAMPLE_HOURS",
]


def iter_candidates(
    start: date,
    end: date,
    granularity: str = "day_hour",
    *,
    daily_window: tuple[time, time] | None = None,
    exclude_weekdays: Iterable[int] = (),
    tz: Any = None,
):
    """逐日逐时辰惰性产出候选时刻（与 ``candidate_datetimes`` 等价，供大窗口流式使用）。"""
    yield from candidate_datetimes(
        start, end, granularity, daily_window=daily_window, exclude_weekdays=exclude_weekdays, tz=tz
    )

#: 12 时辰代表时刻（子=00:00, 丑=02:00 … 亥=22:00）。
#: 采用"时辰中段整点"以避免子初/子正换日歧义；真太阳时开关会改变实际时辰归属。
HOUR_SAMPLE_HOURS: tuple[int, ...] = (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22)


def candidate_datetimes(
    start: date,
    end: date,
    granularity: str = "day_hour",
    *,
    daily_window: tuple[time, time] | None = None,
    exclude_weekdays: Iterable[int] = (),
    tz: Any = None,
) -> list[datetime]:
    """枚举候选时刻（含首尾日期）。

    ``daily_window`` 为每日可用时段（含左闭右开）；``day`` 粒度取当日 12:00 单点。
    """
    if end < start:
        raise ValueError("结束日期不得早于开始日期")
    excluded = set(exclude_weekdays)
    out: list[datetime] = []
    cursor = start
    while cursor <= end:
        if cursor.weekday() not in excluded:
            if granularity == "day":
                out.append(datetime.combine(cursor, time(12, 0), tzinfo=tz))
            else:
                for h in HOUR_SAMPLE_HOURS:
                    moment = datetime.combine(cursor, time(h, 0), tzinfo=tz)
                    if daily_window is not None:
                        lo, hi = daily_window
                        if not (lo <= time(h, 0) < hi):
                            continue
                    out.append(moment)
        cursor += timedelta(days=1)
    return out


class NoSolutionReason(str, Enum):
    """"没有可发布结论"的三种原因 —— 必须在 schema 上与"无解"区分。

    - ``all_rejected``：该窗口内所有候选都被否决层排除（**真的无解**）
    - ``no_conclusion_pending_verification``：有候选未触发否决，但依赖未考证规则 /
      口径未定，**不是无解，是暂无结论**
    - ``constraints_conflict``：约束互斥（如时间窗与每日时段无交集）
    """

    ALL_REJECTED = "all_rejected"
    NO_CONCLUSION_PENDING_VERIFICATION = "no_conclusion_pending_verification"
    CONSTRAINTS_CONFLICT = "constraints_conflict"


@dataclass
class NoSolution:
    """无解/无结论说明：给出被否决原因直方图，**不放宽硬约束**。"""

    total_candidates: int
    rejected: int
    veto_reasons: dict[str, int]
    tier_histogram: dict[str, int]
    message: str
    reason: str = NoSolutionReason.ALL_REJECTED.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason,
            "total_candidates": self.total_candidates,
            "rejected": self.rejected,
            "veto_reasons": self.veto_reasons,
            "tier_histogram": self.tier_histogram,
            "message": self.message,
        }


@dataclass
class GenResult:
    """生成结果。"""

    ranked: list[VerifyResult]
    all_evaluations: list[Evaluation]
    total_candidates: int
    tier_histogram: dict[str, int]
    disagreement: float
    pareto_size: int
    no_solution: NoSolution | None = None
    no_solution_reason: str | None = None
    sensitivity: SensitivityReport | None = None
    robustness: RobustnessReport | None = None
    relaxed: bool = False
    #: 评审扩展版 spec §4 仲裁结构：rejected_dates / scored_dates / consensus_dates
    spec_output: dict[str, Any] | None = None

    @property
    def usable(self) -> list[VerifyResult]:
        """可用集 = 未触发否决层的候选（``state == 可用``）。

        注意：``state=可用`` 只表示"没有硬否决命中"，**不等于可发布**。
        是否可发布取决于 ``tier``（unknown 会把 tier 拉到 NEEDS_REVIEW）
        与规则库的考证状态。
        """
        return [r for r in self.ranked if r.evaluation.state == "可用"]

    @property
    def publishable(self) -> list[VerifyResult]:
        """可发布集 = 可用且 tier ∈ PREFERRED/ACCEPTABLE（无 unknown/conflict）。"""
        return [
            r for r in self.usable if r.evaluation.tier in (TIER_PREFERRED, TIER_ACCEPTABLE)
        ]

    @property
    def is_publishable(self) -> bool:
        """整个结果集是否可对外发布（至少 1 个可发布候选）。"""
        return len(self.publishable) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_candidates": self.total_candidates,
            "tier_histogram": self.tier_histogram,
            "disagreement": round(self.disagreement, 4),
            "pareto_size": self.pareto_size,
            "relaxed": self.relaxed,
            "usable_count": len(self.usable),
            "publishable_count": len(self.publishable),
            "publishable": self.is_publishable,
            "no_solution_reason": self.no_solution_reason,
            "no_solution": self.no_solution.to_dict() if self.no_solution else None,
            "sensitivity": self.sensitivity.to_dict() if self.sensitivity else None,
            "robustness": self.robustness.to_dict() if self.robustness else None,
            "spec_output": self.spec_output,
            "candidates": [r.to_dict() for r in self.ranked],
        }


def _veto_histogram(evals: Iterable[Evaluation]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for ev in evals:
        for res in ev.per_school.values():
            for j in res.vetoes:
                counter[f"{j.rule_id} {j.category}"] += 1
    return dict(counter.most_common())


def generate(
    *,
    start: date,
    end: date,
    site: SiteSpec,
    task: TaskSpec,
    person: PersonSpec | None = None,
    node: str | None = None,
    cal: Any = None,
    registry: RuleRegistry | None = None,
    schools: tuple[str, ...] | None = None,
    allow_unverified: bool = False,
    demo_veto: bool = False,
    top: int = 20,
    daily_window: tuple[time, time] | None = None,
    exclude_weekdays: Iterable[int] = (),
    excluded_dates: Iterable[date] = (),
    with_sensitivity: bool = False,
    sensitivity_sample: int = 12,
    with_robustness: bool = False,
) -> GenResult:
    """在时间窗内穷举并排序候选。"""
    reg = registry or default_registry()
    tz = _tz_of(cal)
    excluded = set(excluded_dates)
    moments = [
        m
        for m in candidate_datetimes(
            start, end, task.granularity, daily_window=daily_window,
            exclude_weekdays=exclude_weekdays, tz=tz,
        )
        if m.date() not in excluded
    ]
    if not moments:
        raise ValueError("候选集为空：请检查时间窗/每日时段/排除星期")

    cfg = EvalConfig(
        task_kind=task.kind,
        node_kind=node,
        strictness=task.strictness,
        schools=schools,
        allow_unverified=allow_unverified,
        demo_veto=demo_veto,
        granularity=task.granularity,
    )

    results: list[VerifyResult] = []
    evaluations: list[Evaluation] = []
    for moment in moments:
        ctx = build_context(
            CourseSpec(dt=moment, node=node), site, task, person=person, cal=cal,
            calibers=reg.calibers,
        )
        ev = evaluate(ctx, reg, cfg)
        evaluations.append(ev)
        results.append(VerifyResult(evaluation=ev, context=ctx, structure=_structure_of(ctx)))

    by_candidate = {r.evaluation.candidate: r for r in results}
    ordered = [by_candidate[e.candidate] for e in rank([r.evaluation for r in results])]
    tier_hist: Counter[str] = Counter(r.evaluation.tier for r in ordered)
    histogram = {
        TIER_PREFERRED: tier_hist.get(TIER_PREFERRED, 0),
        TIER_ACCEPTABLE: tier_hist.get(TIER_ACCEPTABLE, 0),
        TIER_NEEDS_REVIEW: tier_hist.get(TIER_NEEDS_REVIEW, 0),
        TIER_REJECTED: tier_hist.get(TIER_REJECTED, 0),
    }

    usable = [r for r in ordered if r.evaluation.state == "可用"]
    publishable = [
        r for r in usable if r.evaluation.tier in (TIER_PREFERRED, TIER_ACCEPTABLE)
    ]
    no_solution: NoSolution | None = None
    no_solution_reason: str | None = None

    if not usable:
        rejected = sum(1 for r in ordered if r.evaluation.tier == TIER_REJECTED)
        reason = (
            NoSolutionReason.ALL_REJECTED.value
            if rejected == len(ordered)
            else NoSolutionReason.NO_CONCLUSION_PENDING_VERIFICATION.value
        )
        no_solution_reason = reason
        no_solution = NoSolution(
            total_candidates=len(ordered),
            rejected=rejected,
            veto_reasons=_veto_histogram(evaluations),
            tier_histogram=histogram,
            reason=reason,
            message=(
                "本时间窗内无通过否决层的候选。系统**不会**放宽硬约束来凑答案；"
                "如需放宽请显式使用 --relax 并在报告中保留本说明。"
            )
            if reason == NoSolutionReason.ALL_REJECTED.value
            else (
                f"本时间窗内有 {len(ordered) - rejected} 个候选未被完全否决（多为存疑），"
                "但无一达到可发布等级，故**无结论**（非无解）。"
                "补齐规则考证或口径后重跑即可。"
            ),
        )
    elif not publishable:
        # 有候选未触发否决，但没有一个达到可发布等级 —— 这是"无结论"，不是"无解"
        no_solution_reason = NoSolutionReason.NO_CONCLUSION_PENDING_VERIFICATION.value

    sensitivity: SensitivityReport | None = None
    if with_sensitivity:
        sample = ordered[: max(1, sensitivity_sample)]
        base_evals = [r.evaluation for r in sample]

        def _recompute(pert: Perturbation) -> list[Evaluation]:
            return _recompute_with_perturbation(
                pert, sample, site, task, person, node, cal, reg, cfg
            )

        sensitivity = analyze_sensitivity(base_evals, _recompute)

    robustness: RobustnessReport | None = None
    if with_robustness:
        robustness = assess_robustness(
            ordered[: max(1, top)],
            site=site,
            task=task,
            person=person,
            node=node,
            cal=cal or __import__("core_time").CalendarConfig(),
            registry=reg,
            cfg=cfg,
            radius_deg=site.angle_uncertainty_deg or 1.0,
        )

    return GenResult(
        ranked=ordered[: max(1, top)],
        all_evaluations=evaluations,
        spec_output=build_spec_output([(r.evaluation, r.context) for r in results]),
        total_candidates=len(ordered),
        tier_histogram=histogram,
        disagreement=aggregate_disagreement(evaluations),
        pareto_size=len(pareto_front(evaluations)),
        no_solution=no_solution,
        no_solution_reason=no_solution_reason,
        sensitivity=sensitivity,
        robustness=robustness,
        relaxed=False,
    )


def _tz_of(cal: Any) -> Any:
    from zoneinfo import ZoneInfo

    name = getattr(cal, "timezone", None) or "Asia/Shanghai"
    return ZoneInfo(name)


def _structure_of(ctx: dict[str, Any]):
    from core_eval import detect_structure

    course = ctx["course"]
    return detect_structure(
        zhis=[course[k]["zhi"] for k in ("year", "month", "day", "hour")],
        gans=[course[k]["gan"] for k in ("year", "month", "day", "hour")],
        shan_jia_zhi=ctx["site"].get("shan_jia_zhi"),
    )


def _recompute_with_perturbation(
    pert: Perturbation,
    sample: list[VerifyResult],
    site: SiteSpec,
    task: TaskSpec,
    person: PersonSpec | None,
    node: str | None,
    cal: Any,
    reg: RuleRegistry,
    cfg: EvalConfig,
) -> list[Evaluation]:
    """按扰动重算样本候选。历法参数改动经 ``core_time.CalendarConfig``。"""
    from core_time import CalendarConfig

    base_cal = cal or CalendarConfig()
    dt_list = [datetime.fromisoformat(r.context["time"]["datetime"]) for r in sample]

    if pert.param in ("use_true_solar_time", "day_boundary", "year_boundary"):
        new_cal = base_cal.with_overrides(**{pert.param: pert.value})
        out: list[Evaluation] = []
        for moment in dt_list:
            ctx = build_context(
                CourseSpec(dt=moment, node=node), site, task, person=person, cal=new_cal,
                calibers=reg.calibers,
            )
            out.append(evaluate(ctx, reg, cfg))
        return out

    if pert.param == "azimuth_delta":
        new_site = SiteSpec(
            azimuth_deg=(site.azimuth_deg + float(pert.value)) % 360.0,
            lat=site.lat,
            lon=site.lon,
            mountain=site.mountain,
            facing=site.facing,
            fenjin=site.fenjin,
            measure_method=site.measure_method,
            angle_uncertainty_deg=site.angle_uncertainty_deg,
        )
        out = []
        for moment in dt_list:
            ctx = build_context(
                CourseSpec(dt=moment, node=node), new_site, task, person=person, cal=base_cal,
                calibers=reg.calibers,
            )
            out.append(evaluate(ctx, reg, cfg))
        return out

    raise ValueError(f"未知扰动参数: {pert.param}")


_ = (field, Callable)
