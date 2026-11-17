"""core-time 星历底层分支：儒略日边界、VSOP87 分支、求解器与 skyfield 回退。

这些分支不参与吉凶判断，但决定 manifest 能否诚实标注 ``degraded``，
所以每条回退路径都必须有测试盯着（Layer 5）。
"""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime

import pytest
from core_time import ephemeris as ephemeris_mod
from core_time import skyfield_ephemeris
from core_time.ephemeris import (
    apparent_solar_longitude,
    datetime_from_julian_day,
    julian_day_from_datetime,
    solar_longitude_deg,
    solve_solar_longitude,
)


class TestJulianDayBoundary:
    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValueError, match="带时区"):
            julian_day_from_datetime(datetime(2026, 1, 1))

    def test_julian_calendar_branch(self) -> None:
        # 2299159.5 = 1582-10-04（儒略历），z=2299160 < 2299161 触发儒略分支
        assert datetime_from_julian_day(2299159.5).date() == date(1582, 10, 4)

    def test_gregorian_round_trip(self) -> None:
        moment = datetime(2026, 7, 11, 6, 0, tzinfo=UTC)
        assert datetime_from_julian_day(julian_day_from_datetime(moment)) == moment


class TestSolarLongitudeBackendBranch:
    def test_vsop87_fallback_matches_apparent(self, monkeypatch) -> None:
        monkeypatch.setattr(ephemeris_mod, "resolved_backend", lambda: "vsop87")
        jd = 2461234.5
        assert solar_longitude_deg(jd) == apparent_solar_longitude(jd)


class _FakeTimescale:
    tt = 2461234.5
    delta_t = 69.0

    def tt_jd(self, jd_tt: float) -> _FakeTimescale:
        self.tt = jd_tt
        return self

    def utc_datetime(self) -> datetime:
        return datetime(2026, 7, 11, tzinfo=UTC)


class TestSolveSolarLongitude:
    def test_explicit_lon_func_zero_derivative_and_exhausted_iter(self) -> None:
        # 常数黄经 → 有限差导数为 0 → 走 0.9856°/日 兜底；max_iter=1 触发出循环
        jd = solve_solar_longitude(315.0, 2461234.5, max_iter=1, lon_func=lambda jd_tt: 0.0)
        assert isinstance(jd, float)

    def test_default_vsop87_solver_converges(self, monkeypatch) -> None:
        monkeypatch.setattr(ephemeris_mod, "resolved_backend", lambda: "vsop87")
        jd = solve_solar_longitude(315.0, 2461234.5, tol_sec=1.0)
        assert abs(solar_longitude_deg(jd) - 315.0) < 0.01

    def test_max_iter_zero_returns_guess_without_loop(self) -> None:
        jd = solve_solar_longitude(315.0, 2461234.5, max_iter=0)
        assert isinstance(jd, float)


class TestSkyfieldHelpers:
    def test_context_returns_none_without_skyfield(self, monkeypatch) -> None:
        # 全套测试里 skyfield.api 可能已被导入，必须连子模块一起挡住，
        # 否则 `from skyfield.api import ...` 会命中缓存而不触发 ImportError。
        monkeypatch.setitem(sys.modules, "skyfield", None)
        monkeypatch.setitem(sys.modules, "skyfield.api", None)
        assert skyfield_ephemeris._context.__wrapped__() is None

    def test_context_returns_none_when_file_missing(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(skyfield_ephemeris, "ephemeris_path", lambda: tmp_path / "missing.bsp")
        assert skyfield_ephemeris._context.__wrapped__() is None

    def test_require_raises_when_context_unavailable(self, monkeypatch) -> None:
        monkeypatch.setattr(skyfield_ephemeris, "_context", lambda: None)
        with pytest.raises(RuntimeError, match="Skyfield 后端不可用"):
            skyfield_ephemeris._require()

    def test_solve_term_time_zero_derivative_fallback(self, monkeypatch) -> None:
        monkeypatch.setattr(skyfield_ephemeris, "_require", lambda: (_FakeTimescale(), None, None))
        monkeypatch.setattr(skyfield_ephemeris, "solar_longitude_deg", lambda jd_tt: 0.0)
        jd_utc, jd_tt, utc_dt, delta_t = skyfield_ephemeris.solve_term_time(315.0, 2461234.5, max_iter=1)
        assert isinstance(jd_utc, float)
        assert isinstance(jd_tt, float)
        assert utc_dt.date() == date(2026, 7, 11)
        assert delta_t == pytest.approx(69.0)
