"""Phase 7 玄空大卦规则包测试（评审扩展版 spec §2.4 + §6）。"""
import json
from pathlib import Path

import pytest

from core_rule.loader import load_rule

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "core-rule/config/data"
RULES = ROOT / "core-rule/rules/xuankong_dagua"


class TestXuankongPackExistence:
    EXPECTED = ["XK-GUAYUN-001", "XK-CHOUYAO-001", "XK-GUAQI-001", "XK-WANGQI-001"]

    def test_all_four_rules_exist(self) -> None:
        for rid in self.EXPECTED:
            path = RULES / f"{rid}.yaml"
            assert path.exists(), f"{rid}.yaml 不存在"
            rule = load_rule(path)
            assert rule.school == "xuankong_dagua"

    def test_xuankong_dagua_enabled(self, registry) -> None:
        assert registry.policy.schools["xuankong_dagua"].enabled, "Phase 7 启用"
        assert "xuankong_dagua" in registry.policy.route("入宅"), "入宅路由应含 xuankong_dagua"


class TestGuayunCalculation:
    """卦运计算：阳爻 9 年阴爻 6 年（spec 硬性要求）。"""

    def test_data_file_loads(self) -> None:
        data = json.loads((DATA / "xuankong_64gua.json").read_text(encoding="utf-8"))
        assert "hexagrams" in data and "guayun_rule" in data

    def test_kun_guayun_1(self) -> None:
        """坤卦三阴爻 = 6+6+6 = 18 年，管一运。"""
        data = json.loads((DATA / "xuankong_64gua.json").read_text(encoding="utf-8"))
        kun = data["hexagrams"]["坤"]
        assert kun["guayun"] == 1, "坤卦应管一运"
        assert kun["years"] == 18, f"坤卦 18 年，实际 {kun['years']}"

    def test_qian_guayun_9(self) -> None:
        """乾卦三阳爻 = 9×3 = 27 年，管九运。"""
        data = json.loads((DATA / "xuankong_64gua.json").read_text(encoding="utf-8"))
        qian = data["hexagrams"]["乾"]
        assert qian["guayun"] == 9, "乾卦应管九运"
        assert qian["years"] == 27, f"乾卦 27 年，实际 {qian['years']}"

    def test_no_wuyun(self) -> None:
        """玄空大卦无五运。"""
        data = json.loads((DATA / "xuankong_yunyun.json").read_text(encoding="utf-8"))
        assert data["yuan_yun"]["五运"] is None, "五运必须为 null（无五运）"

    def test_384_yao_precision(self) -> None:
        """64 卦 × 6 爻 = 384 爻，每爻 0.9375°。"""
        angle_per_gua = 360 / 64
        angle_per_yao = angle_per_gua / 6
        assert angle_per_gua == 5.625, f"每卦 {angle_per_gua}°"
        assert angle_per_yao == 0.9375, f"每爻 {angle_per_yao}°"
        assert 64 * 6 == 384, "384 爻"
        assert 384 * 0.9375 == 360, "384 爻 × 0.9375° = 360°"


class TestHetuData:
    def test_hetu_loads(self) -> None:
        data = json.loads((DATA / "xuankong_hetu.json").read_text(encoding="utf-8"))
        assert "generated_numbers" in data
        assert len(data["generated_numbers"]) == 5, "河图 5 组生成数"

    def test_he_shi_pairs(self) -> None:
        data = json.loads((DATA / "xuankong_hetu.json").read_text(encoding="utf-8"))
        for a, b in data["he_shi"]["pairs"]:
            assert a + b == 10 or a + b == 5 or a + b == 15, f"({a},{b}) 不合五/十/十五"


