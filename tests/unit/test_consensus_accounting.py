"""共识计票「分账」测试（ADR-0015）：闸门 / 参考层 / 沉默派各自的去处。

为什么要单独测分账
------------------
真实缺陷形态（2026-11-02 发现）：``layer: reference`` 的斗首派不进仲裁，但它的倾向
仍被算进 "favorable"，于是共识比里出现了**没投票的票**。这类错不会让任何断言失败——
报告照样生成、比值照样是个分数，只是数字是假的。

三条分账规则，一条一个用例（缺一条，下次加新 layer 就会漏）：
1. ``reject`` 层：命中只进 ``gate_veto_schools``，不进 ``votes.favorable``，也不进分母；
2. ``reference`` 层：进 ``non_voters``，理由 ``layer_reference``，倾向不得进 favorable；
3. ``scoring`` 层但本轮无判定：进 ``non_voters``，理由 ``no_verdict``，不进分母。

另外锁两条算术不变量：分母恒等于 ``len(voters)``；favorable ⊆ voters。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from core_eval import EvalConfig, evaluate
from core_rule import default_registry

TZ = ZoneInfo("Asia/Shanghai")


def _ctx():
    from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
    from core_time import CalendarConfig

    return build_context(
        course=CourseSpec(dt=datetime(2027, 7, 11, 14, 0, tzinfo=TZ)),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
        person=PersonSpec(),
        cal=CalendarConfig(),
    )


ALL_SCHOOLS = (
    "public", "zhengwuxing", "sanhe", "donggong", "xuankong_dagua", "tianxing", "doushou",
)


def _detail(demo_veto: bool = True, schools: tuple[str, ...] | None = None) -> tuple[dict, object]:
    ev = evaluate(
        _ctx(),
        default_registry(),
        EvalConfig(
            task_kind="修造",
            strictness="strict",
            allow_unverified=True,
            demo_veto=demo_veto,
            schools=schools,
        ),
    )
    return ev.manifest["five_school_output"]["_consensus_detail"], ev


class TestRejectLayer:
    def test_public_is_gate_and_never_votes(self) -> None:
        detail, ev = _detail()
        layers = default_registry().policy.schools
        assert layers["public"].layer == "reject"
        assert "public" not in detail["voters"]
        reasons = {nv["school"]: nv["reason"] for nv in detail["non_voters"]}
        assert reasons["public"] == "layer_reject"

    def test_gate_veto_appears_in_gate_list_only(self) -> None:
        """闸门否决只进 gate_veto_schools，不把自己算成一张反对票。"""
        detail, ev = _detail()
        if "public" not in detail["gate_veto_schools"]:
            # 该日课闸门未命中：本条不成立，但仍要断言两者互斥（不能同时出现）
            assert "public" not in detail["votes"]["unfavorable"]
            return
        assert "public" not in detail["votes"]["unfavorable"], (
            "闸门否决不得同时计入反对票——那会让同一派被记两次"
        )
        assert "public" not in detail["voters"]


class TestReferenceLayer:
    """斗首默认不入路由（layer=reference），必须显式纳入评估才谈得上"未投票"。"""

    def test_doushou_non_voter_with_reason(self) -> None:
        detail, ev = _detail(schools=ALL_SCHOOLS)
        assert default_registry().policy.schools["doushou"].layer == "reference"
        assert "doushou" in ev.per_school, "显式纳入后应出现在参评派里"
        reasons = {nv["school"]: nv["reason"] for nv in detail["non_voters"]}
        assert reasons["doushou"] == "layer_reference"

    def test_reference_tendency_never_counted_as_favorable(self) -> None:
        """核心断言：斗首即使偏吉，也不得出现在 favorable 名单里。"""
        detail, ev = _detail(schools=ALL_SCHOOLS)
        assert "doushou" not in detail["votes"]["favorable"]
        assert "doushou" not in detail["votes"]["unfavorable"]
        assert "doushou" not in detail["voters"]
        _num, den = detail["consensus_ratio"].split("/")
        assert int(den) == len(detail["voters"]), "参考层不得进分母"

    def test_reference_hit_does_not_change_ratio(self) -> None:
        """纳入斗首前后，共识比必须逐字相同（它在场但不投票）。"""
        base, _ = _detail()
        with_ref, _ = _detail(schools=ALL_SCHOOLS)
        assert base["consensus_ratio"] == with_ref["consensus_ratio"]


class TestSilentScoringLayer:
    def test_silent_school_is_non_voter(self) -> None:
        detail, ev = _detail()
        silent = [
            nv
            for nv in detail["non_voters"]
            if nv["reason"] == "no_verdict" and nv["layer"] == "scoring"
        ]
        for nv in silent:
            assert nv["school"] not in detail["voters"]
            res = ev.per_school[nv["school"]]
            assert not (res.vetoes or res.cautions or res.positives), (
                "有判定却被记为沉默派＝分母口径错误"
            )

    def test_denominator_counts_only_scoring_schools_with_verdicts(self) -> None:
        """分母 = 「scoring 层 且 本轮有判定」的派数，一个不多一个不少。"""
        detail, ev = _detail()
        schools = default_registry().policy.schools
        expected = [
            name
            for name, res in ev.per_school.items()
            if schools[name].layer == "scoring" and (res.vetoes or res.cautions or res.positives)
        ]
        _num, den = detail["consensus_ratio"].split("/")
        assert int(den) == len(expected) == len(detail["voters"])


class TestArithmeticInvariants:
    def test_denominator_is_voter_count(self) -> None:
        detail, _ = _detail()
        num, den = detail["consensus_ratio"].split("/")
        assert int(den) == len(detail["voters"])
        assert int(num) == len(detail["votes"]["favorable"])

    def test_favorable_and_unfavorable_partition_voters(self) -> None:
        detail, _ = _detail()
        fav = set(detail["votes"]["favorable"])
        unfav = set(detail["votes"]["unfavorable"])
        voters = set(detail["voters"])
        assert fav <= voters and unfav <= voters
        assert not (fav & unfav)

    def test_all_three_reasons_are_documented(self) -> None:
        """三种未投票原因必须都在报告映射表里有中文解释，否则用户看到裸代码。"""
        from app_zeri.report import _non_voter_reason

        for reason in ("layer_reject", "layer_reference", "no_verdict"):
            text = _non_voter_reason(reason)
            assert text and text != reason, f"{reason} 缺中文解释"
