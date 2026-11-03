"""``tools/coverage_ratchet.py``：包级 + 文件级覆盖率门禁（2026-11-03 评审十/十一回路）。

要防的两层漏水：

- 整体 84% 替 app-zeri 68% 背书（包级地板）；
- 包级 68% 替 cli.py 34% 背书（文件级地板：包内低于 target 的文件必须单列）。

工具本身读 ``.coverage``，所以这里测纯函数与配置不变式；真实门禁由
``make cov`` 跑工具本身验证。

**新增包的操作流程**：``pyproject.toml`` 的 ``[tool.coverage.run].source`` 加包
→ ``make cov`` 得实测 → ``coverage_ratchet.yaml`` 的 ``modules`` 加
``path/min/target`` → 该包内低于 target 的文件在 ``files`` 逐个登记
``min=floor(实测)`` → ``make gate``。本文件的
``test_baseline_covers_every_coverage_source`` 会在第一步之后立刻变红，
提示补第 3/4 步；不要用 skip 绕过。
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "coverage_ratchet", _ROOT / "tools" / "coverage_ratchet.py"
)
assert _SPEC and _SPEC.loader
ratchet = importlib.util.module_from_spec(_SPEC)
# 必须先进 sys.modules：Python 3.14 的 dataclass 解析注解时会查 cls.__module__。
sys.modules[_SPEC.name] = ratchet
_SPEC.loader.exec_module(ratchet)

_BASELINE = ratchet.load_baseline()


def _row(
    name: str,
    minimum: int,
    actual: float | None,
    *,
    target: int = 90,
    kind: str = "module",
    error: str | None = None,
) -> ratchet.Row:
    return ratchet.Row(
        name=name,
        path=name,
        minimum=minimum,
        target=target,
        actual=actual,
        kind=kind,
        error=error,
    )


def test_baseline_covers_every_coverage_source() -> None:
    """新增包进了 coverage.source 却没有 ratchet 基线，等于又开一个盲区。"""
    pyproject = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    sources = set(pyproject["tool"]["coverage"]["run"]["source"])
    assert {spec.path for spec in _BASELINE.modules.values()} == sources
    assert set(_BASELINE.modules) == {
        "core-time",
        "core-symbol",
        "core-rule",
        "core-eval",
        "app-zeri",
    }


def test_targets_are_declared_and_app_zeri_target_is_80() -> None:
    for name, spec in _BASELINE.modules.items():
        assert 0 <= spec.minimum <= 100, name
        assert 0 <= spec.target <= 100, name
    assert _BASELINE.modules["app-zeri"].target == 80


def test_three_known_low_files_have_file_floors() -> None:
    """cli/case_runner/report 是评审点名的真实缺口，不能只靠包级地板。"""
    for path in (
        "app-zeri/src/app_zeri/cli.py",
        "app-zeri/src/app_zeri/case_runner.py",
        "app-zeri/src/app_zeri/report.py",
    ):
        assert path in _BASELINE.files, f"{path} 缺文件级地板"
    for path, spec in _BASELINE.files.items():
        assert spec.minimum <= spec.target, path
        assert any(path.startswith(spec.path + "/") for spec in _BASELINE.modules.values())


def test_new_low_file_without_floor_is_a_failure() -> None:
    """包内新增 10% 的文件但没登记文件地板 → 必须阻断，不能静默漏网。"""
    measured = {
        "app-zeri/src/app_zeri/cli.py": 34.0,  # 已登记
        "app-zeri/src/app_zeri/new_module.py": 10.0,  # 未登记
        "app-zeri/src/app_zeri/verifier.py": 95.0,  # 高于目标，不需要登记
    }
    problems = ratchet.missing_file_baselines(_BASELINE, measured)
    assert len(problems) == 1
    assert "new_module.py" in problems[0]
    assert "低于包目标 80%" in problems[0]


def test_below_floor_is_a_failure() -> None:
    problems = ratchet.failures([_row("app-zeri", 68, 67.9, target=80)])
    assert len(problems) == 1
    assert "app-zeri" in problems[0] and "67.90%" in problems[0]
    assert "只许升不许降" in problems[0]


def test_exactly_at_floor_passes() -> None:
    assert ratchet.failures([_row("core-rule", 92, 92.0)]) == []


def test_missing_data_is_a_failure_not_a_skip() -> None:
    problems = ratchet.failures(
        [_row("core-eval", 92, None, error="无覆盖率数据")]
    )
    assert len(problems) == 1
    assert "无覆盖率数据" in problems[0]


def test_render_shows_module_and_file_sections() -> None:
    rows = [
        _row("core-time", 96, 96.2),
        _row(
            "app-zeri/src/app_zeri/cli.py",
            34,
            34.1,
            target=80,
            kind="file",
        ),
        _row(
            "app-zeri/src/app_zeri/new.py",
            40,
            30.0,
            target=80,
            kind="file",
        ),
    ]
    text = ratchet.render(rows)
    assert "模块" in text and "文件" in text
    assert "core-time" in text and "cli.py" in text
    assert text.count("✅") == 2
    assert text.count("❌") == 1


def test_loose_baseline_warns_but_does_not_fail() -> None:
    """> 2pp 只告警：防止故意写低地板换绿色，但不把「进步」判成失败。"""
    loose = ratchet.loose_baselines([_row("app-zeri", 50, 68.1, target=80)])
    assert len(loose) == 1
    assert "基线过松" not in loose[0]  # 文案由 main 加，函数只给事实
    assert "18.1pp" in loose[0]
    assert ratchet.loose_baselines([_row("app-zeri", 67, 68.1, target=80)]) == []


def test_update_raises_module_and_file_floors_to_current_floor() -> None:
    baseline = ratchet.Baseline(
        modules={
            "app-zeri": ratchet.ModuleSpec(
                name="app-zeri", path="app-zeri/src/app_zeri", minimum=65, target=80
            )
        },
        files={
            "app-zeri/src/app_zeri/cli.py": ratchet.FileSpec(
                path="app-zeri/src/app_zeri/cli.py", minimum=30, target=80
            )
        },
    )
    rows = [
        _row("app-zeri", 65, 68.06, target=80),
        _row("app-zeri/src/app_zeri/cli.py", 30, 34.15, target=80, kind="file"),
    ]
    updated, changes = ratchet.updated_baseline(baseline, rows)
    assert updated.modules["app-zeri"].minimum == 68
    assert updated.files["app-zeri/src/app_zeri/cli.py"].minimum == 34
    assert changes == [
        "app-zeri: 65% → 68%",
        "app-zeri/src/app_zeri/cli.py: 30% → 34%",
    ]


def test_update_never_lowers_baseline() -> None:
    baseline = ratchet.Baseline(
        modules={
            "core-rule": ratchet.ModuleSpec(
                name="core-rule", path="core-rule/src/core_rule", minimum=95, target=90
            )
        },
        files={},
    )
    updated, changes = ratchet.updated_baseline(
        baseline, [_row("core-rule", 95, 80.0)]
    )
    assert updated.modules["core-rule"].minimum == 95
    assert changes == []


def test_bad_baseline_float_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "baseline.yaml"
    bad.write_text(
        "modules:\n"
        "  core-time:\n"
        "    path: core-time/src/core_time\n"
        "    min: 95.5\n"
        "    target: 90\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="min 必须是 0..100 的整数"):
        ratchet.load_baseline(bad)


def test_file_floor_above_target_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "baseline.yaml"
    bad.write_text(
        "modules:\n"
        "  app-zeri:\n"
        "    path: app-zeri/src/app_zeri\n"
        "    min: 60\n"
        "    target: 80\n"
        "files:\n"
        "  app-zeri/src/app_zeri/cli.py:\n"
        "    min: 90\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="高于包目标"):
        ratchet.load_baseline(bad)


def test_file_outside_modules_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "baseline.yaml"
    bad.write_text(
        "modules:\n"
        "  app-zeri:\n"
        "    path: app-zeri/src/app_zeri\n"
        "    min: 60\n"
        "    target: 80\n"
        "files:\n"
        "  tools/orphan.py:\n"
        "    min: 10\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="不在任何 modules 路径下"):
        ratchet.load_baseline(bad)


def test_yaml_file_floors_are_all_below_their_targets() -> None:
    raw = yaml.safe_load(
        (_ROOT / "tools" / "coverage_ratchet.yaml").read_text(encoding="utf-8")
    )
    for name, spec in raw["modules"].items():
        assert isinstance(spec["min"], int) and not isinstance(spec["min"], bool), name
        assert isinstance(spec["target"], int) and not isinstance(spec["target"], bool), name
    for path, spec in raw["files"].items():
        assert isinstance(spec["min"], int) and not isinstance(spec["min"], bool), path
