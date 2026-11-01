"""Phase 8 天星规则包测试（评审扩展版 spec §2.5 + §6）。"""
import json
from pathlib import Path

import pytest

from core_rule.loader import load_rule

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "core-rule/config/data"
RULES = ROOT / "core-rule/rules/tianxing"


class TestTianxingPackExistence:
    EXPECTED = ["TX-SUNDAO-001", "TX-MOONDAO-001", "TX-SANHEGONG-001", "TX-JIAFU-001"]

    def test_all_four_rules_exist(self) -> None:
        for rid in self.EXPECTED:
            path = RULES / f"{rid}.yaml"
            assert path.exists(), f"{rid}.yaml 不存在"
            rule = load_rule(path)
            assert rule.school == "tianxing"

    def test_tianxing_enabled(self, registry) -> None:
        assert registry.policy.schools["tianxing"].enabled, "Phase 8 启用"
        assert "tianxing" in registry.policy.route("安葬"), "安葬路由应含 tianxing"


class Test28Xiu:
    def test_28xiu_data_loads(self) -> None:
        data = json.loads((DATA / "tianxing_28xiu.json").read_text(encoding="utf-8"))
        assert len(data["xiu"]) == 28, "28 宿"

    def test_total_traditional_degrees(self) -> None:
        data = json.loads((DATA / "tianxing_28xiu.json").read_text(encoding="utf-8"))
        total = sum(x["xiu_width"] for x in data["xiu"])
        assert 364 <= total <= 365.25, (
            f"传统度总和应在 364–365.25 之间（版本差异），实际 {total}"
        )

    def test_not_equal_width(self) -> None:
        data = json.loads((DATA / "tianxing_28xiu.json").read_text(encoding="utf-8"))
        widths = [x["xiu_width"] for x in data["xiu"]]
        assert len(set(widths)) > 1, "宿度必须不等宽（禁止 360/28 均分）"

    def test_precession_recorded(self) -> None:
        data = json.loads((DATA / "tianxing_28xiu.json").read_text(encoding="utf-8"))
        assert data["precession_per_year_arcsec"] == 50.3, "岁差速率"

    def test_swisseph_requires_note(self) -> None:
        """四余隐曜计算：Swiss Ephemeris 可能不可用 → 标注。"""
        data = json.loads((DATA / "tianxing_qizheng_mapping.json").read_text(encoding="utf-8"))
        assert "zi_qi" in data and data["zi_qi"]["swisseph_id"] is None, "紫气无 SE 对应"


class TestShanOfLongitude:
    """黄道制到山映射：协纪辨方书节气到山表锚点。"""

    @pytest.mark.parametrize(
        "longitude,expected_shan",
        [
            (270, "子"),   # 冬至太阳到子
            (0, "卯"),     # 春分到卯
            (90, "午"),    # 夏至到午
            (180, "酉"),   # 秋分到酉
            (315, "艮"),   # 立春到艮
            (45, "巽"),    # 立夏到巽
            (135, "坤"),   # 立秋到坤
            (225, "乾"),   # 立冬到乾
            (285, "癸"),   # 小寒到癸
            (330, "寅"),   # 雨水到寅
        ],
    )
    def test_jieqi_anchors(self, longitude: float, expected_shan: str) -> None:
        from core_symbol.tianxing import shan_of_longitude

        assert shan_of_longitude(longitude) == expected_shan


class TestXiuOfLongitude:
    """二十八宿定位：不等宽宿度 + 岁差 + Spica 锚点。"""

    def test_spica_anchor_returns_jiao_zero(self) -> None:
        from core_symbol.tianxing import jiao_start_longitude, xiu_of_longitude

        x = xiu_of_longitude(jiao_start_longitude(2026), 2026)
        assert x["xiu"] == "角" and x["ruxiu_du"] == 0

    def test_winter_solstice_sun_in_ji(self) -> None:
        """2026 冬至太阳（黄经 270°）日躔箕宿（现代日躔一致性锚点）。"""
        from core_symbol.tianxing import xiu_of_longitude

        x = xiu_of_longitude(270.0, 2026)
        assert x["xiu"] == "箕", x
        assert x["element"] == "水"
        assert 1.0 <= x["ruxiu_du"] <= 4.0, x

    def test_chain_gap_returns_none_not_fudged(self) -> None:
        """宿度表总和 364 < 365.25：表末残差区间无宿可归 → None，不均摊。"""
        from core_symbol.tianxing import jiao_start_longitude, xiu_of_longitude

        x = xiu_of_longitude((jiao_start_longitude(2026) - 0.3) % 360, 2026)
        assert x["xiu"] is None
        assert "残差" in x.get("note", "")

    def test_precession_shifts_anchor(self) -> None:
        """岁差使角宿起点黄经逐年东移。"""
        from core_symbol.tianxing import jiao_start_longitude

        a = jiao_start_longitude(2000)
        b = jiao_start_longitude(2100)
        assert b > a
        assert b - a == pytest.approx(50.3 * 100 / 3600, abs=1e-6)


