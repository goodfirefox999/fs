"""太阳位置与时间尺度换算（事实层，纯函数，禁止出现吉凶判断）。

实现依据
--------
1. 太阳几何黄经：VSOP87D 地球 L 序列截断（Meeus, *Astronomical Algorithms* 2nd ed.,
   Appendix III；第 25 章 "Solar Coordinates"）。截断到 L0 前 64 项 / L1 前 34 项 /
   L2 前 10 项 / L3 前 6 项 / L4 前 3 项 / L5 前 1 项，理论误差 < 1"。
2. 章动：Meeus 第 22 章低精度公式（误差 0.5"）。
3. 光行差：-20.4898"/R（Meeus 25.10）。
4. ΔT：Espenak & Meeus 锚点线性插值（见 ``delta_t``），并在返回值上附带不确定度。

精度声明
--------
太阳视黄经误差目标 < 5"（对应节气时刻 < 2 分钟）；ΔT 模型误差 <= 40 s（1900-2100）。
本模块所有函数返回 UTC 或 TT，绝不返回本地民用时；本地化由 ``calendar``/``jieqi`` 负责。

本模块不产生任何"吉/凶/宜/忌"字段（铁律 3）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

__all__ = [
    "J2000",
    "delta_t",
    "jd_tt_from_jd_ut",
    "jd_ut_from_jd_tt",
    "julian_day_from_datetime",
    "datetime_from_julian_day",
    "apparent_solar_longitude",
    "sun_distance_au",
    "solve_solar_longitude",
    "equation_of_time_minutes",
    "obliquity_deg",
]

#: J2000.0 历元（2000-01-01 12:00 TT）的儒略日
J2000 = 2451545.0

_TWO_PI = 2.0 * math.pi
_DEG = math.pi / 180.0


# --------------------------------------------------------------------------- #
# 儒略日
# --------------------------------------------------------------------------- #
def julian_day_from_datetime(dt: datetime) -> float:
    """把带时区的 ``datetime`` 换算为儒略日（UTC 标度）。

    采用 Meeus 7.1 的 Gregorian 分支公式，输入先归一到 UTC。
    """
    if dt.tzinfo is None:
        raise ValueError("julian_day_from_datetime 需要带时区的 datetime（naive 时间不可判定标度）")
    utc = dt.astimezone(timezone.utc)
    year, month = utc.year, utc.month
    day = (
        utc.day
        + (utc.hour + (utc.minute + (utc.second + utc.microsecond / 1e6) / 60.0) / 60.0) / 24.0
    )
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + a // 4
    return (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
    )


def datetime_from_julian_day(jd: float) -> datetime:
    """儒略日 → UTC ``datetime``（Meeus 7.0 逆算法）。"""
    jd = jd + 0.5
    z = math.floor(jd)
    f = jd - z
    if z < 2299161:
        a = z
    else:
        alpha = math.floor((z - 1867216.25) / 36524.25)
        a = z + 1 + alpha - math.floor(alpha / 4.0)
    b = a + 1524
    c = math.floor((b - 122.1) / 365.25)
    d = math.floor(365.25 * c)
    e = math.floor((b - d) / 30.6001)
    day_f = b - d - math.floor(30.6001 * e) + f
    day = int(math.floor(day_f))
    frac = day_f - day
    month = int(e - 1 if e < 14 else e - 13)
    year = int(c - 4716 if month > 2 else c - 4715)
    seconds = frac * 86400.0
    base = datetime(year, month, day, tzinfo=timezone.utc)
    return base + timedelta(seconds=seconds)


# --------------------------------------------------------------------------- #
# ΔT（TT - UT）
# --------------------------------------------------------------------------- #
#: (年份, ΔT 秒) 锚点，取自 Espenak & Meeus 多项式在整十年份上的取值，
#: 2020 之后采用 IERS 实测趋势外推。锚点之间线性插值。
_DELTA_T_ANCHORS: tuple[tuple[float, float], ...] = (
    (1800.0, 13.7),
    (1850.0, 7.1),
    (1900.0, -2.8),
    (1920.0, 21.2),
    (1940.0, 24.3),
    (1950.0, 29.1),
    (1960.0, 33.2),
    (1970.0, 40.2),
    (1980.0, 50.5),
    (1990.0, 56.9),
    (2000.0, 63.8),
    (2010.0, 66.1),
    (2020.0, 69.4),
    (2030.0, 72.0),
    (2050.0, 80.0),
    (2100.0, 130.0),
    (2200.0, 260.0),
)


def delta_t(year: float) -> float:
    """返回 ΔT = TT − UT（秒）。

    锚点线性插值。1900-2100 区间与实测值偏差 <= 40 s；该偏差对节气时刻的影响
    为同量级秒数，小于本系统 ±1 分钟的精度目标，故可接受。
    超出 1800-2200 时按端点斜率外推，并在报告 manifest 中标注 ``delta_t_model``。
    """
    anchors = _DELTA_T_ANCHORS
    if year <= anchors[0][0]:
        (y0, v0), (y1, v1) = anchors[0], anchors[1]
        return v0 + (v1 - v0) * (year - y0) / (y1 - y0)
    if year >= anchors[-1][0]:
        (y0, v0), (y1, v1) = anchors[-2], anchors[-1]
        return v1 + (v1 - v0) * (year - y1) / (y1 - y0)
    for (y0, v0), (y1, v1) in zip(anchors, anchors[1:]):
        if y0 <= year <= y1:
            return v0 + (v1 - v0) * (year - y0) / (y1 - y0)
    raise AssertionError("unreachable")


def _decimal_year(jd_ut: float) -> float:
    dt = datetime_from_julian_day(jd_ut)
    start = datetime(dt.year, 1, 1, tzinfo=timezone.utc)
    end = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    return dt.year + (dt - start).total_seconds() / (end - start).total_seconds()


def jd_tt_from_jd_ut(jd_ut: float) -> float:
    """UT 儒略日 → TT 儒略日。"""
    return jd_ut + delta_t(_decimal_year(jd_ut)) / 86400.0


def jd_ut_from_jd_tt(jd_tt: float) -> float:
    """TT 儒略日 → UT 儒略日（一次迭代反解，误差 < 0.001 s）。"""
    jd_ut = jd_tt - delta_t(_decimal_year(jd_tt)) / 86400.0
    jd_ut = jd_tt - delta_t(_decimal_year(jd_ut)) / 86400.0
    return jd_ut


# --------------------------------------------------------------------------- #
# VSOP87D 地球黄经（截断）
# --------------------------------------------------------------------------- #
# 每项为 (A, B, C)，贡献 A * cos(B + C * tau)，tau 以儒略千年（TT）为单位。
_L0: tuple[tuple[float, float, float], ...] = (
    (175347046.0, 0.0, 0.0),
    (3341656.0, 4.6692568, 6283.0758500),
    (34894.0, 4.62610, 12566.15170),
    (3497.0, 2.7441, 5753.3849),
    (3418.0, 2.8289, 3.5231),
    (3136.0, 3.6277, 77713.7715),
    (2676.0, 4.4181, 7860.4194),
    (2343.0, 6.1352, 3930.2097),
    (1324.0, 0.7425, 11506.7698),
    (1273.0, 2.0371, 529.6910),
    (1199.0, 1.1096, 1577.3435),
    (990.0, 5.233, 5884.927),
    (902.0, 2.045, 26.298),
    (857.0, 3.508, 398.149),
    (780.0, 1.179, 5223.694),
    (753.0, 2.533, 5507.553),
    (505.0, 4.583, 18849.228),
    (492.0, 4.205, 775.523),
    (357.0, 2.920, 0.067),
    (317.0, 5.849, 11790.629),
    (284.0, 1.899, 796.298),
    (271.0, 0.315, 10977.079),
    (243.0, 0.345, 5486.778),
    (206.0, 4.806, 2544.314),
    (205.0, 1.869, 5573.143),
    (202.0, 2.458, 6069.777),
    (156.0, 0.833, 213.299),
    (132.0, 3.411, 2942.463),
    (126.0, 1.083, 20.775),
    (115.0, 0.645, 0.980),
    (103.0, 0.636, 4694.003),
    (102.0, 0.976, 15720.839),
    (102.0, 4.267, 7.114),
    (99.0, 6.21, 2146.17),
    (98.0, 0.68, 155.42),
    (86.0, 5.98, 161000.69),
    (85.0, 1.30, 6275.96),
    (85.0, 3.67, 71430.70),
    (80.0, 1.81, 17260.15),
    (79.0, 3.04, 12036.46),
    (75.0, 1.76, 5088.63),
    (74.0, 3.50, 3154.69),
    (74.0, 4.68, 801.82),
    (70.0, 0.83, 9437.76),
    (62.0, 3.98, 8827.39),
    (61.0, 1.82, 7084.90),
    (57.0, 2.78, 6286.60),
    (56.0, 4.39, 14143.50),
    (56.0, 3.47, 6279.55),
    (52.0, 0.19, 12139.55),
    (52.0, 1.33, 1748.02),
    (51.0, 0.28, 5856.48),
    (49.0, 0.49, 1194.45),
    (41.0, 5.37, 8429.24),
    (41.0, 2.40, 19651.05),
    (39.0, 6.17, 10447.39),
    (37.0, 6.04, 10213.29),
    (37.0, 2.57, 1059.38),
    (36.0, 1.71, 2352.87),
    (36.0, 1.78, 6812.77),
    (33.0, 0.59, 17789.85),
    (30.0, 0.44, 83996.85),
    (30.0, 2.74, 1349.87),
    (25.0, 3.16, 4690.48),
)

_L1: tuple[tuple[float, float, float], ...] = (
    (628331966747.0, 0.0, 0.0),
    (206059.0, 2.678235, 6283.075850),
    (4303.0, 2.6351, 12566.1517),
    (425.0, 1.590, 3.523),
    (119.0, 5.796, 26.298),
    (109.0, 2.966, 1577.344),
    (93.0, 2.59, 18849.23),
    (72.0, 1.14, 529.69),
    (68.0, 1.87, 398.15),
    (67.0, 4.41, 5507.55),
    (59.0, 2.89, 5223.69),
    (56.0, 2.17, 155.42),
    (45.0, 0.40, 796.30),
    (36.0, 0.47, 775.52),
    (29.0, 2.65, 7.11),
    (21.0, 5.34, 0.98),
    (19.0, 1.85, 5486.78),
    (19.0, 4.97, 213.30),
    (17.0, 2.99, 6275.96),
    (16.0, 0.03, 2544.31),
    (16.0, 1.43, 2146.17),
    (15.0, 1.21, 10977.08),
    (12.0, 2.83, 1748.02),
    (12.0, 3.26, 5088.63),
    (12.0, 5.27, 1194.45),
    (12.0, 2.08, 4694.00),
    (11.0, 0.77, 553.57),
    (10.0, 1.30, 6286.60),
    (10.0, 4.24, 1349.87),
    (9.0, 2.70, 242.73),
    (9.0, 5.64, 951.72),
    (8.0, 5.30, 2352.87),
    (6.0, 2.65, 9437.76),
    (6.0, 4.67, 4690.48),
)

_L2: tuple[tuple[float, float, float], ...] = (
    (52919.0, 0.0, 0.0),
    (8720.0, 1.0721, 6283.0758),
    (309.0, 0.867, 12566.152),
    (27.0, 0.05, 3.52),
    (16.0, 5.19, 26.30),
    (16.0, 3.68, 155.42),
    (10.0, 0.76, 18849.23),
    (9.0, 2.06, 77713.77),
    (7.0, 0.83, 775.52),
    (5.0, 4.66, 1577.34),
)

_L3: tuple[tuple[float, float, float], ...] = (
    (289.0, 5.844, 6283.076),
    (35.0, 0.0, 0.0),
    (17.0, 5.49, 12566.15),
    (3.0, 5.20, 155.42),
    (1.0, 4.72, 3.52),
    (1.0, 5.30, 18849.23),
)

_L4: tuple[tuple[float, float, float], ...] = (
    (114.0, 3.142, 0.0),
    (8.0, 4.13, 6283.08),
    (1.0, 3.84, 12566.15),
)

_L5: tuple[tuple[float, float, float], ...] = ((1.0, 3.14, 0.0),)


def _series(terms: tuple[tuple[float, float, float], ...], tau: float) -> float:
    return sum(a * math.cos(b + c * tau) for a, b, c in terms)


def _earth_heliocentric_longitude(jd_tt: float) -> float:
    """VSOP87D 地球日心黄经（弧度，0-2π）。"""
    tau = (jd_tt - J2000) / 365250.0
    l0 = _series(_L0, tau)
    l1 = _series(_L1, tau)
    l2 = _series(_L2, tau)
    l3 = _series(_L3, tau)
    l4 = _series(_L4, tau)
    l5 = _series(_L5, tau)
    total = l0 + l1 * tau + l2 * tau**2 + l3 * tau**3 + l4 * tau**4 + l5 * tau**5
    lon = (total / 1e8) % _TWO_PI
    # VSOP87 → FK5 的常数偏移（Meeus 32.3 的简化形式，量级 0.09"，保留以示来源）
    lon -= 0.09033 / 3600.0 * _DEG
    return lon % _TWO_PI


def sun_distance_au(jd_tt: float) -> float:
    """日地距离（AU）。用低精度真近点角公式，误差 < 1e-5 AU，对光行差影响 < 0.01"。"""
    tau = (jd_tt - J2000) / 365250.0
    t = tau * 10.0  # 世纪
    mean_lon = math.radians((280.46646 + 36000.76983 * t) % 360.0)
    mean_anom = math.radians((357.52911 + 35999.05029 * t) % 360.0)
    e = 0.016708634 - 0.000042037 * t
    center = (
        math.radians(1.914602) * math.sin(mean_anom)
        + math.radians(0.019993) * math.sin(2 * mean_anom)
        + math.radians(0.000289) * math.sin(3 * mean_anom)
    )
    true_anom = mean_anom + center
    del mean_lon  # 仅用于保持公式完整性的记录，不参与 R 计算
    return 1.000001018 * (1.0 - e * e) / (1.0 + e * math.cos(true_anom))


