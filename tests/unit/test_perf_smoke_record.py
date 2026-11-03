"""``tools/perf_smoke_record.py``：记录性能冒烟实测耗时，逼近阈值时提前告警。

背景（评审十回路）：CI 档预算 3.0s，实测 2.62s，余量仅 0.38s。O(n²) 回归能被抓住，
但 runner 变慢/插桩变重会先悄悄吃掉余量。这里锁住「记录 + 连续超档告警」的语义：
**不阻断**（阈值仍是唯一阻断点），只让余量收窄提前可见。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "perf_smoke_record", _ROOT / "tools" / "perf_smoke_record.py"
)
assert _SPEC and _SPEC.loader
perf_smoke_record = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(perf_smoke_record)


def _junit(tmp_path: Path, seconds: float) -> Path:
    path = tmp_path / "junit-perf-smoke.xml"
    path.write_text(
        '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0" '
        f'time="{seconds}">'
        '<testcase classname="tests.golden.test_x" '
        f'name="test_single_month_budget_smoke" time="{seconds}" />'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    return path


def test_missing_junit_records_nothing(tmp_path: Path) -> None:
    """证据缺失时不猜数字：不写样本，返回 None。"""
    history = tmp_path / "perf.jsonl"
    seconds, streak = perf_smoke_record.record(
        junit=tmp_path / "nope.xml", history=history, threshold=2.5
    )
    assert seconds is None
    assert streak == 0
    assert not history.exists(), "读不到耗时时不得写样本（否则编造了证据）"


def test_sample_appended_with_seconds(tmp_path: Path) -> None:
    history = tmp_path / "perf.jsonl"
    seconds, streak = perf_smoke_record.record(
        junit=_junit(tmp_path, 2.62), history=history, threshold=2.5
    )
    assert seconds == 2.62
    assert streak == 1
    sample = json.loads(history.read_text(encoding="utf-8").splitlines()[0])
    assert sample["seconds"] == 2.62


def test_streak_counts_only_consecutive_over_threshold(tmp_path: Path) -> None:
    """连续超档才算告警；中间有一次回落就清零（避免历史旧账长期报警）。"""
    history = tmp_path / "perf.jsonl"
    for value in (2.6, 2.7, 2.1, 2.6):
        perf_smoke_record.record(junit=_junit(tmp_path, value), history=history, threshold=2.5)
    samples = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines()]
    assert perf_smoke_record.consecutive_over(samples, 2.5) == 1
    assert perf_smoke_record.consecutive_over(samples[:-1], 2.5) == 0


def test_main_writes_summary_and_warns_on_streak(tmp_path: Path, monkeypatch) -> None:
    summary = tmp_path / "summary.md"
    summary.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    history = tmp_path / "perf.jsonl"

    for _ in range(2):
        rc = perf_smoke_record.main(
            [
                "--junit", str(_junit(tmp_path, 2.62)),
                "--history", str(history),
                "--warn-above", "2.5",
                "--warn-streak", "2",
            ]
        )
        assert rc == 0, "这是观察装置，不得把 CI 弄红"

    text = summary.read_text(encoding="utf-8")
    assert "本次：`2.62s`" in text
    assert "连续超档：`2` 次" in text
    assert "预算余量在收窄" in text

