"""二十八宿值日测试（Phase 11）。

验证策略（三层，缺一不可）
--------------------------
1. **锚点**：1996-01-28 必须同时是「甲子日」「星期日」「虚宿」——三者任一不符，
   整张表就漂了。
2. **内禀不变式**：宿的七政必须等于当日星期，逐日扫 1900-2100（约 7.3 万日）。
   这条恒等式不依赖任何外部历书，却能抓住「错一位」这类最常见的表错。
3. **外部对算**：与两份黄历页面（2026-11-02 毕月乌、2027-07-11 昴日鸡）逐项核对。
   外部样本只证明区间内某点，故必须与 2 并用；单独用 3 是抽样，单独用 2 是自证。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from core_symbol.xiu import (
    QI_ZHENG,
    WEEKDAY_QIZHENG,
    XIU_ANCHOR,
    XIU_ORDER,
    XIU_TABLE,
    qizheng_of_date,
    weekday_consistent,
    xiu_index_of_date,
    xiu_of_date,
    yuan_of_date,
)
from core_time import CalendarConfig, compute_four_pillars

from datetime import datetime
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Asia/Shanghai")


def _day_ganzhi(d: date) -> str:
    return compute_four_pillars(datetime(d.year, d.month, d.day, 12, 0, tzinfo=_TZ), CalendarConfig()).day.name


class TestAnchor:
    def test_anchor_is_jiazi_sunday_xu(self) -> None:
        assert _day_ganzhi(XIU_ANCHOR) == "甲子"
        assert XIU_ANCHOR.weekday() == 6, "1996-01-28 应为星期日"
        assert xiu_of_date(XIU_ANCHOR).name == "虚"
        assert yuan_of_date(XIU_ANCHOR) == 1

    def test_420_day_cycle_returns_to_anchor(self) -> None:
        """七元 = 420 日 = 60 干支 × 7，走完复归一元起虚。"""
        later = XIU_ANCHOR + timedelta(days=420)
        assert xiu_of_date(later).name == "虚"
        assert yuan_of_date(later) == 1
        assert _day_ganzhi(later) == "甲子"

    def test_qi_yuan_table(self) -> None:
        """七元起宿：一元虚、二元奎、三元毕、四元鬼、五元翼、六元氐、七元箕。"""
        expected = ["虚", "奎", "毕", "鬼", "翼", "氐", "箕"]
        for i, name in enumerate(expected):
            d = XIU_ANCHOR + timedelta(days=60 * i)
            assert yuan_of_date(d) == i + 1
            assert xiu_of_date(d).name == name, f"第 {i + 1} 元应起{name}"


class TestTables:
    def test_28_in_order(self) -> None:
        assert len(XIU_TABLE) == 28
        assert tuple(x.name for x in XIU_TABLE) == XIU_ORDER
        assert XIU_ORDER[0] == "角" and XIU_ORDER[-1] == "轸"

    def test_full_names(self) -> None:
        assert xiu_of_date(XIU_ANCHOR).full_name == "虚日鼠"
        by_name = {x.name: x for x in XIU_TABLE}
        assert by_name["角"].full_name == "角木蛟"
        assert by_name["氐"].full_name == "氐土貉"
        assert by_name["房"].full_name == "房日兔"
        assert by_name["昴"].full_name == "昴日鸡"
        assert by_name["毕"].full_name == "毕月乌"

    def test_qizheng_cycles_with_index(self) -> None:
        for x in XIU_TABLE:
            assert x.qizheng == QI_ZHENG[x.index % 7]


class TestWeekdayInvariant:
    def test_no_violation_1900_2100(self) -> None:
        """宿的七政 == 当日星期，逐日校验。表错一位即在此暴露。"""
        d = date(1900, 1, 1)
        end = date(2100, 12, 31)
        bad: list[date] = []
        while d <= end:
            if qizheng_of_date(d) != WEEKDAY_QIZHENG[d.weekday()]:
                bad.append(d)
            d += timedelta(days=1)
        assert bad == [], f"星期恒等式违例 {len(bad)} 天，首例 {bad[:3]}"

    def test_invariant_holds_by_construction_for_any_offset(self) -> None:
        """即使换成别的一元锚点（只要仍是甲子日+虚宿），恒等式照样成立。

        这解释为什么锚点选哪一年不影响结论：28 与 7 的最小公倍数是 28，
        宿序每 +1 日，七政同时 +1，故只有「表内顺序」与「起宿」两个自由度。
        """
        assert all(weekday_consistent(XIU_ANCHOR + timedelta(days=k)) for k in range(0, 840, 7))


class TestExternalCrossCheck:
    """外部对算：两份黄历页面的值宿（见 docs/research/2026-11-xiu-jishen-zibai.md）。"""

    @pytest.mark.parametrize(
        ("d", "expected"),
        [
            (date(2026, 11, 2), "毕"),
            (date(2027, 7, 11), "昴"),
        ],
    )
    def test_almanac_day(self, d: date, expected: str) -> None:
        assert xiu_of_date(d).name == expected

    def test_ganzhi_of_cross_check_days(self) -> None:
        """两个对算日期的日柱须与黄历一致，否则「同日」前提不成立。"""
        assert _day_ganzhi(date(2026, 11, 2)) == "庚辰"
        assert _day_ganzhi(date(2027, 7, 11)) == "辛卯"


class TestFactsIntegration:
    def test_facts_xiu_present_and_neutral(self) -> None:
        from app_zeri.schemas import CourseSpec, SiteSpec, TaskSpec, build_context

        ctx = build_context(
            course=CourseSpec(dt=datetime(2026, 11, 2, 12, 0, tzinfo=_TZ)),
            site=SiteSpec(azimuth_deg=320.0),
            task=TaskSpec(kind="修造"),
        )
        xiu = ctx["facts"]["xiu"]
        assert xiu["day"] == "毕"
        assert xiu["weekday_consistent"] is True
        assert xiu["status"] == "待考证"
        # 符号层不得出现吉凶字样
        assert not any(w in str(xiu) for w in ("吉", "凶", "宜", "忌"))
