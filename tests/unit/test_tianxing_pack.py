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
