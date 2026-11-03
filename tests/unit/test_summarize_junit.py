"""``tools/summarize_junit.py``：junit 汇总行不得把 skipped 算成 passed。

2026-11-03 评审十一回路发现：``tests`` 是总数，原实现直接报成 ``N passed``。
覆盖率步骤引入 1 个环境性 skip 后，出现「1220 passed + 1 skipped」被报成
「1221 passed / 1 skipped」的自相矛盾行——这是报数工具，不是产品测试，但
错报会让「全绿」与「有跳过」不可区分。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "summarize_junit", _ROOT / "tools" / "summarize_junit.py"
)
assert _SPEC and _SPEC.loader
summarize_junit = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(summarize_junit)


def _xml(tmp_path: Path, *, tests: int, failures: int, errors: int, skipped: int) -> Path:
    path = tmp_path / "junit.xml"
    path.write_text(
        "<testsuites><testsuite "
        f'tests="{tests}" failures="{failures}" errors="{errors}" '
        f'skipped="{skipped}" time="1.5" />'
        "</testsuites>",
        encoding="utf-8",
    )
    return path


def test_passed_excludes_failed_and_skipped(tmp_path: Path) -> None:
    path = _xml(tmp_path, tests=4, failures=1, errors=0, skipped=1)
    line, ok = summarize_junit.summarize(path)
    assert ok is False
    assert "2 passed / 1 failed / 0 errors / 1 skipped" in line


def test_skip_alone_does_not_turn_green_into_red(tmp_path: Path) -> None:
    path = _xml(tmp_path, tests=3, failures=0, errors=0, skipped=1)
    line, ok = summarize_junit.summarize(path)
    assert ok is True
    assert "2 passed / 0 failed / 0 errors / 1 skipped" in line


def test_skipped_reason_is_visible(tmp_path: Path) -> None:
    """skip 不能是无名氏：gate 输出要能回答「跳了什么、为什么」。"""
    path = tmp_path / "junit-skip.xml"
    path.write_text(
        "<testsuites><testsuite tests=\"2\" failures=\"0\" errors=\"0\" "
        "skipped=\"1\" time=\"0.5\">"
        '<testcase classname="tests.golden.test_x" name="test_budget">'
        '<skipped message="覆盖率插桩放大耗时，计时交给独立进程" />'
        "</testcase>"
        '<testcase classname="tests.golden.test_x" name="test_ok" />'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    details = summarize_junit.skipped_details(path)
    assert len(details) == 1
    assert "test_budget" in details[0]
    assert "覆盖率插桩放大耗时" in details[0]


def test_all_skipped_is_not_green(tmp_path: Path) -> None:
    """全跳过不是「通过」：passed=0 时不能给 ✅。"""
    path = _xml(tmp_path, tests=2, failures=0, errors=0, skipped=2)
    line, ok = summarize_junit.summarize(path)
    assert ok is False
    assert "0 passed / 0 failed / 0 errors / 2 skipped" in line
    assert line.startswith("❌")


def test_skip_summons_warning_line(tmp_path: Path) -> None:
    """有 skip 时要额外喊一行「非 pass」，避免「全绿」被读成「性能也验了」。"""
    path = _xml(tmp_path, tests=3, failures=0, errors=0, skipped=1)
    line, ok = summarize_junit.summarize(path)
    assert ok is True
    assert "⚠️ 1 skipped（非 pass）" in line


def test_no_warning_line_without_skip(tmp_path: Path) -> None:
    path = _xml(tmp_path, tests=3, failures=0, errors=0, skipped=0)
    line, _ = summarize_junit.summarize(path)
    assert "skipped（非 pass）" not in line


def test_perf_seconds_read_from_case(tmp_path: Path) -> None:
    path = tmp_path / "junit-perf.xml"
    path.write_text(
        "<testsuites><testsuite tests=\"1\" failures=\"0\" errors=\"0\" "
        "skipped=\"0\" time=\"2.62\">"
        '<testcase classname="tests.golden.test_x" '
        'name="test_single_month_budget_smoke" time="2.62" />'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    assert summarize_junit.perf_seconds(path) == 2.62


def test_perf_seconds_missing_file_is_none(tmp_path: Path) -> None:
    assert summarize_junit.perf_seconds(tmp_path / "nope.xml") is None
