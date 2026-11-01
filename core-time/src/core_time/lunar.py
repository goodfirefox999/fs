"""农历（定朔定气）与闰月（事实层）。

算法
----
1. 朔：Meeus《Astronomical Algorithms》第 49 章新月算法（含 14 项行星摄动修正），
   精度约 ±1 分钟量级，足以判定"朔落在哪一日"（边界情形在 docs 已知限制中登记）。
2. 月：以含冬至之朔望月为十一月，逐月编号。
3. 闰：若从本年十一月朔到次年十一月朔之间有 13 个朔望月，则取第一个不含中气之月为闰月
   （"无中气置闰"）。
4. 日界：以 ``Asia/Shanghai`` 本地日期为准（中国农历定朔惯例）。

本模块不判断吉凶。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from .ephemeris import (
    datetime_from_julian_day,
    jd_tt_from_jd_ut,
    jd_ut_from_jd_tt,
    julian_day_from_datetime,
)
from .jieqi import terms_of_year

__all__ = [
    "LunarDate",
    "LunarMonth",
    "lunar_date_of",
    "chinese_new_year",
    "lunar_months_of_year",
    "lunar_to_solar",
    "LUNAR_MONTH_NAMES",
    "LUNAR_DAY_NAMES",
]

LUNAR_MONTH_NAMES = (
    "正月",
    "二月",
    "三月",
    "四月",
    "五月",
    "六月",
    "七月",
    "八月",
    "九月",
    "十月",
    "冬月",
    "腊月",
)
LUNAR_DAY_NAMES = (
    "初一",
    "初二",
    "初三",
    "初四",
    "初五",
    "初六",
    "初七",
    "初八",
    "初九",
    "初十",
    "十一",
    "十二",
    "十三",
    "十四",
    "十五",
    "十六",
    "十七",
    "十八",
    "十九",
    "二十",
    "廿一",
    "廿二",
    "廿三",
    "廿四",
    "廿五",
    "廿六",
    "廿七",
    "廿八",
    "廿九",
    "三十",
)

_SYNODIC_MONTH = 29.530588861
_NEW_MOON_EPOCH = 2451550.09766  # 2000-01-06 18:14 TT 附近的新月


def _new_moon_jde(k: int) -> float:
    """第 k 个新月的 TT 儒略日（k=0 对应 2000-01 新月）。"""
    t = k / 1236.85
    jde = (
        _NEW_MOON_EPOCH
        + _SYNODIC_MONTH * k
        + 0.00015437 * t**2
        - 0.000000150 * t**3
        + 0.00000000073 * t**4
    )
    e = 1.0 - 0.002516 * t - 0.0000074 * t**2
    m = math.radians((2.5534 + 29.10535670 * k - 0.0000014 * t**2 - 0.00000011 * t**3) % 360.0)
    mp = math.radians(
        (201.5643 + 385.81693528 * k + 0.0107582 * t**2 + 0.00001238 * t**3 - 0.000000058 * t**4)
        % 360.0
    )
    f = math.radians(
        (160.7108 + 390.67050284 * k - 0.0016118 * t**2 - 0.00000227 * t**3 + 0.000000011 * t**4)
        % 360.0
    )
    omega = math.radians((124.7746 - 1.56375588 * k + 0.0020672 * t**2 + 0.00000215 * t**3) % 360.0)

    corr = (
        -0.40720 * math.sin(mp)
        + 0.17241 * e * math.sin(m)
        + 0.01608 * math.sin(2 * mp)
        + 0.01039 * math.sin(2 * f)
        + 0.00739 * e * math.sin(mp - m)
        - 0.00514 * e * math.sin(mp + m)
        + 0.00208 * e * e * math.sin(2 * m)
        - 0.00111 * math.sin(mp - 2 * f)
        - 0.00057 * math.sin(mp + 2 * f)
        + 0.00056 * e * math.sin(2 * mp + m)
        - 0.00042 * math.sin(3 * mp)
        + 0.00042 * e * math.sin(m + 2 * f)
        + 0.00038 * e * math.sin(m - 2 * f)
        - 0.00024 * e * math.sin(2 * mp - m)
        - 0.00017 * math.sin(omega)
        - 0.00007 * math.sin(mp + 2 * m)
        + 0.00004 * math.sin(2 * mp - 2 * f)
        + 0.00004 * math.sin(3 * m)
        + 0.00003 * math.sin(mp + m - 2 * f)
        + 0.00003 * math.sin(2 * mp + 2 * f)
        - 0.00003 * math.sin(mp + m + 2 * f)
        + 0.00003 * math.sin(mp - m + 2 * f)
        - 0.00002 * math.sin(mp - m - 2 * f)
        - 0.00002 * math.sin(3 * mp + m)
        + 0.00002 * math.sin(4 * mp)
    )

    a = (
        299.77 + 0.107408 * k - 0.009173 * t**2,
        251.88 + 0.016321 * k,
        251.83 + 26.651886 * k,
        349.42 + 36.412478 * k,
        84.66 + 18.206239 * k,
        141.74 + 53.303771 * k,
        207.14 + 2.453732 * k,
        154.84 + 7.306860 * k,
        34.52 + 27.261239 * k,
        207.19 + 0.121824 * k,
        291.34 + 1.844379 * k,
        161.72 + 24.198154 * k,
        239.56 + 25.513099 * k,
        331.55 + 3.592518 * k,
    )
    weights = (0.000325, 0.000165, 0.000164, 0.000126, 0.000110, 0.000062, 0.000060,
               0.000056, 0.000047, 0.000042, 0.000040, 0.000037, 0.000035, 0.000023)
    corr += sum(w * math.sin(math.radians(x % 360.0)) for w, x in zip(weights, a))
    return jde + corr


def _new_moon_local_date(k: int, tz: ZoneInfo) -> date:
    jde = _new_moon_jde(k)
    jd_ut = jd_ut_from_jd_tt(jde)
    return datetime_from_julian_day(jd_ut).astimezone(tz).date()


def _k_estimate(d: date) -> int:
    from datetime import time

    jd = julian_day_from_datetime(datetime.combine(d, time(12, 0), tzinfo=timezone.utc))
    return int(round((jd - _NEW_MOON_EPOCH) / _SYNODIC_MONTH))


@dataclass(frozen=True)
class LunarMonth:
    """一个农历月。``start`` 为朔日（初一），``days`` 为 29 或 30。"""

    start: date
    month: int
    is_leap: bool
    lunar_year: int
    days: int

    @property
    def end(self) -> date:
        return self.start + timedelta(days=self.days - 1)

    @property
    def name(self) -> str:
        base = LUNAR_MONTH_NAMES[self.month - 1]
        return f"闰{base}" if self.is_leap else base


@dataclass(frozen=True)
class LunarDate:
    year: int
    month: int
    day: int
    is_leap: bool
    month_name: str
    day_name: str

    def __str__(self) -> str:  # 便于报告
        return f"{self.year}年{self.month_name}{self.day_name}"


def _winter_solstice(year: int, tz_name: str) -> date:
    for term in terms_of_year(year, tz_name):
        if term.name == "冬至":
            return term.local.date()
    raise AssertionError("冬至缺失")  # pragma: no cover


@lru_cache(maxsize=512)
def _cycle_months(year: int, tz_name: str = "Asia/Shanghai") -> tuple[LunarMonth, ...]:
    """构造以"含 ``year`` 年冬至之朔望月"为十一月的连续月序列。

    序列起点为十一月，终点为下一个十一月之前一月，共 12 或 13 个月。
    归属规则：编号 11、12 属农历 ``year`` 年；编号 1-10 属农历 ``year+1`` 年。
    该基准可正确处理年末闰月（闰十一月/闰十二月，如 2033 年）。
    """
    tz = ZoneInfo(tz_name)
    ws_a = _winter_solstice(year, tz_name)
    ws_b = _winter_solstice(year + 1, tz_name)

    k0 = _k_estimate(ws_a - timedelta(days=40))
    starts: list[date] = sorted({_new_moon_local_date(k, tz) for k in range(k0, k0 + 24)})

    def month_start_on_or_before(d: date) -> date:
        cands = [s for s in starts if s <= d]
        if not cands:  # pragma: no cover
            raise AssertionError("朔日序列不足")
        return cands[-1]

    idx_a = starts.index(month_start_on_or_before(ws_a))
    idx_b = starts.index(month_start_on_or_before(ws_b))
    n_months = idx_b - idx_a
    if n_months not in (12, 13):  # pragma: no cover - 结构性断言
        raise AssertionError(f"{year} 农历月数异常: {n_months}")

    zhongqi_dates: set[date] = set()
    for y in (year, year + 1, year + 2):
        for term in terms_of_year(y, tz_name):
            if term.kind == "qi":
                zhongqi_dates.add(term.local.date())

    month_starts = starts[idx_a : idx_b + 1]
    has_zhongqi = [
        any(month_starts[i] <= z < month_starts[i + 1] for z in zhongqi_dates)
        for i in range(n_months)
    ]

    leap_index: int | None = None
    if n_months == 13:
        for i in range(1, n_months):
            if not has_zhongqi[i]:
                leap_index = i
                break
        if leap_index is None:  # pragma: no cover - 理论上不应发生
            leap_index = n_months - 1

    months: list[LunarMonth] = []
    month_no = 11
    prev_no = 11
    for i in range(n_months):
        start = month_starts[i]
        days = (month_starts[i + 1] - start).days
        is_leap = leap_index == i
        cur_no = prev_no if is_leap else month_no
        lunar_year = year if cur_no >= 11 else year + 1
        months.append(
            LunarMonth(start=start, month=cur_no, is_leap=is_leap, lunar_year=lunar_year, days=days)
        )
        if not is_leap:
            prev_no = month_no
            month_no = month_no % 12 + 1
    return tuple(months)


@lru_cache(maxsize=256)
def _months_for_lunar_year(year: int, tz_name: str = "Asia/Shanghai") -> tuple[LunarMonth, ...]:
    """农历 ``year`` 年（正月初一 → 除夕）的月表，按时间升序。"""
    prev_cycle = [m for m in _cycle_months(year - 1, tz_name) if m.lunar_year == year]
    own_cycle = [m for m in _cycle_months(year, tz_name) if m.lunar_year == year]
    months = sorted(prev_cycle + own_cycle, key=lambda m: m.start)
    if not months:  # pragma: no cover
        raise AssertionError(f"农历 {year} 年无月份")
    return tuple(months)


def lunar_months_of_year(year: int, tz_name: str = "Asia/Shanghai") -> tuple[LunarMonth, ...]:
    """农历 ``year`` 年的月表（正月在前，含闰月）。"""
    return _months_for_lunar_year(year, tz_name)


def lunar_date_of(d: date, tz_name: str = "Asia/Shanghai") -> LunarDate:
    """公历日期 → 农历日期。"""
    for candidate in (d.year, d.year - 1, d.year + 1):
        for month in _months_for_lunar_year(candidate, tz_name):
            if month.start <= d <= month.end:
                day = (d - month.start).days + 1
                return LunarDate(
                    year=month.lunar_year,
                    month=month.month,
                    day=day,
                    is_leap=month.is_leap,
                    month_name=month.name,
                    day_name=LUNAR_DAY_NAMES[day - 1],
                )
    raise AssertionError(f"无法定位农历日期: {d}")  # pragma: no cover


def chinese_new_year(year: int, tz_name: str = "Asia/Shanghai") -> date:
    """农历 ``year`` 年正月初一（公历日期）。"""
    months = lunar_months_of_year(year, tz_name)
    for m in months:
        if m.month == 1 and not m.is_leap:
            return m.start
    raise AssertionError(f"{year} 年无正月")  # pragma: no cover


def lunar_to_solar(year: int, month: int, day: int, is_leap: bool = False,
                   tz_name: str = "Asia/Shanghai") -> date:
    """农历 → 公历。``month`` 取 1-12。"""
    for m in lunar_months_of_year(year, tz_name):
        if m.month == month and m.is_leap == is_leap:
            if not 1 <= day <= m.days:
                raise ValueError(f"{m.name} 只有 {m.days} 天")
            return m.start + timedelta(days=day - 1)
    raise ValueError(f"{year} 年无 {'闰' if is_leap else ''}{month} 月")


def leap_month_of(year: int, tz_name: str = "Asia/Shanghai") -> int | None:
    """返回农历 ``year`` 年的闰月月号，无闰月返回 ``None``。"""
    for m in lunar_months_of_year(year, tz_name):
        if m.is_leap:
            return m.month
    return None


_ = (datetime, timezone, jd_tt_from_jd_ut)  # 保留引用，避免静态检查误报
