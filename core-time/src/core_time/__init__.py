"""core-time：择日引擎事实层。

只提供历法与天文事实，**禁止**出现吉凶宜忌字段（架构铁律 3）。
所有争议口径见 ``CalendarConfig``，并在报告中回显。
"""

from __future__ import annotations

from .calendar import (
    GAN,
    GANZHI60,
    ZHI,
    FourPillars,
    Pillar,
    compute_four_pillars,
    day_pillar_index,
    ganzhi_index,
    ganzhi_name,
    jdn_of_date,
)
from .config import CalendarConfig
from .ephemeris import (
    apparent_solar_longitude,
    datetime_from_julian_day,
    delta_t,
    equation_of_time_minutes,
    jd_tt_from_jd_ut,
    jd_ut_from_jd_tt,
    julian_day_from_datetime,
    solve_solar_longitude,
)
from .jieqi import (
    SOLAR_TERMS,
    SolarTerm,
    jie_before,
    month_branch_index,
    next_term_after,
    solar_longitude_at,
    term_datetime,
    terms_between,
    terms_of_year,
    zhongqi_of_year,
)
from .lunar import (
    LUNAR_DAY_NAMES,
    LUNAR_MONTH_NAMES,
    LunarDate,
    LunarMonth,
    chinese_new_year,
    leap_month_of,
    lunar_date_of,
    lunar_months_of_year,
    lunar_to_solar,
)
from .solar_time import equation_of_time, longitude_correction_minutes, true_solar_time

__all__ = [
    "GAN",
    "ZHI",
    "GANZHI60",
    "Pillar",
    "FourPillars",
    "compute_four_pillars",
    "ganzhi_index",
    "ganzhi_name",
    "jdn_of_date",
    "day_pillar_index",
    "CalendarConfig",
    "delta_t",
    "julian_day_from_datetime",
    "datetime_from_julian_day",
    "apparent_solar_longitude",
    "solve_solar_longitude",
    "equation_of_time_minutes",
    "jd_tt_from_jd_ut",
    "jd_ut_from_jd_tt",
    "SOLAR_TERMS",
    "SolarTerm",
    "terms_of_year",
    "terms_between",
    "jie_before",
    "month_branch_index",
    "next_term_after",
    "term_datetime",
    "zhongqi_of_year",
    "solar_longitude_at",
    "LunarDate",
    "LunarMonth",
    "lunar_date_of",
    "lunar_months_of_year",
    "lunar_to_solar",
    "chinese_new_year",
    "leap_month_of",
    "LUNAR_MONTH_NAMES",
    "LUNAR_DAY_NAMES",
    "true_solar_time",
    "equation_of_time",
    "longitude_correction_minutes",
]

__version__ = "0.1.0"
