"""``tools/ci_summary.py``：Step Summary 必须列全套件，失败/缺失都不能从表里消失。

回归用例（run #33）：slow bench 9.02s / 9.36s 超 9.0s 档导致 job 红，但 summary
只有冒烟 1.33s（通过），看 summary 的人无法知道红在哪。覆盖六类形状：全通过、
全失败、全缺失、部分缺失（删一个 junit）、产物未登记、skip 可见；另做双向漂移反查。
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("ci_summary", _ROOT / "tools" / "ci_summary.py")
assert _SPEC and _SPEC.loader
ci_summary = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ci_summary)

_EXPECTED_FILES = list(ci_summary.EXPECTED_SUITES.values())


def _write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(f"<testsuites>{body}</testsuites>", encoding="utf-8")
    return path


def _suite(
    tests: int, failures: int, skipped: int, seconds: float, cases: str = "", errors: int = 0
) -> str:
    return (
        f'<testsuite tests="{tests}" failures="{failures}" errors="{errors}" '
        f'skipped="{skipped}" time="{seconds}">{cases}</testsuite>'
    )


def _passing_cases(count: int = 1) -> str:
    return "".join(
        f'<testcase classname="tests.ok" name="test_ok_{index}" time="0.1" />'
        for index in range(count)
    )


def _write_all_passing(tmp_path: Path) -> None:
    for name in _EXPECTED_FILES:
        _write(tmp_path, name, _suite(1, 0, 0, 10.0, _passing_cases()))


def test_all_expected_suites_pass_is_green(tmp_path: Path) -> None:
    """全通过：判定行必须给出「全部 3 个套件通过」，不能只堆表格。"""
    _write_all_passing(tmp_path)
    text = ci_summary.render(ci_summary.collect(tmp_path))
    assert "**判定：✅ 全部 3 个套件通过。**" in text
    assert text.count("| ✅ |") == 3
    assert "缺失" not in text


def test_missing_bench_junit_is_reported_not_skipped(tmp_path: Path) -> None:
    """核心反证：删掉 junit-bench.xml（bench 步骤挂掉），汇总必须报缺失而非沉默。"""
    _write_all_passing(tmp_path)
    (tmp_path / "junit-bench.xml").unlink()
    text = ci_summary.render(ci_summary.collect(tmp_path))
    assert "`junit-bench.xml`" in text
    assert "缺失：预期套件「bench」未产出 junit" in text
    assert "**判定：❌ " in text and "本页不是绿色证明" in text
    assert text.count("| ✅ |") == 2, "另外两个套件仍应显示通过"


def test_unregistered_junit_is_a_visible_failure(tmp_path: Path) -> None:
    """产物有、清单无：新增套件漏登记时，即使全通过也不能混进「全部通过」。"""
    _write_all_passing(tmp_path)
    _write(tmp_path, "junit-mutation.xml", _suite(1, 0, 0, 10.0, _passing_cases()))
    text = ci_summary.render(ci_summary.collect(tmp_path))
    assert "`junit-mutation.xml`" in text
    assert "未登记套件" in text
    assert "| `junit-mutation.xml` | 1 | 0 | 0 | 0 | 10.0s | ❌ 未登记 |" in text
    assert "**判定：❌ 1 个套件未登记" in text
    assert "本页不是绿色证明" in text
    assert "**判定：✅" not in text


def test_all_missing_reports_every_expected_suite(tmp_path: Path) -> None:
    """全缺失：每个期望套件都要有 ❌ 行，不能只剩一句「没找到文件」。"""
    text = ci_summary.render(ci_summary.collect(tmp_path))
    for name in _EXPECTED_FILES:
        assert f"`{name}`" in text
    assert text.count("缺失：预期套件") == 3
    assert "本页不是绿色证明" in text
    assert "✅" not in text


def test_all_failing_suites_are_visible_with_details(tmp_path: Path) -> None:
    """全失败：三行都 ❌，且每个失败用例名/耗时/首行消息可直接读。"""
    for index, name in enumerate(_EXPECTED_FILES):
        _write(
            tmp_path,
            name,
            _suite(
                1,
                1,
                0,
                5.0,
                f'<testcase classname="tests.bad" name="test_bad_{index}" time="1.0">'
                f'<failure message="boom {index}&#10;assert False" /></testcase>',
            ),
        )
    text = ci_summary.render(ci_summary.collect(tmp_path))
    assert "**判定：❌ 3 个套件失败" in text
    assert text.count("| ❌ |") == 3
    for index, name in enumerate(_EXPECTED_FILES):
        assert f"- `tests.bad::test_bad_{index}`（1.00s）：boom {index}（{name}）" in text


def test_skip_reason_is_carried_into_summary(tmp_path: Path) -> None:
    """skip 不算 pass，也不能隐形：表格计数 + 原因都要在 summary 里。"""
    _write_all_passing(tmp_path)
    _write(
        tmp_path,
        "junit-cov.xml",
        _suite(
            2,
            0,
            1,
            345.8,
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
    assert "**判定：✅ 全部 3 个套件通过。**" in text, "有 skip 但无失败时仍算绿，但 skip 必须可见"


def test_bench_failure_is_visible_next_to_passing_smoke(tmp_path: Path) -> None:
    """run #33 的形状：冒烟绿、slow bench 红——失败项要展开且不渲染双层 bullet。"""
    _write_all_passing(tmp_path)
    _write(
        tmp_path,
        "junit-bench.xml",
        _suite(
            1,
            1,
            0,
            9.02,
            '<testcase classname="tests.bench.test_perf" name="test_full_year_within_budget" time="9.02">'
            '<failure message="全量穷举耗时 9.02s，超出预算 9.0s&#10;assert 9.02 &lt; 9.0" />'
            "</testcase>",
        ),
    )
    text = ci_summary.render(ci_summary.collect(tmp_path))
    assert "`junit-perf-smoke.xml`" in text and "✅" in text
    assert "`junit-bench.xml`" in text and "❌" in text
    assert (
        "- `tests.bench.test_perf::test_full_year_within_budget`（9.02s）："
        "全量穷举耗时 9.02s，超出预算 9.0s" in text
    )
    assert "- - " not in text, "明细自带 bullet 会渲染成双层列表"


