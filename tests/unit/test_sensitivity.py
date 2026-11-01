"""敏感性分析测试：口径一改结论是否翻转，必须可检出且显式登记。"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from core_eval import EvalConfig, Perturbation, SensitivityReport, analyze, evaluate
from core_eval.sensitivity import DEFAULT_PERTURBATIONS

CST = ZoneInfo("Asia/Shanghai")


def _ev(candidate: str, state: str = "可用", tier: str = "ACCEPTABLE"):
    """构造一个最小 Evaluation（仅用于敏感性分析的结构测试）。"""
    from core_eval.engine import Evaluation

    return Evaluation(
        candidate=candidate,
        per_school={},
        state=state,
        tier=tier,
        vectors={},
        conflicts=[],
        unknowns=[],
        manifest={},
        config=EvalConfig(task_kind="修造"),
    )


class TestAnalyze:
    def test_no_flip_is_stable(self) -> None:
        base = [_ev("a"), _ev("b")]
        report = analyze(base, lambda p: [_ev("a"), _ev("b")], DEFAULT_PERTURBATIONS[:1])
        assert report.is_stable is True
        assert report.flips == []
        assert report.flipped_candidates() == []

    def test_flip_detected(self) -> None:
        base = [_ev("a", "可用", "ACCEPTABLE")]
        report = analyze(
            base,
            lambda p: [_ev("a", "不可用", "REJECTED")],
            [Perturbation("日界口径", "day_boundary", "early")],
        )
        assert report.is_stable is False
        assert len(report.flips) == 1
        f = report.flips[0]
        assert f.candidate == "a"
        assert f.from_state == "可用" and f.to_state == "不可用"
        assert f.from_tier == "ACCEPTABLE" and f.to_tier == "REJECTED"
        assert f.to_dict()["param"] == "day_boundary"

    def test_flipped_candidates_dedup(self) -> None:
        base = [_ev("a"), _ev("b")]
        report = analyze(
            base,
            lambda p: [_ev("a", "存疑", "NEEDS_REVIEW"), _ev("b", "存疑", "NEEDS_REVIEW")],
            DEFAULT_PERTURBATIONS[:2],
        )
        assert sorted(report.flipped_candidates()) == ["a", "b"]
        assert len(report.flips) == 4  # 2 候选 × 2 扰动

    def test_recompute_error_recorded(self) -> None:
        def boom(_p):
            raise RuntimeError("重算失败")

        report = analyze([_ev("a")], boom, DEFAULT_PERTURBATIONS[:1])
        assert report.errors
        assert "RuntimeError" in report.errors[0]["error"]

    def test_missing_candidate_recorded(self) -> None:
        report = analyze(
            [_ev("a"), _ev("b")],
            lambda p: [_ev("a")],
            DEFAULT_PERTURBATIONS[:1],
        )
        assert any("缺少候选" in e["error"] for e in report.errors)

    def test_base_states_captured(self) -> None:
        report = analyze([_ev("a", "存疑", "NEEDS_REVIEW")], lambda p: [_ev("a", "存疑", "NEEDS_REVIEW")], [])
        assert report.base_states == {"a": "存疑"}
        assert isinstance(report.to_dict(), dict)


class TestDefaultPerturbations:
    def test_covers_all_disputed_params(self) -> None:
        params = {p.param for p in DEFAULT_PERTURBATIONS}
        assert {"use_true_solar_time", "day_boundary", "year_boundary", "azimuth_delta"} <= params

    def test_azimuth_has_both_directions(self) -> None:
        deltas = [p.value for p in DEFAULT_PERTURBATIONS if p.param == "azimuth_delta"]
        assert 3.0 in deltas and -3.0 in deltas


class TestIntegrationWithGenerator:
    def test_generator_sensitivity_block(self) -> None:
        from app_zeri.generator import generate
        from app_zeri.schemas import SiteSpec, TaskSpec

        result = generate(
            start=date(2027, 7, 1),
            end=date(2027, 7, 5),
            site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", strictness="strict"),
            allow_unverified=True,
            top=5,
            with_sensitivity=True,
            sensitivity_sample=3,
        )
        assert result.sensitivity is not None
        assert isinstance(result.sensitivity, SensitivityReport)
        # 真太阳时/日界/坐向扰动后，某些候选可能翻转；至少不能报错
        assert result.sensitivity.errors == [] or all("缺少候选" not in e["error"] for e in result.sensitivity.errors)

    def test_azimuth_perturbation_can_change_hit(self) -> None:
        """坐向 ±3° 应能改变山家判定（乾山兼亥 → 正针乾山）。"""
        from app_zeri.schemas import SiteSpec, TaskSpec, build_context, CourseSpec

        dt = datetime(2027, 7, 11, 14, 0, tzinfo=CST)
        a = build_context(CourseSpec(dt=dt), SiteSpec(azimuth_deg=320.0), TaskSpec(kind="修造"))
        b = build_context(CourseSpec(dt=dt), SiteSpec(azimuth_deg=316.0), TaskSpec(kind="修造"))
        assert a["site"]["shan_jia_zhi"] == "亥"
        assert b["site"]["shan_jia_zhi"] is None  # 316° 未过兼向阈值，且乾非地支山
