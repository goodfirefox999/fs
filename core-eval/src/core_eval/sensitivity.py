"""敏感性分析（判定层）。

目的：把"口径一改结论就翻"的候选显式暴露出来，而不是藏在默认参数背后。

做法（docs/DEVELOPMENT.md 第 7 节第 9 条）：对 ``use_true_solar_time``、``day_boundary``、
``year_boundary``、``fenjin ± 3°`` 各做一次重算，输出"结论翻转清单"。

本模块**不自行计算历法**：重算通过 ``recompute`` 回调注入（由 ``app-zeri`` 提供），
以保证"判定层不得计算天文量"这条铁律。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from .engine import Evaluation

__all__ = ["Perturbation", "Flip", "SensitivityReport", "analyze", "DEFAULT_PERTURBATIONS"]


@dataclass(frozen=True)
class Perturbation:
    """一次参数扰动。``param`` 为配置键，``value`` 为扰动后取值。"""

    name: str
    param: str
    value: Any
    note: str = ""


@dataclass(frozen=True)
class Flip:
    """一个候选的结论翻转。"""

    candidate: str
    perturbation: str
    param: str
    from_state: str
    to_state: str
    from_tier: str
    to_tier: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate,
            "perturbation": self.perturbation,
            "param": self.param,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "from_tier": self.from_tier,
            "to_tier": self.to_tier,
        }


@dataclass
class SensitivityReport:
    """敏感性分析结果。"""

    base_states: dict[str, str] = field(default_factory=dict)
    flips: list[Flip] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    @property
    def is_stable(self) -> bool:
        return not self.flips

    def flipped_candidates(self) -> list[str]:
        seen: list[str] = []
        for f in self.flips:
            if f.candidate not in seen:
                seen.append(f.candidate)
        return seen

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_stable": self.is_stable,
            "base_states": self.base_states,
            "flips": [f.to_dict() for f in self.flips],
            "flipped_candidates": self.flipped_candidates(),
            "errors": self.errors,
        }


#: 默认扰动集（对应附录 B 争议项）
DEFAULT_PERTURBATIONS: tuple[Perturbation, ...] = (
    Perturbation("真太阳时开关", "use_true_solar_time", True, "经度时差 + 均时差可致时辰跨界"),
    Perturbation("日界口径", "day_boundary", "early", "子初换日 vs 子正换日"),
    Perturbation("年界口径", "year_boundary", "newyear", "立春换年 vs 正月初一换年"),
    Perturbation("坐向 +3°", "azimuth_delta", 3.0, "实测方位角误差"),
    Perturbation("坐向 -3°", "azimuth_delta", -3.0, "实测方位角误差"),
)


def analyze(
    base: Iterable[Evaluation],
    recompute: Callable[[Perturbation], Iterable[Evaluation]],
    perturbations: Iterable[Perturbation] = DEFAULT_PERTURBATIONS,
) -> SensitivityReport:
    """执行敏感性分析。

    ``recompute(perturbation)`` 必须返回与 ``base`` **同一候选集**的评估结果
    （候选标识为 ``Evaluation.candidate``）；缺失的候选记为 error，不静默丢弃。
    """
    base_map = {e.candidate: e for e in base}
    report = SensitivityReport(base_states={c: e.state for c, e in base_map.items()})

    for pert in perturbations:
        try:
            perturbed = {e.candidate: e for e in recompute(pert)}
        except Exception as exc:  # noqa: BLE001 - 扰动失败必须显式记录
            report.errors.append({"perturbation": pert.name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for candidate, base_ev in base_map.items():
            other = perturbed.get(candidate)
            if other is None:
                report.errors.append(
                    {"perturbation": pert.name, "error": f"重算缺少候选 {candidate}"}
                )
                continue
            if other.state != base_ev.state or other.tier != base_ev.tier:
                report.flips.append(
                    Flip(
                        candidate=candidate,
                        perturbation=pert.name,
                        param=pert.param,
                        from_state=base_ev.state,
                        to_state=other.state,
                        from_tier=base_ev.tier,
                        to_tier=other.tier,
                    )
                )
    return report