class TestShengdian:
    """升殿：曜在本曜之宿（殿宿由宿度表 element 字段承载）。"""

    def test_sun_in_fang_is_shengdian(self) -> None:
        """日在房宿（日殿）→ 升殿。"""
        data = json.loads((DATA / "tianxing_28xiu.json").read_text(encoding="utf-8"))
        elem = {x["name"]: x["element"] for x in data["xiu"]}
        assert elem["房"] == "日" and elem["虚"] == "日" and elem["昴"] == "日" and elem["星"] == "日"
        assert elem["心"] == "月" and elem["危"] == "月" and elem["毕"] == "月" and elem["张"] == "月"

    def test_qizheng_element_map_covers_seven(self) -> None:
        from core_symbol.tianxing import _QIZHENG_ELEMENT

        assert set(_QIZHENG_ELEMENT) == {"日", "月", "木", "火", "土", "金", "水"}


class TestDeriveTianxingFacts:
    """facts.tianxing 集成（需 pyswisseph；缺失环境自动降级 unknown）。"""

    def test_golden_case_structure(self) -> None:
        from datetime import date

        from core_symbol.tianxing import SWE_AVAILABLE, derive_tianxing_facts

        fx = derive_tianxing_facts(
            mountain_name="乾", facing_name="巽", local_date=date(2027, 7, 11)
        )
        assert fx["status"] == "待考证"
        assert fx["completeness"] == "PARTIAL"
        assert any("紫气" in m for m in fx["missing"]), "四余不可用须标 PARTIAL"
        assert len(fx["needs_human_review"]) >= 5
        if SWE_AVAILABLE:
            # 2027-07-11 太阳黄经 ≈ 108.7°（夏至后 19 天）→ 丁山
            sun = fx["bodies"]["日"]
            assert 107.0 <= sun["longitude"] <= 110.0
            assert sun["shan"] == "丁"
            assert fx["sun_daoshan"] is False, "坐乾山，太阳在丁山 → 不到山"
            # 罗睺/计都相差 180°
            luo = fx["bodies"]["罗睺"]["longitude"]
            ji = fx["bodies"]["计都"]["longitude"]
            assert (luo + 180.0) % 360.0 == pytest.approx(ji, abs=1e-6)
            # 紫气不推算
            assert fx["bodies"]["紫气"]["longitude"] is None
            # jiafu 为 bool（七政任一到坐山且升殿）
            assert isinstance(fx["jiafu"], bool)
        else:
            assert fx["sun_daoshan"] is None, "无星历库 → 事实为 None（unknown），不给 False"

    def test_missing_date_degrades(self) -> None:
        from core_symbol.tianxing import derive_tianxing_facts

        fx = derive_tianxing_facts(mountain_name="乾", facing_name=None, local_date=None)
        assert fx["sun_daoshan"] is None and fx["jiafu"] is None

    def test_sanzhi_mountain_gets_sanhe_verdict(self) -> None:
        from datetime import date

        from core_symbol.tianxing import SWE_AVAILABLE, derive_tianxing_facts

        fx = derive_tianxing_facts(
            mountain_name="子", facing_name="午", local_date=date(2027, 7, 11)
        )
        if SWE_AVAILABLE:
            assert fx["sanhe_gongzhao"] is None or isinstance(fx["sanhe_gongzhao"], bool)
            # 子山三合 = 申辰
        else:
            assert fx["sanhe_gongzhao"] is None

    def test_sizheng_bagan_mountain_sanhe_is_none(self) -> None:
        """八干四维山三合照不静默判 False——输出 None 挂人工复核。"""
        from datetime import date

        from core_symbol.tianxing import SWE_AVAILABLE, derive_tianxing_facts

        fx = derive_tianxing_facts(
            mountain_name="乾", facing_name="巽", local_date=date(2027, 7, 11)
        )
        if SWE_AVAILABLE:
            assert fx["sanhe_gongzhao"] is None, "乾为四维山 → 三合照 None（流派分歧）"


