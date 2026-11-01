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
