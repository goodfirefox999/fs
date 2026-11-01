"""Phase 4 正五行规则包测试（评审扩展版 spec §2.1 + §6）。

覆盖：5 条子规则存在性 + 调候分组数据 + 通关 DSL 可解析 + zhengwuxing 派启用。
"""
import json
from pathlib import Path

import pytest
import yaml

from core_rule.loader import load_rule

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "core-rule/config/data"
RULES = ROOT / "core-rule/rules/zhengwuxing"


class TestZwxPackExistence:
    """spec §2.1：五条子规则全部存在于规则库。"""

    EXPECTED = [
        "ZWX-BULONG-001", "ZWX-FUSHAN-001", "ZWX-XIANGSHOU-001",
        "ZWX-TIAOHOU-001", "ZWX-TONGGUAN-001",
    ]

    def test_all_five_rules_exist(self) -> None:
        for rid in self.EXPECTED:
            path = RULES / f"{rid}.yaml"
            assert path.exists(), f"{rid}.yaml 不存在"
            rule = load_rule(path)
            assert rule.school == "zhengwuxing", f"{rid} school 应为 zhengwuxing"
            assert rule.status == "待考证", f"{rid} status 应为待考证"

    def test_zhengwuxing_school_enabled(self, registry) -> None:
        assert registry.policy.schools["zhengwuxing"].enabled, "zhengwuxing 应已启用（Phase 4）"
        assert "zhengwuxing" in registry.policy.route("安葬"), "安葬路由应含 zhengwuxing"


class TestTiaohouData:
    """调候分组数据完整性（zwx_tiaohou_groups.json）。"""

    def test_groups_file_loads(self) -> None:
        data = json.loads((DATA / "zwx_tiaohou_groups.json").read_text(encoding="utf-8"))
        assert "groups" in data
        assert set(data["groups"].keys()) == {"cold", "hot", "warm", "cool"}

    def test_all_12_branches_covered(self) -> None:
        data = json.loads((DATA / "zwx_tiaohou_groups.json").read_text(encoding="utf-8"))
        all_branches = set()
        for g in data["groups"].values():
            all_branches.update(g["branches"])
        assert all_branches == set("子丑寅卯辰巳午未申酉戌亥"), "12 地支必须全部分组"

    def test_conflict_rule_present(self) -> None:
        data = json.loads((DATA / "zwx_tiaohou_groups.json").read_text(encoding="utf-8"))
        assert "conflict_rule" in data
        assert "扶抑" in data["conflict_rule"], "spec 要求调候与扶抑冲突时以扶抑为主"


class TestLuMaGuiRenData:
    """禄马贵人表完整性（正五行与三合共享）。"""

    def test_lu_shen_10_gans(self) -> None:
        data = json.loads((DATA / "lu_ma_gui_ren.json").read_text(encoding="utf-8"))
        assert set(data["lu_shen"].keys()) == set("甲乙丙丁戊己庚辛壬癸"), "10 天干禄神全覆盖"

    def test_gui_ren_10_gans(self) -> None:
        data = json.loads((DATA / "lu_ma_gui_ren.json").read_text(encoding="utf-8"))
        assert set(data["tian_yi_gui_ren"].keys()) == set("甲乙丙丁戊己庚辛壬癸")

    def test_yi_ma_4_groups(self) -> None:
        data = json.loads((DATA / "lu_ma_gui_ren.json").read_text(encoding="utf-8"))
        assert set(data["yi_ma"].keys()) == {"申子辰", "寅午戌", "巳酉丑", "亥卯未"}


class TestTongGuanCondition:
    """通关规则条件可解析。"""

    def test_tongguan_loads(self) -> None:
        rule = load_rule(RULES / "ZWX-TONGGUAN-001.yaml")
        assert rule.condition["fact"] == "facts.structure.gan_count"
        assert rule.condition["op"] == "exists"

    def test_tongguan_book_authenticity_disputed(self) -> None:
        rule = load_rule(RULES / "ZWX-TONGGUAN-001.yaml")
        assert rule.citation.book_authenticity == "disputed", (
            "滴天髓为托名著作，book_authenticity 应标 disputed（伪托考辨）"
        )
