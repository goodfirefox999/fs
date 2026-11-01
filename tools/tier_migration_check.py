#!/usr/bin/env python3
"""C16（ADR-0014）：默认档 tier 迁移**确认型**矩阵。

甲案不变式：有争议规则默认参与评估（判定（存疑））但**不得影响 tier**。
方法：12 个月 × 4 坐向逐一 evaluate（默认档，无 --allow-unverified），
对比【全量规则库】与【剔除有争议规则】两个 ruleset 的 tier——
非对角迁移必须为 0，非零即 bug（存疑规则偷偷压了 tier）。

守卫（评审第九轮第 3 条）：窗口集必须至少触发一次有争议规则命中，
否则矩阵全对角只证明"没触发"，判定无效（假阳性）——本脚本直接 FAIL。
坐向集含 180°（坐午向子）：2026 丙午年太岁在午、三煞在北（亥子丑），
该坐向同时触发 PUB-TAISUI-001（坐太岁）与 PUB-SANSHA-003（向三煞）。
"""

from __future__ import annotations

import sys
from dataclasses import replace as dc_replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
for _p in ("core-time/src", "core-symbol/src", "core-rule/src", "core-eval/src", "app-zeri/src"):
    sys.path.insert(0, str(ROOT / _p))
sys.path.insert(0, str(ROOT))

from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context  # noqa: E402
from core_eval import EvalConfig, evaluate  # noqa: E402
from core_rule.provenance import stable_hash  # noqa: E402
from core_rule.registry import default_registry  # noqa: E402
from core_time import CalendarConfig  # noqa: E402

CST = ZoneInfo("Asia/Shanghai")
#: 坐向集：180° 触发有争议规则（守卫要求），其余为对照
AZIMUTHS = (180.0, 330.0, 90.0, 0.0)
YEAR = 2026


def registry_without_controversial(reg):
    kept = tuple(r for r in reg.ruleset.rules if r.status != "有争议")
    by_id = {r.rule_id: r for r in kept}
    ruleset = dc_replace(
        reg.ruleset,
        rules=kept,
        by_id=by_id,
        version="rl-" + stable_hash([(r.rule_id, r.version) for r in kept]),
    )
    return dc_replace(reg, ruleset=ruleset)


def main() -> int:
    reg = default_registry()
    reg2 = registry_without_controversial(reg)
    controversial_hits = 0
    rows: list[str] = []
    failures: list[str] = []

    for month in range(1, 13):
        for az in AZIMUTHS:
            ctx = build_context(
                course=CourseSpec(dt=datetime(YEAR, month, 15, 10, 0, tzinfo=CST)),
                site=SiteSpec(azimuth_deg=az, lat=23.13, lon=113.26),
                task=TaskSpec(kind="修造", nodes=("修造",), strictness="normal"),
                person=PersonSpec(),
                cal=CalendarConfig(),
            )
            ev_full = evaluate(ctx, reg, EvalConfig(task_kind="修造"))
            ev_no = evaluate(ctx, reg2, EvalConfig(task_kind="修造"))
            controversial_hits += int(ev_full.vectors.get("controversial_count", 0))
            if ev_full.tier == ev_no.tier:
                rows.append(f"| {YEAR}-{month:02d} | {az:.0f} | {ev_full.tier} | ✅ 一致 |")
            else:
                rows.append(f"| {YEAR}-{month:02d} | {az:.0f} | {ev_full.tier}→{ev_no.tier} | ❌ 迁移 |")
                failures.append(f"{YEAR}-{month:02d} @ {az:.0f}°: {ev_full.tier} → {ev_no.tier}")

    print(f"### C16 tier 迁移确认矩阵（{YEAR}，默认档，全量 vs 剔除有争议）\n")
    print("| 月份 | 坐向(°) | tier | 结果 |")
    print("|---|---|---|---|")
    print("\n".join(rows))
    print(f"\n有争议规则命中次数：{controversial_hits}")

    if controversial_hits == 0:
        print("\n❌ FAIL：窗口集未触发任何有争议规则——矩阵全对角只证明'没触发'（假阳性），请更换坐向集")
        return 2
    if failures:
        print(f"\n❌ FAIL：{len(failures)} 处非对角迁移（存疑规则影响了 tier，违反甲案不变式）：")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\n✅ PASS：全部对角（有争议规则命中但 tier 零迁移，甲案不变式成立）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
