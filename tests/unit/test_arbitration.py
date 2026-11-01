"""仲裁层测试（评审扩展版 spec §4 + §6）。

覆盖：
1. spec §4 输出结构：rejected_dates / scored_dates / consensus_dates
2. spec §6 仲裁金测试：大煞 reject 的日期进入 rejected_dates，
   董公煞贡值日不能覆盖（school_override_attempted 显式标记）
3. spec §2 school_results payload：overall_tendency / score_delta /
   sub_rules（含 source_ref 与 verification status）/ conflict_flags
"""

from __future__ import annotations

from typing import Any

import pytest

from core_eval.arbitration import SHAGONG_CANNOT_OVERRIDE, build_spec_output
from core_eval.engine import (
    ENGINE_VERSION,
    EvalConfig,
    Evaluation,
    Judgment,
    SchoolResult,
    TIER_REJECTED,
    evaluate,
)
from core_rule.loader import Rule

# --------------------------------------------------------------------------- #
# 工厂：最小可用的 Judgment / SchoolResult / Evaluation
# --------------------------------------------------------------------------- #


def _mk_rule(rule_id: str = "DG-DASHA-001", school: str = "donggong") -> Rule:
    return Rule(
        rule_id=rule_id,
        version=1,
        school=school,
        category="大煞 reject（董公派）",
        status="待考证",
        hard_veto=True,
        severity="禁用",
        target="day",
        condition={"fact": "facts.donggong.is_dasha", "op": "eq", "value": True},
        applies_to={},
        score_weight=None,
        citation={"source": "《董公择日要览》", "entry": "金神七煞"},
        explanation="",
        tests=(),
    )


def _mk_judgment(rule_id: str, school: str, severity: str, status: str = "待考证") -> Judgment:
    return Judgment(
        rule_id=rule_id,
        rule_version=1,
        school=school,
        category="大煞",
        status=status,
        severity=severity,
        target="day",
        matched=True,
        participation="判定",
        hit_detail="",
        explanation="",
        citation={"source": "《董公择日要览》", "entry": "金神七煞"},
        params_hash="x",
        declared_severity=severity,
    )


def _mk_school_result(school: str, tendency: str) -> SchoolResult:
    res = SchoolResult(school=school, state="否决" if tendency == "unfavorable" else "可用")
    if tendency == "unfavorable":
        res.vetoes.append(_mk_judgment("DG-DASHA-001", school, "禁用"))
    if tendency == "favorable":
        res.positives.append(_mk_judgment("DG-SANXING-001", school, "可用"))
    if tendency == "caution":
        res.cautions.append(_mk_judgment("DG-GOUCHEN-001", school, "慎用"))
    return res


def _mk_evaluation(
    candidate: str,
    tendencies: dict[str, str],
    *,
    consensus: str = "mixed",
    conflicts: list[dict[str, Any]] | None = None,
) -> Evaluation:
    per_school = {name: _mk_school_result(name, t) for name, t in tendencies.items()}
    return Evaluation(
        candidate=candidate,
        per_school=per_school,
        state="否决",
        tier="rejected",
        vectors={},
        conflicts=[],
        unknowns=[],
        manifest={
            "engine_version": ENGINE_VERSION,
            "five_school_output": {
                name: {
                    "school": name,
                    "overall_tendency": t,
                    "score_delta": 0,
                    "layer": "scoring",
                    "sub_rules": [],
                    "conflict_flags": [],
                }
                for name, t in tendencies.items()
            }
            | {"_consensus": consensus, "_conflicts": conflicts or []},
        },
        config=EvalConfig(task_kind="修造"),
        structural=[],
        required_rule_ids=(),
        blocked_required=[],
    )


# --------------------------------------------------------------------------- #
# spec §4 结构
# --------------------------------------------------------------------------- #


