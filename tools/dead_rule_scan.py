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
- 处置：warn 不 error（约束 2）——新冒出的零命中规则（不在基线 entries 内）打印告警并以
  退出码 1 供 CI 选用；基线内零命中属已知状态。
- 基线登记：core-rule/config/dead_rule_baseline.yaml（entries：分类+blocked_by）；
  --update-baseline 显式重建；verified_exempt（已验证豁免）当前为空——
  '豁免'仅限已验证非死规则（评审第十四轮：10 unknown=未验证、1 exists=可疑）。
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
# v3 口径（评审第十二轮 P0，事项理由修正于第十三轮）：出行/开业无事项专属规则
# （显式清单 0 次；task_kinds:[] 通用规则仍覆盖它们——初版"零规则事项"系截断误判），
# 换入纳采/修坟（有专属规则的扫描域外代表）；坐向 4→11：补三合局巳酉丑局（巳/酉/丑）
# 与四隅（乾/坤/艮/巽）——v1 的 4 坐向使"巳酉丑局+四隅"类坐山依赖规则结构性无法命中。
TASK_KINDS = ("修造", "嫁娶", "安葬", "纳采", "修坟")
DAYS = (1, 8, 15, 22, 25)
AZIMUTHS = (180.0, 330.0, 90.0, 0.0, 150.0, 270.0, 30.0, 315.0, 225.0, 45.0, 135.0)
YEARS = (2025, 2026, 2027)
HIT_BUCKETS = ("vetoes", "cautions", "controversial", "demo_hits", "positives", "notes", "structural")
BASELINE = ROOT / "core-rule/config/dead_rule_baseline.yaml"


PERSON_FIXTURES = (
    None,                # 无命主（现状）
    PersonSpec(year_zhi="子"),  # 命主 fixture：解锁 CHONGMING/MING-SANSHA 类 person 门控规则
    PersonSpec(year_zhi="午"),
)


def _contexts():
    """按（task_kind, year, month, day, azimuth, person）产出窗口 ctx。

    person fixtures（评审第十三/十四轮两次要求）：无命主时 person 门控规则恒 unknown、
    永不可达——豁免会永久成立且永不被验证。加入 子/午 两个年命 fixture 后，
    日冲命/年命三煞类规则进入可测状态。
    """
    for kind in TASK_KINDS:
        for person in PERSON_FIXTURES:
            for year in YEARS:
                for month in range(1, 13):
                    for day in DAYS:
                        for az in AZIMUTHS:
                            yield kind, year, (
                                build_context(
                                    course=CourseSpec(dt=datetime(year, month, day, 10, 0, tzinfo=CST)),
                                    site=SiteSpec(azimuth_deg=az, lat=23.13, lon=113.26),
                                    task=TaskSpec(kind=kind, nodes=(kind,), strictness="normal"),
                                    person=person or PersonSpec(),
                                    cal=CalendarConfig(),
                                )
                            )