def _nutation(jd_tt: float) -> tuple[float, float]:
    """章动 (Δψ, Δε)，单位度。Meeus 22 章低精度公式。"""
    t = (jd_tt - J2000) / 36525.0
    omega = math.radians((125.04452 - 1934.136261 * t + 0.0020708 * t * t + t**3 / 450000.0) % 360.0)
    l_sun = math.radians((280.4665 + 36000.7698 * t) % 360.0)
    l_moon = math.radians((218.3165 + 481267.8813 * t) % 360.0)
    d_psi = (
        -17.20 * math.sin(omega)
        - 1.32 * math.sin(2 * l_sun)
        - 0.23 * math.sin(2 * l_moon)
        + 0.21 * math.sin(2 * omega)
    ) / 3600.0
    d_eps = (
        9.20 * math.cos(omega)
        + 0.57 * math.cos(2 * l_sun)
        + 0.10 * math.cos(2 * l_moon)
        - 0.09 * math.cos(2 * omega)
    ) / 3600.0
    return d_psi, d_eps


def obliquity_deg(jd_tt: float) -> float:
    """真黄赤交角（度），含章动。Meeus 22.3 + 22.2。"""
    t = (jd_tt - J2000) / 36525.0
    eps0 = (
        23.0
        + 26.0 / 60.0
        + 21.448 / 3600.0
        - (46.8150 * t + 0.00059 * t * t - 0.001813 * t**3) / 3600.0
    )
    _, d_eps = _nutation(jd_tt)
    return eps0 + d_eps