class TestBuildSpecOutput:
    def test_rejected_not_in_scored(self) -> None:
        ev = _mk_evaluation(
            "2027-07-01T00:00:00+08:00",
            {"donggong": "unfavorable", "sanhe": "favorable"},
        )
        ctx = {"facts": {"donggong": {"star": "无"}}}
        out = build_spec_output([(ev, ctx)])
        assert len(out["rejected_dates"]) == 1
        entry = out["rejected_dates"][0]
        assert entry["date"] == ev.candidate
        assert entry["reject_rule"] == "DG-DASHA-001"
        assert "school_override_attempted" not in entry, "非三星值日不标注 override 尝试"
        assert out["scored_dates"] == [], "reject 绝对优先：被拒日期不进评分环节"
        assert out["consensus_dates"] == []

    def test_shagong_cannot_override_marker(self) -> None:
        """spec §6：煞贡值日的大煞日期必须带 override 尝试标记。"""
        for star in ("煞贡", "直星", "人专"):
            ev = _mk_evaluation("2027-07-01T00:00:00+08:00", {"donggong": "unfavorable"})
            ctx = {"facts": {"donggong": {"star": star}}}
            out = build_spec_output([(ev, ctx)])
            entry = out["rejected_dates"][0]
            assert entry["school_override_attempted"] == SHAGONG_CANNOT_OVERRIDE, star

    def test_scored_dates_shape_and_consensus(self) -> None:
        ev = _mk_evaluation(
            "2027-07-02T00:00:00+08:00",
            {"zhengwuxing": "favorable", "sanhe": "favorable", "donggong": "caution",
             "xuankong_dagua": "favorable", "tianxing": "favorable"},
            consensus="favorable",
            conflicts=[{"schools": ["zhengwuxing", "donggong"], "issue": "x"}],
        )
        out = build_spec_output([(ev, {"facts": {}})])
        assert out["rejected_dates"] == []
        s = out["scored_dates"][0]
        assert set(s["school_results"]) == set(ev.manifest["five_school_output"]) - {"_consensus", "_conflicts"}
        assert s["consensus"] == "favorable"
        assert s["conflicts"] == [{"schools": ["zhengwuxing", "donggong"], "issue": "x"}]
        assert out["consensus_dates"] == [{"date": s["date"], "mark": "consensus_favorable"}]

    def test_consensus_dates_exclude_non_favorable(self) -> None:
        ev = _mk_evaluation("2027-07-03T00:00:00+08:00", {"donggong": "caution"}, consensus="mixed")
        out = build_spec_output([(ev, {})])
        assert out["consensus_dates"] == [], "仅三派及以上 favorable 才标记 consensus_favorable"

    def test_spec6_full_flow(self) -> None:
        """spec §6 仲裁金测试完整版：吉星 reject 日与 consensus 日并存。"""
        ev_reject = _mk_evaluation(
            "2027-07-04T00:00:00+08:00",
            {"donggong": "unfavorable", "zhengwuxing": "favorable"},
        )
        ev_ok = _mk_evaluation(
            "2027-07-05T00:00:00+08:00",
            {"zhengwuxing": "favorable", "sanhe": "favorable", "tianxing": "favorable"},
            consensus="favorable",
        )
        ctxs = [
            (ev_reject, {"facts": {"donggong": {"star": "煞贡"}}}),
            (ev_ok, {"facts": {"donggong": {"star": "无"}}}),
        ]
        out = build_spec_output(ctxs)
        assert [e["date"] for e in out["rejected_dates"]] == [ev_reject.candidate]
        assert rejected_scored_disjoint(out)
        assert [c["date"] for c in out["consensus_dates"]] == [ev_ok.candidate]


def rejected_scored_disjoint(out: dict[str, Any]) -> bool:
    """不变量：rejected 与 scored 的日期集合不相交。"""
    rej = {e["date"] for e in out["rejected_dates"]}
    scored = {s["date"] for s in out["scored_dates"]}
    return not (rej & scored)


