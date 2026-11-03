"""``tools/ci_summary.py``：Step Summary 必须列全套件，失败/缺失都不能从表里消失。

回归用例（run #33）：slow bench 9.02s / 9.36s 超 9.0s 档导致 job 红，但 summary
只有冒烟 1.33s（通过），看 summary 的人无法知道红在哪。覆盖全通过、全失败、
全缺失、部分缺失（删一个 junit）、产物未登记、skip 可见；另做清单双向漂移、
本地清单（make cov 解析）漂移、全 workflow 调用点反查（含新增 workflow 反证）。
"""

from __future__ import annotations

import importlib.util
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("ci_summary", _ROOT / "tools" / "ci_summary.py")
assert _SPEC and _SPEC.loader
ci_summary = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ci_summary)

_EXPECTED_FILES = list(ci_summary.EXPECTED_SUITES.values())
# 本地有生产者的套件（make cov 产物）；bench 只在 ci.yml 里跑，单独反查漂移。
_LOCAL_EXPECTED = {"cov": "junit-cov.xml", "perf-smoke": "junit-perf-smoke.xml"}


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


def _render_ci(tmp_path: Path) -> str:
    return ci_summary.render(ci_summary.collect(tmp_path, scope="ci"), scope="ci")


def test_all_expected_suites_pass_is_green(tmp_path: Path) -> None:
    """全通过：判定行必须给出「全部 3 个套件通过」，不能只堆表格。"""
    _write_all_passing(tmp_path)
    text = _render_ci(tmp_path)
    assert "**判定：✅ 全部 3 个套件通过。**" in text
    assert text.count("| ✅ |") == 3
    assert "缺失" not in text


def test_missing_bench_junit_is_reported_not_skipped(tmp_path: Path) -> None:
    """核心反证：删掉 junit-bench.xml（bench 步骤挂掉），汇总必须报缺失而非沉默。"""
    _write_all_passing(tmp_path)
    (tmp_path / "junit-bench.xml").unlink()
    text = _render_ci(tmp_path)
    assert "`junit-bench.xml`" in text
    assert "缺失：预期套件「bench」未产出 junit" in text
    assert "**判定：❌ " in text and "本页不是绿色证明" in text
    assert text.count("| ✅ |") == 2, "另外两个套件仍应显示通过"


def test_unregistered_junit_is_a_visible_failure(tmp_path: Path) -> None:
    """产物有、清单无：新增套件漏登记时，即使全通过也不能混进「全部通过」。"""
    _write_all_passing(tmp_path)
    _write(tmp_path, "junit-mutation.xml", _suite(1, 0, 0, 10.0, _passing_cases()))
    text = _render_ci(tmp_path)
    assert "`junit-mutation.xml`" in text
    assert "未登记套件" in text
    assert "| `junit-mutation.xml` | 1 | 0 | 0 | 0 | 10.0s | ❌ 未登记 |" in text
    assert "**判定：❌ 1 个套件未登记" in text
    assert "本页不是绿色证明" in text
    assert "**判定：✅" not in text


def test_local_scope_ignores_stale_junit(tmp_path: Path) -> None:
    """本地宽松模式：范围外的历史 junit（golden、bench）不报未登记，避免训练忽略。"""
    _write_all_passing(tmp_path)
    _write(tmp_path, "junit-golden.xml", _suite(1, 0, 0, 1.0, _passing_cases()))
    text = ci_summary.render(
        ci_summary.collect(tmp_path, expected=_LOCAL_EXPECTED, scope="local"), scope="local"
    )
    assert "junit-golden.xml" not in text
    assert "junit-bench.xml" not in text, "bench 无本地生产者，不在本地核对范围"
    assert "### 未登记套件" not in text
    assert "❌" not in text
    assert (
        "**判定：✅ 本地宽松模式：本地可产出的套件全部通过（cov、perf-smoke）；"
        "bench 无本地生产者，只能由 CI 证明；未核对未登记。**"
    ) in text


def test_local_scope_reports_missing_as_warning(tmp_path: Path) -> None:
    """本地宽松模式：本地可产出套件缺失要可见（⚠️），但不升级为 ❌；未登记不报。"""
    _write(tmp_path, "junit-cov.xml", _suite(1, 0, 0, 10.0, _passing_cases()))
    text = ci_summary.render(
        ci_summary.collect(tmp_path, expected=_LOCAL_EXPECTED, scope="local"), scope="local"
    )
    assert "`junit-perf-smoke.xml`" in text
    assert "| ⚠️ 缺失（本地未运行该步骤时属正常） |" in text
    assert "### 本地缺失（仅提示，不阻断）" in text
    assert "**判定：⚠️ 本地宽松模式：本地可产出的套件中 1 个未产出（perf-smoke，仅提示）；" in text
    assert "bench 无本地生产者，只能由 CI 证明" in text
    assert "### 未登记套件" not in text
    assert "个套件缺失或不可读" not in text, "旧场景：本地缺失不得走 CI 的严格判定"
    assert "❌" not in text


