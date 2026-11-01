"""边界与约定测试：日柱换日基准、年月/日时时间基准拆分、事实哈希完整性。

对应 2026-11-01 评审的三条 P0：

1. 真太阳时下日柱换日边界必须与 hour_ref 一致（同一类缺陷换了个位置）；
2. `ym_time_ref` / `hour_time_ref` 独立配置（混合口径是选择，不是 bug）；
3. `fact_hash` 必须含完整约定，否则"同 fact 不同口径"会误判一致。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from core_time import CalendarConfig, compute_four_pillars

CST = ZoneInfo("Asia/Shanghai")


class TestDayBoundaryUnderTrueSolarTime:
    """日柱换日必须基于 hour_ref，不能"时柱用真太阳时、日柱用民用时换日"。"""

    def test_civil_2330_late_boundary(self) -> None:
        p = compute_four_pillars(
            datetime(2027, 7, 11, 23, 30, tzinfo=CST),
            CalendarConfig(day_boundary="late"),
        )
        assert p.day.name == "辛卯"  # 23:30 仍属当日

    def test_civil_2330_early_boundary(self) -> None:
        p = compute_four_pillars(
            datetime(2027, 7, 11, 23, 30, tzinfo=CST),
            CalendarConfig(day_boundary="early"),
        )
        assert p.day.name == "壬辰"  # 子初换日 → 次日

    def test_true_solar_pulls_back_before_boundary(self) -> None:
        """东经 113° 下 23:30 → 真太阳时约 22:58，子初换日下**不应换日**。"""
        cfg = CalendarConfig(day_boundary="early", use_true_solar_time=True)
        p = compute_four_pillars(datetime(2027, 7, 11, 23, 30, tzinfo=CST), cfg, lon=113.26)
        assert p.hour_reference.hour == 22, f"真太阳时应回退到 22 时，得到 {p.hour_reference}"
        assert p.day.name == "辛卯", "真太阳时 22:58 未过子初，日柱不应换"
        assert p.hour.zhi == "亥"

    def test_true_solar_can_also_cross_forward(self) -> None:
        """东经 125°（>120）真太阳时前移：民用时 22:55 未过子初，真太阳时 23:10 已过。"""
        at = datetime(2027, 7, 11, 22, 55, tzinfo=CST)
        civil = compute_four_pillars(at, CalendarConfig(day_boundary="early"))
        solar = compute_four_pillars(
            at, CalendarConfig(day_boundary="early", use_true_solar_time=True), lon=125.0
        )
        assert civil.day.name == "辛卯", "民用时 22:55 未过子初，日柱不换"
        assert solar.hour_reference.hour == 23, f"真太阳时应前移到 23 时，得到 {solar.hour_reference}"
        assert solar.day.name == "壬辰", "真太阳时 23:10 已过子初，日柱应换"


class TestTimeRefSplit:
    """年月柱与日时柱的时间基准独立配置。"""

    def test_default_is_civil(self) -> None:
        cfg = CalendarConfig()
        assert cfg.ym_time_ref == "auto" and cfg.hour_time_ref == "auto"
        assert cfg.use_true_solar_for(cfg.ym_time_ref) is False

    def test_auto_follows_global_switch(self) -> None:
        cfg = CalendarConfig(use_true_solar_time=True)
        assert cfg.use_true_solar_for("auto") is True
        assert cfg.use_true_solar_for("civil") is False
        assert cfg.use_true_solar_for("true_solar") is True

    def test_mixed_convention_ym_civil_hour_solar(self) -> None:
        """混合口径：年月柱用钟表时、日时柱用真太阳时（传统常见做法）。"""
        lichun = datetime(2027, 2, 4, 9, 46, tzinfo=CST)  # 2027 立春附近
        at = lichun + __import__("datetime").timedelta(minutes=10)

        mixed = compute_four_pillars(
            at, CalendarConfig(ym_time_ref="civil", hour_time_ref="true_solar"), lon=113.26
        )
        all_solar = compute_four_pillars(
            at, CalendarConfig(use_true_solar_time=True), lon=113.26
        )
        all_civil = compute_four_pillars(at, CalendarConfig())

        # 混合口径下：年柱按民用时（已过交节 → 丁未），时柱按真太阳时
        assert mixed.year.name == "丁未"
        assert all_solar.year.name == "丙午", "全真太阳时下应被拉回交节前"
        assert all_civil.year.name == "丁未"

    def test_bad_time_ref_rejected(self) -> None:
        with pytest.raises(ValueError, match="ym_time_ref"):
            CalendarConfig(ym_time_ref="solar")
        with pytest.raises(ValueError, match="hour_time_ref"):
            CalendarConfig(hour_time_ref="lunar")

    def test_echoed_in_pillars(self) -> None:
        cfg = CalendarConfig(ym_time_ref="civil", hour_time_ref="true_solar")
        p = compute_four_pillars(datetime(2027, 7, 11, 14, 0, tzinfo=CST), cfg, lon=113.26)
        d = p.to_dict()
        assert d["ym_time_ref"] == "civil"
        assert d["hour_time_ref"] == "true_solar"


class TestFactHashConvention:
    """fact_hash 必须含完整约定，否则"同 fact 不同口径"会误判一致。"""

    def _hash(self, **overrides):
        from app_zeri.schemas import CourseSpec, SiteSpec, TaskSpec, build_context
        from core_eval.engine import _convention_hash  # type: ignore[attr-defined]

        cfg = CalendarConfig(**overrides) if overrides else CalendarConfig()
        ctx = build_context(
            CourseSpec(dt=datetime(2027, 7, 11, 14, 0, tzinfo=CST)),
            SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
            TaskSpec(kind="修造"),
            cal=cfg,
        )
        return _convention_hash(ctx)

    def test_same_convention_same_hash(self) -> None:
        assert self._hash() == self._hash()

    def test_different_day_boundary_different_hash(self) -> None:
        assert self._hash(day_boundary="late") != self._hash(day_boundary="early")

    def test_different_time_ref_different_hash(self) -> None:
        assert self._hash(ym_time_ref="civil") != self._hash(ym_time_ref="true_solar")


class TestTwoAxisCombination:
    """两轴组合的合法边界：年柱已换、日柱未换。

    场景（2021 立春 22:58，民用时 23:10，东经 113.26°）：
    - 年柱：`ym_time_ref=civil` → 23:10 已过 22:58 → 换年（辛丑）
    - 日柱：`hour_time_ref=true_solar` → 真太阳时约 22:37，未到 23:00 → **不换日**
    这是用户显式选择混合口径后的自洽结果，不是 bug；报告必须回显两条基准。
    """

    AT = datetime(2021, 2, 3, 23, 10, tzinfo=CST)
    LON = 113.26

    def test_mixed_year_changed_day_not(self) -> None:
        cfg = CalendarConfig(
            ym_time_ref="civil", hour_time_ref="true_solar", day_boundary="early"
        )
        p = compute_four_pillars(self.AT, cfg, lon=self.LON)
        assert p.year.name == "辛丑", "年柱按民用时判断，已过立春（22:58）应换年"
        assert p.month.name == "庚寅", "月柱同理：已过立春 → 寅月"
        assert p.hour_reference.hour == 22, "真太阳时应回退到 22 时"
        assert p.day.name == "壬午", "真太阳时未过子初，日柱不应换（2021-02-03 日柱=壬午）"

    def test_all_solar_year_not_changed(self) -> None:
        """全真太阳时：22:37 未过 22:58 → 年柱仍是庚子。"""
        cfg = CalendarConfig(use_true_solar_time=True, day_boundary="early")
        p = compute_four_pillars(self.AT, cfg, lon=self.LON)
        assert p.year.name == "庚子"
        assert p.month.name == "己丑", "未过立春 → 仍是丑月"
        assert p.day.name == "壬午"

    def test_all_civil_year_changed_day_changed(self) -> None:
        """全 Civil + 子初：23:10 已过立春且已过子初 → 年换、日也换。"""
        cfg = CalendarConfig(day_boundary="early")
        p = compute_four_pillars(self.AT, cfg)
        assert p.year.name == "辛丑"
        assert p.day.name == "癸未", "民用时 23:10 已过子初，日柱换到 2021-02-04（癸未）"

    def test_report_echoes_both_refs(self) -> None:
        """报告必须同时回显两条时间基准，否则用户看不懂四柱怎么来的。"""
        from app_zeri.report import render_markdown
        from app_zeri.schemas import CourseSpec, SiteSpec, TaskSpec, build_context
        from app_zeri.verifier import VerifyResult
        from core_eval import detect_structure

        cfg = CalendarConfig(ym_time_ref="civil", hour_time_ref="true_solar", day_boundary="early")
        ctx = build_context(
            CourseSpec(dt=self.AT),
            SiteSpec(azimuth_deg=320.0, lon=self.LON),
            TaskSpec(kind="修造", strictness="normal"),
            cal=cfg,
        )
        from core_eval import EvalConfig, evaluate
        from core_rule import default_registry

        ev = evaluate(ctx, default_registry(), EvalConfig(task_kind="修造", strictness="normal"))
        md = render_markdown(
            VerifyResult(
                evaluation=ev,
                context=ctx,
                structure=detect_structure(["丑", "寅", "午", "亥"], ["辛", "庚", "壬", "辛"]),
            )
        )
        assert "年/月柱时间基准" in md and "civil" in md
        assert "日/时柱时间基准" in md and "true_solar" in md
        assert "日界规则" in md
