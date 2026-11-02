"""Q-015 影子对照：日紫白「连续 60 日法」vs「换节即换元法」。

为什么要跑影子而不是干等裁定
--------------------------
Q-015 两种日盘起元读法在节气附近会给出不同入中星。等师傅裁定前，工程上能做的是
**把差异量化**：差多少天、差几个星位、集中在哪些日期。有了这张表，裁定讨论
就从"用哪套"变成"这套会让 2026 年有 8% 的日子换星位，是否接受"。

两种读法（都必须先把定义写死，否则比较无意义）
--------------------------------------------
- **A 连续 60 日法**（当前实现，`zibai.day_center_star`）：
  取「本 60 甲子周期的甲子日」为锚，向前找最近一个已过的日盘节气（冬至/雨水/谷雨
  或 夏至/处暑/霜降），自该节气的起星顺/逆数。未到下一个甲子前仍属上一元。
- **B 换节即换元法**（对照读法，非抄本依据）：
  节气当日即换元，起星直接取该节气的 1/4/7（阳遁）或 9/3/6（阴遁），
  按日顺/逆数，不等甲子。

B 是"最激进的换元读法"，把它作为**上界**：真实符头法若存在，其差异面不会超过 B。
故本表给出的是「口径争议的最大影响面」，不是"符头法会这样"。

用法
----
    python tools/zibai_yuan_shadow.py --years 2025 2026 2027
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
for pkg in ("core-time", "core-symbol"):
    src = ROOT / pkg / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

from core_symbol.zibai import (  # noqa: E402
    _DAY_SEGMENTS,
    _YANG_TERMS,
    _YIN_TERMS,
    _is_yang_dun,
    _wrap9,
    day_center_star,
)
from core_time import CalendarConfig, compute_four_pillars, terms_of_year  # noqa: E402

TZ = ZoneInfo("Asia/Shanghai")


def _terms(years: list[int]) -> dict[int, dict[str, date]]:
    return {y: {t.name: t.local.date() for t in terms_of_year(y, "Asia/Shanghai")} for y in years}


def star_b(d: date, terms: dict[int, dict[str, date]]) -> tuple[int, str, int]:
    """换节即换元：返回 (入中星, 节气名, 距节气天数)。"""
    yang = _is_yang_dun(d, terms)
    names = _YANG_TERMS if yang else _YIN_TERMS
    best: tuple[date, str] | None = None
    for year in (d.year - 1, d.year):
        for name in names:
            td = terms.get(year, {}).get(name)
            if td is None or td > d:
                continue
            if best is None or td > best[0]:
                best = (td, name)
    if best is None:
        raise RuntimeError(f"{d} 找不到可用节气")
    td, name = best
    start = _DAY_SEGMENTS[name]
    steps = (d - td).days
    return _wrap9(start + steps if yang else start - steps), name, steps


def _delta(a: int, b: int) -> int:
    """环上最小差（1..9 循环）。"""
    raw = abs(a - b) % 9
    return min(raw, 9 - raw)


def scan(years: list[int]) -> dict:
    terms = _terms(years + [min(years) - 1])
    cal = CalendarConfig()
    rows: list[tuple[date, int, int, str, int]] = []
    for y in years:
        d = date(y, 1, 1)
        while d.year == y:
            dt = datetime(d.year, d.month, d.day, 12, 0, tzinfo=TZ)
            day_gz = compute_four_pillars(dt, cal).day.name
            a, _meta = day_center_star(day_gz, d, terms)
            if a is None:
                d += timedelta(days=1)
                continue
            b, seg, steps = star_b(d, terms)
            rows.append((d, a, b, seg, steps))
            d += timedelta(days=1)

    diffs = [r for r in rows if r[1] != r[2]]
    per_year: dict[int, dict[str, int]] = {}
    for y in years:
        sub = [r for r in rows if r[0].year == y]
        sd = [r for r in diffs if r[0].year == y]
        per_year[y] = {
            "days": len(sub),
            "diff": len(sd),
            "pct": round(100 * len(sd) / len(sub), 1) if sub else 0.0,
            "max_delta": max((_delta(r[1], r[2]) for r in sd), default=0),
        }
    return {
        "rows": rows,
        "diffs": diffs,
        "per_year": per_year,
        "delta_hist": Counter(_delta(r[1], r[2]) for r in diffs),
        "seg_hist": Counter(r[3] for r in diffs),
    }


def render(result: dict, years: list[int]) -> str:
    lines: list[str] = []
    lines.append("## 逐年差异")
    lines.append("")
    lines.append("| 年 | 日数 | 两口径不一致 | 占比 | 最大星位差 |")
    lines.append("|---|---|---|---|---|")
    for y in years:
        s = result["per_year"][y]
        lines.append(f"| {y} | {s['days']} | {s['diff']} | {s['pct']}% | {s['max_delta']} |")
    lines.append("")
    lines.append("## 星位差分布（不一致日）")
    lines.append("")
    lines.append("| 星位差 | 天数 |")
    lines.append("|---|---|")
    for delta in sorted(result["delta_hist"]):
        lines.append(f"| {delta} | {result['delta_hist'][delta]} |")
    lines.append("")
    lines.append("## 集中在哪些节气段")
    lines.append("")
    lines.append("| 节气段 | 不一致日数 |")
    lines.append("|---|---|")
    for seg, n in result["seg_hist"].most_common():
        lines.append(f"| {seg} | {n} |")
    lines.append("")
    lines.append("## 前 10 个不一致日")
    lines.append("")
    lines.append("| 日期 | A 连续60日 | B 换节换元 | 节气 | 距节天数 |")
    lines.append("|---|---|---|---|---|")
    for d, a, b, seg, steps in result["diffs"][:10]:
        lines.append(f"| {d} | {a} | {b} | {seg} | {steps} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q-015 日盘起元双读法影子对照")
    parser.add_argument("--years", nargs="+", type=int, default=[2025, 2026, 2027])
    parser.add_argument("--out", default=None, help="写入文件（默认打印）")
    args = parser.parse_args(argv)

    result = scan(args.years)
    text = render(result, args.years)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"已写入 {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
