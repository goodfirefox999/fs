"""确定性门禁的退出码语义（2026-11-03）。

门禁只要有一处含糊，就会重演"把机器慢读成算法坏"的误判。故这里逐个钉死：

- 指纹不一致 → 1（PRODUCT_FAIL，产品侧不确定）
- 耗时异常   → 2（ENV_SUSPECT，先怀疑机器，不许判产品）
- 正常       → 0

每个用例都配反证：让条件成立时确实报警，条件不成立时确实沉默。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "determinism_probe", Path(__file__).resolve().parents[2] / "tools" / "determinism_probe.py"
)
assert _SPEC and _SPEC.loader
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


@pytest.fixture
def baseline(tmp_path: Path, monkeypatch) -> Path:
    path = tmp_path / "determinism_baseline.json"
    monkeypatch.setattr(probe, "BASELINE_PATH", path)
    return path


class TestTimingCheck:
    def test_slow_run_returns_env_suspect(self, baseline: Path, capsys) -> None:
        """超基线 2 倍 → 2（ENV_SUSPECT），且**不得**返回 1。"""
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text('{"samples_ms": [100.0, 110.0, 105.0]}', encoding="utf-8")
        rc = probe._timing_check(300.0)
        assert rc == 2
        assert "ENV_SUSPECT" in capsys.readouterr().err

    def test_fast_run_is_silent(self, baseline: Path, capsys) -> None:
        """反证：未超阈值必须沉默并返回 0。"""
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text('{"samples_ms": [100.0, 110.0, 105.0]}', encoding="utf-8")
        rc = probe._timing_check(150.0)
        assert rc == 0
        assert "ENV_SUSPECT" not in capsys.readouterr().err

    def test_first_run_records_baseline(self, baseline: Path) -> None:
        """没有基线时记录样本，不报警。"""
        assert probe._timing_check(120.0) == 0
        assert baseline.exists()
        assert "120.0" in baseline.read_text(encoding="utf-8")

    def test_corrupt_baseline_does_not_alarm(self, baseline: Path) -> None:
        """基线损坏 → 当作首次运行，不能因为基线坏了就判 ENV_SUSPECT。"""
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text("{not json", encoding="utf-8")
        assert probe._timing_check(999.0) == 0

    def test_samples_are_capped(self, baseline: Path) -> None:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text('{"samples_ms": [' + ",".join(["100.0"] * 50) + "]}", encoding="utf-8")
        probe._timing_check(100.0)
        data = baseline.read_text(encoding="utf-8")
        assert data.count("100.0") <= probe._BASELINE_SAMPLES + 1


class TestGateExitCodes:
    def test_two_seeds_are_deterministic(self) -> None:
        """真实门禁：两个 seed 指纹一致 → 0。"""
        assert probe._gate("0,1") == 0

    def test_single_seed_is_invalid(self) -> None:
        """门禁至少两个 seed，否则"一致"没有意义。"""
        assert probe._gate("0") == 1

    def test_gate_prints_fingerprint(self, capsys) -> None:
        assert probe._gate("0,1") == 0
        out = capsys.readouterr().out
        assert "DETERMINISTIC" in out

    def test_fingerprint_covers_facts_and_eval_both(self) -> None:
        """指纹必须同时覆盖事实层与判定层——只盖一层会让另一层的漂移漏网。"""
        parts = probe.fingerprint()
        assert any(k.endswith(".facts") for k in parts)
        assert any(k.endswith(".eval") for k in parts)
