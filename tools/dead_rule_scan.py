#!/usr/bin/env python3
"""C21（评审第十一/十二轮批准）：死规则扫描——"适用域内零命中"检测。

统计口径（写死，评审第十二轮约束 1）：
- 窗口集：task_kinds 取每条规则 applies_to.task_kinds 与
  {修造, 嫁娶, 安葬, 出行, 开业} 的交集（最多 2 个，防爆炸）；
  时刻 = {2025, 2026, 2027} × 12 月 × {1,8,15,22,25} 日 10:00（Asia/Shanghai；
  每月 5 天保证日支多样性——v1 固定单日把月破/岁破/日冲类命中率人为压没，已修正）；
  坐向 = 180/330/90/0 度；strictness=normal；allow_unverified=True。
- 扫描域 = 当前启用派别（ZWX/DS/XK 默认关闭 → 不参与死规则判据）。
- 命中定义 = 任一命中桶出现判定（vetoes/cautions/controversial/demo_hits/
  positives/notes/structural；演示与仅登记均算——v1 用 matched 过滤把演示命中全数漏计，已修正）。
- 统计量：命中候选数/参与评估候选数，按（规则 × 年份）分组分别统计——
  年支类规则天然只在特定年命中，"全年零命中"不是死规则判据。
- 判据：适用域内零命中 = 规则在其声明的全部适用 task_kind × 全部年份上均零命中。
- 处置：warn 不 error（约束 2）——新零命中规则（不在基线豁免内）打印告警并以
  退出码 1 供 CI 选用；基线内零命中属已知状态。
- 基线豁免：core-rule/config/dead_rule_baseline.yaml；--update-baseline 显式重建。
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]
for _p in ("core-time/src", "core-symbol/src", "core-rule/src", "core-eval/src", "app-zeri/src"):
    sys.path.insert(0, str(ROOT / _p))
sys.path.insert(0, str(ROOT))

from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context  # noqa: E402
from core_eval import EvalConfig, evaluate  # noqa: E402
from core_rule.registry import default_registry  # noqa: E402
from core_time import CalendarConfig  # noqa: E402

CST = ZoneInfo("Asia/Shanghai")
TASK_KINDS = ("修造", "嫁娶", "安葬", "出行", "开业")
DAYS = (1, 8, 15, 22, 25)
AZIMUTHS = (180.0, 330.0, 90.0, 0.0)
YEARS = (2025, 2026, 2027)
HIT_BUCKETS = ("vetoes", "cautions", "controversial", "demo_hits", "positives", "notes", "structural")
BASELINE = ROOT / "core-rule/config/dead_rule_baseline.yaml"


def _contexts():
    """按（task_kind, year, month, day, azimuth）产出窗口 ctx。"""
    for kind in TASK_KINDS:
        for year in YEARS:
            for month in range(1, 13):
                for day in DAYS:
                    for az in AZIMUTHS:
                        yield kind, year, (
                            build_context(
                                course=CourseSpec(dt=datetime(year, month, day, 10, 0, tzinfo=CST)),
                                site=SiteSpec(azimuth_deg=az, lat=23.13, lon=113.26),
                                task=TaskSpec(kind=kind, nodes=(kind,), strictness="normal"),
                                person=PersonSpec(),
                                cal=CalendarConfig(),
                            )
                        )


def run_scan():
    reg = default_registry()
    enabled_schools = set(reg.policy.enabled_schools())
    stats = defaultdict(lambda: defaultdict(int))
    evaluated = 0
    for kind, year, ctx in _contexts():
        ev = evaluate(ctx, reg, EvalConfig(task_kind=kind, allow_unverified=True))
        evaluated += 1
        for res in ev.per_school.values():
            for bucket in HIT_BUCKETS:
                for j in getattr(res, bucket):
                    stats[j.rule_id][year] += 1

    out = {}
    for rule in reg.ruleset.rules:
        if rule.status == "弃用" or rule.school not in enabled_schools:
            continue
        kinds = [k for k in rule.applies_to.task_kinds if k in TASK_KINDS][:2]
        if not kinds:
            continue  # 适用域不在扫描窗口 → 不判死（口径如此，不外推）
        per_year = {y: stats.get(rule.rule_id, {}).get(y, 0) for y in YEARS}
        total_hits = sum(per_year.values())
        out[rule.rule_id] = {
            "task_kinds": kinds,
            "hits_per_year": per_year,
            "zero_hit": total_hits == 0,
        }

    zero_hit = sorted(rid for rid, d in out.items() if d["zero_hit"])
    baseline = {}
    if BASELINE.exists():
        baseline = yaml.safe_load(BASELINE.read_text(encoding="utf-8")) or {}
    exempt = set(baseline.get("baseline_zero_hit") or [])
    new_zero = [rid for rid in zero_hit if rid not in exempt]
    return out, zero_hit, new_zero, evaluated


def main() -> int:
    out, zero_hit, new_zero, evaluated = run_scan()
    print(f"扫描完成：{evaluated} 个窗口候选，适用域内规则 {len(out)} 条")
    print("\n分规则 × 年份命中数（判据=适用域内零命中，非全年零命中）：")
    for rid in sorted(out):
        d = out[rid]
        tag = "  <- 零命中" if d["zero_hit"] else ""
        print(f"  - {rid} [{','.join(d['task_kinds'])}] {d['hits_per_year']}{tag}")

    baseline = {}
    if BASELINE.exists():
        baseline = yaml.safe_load(BASELINE.read_text(encoding="utf-8")) or {}
    exempt = set(baseline.get("baseline_zero_hit") or [])
    print(f"\nzero_hit: {zero_hit}")
    print(f"基线豁免：{sorted(exempt)}")
    if new_zero:
        print(f"\n⚠️ warn：新出现零命中规则（不在基线豁免内）：{new_zero}")
        print("   若属预期（窗口未覆盖其适用域），用 --update-baseline 显式登记；否则排查条件。")
        rc = 1
    else:
        print("\n✅ 无新增零命中规则（warn 级，不阻断——评审第十二轮约束 2）")
        rc = 0

    if "--update-baseline" in sys.argv:
        spec = {
            "window": {
                "task_kinds": list(TASK_KINDS),
                "years": list(YEARS),
                "days_of_month": list(DAYS),
                "hour": "10:00 Asia/Shanghai",
                "azimuths": list(AZIMUTHS),
                "strictness": "normal",
                "allow_unverified": True,
                "enabled_schools_only": True,
            },
            "statistic": "命中候选数/参与评估候选数，按（规则×年份）分组；判据=适用域内零命中",
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
            "baseline_zero_hit": zero_hit,
        }
        BASELINE.write_text(
            "# C21 死规则扫描基线（口径必须与 tools/dead_rule_scan.py docstring 一致；"
            "只许 --update-baseline 显式刷新）\n"
            + yaml.safe_dump(spec, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print(f"\n基线已更新：{BASELINE}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
