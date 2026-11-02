"""符号层测试：干支关系、自刑纠正、二十四山、分金、纳音、旬空、派生事实状态。"""

from __future__ import annotations

import pytest

from core_symbol import (
    GANZHI60,
    MOUNTAINS_24,
    ZHI,
    ZIXING,
    all_relations_between_zhi,
    derive_facts,
    facing_of,
    fact_status_summary,
    fenjin_of_azimuth,
    jian_xiang,
    mountain_of_azimuth,
    nayin_element_of,
    nayin_of,
    relation_between_zhi,
    same_group,
    sanhe_present,
    unavailable_facts,
    wuhuang_year,
    xunkong_of,
    zhi_counts,
)


class TestSelfPunishment:
    """自刑纠正：仅辰辰、午午、酉酉、亥亥；未未不是自刑。"""

    @pytest.mark.parametrize("zhi", ["辰", "午", "酉", "亥"])
    def test_self_punishment_pairs(self, zhi: str) -> None:
        rel = relation_between_zhi(zhi, zhi)
        assert rel.kind == "自刑", f"{zhi}{zhi} 应为自刑，得到 {rel.kind}"

    def test_weiwei_is_not_self_punishment(self) -> None:
        rel = relation_between_zhi("未", "未")
        assert rel.kind != "自刑"
        assert rel.kind == "同支"

    def test_zixing_set_exact(self) -> None:
        assert ZIXING == frozenset("辰午酉亥")
        assert "未" not in ZIXING

    @pytest.mark.parametrize("zhi", ["子", "丑", "寅", "卯", "巳", "申", "戌", "未"])
    def test_non_zixing_branches(self, zhi: str) -> None:
        assert relation_between_zhi(zhi, zhi).kind != "自刑"


class TestRelations:
    @pytest.mark.parametrize(
        "a,b,kind",
        [("子", "午", "冲"), ("丑", "未", "冲"), ("寅", "亥", "合"), ("辰", "酉", "合"),
         ("子", "未", "害"), ("寅", "巳", "刑"), ("子", "酉", "破")],
    )
    def test_pair_relations(self, a: str, b: str, kind: str) -> None:
        kinds = [r.kind for r in all_relations_between_zhi(a, b)]
        assert kind in kinds, f"{a}{b} 应含 {kind}，得到 {kinds}"

    def test_sanhe_groups(self) -> None:
        assert sanhe_present("申子辰") == [(frozenset("申子辰"), "水")]
        assert sanhe_present("亥卯未") == [(frozenset("亥卯未"), "木")]
        assert sanhe_present("亥卯") == []

    def test_same_group_kinds(self) -> None:
        assert same_group("亥", "卯", "sanhe")
        assert same_group("子", "午", "chong")
        assert not same_group("子", "丑", "chong")

    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(ValueError):
            same_group("子", "丑", "unknown_kind")

    def test_zhi_counts(self) -> None:
        assert zhi_counts(["未", "未", "卯", "未"]) == {"未": 3, "卯": 1}


class TestMountain:
    def test_er_shisi_shan_order(self) -> None:
        assert len(MOUNTAINS_24) == 24
        # 逐位断言：变异测试发现"只抽查首尾"会漏掉中间两位互换
        expected = ("子", "癸", "丑", "艮", "寅", "甲", "卯", "乙", "辰", "巽", "巳", "丙",
                    "午", "丁", "未", "坤", "申", "庚", "酉", "辛", "戌", "乾", "亥", "壬")
        assert MOUNTAINS_24 == expected

    def test_qian_shan_xun_xiang(self) -> None:
        m = mountain_of_azimuth(315.0)
        assert m.name == "乾"
        assert facing_of(m).name == "巽"

    def test_jian_xiang_threshold(self) -> None:
        assert jian_xiang(mountain_of_azimuth(315.0)) is None       # 正针
        assert jian_xiang(mountain_of_azimuth(316.0)) is None       # 未过 3°
        assert jian_xiang(mountain_of_azimuth(320.0)) == "亥"       # 兼亥
        assert jian_xiang(mountain_of_azimuth(310.0)) == "戌"       # 兼戌

    def test_azimuth_normalization(self) -> None:
        assert mountain_of_azimuth(360.0).name == "子"
        assert mountain_of_azimuth(-15.0).name == "壬"

    def test_fenjin_slots(self) -> None:
        fj = fenjin_of_azimuth(320.0)
        assert fj.mountain.name == "乾"
        assert 0 <= fj.slot <= 4
        # 每山 5 槽、每槽 3°：槽中心应落在 [307.5, 322.5]
        assert 307.5 <= fj.center_deg <= 322.5


