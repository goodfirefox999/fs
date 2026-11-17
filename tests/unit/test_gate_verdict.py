"""门禁三态（2026-11-04 第五层）：pass / violation / undetermined。

验收信号：
- 一个 skip 使门禁退出 4（不是 0）；
- 真实失败退出 1；
- 全通过退出 0；
- 每一项无法判定都写进 ``out/undetermined.json``，不静默吞掉。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "gate_verdict", _ROOT / "tools" / "gate_verdict.py"
)
assert _SPEC and _SPEC.loader
gv = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gv)


def _suite_xml(
    tests: int,
    *,
    failures: int = 0,
    errors: int = 0,
    skipped: int = 0,
    undetermined: int = 0,
    skipped_case: bool = False,
    failed_case: bool = False,
) -> str:
    cases = []
    for index in range(tests):
        if index == 0 and failed_case:
            cases.append(
                f'<testcase classname="tests.x" name="test_{index}" time="0.1">'
                '<failure message="boom" /></testcase>'
            )
        elif index == 0 and skipped_case:
            cases.append(
                f'<testcase classname="tests.x" name="test_{index}" time="0.0">'
                '<skipped message="环境不满足" /></testcase>'
            )
        else:
            cases.append(f'<testcase classname="tests.x" name="test_{index}" time="0.1" />')
    return (
        f'<testsuites><testsuite tests="{tests}" failures="{failures}" errors="{errors}" '
        f'skipped="{skipped}" undetermined="{undetermined}" time="1.0">'
        + "".join(cases)
        + "</testsuite></testsuites>"
    )


def _write_junit(tmp_path: Path, name: str, body: str) -> None:
    (tmp_path / name).write_text(body, encoding="utf-8")


def _write_passing(tmp_path: Path) -> None:
    for name in ("junit-cov.xml", "junit-perf-smoke.xml"):
        _write_junit(tmp_path, name, _suite_xml(1))


def test_all_pass_is_exit_0(tmp_path: Path) -> None:
    _write_passing(tmp_path)
    rc, payload = gv.run(tmp_path, scope="local", determinism_rc=0)
    assert rc == 0
    assert payload["verdict"] == "pass"
    report = json.loads((tmp_path / "undetermined.json").read_text(encoding="utf-8"))
    assert report["undetermined_count"] == 0


def test_one_skip_makes_gate_undetermined(tmp_path: Path) -> None:
    """**验收信号**：一个 skip 使门禁退出 4，且不是 violation。"""
    _write_passing(tmp_path)
    _write_junit(tmp_path, "junit-cov.xml", _suite_xml(2, skipped=1, skipped_case=True))
    rc, payload = gv.run(tmp_path, scope="local", determinism_rc=0)
    assert rc == 4
    assert payload["verdict"] == "undetermined"
    assert any(item["kind"] == "skipped" for item in payload["items"])
    report = json.loads((tmp_path / "undetermined.json").read_text(encoding="utf-8"))
    assert report["undetermined_count"] >= 1
    # 只报数量无法逐项登记：skip 的用例名与原因必须落盘
    skipped = next(item for item in report["items"] if item["kind"] == "skipped")
    assert "test_0" in skipped["detail"]
    assert "环境不满足" in skipped["detail"]


def test_real_failure_is_exit_1(tmp_path: Path) -> None:
    """**验收信号**：真实失败退出 1，不得被 skip/缺失掩盖。"""
    _write_passing(tmp_path)
    _write_junit(tmp_path, "junit-cov.xml", _suite_xml(1, failures=1, failed_case=True))
    rc, payload = gv.run(tmp_path, scope="local", determinism_rc=0)
    assert rc == 1
    assert payload["verdict"] == "violation"
    assert any(item["kind"] == "test_failure" for item in payload["violations"])


def test_missing_local_suite_is_undetermined(tmp_path: Path) -> None:
    _write_junit(tmp_path, "junit-cov.xml", _suite_xml(1))
    rc, payload = gv.run(tmp_path, scope="local", determinism_rc=0)
    assert rc == 4
    assert any(item["kind"] == "missing_local" for item in payload["items"])


def test_determinism_output_fail_is_undetermined(tmp_path: Path) -> None:
    _write_passing(tmp_path)
    rc, payload = gv.run(tmp_path, scope="local", determinism_rc=4)
    assert rc == 4
    assert any(item["kind"].startswith("determinism") for item in payload["items"])


def test_determinism_product_fail_is_violation(tmp_path: Path) -> None:
    _write_passing(tmp_path)
    rc, payload = gv.run(tmp_path, scope="local", determinism_rc=1)
    assert rc == 1
    assert any(item["kind"] == "product_fail" for item in payload["violations"])


def test_cli_reports_count(tmp_path: Path, capsys) -> None:
    _write_passing(tmp_path)
    assert gv.main(["--dir", str(tmp_path), "--scope", "local", "--determinism-rc", "0"]) == 0
    out = capsys.readouterr().out
    assert "本次无无法判定项" in out
    assert "pass（退出码 0）" in out
