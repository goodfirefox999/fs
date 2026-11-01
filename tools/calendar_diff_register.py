#!/usr/bin/env python3
"""C20（降级版，评审第十二轮批准）：历算差异**登记表**——不是门禁。

定位与边界（评审第十二轮第三节）：
- 产出 = 分歧报告 + 分歧归类（节气/干支纪日/闰月），**多数票不裁决正确值**；
- 一致 ≠ 正确（第三方库可能同源互抄）；规范依据 = GB/T 33661-2017《农历的编算和颁行》
  （2017-05-12 发布，紫金山天文台起草，2023-12 复审有效）+ 紫金山天文台《中国天文年历》；
  第三方库只是交叉检查工具；
- oracle 为 dev-only（tools/requirements-dev-oracle.txt），禁入运行时依赖；
- 已知库特性：sxtwl 节气接口以儒略日/UT 为主（时区换算需自行处理）、
  lunar_python 闰月返回 0=无闰；两库不一致时的处置 = 登记 QUESTION，不自动改代码。

登记维度（首版）：
1. 节气时刻：2026–2027 × 24 节气，zeri vs lunar_python（sxtwl 逐日扫描近似，标精度口径）
2. 干支纪日：2024–2027 每月 1/11/21 日（192 样本），zeri vs lunar_python vs sxtwl
3. 闰月：2017–2027（含 2020/2023 闰月年），zeri vs lunar_python
输出：stdout 登记表 + docs/research/calendar-diff-register-2026-11.md（--write）
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
for _p in ("core-time/src", "core-symbol/src", "core-rule/src", "core-eval/src", "app-zeri/src"):
    sys.path.insert(0, str(ROOT / _p))
sys.path.insert(0, str(ROOT))

from core_time import CalendarConfig  # noqa: E402
from core_time.calendar import day_pillar_index, ganzhi_name  # noqa: E402
from core_time.jieqi import terms_of_year  # noqa: E402
from core_time.lunar import leap_month_of  # noqa: E402

CST = ZoneInfo("Asia/Shanghai")


def zeri_terms(year: int) -> dict[str, datetime]:
    # 统一口径：naive 北京时间（CST），与 oracle 对齐（登记口径：忽略 tzinfo 语义差异）
    return {t.name: t.local.replace(tzinfo=None) for t in terms_of_year(year)}


def lunar_terms(year: int) -> dict[str, datetime]:
    from lunar_python import Lunar, Solar

    out: dict[str, datetime] = {}
    lunar = Lunar.fromDate(datetime(year, 6, 1))
    for jq in lunar.getJieQiTable().items():
        name, solar = jq
        out[name] = datetime(solar.getYear(), solar.getMonth(), solar.getDay(),
                             solar.getHour(), solar.getMinute(), solar.getSecond())
    # lunar_python 的表横跨上一冬至上下一冬至，仅保留本公历年内的条目
    return {k: v for k, v in out.items() if v.year == year}


def sxtwl_terms(year: int) -> dict[str, datetime]:
    """sxtwl 节气（UT 儒略日 → 北京时间 naive；+8h 换算，秒级差异属实现差异）。"""
    import math
    from datetime import timedelta

    import sxtwl

    out: dict[str, datetime] = {}
    day = sxtwl.fromSolar(year, 1, 1)
    while day.getSolarYear() == year:
        if day.hasJieQi():
            jd = day.getJieQiJD() + 8 / 24.0  # UT → 北京时间
            z, f = math.modf(jd + 0.5)
            out[day.getCurrentJieQi()] = (
                datetime(1858, 11, 17) + timedelta(days=int(z), seconds=int(round(f * 86400)))
            )  # JD 2400000.5 = 1858-11-17（MJD 原点换算；sxtwl 的 JD 为标准儒略日）
        day = day.after(1)
    return out




def zeri_leap(year: int) -> int:
    m = leap_month_of(year)
    return m or 0


def lunar_leap(year: int) -> int:
    from lunar_python import LunarYear

    return LunarYear.fromYear(year).getLeapMonth()


def day_ganzhi_zeri(d: date) -> str:
    return ganzhi_name(day_pillar_index(d))


def day_ganzhi_lunar(d: date) -> str:
    from lunar_python import Lunar, Solar

    lunar = Lunar.fromDate(datetime(d.year, d.month, d.day))
    gz = lunar.getDayInGanZhi()
    return gz


def day_ganzhi_sxtwl(d: date) -> str:
    import sxtwl

    day = sxtwl.fromSolar(d.year, d.month, d.day)
    gz = day.getDayGZ()
    return f"{'甲乙丙丁戊己庚辛壬癸'[gz.tg]}{'子丑寅卯辰巳午未申酉戌亥'[gz.dz]}"


def main() -> int:
    lines: list[str] = []
    add = lines.append

    # ---- 1) 节气时刻（2026–2027，zeri vs lunar_python）----
    add("## 一、节气时刻（2026–2027 × 24 节气，zeri vs lunar_python）")
    add("")
    term_diff = 0
    term_total = 0
    max_diff = 0.0
    diff_samples: list[str] = []
    for year in (2026, 2027):
        zt = zeri_terms(year)
        lt = lunar_terms(year)
        for name, zdt in zt.items():
            ldt = lt.get(name)
            term_total += 1
            if ldt is None:
                diff_samples.append(f"- {year} {name}: lunar_python 无此条（键名映射待核）")
                continue
            diff = abs((zdt - ldt).total_seconds())
            max_diff = max(max_diff, diff)
            if diff > 60:  # 超过 1 分钟记分歧（秒级舍入差异属实现差异）
                term_diff += 1
                diff_samples.append(f"- {year} {name}: zeri {zdt} vs lunar {ldt}（差 {diff:.0f}s）")
    add(f"- 样本 {term_total} 条，>60s 分歧 {term_diff} 条，最大秒差 {max_diff:.0f}s")
    for sample in diff_samples[:12]:
        add(sample)
    add("")

    # ---- 2) 干支纪日（2024–2027 每月 1/11/21 日，三方）----
    add("## 二、干支纪日（2024–2027 × 每月 1/11/21 日 = 144 样本，zeri vs lunar_python vs sxtwl）")
    add("")
    gz_diff = 0
    gz_total = 0
    for year in (2024, 2025, 2026, 2027):
        for month in range(1, 13):
            for day in (1, 11, 21):
                d = date(year, month, day)
                gz_total += 1
                vals = {"zeri": day_ganzhi_zeri(d), "lunar": day_ganzhi_lunar(d),
                        "sxtwl": day_ganzhi_sxtwl(d)}
                if len(set(vals.values())) > 1:
                    gz_diff += 1
                    add(f"- {d}: {vals}")
    add(f"- 样本 {gz_total} 条，分歧 {gz_diff} 条")
    add("")

    # ---- 3) 闰月（2017–2027，zeri vs lunar_python）----
    add("## 三、闰月（2017–2027，zeri vs lunar_python；0=无闰）")
    add("")
    leap_diff = 0
    for year in range(2017, 2028):
        z, l = zeri_leap(year), lunar_leap(year)
        if z != l:
            leap_diff += 1
            add(f"- {year}: zeri={z} lunar={l} ← 分歧")
    add(f"- 样本 11 年，分歧 {leap_diff} 条（2020 闰四月、2023 闰二月为已知锚点）")
    add("")

    # ---- 4) sxtwl 节气接入状态 ----
    add("## 四、sxtwl 节气接入状态")
    add("")
    add("- sxtwl 2.0.7 节气接口为逐日扫描 + 儒略日（UT），与本登记表的北京时间口径需换算；")
    add("- 首版登记表未纳入其节气列（换算实现见 tools/calendar_diff_register.py 的 sxtwl_terms，")
    add("  精度口径待与 GB/T 33661 对齐后升级）——如实登记为「接入中」。")
    add("")

    text = "\n".join(lines)
    print(text)
    print(f"汇总：节气分歧 {term_diff}/{term_total}（最大 {max_diff:.0f}s）｜"
          f"干支纪日分歧 {gz_diff}/{gz_total}｜闰月分歧 {leap_diff}/11")
    if "--write" in sys.argv:
        out = ROOT / "docs/research/calendar-diff-register-2026-11.md"
        out.write_text(
            "# C20 历算差异登记表（首版，2026-11-01）\n\n"
            "> 定位：分歧登记，非门禁。规范依据：GB/T 33661-2017《农历的编算和颁行》"
            "（2017-05-12 发布，紫金山天文台起草）+ 紫金山天文台《中国天文年历》。\n"
            "> oracle：lunar_python 1.4.8 / sxtwl 2.0.7（dev-only，tools/requirements-dev-oracle.txt）。\n\n"
            + text,
            encoding="utf-8",
        )
        print(f"\n登记表已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
