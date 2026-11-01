"""真太阳时（事实层）。

真太阳时 = 标准时（民用时） + 经度时差 + 均时差
- 经度时差 = (站点经度 − 时区中央经线) × 4 分钟/度
- 均时差见 ``ephemeris.equation_of_time_minutes``

返回值的 ``tzinfo`` 仅保留原始时区标识，数值语义为"真太阳时钟面读数"。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .ephemeris import equation_of_time_minutes, jd_tt_from_jd_ut, julian_day_from_datetime

__all__ = ["longitude_correction_minutes", "equation_of_time", "true_solar_time", "standard_meridian"]


def standard_meridian(tz: ZoneInfo | timezone, at: datetime) -> float:
    """返回 ``at`` 时刻该时区的中央经线（度）。"""
    offset = at.utcoffset()
    if offset is None:
        raise ValueError("需要带时区的时间")
    return offset.total_seconds() / 3600.0 * 15.0


def longitude_correction_minutes(lon: float, tz: ZoneInfo | timezone, at: datetime) -> float:
    """经度时差（分钟）。东经为正。"""
    return (lon - standard_meridian(tz, at)) * 4.0


def equation_of_time(at: datetime) -> float:
    """均时差（分钟）。"""
    jd_tt = jd_tt_from_jd_ut(julian_day_from_datetime(at))
    return equation_of_time_minutes(jd_tt)


def true_solar_time(at: datetime, lon: float) -> datetime:
    """把民用时 ``at`` 换算为同一时区标识下的真太阳时读数。"""
    if at.tzinfo is None:
        raise ValueError("true_solar_time 需要带时区的时间")
    delta = longitude_correction_minutes(lon, at.tzinfo, at) + equation_of_time(at)
    return at + timedelta(minutes=delta)
