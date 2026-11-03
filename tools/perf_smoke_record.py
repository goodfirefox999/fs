#!/usr/bin/env python3
"""记录每次性能冒烟实测耗时，并在逼近阈值时提前告警（评审十回路）。

背景：CI 档预算 3.0s，实测 2.62s——余量只有 0.38s。O(n²) 回归（9s）能抓住，
但 runner 变慢或插桩变重（新增测试）会先悄悄吃掉余量再踩线。等它红了才发现
「3.0s 早就不够了」是最贵的发现方式。

做法：从 ``out/junit-perf-smoke.xml`` 读实测耗时，追加一行到 ``out/perf-smoke.jsonl``，
写进 ``$GITHUB_STEP_SUMMARY``；连续 N 次超过 ``--warn-above`` 时打 ``::warning``。
**不阻断**：这是观察装置，不是门禁——阈值仍是唯一的阻断点。

用法::

    python tools/perf_smoke_record.py --junit out/junit-perf-smoke.xml --warn-above 2.5
"""

from __future__ import annotations

import argparse
import json
import os
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

__all__ = ["read_seconds", "record", "consecutive_over"]


def read_seconds(junit: Path, case_contains: str = "budget_smoke") -> float | None:
    """从 junit 读目标用例耗时；读不到返回 None（缺失按「无证据」处理，不猜）。"""
    if not junit.exists():
        return None
    try:
        root = ET.parse(junit).getroot()
    except ET.ParseError:
        return None
    for case in root.iter("testcase"):
        if case_contains in (case.get("name") or ""):
            try:
                return float(case.get("time", ""))
            except (TypeError, ValueError):
                return None
    return None


def consecutive_over(samples: list[dict], threshold: float) -> int:
    """从最新往回数，连续有多少次超过阈值。"""
    count = 0
    for sample in reversed(samples):
        if float(sample.get("seconds", 0)) > threshold:
            count += 1
        else:
            break
    return count


def record(
    junit: Path,
    history: Path,
    threshold: float,
    warn_streak: int = 2,
    summary_path: Path | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[float | None, int]:
    """追加一条样本；返回 (本次耗时, 连续超阈次数)。耗时不可读时不写样本。"""
    env = environ if environ is not None else os.environ
    seconds = read_seconds(junit)
    if seconds is None:
        return None, 0

    history.parent.mkdir(parents=True, exist_ok=True)
    sample = {
        "seconds": round(seconds, 3),
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "ref": env.get("GITHUB_REF_NAME", ""),
        "sha": env.get("GITHUB_SHA", "")[:12],
        "run_id": env.get("GITHUB_RUN_ID", ""),
    }
    with history.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(sample, ensure_ascii=False) + "\n")

    samples: list[dict] = []
    for line in history.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            samples.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    streak = consecutive_over(samples, threshold)
    return seconds, streak


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", default="out/junit-perf-smoke.xml")
    parser.add_argument("--history", default="out/perf-smoke.jsonl")
    parser.add_argument("--warn-above", type=float, default=2.5)
    parser.add_argument("--warn-streak", type=int, default=2)
    args = parser.parse_args(argv)

    seconds, streak = record(
        junit=Path(args.junit),
        history=Path(args.history),
        threshold=args.warn_above,
        warn_streak=args.warn_streak,
    )
    if seconds is None:
        print(f"perf_smoke_seconds: 不可读（{args.junit}）——按无证据处理，不记录")
        return 0

    print(f"perf_smoke_seconds: {seconds:.2f}（观察档 {args.warn_above:.2f}s）")
    lines = [
        "## 性能冒烟实测",
        "",
        f"- 本次：`{seconds:.2f}s`",
        f"- 观察档：`{args.warn_above:.2f}s`；连续超档：`{streak}` 次",
    ]
    if streak >= args.warn_streak:
        msg = (
            f"perf smoke 连续 {streak} 次超过 {args.warn_above:.2f}s "
            f"（本次 {seconds:.2f}s）——预算余量在收窄，考虑上浮 CI 档或查回归"
        )
        print(f"::warning title=PERF_SMOKE_NEAR_BUDGET::{msg}")
        lines += ["", f"⚠️ {msg}"]

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