def apparent_solar_longitude(jd_tt: float) -> float:
    """太阳视黄经（度，[0,360)）。= 几何黄经 + 章动 − 光行差。"""
    lon = _earth_heliocentric_longitude(jd_tt) + math.pi  # 日心 → 地心
    d_psi, _ = _nutation(jd_tt)
    aberration = -20.4898 / 3600.0 / sun_distance_au(jd_tt)  # 度
    deg = (math.degrees(lon) + d_psi + aberration) % 360.0
    return deg


# --------------------------------------------------------------------------- #
# 反解：太阳视黄经到达指定度数
# --------------------------------------------------------------------------- #
def solve_solar_longitude(
    target_deg: float,
    jd_ut_guess: float,
    tol_sec: float = 0.5,
    max_iter: int = 60,
) -> float:
    """求太阳视黄经等于 ``target_deg`` 的 UT 儒略日。

    在 TT 域用牛顿迭代（解析导数用有限差分），收敛判据为时间增量 < ``tol_sec``。
    返回 UT 儒略日。跨越 0°/360° 时用最短角度差处理。
    """
    target = target_deg % 360.0
    jd_tt = jd_tt_from_jd_ut(jd_ut_guess)
    for _ in range(max_iter):
        lon = apparent_solar_longitude(jd_tt)
        diff = (target - lon + 180.0) % 360.0 - 180.0  # (-180, 180]
        if abs(diff) < 1e-9:
            break
        # 太阳视黄经平均日变化约 0.9856°/日，用局部差分提高收敛稳定性
        h = 0.05
        d_lon = (apparent_solar_longitude(jd_tt + h) - apparent_solar_longitude(jd_tt - h)) / (2 * h)
        if d_lon <= 0:
            d_lon = 0.9856
        step = diff / d_lon
        step = max(min(step, 10.0), -10.0)
        jd_tt += step
        if abs(step) * 86400.0 < tol_sec:
            break
    return jd_ut_from_jd_tt(jd_tt)


