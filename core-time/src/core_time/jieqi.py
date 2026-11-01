"""二十四节气（事实层）。

节气定义：太阳视黄经每 15° 一个节气，共 24 个。
其中"节"（12 个）用于月柱换月，"气"（12 个，含中气）用于农历置闰。

精度：见 ``ephemeris``，节气时刻误差 < 2 分钟（实测与权威历书差 15 s 量级）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from .ephemeris import (
    datetime_from_julian_day,
    julian_day_from_datetime,
    solve_solar_longitude,
)

__all__ = [
    "SOLAR_TERMS",
    "SolarTerm",
    "terms_of_year",
    "terms_between",
    "jie_before",
    "month_branch_index",
    "zhongqi_of_year",
]

TermKind = Literal["jie", "qi"]

#: (名称, 太阳视黄经, 类型, 公历锚点月, 公历锚点日)
#: 锚点仅用于牛顿迭代初值，不参与最终判定。
SOLAR_TERMS: tuple[tuple[str, int, TermKind, int, int], ...] = (
    ("小寒", 285, "jie", 1, 6),
    ("大寒", 300, "qi", 1, 20),
    ("立春", 315, "jie", 2, 4),
    ("雨水", 330, "qi", 2, 19),
    ("惊蛰", 345, "jie", 3, 6),
    ("春分", 0, "qi", 3, 20),
    ("清明", 15, "jie", 4, 5),
    ("谷雨", 30, "qi", 4, 20),
    ("立夏", 45, "jie", 5, 6),
    ("小满", 60, "qi", 5, 21),
    ("芒种", 75, "jie", 6, 6),
    ("夏至", 90, "qi", 6, 21),
    ("小暑", 105, "jie", 7, 7),
    ("大暑", 120, "qi", 7, 23),
    ("立秋", 135, "jie", 8, 8),
    ("处暑", 150, "qi", 8, 23),
    ("白露", 165, "jie", 9, 8),
    ("秋分", 180, "qi", 9, 23),
    ("寒露", 195, "jie", 10, 8),
    ("霜降", 210, "qi", 10, 23),
    ("立冬", 225, "jie", 11, 7),
    ("小雪", 240, "qi", 11, 22),
    ("大雪", 255, "jie", 12, 7),
    ("冬至", 270, "qi", 12, 22),
)

#: 节气名 → 黄经
TERM_LONGITUDE: dict[str, int] = {name: lon for name, lon, _, _, _ in SOLAR_TERMS}

#: 十二节 → 月支序号（0=子, 1=丑, 2=寅 ...）。寅月自立春起。
JIE_TO_MONTH_BRANCH: dict[str, int] = {
    "立春": 2,
    "惊蛰": 3,
    "清明": 4,
    "立夏": 5,
    "芒种": 6,
    "小暑": 7,
    "立秋": 8,
    "白露": 9,
    "寒露": 10,
    "立冬": 11,
    "大雪": 0,
    "小寒": 1,
}


@dataclass(frozen=True)
class SolarTerm:
    """一个节气时刻。``jd_ut`` 为 UT 儒略日，``utc``/``local`` 为双份时刻。"""

    name: str
    longitude: int
    kind: TermKind
    jd_ut: float
    utc: datetime
    local: datetime

    @property
    def local_date(self) -> "datetime.date":  # noqa: F821 - 仅作类型标注
        return self.local.date()


def _term_time(name: str, longitude: int, year: int, tz: ZoneInfo) -> SolarTerm:
    month, day = next((m, d) for n, _, _, m, d in SOLAR_TERMS if n == name)
    guess = datetime(year, month, day, 12, tzinfo=timezone.utc)
    jd_ut = solve_solar_longitude(longitude, julian_day_from_datetime(guess))
    utc = datetime_from_julian_day(jd_ut)
    kind: TermKind = next(k for n, _, k, _, _ in SOLAR_TERMS if n == name)
    return SolarTerm(
        name=name,
        longitude=longitude,
        kind=kind,
        jd_ut=jd_ut,
        utc=utc,
        local=utc.astimezone(tz),
    )


@lru_cache(maxsize=512)
def terms_of_year(year: int, tz_name: str = "Asia/Shanghai") -> tuple[SolarTerm, ...]:
    """返回 ``year`` 公历年内（本地时区）的全部 24 个节气，按时刻升序。

    结果按 (year, tz) 缓存；纯函数语义，缓存不影响可复现性。
    """
    tz = ZoneInfo(tz_name)
    terms: list[SolarTerm] = []
    for name, lon, _, _, _ in SOLAR_TERMS:
        # 小寒/大寒落在 1 月，其余按公历年内锚点求解，跨年由锚点自然处理
        for candidate_year in (year, year - 1, year + 1):
            term = _term_time(name, lon, candidate_year, tz)
            if term.local.year == year:
                terms.append(term)
                break
    terms.sort(key=lambda t: t.jd_ut)
    if len(terms) != 24:  # pragma: no cover - 结构性断言
        raise AssertionError(f"{year} 年节气数量异常: {len(terms)}")
    return tuple(terms)


def terms_between(start: datetime, end: datetime, tz_name: str = "Asia/Shanghai") -> list[SolarTerm]:
    """返回 [start, end) 区间内的节气（按时刻升序）。"""
    if start.tzinfo is None or end.tzinfo is None:
        raise ValueError("terms_between 需要带时区的时间")
    if end <= start:
        raise ValueError("end 必须晚于 start")
    out: list[SolarTerm] = []
    for year in range(start.year - 1, end.year + 2):
        for term in terms_of_year(year, tz_name):
            if start <= term.local < end:
                out.append(term)
    out.sort(key=lambda t: t.jd_ut)
    return out


def jie_before(dt: datetime, tz_name: str = "Asia/Shanghai") -> SolarTerm:
    """返回不晚于 ``dt`` 的最近一个"节"（月柱换月的依据）。

    只查询本年与上一年（12 月大雪到次年小寒之间最多跨一年），避免全量排序。
    """
    for year in (dt.year, dt.year - 1):
        candidates = [t for t in terms_of_year(year, tz_name) if t.kind == "jie" and t.local <= dt]
        if candidates:
            return max(candidates, key=lambda t: t.jd_ut)
    raise AssertionError("无法定位月建节气")  # pragma: no cover


def month_branch_index(dt: datetime, tz_name: str = "Asia/Shanghai") -> int:
    """``dt`` 所处月建的月支序号（0=子 … 2=寅）。以"节"为界。"""
    return JIE_TO_MONTH_BRANCH[jie_before(dt, tz_name).name]


def zhongqi_of_year(year: int, tz_name: str = "Asia/Shanghai") -> tuple[SolarTerm, ...]:
    """返回某公历年内的 12 个中气（用于农历置闰）。"""
    return tuple(t for t in terms_of_year(year, tz_name) if t.kind == "qi")


def mean_solar_term_day(year: int, longitude: int) -> float:  # pragma: no cover - 辅助
    """粗略估计某黄经对应的年内日序，仅用于调试。"""
    base = {0: 79, 15: 95, 30: 110, 45: 126, 60: 141, 75: 157, 90: 172, 105: 188}.get(
        longitude, 172
    )
    return base + (year - 2020) * 0.2422


def term_datetime(name: str, year: int, tz_name: str = "Asia/Shanghai") -> datetime:
    """按名称取某年的节气时刻（本地时区）。"""
    for term in terms_of_year(year, tz_name):
        if term.name == name:
            return term.local
    raise KeyError(f"{year} 年无节气 {name}")


def _angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def solar_longitude_at(dt: datetime) -> float:  # 便利函数，避免上层直接依赖 ephemeris
    """返回 ``dt``（任意时区）时刻的太阳视黄经。"""
    from .ephemeris import apparent_solar_longitude, jd_tt_from_jd_ut

    return apparent_solar_longitude(jd_tt_from_jd_ut(julian_day_from_datetime(dt)))


def next_term_after(dt: datetime, tz_name: str = "Asia/Shanghai") -> SolarTerm:
    """返回严格晚于 ``dt`` 的第一个节气。"""
    for year in (dt.year, dt.year + 1):
        for term in terms_of_year(year, tz_name):
            if term.local > dt:
                return term
    raise AssertionError("unreachable")


def _sanity() -> None:  # pragma: no cover - 供人工核查
    t = term_datetime("立春", 2026)
    assert abs(t.hour - 4) <= 1, t
    assert math.isfinite(julian_day_from_datetime(datetime.now(timezone.utc)))


_ = timedelta  # 保留导入以便未来扩展（避免未使用告警）