def test_local_verdict_is_built_from_checked_suites(tmp_path: Path) -> None:
    """判定行按实际核对清单拼接：新增本地套件必须出现，防硬编码 cov/perf-smoke。"""
    expected = {**_LOCAL_EXPECTED, "golden": "junit-golden.xml"}
    _write_all_passing(tmp_path)
    _write(tmp_path, "junit-golden.xml", _suite(1, 0, 0, 1.0, _passing_cases()))
    text = ci_summary.render(
        ci_summary.collect(tmp_path, expected=expected, scope="local"), scope="local"
    )
    assert "本地可产出的套件全部通过（cov、perf-smoke、golden）" in text


def test_all_missing_reports_every_expected_suite(tmp_path: Path) -> None:
    """全缺失：每个期望套件都要有 ❌ 行，不能只剩一句「没找到文件」。"""
    text = _render_ci(tmp_path)
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
    text = _render_ci(tmp_path)
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
    text = _render_ci(tmp_path)
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
    text = _render_ci(tmp_path)
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
    text = _render_ci(tmp_path)
    assert "`junit-bench.xml`" in text
    assert "XML 损坏" in text
    assert "❌" in text


def test_no_records_at_all_is_explicitly_not_green(tmp_path: Path) -> None:
    """关闭期望清单时（expected=None），空目录仍走「测试可能没跑」分支。"""
    text = ci_summary.render(ci_summary.collect(tmp_path, expected=None))
    assert "未找到任何 junit 产物" in text
    assert "不是绿色证明" in text
    assert "| 套件 |" not in text