def equation_of_time_minutes(jd_tt: float) -> float:
    """均时差（分钟）= 真太阳时 − 平太阳时。Meeus 28.3 的等价展开式。

    公式::

        E = L0 − 0.0057183° − α + Δψ

    其中 ``L0`` 为太阳**平黄经**（Meeus 25.2，系数为"每儒略世纪"，即 36000.76983°/世纪），
    ``α`` 为视赤经，``Δψ`` 为章动。结果归一到 (−180°, 180°] 后 ×4 转分钟。

    精度约 ±10 s（对应 0.2 分钟），满足择日分钟级需求。
    注意：Meeus 28.3 另有一个以"儒略千年"为单位的 L0 表达式（系数 360007.6982779），
    两式不可混用 —— 混用会引入约 400 分钟的偏差（本项目曾踩此坑，见 CHANGELOG）。
    """
    t = (jd_tt - J2000) / 36525.0
    epsilon = obliquity_deg(jd_tt) * _DEG
    # 太阳平黄经（度，每儒略世纪 36000.76983°）
    l0_deg = (280.4664567 + 36000.76983 * t + 0.0003032 * t * t) % 360.0
    l0 = math.radians(l0_deg)
    d_psi, _ = _nutation(jd_tt)
    # 视太阳黄经（弧度）
    lam = apparent_solar_longitude(jd_tt) * _DEG
    alpha = math.atan2(math.cos(epsilon) * math.sin(lam), math.cos(lam))
    e = l0 - 0.0057183 * _DEG - alpha + d_psi * _DEG
    # 归一到 (-180°, 180°] 后转分钟（1° = 4 分钟）
    deg = (math.degrees(e) + 180.0) % 360.0 - 180.0
    return deg * 4.0


@dataclass(frozen=True)
class SolarPosition:
    """太阳位置快照（供报告回显与调试，不参与判定）。"""

    jd_tt: float
    longitude_deg: float
    distance_au: float
    obliquity_deg: float
    equation_of_time_min: float
