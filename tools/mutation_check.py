"""变异测试抽查（CI 可选用，也可手动跑）。

为什么需要
----------
AI 生成的测试有个常见毛病：**断言与实现同源** —— 测试只是把实现的写法抄了一遍，
改坏实现它也不报错。变异测试是低成本暴露这一点的办法：
把实现里的关键判断改坏（``in``→``nin``、``>=``→``>``、边界值挪一格），
如果测试仍然全绿，说明测试没真正验证行为。

本脚本不做全量变异（那需要 mutmut/cosmic-ray），只做**定点抽查**：
每个关键模块挑 1-2 处最容易被写错的地方，改坏 → 跑指定测试 → 期望失败 → 还原。

用法
----
``python3 tools/mutation_check.py``       # 全部抽查
``python3 tools/mutation_check.py -k dsl`` # 只跑 dsl 相关
退出码：0 = 所有变异都被测试抓住；1 = 有变异"存活"（说明测试有缺口）。
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


#: PR 门禁只跑核心子集（覆盖最关键的语义通道），nightly 跑全量。
CORE_KEYS: frozenset[str] = frozenset({
    "dsl-in", "dsl-gte", "dsl-between",
    "zixing-set", "three-state", "tier-unknown",
    "def-severity-whitelist", "publishable-required", "demo-participation",
    "rule-conflict",
})


@dataclass(frozen=True)
class Mutation:
    key: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]
    why: str


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        key="dsl-in",
        path="core-rule/src/core_rule/dsl.py",
        old='"in": _op_in,',
        new='"in": _op_nin,',
        tests=("tests/unit/test_dsl.py",),
        why="in 与 nin 互换 —— 若测试未覆盖集合归属，会静默通过",
    ),
    Mutation(
        key="dsl-gte",
        path="core-rule/src/core_rule/dsl.py",
        old="    return a >= b",
        new="    return a > b",
        tests=("tests/unit/test_dsl.py",),
        why="gte 边界改成严格大于 —— 若测试只测了远离边界的值，会漏",
    ),
    Mutation(
        key="dsl-between",
        path="core-rule/src/core_rule/dsl.py",
        old="    return lo <= a <= hi",
        new="    return lo < a < hi",
        tests=("tests/unit/test_dsl.py",),
        why="between 边界开闭 —— 边界值是择日判定最常见 off-by-one",
    ),
    Mutation(
        key="zixing-set",
        path="core-symbol/src/core_symbol/ganzhi.py",
        old='ZIXING: frozenset[str] = frozenset("辰午酉亥")',
        new='ZIXING: frozenset[str] = frozenset("辰午酉亥未")',
        tests=("tests/unit/test_symbol.py",),
        why="把未塞进自刑表 —— 这是本项目明确纠正过的错误，必须有测试守住",
    ),
    Mutation(
        key="sansha-direction",
        path="core-symbol/src/core_symbol/shensha.py",
        old='frozenset("亥卯未"): ("申", "酉", "戌"),',
        new='frozenset("亥卯未"): ("寅", "卯", "辰"),',
        tests=("tests/unit/test_symbol.py",),
        why="三煞方位错位（亥卯未煞西→煞东）—— 方位错则整条否决层错",
    ),
    Mutation(
        key="three-state",
        path="core-eval/src/core_eval/engine.py",
        old="    if vetoes:\n        state = STATE_BLOCKED",
        new="    if False:\n        state = STATE_BLOCKED",
        tests=("tests/unit/test_engine.py",),
        why="禁用命中不再判不可用 —— 三态定义被破坏",
    ),
    Mutation(
        key="day-pillar",
        path="core-time/src/core_time/calendar.py",
        old="    return (jdn_of_date(d) + 49) % 60",
        new="    return (jdn_of_date(d) + 50) % 60",
        tests=("tests/unit/test_time.py",),
        why="日柱基准偏移一天 —— 金标准四柱会全错",
    ),
    Mutation(
        key="tier-unknown",
        path="core-eval/src/core_eval/engine.py",
        old="    elif strong_avoid > 0 or conflict_count > 0 or unknown_count > 0:",
        new="    elif strong_avoid > 0 or conflict_count > 0:",
        tests=("tests/unit/test_engine.py", "tests/golden/test_golden_case.py"),
        why="unknown 不再拉低 tier —— 会把\"未知\"当\"可用\"放行",
    ),
    # ---------- 第二轮扩充：覆盖分支边界与语义通道（评审要求 20-30 个） ----------
    Mutation(
        key="def-severity-whitelist",
        path="core-rule/src/core_rule/loader.py",
        old="        if severity != DEFINITIONAL_SEVERITY:",
        new="        if False:",
        tests=("tests/unit/test_v2_features.py",),
        why="定义级 severity 白名单失效 —— 断言可伪装成定义（ADR-0009 核心防线）",
    ),
    Mutation(
        key="publishable-required",
        path="core-eval/src/core_eval/engine.py",
        old="            if self.blocked_required:",
        new="            if False:",
        tests=("tests/unit/test_v2_features.py",),
        why="必需集阻塞失效 —— 待考证规则也能发布（ADR-0010 核心防线）",
    ),
    Mutation(
        key="caution-not-unsure",
        path="core-eval/src/core_eval/engine.py",
        old="    elif cautions:",
        new="    elif False:",
        tests=("tests/unit/test_engine.py",),
        why="强忌不再判存疑 —— 三态定义被破坏",
    ),
    Mutation(
        key="tier-hardfail",
        path="core-eval/src/core_eval/engine.py",
        old="    if hard_fail > 0:",
        new="    if False:",
        tests=("tests/unit/test_engine.py",),
        why="硬伤不判 REJECTED —— 否决层被架空",
    ),
    Mutation(
        key="rule-conflict",
        path="core-eval/src/core_eval/engine.py",
        old="            if negative and positive:",
        new="            if False:",
        tests=("tests/unit/test_v2_features.py",),
        why="同派内规则冲突不检测 —— 天德/勾陈类互相抵消会被漏掉",
    ),
    Mutation(
        key="unknown-reason",
        path="core-eval/src/core_eval/engine.py",
        old="            UNKNOWN_UNVERIFIED,",
        new="            UNKNOWN_MISSING_INPUT,",
        tests=("tests/unit/test_v2_features.py",),
        why="unknown 三分类串味 —— 用户拿不到正确的解除条件",
    ),
    Mutation(
        key="same-group-kind",
        path="core-rule/src/core_rule/dsl.py",
        old='    kind = b.get("kind", "sanhe")',
        new='    kind = "sanhe"',
        tests=("tests/unit/test_dsl.py",),
        why="same_group 的 kind 被忽略 —— 六冲/六合/三刑退化为三合判断",
    ),
    Mutation(
        key="count-gte",
        path="core-rule/src/core_rule/dsl.py",
        old="    return len(a) >= b",
        new="    return len(a) > b",
        tests=("tests/unit/test_dsl.py",),
        why="count_gte 边界改成严格大于 —— '至少一条'判定失准",
    ),
    Mutation(
        key="lichun-longitude",
        path="core-time/src/core_time/jieqi.py",
        old='("立春", 315, "jie", 2, 4),',
        new='("立春", 316, "jie", 2, 4),',
        tests=("tests/unit/test_time.py",),
        why="立春黄经偏 1° —— 交节时刻错约 1 天，年柱全错",
    ),
    Mutation(
        key="leap-month",
        path="core-time/src/core_time/lunar.py",
        old="            if not has_zhongqi[i]:",
        new="            if has_zhongqi[i]:",
        tests=("tests/unit/test_time.py",),
        why="置闰取反（有中气月当闰月）—— 闰月全错",
    ),
    Mutation(
        key="hour-gan",
        path="core-time/src/core_time/calendar.py",
        old="    hour_gan = ((day_pillar.gan_index % 5) * 2 + hour_branch) % 10",
        new="    hour_gan = ((day_pillar.gan_index % 5) * 2 + hour_branch + 1) % 10",
        tests=("tests/unit/test_time.py",),
        why="五鼠遁偏移一位 —— 时柱全错",
    ),
    Mutation(
        key="month-gan",
        path="core-time/src/core_time/calendar.py",
        old="    month_gan = (_YIN_MONTH_GAN[year_pillar.gan_index] + order - 1) % 10",
        new="    month_gan = (_YIN_MONTH_GAN[year_pillar.gan_index] + order) % 10",
        tests=("tests/unit/test_time.py",),
        why="五虎遁偏移一位 —— 月柱全错",
    ),
    Mutation(
        key="xunkong-table",
        path="core-symbol/src/core_symbol/nayin.py",
        old='    "甲子": XunKong("甲子", 0, ("戌", "亥")),',
        new='    "甲子": XunKong("甲子", 0, ("申", "酉")),',
        tests=("tests/unit/test_symbol.py",),
        why="旬空表错位 —— 空亡判定全错",
    ),
    Mutation(
        key="nayin-table",
        path="core-symbol/src/core_symbol/nayin.py",
        old='    ("海中金", "金"),',
        new='    ("海中金", "水"),',
        tests=("tests/unit/test_symbol.py",),
        why="纳音五行错 —— 阴府等以纳音为据的判定全错",
    ),
    Mutation(
        key="mountain-order",
        path="core-symbol/src/core_symbol/mountain.py",
        old='"辰", "巽", "巳", "丙",',
        new='"辰", "巽", "丙", "巳",',
        tests=("tests/unit/test_symbol.py",),
        why="二十四山顺序错（丙巳互换）—— 坐向判定错位",
    ),
    Mutation(
        key="disagreement-formula",
        path="core-eval/src/core_eval/disagreement.py",
        old="    return 1.0 - mode_count / len(nums)",
        new="    return mode_count / len(nums)",
        tests=("tests/unit/test_engine.py",),
        why="分歧度公式取反 —— 0 表示一致变成 0 表示最分歧",
    ),
    Mutation(
        key="tier-rank-order",
        path="core-eval/src/core_eval/ranker.py",
        old="    TIER_PREFERRED: 0,",
        new="    TIER_PREFERRED: 9,",
        tests=("tests/unit/test_v2_features.py", "tests/unit/test_engine.py"),
        why="排序方向反了 —— PREFERRED 排到最后",
    ),
    Mutation(
        key="demo-participation",
        path="core-eval/src/core_eval/engine.py",
        old='            participation = "演示"',
        new='            participation = "判定"',
        tests=("tests/unit/test_v2_features.py", "tests/golden/test_golden_case.py"),
        why="演示命中被当成确定判定 —— 未考证规则会被表述为「确定排除」",
    ),
    # ---- 并行写入线产出的两个模块（2026-11-03 评审七回路：Q2「反错误」补强）----
    # 反退化测试只能证明「输出不是常量」，证明不了「输出正确」。
    # 这两条把公式/表**故意改错一位**，若测试仍绿，说明它没在测语义。
    Mutation(
        key="jianchu-offset",
        path="core-symbol/src/core_symbol/jianchu.py",
        old="    return (ZHI.index(target_zhi) - ZHI.index(month_zhi)) % 12",
        new="    return (ZHI.index(target_zhi) - ZHI.index(month_zhi) + 1) % 12",
        tests=("tests/unit/test_paipan_fixed.py",),
        why="建除位次整体错一位 —— 建日不再是月建日，破日不再等于月破；恒等式必红",
    ),
    Mutation(
        key="huangdao-star-swap",
        path="core-symbol/src/core_symbol/huangdao.py",
        old='    "青龙", "明堂", "天刑", "朱雀", "金匮", "天德",',
        new='    "明堂", "青龙", "天刑", "朱雀", "金匮", "天德",',
        tests=("tests/unit/test_paipan_fixed.py",),
        why="青龙与明堂对调 —— 月建日不再值青龙，勾陈 12/12 交叉对照必红",
    ),
)


def run_tests(tests: tuple[str, ...]) -> int:
    env_cmd = [
        sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider",
        *tests,
    ]
    proc = subprocess.run(env_cmd, cwd=ROOT, capture_output=True, text=True)
    return proc.returncode


def apply_and_test(m: Mutation, *, dry_run: bool = False) -> tuple[bool, str]:
    """返回 (变异是否被抓住, 说明)。"""
    target = ROOT / m.path
    original = target.read_text(encoding="utf-8")
    if m.old not in original:
        return False, f"⚠️  变异点未找到（源码可能已改）：{m.path} :: {m.old[:40]}"
    if dry_run:
        return True, "dry-run：跳过实际改写"

    backup = Path(tempfile.mkdtemp(prefix="zeri-mut-")) / target.name
    shutil.copy2(target, backup)
    try:
        target.write_text(original.replace(m.old, m.new, 1), encoding="utf-8")
        code = run_tests(m.tests)
    finally:
        shutil.copy2(backup, target)
        shutil.rmtree(backup.parent, ignore_errors=True)

    if code == 0:
        return False, "❌ 变异存活（测试没抓住）"
    return True, "✅ 变异被抓住"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-k", "--key", default=None, help="只跑匹配的变异 key")
    parser.add_argument(
        "--level", choices=["core", "full"], default="full",
        help="core = PR 门禁子集（10 个）；full = 全量（26 个，nightly）",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report",
        default=None,
        help="报告路径（默认 out/mutation-report.md，运行产物不进 git；归档时显式传 docs/mutation-report.md）",
    )
    args = parser.parse_args(argv)

    selected = [m for m in MUTATIONS if not args.key or args.key in m.key]
    if args.level == "core":
        selected = [m for m in selected if m.key in CORE_KEYS]
    if not selected:
        print(f"没有匹配的变异: {args.key}")
        return 1

    survived: list[Mutation] = []
    for m in selected:
        ok, msg = apply_and_test(m, dry_run=args.dry_run)
        print(f"[{m.key}] {msg}")
        print(f"    目的：{m.why}")
        if not ok:
            survived.append(m)

    print()
    # 默认写 out/：每次跑都变的运行时间戳不应污染 docs/ 的提交历史。
    # 需要把某次结果作为审计证据归档时，显式 --report docs/mutation-report.md。
    report_path = Path(args.report) if args.report else ROOT / "out" / "mutation-report.md"
    _write_report(report_path, selected, survived, level=args.level)

    if survived:
        print(f"❌ {len(survived)}/{len(selected)} 个变异存活，说明测试存在缺口：")
        for m in survived:
            print(f"   - {m.key}: {m.path} :: {m.old[:50]}")
        print(f"   存活列表已写入 {report_path}")
        return 1
    print(f"✅ {len(selected)} 个变异全部被测试抓住（测试有效性抽查通过）")
    print(f"   报告已写入 {report_path}")
    return 0


def _write_report(path: Path, selected, survived, *, level: str) -> None:
    from datetime import datetime as _dt

    survived_keys = {m.key for m in survived}
    lines = [
        "# 变异测试报告",
        "",
        f"- 运行时间：{_dt.now().astimezone().isoformat(timespec='seconds')}",
        f"- 级别：`{level}`（core = PR 门禁子集，full = nightly 全量）",
        f"- 变异点数：{len(selected)}　存活：{len(survived)}",
        f"- 结论：{'❌ 存在存活变异（测试缺口）' if survived else '✅ 全部被抓住'}",
        "",
        "| 变异点 | 结果 | 目的 |",
        "|---|---|---|",
    ]
    for m in selected:
        mark = "❌ 存活" if m.key in survived_keys else "✅ 抓住"
        lines.append(f"| `{m.key}` | {mark} | {m.why} |")
    lines.append("")
    lines.append(
        "> 存活 = 测试没真正验证行为。处置方式是**补测试**，不是改变异点或降低阈值。"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
