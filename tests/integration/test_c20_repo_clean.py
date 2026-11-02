"""仓库级断言：C20 在**真仓库**上必须干净（与工具单元测试分离）。

为什么单独成文件
----------------
这个断言依赖"引擎已经修完"（`_mean_rank_score` 已删）。若把它放在工具片
（`tests/unit/test_no_aggregate_score_lint.py`），工具片单独检出时必然变红——
那是 bisect 最怕的形态：一个只加了 lint 工具的提交，却因为仓库里还有旧代码而失败。

工具本身的能力用 fixture 验证（那才是反证）；"今天仓库是否干净"是另一件事。
"""

from __future__ import annotations

import ast
from pathlib import Path

from tools.check_no_aggregate_score import MIN_REASON_LEN, list_exemptions, scan_repo

ROOT = Path(__file__).resolve().parents[2]


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
