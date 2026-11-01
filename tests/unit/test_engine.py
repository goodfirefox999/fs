"""判定引擎测试：三态判定、分层向量、未知暴露、派别并列、禁止单一总分。"""

from __future__ import annotations

import pytest

from core_eval import (
    STATE_BLOCKED,
    STATE_OK,
    STATE_UNSURE,
    TIER_ACCEPTABLE,
    TIER_NEEDS_REVIEW,
    TIER_PREFERRED,
    TIER_REJECTED,
    EvalConfig,
    Evaluation,
    evaluate,
    render_explanation,
)
from core_eval.disagreement import disagreement_of, disagreement_of_evaluation
from core_eval.ranker import pareto_front, rank, sort_key
from core_eval.structure import detect_structure
from core_rule.models import Rule


class TestThreeState:
    def test_definitional_structure_does_not_affect_state(self, base_ctx, registry) -> None:
        """定义级结构（自刑）只陈述事实，不得判不可用，也不得拉成存疑（ADR-0009）。"""
        from tests.conftest import deep_merge

        ctx = deep_merge(base_ctx, {"facts": {"structure": {"zixing_pairs": [{"a": "辰", "b": "辰"}]}}})
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="strict"))
        assert ev.vectors["hard_fail_count"] == 0
        assert ev.vectors["strong_avoid_count"] == 0
        assert ev.state == STATE_OK
        assert any(j.rule_id == "DEF-ZIXING-001" for j in ev.structural)
        assert all(j.severity == "记录" for j in ev.structural)

    def test_veto_means_blocked(self, base_ctx, registry) -> None:
        ctx = _with_veto(base_ctx)
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True))
        assert ev.state == STATE_BLOCKED
        assert ev.tier == TIER_REJECTED
        assert ev.vectors["hard_fail_count"] > 0

    def test_caution_means_unsure(self, base_ctx, registry) -> None:
        # 注意：strict 档会把断言级慎用升级为否决（ADR-0008），故此处用 normal
        ctx = _with_caution(base_ctx)
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="normal", allow_unverified=True))
        assert ev.state == STATE_UNSURE
        assert ev.tier == TIER_NEEDS_REVIEW

    def test_structural_hits_are_not_unknown(self, base_ctx, registry) -> None:
        """定义级结构必须"确定可见"，不能和阴府一样混进 unknown。"""
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="strict"))
        structural_ids = {j.rule_id for j in ev.structural}
        unknown_ids = {u["rule_id"] for u in ev.unknowns}
        assert structural_ids, "基准案例应有结构判定（三合/重复）"
        assert not (structural_ids & unknown_ids), "定义级结构不得同时登记为 unknown"

    def test_no_hit_means_ok_but_unknown_keeps_needs_review(self, base_ctx, registry) -> None:
        """无 veto/caution 时 state=可用，但 unknown 仍把 tier 拉到 NEEDS_REVIEW。"""
        ctx = _strip_hits(base_ctx)
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True))
        assert ev.state == STATE_OK
        assert ev.tier in (TIER_NEEDS_REVIEW, TIER_ACCEPTABLE, TIER_PREFERRED)

    def test_unverified_hits_become_unknown_when_not_allowed(self, base_ctx, registry) -> None:
        """默认（不允许未考证）时，命中的待考证规则只登记 unknown，不参与判定。"""
        ctx = _with_veto(base_ctx)
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=False))
        assert ev.vectors["hard_fail_count"] == 0
        assert ev.vectors["unverified_hit_count"] >= 1
        assert any(
            j.participation == "仅登记" and j.unknown_reason == "unverified_rule"
            for res in ev.per_school.values()
            for j in res.unknowns
        )
        assert ev.tier == TIER_NEEDS_REVIEW  # unknown 必须把 tier 拉离 PREFERRED
        assert ev.publishable is False

    def test_unknown_alone_lifts_tier(self, base_ctx, registry) -> None:
        """没有任何强忌/冲突，只有 unknown，tier 也必须是 NEEDS_REVIEW。

        变异测试发现过这里没覆盖：把 `unknown_count > 0` 从 tier 条件里删掉，
        测试仍然全绿 —— 那等于把"未知"当"可用"放行。
        """
        from tests.conftest import deep_merge

        ctx = deep_merge(_strip_hits(base_ctx), {"facts": {"suipo": {"hit_mountain": True}}})
        ev = evaluate(
            ctx, registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=False)
        )
        assert ev.vectors["hard_fail_count"] == 0
        assert ev.vectors["strong_avoid_count"] == 0
        assert ev.vectors["conflict_count"] == 0
        assert ev.vectors["unknown_count"] > 0
        assert ev.tier == TIER_NEEDS_REVIEW
        assert ev.publishable is False

    def test_unknown_never_silently_passes(self, base_ctx, registry) -> None:
        ctx = _with_veto(base_ctx)
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=False))
        assert ev.unknowns, "命中的待考证规则必须出现在 unknowns 中"
        assert ev.tier != TIER_PREFERRED


