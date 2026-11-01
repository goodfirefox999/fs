"""事实层测试：节气精度、四柱、日界/年界、农历闰月、真太阳时。

数值基准取自公开权威历书（紫金山天文台《中国天文年历》口径），容差 ±2 分钟，
对应本系统"节气时刻 ±1 分钟"精度目标 + ΔT 模型不确定度。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from core_time import (
    CalendarConfig,
    apparent_solar_longitude,
    chinese_new_year,
    compute_four_pillars,
    delta_t,
    julian_day_from_datetime,
    leap_month_of,
    lunar_date_of,
    lunar_to_solar,
    term_datetime,
    terms_of_year,
    true_solar_time,
)
from core_time.calendar import day_pillar_index, ganzhi_index, GANZHI60, jdn_of_date
from core_time.ephemeris import datetime_from_julian_day

CST = ZoneInfo("Asia/Shanghai")
TOL = timedelta(minutes=2)

#: (节气名, 年, 权威时刻) —— 公开历书值
GOLDEN_TERMS = [
    ("立春", 2024, datetime(2024, 2, 4, 16, 26, 53, tzinfo=CST)),
    ("立春", 2025, datetime(2025, 2, 3, 22, 10, 13, tzinfo=CST)),
    ("春分", 2025, datetime(2025, 3, 20, 17, 1, 15, tzinfo=CST)),
    ("冬至", 2025, datetime(2025, 12, 21, 23, 2, 48, tzinfo=CST)),
    ("立春", 2026, datetime(2026, 2, 4, 4, 1, 51, tzinfo=CST)),
]


@pytest.mark.parametrize("name,year,expected", GOLDEN_TERMS)
def test_solar_term_precision(name: str, year: int, expected: datetime) -> None:
    got = term_datetime(name, year, "Asia/Shanghai")
    assert abs(got - expected) <= TOL, f"{year}{name}: 得到 {got}，权威 {expected}"


def test_terms_count_and_monotonic() -> None:
    for year in (2024, 2025, 2026, 2027, 2033):
        terms = terms_of_year(year, "Asia/Shanghai")
        assert len(terms) == 24, f"{year} 年节气数 {len(terms)}"
        for a, b in zip(terms, terms[1:]):
            assert a.jd_ut < b.jd_ut, f"{year} 年节气非严格单调：{a.name} → {b.name}"
        # 相邻节气间隔应在 14~16.5 天
        for a, b in zip(terms, terms[1:]):
            gap = b.jd_ut - a.jd_ut
            assert 14.0 < gap < 16.5, f"{a.name}→{b.name} 间隔异常 {gap:.2f} 天"


def test_terms_no_overlap_across_years() -> None:
    a = terms_of_year(2026, "Asia/Shanghai")
    b = terms_of_year(2027, "Asia/Shanghai")
    assert a[-1].jd_ut < b[0].jd_ut


def test_delta_t_reasonable() -> None:
    assert 60.0 < delta_t(2025) < 80.0
    assert -5.0 < delta_t(1900) < 5.0


def test_julian_day_roundtrip() -> None:
    dt = datetime(2027, 7, 11, 14, 30, 15, tzinfo=timezone.utc)
    jd = julian_day_from_datetime(dt)
    back = datetime_from_julian_day(jd)
    assert abs((back - dt).total_seconds()) < 0.01


def test_day_pillar_known_anchor() -> None:
    """2000-01-01 为戊午日（公开历表基准）。"""
    assert GANZHI60[day_pillar_index(date(2000, 1, 1))] == "戊午"
    assert GANZHI60[day_pillar_index(date(1949, 10, 1))] == "甲子"


def test_jdn_consistency() -> None:
    assert jdn_of_date(date(2000, 1, 1)) == 2451545


def test_ganzhi_index_roundtrip() -> None:
    for i, gz in enumerate(GANZHI60):
        assert ganzhi_index(gz[0], gz[1]) == i


def test_golden_four_pillars() -> None:
    """金标准案例：2027-07-11 未时 = 丁未 丁未 辛卯 乙未。"""
    p = compute_four_pillars(datetime(2027, 7, 11, 14, 0, tzinfo=CST))
    assert p.bazi == "丁未 丁未 辛卯 乙未"
    assert p.jie_name == "小暑"


def test_year_boundary_lichun_switch() -> None:
    """2024 立春 16:27 前后年柱切换。"""
    before = compute_four_pillars(datetime(2024, 2, 4, 16, 0, tzinfo=CST))
    after = compute_four_pillars(datetime(2024, 2, 4, 17, 0, tzinfo=CST))
    assert before.year.name == "癸卯"
    assert after.year.name == "甲辰"


def test_year_boundary_newyear_option() -> None:
    """正月初一换年口径下，立春前仍属旧年，春节后属新年。"""
    cfg = CalendarConfig(year_boundary="newyear")
    cny = chinese_new_year(2024)  # 2024-02-10
    before = compute_four_pillars(
        datetime(cny.year, cny.month, cny.day, 12, 0, tzinfo=CST) - timedelta(days=1), cfg
    )
    after = compute_four_pillars(datetime(cny.year, cny.month, cny.day, 12, 0, tzinfo=CST), cfg)
    assert before.year.name == "癸卯"
    assert after.year.name == "甲辰"


def test_day_boundary_early_vs_late() -> None:
    """23:30 在子初换日下归次日，在子正换日下仍属当日。"""
    late = compute_four_pillars(datetime(2027, 7, 11, 23, 30, tzinfo=CST), CalendarConfig(day_boundary="late"))
    early = compute_four_pillars(datetime(2027, 7, 11, 23, 30, tzinfo=CST), CalendarConfig(day_boundary="early"))
    assert late.day.name == "辛卯"
    assert early.day.name == "壬辰"
    # 时柱随时干变化：辛日子时戊子，壬日子时庚子
    assert late.hour.name == "戊子"
    assert early.hour.name == "庚子"


def test_month_pillar_wu_hu_dun() -> None:
    """五虎遁：丁年寅月壬寅，未月丁未。"""
    p = compute_four_pillars(datetime(2027, 7, 11, 14, 0, tzinfo=CST))
    assert p.month.name == "丁未"
    assert p.year.gan == "丁"


def test_hour_pillar_wu_shu_dun() -> None:
    """五鼠遁：辛日未时乙未。"""
    p = compute_four_pillars(datetime(2027, 7, 11, 14, 0, tzinfo=CST))
    assert p.hour.name == "乙未"


@pytest.mark.parametrize(
    "year,expected",
    [(2024, date(2024, 2, 10)), (2025, date(2025, 1, 29)), (2026, date(2026, 2, 17)),
     (2027, date(2027, 2, 6)), (2028, date(2028, 1, 26))],
)
def test_chinese_new_year(year: int, expected: date) -> None:
    assert chinese_new_year(year) == expected


@pytest.mark.parametrize(
    "year,leap_month",
    [(2020, 4), (2023, 2), (2025, 6), (2028, 5), (2031, 3), (2033, 11), (2036, 6)],
)
def test_leap_month(year: int, leap_month: int) -> None:
    """闰月回归：含 2033 年罕见的闰十一月（闰冬月）。"""
    assert leap_month_of(year) == leap_month


def test_leap_month_start_dates() -> None:
    assert lunar_to_solar(2020, 4, 1, is_leap=True) == date(2020, 5, 23)
    assert lunar_to_solar(2023, 2, 1, is_leap=True) == date(2023, 3, 22)
    assert lunar_to_solar(2025, 6, 1, is_leap=True) == date(2025, 7, 25)
    assert lunar_to_solar(2033, 11, 1, is_leap=True) == date(2033, 12, 22)


def test_lunar_roundtrip_sweep() -> None:
    """农历 → 公历 → 农历 往返一致性（抽样 3 年逐月逐日）。"""
    for year in (2024, 2025, 2033):
        for month in range(1, 13):
            for is_leap in (False, True):
                try:
                    start = lunar_to_solar(year, month, 1, is_leap=is_leap)
                except ValueError:
                    continue
                ld = lunar_date_of(start)
                assert (ld.year, ld.month, ld.is_leap) == (year, month, is_leap)
                assert ld.day == 1


def test_lunar_no_duplicate_days() -> None:
    """连续 400 天农历日期严格递增且日序连续。"""
    d = date(2026, 1, 1)
    prev = lunar_date_of(d)
    for i in range(1, 400):
        cur = lunar_date_of(d + timedelta(days=i))
        if cur.day == 1:
            assert cur.month != prev.month or cur.is_leap != prev.is_leap or cur.year != prev.year
        else:
            assert cur.day == prev.day + 1, f"{d + timedelta(days=i)} 日序断裂"
        prev = cur


def test_true_solar_time_longitude_effect() -> None:
    """东经 120° 与 113° 的真太阳时差约 28 分钟（经度时差）。"""
    at = datetime(2027, 7, 11, 12, 0, tzinfo=CST)
    t120 = true_solar_time(at, 120.0)
    t113 = true_solar_time(at, 113.0)
    diff_min = (t120 - t113).total_seconds() / 60.0
    assert 27.0 < diff_min < 29.0


def test_solar_longitude_bounds() -> None:
    for month in range(1, 13):
        lon = apparent_solar_longitude(
            julian_day_from_datetime(datetime(2027, month, 15, 12, tzinfo=timezone.utc))
        )
        assert 0.0 <= lon < 360.0


def test_config_manifest_roundtrip() -> None:
    cfg = CalendarConfig(day_boundary="early", year_boundary="newyear", use_true_solar_time=True)
    manifest = cfg.to_manifest()
    assert manifest["day_boundary"] == "early"
    assert manifest["year_boundary"] == "newyear"
    assert manifest["use_true_solar_time"] is True


def test_config_rejects_bad_values() -> None:
    with pytest.raises(ValueError):
        CalendarConfig(day_boundary="midnight")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        CalendarConfig(year_boundary="solar")  # type: ignore[arg-type]
