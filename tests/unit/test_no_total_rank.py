"""`_total_rank` / `_mean_rank_score` 删除的反证测试（ADR-0015）。

为什么"删了"必须被测试锁住
--------------------------
删一个分支的理由再正确，也只是**声明**；下一个人把 `score_weight` 上限放宽、
或把 `positive >= 2` 改回 `>= 1`，那条被删的分支就会"复活"——而没有任何测试会红。

故这里用两把锁：

1. **源码锁（AST）**：两个符号不得以任何形式重新出现（定义、调用、属性访问）。
   字符串出现在注释里是允许的（那是历史说明），但语法树里不得有。
2. **行为锁（sort_key）**：排序末位必须是整数 `positive_count`，且**对跨派 `rank_score` 不敏感**。
   构造两个只有 rank_score 不同的评估对象，排序键必须逐字相同。

锁的边界（重要，防止误伤合法用法）
--------------------------------
本锁反对的是 **`rank_score` 跨派合成/求均值**（`sum(scores)/len(scores)`），
不是"`rank_score` 永远不能出现在排序逻辑里"。

**单派内部**按自己的 `rank_score` 排序是**合法用途**（域内相对值，ADR-0015 明确保留：
`explain_sort` 仍原样输出 `school_rank_scores` 供复核）。若将来确实需要引入，
应把本锁改成"排序键中的 `rank_score` 只出现在单派分区内，不跨派累加/平均"，
而不是直接删掉它。

换句话说：
- ❌ `-mean([r.rank_score for r in per_school])`——跨派合成，本锁禁止；
- ✅ `sorted(positives, key=lambda j: j.score_weight)`——单派内排序，合法，与本锁无关。
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from core_eval.ranker import sort_key

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "core-eval" / "src" / "core_eval" / "engine.py"
RANKER = ROOT / "core-eval" / "src" / "core_eval" / "ranker.py"

BANNED = ("_total_rank", "_mean_rank_score")


def _names_in(path: Path) -> set[str]:
    """收集模块里作为**代码**出现的标识符（定义名、调用名、属性名）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


class TestSourceLock:
    @pytest.mark.parametrize("banned", BANNED)
    @pytest.mark.parametrize("path", [ENGINE, RANKER], ids=lambda p: p.name)
    def test_symbol_absent_from_ast(self, path: Path, banned: str) -> None:
        assert banned not in _names_in(path), (
            f"{path.name} 的语法树里仍有 `{banned}`（定义/调用/属性访问）——"
            "跨派聚合键被重新引入，ADR-0015 失效"
        )

    def test_comment_keeps_history(self) -> None:
        """注释里保留历史说明是有意的：后人要知道这里删过什么、为什么删。"""
        text = ENGINE.read_text(encoding="utf-8")
        assert "_total_rank" in text, "engine.py 应保留删除说明（否则下一个人会重新发明它）"

    def test_no_aggregate_lint_tool_exists(self) -> None:
        """配套的静态门禁必须在盘上，否则 AST 锁只是孤证。"""
        tool = ROOT / "tools" / "check_no_aggregate_score.py"
        assert tool.exists()
        assert "consensus_ratio" in tool.read_text(encoding="utf-8")


class TestSortKeyBehavior:
    def _ev(self, *, positive: int, rank_score: float | None = None) -> SimpleNamespace:
        return SimpleNamespace(
            candidate="2027-07-11T14:00",
            tier="NEEDS_REVIEW",
            vectors={
                "hard_fail_count": 0,
                "strong_avoid_count": 1,
                "conflict_count": 0,
                "unknown_count": 4,
                "positive_count": positive,
            },
            per_school={
                "sanhe": SimpleNamespace(rank_score=rank_score),
            },
        )

    def test_last_key_is_integer_positive_count(self) -> None:
        key = sort_key(self._ev(positive=3))
        assert key[-2] == -3, f"排序末位应为 -positive_count，得到 {key[-2]}"
        assert isinstance(key[-2], int)

    def test_rank_score_does_not_affect_sort_key(self) -> None:
        """同一份计数、不同 rank_score → 排序键必须完全相同。

        旧实现末位是 `-mean_rank_score`，这条断言会直接失败。
        """
        low = sort_key(self._ev(positive=2, rank_score=0.0))
        high = sort_key(self._ev(positive=2, rank_score=9.9))
        assert low == high

    def test_more_positives_sort_earlier(self) -> None:
        assert sort_key(self._ev(positive=5)) < sort_key(self._ev(positive=1))

    def test_negative_zero_is_stable(self) -> None:
        """-0 == 0，不能因为正负号产生不必要的排序抖动。"""
        assert sort_key(self._ev(positive=0)) == sort_key(self._ev(positive=0))