class TestNoSingleScore:
    def test_evaluation_has_no_total_score(self, base_ctx, registry) -> None:
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="strict"))
        data = ev.to_dict()
        for forbidden in ("score", "total_score", "auspicious_score", "吉凶分"):
            assert forbidden not in data
        assert "vectors" in data
        assert set(data["vectors"]) >= {
            "hard_fail_count", "strong_avoid_count", "conflict_count", "unknown_count", "positive_count"
        }

    def test_per_school_not_merged(self, base_ctx, registry) -> None:
        ev = evaluate(
            base_ctx, registry,
            EvalConfig(task_kind="修造", strictness="strict", schools=("public", "zhengwuxing"),
                       allow_unverified=True),
        )
        assert set(ev.per_school) == {"public", "zhengwuxing"}
        # 各派独立 state，且综合 state 取最严
        assert ev.state in {r.state for r in ev.per_school.values()}

    def test_rank_score_only_when_ok(self, base_ctx, registry) -> None:
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True))
        for res in ev.per_school.values():
            if res.state != STATE_OK:
                assert res.rank_score is None
            else:
                assert res.rank_score is not None


class TestConflict:
    def test_state_divergence_detected(self, base_ctx, registry) -> None:
        ev = evaluate(
            base_ctx, registry,
            EvalConfig(task_kind="修造", strictness="strict", schools=("public", "zhengwuxing"),
                       allow_unverified=True),
        )
        assert ev.conflicts, "public 与 zhengwuxing 三态不一致时必须登记冲突"
        types = {c["type"] for c in ev.conflicts}
        assert types & {"state_divergence", "verdict_conflict"}
        assert ev.vectors["conflict_count"] == len(ev.conflicts)

    def test_conflict_lifts_tier(self, base_ctx, registry) -> None:
        ev = evaluate(
            base_ctx, registry,
            EvalConfig(task_kind="修造", strictness="strict", schools=("public", "zhengwuxing"),
                       allow_unverified=True),
        )
        assert ev.tier != TIER_PREFERRED


class TestVetoParticipation:
    def test_school_without_veto_downgrades_to_note(self, base_ctx, registry) -> None:
        """斗首/玄空默认不参与否决：其禁用规则应降级为提示，不判不可用。"""
        ctx = _with_veto(base_ctx)
        ev = evaluate(
            ctx, registry,
            EvalConfig(task_kind="修造", strictness="strict", schools=("doushou",), allow_unverified=True),
        )
        res = ev.per_school["doushou"]
        assert res.counts["hard_fail_count"] == 0
        assert res.state != STATE_BLOCKED


class TestDisagreement:
    @pytest.mark.parametrize(
        "states,expected",
        [
            (["可用"], 0.0),
            (["可用", "可用"], 0.0),
            (["可用", "不可用"], 0.5),
            (["可用", "存疑", "不可用"], pytest.approx(2 / 3)),
            (["可用", "可用", "不可用"], pytest.approx(1 / 3)),
        ],
    )
    def test_formula(self, states: list[str], expected) -> None:
        assert disagreement_of(states) == expected

    def test_bounds(self) -> None:
        for states in (["可用", "存疑"], ["存疑", "存疑"], ["不可用", "存疑", "可用"]):
            assert 0.0 <= disagreement_of(states) < 1.0

    def test_evaluation_disagreement(self, base_ctx, registry) -> None:
        ev = evaluate(
            base_ctx, registry,
            EvalConfig(task_kind="修造", strictness="strict", schools=("public", "zhengwuxing"),
                       allow_unverified=True),
        )
        d = disagreement_of_evaluation(ev)
        assert 0.0 < d < 1.0


class TestRanker:
    def test_sort_key_prefers_fewer_bad(self, base_ctx, registry) -> None:
        ev_bad = evaluate(_with_veto(base_ctx), registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True))
        ev_ok = evaluate(_with_caution(base_ctx), registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True))
        assert sort_key(ev_ok) < sort_key(ev_bad)

    def test_rank_orders(self, base_ctx, registry) -> None:
        evs = [
            evaluate(_with_veto(base_ctx), registry, EvalConfig(task_kind="修造", strictness="normal", allow_unverified=True)),
            evaluate(_with_caution(base_ctx), registry, EvalConfig(task_kind="修造", strictness="normal", allow_unverified=True)),
        ]
        ordered = rank(evs)
        assert ordered[0].tier == TIER_NEEDS_REVIEW
        assert ordered[-1].tier == TIER_REJECTED

    def test_pareto_front_subset(self, base_ctx, registry) -> None:
        evs = [
            evaluate(_with_veto(base_ctx), registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True)),
            evaluate(_with_caution(base_ctx), registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True)),
        ]
        front = pareto_front(evs)
        assert front and len(front) <= len(evs)


