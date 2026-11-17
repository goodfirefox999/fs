"""共识置信度与未判定名单（2026-11-04 第四层）。

要守的不是"能跑"，而是四件事：

1. 每张票都能回溯证据等级：``voter_evidence_grades`` 的键恰好等于 voters，
   且没有"未登记等级"静默冒充 A；
2. 每个未投票派都有 reason + 中文 detail，不能只给裸代码；
3. 主结论必须写明必需集未判定计数（证据不足/待裁定/待签名/输入不足/不适用），
   否则读者会把"没判"读成"判了且通过"；
4. 文献正当性有争议的派别（斗首）票面永远不能是 A/B——即使算法跑通、
   即使将来升为投票派，也只能是 ``disputed``；报告须同步显示提示。
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app_zeri.report import consensus_notice, undetermined_notice
from core_eval import EvalConfig, evaluate
from core_eval.engine import _voter_grade_labels
from core_rule import default_registry
from core_rule.models import Evidence


def _ctx():
    from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
    from core_time import CalendarConfig

    return build_context(
        course=CourseSpec(dt=datetime(2027, 7, 11, 14, 0, tzinfo=ZoneInfo("Asia/Shanghai"))),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
        person=PersonSpec(),
        cal=CalendarConfig(),
    )


def _evaluate(*, demo_veto: bool = False):
    return evaluate(
        _ctx(),
        default_registry(),
        EvalConfig(
            task_kind="修造",
            strictness="strict",
            allow_unverified=True,
            demo_veto=demo_veto,
        ),
    )


def _detail(ev) -> dict:
    return ev.manifest["five_school_output"]["_consensus_detail"]


class TestVoterEvidenceGrades:
    def test_keys_partition_voters_and_never_empty(self) -> None:
        detail = _detail(_evaluate(demo_veto=True))
        assert detail["voters"], "样本需要至少一张票，否则本条无意义"
        assert set(detail["voter_evidence_grades"]) == set(detail["voters"])
        for school, grades in detail["voter_evidence_grades"].items():
            assert grades, f"{school} 的票没有任何证据等级"

    def test_demo_votes_are_grade_c_not_a(self) -> None:
        """演示票来自未考证规则：等级必须显式是 C，不得静默升成 A。"""
        detail = _detail(_evaluate(demo_veto=True))
        assert all(grades == ["C"] for grades in detail["voter_evidence_grades"].values())

    def test_zero_voters_has_empty_grades(self) -> None:
        detail = _detail(_evaluate(demo_veto=False))
        assert detail["voters"] == []
        assert detail["voter_evidence_grades"] == {}


class TestNonVoterDetails:
    def test_every_non_voter_has_reason_and_detail(self) -> None:
        detail = _detail(_evaluate())
        assert detail["non_voters"]
        for nv in detail["non_voters"]:
            assert nv["reason"], nv
            assert nv["detail"], f"{nv['school']} 缺中文 detail"
            assert nv["detail"] != nv["reason"]


class TestUndeterminedList:
    def test_counts_are_internally_consistent(self) -> None:
        ev = _evaluate()
        detail = _detail(ev)["undetermined"]
        kinds = (
            "evidence_insufficient_count",
            "input_insufficient_count",
            "pending_ruling_count",
            "pending_verification_count",
        )
        blocked = sum(detail[key] for key in kinds)
        assert blocked == len(ev.required_blockers), "分类计数之和必须等于阻塞规则数"
        assert detail["undetermined_required_count"] == (
            len(ev.required_blockers) + len(ev.required_not_applicable)
        )
        assert len(detail["rules"]) == detail["undetermined_required_count"]
        assert detail["required_total"] >= detail["undetermined_required_count"]

    def test_rules_carry_actionable_kind(self) -> None:
        detail = _detail(_evaluate())["undetermined"]
        for item in detail["rules"]:
            assert item["rule_id"] and item["kind"] and item["reason"], item

    def test_notice_states_count_and_scope(self) -> None:
        ev = _evaluate()
        text = "\n".join(undetermined_notice(ev))
        detail = _detail(ev)["undetermined"]
        assert (
            f"本次评估中 {detail['undetermined_required_count']} 条必需规则未判定" in text
        )
        assert f"{detail['evidence_insufficient_count']} 条证据不足" in text
        assert f"{detail['not_applicable_count']} 条不适用" in text
        assert "共识比仅反映已判定规则" in text

    def test_no_required_set_emits_nothing(self) -> None:
        ev = SimpleNamespace(required_rule_ids=(), required_blockers=[], required_not_applicable=[])
        assert undetermined_notice(ev) == []


class TestEvidenceLabel:
    def test_grade_a_label(self) -> None:
        from core_eval import Judgment

        j = Judgment(
            rule_id="X",
            rule_version=1,
            school="s",
            category="c",
            status="已考证",
            severity="慎用",
            target="day",
            matched=True,
            participation="判定",
            hit_detail="",
            explanation="",
            citation={},
            params_hash="",
            evidence_grade="A",
        )
        assert j.evidence_grade_label == "A"

    def test_missing_grade_is_explicit(self) -> None:
        from core_eval import Judgment

        base = dict(
            rule_id="X",
            rule_version=1,
            school="s",
            category="c",
            status="待考证",
            severity="慎用",
            target="day",
            matched=True,
            participation="演示",
            hit_detail="",
            explanation="",
            citation={},
            params_hash="",
        )
        assert Judgment(**base).evidence_grade_label == "unrecorded"
        assert Judgment(**base, definitional=True).evidence_grade_label == "definitional"

    def test_evidence_model_keeps_grade_binding(self) -> None:
        """A 级必须 primary_scan；B/C 不得声称逐字核对（层二约束不得回退）。"""
        assert Evidence(grade="A", source_tier="primary_scan", quote_verified=True).votable
        for bad in (
            {"grade": "B", "source_tier": "primary_scan"},
            {"grade": "B", "source_tier": "secondary_transcription", "quote_verified": True},
        ):
            try:
                Evidence(**bad)
            except ValueError:
                continue
            raise AssertionError(f"应拒绝非法 evidence：{bad}")


def _vote(label: str, participation: str = "判定") -> SimpleNamespace:
    return SimpleNamespace(evidence_grade_label=label, participation=participation)


def _school(*votes: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(vetoes=list(votes), cautions=[], positives=[])


class TestDisputedLiteratureGrade:
    """斗首的票面等级：算法可跑 ≠ 证据可用。"""

    def test_grade_a_vote_is_downgraded_to_disputed(self) -> None:
        grades = _voter_grade_labels("doushou", _school(_vote("A")))
        assert grades == ["disputed"], "斗首票不得标 A/B，即使规则 evidence 标 A"

    def test_mixed_grades_keep_actual_but_add_disputed(self) -> None:
        assert _voter_grade_labels("doushou", _school(_vote("C"))) == ["C", "disputed"]

    def test_non_voting_hits_do_not_create_grades(self) -> None:
        res = _school(_vote("A", participation="未判定"))
        assert _voter_grade_labels("doushou", res) == []

    def test_xuankong_keeps_actual_grade(self) -> None:
        """玄空缺的是一手原典，不是文献伪托；等级按实际标注，不硬改 disputed。"""
        assert _voter_grade_labels("xuankong_dagua", _school(_vote("C"))) == ["C"]


def _detail_ev(detail: dict | None) -> SimpleNamespace:
    fso = {} if detail is None else {"_consensus_detail": detail}
    return SimpleNamespace(manifest={"five_school_output": fso})


class TestConsensusNotice:
    """主结论区的共识摘要：有票才出现，且必须带等级与相反意见。"""

    def _detail(self, **overrides) -> dict:
        detail = {
            "consensus": "favorable",
            "consensus_ratio": "1/2",
            "voters": ["sanhe", "zhengwuxing"],
            "voter_evidence_grades": {"sanhe": ["A"], "zhengwuxing": ["C"]},
            "votes": {"favorable": ["sanhe"], "unfavorable": ["zhengwuxing"]},
            "conflicts": [
                {
                    "between": ["sanhe", "zhengwuxing"],
                    "type": "OPPOSITE_VERDICT",
                    "detail": "sanhe=favorable vs zhengwuxing=unfavorable",
                }
            ],
        }
        detail.update(overrides)
        return detail

    def test_no_voters_emits_nothing(self) -> None:
        """0/0 由 zero_voter_notice 负责，这里不得重复成"有共识"。"""
        assert consensus_notice(_detail_ev(self._detail(voters=[]))) == []

    def test_shows_ratio_voters_and_each_grade(self) -> None:
        text = "\n".join(consensus_notice(_detail_ev(self._detail())))
        assert "共识 1/2" in text
        assert "参与投票 2 派" in text
        assert "`sanhe`=A" in text
        assert "`zhengwuxing`=C" in text

    def test_opposite_verdict_is_highlighted_not_resolved(self) -> None:
        text = "\n".join(consensus_notice(_detail_ev(self._detail())))
        assert "OPPOSITE_VERDICT" in text
        assert "sanhe vs zhengwuxing" in text
        assert "系统不自动裁决" in text

    def test_doushou_voter_triggers_literature_warning(self) -> None:
        detail = self._detail(
            voters=["doushou"],
            voter_evidence_grades={"doushou": ["disputed"]},
            votes={"favorable": ["doushou"], "unfavorable": []},
            conflicts=[],
        )
        text = "\n".join(consensus_notice(_detail_ev(detail)))
        assert "文献正当性提示" in text
        assert "斗首结果仅作参考" in text
        assert "协纪辨方书卷三十六" in text
        assert "不构成 A 级证据" in text

    def test_xuankong_voter_triggers_source_warning(self) -> None:
        detail = self._detail(
            voters=["xuankong_dagua"],
            voter_evidence_grades={"xuankong_dagua": ["C"]},
            votes={"favorable": ["xuankong_dagua"], "unfavorable": []},
            conflicts=[],
        )
        text = "\n".join(consensus_notice(_detail_ev(detail)))
        assert "原典缺失提示" in text
        assert "primary_source_missing" in text


class TestConsensusConflicts:
    """共识冲突必须是机器可读的 typed 结构，而不是一句自然语言。"""

    def test_real_eval_conflicts_are_typed_pairs(self) -> None:
        detail = _detail(_evaluate(demo_veto=True))
        conflicts = detail["conflicts"]
        assert conflicts, "样本需要至少一组方向相反的派别"
        for item in conflicts:
            assert set(item) == {"between", "type", "detail"}, item
            assert item["type"] == "OPPOSITE_VERDICT"
            assert len(item["between"]) == 2
            assert item["detail"]

    def test_conflict_pairs_match_opposite_tendencies(self) -> None:
        ev = _evaluate(demo_veto=True)
        detail = _detail(ev)
        fso = ev.manifest["five_school_output"]
        tendencies = {
            name: payload["overall_tendency"]
            for name, payload in fso.items()
            if isinstance(payload, dict) and "overall_tendency" in payload
        }
        for item in detail["conflicts"]:
            a, b = item["between"]
            assert {tendencies[a], tendencies[b]} == {"favorable", "unfavorable"}, item

    def test_no_conflict_when_one_sided(self) -> None:
        detail = _detail(_evaluate(demo_veto=False))
        assert detail["conflicts"] == []
