"""吉神表测试（Phase 11）：天德 / 月德 / 月德合 / 天赦。

为什么这些断言值得写
--------------------
吉神表是最容易「抄错一个干、整月结论全反」的地方，而它长得像常识、不容易被人复核。
故测试分两类：
1. **口诀逐项核对**：把《协纪辨方书》义例口诀逐字拆成 12 个月的期望值；
2. **结构不变式**：月德只取阳干（乙丁辛癸永不出现）、天赦四季各一日、
   月德合必与月德五合 —— 这类不变式不依赖具体抄本也能抓错。
"""

from __future__ import annotations

import pytest

from core_symbol.ganzhi import GAN_HE
from core_symbol.jishen import (
    TIAN_DE_GUA_CALIBERS,
    TIAN_DE_TABLE,
    derive_jishen_facts,
    tiande_of_month,
    tianshe_of_month,
    yuande_he_of_month,
    yuande_of_month,
)

#: 义例口诀「正丁二坤宫，三壬四辛同，五乾六甲上，七癸八艮中，九丙十居乙，子巽丑庚从」
TIAN_DE_KOUJUE: dict[str, tuple[str, str]] = {
    "寅": ("gan", "丁"), "卯": ("gong", "坤"), "辰": ("gan", "壬"), "巳": ("gan", "辛"),
    "午": ("gong", "乾"), "未": ("gan", "甲"), "申": ("gan", "癸"), "酉": ("gong", "艮"),
    "戌": ("gan", "丙"), "亥": ("gan", "乙"), "子": ("gong", "巽"), "丑": ("gan", "庚"),
}

#: 月德「寅午戌月丙，亥卯未月甲，申子辰月壬，巳酉丑月庚」
YUE_DE_KOUJUE: dict[str, str] = {
    "寅": "丙", "午": "丙", "戌": "丙",
    "亥": "甲", "卯": "甲", "未": "甲",
    "申": "壬", "子": "壬", "辰": "壬",
    "巳": "庚", "酉": "庚", "丑": "庚",
}


class TestTianDe:
    def test_table_matches_koujue(self) -> None:
        assert TIAN_DE_TABLE == TIAN_DE_KOUJUE

    def test_four_gong_months_only(self) -> None:
        gongs = {z for z, (kind, _v) in TIAN_DE_TABLE.items() if kind == "gong"}
        assert gongs == {"卯", "午", "酉", "子"}

    def test_gan_months_ignore_caliber(self) -> None:
        """天德为干的月份，卦位口径不应改变结论。"""
        a = derive_jishen_facts(month_zhi="寅", day_ganzhi="丁卯", tiande_caliber="gong_union")
        b = derive_jishen_facts(month_zhi="寅", day_ganzhi="丁卯", tiande_caliber="shen_hai_yin_si")
        assert a["tian_de"]["hit"] is True is b["tian_de"]["hit"]
        assert a["tian_de"]["alternatives"] == []

    @pytest.mark.parametrize(
        ("day_zhi", "gong_union", "shen_hai", "wei_xu"),
        [
            ("未", True, False, True),   # 卯月：坤宫 = 未申
            ("申", True, True, False),
            ("戌", False, False, False),  # 不在坤宫
        ],
    )
    def test_gong_calibers_diverge(self, day_zhi: str, gong_union: bool, shen_hai: bool, wei_xu: bool) -> None:
        hits = {
            cal: derive_jishen_facts(month_zhi="卯", day_ganzhi=f"甲{day_zhi}", tiande_caliber=cal)["tian_de"]["hit"]
            for cal in ("gong_union", "shen_hai_yin_si", "wei_xu_chou_chen")
        }
        assert hits == {"gong_union": gong_union, "shen_hai_yin_si": shen_hai, "wei_xu_chou_chen": wei_xu}

    def test_gua_calibers_cover_same_gong(self) -> None:
        """两单支口径的并集 == 整宫口径（分歧只在「取单支还是整宫」）。"""
        from core_symbol.jishen import GUA_ZHI, _tiande_zhi_set

        for gong in GUA_ZHI:
            left = set(_tiande_zhi_set(gong, "shen_hai_yin_si"))
            right = set(_tiande_zhi_set(gong, "wei_xu_chou_chen"))
            assert left | right == set(GUA_ZHI[gong])
            assert left & right == set()

    def test_unknown_caliber_raises(self) -> None:
        with pytest.raises(ValueError):
            derive_jishen_facts(month_zhi="卯", day_ganzhi="甲申", tiande_caliber="nope")

    def test_all_calibers_registered_in_config(self) -> None:
        """口径名必须与 core-rule/config/calibers/tiande.yaml 一致（防两处漂移）。"""
        import yaml
        from pathlib import Path

        cfg = Path(__file__).resolve().parents[2] / "core-rule" / "config" / "calibers" / "tiande.yaml"
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        assert set(data["calibers"]) == {"gong_union", *TIAN_DE_GUA_CALIBERS}


class TestYueDe:
    def test_table_matches_koujue(self) -> None:
        assert {z: yuande_of_month(z) for z in YUE_DE_KOUJUE} == YUE_DE_KOUJUE

    def test_only_yang_stems(self) -> None:
        """月属阴，以阳干为德：乙丁辛癸永不出现，戊（土）亦不与。"""
        used = set(YUE_DE_KOUJUE.values())
        assert used == {"丙", "甲", "壬", "庚"}
        assert not used & set("乙丁辛癸戊")

    def test_he_is_wuhe(self) -> None:
        for month_zhi in YUE_DE_KOUJUE:
            gan = yuande_of_month(month_zhi)
            he = yuande_he_of_month(month_zhi)
            assert frozenset((gan, he)) in GAN_HE, f"{gan}/{he} 非五合"

    def test_hit_semantics(self) -> None:
        # 寅月（寅午戌）月德为丙、月德合为辛
        de = derive_jishen_facts(month_zhi="寅", day_ganzhi="丙午")
        assert de["yue_de"]["hit"] is True and de["yue_de"]["he_hit"] is False
        he = derive_jishen_facts(month_zhi="寅", day_ganzhi="辛未")
        assert he["yue_de"]["hit"] is False and he["yue_de"]["he_hit"] is True
        neither = derive_jishen_facts(month_zhi="寅", day_ganzhi="甲子")
        assert neither["yue_de"]["hit"] is False and neither["yue_de"]["he_hit"] is False


class TestTianShe:
    @pytest.mark.parametrize(
        ("month_zhi", "season", "day"),
        [("寅", "春", "戊寅"), ("卯", "春", "戊寅"), ("巳", "夏", "甲午"),
         ("申", "秋", "戊申"), ("亥", "冬", "甲子"), ("丑", "冬", "甲子")],
    )
    def test_seasons(self, month_zhi: str, season: str, day: str) -> None:
        got_season, got_day = tianshe_of_month(month_zhi)
        assert (got_season, got_day) == (season, day)

    def test_hit_requires_exact_ganzhi(self) -> None:
        """甲子日只是「冬」之赦；同季其他日不算。"""
        ok = derive_jishen_facts(month_zhi="亥", day_ganzhi="甲子")
        assert ok["tian_she"]["hit"] is True
        other = derive_jishen_facts(month_zhi="亥", day_ganzhi="甲戌")
        assert other["tian_she"]["hit"] is False

    def test_each_season_has_one_day(self) -> None:
        seen = {tianshe_of_month(z)[1] for z in ("寅", "巳", "申", "亥")}
        assert len(seen) == 4
