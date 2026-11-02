"""报告「共识度」节测试（ADR-0015）。

报告是对外唯一形态，所以这里守的不是"能不能跑"，而是**长什么样**：
只许出现整数比与名单，不许出现任何浮点分值——一旦报告里有 0.6、82.5 这类数，
下游（含 LLM 解释层）就会把它当"综合吉凶分"引用。
"""

from __future__ import annotations

import re

from app_zeri.report import _consensus_block

DETAIL = {
    "consensus": "mixed",
    "consensus_ratio": "2/3",
    "votes": {"favorable": ["sanhe", "zhengwuxing"], "unfavorable": ["xuankong_dagua"]},
    "voters": ["sanhe", "zhengwuxing", "xuankong_dagua"],
    "non_voters": [
        {"school": "public", "layer": "reject", "reason": "layer_reject"},
        {"school": "doushou", "layer": "reference", "reason": "layer_reference"},
        {"school": "tianxing", "layer": "scoring", "reason": "no_verdict"},
    ],
    "gate_veto_schools": ["public"],
    "threshold": {"min_agree_num": 3, "min_agree_den": 5},
    "task_kind": "修造",
}


def _render(detail: dict | None) -> str:
    fso = {} if detail is None else {"_consensus_detail": detail}
    return "\n".join(_consensus_block(fso))


class TestConsensusSection:
    def test_shows_integer_ratio_and_threshold(self) -> None:
        out = _render(DETAIL)
        assert "**2/3 同向**" in out
        assert "阈值 3/5" in out
        assert "修造" in out

    def test_lists_voters_and_both_sides(self) -> None:
        out = _render(DETAIL)
        assert "参与投票（3 派）" in out
        assert "sanhe、zhengwuxing" in out
        assert "xuankong_dagua" in out

    def test_explains_every_non_voter(self) -> None:
        out = _render(DETAIL)
        assert "闸门层，只否决不计票" in out
        assert "参考层，不参与仲裁" in out
        assert "本轮无判定" in out

    def test_no_float_score_in_output(self) -> None:
        out = _render(DETAIL)
        assert not re.search(r"\d+\.\d+", out), f"报告中出现浮点分值：\n{out}"

    def test_states_this_is_not_a_probability(self) -> None:
        out = _render(DETAIL)
        assert "不是吉凶概率" in out

    def test_missing_detail_degrades_honestly(self) -> None:
        out = _render(None)
        assert "未产出共识明细" in out

    def test_gate_veto_is_surfaced(self) -> None:
        out = _render(DETAIL)
        assert "闸门否决" in out
        assert "public" in out
