"""Phase 6 董公规则包测试（评审扩展版 spec §2.3 + §6）。"""
import json
from pathlib import Path

import pytest

from core_rule.loader import load_rule

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "core-rule/config/data"
RULES = ROOT / "core-rule/rules/donggong"


class TestDongGongPackExistence:
    EXPECTED = [
        "DG-JINSHEN-001", "DG-SANXING-001", "DG-DASHA-001",
        "DG-GOUCHEN-001", "DG-JIANCHU-001",
    ]

    def test_all_five_rules_exist(self) -> None:
        for rid in self.EXPECTED:
            path = RULES / f"{rid}.yaml"
            assert path.exists(), f"{rid}.yaml 不存在"
            rule = load_rule(path)
            assert rule.school == "donggong"

    def test_donggong_enabled_with_veto(self, registry) -> None:
        assert registry.policy.schools["donggong"].enabled
        assert registry.policy.schools["donggong"].participates_in_veto
        assert "donggong" in registry.policy.route("安葬")


class TestRejectRules:
    """金神七煞和大煞 reject 规则必须是 hard_veto（Layer 3 对接）。"""

    def test_jinshen_is_reject(self) -> None:
        rule = load_rule(RULES / "DG-JINSHEN-001.yaml")
        assert rule.hard_veto is True, "金神七煞必须 hard_veto=true（Layer 3 reject）"
        assert rule.severity == "禁用"

    def test_dasha_is_reject(self) -> None:
        rule = load_rule(RULES / "DG-DASHA-001.yaml")
        assert rule.hard_veto is True, "大煞必须 hard_veto=true（Layer 3 reject）"
        assert rule.severity == "禁用"


class TestSanxingData:
    """三星值日表 60 甲子完整性（spec：不得口诀近似）。"""

    def test_60_jiazi_complete(self) -> None:
        data = json.loads((DATA / "donggong_sanxing_60jiazi.json").read_text(encoding="utf-8"))
        days = data["days"]
        assert len(days) == 60, f"三星值日表必须 60 条，实际 {len(days)}"
        # 60 甲子 = 10 干 × 12 支中阴阳性配对的 60 个组合（非全部 120 个）
        GAN = "甲乙丙丁戊己庚辛壬癸"
        ZHI = "子丑寅卯辰巳午未申酉戌亥"
        valid_jz = {GAN[i] + ZHI[j] for i in range(10) for j in range(12) if (i + j) % 2 == 0}
        assert len(valid_jz) == 60
        assert set(days.keys()) == valid_jz, (
            f"60 甲子键不匹配：缺 {valid_jz - set(days.keys())}，多 {set(days.keys()) - valid_jz}"
        )
        assert set(days.values()) <= {"煞贡", "直星", "人专"}


class TestSanxingDataIntegrity:
    """固定三循环表不随月建变化，与三星起例不符（2026-11-03 评审登记）。

    修正前**所有**三星命中都不可信，不只是未月甲午；规则以 ``data_integrity: broken``
    显式声明，lint 的 ``data_integrity_broken`` 组逐轮回显。
    """

    def test_rule_declares_broken_data(self) -> None:
        rule = load_rule(RULES / "DG-SANXING-001.yaml")
        assert rule.raw.get("data_integrity") == "broken"
        assert rule.status == "待考证"
        note = rule.raw.get("data_integrity_note") or ""
        assert "月建" in note, "数据缺陷说明必须写明起例按月建分组"
        assert "全年" in note, "影响面必须写明是全年所有判定，而非个别日期"

    def test_broken_data_cannot_be_verified(self) -> None:
        for path in sorted((ROOT / "core-rule/rules").rglob("*.yaml")):
            rule = load_rule(path)
            if (rule.raw or {}).get("data_integrity") == "broken":
                assert rule.status not in ("已考证", "定义级"), (
                    f"{rule.rule_id}: data_integrity=broken 不得标 {rule.status}"
                )


class TestDashaData:
    """大煞 reject 数据完整性。"""

    def test_shousi_12_months(self) -> None:
        data = json.loads((DATA / "donggong_dasha_reject.json").read_text(encoding="utf-8"))
        by_month = data["shou_si"]["by_month"]
        assert len(by_month) == 12, "受死日必须覆盖 12 月支"

    def test_sifei_4_seasons(self) -> None:
        data = json.loads((DATA / "donggong_dasha_reject.json").read_text(encoding="utf-8"))
        assert set(data["si_fei"]["by_season"].keys()) == {"spring", "summer", "autumn", "winter"}

    def test_shie_by_year_stem(self) -> None:
        data = json.loads((DATA / "donggong_dasha_reject.json").read_text(encoding="utf-8"))
        stems = set(data["shi_e_da_bai"]["by_year_stem"].keys())
        assert stems == set("甲乙丙丁戊己庚辛壬癸"), "十恶大败按 10 年干全覆盖"