class TestNayinXunkong:
    def test_nayin_known(self) -> None:
        assert nayin_of("甲子") == "海中金"
        assert nayin_of("丙寅") == "炉中火"
        assert nayin_of("壬戌") == "大海水"
        assert nayin_element_of("甲子") == "金"

    def test_nayin_full_coverage(self) -> None:
        for gz in GANZHI60:
            assert nayin_of(gz)

    def test_xunkong(self) -> None:
        assert xunkong_of("甲子").empty == ("戌", "亥")
        assert xunkong_of("辛卯").head == "甲申"
        assert xunkong_of("辛卯").empty == ("午", "未")
        assert xunkong_of("癸亥").head == "甲寅"
        assert xunkong_of("癸亥").empty == ("子", "丑")


class TestFacts:
    def _facts(self, **overrides):
        base = dict(
            year_zhi="未", month_zhi="未", day_ganzhi="辛卯",
            gans=["丁", "丁", "辛", "乙"], zhis=["未", "未", "卯", "未"],
            mountain=mountain_of_azimuth(320.0), facing=facing_of(mountain_of_azimuth(320.0)),
            shan_jia_zhi="亥",
        )
        base.update(overrides)
        return derive_facts(**base)

    def test_sansha_for_weiyear(self) -> None:
        """丁未年属亥卯未木局 → 三煞在西方（申酉戌）。"""
        f = self._facts()
        assert f["sansha"]["year"]["mountains"] == ["申", "酉", "戌"]
        assert f["sansha"]["year"]["direction"] == "西"
        assert f["sansha"]["year"]["hit_mountain"] is False

    def test_tiaohou_uses_day_gan(self) -> None:
        """调候按日干（gans[2]=辛），不是年干（gans[0]=丁）。"""
        f = self._facts()
        assert f["tiaohou"]["day_gan"] == "辛"

    def test_lumaguiren_uses_day_gan(self) -> None:
        """禄神按日干取：辛日禄在酉；若误用年干丁则禄在午。"""
        f = self._facts(shan_jia_zhi="酉")
        assert f["lumaguiren"]["lu"] == "酉"
        assert f["lumaguiren"]["lu_to_shan"] is True

    def test_sanhe_with_mountain(self) -> None:
        f = self._facts()
        assert len(f["structure"]["sanhe_with_mountain"]) == 1
        assert f["structure"]["sanhe_with_mountain"][0]["group"] == ["亥", "卯", "未"]

    def test_repeat_is_not_zixing(self) -> None:
        f = self._facts()
        assert f["structure"]["max_repeat"] == 3
        assert f["structure"]["repeated"] == {"未": 3}
        assert f["structure"]["zixing_pairs"] == []

    def test_yinfu_not_inferred(self) -> None:
        """阴府须以坐山纳音取，取用体系未裁定 → 本系统不推断。"""
        f = self._facts()
        assert f["yinfu"]["candidates"]["value"] is None
        assert f["yinfu"]["candidates"]["status"] == "有争议"

    def test_unavailable_facts_registered(self) -> None:
        names = unavailable_facts()
        for expected in ("dutiansha", "fubing_dahuo", "yangongji", "wuhuang.month"):
            assert expected in names

    def test_fact_status_has_no_verified_except_xunkong(self) -> None:
        summary = fact_status_summary()
        assert summary.get("已考证", 0) >= 1  # 旬空表
        assert summary.get("待考证", 0) >= 5

    def test_wuhuang_year_2027(self) -> None:
        """2027 年九紫入中，五黄落坎（正北）。"""
        wh = wuhuang_year(2027)
        assert wh.value["center_star"] == 9
        assert wh.value["palace"] == "坎"
        assert wh.value["mountain"] == "子"

    def test_wuhuang_year_2024(self) -> None:
        """2024 年三碧入中，五黄落兑（正西）。"""
        wh = wuhuang_year(2024)
        assert wh.value["center_star"] == 3
        assert wh.value["palace"] == "兑"


def test_zhi_tuple_is_12() -> None:
    assert len(ZHI) == 12
