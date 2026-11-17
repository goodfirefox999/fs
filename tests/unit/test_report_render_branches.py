"""报告渲染的分支覆盖：台账、盘面、共识、无解/稳健/敏感与 JSON。

这些分支大多只在特定输入组合下才出现；用合成对象直接锁定输出，
避免为了覆盖率去构造昂贵且脆弱的完整日课。
"""

from __future__ import annotations

from types import SimpleNamespace

from app_zeri.report import (
    _consensus_block,
    _cosmos_block,
    _fmt_citation,
    _hit_ledger,
    _judgment_rows,
    _school_block,
    consensus_notice,
    ephemeris_notice,
    render_generation_markdown,
    render_json,
    render_manifest_block,
    undetermined_notice,
)
from core_eval.engine import SchoolResult


def _judgment(**overrides):
    base = dict(
        rule_id="R-001",
        category="测试",
        severity="慎用",
        citation={},
        hit_detail="命中说明",
        is_demo=False,
        declared_severity=None,
        evidence_grade_label="C",
        source_status="unverified",
        ineligible_reason=None,
        remedy=None,
        unknown_reason=None,
        participation="判定",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestCitationAndRows:
    def test_citation_formats_juan_and_pian(self) -> None:
        text = _fmt_citation({"source": "协纪", "juan": "三", "pian": "义例", "quote": "原文"})
        assert text == "协纪（卷三·篇义例）：「原文」"

    def test_citation_marks_missing_location(self) -> None:
        assert "卷次待补" in _fmt_citation({"source": "协纪", "quote": "原文"})

    def test_citation_marks_missing_quote(self) -> None:
        assert "原文待补" in _fmt_citation({"source": "协纪"})

    def test_empty_rows_use_placeholder(self) -> None:
        assert _judgment_rows([]) == ["| — | — | — | — |"]


class TestHitLedgerBranches:
    def _res(self, **buckets):
        base = dict(
            vetoes=[], cautions=[], positives=[], structural=[], notes=[],
            controversial=[], demo_hits=[], reference=[],
        )
        base.update(buckets)
        return SimpleNamespace(**base)

    def test_empty_ledger_is_explicit(self) -> None:
        assert _hit_ledger(SimpleNamespace(per_school={})) == ["- 本轮无命中规则。"]

    def test_duplicate_rule_is_rendered_once(self) -> None:
        j = _judgment(rule_id="DUP-001")
        ev = SimpleNamespace(per_school={"sanhe": self._res(vetoes=[j], notes=[j])})
        text = "\n".join(_hit_ledger(ev))
        assert text.count("`DUP-001`") == 1

    def test_declared_severity_and_fallbacks_are_visible(self) -> None:
        j = _judgment(
            rule_id="R-002",
            severity="慎用",
            declared_severity="禁用",
            evidence_grade_label="Z",
            source_status="unknown-source",
        )
        ev = SimpleNamespace(per_school={"sanhe": self._res(cautions=[j])})
        text = "\n".join(_hit_ledger(ev))
        assert "禁用→慎用" in text
        assert "| Z |" in text
        assert "—" in text


class TestSchoolBlockBranches:
    def _res(self, **buckets) -> SchoolResult:
        base = dict(
            school="sanhe",
            state="可用",
            vetoes=[], cautions=[], notes=[], positives=[], unknowns=[],
            structural=[], controversial=[], demo_hits=[], reference=[], not_applicable=[],
        )
        base.update(buckets)
        return SchoolResult(**base)

    def test_all_buckets_are_rendered(self) -> None:
        res = self._res(
            cautions=[_judgment(rule_id="C-001", severity="慎用")],
            controversial=[_judgment(rule_id="Q-001")],
            demo_hits=[_judgment(rule_id="D-001", is_demo=True)],
            reference=[_judgment(rule_id="F-001", ineligible_reason="无原典")],
            not_applicable=[_judgment(rule_id="N-001", remedy="四维山")],
            positives=[_judgment(rule_id="P-001", severity="可用")],
            notes=[_judgment(rule_id="T-001", severity="记录")],
            unknowns=[
                _judgment(
                    rule_id="U-001",
                    severity="未知",
                    unknown_reason="missing_input",
                    remedy="补坐向",
                )
            ],
        )
        text = "\n".join(_school_block(res))
        for rule_id in ("C-001", "Q-001", "D-001", "F-001", "N-001", "P-001", "T-001", "U-001"):
            assert rule_id in text
        assert "缺输入" in text
        assert "四维山" in text


class TestCosmosAndConsensusBranches:
    def test_cosmos_handles_missing_xiu_and_deities(self) -> None:
        text = "\n".join(_cosmos_block({"xiu": {}, "zibai": {}, "jishen": {}}))
        assert "值日星宿：—" in text
        assert "五黄到坐山" in text

    def test_cosmos_renders_present_deities(self) -> None:
        facts = {
            "xiu": {"day": True, "full_name": "角", "qizheng": "木", "yuan": 1, "weekday_consistent": True},
            "zibai": {"day": {"center": 5, "wuhuang_hit_palace": True}},
            "jishen": {
                "tian_de": {"kind": "gong", "target": "乾", "hit": True, "caliber": "gong_union"},
                "yue_de": {"gan": "甲", "hit": True, "he_gan": "己", "he_hit": False},
                "tian_she": {"season": "春", "day_ganzhi": "戊寅", "hit": False},
            },
        }
        text = "\n".join(_cosmos_block(facts))
        assert "天德" in text and "月德" in text and "天赦" in text
        assert "卦位口径" in text

    def test_consensus_without_detail_is_explicit(self) -> None:
        assert "未产出共识明细" in "\n".join(_consensus_block({}))

    def test_consensus_covers_gate_veto_undetermined_and_no_non_voters(self) -> None:
        fso = {
            "_consensus_detail": {
                "threshold": {"min_agree_num": 3, "min_agree_den": 5},
                "consensus_ratio": "1/2",
                "votes": {"favorable": ["sanhe"], "unfavorable": ["zhengwuxing"]},
                "voters": ["sanhe", "zhengwuxing"],
                "voter_evidence_grades": {"sanhe": ["A"], "zhengwuxing": ["C"]},
                "non_voters": [],
                "gate_veto_schools": ["public"],
                "undetermined": {
                    "undetermined_required_count": 1,
                    "pending_ruling_count": 1,
                    "rules": [{"rule_id": "PUB-X", "kind": "pending_ruling", "reason": "待裁定"}],
                },
                "task_kind": "修造",
                "consensus": "mixed",
            }
        }
        text = "\n".join(_consensus_block(fso))
        assert "闸门否决" in text
        assert "未投票：无" in text
        assert "未判定：1 条" in text
        assert "PUB-X" in text

    def test_consensus_lists_non_voters_and_reason_text(self) -> None:
        fso = {
            "_consensus_detail": {
                "consensus_ratio": "0/1",
                "voters": [],
                "votes": {},
                "non_voters": [
                    {"school": "public", "layer": "reject", "reason": "layer_reject"},
                    {"school": "sanhe", "layer": "scoring", "reason": "demo_only_not_voting"},
                ],
            }
        }
        text = "\n".join(_consensus_block(fso))
        assert "闸门层，只否决不计票" in text
        assert "不作为票" in text


class TestNotices:
    def _ev(self, **manifest):
        return SimpleNamespace(manifest=manifest)

    def test_ephemeris_notice_silent_without_second_precision(self) -> None:
        assert ephemeris_notice(self._ev()) == []

    def test_ephemeris_notice_reports_degraded_backend(self) -> None:
        ev = self._ev(
            ephemeris={
                "second_precision_required": True,
                "nearest_jie": "立春",
                "distance_to_jie_s": 0.5,
                "backend": "vsop87",
            }
        )
        text = "\n".join(ephemeris_notice(ev))
        assert "vsop87" in text and "0.5 秒" in text

    def test_undetermined_notice_silent_without_blocks(self) -> None:
        ev = SimpleNamespace(required_rule_ids=["R"], required_blockers=[], required_not_applicable=[])
        assert undetermined_notice(ev) == []
        assert undetermined_notice(SimpleNamespace(required_rule_ids=[])) == []

    def test_undetermined_notice_counts_each_kind(self) -> None:
        ev = SimpleNamespace(
            required_rule_ids=["R1", "R2", "R3"],
            required_blockers=[
                {"kind": "pending_ruling"},
                {"kind": "input_insufficient"},
            ],
            required_not_applicable=[{"rule_id": "R4"}],
        )
        text = "\n".join(undetermined_notice(ev))
        assert "3 条必需规则未判定" in text
        assert "1 条不适用" in text
        assert "1 条待裁定" in text
        assert "1 条输入不足" in text

    def test_manifest_block_with_calendar_config(self) -> None:
        text = "\n".join(render_manifest_block({"a": 1}, {"tz": "Asia/Shanghai"}))
        assert "历法口径" in text
        assert "Asia/Shanghai" in text

    def test_consensus_notice_missing_grade_and_other_conflict(self) -> None:
        ev = self._ev(
            five_school_output={
                "_consensus_detail": {
                    "consensus_ratio": "1/1",
                    "voters": ["sanhe"],
                    "voter_evidence_grades": {},
                    "conflicts": [{"between": ["a", "b"], "type": "OTHER"}],
                }
            }
        )
        text = "\n".join(consensus_notice(ev))
        assert "`sanhe`=unrecorded" in text
        assert "OPPOSITE_VERDICT" not in text


def _gen_result(**overrides):
    ranked = [
        SimpleNamespace(
            evaluation=SimpleNamespace(
                candidate="2027-07-01T09:00",
                state="可用",
                tier="ACCEPTABLE",
                vectors={
                    "hard_fail_count": 0,
                    "strong_avoid_count": 0,
                    "conflict_count": 0,
                    "unknown_count": 0,
                    "positive_count": 1,
                },
            ),
            context={"course": {"bazi": "丁未 丙午 甲子 己巳"}},
        )
    ]
    base = dict(
        ranked=ranked,
        all_evaluations=[],
        total_candidates=1,
        tier_histogram={"ACCEPTABLE": 1},
        disagreement=0.0,
        pareto_size=1,
        no_solution=None,
        no_solution_reason=None,
        sensitivity=None,
        robustness=None,
        relaxed=False,
        spec_output=None,
        usable=ranked,
        publishable=ranked,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class TestGenerationReportBranches:
    def test_all_no_solution_reasons_render(self) -> None:
        for reason, needle in (
            ("no_conclusion_pending_verification", "本次无结论"),
            ("all_rejected", "全部候选被否决层排除"),
            ("constraints_conflict", "约束互斥"),
        ):
            text = render_generation_markdown(_gen_result(no_solution_reason=reason))
            assert needle in text

    def test_no_solution_and_relaxed_are_rendered(self) -> None:
        ns = SimpleNamespace(
            message="无解原因",
            total_candidates=3,
            rejected=3,
            veto_reasons={"PUB-X": 2},
        )
        text = render_generation_markdown(
            _gen_result(no_solution=ns, no_solution_reason="all_rejected", relaxed=True)
        )
        assert "无解说明" in text
        assert "PUB-X" in text
        assert "--relax" in text

    def test_robustness_and_sensitivity_are_rendered(self) -> None:
        rb = SimpleNamespace(
            perturbations=["±1°"],
            radius_deg=1.0,
            robust=["A"],
            sensitive=[{"candidate": "B", "flips": [{"from": "可用", "perturbation": "±1°", "to": "不可用"}]}],
            errors={"probe": "failed"},
            stable_ratio=0.5,
        )
        sens = SimpleNamespace(
            is_stable=False,
            flips=[
                SimpleNamespace(
                    candidate="B",
                    perturbation="caliber",
                    from_state="可用",
                    from_tier="ACCEPTABLE",
                    to_state="不可用",
                    to_tier="REJECTED",
                )
            ],
            errors={"recalc": "failed"},
        )
        text = render_generation_markdown(_gen_result(robustness=rb, sensitivity=sens))
        assert "稳健集" in text and "敏感集" in text
        assert "存在翻转" in text
        assert "probe" in text and "recalc" in text

    def test_render_json_supports_both_result_types(self) -> None:
        class _Jsonable:
            def to_dict(self):
                return {"ok": True}

        assert render_json(_Jsonable()) == '{\n  "ok": true\n}'
        assert '"ok": true' in render_json(_Jsonable())
