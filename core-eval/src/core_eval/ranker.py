"""排序与 Pareto 分层（判定层）。

铁律：**禁止单一总分**。排序是多目标分层，不是 ``sum(score)``。

排序键（字典序，全部"越小越好"）
------------------------------
``(tier_rank, hard_fail_count, strong_avoid_count, conflict_count, unknown_count, -mean_rank_score, candidate)``

- ``tier_rank``：REJECTED > NEEDS_REVIEW > ACCEPTABLE > PREFERRED（REJECTED 排最后）
- ``mean_rank_score`` 仅在"可用"集内有意义，且**不得**被表述为吉凶概率

Pareto 前沿：在 (hard_fail, strong_avoid, conflict, unknown) 四维上做非支配筛选，
``positive`` 与 ``feasibility`` 作为正向维度取"越大越好"。
"""

from __future__ import annotations

from typing import Iterable

from .engine import (
    TIER_ACCEPTABLE,
    TIER_NEEDS_REVIEW,
    TIER_PREFERRED,
    TIER_REJECTED,
    Evaluation,
)

__all__ = ["TIER_RANK", "sort_key", "rank", "pareto_front", "top_k", "explain_sort"]

TIER_RANK: dict[str, int] = {
    TIER_PREFERRED: 0,
    TIER_ACCEPTABLE: 1,
    TIER_NEEDS_REVIEW: 2,
    TIER_REJECTED: 3,
}


def _mean_rank_score(ev: Evaluation) -> float:
    scores = [r.rank_score for r in ev.per_school.values() if r.rank_score is not None]
    return sum(scores) / len(scores) if scores else 0.0


def sort_key(ev: Evaluation) -> tuple:
    v = ev.vectors
    return (
        TIER_RANK.get(ev.tier, 9),
        v.get("hard_fail_count", 0),
        v.get("strong_avoid_count", 0),
        v.get("conflict_count", 0),
        v.get("unknown_count", 0),
        -_mean_rank_score(ev),
        ev.candidate,
    )


def rank(evals: Iterable[Evaluation]) -> list[Evaluation]:
    """按分层字典序排序。"""
    return sorted(evals, key=sort_key)


def top_k(evals: Iterable[Evaluation], k: int = 20) -> list[Evaluation]:
    if k <= 0:
        raise ValueError("k 必须为正整数")
    return rank(evals)[:k]


def _dominates(a: Evaluation, b: Evaluation) -> bool:
    """a 是否支配 b（四维劣势全不差 + 正向不差，且至少一维严格更好）。"""
    va, vb = a.vectors, b.vectors
    a_bad = (
        va.get("hard_fail_count", 0),
        va.get("strong_avoid_count", 0),
        va.get("conflict_count", 0),
        va.get("unknown_count", 0),
    )
    b_bad = (
        vb.get("hard_fail_count", 0),
        vb.get("strong_avoid_count", 0),
        vb.get("conflict_count", 0),
        vb.get("unknown_count", 0),
    )
    if any(x > y for x, y in zip(a_bad, b_bad)):
        return False
    if va.get("positive_count", 0) < vb.get("positive_count", 0):
        return False
    return a_bad != b_bad or va.get("positive_count", 0) > vb.get("positive_count", 0)


def pareto_front(evals: Iterable[Evaluation]) -> list[Evaluation]:
    """非支配前沿（按分层键排序后返回）。"""
    items = list(evals)
    front: list[Evaluation] = []
    for candidate in items:
        if not any(_dominates(other, candidate) for other in items if other is not candidate):
            front.append(candidate)
    return rank(front)


def explain_sort(ev: Evaluation) -> dict[str, object]:
    """返回排序依据的显式分解，供报告回显（避免"黑箱排序"）。"""
    v = ev.vectors
    return {
        "candidate": ev.candidate,
        "tier": ev.tier,
        "tier_rank": TIER_RANK.get(ev.tier, 9),
        "hard_fail_count": v.get("hard_fail_count", 0),
        "strong_avoid_count": v.get("strong_avoid_count", 0),
        "conflict_count": v.get("conflict_count", 0),
        "unknown_count": v.get("unknown_count", 0),
        "mean_rank_score": round(_mean_rank_score(ev), 4),
        "note": "mean_rank_score 仅为同派内可比的正向权重均值，非吉凶概率",
    }
