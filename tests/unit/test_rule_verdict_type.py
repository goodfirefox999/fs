"""判定类型（verdict_type / layer / engine_eligible）契约测试（C 第一批）。

为什么单独测"字段契约"
--------------------
这套字段的价值不在"能读"，而在**读错就报错**：

- ``engine_eligible=false`` 却没理由 → 等于静默降级，报告无法解释"这条为什么没影响结论"；
- ``layer=reference`` 却还能计分 → "参考层"变成自欺；
- 已考证规则躲在参考层 → 用已确定的证据规避判定，方向反了。

前三条在 loader / lint 层拒绝，后一条在 lint 层拒绝。本文件锁住这四条边界，
外加 Phase 11 十条规则的标注表（防止迁移时被随手改成默认值）。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml
from core_rule import default_registry
from core_rule.errors import DSLValidationError
from core_rule.loader import load_rule

_TZ = ZoneInfo("Asia/Shanghai")

_BASE = {
    "api_version": 1,
    "rule_id": "PUB-TEST-001",
    "version": 1,
    "school": "public",
    "category": "测试",
    "status": "待考证",
    "hard_veto": False,
    "severity": "慎用",
    "target": "day",
    "applies_to": {"task_kinds": [], "node_kinds": [], "strictness_min": "normal"},
    "condition": {"fact": "facts.xiu.day", "op": "in", "value": ["角"]},
    "score_weight": None,
    "citation": {
        "kind": "classic", "source": "《测试》", "edition": None, "juan": None, "pian": None,
        "entry": None, "quote_kind": None, "quote": None, "url_or_path": None,
        "verified_by": None, "verified_at": None, "confidence": "低",
    },
    "tests": ["RT-PUB-TEST-001-HIT", "RT-PUB-TEST-001-MISS"],
    "explanation": "测试规则。",
    "supersedes": None,
    "notes": None,
}


def _load(tmp_path: Path, **overrides) -> object:
    data = {**_BASE, **overrides}
    path = tmp_path / f"{data['rule_id']}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return load_rule(path)


class TestLoaderContract:
    def test_defaults_are_backward_compatible(self, tmp_path: Path) -> None:
        """未标注的老规则必须原样加载（迁移期不许一刀切）。"""
        rule = _load(tmp_path)
        assert rule.verdict_type is None
        assert rule.layer is None
        assert rule.engine_eligible is True
        assert rule.ineligible_reason is None

    def test_effective_verdict_type_inferred(self, tmp_path: Path) -> None:
        """未标注 → unspecified（**不猜 vote**）；硬否定仍推断为 gate。"""
        rule = _load(tmp_path)
        assert rule.effective_verdict_type == "unspecified"
        gate = _load(tmp_path, rule_id="PUB-TEST-002", hard_veto=True, severity="禁用")
        assert gate.effective_verdict_type == "gate", "硬否定按定义只能是闸门，可推断"
        explicit = _load(tmp_path, rule_id="PUB-TEST-003", verdict_type="reference")
        assert explicit.effective_verdict_type == "reference"

    def test_explicit_unspecified_is_rejected(self, tmp_path: Path) -> None:
        """不许把待办写成结论：显式 'unspecified' 一律拒绝。"""
        with pytest.raises(DSLValidationError, match="不接受显式"):
            _load(tmp_path, verdict_type="unspecified")

    def test_invalid_verdict_type_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DSLValidationError, match="verdict_type"):
            _load(tmp_path, verdict_type="maybe")

    def test_ineligible_requires_reason(self, tmp_path: Path) -> None:
        with pytest.raises(DSLValidationError, match="ineligible_reason"):
            _load(tmp_path, engine_eligible=False)

    def test_reason_without_ineligible_is_contradiction(self, tmp_path: Path) -> None:
        with pytest.raises(DSLValidationError, match="自相矛盾"):
            _load(tmp_path, ineligible_reason="whatever")

    def test_ineligible_rejected_for_verified(self, tmp_path: Path) -> None:
        """已考证不得躲进参考层：那等于用确定证据规避判定。"""
        citation = {
            **_BASE["citation"],
            "quote_kind": "原文",
            "juan": "卷一",
            "quote": "测试用引文（仅用于触发 loader 的签名校验路径）",
            "verified_by": "测试",
            "verified_at": "2026-11-02",
        }
        with pytest.raises(DSLValidationError, match="不得用于"):
            _load(
                tmp_path,
                status="已考证",
                citation=citation,
                engine_eligible=False,
                ineligible_reason="x",
            )

    def test_full_annotation_roundtrip(self, tmp_path: Path) -> None:
        rule = _load(
            tmp_path,
            verdict_type="gate",
            layer="reference",
            engine_eligible=False,
            ineligible_reason="day_yuan_undecided",
        )
        assert (rule.verdict_type, rule.layer, rule.engine_eligible, rule.ineligible_reason) == (
            "gate", "reference", False, "day_yuan_undecided",
        )
        assert rule.to_dict()["engine_eligible"] is False
        assert rule.to_dict()["ineligible_reason"] == "day_yuan_undecided"


class TestPhase11Annotations:
    """Phase 11 十条规则的第一批标注（第二批批量迁移前必须保持）。"""

    EXPECTED = {
        "PUB-ZIBAI-MONTH-001": ("gate", None, True, None),
        "PUB-ZIBAI-DAY-001": ("gate", "reference", False, "day_yuan_undecided"),
        "PUB-ZIBAI-HOUR-001": ("gate", "reference", False, "day_yuan_undecided"),
        "PUB-ZIBAI-JI-001": ("reference", "reference", False, "no_primary_source_four_auspicious"),
        "PUB-XIU-XIONG-001": ("reference", "reference", False, "coarse_label_no_primary_source"),
        "PUB-XIU-JI-001": ("reference", "reference", False, "coarse_label_no_primary_source"),
        "PUB-TIANDE-001": ("vote", None, True, None),
        "PUB-YUEDE-001": ("vote", None, True, None),
        "PUB-YUEDE-HE-001": ("vote", None, True, None),
        "PUB-TIANSHE-001": ("vote", None, True, None),
    }

    def test_table(self) -> None:
        rs = default_registry().ruleset
        for rid, expected in self.EXPECTED.items():
            rule = rs.by_id.get(rid)
            assert rule is not None, rid
            got = (rule.verdict_type, rule.layer, rule.engine_eligible, rule.ineligible_reason)
            assert got == expected, f"{rid}: {got} != {expected}"

    def test_reference_layer_never_eligible(self) -> None:
        """全局不变式：任何 layer=reference 的规则都不得 engine_eligible。"""
        rs = default_registry().ruleset
        bad = [r.rule_id for r in rs.rules if r.layer == "reference" and r.engine_eligible]
        assert bad == []

    def test_ineligible_never_in_required_set(self) -> None:
        reg = default_registry()
        required = set(reg.required_rules.all_rule_ids())
        bad = [r.rule_id for r in reg.ruleset.rules if not r.engine_eligible and r.rule_id in required]
        assert bad == [], "参考层规则进必需集会让 publishable 永久 false"


class TestReferenceRouting:
    """参考层命中必须"看得见、不算数"。"""

    def _ctx(self, hit: bool) -> dict:
        from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
        from core_time import CalendarConfig

        from tests.conftest import deep_merge

        ctx = build_context(
            course=CourseSpec(dt=datetime(2027, 7, 11, 14, 0, tzinfo=_TZ)),
            site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
            person=PersonSpec(),
            cal=CalendarConfig(),
        )
        # 值宿规则已标 reference：用哨兵切换命中，检验"只渲染不计分"
        return deep_merge(ctx, {"facts": {"xiu": {"day": "角" if hit else "__none__"}}})

    def _eval(self, ctx: dict):
        from core_eval import EvalConfig, evaluate

        return evaluate(
            ctx,
            default_registry(),
            EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True, demo_veto=True),
        )

    def test_reference_hit_visible_and_inert(self) -> None:
        off, on = self._eval(self._ctx(False)), self._eval(self._ctx(True))
        ref_ids = [j.rule_id for res in on.per_school.values() for j in res.reference]
        assert "PUB-XIU-JI-001" in ref_ids
        assert (on.state, on.tier, on.publishable) == (off.state, off.tier, off.publishable)
        assert on.vectors == off.vectors

    def test_reference_hit_not_in_strength_buckets(self) -> None:
        on = self._eval(self._ctx(True))
        for school, res in on.per_school.items():
            for bucket in ("vetoes", "cautions", "positives", "unknowns", "structural", "demo_hits"):
                ids = [j.rule_id for j in (getattr(res, bucket) or [])]
                assert "PUB-XIU-JI-001" not in ids, f"参考层规则泄漏进 {school}.{bucket}"


class TestUnlabeledReportSection:
    """「未归类」必须在报告里可见——它是待办队列，不是内部细节。"""

    def _text(self) -> str:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from app_zeri.report import render_markdown
        from app_zeri.schemas import PersonSpec, SiteSpec, TaskSpec
        from app_zeri.verifier import verify

        result = verify(
            dt=datetime(2027, 7, 11, 14, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
            site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
            person=PersonSpec(),
            allow_unverified=True,
        )
        return render_markdown(result)

    def test_section_present_with_count(self) -> None:
        text = self._text()
        assert "## 未归类规则" in text
        assert "本次评估涉及" in text

    def test_caveat_present(self) -> None:
        text = self._text()
        assert "未归类 ≠ 投票" in text

    def test_labeled_rule_not_listed_as_unlabeled(self) -> None:
        """已标注的规则不得出现在未归类清单里（否则清单会自我矛盾）。"""
        text = self._text()
        start = text.find("## 未归类规则")
        end = text.find("\n## ", start + 5)
        section = text[start:end if end > 0 else len(text)]
        for rid in ("PUB-XIU-XIONG-001", "PUB-TIANDE-001", "PUB-ZIBAI-MONTH-001"):
            assert f"`{rid}`" not in section, f"{rid} 已标注却出现在未归类清单"
