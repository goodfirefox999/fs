"""证据等级（A/B/C）在加载期的硬约束。

Layer 2 把 ``evidence`` 写进规则 YAML 后，"B 级只能进参考层""定义级不得
携带证据等级"等约束必须在 loader 级验证——合成注入测试只能证明引擎行为，
字段拼错/组合非法只有走标准加载器才能抓到。
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from core_rule.errors import DSLValidationError
from core_rule.loader import load_rule

ROOT = Path(__file__).resolve().parents[2]
BASE = yaml.safe_load((ROOT / "core-rule/rules/public/PUB-TIANDE-001.yaml").read_text(encoding="utf-8"))


def _write(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "rule.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def _signed_citation() -> dict:
    return {
        "kind": "classic",
        "source": "测试专用（非古籍）",
        "quote": "测试用原文占位",
        "quote_kind": "原文",
        "juan": "一",
        "pian": "测试篇",
        "verified_by": "pytest",
    }


class TestEvidenceLoader:
    def test_unknown_evidence_field_rejected(self, tmp_path: Path) -> None:
        data = copy.deepcopy(BASE)
        data["evidence"]["typo_field"] = 1
        with pytest.raises(DSLValidationError, match="未知字段"):
            load_rule(_write(tmp_path, data))

    def test_definitional_rule_rejects_evidence(self, tmp_path: Path) -> None:
        data = copy.deepcopy(BASE)
        data.update(
            status="定义级",
            severity="记录",
            hard_veto=False,
            verdict_type=None,
            citation={"kind": "spec", "source": "内核规格", "quote": "关系表条款"},
        )
        with pytest.raises(DSLValidationError, match="定义级规则不使用 evidence"):
            load_rule(_write(tmp_path, data))

    def test_layer_must_be_string(self, tmp_path: Path) -> None:
        data = copy.deepcopy(BASE)
        data["layer"] = 123
        with pytest.raises(DSLValidationError, match="layer 必须是字符串"):
            load_rule(_write(tmp_path, data))

    def test_b_grade_must_be_reference_layer(self, tmp_path: Path) -> None:
        data = copy.deepcopy(BASE)
        data["evidence"] = {
            "grade": "B",
            "source_tier": "secondary_transcription",
            "quote_verified": False,
            "blocking_ruling": None,
        }
        with pytest.raises(DSLValidationError, match="只能进参考层"):
            load_rule(_write(tmp_path, data))

    def test_b_grade_reference_rule_loads(self, tmp_path: Path) -> None:
        data = copy.deepcopy(BASE)
        data.update(
            layer="reference",
            verdict_type="reference",
            engine_eligible=False,
            ineligible_reason="secondary_transcription",
            evidence={
                "grade": "B",
                "source_tier": "secondary_transcription",
                "quote_verified": False,
                "blocking_ruling": None,
            },
        )
        rule = load_rule(_write(tmp_path, data))
        assert rule.evidence is not None and rule.evidence.grade == "B"
        assert rule.evidence.votable is False
        assert rule.engine_eligible is False

    def test_engine_eligible_false_requires_reason(self, tmp_path: Path) -> None:
        data = copy.deepcopy(BASE)
        data["engine_eligible"] = False
        with pytest.raises(DSLValidationError, match="必须带 ineligible_reason"):
            load_rule(_write(tmp_path, data))

    def test_ineligible_reason_on_eligible_rule_rejected(self, tmp_path: Path) -> None:
        data = copy.deepcopy(BASE)
        data["ineligible_reason"] = "day_yuan_undecided"
        with pytest.raises(DSLValidationError, match="状态自相矛盾"):
            load_rule(_write(tmp_path, data))

    def test_signed_rule_cannot_be_engine_ineligible(self, tmp_path: Path) -> None:
        data = copy.deepcopy(BASE)
        data.update(
            status="已考证",
            citation=_signed_citation(),
            engine_eligible=False,
            ineligible_reason="day_yuan_undecided",
        )
        with pytest.raises(DSLValidationError, match="不得用于"):
            load_rule(_write(tmp_path, data))

    def test_assertion_rule_cannot_override_to_definitional(self, tmp_path: Path) -> None:
        data = copy.deepcopy(BASE)
        data["severity_overrides"] = {"public": "记录"}
        with pytest.raises(DSLValidationError, match="不得把断言级规则降为"):
            load_rule(_write(tmp_path, data))