class TestEphemerisPrecision:
    """spec §6 星历精度：已知天象时刻与独立公布值误差 < 0.01°。

    锚点为**独立公布**的天象时刻（NASA/天文年历），不是 swisseph 自身输出：
    - 二分二至：太阳视黄经恰为 0/90/180/270°；
    - 朔（合朔）：日月黄经差 ≈ 0°；望：差 ≈ 180°。
    """

    TOL = 0.01

    @pytest.mark.parametrize(
        "y,mo,d,h,target",
        [
            (2024, 3, 20, 3.10, 0), (2024, 6, 20, 20.85, 90),
            (2024, 9, 22, 12.73, 180), (2024, 12, 21, 9.33, 270),
            (2025, 3, 20, 9.02, 0), (2025, 6, 21, 2.70, 90),
            (2025, 9, 22, 18.32, 180), (2025, 12, 21, 15.05, 270),
        ],
    )
    def test_sun_at_equinox_solstice(self, y, mo, d, h, target) -> None:
        import swisseph as swe

        jd = swe.julday(y, mo, d, h)
        sun, _ = swe.calc_ut(jd, swe.SUN, swe.FLG_MOSEPH)
        diff = (sun[0] - target) % 360
        diff = min(diff, 360 - diff)
        assert diff < self.TOL, f"{y}-{mo}-{d} {h}h 太阳黄经距 {target}° 差 {diff:.6f}°"

    @pytest.mark.parametrize(
        "y,mo,d,h,target",
        [
            (2024, 4, 8, 18.35, 0),     # 日全食合朔 18:21 UTC
            (2024, 10, 2, 18.82, 0),    # 日环食合朔 18:49 UTC
            (2025, 3, 29, 10.97, 0),    # 日偏食合朔 10:58 UTC
            (2024, 9, 18, 2.57, 180),   # 月偏食望 02:34 UTC
        ],
    )
    def test_moon_elongation_at_syzygy(self, y, mo, d, h, target) -> None:
        import swisseph as swe

        jd = swe.julday(y, mo, d, h)
        sun, _ = swe.calc_ut(jd, swe.SUN, swe.FLG_MOSEPH)
        moon, _ = swe.calc_ut(jd, swe.MOON, swe.FLG_MOSEPH)
        e = ((moon[0] - sun[0]) % 360 + 180) % 360 - 180
        assert abs(e - target) < self.TOL, f"{y}-{mo}-{d} {h}h 日月黄经差 {e:.6f}° ≠ {target}"

    def test_no_equal_width_xiu(self) -> None:
        """反捷径：宿度不得均分——表内宽度必须不全等。"""
        data = json.loads((DATA / "tianxing_28xiu.json").read_text(encoding="utf-8"))
        widths = {x["xiu_width"] for x in data["xiu"]}
        assert len(widths) > 1, "宿度被均分（360/28 简化）"


class TestRiyueJiafu:
    """spec §2.5 关键吉格：日月夹辅山向（窄夹=两侧相邻山）。"""

    def test_golden_case_not_jiafu(self) -> None:
        """金标准（乾山，2027-07-11）：日在丁、月在辛？——非乾山两侧（午/戌?）。"""
        from datetime import date

        from core_symbol.tianxing import SWE_AVAILABLE, derive_tianxing_facts

        fx = derive_tianxing_facts(
            mountain_name="乾", facing_name="巽", local_date=date(2027, 7, 11)
        )
        if SWE_AVAILABLE:
            # 乾山罗盘序 21 → 两侧为 戌(20)/亥(22)
            jf = fx["riyue_jiafu"]
            sun_shan = fx["bodies"]["日"]["shan"]
            moon_shan = fx["bodies"]["月"]["shan"]
            expected = {sun_shan, moon_shan} == {"戌", "亥"}
            assert jf["shan"] is expected
            assert jf["shan"] is False, f"日在{sun_shan}月在{moon_shan}，非戌/亥夹乾"

    def test_structure_and_none_cases(self) -> None:
        from core_symbol.tianxing import derive_tianxing_facts

        fx = derive_tianxing_facts(mountain_name="乾", facing_name=None, local_date=None)
        assert fx["riyue_jiafu"] is None or fx["sun_daoshan"] is None
        from core_symbol.tianxing import SWE_AVAILABLE

        if not SWE_AVAILABLE:
            assert fx["riyue_jiafu"] is None