class TestXuankongDataCompleteness:
    """64 卦数据完整性：此前仅 8 纯卦、56 别卦缺失——收尾补全。"""

    def test_64_hexagrams_complete(self) -> None:
        data = json.loads((DATA / "xuankong_64gua.json").read_text(encoding="utf-8"))
        hx = data["hexagrams"]
        assert len(hx) == 64, f"64 卦，实际 {len(hx)}"
        binaries = {g["binary"] for g in hx.values()}
        assert len(binaries) == 64, "二进制须两两不同"
        names = set(hx)
        assert {"乾", "坤", "否", "泰", "既济", "未济", "复", "姤"} <= names

    def test_circle_order_is_fuxi_sequence(self) -> None:
        """圆图次序 = 二进制降序（伏羲先天次序），端点为乾/坤、中界复/姤。"""
        data = json.loads((DATA / "xuankong_64gua.json").read_text(encoding="utf-8"))
        order = data["circle_order"]
        assert len(order) == 64
        assert order[:8] == ["乾", "夬", "大有", "大壮", "小畜", "需", "大畜", "泰"]
        assert order[15] == "临" and order[16] == "同人"
        assert order[31] == "复" and order[32] == "姤"
        assert order[47] == "师" and order[48] == "遁"
        assert order[63] == "坤"
        # 与 hexagrams 二进制一致
        hx = data["hexagrams"]
        assert [hx[n]["binary"] for n in order] == sorted(
            (g["binary"] for g in hx.values()), reverse=True
        )

    def test_all_guayun_follow_inner_trigram(self) -> None:
        """64 别卦卦运 = 内卦经卦运数；years = 内卦经卦运年期。"""
        data = json.loads((DATA / "xuankong_64gua.json").read_text(encoding="utf-8"))
        jing_yun = {"坤": 1, "巽": 2, "离": 3, "兑": 4, "艮": 6, "坎": 7, "震": 8, "乾": 9}
        jing_years = {"坤": 18, "巽": 24, "离": 24, "兑": 24, "艮": 21, "坎": 21, "震": 21, "乾": 27}
        for name, g in data["hexagrams"].items():
            assert g["lower"] in jing_yun, f"{name} 内卦非法"
            assert g["guayun"] == jing_yun[g["lower"]], f"{name} 卦运须取内卦 {g['lower']}"
            assert g["years"] == jing_years[g["lower"]], f"{name} 年期须为内卦运年期"
            # binary 与 lower/upper 三爻一致
            tri = {"乾": "111", "兑": "110", "离": "101", "震": "100",
                   "巽": "011", "坎": "010", "艮": "001", "坤": "000"}
            assert g["binary"] == tri[g["lower"]] + tri[g["upper"]], f"{name} 二进制与内/外卦不符"

    def test_jinggua_years_sum_90_90(self) -> None:
        """经卦运年期：上元（坤巽离兑）90 年＋下元（艮坎震乾）90 年＝180 年。"""
        jing_years = {"坤": 18, "巽": 24, "离": 24, "兑": 24, "艮": 21, "坎": 21, "震": 21, "乾": 27}
        assert sum(jing_years[k] for k in ("坤", "巽", "离", "兑")) == 90
        assert sum(jing_years[k] for k in ("艮", "坎", "震", "乾")) == 90

    def test_yunyun_years_match_jinggua(self) -> None:
        """元运表各运年数 = 其经卦运年期（曾出现巽18/离21/艮24/震24 四处错值）。"""
        data = json.loads((DATA / "xuankong_yunyun.json").read_text(encoding="utf-8"))
        jing_years = {"坤": 18, "巽": 24, "离": 24, "兑": 24, "艮": 21, "坎": 21, "震": 21, "乾": 27}
        for yname, spec in data["yuan_yun"].items():
            if spec is None:
                assert yname == "五运"
                continue
            assert spec["years"] == jing_years[spec["gua"]], f"{yname}({spec['gua']}) 年数错"
        shang = sum(s["years"] for s in data["yuan_yun"].values() if s and s["period"] == "上元")
        xia = sum(s["years"] for s in data["yuan_yun"].values() if s and s["period"] == "下元")
        assert (shang, xia) == (90, 90)


