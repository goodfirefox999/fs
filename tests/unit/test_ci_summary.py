"""``tools/ci_summary.py``：Step Summary 必须列出所有失败项，不只 perf_smoke。

回归用例（run #33）：slow bench 9.02s / 9.36s 超 9.0s 档导致 job 红，但 summary
只有冒烟 1.33s（通过），看 summary 的人无法知道红在哪。这里锁住三件事：
1. 每个 junit 套件都出现在表里；
2. 失败用例名、耗时、首行断言消息可在 summary 里直接读到；
3. 没有 junit 产物时明确写「不是绿色证明」，不输出空白页。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("ci_summary", _ROOT / "tools" / "ci_summary.py")
assert _SPEC and _SPEC.loader
ci_summary = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ci_summary)


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(f"<testsuites>{body}</testsuites>", encoding="utf-8")
    return path


def _suite(tests: int, failures: int, skipped: int, seconds: float, cases: str = "") -> str:
    return (
        f'<testsuite tests="{tests}" failures="{failures}" errors="0" skipped="{skipped}" '
        f'time="{seconds}">{cases}</testsuite>'
    )


def test_bench_failure_is_visible_next_to_passing_smoke(tmp_path: Path) -> None:
    """run #33 的形状：冒烟绿、slow bench 红——两行都要在表里，失败项要展开。"""
    _write(
        tmp_path,
        "junit-perf-smoke.xml",
        _suite(
            1, 0, 0, 1.33,
            '<testcase classname="tests.golden.test_x" '
            'name="test_single_month_budget_smoke" time="1.33" />',
        ),
    )
    _write(
        tmp_path,
        "junit-bench.xml",
        _suite(
            1, 1, 0, 9.02,
            '<testcase classname="tests.bench.test_perf" name="test_full_year_within_budget" time="9.02">'
            '<failure message="全量穷举耗时 9.02s，超出预算 9.0s&#10;assert 9.02 &lt; 9.0" />'
            "</testcase>",
        ),
    )
    text = ci_summary.render(ci_summary.collect(tmp_path))
    assert "`junit-perf-smoke.xml`" in text and "✅" in text
    assert "`junit-bench.xml`" in text and "❌" in text
    assert "- `tests.bench.test_perf::test_full_year_within_budget`（9.02s）：全量穷举耗时 9.02s，超出预算 9.0s" in text
    assert "- - " not in text, "明细自带 bullet 会渲染成双层列表"


def test_skip_reason_is_carried_into_summary(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "junit-cov.xml",
        _suite(
            2, 0, 1, 345.8,
            '<testcase classname="tests.golden.test_x" name="test_a" time="0.1" />'
            '<testcase classname="tests.golden.test_x" name="test_smoke" time="0.0">'
            '<skipped message="覆盖率插桩放大耗时" />'
            "</testcase>",
        ),
    )
    text = ci_summary.render(ci_summary.collect(tmp_path))
    assert "| `junit-cov.xml` | 1 | 0 | 0 | 1 | 345.8s | ✅ |" in text
    assert "### 跳过项（非 pass）" in text
    assert "`tests.golden.test_x::test_smoke`：覆盖率插桩放大耗时" in text


def test_empty_directory_is_explicitly_not_green(tmp_path: Path) -> None:
    text = ci_summary.render(ci_summary.collect(tmp_path))
    assert "未找到任何 junit 产物" in text
    assert "不是绿色证明" in text
    assert "| 套件 |" not in text


def test_corrupt_xml_is_a_visible_failure(tmp_path: Path) -> None:
    (tmp_path / "junit-broken.xml").write_text("<testsuites>", encoding="utf-8")
    text = ci_summary.render(ci_summary.collect(tmp_path))
    assert "`junit-broken.xml`" in text
    assert "XML 损坏" in text
    assert "❌" in text
