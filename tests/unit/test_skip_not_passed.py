"""锁死「skip 不算 pass」：junit 的 passed 字段绝不能把跳过项算进去。

背景：唯一合法的 UNDETERMINED 来自 `test_single_month_budget_smoke` 在覆盖率
插桩下自行跳过（计时不可比）。这条通道必须一直可见，且不能被人「顺手删掉」：
删了 skip，passed 数会从 N 变成 N+1，但汇总页仍显示全绿，异常就被静默吞掉。

本文件做两件事：
1. 用合成 junit 断言 ``tests - failures - errors - skipped - undetermined`` 的算术；
2. 用 AST 锁住真实 skip 测试的存在、跳过条件与跳过原因——删测试、删 skip、
   或改掉原因文案都会让这里失败。
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("ci_summary", _ROOT / "tools" / "ci_summary.py")
assert _SPEC and _SPEC.loader
ci_summary = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ci_summary)

_GOLDEN = _ROOT / "tests/golden/test_required_and_negative.py"
_SKIP_TEST = "test_single_month_budget_smoke"


def _write(tmp_path: Path, suite_attrs: str, cases: str = "") -> Path:
    path = tmp_path / "junit-cov.xml"
    path.write_text(
        f"<testsuites><testsuite {suite_attrs}>{cases}</testsuite></testsuites>",
        encoding="utf-8",
    )
    return path


class TestPassedArithmetic:
    def test_skipped_not_in_passed(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            'tests="3" failures="0" errors="0" skipped="1" time="1.0"',
            '<testcase classname="a" name="ok1"/><testcase classname="a" name="ok2"/>'
            '<testcase classname="a" name="slow"><skipped message="插桩不计时"/></testcase>',
        )
        record = ci_summary._suite(path)
        assert record["passed"] == 2
        assert record["skipped"] == 1
        assert record["ok"] is False
        assert len(record["skip_details"]) == 1

    def test_only_skipped_means_zero_passed(self, tmp_path: Path) -> None:
        path = _write(
            tmp_path,
            'tests="1" failures="0" errors="0" skipped="1" time="0.5"',
            '<testcase classname="a" name="slow"><skipped message="x"/></testcase>',
        )
        record = ci_summary._suite(path)
        assert record["passed"] == 0
        assert record["ok"] is False

    def test_undetermined_not_in_passed(self, tmp_path: Path) -> None:
        path = _write(tmp_path, 'tests="2" failures="0" errors="0" skipped="0" undetermined="1"')
        record = ci_summary._suite(path)
        assert record["passed"] == 1
        assert record["ok"] is False

    def test_failure_and_skip_do_not_double_count(self, tmp_path: Path) -> None:
        path = _write(tmp_path, 'tests="2" failures="1" errors="0" skipped="1"')
        record = ci_summary._suite(path)
        assert record["passed"] == 0

    def test_render_marks_skip_as_undetermined(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            'tests="2" failures="0" errors="0" skipped="1" time="1.0"',
            '<testcase classname="tests.golden.test_required_and_negative" '
            f'name="{_SKIP_TEST}"><skipped message="覆盖率插桩"/></testcase>',
        )
        records = ci_summary.collect(tmp_path, expected=None)
        page = ci_summary.render(records, scope="local")
        assert "⚠️ 无法判定" in page
        assert _SKIP_TEST in page
        assert "✅ 全部" not in page


def _skip_test_node() -> ast.FunctionDef:
    tree = ast.parse(_GOLDEN.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == _SKIP_TEST:
            return node
    raise AssertionError(f"{_GOLDEN} 缺少 {_SKIP_TEST}；skip 通道不能静默消失")


def _calls(node: ast.AST, func_name: str) -> list[ast.Call]:
    found: list[ast.Call] = []
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if (isinstance(func, ast.Name) and func.id == func_name) or (
            isinstance(func, ast.Attribute) and func.attr == func_name
        ):
            found.append(sub)
    return found


class TestRealSkipTestIsLocked:
    def test_skip_test_exists(self) -> None:
        node = _skip_test_node()
        assert node.lineno > 0

    def test_skip_is_guarded_by_coverage_check(self) -> None:
        node = _skip_test_node()
        guarded = [
            stmt for stmt in ast.walk(node) if isinstance(stmt, ast.If) and _calls(stmt.test, "_coverage_active")
        ]
        assert guarded, "计时 skip 必须仍由 _coverage_active() 守卫，不能无条件跳过"
        assert any(_calls(stmt, "skip") for stmt in guarded), "守卫分支里找不到 pytest.skip"

    def test_skip_reason_still_explains_instrumentation(self) -> None:
        node = _skip_test_node()
        reasons = [
            arg.value
            for call in _calls(node, "skip")
            for arg in call.args
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
        ]
        assert reasons, "pytest.skip 缺少原因文案"
        text = "".join(reasons)
        assert "覆盖率插桩" in text
        assert "2.07–2.62s" in text, "实测区间被改掉，汇总页的理由就不再是证据"

    def test_coverage_helper_still_checks_instrumentation(self) -> None:
        tree = ast.parse(_GOLDEN.read_text(encoding="utf-8"))
        helper = next(
            (node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "_coverage_active"),
            None,
        )
        assert helper is not None, "_coverage_active 被删除，skip 条件失去依据"
        assert _calls(helper, "current"), "必须用 Coverage.current() 判断插桩，不能用环境变量猜"