class TestDayun:
    """大卦元运：上元甲子起一运，阳爻 9 年阴爻 6 年，180 年周期。"""

    @pytest.mark.parametrize(
        "year,expected_yun",
        [
            (1984, 1), (2001, 1),          # 一运 1984-2001（18 年）
            (2002, 2), (2025, 2),          # 二运 2002-2025（24 年）
            (2026, 3), (2027, 3), (2049, 3),  # 三运 2026-2049
            (2050, 4), (2073, 4),          # 四运 2050-2073
            (2074, 6), (2094, 6),          # 六运 2074-2094（21 年）
            (2095, 7), (2115, 7),          # 七运 2095-2115
            (2116, 8), (2136, 8),          # 八运 2116-2136
            (2137, 9), (2163, 9),          # 九运 2137-2163（27 年）
            (2164, 1),                     # 新周期 2164-2181
        ],
    )
    def test_dayun_sequence(self, year: int, expected_yun: int) -> None:
        from core_symbol.xuankong import current_dayun

        assert current_dayun(year)["yun"] == expected_yun

    def test_dayun_anchor_is_shangyuan_jiazi_not_any_jiazi(self) -> None:
        """锚定年须为 180 年周期的上元甲子（1984），而非运内甲子（2044）。

        回归：曾误用 60 年甲子周期取锚，导致 2044 被判为新周期一运。
        """
        from core_symbol.xuankong import current_dayun

        d = current_dayun(2044)
        assert d["yun"] == 3, "2044 仍在 1984 锚定的三运（2026-2049）内"
        assert d["anchor_year"] == 1984
        d2 = current_dayun(2027)
        assert d2["anchor_year"] == 1984 and d2["start_year"] == 2026 and d2["end_year"] == 2049

    def test_dayun_no_20y_simplification(self) -> None:
        """各运年数不等（18/24/24/24/21/21/21/27）——禁"每运 20 年"简化。"""
        from core_symbol.xuankong import current_dayun

        years = {current_dayun(y)["years"] for y in (1990, 2010, 2030, 2060, 2080, 2100, 2120, 2150)}
        assert years == {18, 24, 21, 27}, f"运年数须来自爻阴阳：{years}"


class TestCircle384:
    """先天圆图 384 爻：边界与排布口径（乾起午中、坤尽子中）。"""

    def test_south_boundary(self) -> None:
        from core_symbol.xuankong import yao_at_bearing

        c = yao_at_bearing(180.0)
        assert (c.gua, c.yao, c.half) == ("姤", 1, "west"), "180° 整点归西半姤初"
        c2 = yao_at_bearing(179.9)
        assert (c2.gua, c2.yao, c2.half) == ("乾", 1, "east"), "乾初爻在午中东侧"

    def test_north_boundary(self) -> None:
        from core_symbol.xuankong import yao_at_bearing

        assert (yao_at_bearing(0.0).gua, yao_at_bearing(0.0).yao) == ("复", 6)
        assert (yao_at_bearing(359.9).gua, yao_at_bearing(359.9).yao) == ("坤", 6)

    def test_quarter_points(self) -> None:
        from core_symbol.xuankong import yao_at_bearing

        c = yao_at_bearing(90.0)   # 卯山心 → 同人初爻（东半第 97 爻）
        assert (c.gua, c.yao, c.half) == ("同人", 1, "east")
        c2 = yao_at_bearing(315.0)  # 乾山心 → 否初爻（西半）
        assert (c2.gua, c2.yao, c2.half) == ("否", 1, "west")

    def test_yao_width_and_contiguity(self) -> None:
        from core_symbol.xuankong import DEG_PER_YAO, yao_at_bearing

        assert DEG_PER_YAO == 0.9375
        cells = [yao_at_bearing(180.0 + i * DEG_PER_YAO + 0.01) for i in range(192)]
        assert [c.gua for c in cells][:6] == ["姤"] * 6, "姤卦 6 爻连续"
        assert cells[191].gua == "坤" and cells[191].yao == 6
        for a, b in zip(cells, cells[1:]):
            assert b.start_deg >= a.end_deg - 1e-9, "爻区间须递增不重叠"


class TestChangedGua:
    """抽爻换象：翻转指定爻得变卦。"""

    def test_qian_yao_changes(self) -> None:
        from core_symbol.xuankong import changed_gua_name

        assert changed_gua_name("111111", 1) == "姤", "乾初爻变 → 姤（巽下乾上）"
        assert changed_gua_name("111111", 6) == "夬", "乾上爻变 → 夬（乾下兑上）"

    def test_pi_chu_yao_to_wuwang(self) -> None:
        from core_symbol.xuankong import changed_gua_name

        assert changed_gua_name("000111", 1) == "无妄", "否初爻变 → 无妄（震下乾上）"
        assert changed_gua_name("000000", 6) == "剥", "坤上爻变 → 剥（坤下艮上）"

    def test_yao_pos_bounds(self) -> None:
        import pytest as _pytest

        from core_symbol.xuankong import changed_gua_name

        with _pytest.raises(ValueError):
            changed_gua_name("111111", 0)
        with _pytest.raises(ValueError):
            changed_gua_name("111111", 7)


