"""仲裁层输出（评审扩展版 spec §4）：rejected_dates / scored_dates / consensus_dates。

仲裁原则（spec §4，逐条对应）：
1. **reject 绝对优先**：触达任一 hard_veto 的日期直接进入 ``rejected_dates``，
   不进入 ``scored_dates``——董公煞贡/直星/人专不能绕过（Layer 3 优先性）。
   若被拒日期恰逢董公三星值日，条目带
   ``school_override_attempted: "donggong_shagong_cannot_override"``，
   显式告知下游"该吉星不能推翻 reject"。
2. **五派输出并列保留**：``scored_dates`` 每条带 ``school_results``（五派各自
   overall_tendency / score_delta / sub_rules / conflict_flags），仲裁层不丢弃、
   不合并任一派原始输出。
3. **冲突显式呈现**：两派 tendency 相反 → ``conflicts`` 列出双方派名与依据，
   不裁决谁对谁错。
4. **consensus_dates**：五派中三派及以上 favorable 且未被 reject 的日期标记
   ``consensus_favorable``；仍保留各派原始输出与分歧（scored_dates 照常收录）。

本模块只做结构重组，不做任何新的事实计算或吉凶判断。
"""

from __future__ import annotations

from typing import Any, Iterable

from .engine import Evaluation

__all__ = ["build_spec_output", "SHAGONG_CANNOT_OVERRIDE"]

#: spec §3/§4：董公三星不能推翻 Layer 3 reject 的显式标记
SHAGONG_CANNOT_OVERRIDE = "donggong_shagong_cannot_override"

#: 董公三星（spec §2.3：煞贡/直星/人专能解诸凶，唯不能解金神七煞）
_SHAGONG_STARS = ("煞贡", "直星", "人专")


def build_spec_output(pairs: Iterable[tuple[Evaluation, dict[str, Any]]]) -> dict[str, Any]:
    """把逐候选评估结果重组成 spec §4 仲裁结构。

    ``pairs`` 为 ``(Evaluation, ctx)`` 序列；ctx 用于读取董公三星事实以标注
    ``school_override_attempted``。**不引入任何新判断**——reject 判定复用
    评估结果中的 veto 桶（即 hard_veto 规则命中）。
    """
    rejected_dates: list[dict[str, Any]] = []
    scored_dates: list[dict[str, Any]] = []
    for ev, ctx in pairs:
        reject_rules = [j.rule_id for res in ev.per_school.values() for j in res.vetoes]
        if reject_rules:
            entry: dict[str, Any] = {
                "date": ev.candidate,
                "reject_rule": reject_rules[0],
                "reject_rules": reject_rules,
            }
            star = ((ctx.get("facts") or {}).get("donggong") or {}).get("star")
            if star in _SHAGONG_STARS:
                entry["school_override_attempted"] = SHAGONG_CANNOT_OVERRIDE
            rejected_dates.append(entry)
            continue  # reject 绝对优先：不进评分环节

        fso = ev.manifest.get("five_school_output") or {}
        school_results = {
            name: d
            for name, d in fso.items()
            if not name.startswith("_") and isinstance(d, dict)
        }
        scored_dates.append(
            {
                "date": ev.candidate,
                "school_results": school_results,
                "consensus": fso.get("_consensus"),
                "conflicts": list(fso.get("_conflicts") or []),
            }
        )

    # consensus_dates：三派及以上 favorable 且未被 reject（spec §4.5）
    consensus_dates = [
        {"date": s["date"], "mark": "consensus_favorable"}
        for s in scored_dates
        if s["consensus"] == "favorable"
    ]
    return {
        "rejected_dates": rejected_dates,
        "scored_dates": scored_dates,
        "consensus_dates": consensus_dates,
    }
