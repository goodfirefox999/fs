"""斗首五行规则包测试（Phase 9）。

覆盖三层：
1. **表层**：斗首五行表 / 化气表 完整性，且与正五行**不同**（最容易写错的地方）；
2. **事实层**：五星定位、番化、得位（含土长生两口径）；
3. **集成层**：``derive_facts`` 必须产出 ``facts.doushou``，且口径回显。
"""

from __future__ import annotations

from datetime import date

import pytest

from core_symbol.doushou import (
    DOUSHOU_ELEMENT,
    FANHUA,
    HUAQI_ELEMENT,
    derive_doushou_facts,
)
from core_symbol.mountain import MOUNTAINS_24


class TestTables:
    def test_doushou_covers_all_24_mountains(self) -> None:
        assert set(DOUSHOU_ELEMENT) == set(MOUNTAINS_24)
        assert len(DOUSHOU_ELEMENT) == 24

    def test_huaqi_covers_all_10_stems(self) -> None:
        assert set(HUAQI_ELEMENT) == set("甲乙丙丁戊己庚辛壬癸")
        # 五运：甲己土 乙庚金 丙辛水 丁壬木 戊癸火
        assert HUAQI_ELEMENT["甲"] == HUAQI_ELEMENT["己"] == "土"
        assert HUAQI_ELEMENT["乙"] == HUAQI_ELEMENT["庚"] == "金"
        assert HUAQI_ELEMENT["丙"] == HUAQI_ELEMENT["辛"] == "水"
        assert HUAQI_ELEMENT["丁"] == HUAQI_ELEMENT["壬"] == "木"
        assert HUAQI_ELEMENT["戊"] == HUAQI_ELEMENT["癸"] == "火"

    def test_doushou_element_differs_from_zhengwuxing(self) -> None:
        """斗首五行 ≠ 正五行：甲山斗首属水（正五行属木）、子山斗首属土（正五行属水）。

        这条断言是防回归的核心——两张表一旦被"顺手统一"，斗首整套判定全错。
        """
        assert DOUSHOU_ELEMENT["甲"] == "水"
        assert DOUSHOU_ELEMENT["子"] == "土"
        assert DOUSHOU_ELEMENT["壬"] == "土"
        assert DOUSHOU_ELEMENT["癸"] == "火"
        # 与正五行相同的只有部分山，整体分布是 6/4/6/4/4
        from collections import Counter

        dist = Counter(DOUSHOU_ELEMENT.values())
        assert dist == {"土": 6, "火": 6, "木": 4, "水": 4, "金": 4}

    def test_fanhua_covers_five_aliases(self) -> None:
        assert set(FANHUA) == {"元辰", "武财", "贪官", "破鬼", "廉子"}
        assert FANHUA["元辰"] == "元辰"
        assert FANHUA["武财"] == "贪官"
        assert FANHUA["贪官"] == "破鬼"
        assert FANHUA["破鬼"] == "廉子"
        assert FANHUA["廉子"] == "武财"


