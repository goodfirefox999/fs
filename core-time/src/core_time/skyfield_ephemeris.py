"""Skyfield/DE440s 高精度太阳位置后端（可选依赖）。

只在 ``core-time`` 内部使用；没有 skyfield 或星历文件时由
``ephemeris.resolved_backend()`` 回退到 VSOP87。

星历文件默认读 ``~/.cache/zeri/skyfield/de440s.bsp``，可用
``ZERI_EPHEMERIS_PATH`` 覆盖。**本模块不会自动下载**，避免离线环境
在生产路径上隐式联网。
"""

from __future__ import annotations

import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path

__all__ = [
    "ephemeris_path",
    "available",
    "solar_longitude_deg",
    "solve_term_time",
]

DEFAULT_EPHEMERIS_PATH = "~/.cache/zeri/skyfield/de440s.bsp"


def ephemeris_path() -> Path:
    return Path(os.environ.get("ZERI_EPHEMERIS_PATH", DEFAULT_EPHEMERIS_PATH)).expanduser()


# C19-exempt: 零参数缓存（键恒为 ()），只缓存星历句柄，无复合参数串味面
@lru_cache(maxsize=1)
def _context():
    try:
        from skyfield.api import Loader, load
    except ImportError:
        return None
    path = ephemeris_path()
    if not path.is_file():
        return None
    loader = Loader(str(path.parent), verbose=False)
    eph = loader(path.name)
    return load.timescale(), eph["earth"], eph["sun"]


def available() -> bool:
    """skyfield 可导入且星历文件存在时为 True（不做网络下载）。"""
    return _context() is not None


def _require():
    ctx = _context()
    if ctx is None:
        raise RuntimeError(
            "Skyfield 后端不可用：需要安装 skyfield，并把 de440s.bsp 放到 "
            f"{ephemeris_path()}（或设置 ZERI_EPHEMERIS_PATH）"
        )
    return ctx


def solar_longitude_deg(jd_tt: float) -> float:
    """太阳视黄经（度，历元 of date），DE440s。"""
    ts, earth, sun = _require()
    t = ts.tt_jd(jd_tt)
    _, lon, _ = earth.at(t).observe(sun).apparent().ecliptic_latlon(epoch="date")
    return float(lon.degrees) % 360.0


def solve_term_time(
    target_deg: float,
    jd_tt_guess: float,
    tol_sec: float = 0.01,
    max_iter: int = 60,
) -> tuple[float, float, datetime, float]:
    """求太阳视黄经等于 ``target_deg`` 的时刻。

    返回 ``(jd_utc, jd_tt, utc_datetime, delta_t_s)``。``jd_utc`` 为 UTC
    儒略日，与 ``ephemeris.datetime_from_julian_day`` 的语义一致。
    """
    ts, _, _ = _require()
    target = target_deg % 360.0
    jd_tt = jd_tt_guess
    for _ in range(max_iter):
        lon = solar_longitude_deg(jd_tt)
        diff = (target - lon + 180.0) % 360.0 - 180.0
        if abs(diff) < 1e-9:
            break
        h = 0.05
        # 差分跨 0°/360° 解缠，否则春分附近会得到约 -3600°/日 的假导数。
        delta = (
            solar_longitude_deg(jd_tt + h) - solar_longitude_deg(jd_tt - h) + 180.0
        ) % 360.0 - 180.0
        d_lon = delta / (2 * h)
        if d_lon <= 0:
            d_lon = 0.9856
        step = max(min(diff / d_lon, 10.0), -10.0)
        jd_tt += step
        if abs(step) * 86400.0 < tol_sec:
            break
    t = ts.tt_jd(jd_tt)
    utc_dt = t.utc_datetime()
    from .ephemeris import julian_day_from_datetime

    return julian_day_from_datetime(utc_dt), float(t.tt), utc_dt, float(t.delta_t)
