"""``tools/check_yaml.py``：workflow YAML 全文件语法校验（2026-11-03）。

背景：只修一个 ``C19:`` 非法步骤名，不等于整个 workflow 合法。YAML 的
``key: value`` 在 value 含冒号空格时同样会解析失败；这里用真实 workflow
做回归锚点，并用反例证明校验器确实会报警而不是恒绿。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_yaml", Path(__file__).resolve().parents[2] / "tools" / "check_yaml.py"
)
assert _SPEC and _SPEC.loader
check_yaml = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(check_yaml)


def test_all_workflow_files_are_valid_yaml() -> None:
    paths = check_yaml.default_paths()
    assert paths, "至少要有一个 .github/workflows/*.yml 参与校验"
    assert check_yaml.check(paths) == []


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text("jobs:\n  test:\n    steps: [unclosed\n", encoding="utf-8")
    errors = check_yaml.check([bad])
    assert errors and "YAML 语法错误" in errors[0]


def test_empty_file_is_reported(tmp_path: Path) -> None:
    empty = tmp_path / "empty.yml"
    empty.write_text("", encoding="utf-8")
    errors = check_yaml.check([empty])
    assert errors and "空文件" in errors[0]


def test_no_files_is_reported() -> None:
    errors = check_yaml.check([])
    assert errors and "没有找到" in errors[0]


def test_main_returns_nonzero_on_invalid(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.yml"
    bad.write_text("key: [unclosed\n", encoding="utf-8")
    assert check_yaml.main([str(bad)]) == 1
    assert "YAML 校验失败" in capsys.readouterr().err