def test_cli_defaults_to_ci_and_accepts_local(tmp_path: Path, capsys) -> None:
    """CLI 默认 fail closed（严格对称差）；本地须显式 --scope local。"""
    _write_all_passing(tmp_path)
    _write(tmp_path, "junit-golden.xml", _suite(1, 0, 0, 1.0, _passing_cases()))
    assert ci_summary.main(["--dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "junit-golden.xml" in out and "未登记" in out
    assert ci_summary.main(["--dir", str(tmp_path), "--scope", "local"]) == 0
    out = capsys.readouterr().out
    assert "junit-golden.xml" not in out
    assert "本地宽松模式" in out


def test_cli_local_scope_checks_make_cov_suites_only(tmp_path: Path, capsys) -> None:
    """CLI local 走 local_expected：bench 不再产生永久 ⚠️，但必须写明只能由 CI 证明。"""
    _write_all_passing(tmp_path)
    assert ci_summary.main(["--dir", str(tmp_path), "--scope", "local"]) == 0
    out = capsys.readouterr().out
    assert "junit-bench.xml" not in out
    assert (
        "**判定：✅ 本地宽松模式：本地可产出的套件全部通过（cov、perf-smoke）；"
        "bench 无本地生产者，只能由 CI 证明；未核对未登记。**"
    ) in out


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


def test_local_expected_parses_make_cov_recipe() -> None:
    """本地清单 = make cov 实际产物；全部已登记，且当前不含 bench（CI-only）。"""
    makefile = (_ROOT / "Makefile").read_text(encoding="utf-8")
    produced = set(
        re.findall(r"--junitxml=out/(junit-[A-Za-z0-9_.-]+\.xml)", _make_recipe(makefile, "cov"))
    )
    local = ci_summary.local_expected()
    assert set(local.values()) == produced, "local_expected 与 make cov 配方漂移"
    assert set(local.values()) <= set(ci_summary.EXPECTED_SUITES.values())
    assert set(local) == {"cov", "perf-smoke"}, (
        "本地生产者集合变了：若 bench 等套件获得本地生产者，须同步判定行与文档里的 CI-only 声明"
    )


def test_local_expected_fails_closed_on_unparseable_makefile(tmp_path: Path) -> None:
    """Makefile 变量化/缺 junitxml 时必须报错，不能静默返回空清单伪装「全部通过」。"""
    makefile = tmp_path / "Makefile"
    makefile.write_text(
        "JUNIT_COV := out/junit-cov.xml\n"
        "cov:\n"
        "\t$(PYTHON) -m pytest --junitxml=$(JUNIT_COV)\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="无法从 make cov 配方解析"):
        ci_summary.local_expected(makefile)

    makefile.write_text("cov:\n\t$(PYTHON) -m pytest\n", encoding="utf-8")
    with pytest.raises(ValueError, match="没有 --junitxml"):
        ci_summary.local_expected(makefile)


def _logical_lines(text: str) -> Iterator[tuple[int, str]]:
    """把反斜杠续行合并成逻辑行（YAML run 块里一条命令可能跨多行）。"""
    start = 0
    buffer = ""
    for lineno, line in enumerate(text.splitlines(), 1):
        if not buffer:
            start = lineno
        buffer += line.rstrip()
        if buffer.endswith("\\"):
            buffer = buffer[:-1] + " "
            continue
        yield start, buffer
        buffer = ""
    if buffer:
        yield start, buffer


_SCOPE_ARG = re.compile(r"--scope(?:=|\s+)([\w-]+)")


def _scope_args(command: str) -> list[str]:
    """提取调用点的 scope 值：同时接受 ``--scope ci`` 与 ``--scope=ci``。"""
    return _SCOPE_ARG.findall(command)


def _scan_ci_invocations(workflows_dir: Path) -> list[tuple[str, int, str]]:
    """扫全部 workflow（.yml/.yaml，与 check_yaml 同范围）的非注释调用点。"""
    invocations: list[tuple[str, int, str]] = []
    for path in sorted(workflows_dir.glob("*.y*ml")):
        for lineno, logical in _logical_lines(path.read_text(encoding="utf-8")):
            # shell/YAML 注释：行首或空白后的 #；引号内的 # 不当作注释
            command = re.split(r"(?:^|\s)#", logical, maxsplit=1)[0]
            if "tools/ci_summary.py" in command:
                invocations.append((path.name, lineno, command.strip()))
    return invocations


def test_ci_invocations_explicitly_use_ci_scope() -> None:
    """所有 workflow 的调用点都必须显式 scope=ci（空格或等号写法均可）。

    默认值只保证「不写 --scope」时 fail closed；未来新增 release.yml/nightly.yml
    若显式写 --scope local，默认值救不了。范围与 check_yaml 一致，全目录扫描，
    新增 workflow 不靠人记得登记反查。只看「是否含有 --scope ci 子串」会把
    `--scope=ci` 误判为缺失，所以按参数解析后精确比较值为 ``["ci"]``。
    """
    invocations = _scan_ci_invocations(_ROOT / ".github" / "workflows")
    assert invocations, "所有 workflow 里找不到 ci_summary 调用点，反查测试已失效"
    offenders = [
        f"{file}:{lineno}: {command}（scope={_scope_args(command) or '缺'}）"
        for file, lineno, command in invocations
        if _scope_args(command) != ["ci"]
    ]
    assert not offenders, "CI 调用点必须且只能带一次 scope=ci：\n" + "\n".join(offenders)


def test_workflow_scan_accepts_equals_form_and_rejects_local(tmp_path: Path) -> None:
    """`--scope=ci` 与 `--scope ci` 等价；`--scope=local` 必须判违规。"""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "equals.yml").write_text(
        "      - run: python tools/ci_summary.py --dir out --scope=ci\n", encoding="utf-8"
    )
    (workflows / "bad.yaml").write_text(
        "      - run: python tools/ci_summary.py --dir out --scope=local\n", encoding="utf-8"
    )
    scopes = {
        file: _scope_args(command) for file, _, command in _scan_ci_invocations(workflows)
    }
    assert scopes == {"bad.yaml": ["local"], "equals.yml": ["ci"]}
    assert [file for file, args in scopes.items() if args != ["ci"]] == ["bad.yaml"]


def test_workflow_scan_catches_bad_invocation_in_any_workflow(tmp_path: Path) -> None:
    """反证：未来新增 workflow 若显式 --scope local（含续行），全目录扫描必须抓住。"""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "ci.yml").write_text(
        "# python tools/ci_summary.py --scope local（注释不算调用）\n"
        "      - run: python tools/ci_summary.py --dir out --scope ci\n",
        encoding="utf-8",
    )
    (workflows / "nightly.yaml").write_text(
        "      - run: |\n"
        "          python tools/ci_summary.py --dir out \\\n"
        "            --scope local\n",
        encoding="utf-8",
    )
    (workflows / "notes.md").write_text(
        "python tools/ci_summary.py --scope local\n", encoding="utf-8"
    )
    invocations = _scan_ci_invocations(workflows)
    assert [file for file, _, _ in invocations] == ["ci.yml", "nightly.yaml"], (
        "非 y*ml 文件不应被扫描；注释行不算调用"
    )
    offenders = [
        (file, command) for file, _, command in invocations if _scope_args(command) != ["ci"]
    ]
    assert len(offenders) == 1, "注释里的违规调用不得误报，违规调用也不得漏报"
    assert offenders[0][0] == "nightly.yaml"
    assert _scope_args(offenders[0][1]) == ["local"], "续行合并后应看到完整命令"
