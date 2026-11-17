"""排序的共识维度：方向 → 证据等级 → 同向派数 → 冲突数。

排序是报告里"候选先后"的唯一来源。这里守的不是"排出来能看"，而是
**每一维的优先级都不能被下一位悄悄越权**：

1. 硬闸门（tier）永远第一——再强的正向共识也不能把 REJECTED 抬到前面；
2. 方向优先于票数——POSITIVE_STRONG 不应输给"票多但意见相反"；
3. 证据等级优先于同向派数——两张 C 票不能压过一张 A 票；
4. 冲突数只在前面全部相同时才起作用。

全程字典序，不做任何加权求和（ADR-0015）。
"""

from __future__ import annotations

from types import SimpleNamespace

from core_eval.ranker import sort_key

TIER_OK = "ACCEPTABLE"
TIER_REJECTED = "REJECTED"


def _ev(
    *,
    tier: str = TIER_OK,
    candidate: str = "c",
    consensus: str = "mixed",
    favorable: tuple[str, ...] = (),
    unfavorable: tuple[str, ...] = (),
    voters: tuple[str, ...] | None = None,
    grades: dict[str, list[str]] | None = None,
    conflicts: int = 0,
) -> SimpleNamespace:
    if voters is None:
        voters = favorable + unfavorable
    if grades is None:
        grades = {name: ["A"] for name in voters}
    detail = {
        "consensus": consensus,
        "votes": {"favorable": list(favorable), "unfavorable": list(unfavorable)},
        "voters": list(voters),
        "voter_evidence_grades": grades,
    }
    return SimpleNamespace(
        tier=tier,
        candidate=candidate,
        vectors={
            "hard_fail_count": 0,
            "strong_avoid_count": 0,
            "conflict_count": conflicts,
            "unknown_count": 0,
            "positive_count": len(favorable),
        },
        manifest={"five_school_output": {"_consensus_detail": detail}},
    )


def _ordered(*evs: SimpleNamespace) -> list[str]:
    return [ev.candidate for ev in sorted(evs, key=sort_key)]


class TestDirection:
    def test_strong_then_conflicted_then_mixed_then_negative(self) -> None:
        strong = _ev(candidate="strong", consensus="favorable", favorable=("sanhe",))
        conflicted = _ev(
            candidate="conflicted",
            consensus="favorable",
            favorable=("sanhe",),
            unfavorable=("xuankong_dagua",),
        )
        mixed = _ev(candidate="mixed", consensus="mixed", favorable=("sanhe",))
        negative = _ev(
            candidate="negative", consensus="unfavorable", unfavorable=("sanhe",)
        )
        assert _ordered(negative, mixed, conflicted, strong) == [
            "strong",
            "conflicted",
            "mixed",
            "negative",
        ]

    def test_direction_does_not_outrank_hard_gate(self) -> None:
        rejected_good = _ev(
            candidate="rejected", tier=TIER_REJECTED, consensus="favorable", favorable=("sanhe",)
        )
        acceptable_bad = _ev(
            candidate="acceptable", consensus="unfavorable", unfavorable=("sanhe",)
        )
        assert _ordered(rejected_good, acceptable_bad) == ["acceptable", "rejected"]


class TestVoterGrade:
    def test_all_a_beats_disputed_beats_c_beats_no_voters(self) -> None:
        all_a = _ev(
            candidate="a",
            consensus="favorable",
            favorable=("sanhe",),
            voters=("sanhe",),
            grades={"sanhe": ["A"]},
        )
        disputed = _ev(
            candidate="disputed",
            consensus="favorable",
            favorable=("doushou",),
            voters=("doushou",),
            grades={"doushou": ["disputed"]},
        )
        c_grade = _ev(
            candidate="c",
            consensus="favorable",
            favorable=("zhengwuxing",),
            voters=("zhengwuxing",),
            grades={"zhengwuxing": ["C"]},
        )
        no_vote = _ev(candidate="none", consensus="mixed", voters=())
        assert _ordered(no_vote, c_grade, disputed, all_a) == [
            "a",
            "disputed",
            "c",
            "none",
        ]

    def test_one_a_beats_two_c_votes(self) -> None:
        one_a = _ev(
            candidate="one_a",
            consensus="favorable",
            favorable=("sanhe",),
            voters=("sanhe",),
            grades={"sanhe": ["A"]},
        )
        two_c = _ev(
            candidate="two_c",
            consensus="favorable",
            favorable=("zhengwuxing", "donggong"),
            voters=("zhengwuxing", "donggong"),
            grades={"zhengwuxing": ["C"], "donggong": ["C"]},
        )
        assert _ordered(two_c, one_a) == ["one_a", "two_c"], (
            "证据等级优先于同向派数：两张 C 票不得压过一张 A 票"
        )


class TestCounts:
    def test_more_same_direction_votes_first(self) -> None:
        two = _ev(candidate="two", consensus="favorable", favorable=("sanhe", "zhengwuxing"))
        one = _ev(candidate="one", consensus="favorable", favorable=("sanhe",))
        assert _ordered(one, two) == ["two", "one"]

    def test_fewer_conflicts_first(self) -> None:
        clean = _ev(candidate="clean", consensus="favorable", favorable=("sanhe",), conflicts=0)
        dirty = _ev(candidate="dirty", consensus="favorable", favorable=("sanhe",), conflicts=2)
        assert _ordered(dirty, clean) == ["clean", "dirty"]