class TestDerive:
    def test_golden_case_qian_mountain(self) -> None:
        """金标准：乾山，丁未 丁未 辛卯 乙未（未月）。

        乾山斗首属火；丁化木（生我→贪狼）、辛化水（克我→破军）、乙化金（我克→武曲）。
        """
        fx = derive_doushou_facts(
            mountain_name="乾", gans=["丁", "丁", "辛", "乙"], month_zhi="未"
        )
        assert fx["shan"]["element"] == "火"
        stars = [s["star"] for s in fx["stems"]]
        assert stars == ["贪狼", "贪狼", "破军", "武曲"]
        assert fx["counts"] == {"元辰": 0, "贪狼": 2, "廉贞": 0, "武曲": 1, "破军": 1}
        assert fx["sanyuan"] is False
        assert fx["sanwu"] is False
        assert fx["status"] == "待考证"

    def test_same_element_is_yuanchen(self) -> None:
        """乾山属火，戊/癸化火 → 同我 → 元辰。"""
        fx = derive_doushou_facts(
            mountain_name="乾", gans=["戊", "癸", "戊", "癸"], month_zhi="午"
        )
        assert [s["star"] for s in fx["stems"]] == ["元辰"] * 4
        assert fx["sanyuan"] is True

    def test_sanwu_ge(self) -> None:
        """乾山属火，乙/庚化金 → 我克 → 武财，三见即三武格。"""
        fx = derive_doushou_facts(
            mountain_name="乾", gans=["乙", "庚", "乙", "戊"], month_zhi="午"
        )
        assert fx["counts"]["武曲"] == 3
        assert fx["sanwu"] is True
        assert fx["sanyuan"] is False

    def test_lianzhen_wosheng(self) -> None:
        """乾山属火，甲/己化土 → 我生 → 廉贞。"""
        fx = derive_doushou_facts(
            mountain_name="乾", gans=["甲", "己", "甲", "己"], month_zhi="午"
        )
        assert [s["star"] for s in fx["stems"]] == ["廉贞"] * 4

    def test_dewei_by_month(self) -> None:
        """得位＝化气五行于月令逢长生/冠带/临官/帝旺。

        木长生在亥：亥=长生、丑=冠带、寅=临官、卯=帝旺；辰=衰 不得位。
        """
        fx = derive_doushou_facts(mountain_name="乾", gans=["丁", "甲", "乙", "丙"], month_zhi="寅")
        ding = fx["stems"][0]  # 丁化木，寅月 → 临官
        assert ding["huaqi"] == "木"
        assert ding["stage"] == "临官"
        assert ding["dewei"] is True

        fx2 = derive_doushou_facts(mountain_name="乾", gans=["丁", "甲", "乙", "丙"], month_zhi="辰")
        assert fx2["stems"][0]["stage"] == "衰"
        assert fx2["stems"][0]["dewei"] is False

    def test_tu_changsheng_caliber_flips_result(self) -> None:
        """土的长生位两说：申（土寄坤）vs 寅（土寄艮），对土行得位给出相反结论。"""
        # 艮山斗首属木 → 用甲/己化土 得「我克」；此处只看得位，故取土行本身
        # 直接构造：艮山属木，甲化土；土在「申」月为长生，在「寅」月为长生
        shen = derive_doushou_facts(
            mountain_name="艮", gans=["甲", "甲", "甲", "甲"], month_zhi="申",
            tu_changsheng="shen",
        )
        yin = derive_doushou_facts(
            mountain_name="艮", gans=["甲", "甲", "甲", "甲"], month_zhi="申",
            tu_changsheng="yin",
        )
        assert shen["stems"][0]["stage"] == "长生"
        assert shen["stems"][0]["dewei"] is True
        assert yin["stems"][0]["stage"] == "病"
        assert yin["stems"][0]["dewei"] is False

    def test_unknown_mountain_degrades_not_silently(self) -> None:
        fx = derive_doushou_facts(mountain_name="?", gans=["甲", "乙", "丙", "丁"], month_zhi="子")
        assert fx["shan"]["element"] is None
        assert all(s["star"] is None for s in fx["stems"])
        assert any("不在二十四山斗首五行表内" in m for m in fx["needs_human_review"])

    def test_invalid_caliber_rejected(self) -> None:
        with pytest.raises(ValueError):
            derive_doushou_facts(
                mountain_name="乾", gans=["甲"], month_zhi="子", tu_changsheng="bogus"
            )

    def test_needs_human_review_declares_ambiguities(self) -> None:
        fx = derive_doushou_facts(
            mountain_name="乾", gans=["丁", "辛", "乙", "甲"], month_zhi="未"
        )
        joined = " ".join(fx["needs_human_review"])
        assert "土寄坤" in joined
        assert "贪狼" in joined and "廉贞" in joined
        assert "番化" in joined


class TestIntegration:
    def test_derive_facts_exposes_doushou(self) -> None:
        from core_symbol.mountain import mountain_by_name
        from core_symbol.registry import derive_facts

        mountain = mountain_by_name("乾")
        fx = derive_facts(
            year_zhi="未",
            month_zhi="未",
            day_ganzhi="辛卯",
            gans=["丁", "丁", "辛", "乙"],
            zhis=["未", "未", "卯", "未"],
            mountain=mountain,
            facing=mountain_by_name("巽"),
            shan_jia_zhi="亥",
            local_date=date(2027, 7, 11),
            doushou_tu_changsheng="shen",
        )
        assert "doushou" in fx
        assert fx["doushou"]["shan"]["element"] == "火"
        assert fx["_calibers"]["doushou_tu_changsheng"] == "shen"

    def test_caliber_is_echoed(self) -> None:
        from core_symbol.mountain import mountain_by_name
        from core_symbol.registry import derive_facts

        fx = derive_facts(
            year_zhi="午",
            month_zhi="午",
            day_ganzhi="甲子",
            gans=["甲", "庚", "甲", "庚"],
            zhis=["午", "午", "子", "午"],
            mountain=mountain_by_name("乾"),
            local_date=date(2026, 6, 1),
            doushou_tu_changsheng="yin",
        )
        assert fx["doushou"]["caliber"]["tu_changsheng"] == "yin"
        assert fx["_calibers"]["doushou_tu_changsheng"] == "yin"
