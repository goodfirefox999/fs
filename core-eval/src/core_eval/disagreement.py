"""派别分歧度（判定层）。

公式（**口径固定，不得改写**，docs/DEVELOPMENT.md 第 7 节第 8 条）
--------------------------------------------------------------
对候选 ``t``，取各派判定映射 ``{禁用:0, 慎用:1, 可用:2}``::

    disagreement(t) = 1 - 众数频次 / 派数

全局分歧度 = 候选集 ``disagreement(t)`` 的算术平均。

语义：``0`` 表示所有派别判定一致；越高表示分歧越大。**它不是"吉凶概率"**，
也不参与推荐等级计算，只用于报告"这套规则在不同派别下有多不一致"。
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping

from .engine import STATE_BLOCKED, STATE_OK, STATE_UNSURE, Evaluation

__all__ = [
    "STATE_TO_NUM",
    "disagreement_of",
    "disagreement_of_evaluation",
    "aggregate_disagreement",
    "most_divisive",
]

#: 三态 → 数值（口径固定）
STATE_TO_NUM: dict[str, int] = {STATE_BLOCKED: 0, STATE_UNSURE: 1, STATE_OK: 2}


def disagreement_of(states: Iterable[str]) -> float:
    """由各派三态计算分歧度，取值 [0, 1)。单派时恒为 0。"""
    nums = [STATE_TO_NUM[s] for s in states]
    if len(nums) <= 1:
        return 0.0
    mode_count = Counter(nums).most_common(1)[0][1]
    return 1.0 - mode_count / len(nums)


def disagreement_of_evaluation(ev: Evaluation) -> float:
    return disagreement_of(res.state for res in ev.per_school.values())


def aggregate_disagreement(evals: Iterable[Evaluation]) -> float:
    """候选集平均分歧度。空集返回 0。"""
    values = [disagreement_of_evaluation(e) for e in evals]
    return sum(values) / len(values) if values else 0.0


def most_divisive(evals: Iterable[Evaluation], top: int = 10) -> list[tuple[str, float, Mapping[str, str]]]:
    """返回分歧最大的候选清单：``(candidate, disagreement, {school: state})``。"""
    rows = [
        (e.candidate, disagreement_of_evaluation(e), {k: r.state for k, r in e.per_school.items()})
        for e in evals
    ]
    rows.sort(key=lambda r: (-r[1], r[0]))
    return rows[:top]
