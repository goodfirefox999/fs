"""Phase 5 三合规则包测试（评审扩展版 spec §2.2 + §6）。"""
import json
from pathlib import Path

import pytest

from core_rule.loader import load_rule

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "core-rule/config/data"
RULES = ROOT / "core-rule/rules/sanhe"


class TestSanhePackExistence:
    EXPECTED = [
        "SH-SANHEJU-001", "SH-LIUHE-001",
        "SH-LUMAGUIREN-001", "SH-CHONGSHAN-MARKER-001",
    ]

    def test_all_four_rules_exist(self) -> None:
        for rid in self.EXPECTED:
            path = RULES / f"{rid}.yaml"
            assert path.exists(), f"{rid}.yaml 不存在"
            rule = load_rule(path)
            assert rule.school == "sanhe", f"{rid} school 应为 sanhe"

    def test_sanhe_school_enabled(self, registry) -> None:
        assert registry.policy.schools["sanhe"].enabled, "sanhe 应已启用（Phase 5）"
        assert "sanhe" in registry.policy.route("安葬"), "安葬路由应含 sanhe"


class TestLuMaGuiRen24Shan:
    """24 山禄马贵人到方速查表完整性。"""

    def test_24shan_lu_shen(self) -> None:
        data = json.loads((DATA / "sanhe_lu_ma_gui_ren_24shan.json").read_text(encoding="utf-8"))
        assert len(data["lu_shen_to_shan"]) == 10, "10 天干禄神"

    def test_24shan_gui_ren_includes_4corners(self) -> None:
        data = json.loads((DATA / "sanhe_lu_ma_gui_ren_24shan.json").read_text(encoding="utf-8"))
        gui = data["gui_ren_to_shan"]
        # 四维卦山（乾坤艮巽）必须在贵人表中（spec：乾纳甲壬，坤纳乙癸，艮纳丙，巽纳辛）
        for corner in ("乾", "坤", "艮", "巽"):
            assert corner in gui, f"四维卦山 {corner} 缺贵人条目"

    def test_yi_ma_4_groups(self) -> None:
        data = json.loads((DATA / "sanhe_lu_ma_gui_ren_24shan.json").read_text(encoding="utf-8"))
        assert set(data["yi_ma_to_shan"].keys()) == {"申子辰", "寅午戌", "巳酉丑", "亥卯未"}

    def test_shared_with_zwx(self) -> None:
        """三合与正五行共享禄马贵人表——两个 JSON 的禄神表必须一致。"""
        zwx = json.loads((DATA / "lu_ma_gui_ren.json").read_text(encoding="utf-8"))
        sh = json.loads((DATA / "sanhe_lu_ma_gui_ren_24shan.json").read_text(encoding="utf-8"))
        assert zwx["lu_shen"] == sh["lu_shen_to_shan"], "禄神表必须一致（spec：共享表）"


class TestChongshanMarker:
    def test_marker_severity(self) -> None:
        rule = load_rule(RULES / "SH-CHONGSHAN-MARKER-001.yaml")
        assert rule.severity == "慎用", "标记规则 severity 应为慎用（不参与否决/tier 但非定义级）"
        assert rule.hard_veto is False, "标记规则不得为硬否决"
