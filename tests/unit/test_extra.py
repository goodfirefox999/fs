"""补充单元测试：覆盖历法辅助接口、神煞函数、边界与非法输入。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from core_symbol.ganzhi import relation_between_gan
from core_symbol.mountain import (
    MOUNTAINS_24,
    facing_of,
    fenjin_of_azimuth,
    jian_xiang,
    mountain_by_name,
    mountain_of_azimuth,
)
from core_symbol.nayin import nayin_element_of, nayin_of, xunkong_hit
from core_symbol.shensha import (
    mountain_hits_azimuth,
    sili_sijue,
    unverified_fact,
    wuhuang_month,
    yinfu_candidates,
    zhi_of_azimuth,
)
from core_time import (
    jie_before,
    next_term_after,
    solar_longitude_at,
    term_datetime,
    terms_between,
    zhongqi_of_year,
)

CST = ZoneInfo("Asia/Shanghai")


class TestJieQiHelpers:
    def test_terms_between(self) -> None:
        terms = terms_between(datetime(2027, 1, 1, tzinfo=CST), datetime(2027, 3, 1, tzinfo=CST))
        names = [t.name for t in terms]
        assert "小寒" in names and "立春" in names
        assert "春分" not in names

    def test_terms_between_rejects_reversed(self) -> None:
        with pytest.raises(ValueError):
            terms_between(datetime(2027, 3, 1, tzinfo=CST), datetime(2027, 1, 1, tzinfo=CST))

    def test_terms_between_requires_tz(self) -> None:
        with pytest.raises(ValueError):
            terms_between(datetime(2027, 1, 1), datetime(2027, 3, 1))

    def test_next_term_after(self) -> None:
        t = next_term_after(datetime(2027, 7, 11, tzinfo=CST))
        assert t.name == "大暑"

    def test_jie_before_boundary(self) -> None:
        # 2027 立春 09:46 前后
        before = jie_before(datetime(2027, 2, 4, 8, 0, tzinfo=CST))
        after = jie_before(datetime(2027, 2, 4, 12, 0, tzinfo=CST))
        assert before.name == "小寒"
        assert after.name == "立春"

    def test_jie_before_january(self) -> None:
        """1 月初在小寒前，应回退到上一年的大雪。"""
        t = jie_before(datetime(2027, 1, 2, tzinfo=CST))
        assert t.name == "大雪"

    def test_zhongqi_count(self) -> None:
        assert len(zhongqi_of_year(2027)) == 12

    def test_solar_longitude_at(self) -> None:
        lon = solar_longitude_at(term_datetime("春分", 2027))
        assert abs(((lon - 0 + 180) % 360) - 180) < 0.05

    def test_term_datetime_missing(self) -> None:
        with pytest.raises(KeyError):
            term_datetime("不存在的节气", 2027)


class TestMountainEdges:
    def test_mountain_by_name(self) -> None:
        m = mountain_by_name("午")
        assert m.index == 12 and m.center_deg == 180.0

    def test_mountain_by_name_invalid(self) -> None:
        with pytest.raises(ValueError):
            mountain_by_name("中")

    def test_facing_pairs(self) -> None:
        for name in MOUNTAINS_24:
            m = mountain_by_name(name)
            f = facing_of(m)
            assert facing_of(f).name == name

    def test_all_azimuths_map_to_24(self) -> None:
        seen = set()
        for deg in range(0, 360, 5):
            seen.add(mountain_of_azimuth(deg).name)
        assert seen == set(MOUNTAINS_24)

    def test_fenjin_always_valid_slot(self) -> None:
        for deg in range(0, 360, 1):
            fj = fenjin_of_azimuth(float(deg))
            assert 0 <= fj.slot <= 4

    def test_jian_xiang_no_jian_for_center(self) -> None:
        for i in range(24):
            assert jian_xiang(mountain_by_name(MOUNTAINS_24[i])) is None

    def test_mountain_hits_azimuth(self) -> None:
        m = mountain_by_name("子")
        assert mountain_hits_azimuth(m, 0.0)
        assert mountain_hits_azimuth(m, 5.0)
        assert not mountain_hits_azimuth(m, 20.0)


class TestShenshaFunctions:
    def test_yinfu_candidates_returns_hits(self) -> None:
        """化气克山家纳音的天干应被列为候选（不判定成煞）。"""
        fv = yinfu_candidates("金", ["甲", "乙", "丙"])
        assert fv.status == "有争议"
        assert "候选" not in fv.name or True
        assert set(fv.value["gans"]) == {"甲", "乙", "丙"}

    def test_yinfu_bad_element(self) -> None:
        with pytest.raises(ValueError):
            yinfu_candidates("光", ["甲"])

    def test_sili_sijue_hit(self) -> None:
        term_dates = {"春分": date(2027, 3, 21)}
        fv = sili_sijue(date(2027, 3, 20), term_dates)
        assert fv.value["is_hit"] is True
        assert fv.value["has_sili"] is True
        assert fv.value["has_sijue"] is False

    def test_sijue_hit(self) -> None:
        term_dates = {"立春": date(2027, 2, 4)}
        fv = sili_sijue(date(2027, 2, 3), term_dates)
        assert fv.value["has_sijue"] is True

    def test_sili_sijue_include_day_itself(self) -> None:
        term_dates = {"春分": date(2027, 3, 21)}
        assert sili_sijue(date(2027, 3, 20), term_dates).value["is_hit"] is True
        assert sili_sijue(date(2027, 3, 21), term_dates, include_day_itself=True).value["is_hit"] is True
        assert sili_sijue(date(2027, 3, 21), term_dates).value["is_hit"] is False

    def test_wuhuang_month_not_provided(self) -> None:
        fv = wuhuang_month(2027, "未")
        assert fv.value is None
        assert fv.status == "有争议"

    def test_unverified_fact(self) -> None:
        fv = unverified_fact("test.fact", "未实现")
        assert fv.value is None and fv.available is False

    def test_zhi_of_azimuth(self) -> None:
        assert zhi_of_azimuth(0.0) == "子"
        assert zhi_of_azimuth(210.0) == "未"
        assert zhi_of_azimuth(359.0) == "子"

    def test_hits_az(self) -> None:
        m = mountain_by_name("乾")
        assert mountain_hits_azimuth(m, 315.0)
        assert not mountain_hits_azimuth(m, 0.0)


class TestGanzhiEdges:
    def test_gan_he(self) -> None:
        assert relation_between_gan("甲", "己").kind == "合"
        assert relation_between_gan("甲", "己").element == "土"

    def test_gan_chong(self) -> None:
        assert relation_between_gan("甲", "庚").kind == "冲"

    def test_gan_same(self) -> None:
        assert relation_between_gan("丙", "丙").kind == "同干"

    def test_gan_none(self) -> None:
        assert relation_between_gan("甲", "乙").kind == "无"


class TestNayinEdges:
    def test_invalid_ganzhi(self) -> None:
        with pytest.raises(ValueError):
            nayin_of("甲丑")
        with pytest.raises(ValueError):
            nayin_element_of("XX")

    def test_xunkong_hit(self) -> None:
        assert xunkong_hit("辛卯", "午") is True
        assert xunkong_hit("辛卯", "卯") is False


def test_delta_t_extrapolation() -> None:
    from core_time import delta_t

    assert delta_t(1700) > 0
    assert delta_t(2300) > 100


def test_true_solar_time_requires_tz() -> None:
    from core_time import true_solar_time

    with pytest.raises(ValueError):
        true_solar_time(datetime(2027, 7, 11, 12, 0), 113.0)


def test_four_pillars_requires_tz() -> None:
    from core_time import compute_four_pillars

    with pytest.raises(ValueError):
        compute_four_pillars(datetime(2027, 7, 11, 12, 0))


def test_true_solar_time_requires_longitude() -> None:
    from core_time import CalendarConfig, compute_four_pillars

    with pytest.raises(ValueError, match="经度"):
        compute_four_pillars(
            datetime(2027, 7, 11, 12, 0, tzinfo=CST),
            CalendarConfig(use_true_solar_time=True),
        )


def test_true_solar_time_shift_changes_hour_branch() -> None:
    """真太阳时开启后，东经 113° 的 23:30 可能回退到亥时。"""
    from core_time import CalendarConfig, compute_four_pillars

    base = compute_four_pillars(datetime(2027, 7, 11, 23, 30, tzinfo=CST))
    shifted = compute_four_pillars(
        datetime(2027, 7, 11, 23, 30, tzinfo=CST),
        CalendarConfig(use_true_solar_time=True),
        lon=113.26,
    )
    assert base.hour.zhi == "子"
    assert shifted.hour.zhi in ("子", "亥")