def test_corrupt_xml_is_a_visible_failure(tmp_path: Path) -> None:
    """损坏的 junit 与缺失同等对待：一行 ❌，不能当作没跑过而略过。"""
    _write_all_passing(tmp_path)
    (tmp_path / "junit-bench.xml").write_text("<testsuites>", encoding="utf-8")
    text = ci_summary.render(ci_summary.collect(tmp_path))
    assert "`junit-bench.xml`" in text
    assert "XML 损坏" in text
    assert "❌" in text


def test_no_records_at_all_is_explicitly_not_green(tmp_path: Path) -> None:
    """关闭期望清单时（expected=None），空目录仍走「测试可能没跑」分支。"""
    text = ci_summary.render(ci_summary.collect(tmp_path, expected=None))
    assert "未找到任何 junit 产物" in text
    assert "不是绿色证明" in text
    assert "| 套件 |" not in text


def _make_recipe(makefile: str, target: str) -> str:
    lines = makefile.splitlines()
    for index, line in enumerate(lines):
        if not line.startswith(f"{target}:"):
            continue
        recipe: list[str] = []
        for nxt in lines[index + 1 :]:
            if nxt and not nxt.startswith("\t"):
                break
            recipe.append(nxt)
        return "\n".join(recipe)
    raise AssertionError(f"Makefile 缺少 {target} 目标")


def test_expected_suites_match_ci_artifacts_both_directions() -> None:
    """清单与 CI 产物必须双向一致：漏登记新增 junit 或登记了不产出的名字都要红。"""
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
    # 范围只取 CI 实际走的产物：ci.yml 内联步骤 + make cov 配方。Makefile 的
    # test/test-fast/golden 是本地目标，不产出 CI artifact，刻意不纳入。
    produced = set(
        re.findall(
            r"--junitxml=out/(junit-[A-Za-z0-9_.-]+\.xml)",
            workflow + "\n" + _make_recipe(makefile, "cov"),
        )
    )
    declared = set(ci_summary.EXPECTED_SUITES.values())
    assert produced == declared, (
        f"未登记（产物有清单无）：{sorted(produced - declared)}；"
        f"已失效（清单有产物无）：{sorted(declared - produced)}"
    )