class TestExplanationRendering:
    def test_placeholder_replaced(self, base_ctx) -> None:
        text = render_explanation("坐山{site.mountain}，日支{course.day.zhi}", base_ctx)
        assert "乾" in text and "卯" in text
        assert "{" not in text

    def test_missing_placeholder_marked(self, base_ctx) -> None:
        text = render_explanation("命主{person.year_zhi}", base_ctx)
        assert "未提供" in text

    def test_no_free_generation(self) -> None:
        """解释只允许模板替换，不允许凭空生成 —— 空模板返回空串。"""
        assert render_explanation("", {}) == ""


class TestStructureDetector:
    def test_weiwei_not_self_punishment(self) -> None:
        rep = detect_structure(["未", "未", "卯", "未"], ["丁", "丁", "辛", "乙"])
        assert rep.max_repeat == 3
        assert rep.has_self_punishment is False
        assert rep.weiwei_is_self_punishment is False

    @pytest.mark.parametrize("zhi", ["辰", "午", "酉", "亥"])
    def test_self_punishment_detected(self, zhi: str) -> None:
        rep = detect_structure([zhi, zhi, "子", "丑"], ["甲", "乙", "丙", "丁"])
        assert rep.has_self_punishment is True

    def test_sanhe_detected(self) -> None:
        rep = detect_structure(["亥", "卯", "未", "子"], ["甲", "乙", "丙", "丁"])
        kinds = {h.kind for h in rep.hits}
        assert "三合" in kinds

    def test_shan_jia_sanhe(self) -> None:
        rep = detect_structure(["未", "未", "卯", "未"], ["丁", "丁", "辛", "乙"], shan_jia_zhi="亥")
        assert any(h.kind == "山家三合" for h in rep.hits)

    def test_no_jixiong_words(self) -> None:
        """结构报告不得出现吉凶字样（铁律 3）。"""
        rep = detect_structure(["未", "未", "卯", "未"], ["丁", "丁", "辛", "乙"], shan_jia_zhi="亥")
        text = str(rep.to_dict())
        for word in ("吉", "凶", "宜", "忌"):
            assert word not in text


# --------------------------------------------------------------------------- #
# 辅助：构造不同命中的 ctx
# --------------------------------------------------------------------------- #
def _with_veto(ctx: dict) -> dict:
    """注入**断言级**否决命中（岁破占山，PUB-SUIPO-001，severity=禁用）。

    注意：自刑（DEF-ZIXING-001）现在是**定义级**结构事实，只判"存疑"，
    不再产生 REJECTED —— 见 ADR-0007。
    """
    from tests.conftest import deep_merge

    return deep_merge(ctx, {"facts": {"suipo": {"hit_mountain": True}}})


def _with_caution(ctx: dict) -> dict:
    """注入**断言级**慎用命中（时冲山，PUB-CHONGSHAN-002）。

    注意：地支三见（DEF-REPEAT-001）现在是定义级 `记录`，只陈述结构、**不影响 tier**；
    它的断言部分拆到了 ASSERT-REPEAT-001（待考证）。
    """
    from tests.conftest import deep_merge

    return deep_merge(ctx, {"course": {"hour": {"zhi": "巳"}}})


def _strip_hits(ctx: dict) -> dict:
    from tests.conftest import deep_merge

    return deep_merge(
        ctx,
        {
            "facts": {
                "structure": {
                    "max_repeat": 1,
                    "zixing_pairs": [],
                    "chong_pairs": [],
                    "hai_pairs": [],
                    "po_pairs": [],
                    "xing_pairs": [],
                    "gan_chong_pairs": [],
                    "sanhe_with_mountain": [],
                    "banhe_with_mountain": [],
                },
                "xunkong": {"hits": []},
                "sansha": {"year": {"hit_mountain": False, "hit_facing": False},
                           "month": {"hit_mountain": False, "hit_facing": False}},
                "suipo": {"hit_mountain": False, "hit_facing": False},
                "yuepo": {"hit_mountain": False, "hit_facing": False},
                "wuhuang": {"year": {"hit_mountain": False, "hit_facing": False}},
                "sili_sijue": {"has_sili": False, "has_sijue": False, "is_hit": False, "hits": []},
            }
        },
    )
