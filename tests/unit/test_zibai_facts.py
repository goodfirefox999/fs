"""紫白四盘接入测试（Phase 11）。

这份测试的存在理由
------------------
``zibai.py`` 在 Phase 10 就已写好，但 ``derive_zibai_facts`` **从未被调用**——
模块躺在盘上、``facts.zibai`` 不存在、没有任何规则能引用它（"死模块"）。
本文件锁三件事：

1. **接上了**：``facts.zibai`` 有年/月/日/时四盘，且与通书起例表逐项相符；
2. **没串味**：时盘必须在候选级重算，不能沿用当日首个子时的结果
   （与 CHANGELOG 0.5.0 的跨时辰 P0 同形，只是换个事实面）；
3. **口径可切**：``zibai_fly`` 换口径只动日/时盘，年/月盘恒顺飞。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from core_rule.calibers import CALIBER_ZIBAI_FLY, CaliberRegistry, load_caliber_sets
from core_symbol.zibai import (
    month_center_star,
    year_center_star,
    zibai_year_of,
)

_TZ = ZoneInfo("Asia/Shanghai")


def _ctx(dt: datetime, *, azimuth: float = 320.0, calibers: CaliberRegistry | None = None):
    from app_zeri.schemas import CourseSpec, SiteSpec, TaskSpec, build_context

    return build_context(
        course=CourseSpec(dt=dt),
        site=SiteSpec(azimuth_deg=azimuth),
        task=TaskSpec(kind="修造"),
        calibers=calibers or load_caliber_sets(),
    )


class TestYearPlate:
    def test_known_years(self) -> None:
        """下元甲子（1984）起七赤，逐年逆退：2024 三碧、2025 二黑、2026 一白、2027 九紫。"""
        assert year_center_star(1984) == 7
        assert year_center_star(2024) == 3
        assert year_center_star(2025) == 2
        assert year_center_star(2026) == 1

    def test_lichun_boundary(self) -> None:
        """立春换年：2026-01 的年支仍是乙巳，紫白年应回退一位取 2025。"""
        from datetime import date

        assert zibai_year_of(date(2026, 1, 20), year_zhi="巳") == 2025
        assert zibai_year_of(date(2026, 3, 1), year_zhi="午") == 2026

    def test_year_plate_matches_center(self) -> None:
        f = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ))["facts"]["zibai"]
        assert f["year"]["center"] == 1
        assert f["year"]["zibai_year"] == 2026


class TestMonthPlate:
    @pytest.mark.parametrize(
        ("year_zhi", "expected"),
        [
            # 子午卯酉年正月八白（逐月逆退，九月为九紫，十二月为六白）
            ("午", {1: 8, 2: 7, 9: 9, 12: 6}),
            # 辰戌丑未年正月五黄
            ("戌", {1: 5, 2: 4, 9: 6, 12: 3}),
            # 寅申巳亥年正月二黑（2,1,9,8,7,6,5,4,3,…）
            ("亥", {1: 2, 2: 1, 9: 3, 12: 9}),
        ],
    )
    def test_koujue_table(self, year_zhi: str, expected: dict[int, int]) -> None:
        assert {m: month_center_star(year_zhi, m) for m in expected} == expected

    def test_september_wraps(self) -> None:
        """九个月一循环：正月与十月同星。"""
        for y in ("子", "午", "卯", "酉", "辰", "戌", "丑", "未", "寅", "申", "巳", "亥"):
            assert month_center_star(y, 1) == month_center_star(y, 10)

    def test_month_plate_uses_jieqi_month(self) -> None:
        """2026-11-02 属戌月（节气月第 9），午年 → 九紫入中。"""
        f = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ))["facts"]["zibai"]
        assert f["month"]["month_index"] == 9
        assert f["month"]["center"] == 9


class TestDayHourPlates:
    def test_day_plate_has_dun_and_segment(self) -> None:
        f = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ))["facts"]["zibai"]
        day = f["day"]
        assert day["dun"] == "阴遁"
        assert day["segment"] in ("夏至", "处暑", "霜降")
        assert day["start_star"] in (9, 3, 6)
        assert isinstance(day["center"], int)

    def test_hour_plate_present(self) -> None:
        f = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ))["facts"]["zibai"]
        assert f["hour"]["center"] is not None
        assert f["hour"]["dun"] == "阴遁"

    def test_hour_plate_differs_across_hours_same_day(self) -> None:
        """同一日不同时辰必须得到不同时盘（日级缓存串味的回归护栏）。

        庚辰日阴遁：子时起六白，逐时逆退 → 午时为九紫。若时盘被日级缓存吃掉，
        两个时刻会返回同一个入中星。
        """
        cal = load_caliber_sets()
        zi = _ctx(datetime(2026, 11, 2, 0, 30, tzinfo=_TZ), calibers=cal)["facts"]["zibai"]
        wu = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ), calibers=cal)["facts"]["zibai"]
        assert zi["hour"]["center"] == 6
        assert wu["hour"]["center"] == 9
        assert zi["hour"]["center"] != wu["hour"]["center"]
        # 日盘不受时辰影响
        assert zi["day"]["center"] == wu["day"]["center"]

    def test_hour_plate_matches_formula(self) -> None:
        """时盘入中星 = 起星 ± 时支序；用独立公式再算一遍。"""
        from core_symbol.ganzhi import ZHI

        f = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ))["facts"]["zibai"]
        start, yin_start = 4, 6  # 辰日
        expected = (yin_start - ZHI.index("午") - 1) % 9 + 1
        assert f["hour"]["center"] == expected


class TestCaliber:
    def test_default_is_shun(self) -> None:
        assert load_caliber_sets().chosen(CALIBER_ZIBAI_FLY) == "shun"

    def test_ni_flips_day_and_hour_only(self) -> None:
        shun = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ))
        ni_reg = load_caliber_sets().with_selection({CALIBER_ZIBAI_FLY: "ni"})
        ni = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ), calibers=ni_reg)

        s, n = shun["facts"]["zibai"], ni["facts"]["zibai"]
        assert s["day"]["center"] == n["day"]["center"]  # 入中星相同
        assert s["day"]["palaces"] != n["day"]["palaces"]  # 飞布方向不同
        assert s["month"]["palaces"] == n["month"]["palaces"]  # 月盘恒顺飞
        assert n["caliber"]["fly"] == "ni"
        assert any(a["fly"] == "shun" for a in n["caliber"]["alternatives"])

    def test_caliber_is_echoed_in_facts(self) -> None:
        ctx = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ))
        assert ctx["facts"]["_calibers"]["zibai_fly"] == "shun"

    def test_selection_is_reflected_in_cache_key(self) -> None:
        """换口径必须换日级缓存键，否则第二次调用会拿到旧口径的盘。"""
        cal = load_caliber_sets()
        a = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ), calibers=cal)["facts"]["zibai"]["day"]["palaces"]
        b = _ctx(
            datetime(2026, 11, 2, 12, 0, tzinfo=_TZ),
            calibers=cal.with_selection({CALIBER_ZIBAI_FLY: "ni"}),
        )["facts"]["zibai"]["day"]["palaces"]
        c = _ctx(datetime(2026, 11, 2, 12, 0, tzinfo=_TZ), calibers=cal)["facts"]["zibai"]["day"]["palaces"]
        assert a == c
        assert a != b


class TestEdgeCases:
    """边界与错误契约：缺数据必须降级为 unknown，不得静默给出星位。"""

    def test_missing_terms_degrades_to_none(self) -> None:
        from core_symbol.zibai import derive_zibai_facts

        out = derive_zibai_facts(
            year_zhi="午", month_zhi="戌", day_ganzhi="庚辰", hour_zhi=None,
            local_date=None, terms=None, mountain_name="乾",
        )
        assert out["year"]["center"] is None
        assert out["day"]["center"] is None
        assert out["hour"]["center"] is None
        assert any("日盘缺节气数据" in r for r in out["needs_human_review"])

    def test_illegal_day_ganzhi(self) -> None:
        from core_symbol.zibai import day_center_star

        star, meta = day_center_star("甲子子", __import__("datetime").date(2026, 11, 2), {})
        assert star is None and "error" in meta

    def test_missing_terms_for_dun_raises(self) -> None:
        from core_symbol.zibai import _is_yang_dun

        with pytest.raises(ValueError):
            _is_yang_dun(__import__("datetime").date(2026, 11, 2), {})

    def test_invalid_fly_direction(self) -> None:
        from core_symbol.zibai import fly_palaces

        with pytest.raises(ValueError):
            fly_palaces(5, direction=2)

    def test_invalid_inputs_raise(self) -> None:
        from core_symbol.zibai import hour_center_star, month_center_star

        with pytest.raises(ValueError):
            month_center_star("午", 13)
        with pytest.raises(ValueError):
            month_center_star("甲", 1)
        with pytest.raises(ValueError):
            hour_center_star("甲", "子", yang_dun=True)
        with pytest.raises(ValueError):
            hour_center_star("子", "甲", yang_dun=True)

    def test_unknown_fly_caliber_raises(self) -> None:
        from core_symbol.zibai import derive_zibai_hour

        with pytest.raises(ValueError):
            derive_zibai_hour(day_zhi="辰", hour_zhi="午", yang_dun=False,
                              mountain_name="乾", fly_caliber="sideways")
