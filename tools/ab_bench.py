#!/usr/bin/env python3
"""A/B 交错对照：把「代码边际」从「环境噪声」里分出来。

A = 正常 ``derive_facts``（含正五行扶山 facts）
B = 同一路径，但把 ``derive_zhengwuxing_facts`` 换为空壳

每轮 A/B 相邻执行，并在轮次间交换先后顺序（AB / BA 交替），
让宿主负载漂移同时作用在两侧；输出每轮差值、中位数与占比。
**这不是 gate，也不改预算**；它只产出「边际耗时」证据。

用法::

    python tools/ab_bench.py                 # 3 轮，全年 4380 候选
    python tools/ab_bench.py --rounds 5
    python tools/ab_bench.py --days 30 --rounds 2

退出码：正常完成 = 0；参数/执行错误 = 1。
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
for _pkg in ("core-time", "core-symbol", "core-rule", "core-eval", "app-zeri"):
    _src = str(REPO_ROOT / _pkg / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app_zeri.generator import generate  # noqa: E402
from app_zeri.schemas import SiteSpec, TaskSpec  # noqa: E402
from core_symbol import registry as symbol_registry  # noqa: E402

SITE = SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26)
TASK = TaskSpec(kind="修造", strictness="strict")


def _stub_zhengwuxing(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
    return {"status": "stub", "note": "ab_bench: 故意跳过的正五行扶山 facts"}


def _run_once(start: date, end: date, top: int) -> tuple[float, int]:
    began = time.perf_counter()
    result = generate(
        start=start,
        end=end,
        site=SITE,
        task=TASK,
        allow_unverified=True,
        top=top,
    )
    return time.perf_counter() - began, result.total_candidates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A/B 交错性能对照（不改预算）")
    parser.add_argument("--rounds", type=int, default=3, help="A/B 轮数（默认 3）")
    parser.add_argument("--days", type=int, default=365, help="窗口天数（默认 365）")
    parser.add_argument("--start", default="2027-01-01", help="起始日期（默认 2027-01-01）")
    parser.add_argument("--top", type=int, default=20, help="生成器 top（默认 20）")
    args = parser.parse_args(argv)
    if args.rounds < 1 or args.days < 1:
        print("rounds/days 必须 >= 1", file=sys.stderr)
        return 1

    start = date.fromisoformat(args.start)
    end = start + timedelta(days=args.days - 1)
    expected = args.days * 12

    original = symbol_registry.derive_zhengwuxing_facts
    rows: list[tuple[int, float, float, float, int]] = []
    try:
        # 预热：两侧各跑一次短窗口，摊掉模块导入/数据文件缓存/星历初始化，
        # 否则第一轮 A 会把一次性的初始化成本算成正五行边际。
        warm_end = start + timedelta(days=min(2, args.days) - 1)
        _run_once(warm_end, warm_end, args.top)
        symbol_registry.derive_zhengwuxing_facts = _stub_zhengwuxing
        _run_once(warm_end, warm_end, args.top)
        symbol_registry.derive_zhengwuxing_facts = original
        print("预热完成（A/B 各 1 日）")

        for round_no in range(1, args.rounds + 1):
            if round_no % 2 == 1:
                a_elapsed, a_count = _run_once(start, end, args.top)
                symbol_registry.derive_zhengwuxing_facts = _stub_zhengwuxing
                b_elapsed, b_count = _run_once(start, end, args.top)
                symbol_registry.derive_zhengwuxing_facts = original
            else:
                symbol_registry.derive_zhengwuxing_facts = _stub_zhengwuxing
                b_elapsed, b_count = _run_once(start, end, args.top)
                symbol_registry.derive_zhengwuxing_facts = original
                a_elapsed, a_count = _run_once(start, end, args.top)
            if a_count != expected or b_count != expected:
                print(
                    f"候选数异常：A={a_count} B={b_count} 期望={expected}",
                    file=sys.stderr,
                )
                return 1
            load1 = os.getloadavg()[0] if hasattr(os, "getloadavg") else float("nan")
            rows.append((round_no, a_elapsed, b_elapsed, load1, a_count))
            print(
                f"第 {round_no} 轮：A={a_elapsed:.2f}s  B={b_elapsed:.2f}s  "
                f"A-B={a_elapsed - b_elapsed:+.2f}s  load1={load1:.2f}"
            )
    finally:
        symbol_registry.derive_zhengwuxing_facts = original

    a_times = [row[1] for row in rows]
    b_times = [row[2] for row in rows]
    deltas = [row[1] - row[2] for row in rows]
    a_median = statistics.median(a_times)
    b_median = statistics.median(b_times)
    delta_median = statistics.median(deltas)
    share = (delta_median / a_median * 100) if a_median else 0.0
    print("")
    print(f"窗口：{start} → {end}（{expected} 候选），轮数 {args.rounds}")
    print(f"A 中位数：{a_median:.3f}s")
    print(f"B 中位数：{b_median:.3f}s")
    print(f"边际（A-B）中位数：{delta_median:+.3f}s（占 A 的 {share:.1f}%）")
    print(
        "> 边际耗时只用于判断「是否值得优化」；"
        "预算判定仍由 tests/bench/test_perf.py 的绝对预算与相对门禁负责。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