# --------------------------------------------------------------------------- #
# 引擎集成：真实 evaluate + demo_veto（库内暂无已考证 hard_veto 规则）
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def reg():
    from core_rule import default_registry

    return default_registry()


class TestEngineIntegration:
    def test_school_payload_shape(self, base_ctx, reg) -> None:
        """spec §2 payload：overall_tendency/score_delta/sub_rules/conflict_flags + layer。"""
        cfg = EvalConfig(task_kind="修造", strictness="strict")
        ev = evaluate(base_ctx, reg, cfg)
        fso = ev.manifest["five_school_output"]
        for name, d in fso.items():
            if name.startswith("_"):
                continue
            assert {"school", "overall_tendency", "score_delta", "layer", "sub_rules",
                    "conflict_flags"} <= set(d), name
            assert d["overall_tendency"] in ("favorable", "neutral", "unfavorable")
            for sub in d["sub_rules"]:
                assert {"rule_id", "verdict", "status", "source_ref", "bucket",
                        "score_delta"} <= set(sub), sub
                assert sub["source_ref"]["source"], "每条规则必须带 source_ref（元指令 3）"
                assert sub["status"], "每条规则必须带 verification status（元指令 3）"
        assert fso["public"]["layer"] == "reject", "公共大煞层 layer=reject（policy loader 修复）"
        assert "_consensus" in fso and "_conflicts" in fso

    def test_dasha_reject_with_shagong(self, base_ctx, reg) -> None:
        """spec §6：大煞 reject + 煞贡值日 → rejected_dates + override 标记。"""
        from tests.conftest import deep_merge

        ctx = deep_merge(base_ctx, {
            "facts": {"donggong": {"is_dasha": True, "star": "煞贡"}},
        })
        cfg = EvalConfig(
            task_kind="修造", strictness="strict",
            allow_unverified=True, demo_veto=True,  # 联调例外：未考证规则按声明严重度路由
        )
        ev = evaluate(ctx, reg, cfg)
        assert ev.tier == TIER_REJECTED, "大煞命中（demo 路由）→ rejected"
        out = build_spec_output([(ev, ctx)])
        assert len(out["rejected_dates"]) == 1
        entry = out["rejected_dates"][0]
        assert entry["school_override_attempted"] == SHAGONG_CANNOT_OVERRIDE, (
            "煞贡不能推翻 Layer 3 reject——必须显式标注"
        )
        assert rejected_scored_disjoint(out)

    def test_sansha_reject_with_zhengwuxing_favorable(self, base_ctx, reg) -> None:
        """spec §6 仲裁金测试（字面场景）：正五行 favorable + 三煞 reject
        → rejected_dates，董公吉星（直星）不能覆盖 Layer 3。"""
        from tests.conftest import deep_merge

        ctx = deep_merge(base_ctx, {
            "facts": {
                "sansha": {"year": {"hit_mountain": True}},      # 三煞占山（Layer 3）
                "donggong": {"star": "直星"},                    # 董公吉星值日
                "tongguan": {"conflicts": [{"a": "金", "b": "木"}]},  # 正五行通关命中 → favorable
            },
        })
        cfg = EvalConfig(
            task_kind="修造", strictness="strict",
            allow_unverified=True, demo_veto=True,
        )
        ev = evaluate(ctx, reg, cfg)
        assert ev.tier == TIER_REJECTED, "三煞占山 → Layer 3 reject"
        fso = ev.manifest["five_school_output"]
        assert fso["zhengwuxing"]["overall_tendency"] == "favorable", (
            "通关命中（演示路由按声明可用）→ 正五行 favorable"
        )
        out = build_spec_output([(ev, ctx)])
        entry = out["rejected_dates"][0]
        assert "PUB-SANSHA-001" in entry["reject_rules"], entry["reject_rules"]
        assert entry["school_override_attempted"] == SHAGONG_CANNOT_OVERRIDE, (
            "直星值日不能推翻三煞 reject——必须显式标注"
        )
        assert rejected_scored_disjoint(out)
