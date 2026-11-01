"""节气回归面与交节边界交叉测试。

为什么需要
----------
自实现天文公式的错误模式是**量纲/系数错位**（如 Meeus 28.3 的千年系数配世纪 T，
导致均时差偏差 400 分钟），而不是"缓慢漂移"。这种错只有靠**宽年份回归**才能抓住，
两个点的抽样会漏掉。

三层验证
--------
1. **锚点比对**：2024-2026 年 10 个节气与权威历书对照（容差 2 分钟）。
2. **求解器自检**：把求得的时刻代回 ``apparent_solar_longitude``，必须回到目标黄经
   （容差 1e-4°）。这验证迭代收敛，不验证绝对正确性。
3. **回归年线性**：1900-2100 每年立春的儒略日差必须落在 365.2422±0.2 天内。
   若某年算法失稳，该年与其相邻年的差会显著偏离。

外加**交节边界交叉**：立春 ±10 分钟 × 日界(早/晚) × 真太阳时(开/关)，
断言年柱/月柱归属可解释（真太阳时会改变归属，且方向必须正确）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from core_time import (
    CalendarConfig,
    apparent_solar_longitude,
    compute_four_pillars,
    jd_tt_from_jd_ut,
    julian_day_from_datetime,
    term_datetime,
    terms_of_year,
)

CST = ZoneInfo("Asia/Shanghai")
TOL = timedelta(minutes=2)
TROPICAL_YEAR = 365.2422

#: (节气, 年, 权威时刻, 容差分钟) —— 取自公开历书（紫金山天文台口径）
ANCHORS = [
    ("立春", 2024, datetime(2024, 2, 4, 16, 26, 53, tzinfo=CST), 2),
    ("春分", 2024, datetime(2024, 3, 20, 11, 6, 21, tzinfo=CST), 2),
    ("夏至", 2024, datetime(2024, 6, 21, 4, 50, 46, tzinfo=CST), 2),
    ("秋分", 2024, datetime(2024, 9, 22, 20, 43, 45, tzinfo=CST), 2),
    ("冬至", 2024, datetime(2024, 12, 21, 17, 20, 34, tzinfo=CST), 2),
    ("立春", 2025, datetime(2025, 2, 3, 22, 10, 13, tzinfo=CST), 2),
    ("春分", 2025, datetime(2025, 3, 20, 17, 1, 15, tzinfo=CST), 2),
    ("夏至", 2025, datetime(2025, 6, 21, 10, 42, 0, tzinfo=CST), 2),
    ("秋分", 2025, datetime(2025, 9, 23, 2, 19, 4, tzinfo=CST), 2),
    ("冬至", 2025, datetime(2025, 12, 21, 23, 2, 48, tzinfo=CST), 2),
    ("立春", 2026, datetime(2026, 2, 4, 4, 1, 51, tzinfo=CST), 2),
]


@pytest.mark.parametrize("name,year,expected,tol_min", ANCHORS, ids=[f"{a[1]}{a[0]}" for a in ANCHORS])
def test_anchor_against_almanac(name: str, year: int, expected: datetime, tol_min: int) -> None:
    got = term_datetime(name, year, "Asia/Shanghai")
    delta = abs(got - expected)
    assert delta <= timedelta(minutes=tol_min), f"{year}{name}: 得到 {got}，权威 {expected}，偏差 {delta}"


@pytest.mark.parametrize("year", list(range(1900, 2101, 10)) + [1900, 2100])
def test_solver_converges_all_terms(year: int) -> None:
    """1900-2100 每 10 年：24 节气求解后必须精确回到目标黄经。"""
    for term in terms_of_year(year, "Asia/Shanghai"):
        lon = apparent_solar_longitude(jd_tt_from_jd_ut(term.jd_ut))
        diff = abs((lon - term.longitude + 180) % 360 - 180)
        assert diff < 1e-4, f"{year}{term.name}: 代回黄经偏差 {diff:.6f}°"


@pytest.mark.parametrize("year", list(range(1900, 2100, 5)))
def test_lichun_tropical_year_linearity(year: int) -> None:
    """立春的儒略日差必须≈回归年（365.2422 天），防止某年算法失稳。"""
    a = term_datetime("立春", year, "Asia/Shanghai")
    b = term_datetime("立春", year + 1, "Asia/Shanghai")
    delta = (b - a).total_seconds() / 86400.0
    assert abs(delta - TROPICAL_YEAR) < 0.2, (
        f"{year}→{year + 1} 立春间隔 {delta:.4f} 天，偏离回归年 {TROPICAL_YEAR}"
    )


@pytest.mark.parametrize("year", [1900, 1950, 2000, 2050, 2100])
def test_terms_within_year_monotonic_and_gaps(year: int) -> None:
    terms = terms_of_year(year, "Asia/Shanghai")
    assert len(terms) == 24
    for a, b in zip(terms, terms[1:]):
        gap = (b.local - a.local).total_seconds() / 86400.0
        assert 14.0 < gap < 16.5, f"{year}: {a.name}→{b.name} 间隔 {gap:.2f} 天"


# --------------------------------------------------------------------------- #
# 交节边界交叉：立春 × 日界 × 真太阳时
# --------------------------------------------------------------------------- #
def _lichun_2027() -> datetime:
    return term_datetime("立春", 2027, "Asia/Shanghai")


def test_boundary_switch_within_20_minutes() -> None:
    """立春前后 10 分钟，年柱必须切换（否则说明交节时刻未被正确使用）。"""
    lichun = _lichun_2027()
    before = compute_four_pillars(lichun - timedelta(minutes=10))
    after = compute_four_pillars(lichun + timedelta(minutes=10))
    assert before.year.name == "丙午"
    assert after.year.name == "丁未"


@pytest.mark.parametrize("day_boundary", ["early", "late"])
def test_boundary_cross_day_boundary(day_boundary: str) -> None:
    """日界口径不改变"交节即换年"这一事实（交节时刻在白天）。"""
    lichun = _lichun_2027()
    cfg = CalendarConfig(day_boundary=day_boundary)  # type: ignore[arg-type]
    before = compute_four_pillars(lichun - timedelta(minutes=10), cfg)
    after = compute_four_pillars(lichun + timedelta(minutes=10), cfg)
    assert before.year.name == "丙午"
    assert after.year.name == "丁未"


def test_true_solar_time_shifts_year_boundary() -> None:
    """真太阳时会平移交节判定：东经 113° 下，交节后 10 分钟可能仍被判在交节前。

    这不是 bug，而是"真太阳时口径"的必然结果 —— 但必须**方向正确**且可解释。
    """
    lichun = _lichun_2027()
    local_after = lichun + timedelta(minutes=10)

    civil = compute_four_pillars(local_after, CalendarConfig(use_true_solar_time=False))
    solar = compute_four_pillars(
        local_after, CalendarConfig(use_true_solar_time=True), lon=113.26
    )

    # 民用时：已过交节 → 丁未年
    assert civil.year.name == "丁未"
    # 真太阳时：经度时差约 -27 分钟 + 均时差，把 09:56 拉回 09:28 左右 → 仍在交节前
    assert solar.year.name == "丙午", "真太阳时应把交节后 10 分钟拉回交节前（东经 113°）"
    assert solar.hour_reference < lichun


def test_true_solar_time_does_not_change_pillar_arithmetic() -> None:
    """真太阳时只改"用哪个时刻定四柱"，不改干支排布规则本身。"""
    at = datetime(2027, 7, 11, 14, 0, tzinfo=CST)
    a = compute_four_pillars(at, CalendarConfig(use_true_solar_time=False))
    b = compute_four_pillars(at, CalendarConfig(use_true_solar_time=True), lon=120.0)
    # 东经 120° 恰为标准经线，仅差均时差（约 -5 分钟），不应跨时辰
    assert a.bazi == b.bazi


def test_month_pillar_switches_at_jie() -> None:
    """月柱在"节"（小暑）处切换，不在"气"（大暑）处切换。"""
    xiaoshu = term_datetime("小暑", 2027, "Asia/Shanghai")
    before = compute_four_pillars(xiaoshu - timedelta(minutes=10))
    after = compute_four_pillars(xiaoshu + timedelta(minutes=10))
    assert before.month.zhi == "午"
    assert after.month.zhi == "未"

    dashu = term_datetime("大暑", 2027, "Asia/Shanghai")
    b2 = compute_four_pillars(dashu - timedelta(minutes=10))
    a2 = compute_four_pillars(dashu + timedelta(minutes=10))
    assert b2.month.zhi == a2.month.zhi == "未", "大暑是气，不换月"


def test_jd_roundtrip_across_two_centuries() -> None:
    from core_time.ephemeris import datetime_from_julian_day

    for year in (1900, 1950, 2000, 2050, 2100):
        dt = datetime(year, 6, 15, 12, tzinfo=timezone.utc)
        jd = julian_day_from_datetime(dt)
        back = datetime_from_julian_day(jd)
        assert abs((back - dt).total_seconds()) < 0.01, f"{year} JD 往返偏差 {back - dt}"