class TestGuaqiRelation:
    """卦气配合：两卦运数的河图关系。"""

    def test_he_shi(self) -> None:
        from core_symbol.xuankong import guaqi_relation

        assert guaqi_relation(1, 9) == "合十" and guaqi_relation(9, 1) == "合十"
        assert guaqi_relation(2, 8) == "合十" and guaqi_relation(3, 7) == "合十"
        assert guaqi_relation(4, 6) == "合十"

    def test_he_wu_shi_wu(self) -> None:
        from core_symbol.xuankong import guaqi_relation

        assert guaqi_relation(1, 4) == "合五" and guaqi_relation(2, 3) == "合五"
        assert guaqi_relation(6, 9) == "合十五" and guaqi_relation(7, 8) == "合十五"

    def test_he_shengcheng(self) -> None:
        from core_symbol.xuankong import guaqi_relation

        for a, b in ((1, 6), (2, 7), (3, 8), (4, 9)):
            assert guaqi_relation(a, b) == "合生成", (a, b)

    def test_none_cases(self) -> None:
        from core_symbol.xuankong import guaqi_relation

        assert guaqi_relation(3, 3) is None, "比和归旺气规则，不计卦气关系"
        assert guaqi_relation(1, 2) is None


class TestDeriveXuankongFacts:
    """facts.xuankong 集成：金标准口径（乾山巽向、2027 → 三运离）。"""

    def _facts(self):
        from datetime import date

        from core_symbol.mountain import mountain_by_name
        from core_symbol.xuankong import derive_xuankong_facts

        return derive_xuankong_facts(
            mountain=mountain_by_name("乾"),
            facing=mountain_by_name("巽"),
            local_date=date(2027, 7, 11),
        )

    def test_golden_case_values(self) -> None:
        fx = self._facts()
        g = fx["guayun_current"]
        assert g["current_yun"] == 3 and g["current_gua"] == "离"
        assert g["sitting_gua"] == "否" and g["sitting_guayun"] == 1
        assert g["matched"] is False, "一运否卦 vs 三运离 → 不当旺"
        assert fx["wangqi"]["daoshan"] is False
        assert fx["wangqi"]["facing_gua"] == "履" and fx["wangqi"]["daoxiang"] is False
        assert fx["guaqi"]["relation"] == "合五", "坐否（运1）向履（运4）→ 1+4 合五"
        cy = fx["chouyao"]
        assert (cy["sitting_gua"], cy["yao_pos"]) == ("否", 1)
        assert cy["changed_gua"] == "无妄" and cy["changed_guayun"] == 8
        assert cy["matched_dayun"] is False, "无妄八运 vs 三运 → 不当旺"
        assert cy["ding_cai"] is None, "丁爻/财爻流派分歧未实现"

    def test_dayun_matched_case(self) -> None:
        """构造当旺命中：三运卦坐山（离宫八卦内卦离，如丰卦方位）。

        离山心 90° → 同人（内离，三运卦）→ matched=True。
        """
        from datetime import date

        from core_symbol.mountain import mountain_by_name
        from core_symbol.xuankong import derive_xuankong_facts

        fx = derive_xuankong_facts(
            mountain=mountain_by_name("卯"),  # 90°
            facing=mountain_by_name("酉"),
            local_date=date(2027, 7, 11),
        )
        g = fx["guayun_current"]
        assert g["sitting_gua"] == "同人" and g["sitting_guayun"] == 3
        assert g["matched"] is True, "同人三运卦 vs 2027 三运 → 当旺"
        assert fx["wangqi"]["daoshan"] is True

    def test_review_flags_and_no_fortune_verdict(self) -> None:
        fx = self._facts()
        assert fx["status"] == "待考证"
        assert len(fx["needs_human_review"]) >= 4, "流派分歧须显式挂人工复核"
        assert "caliber" in fx and "dayun" in fx["caliber"]

    def test_missing_date_degrades_to_none(self) -> None:
        """local_date 缺失 → 当旺比对无法成立（None），不静默判 False。"""
        from core_symbol.mountain import mountain_by_name
        from core_symbol.xuankong import derive_xuankong_facts

        fx = derive_xuankong_facts(
            mountain=mountain_by_name("乾"), facing=None, local_date=None
        )
        assert fx["guayun_current"] is None
        assert fx["wangqi"] is None and fx["guaqi"] is None and fx["chouyao"] is None
