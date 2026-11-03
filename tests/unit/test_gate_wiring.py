"""``make gate`` 的接线锁（2026-11-03 评审九回路）。

事故：``gate`` 只跑 ``test-fast``（不采集覆盖率），然后 ``coverage report``
读上一次遗留的 ``.coverage``，报出 75%；再跟 ``|| true``，覆盖率门禁名存实亡。
fresh ``make cov`` 实测 84%——75% 是旧数据，不是当前代码。

本文件锁住三件事，防止接线被改回去：

1. ``gate`` 依赖 ``cov``（pytest --cov 新鲜采集），不再依赖不采覆盖率的 ``test-fast``；
2. ``coverage report --fail-under=80`` 不得跟 ``|| true``；
3. CI 中确定性门禁只能走 ``tools/determinism_gate.py``，``make determinism``
   在 ``CI=true`` 时必须拒绝。
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_MAKEFILE = (_ROOT / "Makefile").read_text(encoding="utf-8")
_CI = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def _target(name: str) -> tuple[list[str], list[str]]:
    """返回 (依赖列表, recipe 行列表)；找不到目标直接失败。"""
    lines = _MAKEFILE.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(f"{name}:"):
            deps = line.split(":", 1)[1].split()
            recipe: list[str] = []
            for following in lines[index + 1 :]:
                if not following.startswith("\t"):
                    break
                recipe.append(following[1:])
            return deps, recipe
    raise AssertionError(f"Makefile 缺少目标 {name}")


def test_gate_uses_fresh_coverage_not_test_fast() -> None:
    deps, _ = _target("gate")
    assert "cov" in deps, "gate 必须依赖 cov，由 pytest --cov 新鲜写 .coverage"
    assert "test-fast" not in deps, "test-fast 不采集覆盖率，不能作为 coverage report 的数据源"


def test_cov_collects_then_enforces_threshold() -> None:
    _, recipe = _target("cov")
    text = "\n".join(recipe)
    assert "--cov" in text and "pytest" in text, "cov 必须自己采集覆盖率"
    assert "coverage report --fail-under=80" in text, "覆盖率阈值必须由 cov 自己阻断"


def test_coverage_failure_is_never_swallowed() -> None:
    _, gate_recipe = _target("gate")
    assert "|| true" not in "\n".join(gate_recipe), "gate 不得吞掉任何失败"
    for line in _MAKEFILE.splitlines():
        if "coverage report" in line:
            assert "|| true" not in line, f"覆盖率门禁不得被 || true 吞掉：{line.strip()}"


def test_determinism_refuses_direct_ci_call() -> None:
    _, recipe = _target("determinism")
    text = "\n".join(recipe)
    assert "CI" in text and "exit 64" in text, "CI=true 时 make determinism 必须拒绝运行"
    assert "make gate" in text, "拒绝信息必须指向唯一 CI 入口 make gate"


def test_ci_determinism_step_uses_adapter_only() -> None:
    assert "tools/determinism_gate.py" in _CI
    assert "make determinism" not in _CI, "CI 不得直接调用会绕过适配层的 make determinism"
    assert "determinism_probe.py --gate" not in _CI, "CI 不得直接调用原始探针"