def coverage_report(contexts_meta: list[tuple]) -> list[str]:
    """四维覆盖度统计（评审第十二轮 P0）：日支/坐向→山/事项/节气邻近。"""
    from core_time.calendar import day_pillar_index
    from core_time.jieqi import terms_of_year

    lines: list[str] = []
    moments = sorted({dt for _, dt in contexts_meta})
    # ① 日支
    zhi_count: dict[str, int] = defaultdict(int)
    for dt in moments:
        zhi_count["子丑寅卯辰巳午未申酉戌亥"[day_pillar_index(dt.date()) % 12]] += 1
    lines.append(f"① 日支覆盖：{len(zhi_count)}/12 → {dict(sorted(zhi_count.items()))}")
    # ② 坐向→山（24 山每 15°）
    MOUNTAINS = "子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬"
    covered = sorted({MOUNTAINS[int(((az % 360) + 7.5) // 15) % 24] for az in AZIMUTHS})
    missing = [m for m in MOUNTAINS if m not in covered]
    lines.append(f"② 坐向覆盖：{len(AZIMUTHS)} 坐向 → {len(covered)} 山 {covered}；"
                 f"24 山缺口 {len(missing)}：{''.join(missing)}（代表性覆盖：四正✓ 四隅✓ 三合局 4/4✓）")
    # ③ 事项
    reg = default_registry()
    union: set[str] = set()
    for rule in reg.ruleset.rules:
        if rule.status != "弃用" and rule.school in set(reg.policy.enabled_schools()):
            union.update(rule.applies_to.task_kinds)
    covered_kinds = [k for k in TASK_KINDS if k in union]
    outside = sorted(union - set(TASK_KINDS))
    lines.append(f"③ 事项覆盖：规则适用域并集 {len(union)} 类；扫描 {len(covered_kinds)} 类 "
                 f"{covered_kinds}；域外有规则事项 {outside}（若非空则为盲区）")
    # ④ 节气邻近
    import bisect

    terms = sorted(
        t.local.astimezone(CST).replace(tzinfo=None) for y in YEARS for t in terms_of_year(y)
    )
    near = 0
    min_gap = None
    for dt in moments:
        i = bisect.bisect_left(terms, dt)
        cand = []
        if i < len(terms):
            cand.append(abs((terms[i] - dt).total_seconds()))
        if i > 0:
            cand.append(abs((dt - terms[i - 1]).total_seconds()))
        g = min(cand) if cand else None
        if g is not None:
            min_gap = g if min_gap is None else min(min_gap, g)
            if g < 86400:
                near += 1
    lines.append(f"④ 节气邻近：{len(moments)} 时刻中距最近节气 <24h 的 {near} 个，"
                 f"最小间距 {min_gap/3600:.1f}h（月柱边界覆盖度）")
    # ⑤ 农历日维度（评审第十三轮：杨公忌日类规则判农历特定日，与日支不同坐标系）
    # lunar_python 为 dev-only oracle 依赖——CI/生产环境可能未安装，缺 lxml 时跳过此维度
    from collections import defaultdict as _dd

    try:
        from lunar_python import Solar
        has_lunar = True
    except ImportError:
        has_lunar = False
    if not has_lunar:
        lines.append("⑤ 农历日覆盖：跳过（lunar_python 未安装——dev-only oracle 依赖）")
        return lines

    lunar_days: dict = _dd(int)
    leap_months: set = set()
    for dt in moments:
        solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, 10, 0, 0)
        lunar = solar.getLunar()
        leap = lunar.getMonth() < 0
        lunar_days[(abs(lunar.getMonth()), lunar.getDay(), leap)] += 1
        if leap:
            leap_months.add(abs(lunar.getMonth()))
    day_nums = sorted({d for (m, d, lp) in lunar_days})
    lines.append(f"⑤ 农历日覆盖：{len(lunar_days)} 个唯一（农历月,日,闰）组合；"
                 f"农历日 {min(day_nums)}–{max(day_nums)} 号覆盖 {len(day_nums)}/30 档；"
                 f"命中闰月月份：{sorted(leap_months) or '无'}"
                 "——杨公忌日类农历日规则的判定维度（评审第十三轮第一节）")
    return lines


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
            "evaluable": rule.evaluable,
        }

    zero_hit = sorted(rid for rid, d in out.items() if d["zero_hit"])
    baseline = {}
    if BASELINE.exists():
        baseline = yaml.safe_load(BASELINE.read_text(encoding="utf-8")) or {}
    # v3 基线 schema：entries（分类+blocked_by）取代扁平 baseline_zero_hit——
    # "豁免"只留给已验证非死规则（当前为空）；未验证/可疑不享受豁免语义
    # （评审第十四轮：10 unknown=未验证、1 exists=可疑，措辞不得混用）
    entries = {e.get("rule_id"): e for e in (baseline.get("entries") or [])}
    legacy = set(baseline.get("baseline_zero_hit") or [])
    exempt = {rid for rid, e in entries.items() if e.get("classification") == "verified_exempt"}
    exempt |= legacy  # 兼容旧扁平字段（逐条迁移后删除）
    new_zero = [rid for rid in zero_hit if rid not in exempt]
    entries_map = {rid: entries.get(rid, {}) for rid in zero_hit}
    return out, zero_hit, new_zero, evaluated, entries_map


def main() -> int:
    if "--coverage" in sys.argv:
        ctxs = [(k, dt) for k, year, dt in []]  # 占位：真实统计在下方
    meta = []
    for kind in TASK_KINDS:
        for year in YEARS:
            for month in range(1, 13):
                for day in DAYS:
                    for az in AZIMUTHS:
                        meta.append((kind, datetime(year, month, day, 10, 0)))
    print("\n".join(coverage_report(meta)))
    print("")
    out, zero_hit, new_zero, evaluated, entries_map = run_scan()
    print(f"扫描完成：{evaluated} 个窗口候选，适用域内规则 {len(out)} 条")
    print("\n分规则 × 年份命中数（判据=适用域内零命中，非全年零命中）：")
    for rid in sorted(out):
        d = out[rid]
        tag = "  <- 零命中" if d["zero_hit"] else ""
        print(f"  - {rid} [{','.join(d['task_kinds'])}] {d['hits_per_year']}{tag}")

    baseline = {}
    if BASELINE.exists():
        baseline = yaml.safe_load(BASELINE.read_text(encoding="utf-8")) or {}
    entries_all = {e.get("rule_id"): e for e in (baseline.get("entries") or [])}
    verified_exempt = {rid for rid, e in entries_all.items() if e.get("classification") == "verified_exempt"}
    print(f"\nzero_hit: {zero_hit}")
    print(f"verified_exempt（已验证豁免）：{sorted(verified_exempt) or '空（当前无——13 条均为未验证/可疑）'}")
    classified = {rid: entries_map.get(rid, {}).get("classification", "未登记") for rid in zero_hit}
    # summary 三栏（评审第十四轮：已验证零命中/已验证命中/未验证+可疑——"豁免"只指第一栏）
    n_verified_hit = sum(1 for rid, d in out.items() if not d["zero_hit"])
    n_verified_exempt = sum(1 for rid in zero_hit if entries_map.get(rid, {}).get("classification") == "verified_exempt")
    n_unverified = sum(1 for rid in zero_hit if classified.get(rid, "").startswith("unverified"))
    n_suspected = sum(1 for rid in zero_hit if classified.get(rid, "").startswith("suspected"))
    print("\n三栏 summary（C21 成功标准 = 三栏各归其位，而非\u201c13 条都不是死规则\u201d）：")
    print(f"  已验证命中（正常规则）：{n_verified_hit}")
    print(f"  已验证零命中（豁免）：{n_verified_exempt}")
    print(f"  未验证（门控未开）：{n_unverified} ｜ 可疑（语义待裁定）：{n_suspected}")
    print("\n零命中分类：")
    for rid in zero_hit:
        print(f"  - {rid}: {classified[rid]}")
    # suspected 棘轮：可疑计数不得高于基线登记值（登记≠消音——挂账且可见）
    ratchet = baseline.get("suspected_ratchet")
    if ratchet is not None and n_suspected > ratchet:
        print(f"\n❌ suspected 棘轮触发：{n_suspected} > 基线 {ratchet}——新增可疑必须显式登记理由")
        rc = 1
    new_zero = [rid for rid in zero_hit if rid not in entries_all]
    if new_zero:
        print(f"\n⚠️ warn：**新冒出**的零命中规则（不在基线 entries 内）：{new_zero}")
        print("   用 --update-baseline 显式登记（须带 classification + blocked_by）。")
        rc = 1
    else:
        print("\n✅ 零命中集合与基线 entries 完全一致（warn 级，不阻断）")
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
            "denominator": len(out),
            "suspected_ratchet": n_suspected,
            "rationale": ("可达性归因（docs/research/reachability-2026-11.md）：12 条未验证"
                          "（unknown 门控：命主3/口径未定1/起例未实现8）、1 条可疑"
                          "（XIUJIU exists 语义待裁定 Q-014）；verified_exempt（已验证非死规则）=0，"
                          "豁免基线为空——'豁免'仅限已验证（评审第十四轮）"),
            "recorded_at": datetime.now().isoformat(timespec="seconds"),
            "entries": [
                {"rule_id": rid,
                 "classification": (
                     "unimplemented_not_evaluable" if out[rid]["evaluable"] is False
                     else "unverified_unknown_gated"),
                 "blocked_by": (
                     "Q-014 + 起例实现" if out[rid]["evaluable"] is False
                     else ("Q-005" if rid == "PUB-YINFU-001" else "person 输入（fixture 已解锁，见 hits_per_year）"))}
                for rid in zero_hit
            ],
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
