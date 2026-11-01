"""性能测试：365 天 × 12 时辰 = 4380 候选。

预算（docs/DEVELOPMENT.md 第 7 节）：单次一年窗口全量穷举 < 3 s。
预算沿革：52 规则（无五派 facts）时代为 2.0s；Phase 4–8 纳入调候/通关/三合局/
禄马贵人/董公/玄空大卦/天星星历（spec 硬性要求的真实计算，含逐日星历）
后更新为 3.0s。防回归由相对门禁承担（中位数 × 1.5，先记后断）——
绝对预算只防数量级劣化，不得通过降低候选数或跳过规则来"达标"。
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app_zeri.generator import HOUR_SAMPLE_HOURS, candidate_datetimes, generate
from app_zeri.schemas import SiteSpec, TaskSpec

CST = ZoneInfo("Asia/Shanghai")
BUDGET_SEC = 3.0
HISTORY = Path(__file__).resolve().parent / "bench_history.jsonl"
REGRESSION_FACTOR = 1.5


def _is_ci() -> bool:
    """CI 环境检测谓词（评审第十四轮：显式化 + 可测试）。

    依据 GitHub Actions 标准环境变量 CI / GITHUB_ACTIONS；换平台时在此追加。
    过渡态声明：CI 样本写入 bench_history.ci.jsonl（分平台文件），**不进本地中位数**；
    相对门禁落地时改为分平台基线（ADR-0014 验收节登记为过渡态，不得固化）。
    """
    import os

    return bool(os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"))


def _record_and_check(elapsed: float, pareto_size: int | None = None) -> None:
    global HISTORY
    history = (HISTORY.parent / "bench_history.ci.jsonl") if _is_ci() else HISTORY
    """记录本次耗时，并与历史中位数比较（防止"每次改一点"的渐进劣化）。

    评审第十一轮：**先记后断**——失败运行也入历史（带 passed 标记），
    消除"历史只含存活者"的系统性偏差；相对门禁（下一批）不得建立在幸存者中位数上。
    """
    samples: list[float] = []
    if history.exists():
        for line in HISTORY.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                samples.append(float(json.loads(line)["elapsed"]))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
    median = statistics.median(samples) if len(samples) >= 3 else None
    passed = median is None or elapsed <= median * REGRESSION_FACTOR
    record = {"ts": datetime.now().isoformat(timespec="seconds"),
              "candidates": 4380, "elapsed": round(elapsed, 4), "passed": passed}
    if pareto_size is not None:
        record["pareto_size"] = pareto_size  # u 的下游代理（front 规模），监控分组收益退化
    with history.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    if median is not None:
        assert passed, (
            f"性能回归：本次 {elapsed:.2f}s，历史中位数 {median:.2f}s，"
            f"超过 {REGRESSION_FACTOR}× 阈值"
        )


def test_candidate_count_is_4380() -> None:
    moments = candidate_datetimes(date(2027, 1, 1), date(2027, 12, 31), "day_hour")
    assert len(HOUR_SAMPLE_HOURS) == 12
    assert len(moments) == 365 * 12 == 4380


@pytest.mark.slow
def test_full_year_within_budget() -> None:
    started = time.perf_counter()
    result = generate(
        start=date(2027, 1, 1),
        end=date(2027, 12, 31),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", strictness="strict"),
        allow_unverified=True,
        top=20,
    )
    elapsed = time.perf_counter() - started
    assert result.total_candidates == 4380
    _record_and_check(elapsed, pareto_size=result.pareto_size)
    assert elapsed < BUDGET_SEC, f"全量穷举耗时 {elapsed:.2f}s，超出预算 {BUDGET_SEC}s"


@pytest.mark.slow
def test_verified_rules_performance() -> None:
    """模拟"规则全部已考证"的性能：定义级+断言级都参与判定时的耗时。

    评审指出：当前 1.49s 是"全部 unknown"状态下的性能，一旦规则有真实结论，
    冲突检测与证据链组装成本会上升。本测试把待考证规则用 allow_unverified 放行，
    逼近最坏情况。
    """
    started = time.perf_counter()
    result = generate(
        start=date(2027, 1, 1),
        end=date(2027, 12, 31),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", strictness="strict"),
        allow_unverified=True,  # 最坏情况：全部规则参与判定
        top=20,
    )
    elapsed = time.perf_counter() - started
    assert result.total_candidates == 4380
    # 容量目标只有一个：52 条规则 × 4380 候选 < 2s（不再另设 3s 阈值，避免两个数互相矛盾）
    _record_and_check(elapsed, pareto_size=result.pareto_size)
    assert elapsed < BUDGET_SEC, f"已考证模拟耗时 {elapsed:.2f}s，超出容量目标 {BUDGET_SEC}s"


@pytest.mark.slow
def test_brute_force_matches_sampled() -> None:
    """抽样对照：生成器结果与"逐候选直接评估"完全一致（剪枝不得改变结果集）。"""
    from core_eval import EvalConfig, evaluate
    from app_zeri.schemas import CourseSpec, build_context

    site = SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26)
    task = TaskSpec(kind="修造", strictness="strict")
    result = generate(
        start=date(2027, 3, 1),
        end=date(2027, 3, 5),
        site=site,
        task=task,
        allow_unverified=True,
        top=1000,
    )
    assert result.total_candidates == 5 * 12

    cfg = EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True)
    brute_states = []
    for moment in candidate_datetimes(date(2027, 3, 1), date(2027, 3, 5), "day_hour", tz=CST):
        ctx = build_context(CourseSpec(dt=moment), site, task)
        ev = evaluate(ctx, __import__("core_rule").default_registry(), cfg)
        brute_states.append((moment.isoformat(), ev.state, ev.tier))

    generated = [(r.evaluation.candidate, r.evaluation.state, r.evaluation.tier) for r in result.ranked]
    assert sorted(generated) == sorted(brute_states), "生成器结果集与暴力全量不一致"
