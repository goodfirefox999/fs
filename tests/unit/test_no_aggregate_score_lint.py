"""C20 禁聚合总分 lint 的测试（含反证）。

AGENTS 补丁纪律第 3 条：每条 lint 不变式必须配反证测试——
构造违规样本断言**报警**，移除触发条件后断言**沉默**。
只断言"仓库恰好干净"不算验证：那只能证明今天没人写坏，证明不了明天会被抓住。
"""

from __future__ import annotations

import ast
from pathlib import Path

from tools.check_no_aggregate_score import (
    MIN_REASON_LEN,
    list_exemptions,
    scan_repo,
    scan_source,
)

ROOT = Path(__file__).resolve().parents[2]


def _codes(text: str) -> list[str]:
    return [f.code for f in scan_source(text, "<sample>")]


class TestDetectsAggregateMean:
    def test_cross_school_mean_is_reported(self) -> None:
        src = "def f(scores):\n    return sum(scores) / len(scores)\n"
        assert "C20-mean" in _codes(src)

    def test_same_sample_without_division_is_silent(self) -> None:
        """反证：把 `/ len(scores)` 去掉（改回计数），同一函数必须不再报警。"""
        src = "def f(scores):\n    return sum(scores)\n"
        assert _codes(src) == []

    def test_integer_count_of_rules_is_allowed(self) -> None:
        """`sum(len(...))` 是计数，不是均值——这是合规形态，不能误杀。"""
        src = (
            "def f(per_school):\n"
            "    return sum(len(r.vetoes) for r in per_school.values())\n"
        )
        assert _codes(src) == []

    def test_statistics_mean_call_is_reported(self) -> None:
        src = "import statistics\n\ndef f(xs):\n    return statistics.mean(xs)\n"
        assert "C20-mean-call" in _codes(src)

    def test_mean_named_helper_is_reported(self) -> None:
        """重建一个叫 mean 的辅助函数同样是重建均值工具。"""
        src = "def _mean_rank_score(xs):\n    total = 0.0\n    return total\n"
        assert "C20-mean-def" in _codes(src)


class TestExemption:
    def test_exempt_marker_silences(self) -> None:
        src = (
            "def f(scores):\n"
            "    # lint-exempt: 分歧度只用于报告展示，不进排序键\n"
            "    return sum(scores) / len(scores)\n"
        )
        assert _codes(src) == []

    def test_same_line_exempt_marker_silences(self) -> None:
        src = "def f(scores):\n    return sum(scores) / len(scores)  # lint-exempt: 评测吻合率，不进候选排序\n"
        assert _codes(src) == []

    def test_empty_exempt_reason_is_reported(self) -> None:
        src = "def f(scores):\n    # lint-exempt:\n    return sum(scores) / len(scores)\n"
        assert _codes(src) == ["C20-empty-exempt"]

    def test_short_exempt_reason_is_reported(self) -> None:
        src = "def f(scores):\n    # lint-exempt: 没事\n    return sum(scores) / len(scores)\n"
        assert _codes(src) == ["C20-empty-exempt"]

    def test_reason_length_threshold_is_enforced(self) -> None:
        ok = "x" * MIN_REASON_LEN
        bad = "x" * (MIN_REASON_LEN - 1)
        assert _codes(f"# lint-exempt: {ok}\n") == []
        src = f"def f(s):\n    # lint-exempt: {bad}\n    return sum(s) / len(s)\n"
        assert _codes(src) == ["C20-empty-exempt"]


class TestRepoIsClean:
    def test_repository_has_no_unexempted_mean(self) -> None:
        assert scan_repo(ROOT) == []

    def test_every_exemption_states_a_reason(self) -> None:
        rows = list_exemptions(ROOT)
        assert rows, "豁免清单不应为空：既有 5 处描述统计需要显式理由"
        for row in rows:
            reason = row.split(": ", 1)[1].strip()
            assert len(reason) >= MIN_REASON_LEN, f"豁免理由过短: {row}"

    def test_sort_key_contains_no_division_and_no_mean(self) -> None:
        """定点守卫：排序键函数里不得出现除法或均值调用（C20 的具体退化形态）。"""
        path = ROOT / "core-eval" / "src" / "core_eval" / "ranker.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        sort_key = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "sort_key"
        )
        for node in ast.walk(sort_key):
            assert not (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)), (
                "sort_key 出现除法：排序键必须是整数计数，不得是均值"
            )
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                assert name not in {"mean", "fmean", "average"}, (
                    f"sort_key 调用了均值函数 {name}"
                )
