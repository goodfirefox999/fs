"""紫白飞星 facts（Phase 10：年/月/日/时四盘）。

紫白是「虚拟天星」里最容易程序化的一支：给定入中星，九宫按洛书路径排布即可。
难点不在算术，在**起例口径**——本模块把每一处争议显式写出来，不静默选一个。

四盘起例（来源见各函数 docstring）
----------------------------------
- **年**：上元甲子一白、中元四绿、下元七赤，逐年**逆**退一位。1864 甲子＝一白为基准。
- **月**：子午卯酉年正月八白、辰戌丑未年正月五黄、寅申巳亥年正月二黑，逐月**逆**退一位。
  月序取**节气月**（寅=1 … 丑=12），与年柱同以立春为界。
- **日**：冬至/雨水/谷雨后首个甲子日起一白/四绿/七赤，**顺**行；
  夏至/处暑/霜降后首个甲子日起九紫/三碧/六白，**逆**行。
  口诀「冬至雨水及谷雨，阳顺一四七中游；夏至处暑霜降后，九三六星逆行求」。
- **时**：子午卯酉日 子时起一白（冬至后）／九紫（夏至后）；辰戌丑未日 四绿／六白；
  寅申巳亥日 七赤／三碧；逐时 ±1。

已知争议（全部进 ``needs_human_review``，不静默）
------------------------------------------------
1. **日/时盘的九宫飞布方向**：《选择求真》作「移入中宫，逆飞八方」，
   通行通书多作顺飞（洛书路径星数递增）。本模块用口径 ``zibai_fly``
   控制（默认 ``shun``），另一说在 ``caliber.alternatives`` 回显。
2. **年紫白换年点**：玄空以**立春**换年，部分通书按正月初一。本模块按立春
   （与年柱一致），由调用方传入的年支反推，见 ``zibai_year_of``。
3. **月紫白的「正月」**：取节气月（立春起寅）而非农历正月；闰月不另立。
4. **日盘的三元边界**：「冬至后甲子」指节气后**首个**甲子日，故冬至到该甲子日
   之间仍属上一元，本模块按此实现（连续 60 日一段，不断档）。

不职责：本模块只产出「某星落某宫、某山得某星」，**不判吉凶**。
"五黄到山为凶" 属规则层，且各派强度不一。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from .ganzhi import GANZHI60, ZHI

__all__ = [
    "FLY_ORDER",
    "MOUNTAIN_PALACE",
    "PALACE_MOUNTAINS",
    "fly_palaces",
    "year_center_star",
    "month_center_star",
    "day_center_star",
    "hour_center_star",
    "derive_zibai_hour",
    "zibai_year_of",
    "derive_zibai_facts",
]

#: 九宫飞泊顺序（自中宫起，洛书路径）：中、乾、兑、艮、离、坎、坤、震、巽
FLY_ORDER: tuple[tuple[str, float | None], ...] = (
    ("中", None),
    ("乾", 315.0),
    ("兑", 270.0),
    ("艮", 45.0),
    ("离", 180.0),
    ("坎", 0.0),
    ("坤", 225.0),
    ("震", 90.0),
    ("巽", 135.0),
)

#: 二十四山 → 八宫（每宫三山；中宫无山）
MOUNTAIN_PALACE: dict[str, str] = {
    "壬": "坎", "子": "坎", "癸": "坎",
    "丑": "艮", "艮": "艮", "寅": "艮",
    "甲": "震", "卯": "震", "乙": "震",
    "辰": "巽", "巽": "巽", "巳": "巽",
    "丙": "离", "午": "离", "丁": "离",
    "未": "坤", "坤": "坤", "申": "坤",
    "庚": "兑", "酉": "兑", "辛": "兑",
    "戌": "乾", "乾": "乾", "亥": "乾",
}

#: 八宫 → 所辖三山（``MOUNTAIN_PALACE`` 的反查；中宫无山，故不收录）。
#: 五黄、二黑等「到宫」判定用此表：一宫三山同受，只认宫心那一山会漏掉八干山。
PALACE_MOUNTAINS: dict[str, tuple[str, ...]] = {
    palace: tuple(m for m, p in MOUNTAIN_PALACE.items() if p == palace)
    for palace in ("坎", "艮", "震", "巽", "离", "坤", "兑", "乾")
}

#: 日盘六节气 → 起始入中星（阳遁 1/4/7，阴遁 9/3/6）
_DAY_SEGMENTS: dict[str, int] = {
    "冬至": 1, "雨水": 4, "谷雨": 7,
    "夏至": 9, "处暑": 3, "霜降": 6,
}
_YANG_TERMS = ("冬至", "雨水", "谷雨")
_YIN_TERMS = ("夏至", "处暑", "霜降")

#: 时盘起星：日支组 → (冬至后, 夏至后)
_HOUR_START: dict[str, tuple[int, int]] = {
    "子": (1, 9), "午": (1, 9), "卯": (1, 9), "酉": (1, 9),
    "辰": (4, 6), "戌": (4, 6), "丑": (4, 6), "未": (4, 6),
    "寅": (7, 3), "申": (7, 3), "巳": (7, 3), "亥": (7, 3),
}


def _wrap9(n: int) -> int:
    """把任意整数归一到 1..9。"""
    return (n - 1) % 9 + 1


def fly_palaces(center: int, *, direction: int = 1) -> dict[str, int]:
    """入中星 → 九宫分布。``direction=1`` 顺飞，``-1`` 逆飞。"""
    if direction not in (1, -1):
        raise ValueError(f"飞布方向只能是 ±1，得到 {direction}")
    return {
        palace: _wrap9(center + direction * step)
        for step, (palace, _az) in enumerate(FLY_ORDER)
    }


def year_center_star(year: int) -> int:
    """年紫白入中星。基准 1864 甲子＝一白，逐年逆退。"""
    return _wrap9(1864 - year + 1)


def zibai_year_of(local_date: date, year_zhi: str) -> int:
    """紫白「年」——以立春为界。

    判断方式：公历年 ``Y`` 的年支应为 ``ZHI[(Y-1984) % 12]``；若传入的年支与之不符，
    说明尚未立春，紫白年仍属 ``Y-1``。这样无需再算一次节气。
    """
    expected = ZHI[(local_date.year - 1984) % 12]
    return local_date.year if year_zhi == expected else local_date.year - 1


def month_center_star(year_zhi: str, month_index: int) -> int:
    """月紫白入中星。``month_index``：寅=1 … 丑=12（节气月）。"""
    if not 1 <= month_index <= 12:
        raise ValueError(f"节气月序必须是 1..12，得到 {month_index}")
    if year_zhi in ("子", "午", "卯", "酉"):
        start = 8
    elif year_zhi in ("辰", "戌", "丑", "未"):
        start = 5
    elif year_zhi in ("寅", "申", "巳", "亥"):
        start = 2
    else:
        raise ValueError(f"非法年支: {year_zhi}")
    return _wrap9(start - (month_index - 1))


def _term(terms: dict[int, dict[str, date]], year: int, name: str) -> date | None:
    table = terms.get(year)
    return table.get(name) if table else None


def _is_yang_dun(d: date, terms: dict[int, dict[str, date]]) -> bool:
    """冬至（含）至夏至（不含）为阳遁，其余为阴遁。"""
    dongzhi = _term(terms, d.year, "冬至")
    xiazhi = _term(terms, d.year, "夏至")
    if dongzhi is None or xiazhi is None:
        raise ValueError(f"{d.year} 年缺少冬至/夏至日期，无法判定阴阳遁")
    if d >= dongzhi:
        return True
    return d < xiazhi


def day_center_star(
    day_ganzhi: str,
    d: date,
    terms: dict[int, dict[str, date]],
) -> tuple[int | None, dict[str, Any]]:
    """日紫白入中星。返回 ``(星, 说明)``；缺数据时星为 ``None``。

    ``terms`` 为 ``{公历年: {节气名: 日期}}``，需覆盖 d 所在年及前一年
    （1 月的日课要回溯到上一年的冬至/霜降）。
    """
    if day_ganzhi not in GANZHI60:
        return None, {"error": f"非法日干支: {day_ganzhi}"}
    offset_in_cycle = GANZHI60.index(day_ganzhi)
    anchor = d - timedelta(days=offset_in_cycle)  # 本旬甲子日

    yang = _is_yang_dun(d, terms)
    names = _YANG_TERMS if yang else _YIN_TERMS

    # 候选边界：取 anchor 前后两年，找出「最后一个已过」的边界
    best: tuple[date, str] | None = None
    for year in (anchor.year - 1, anchor.year, anchor.year + 1):
        for name in names:
            td = _term(terms, year, name)
            if td is None or td > anchor:
                continue
            if best is None or td > best[0]:
                best = (td, name)
    if best is None:
        return None, {"error": "缺少日盘所需的节气日期（冬至/雨水/谷雨 或 夏至/处暑/霜降）"}

    start = _DAY_SEGMENTS[best[1]]
    steps = (d - anchor).days
    star = _wrap9(start + steps if yang else start - steps)
    return star, {
        "dun": "阳遁" if yang else "阴遁",
        "segment": best[1],
        "segment_date": best[0].isoformat(),
        "anchor_jiazi": anchor.isoformat(),
        "offset_in_cycle": offset_in_cycle,
        "steps_from_anchor": steps,
        "start_star": start,
    }


def hour_center_star(day_zhi: str, hour_zhi: str, *, yang_dun: bool) -> int:
    """时紫白入中星。``hour_zhi`` 为子…亥。"""
    if day_zhi not in _HOUR_START:
        raise ValueError(f"非法日支: {day_zhi}")
    if hour_zhi not in ZHI:
        raise ValueError(f"非法时支: {hour_zhi}")
    yang_start, yin_start = _HOUR_START[day_zhi]
    start = yang_start if yang_dun else yin_start
    idx = ZHI.index(hour_zhi)
    return _wrap9(start + idx if yang_dun else start - idx)


#: 八宫中心山（用于「山级」命中：只有宫心那一山算，与 facts.wuhuang.year.hit_mountain 同义）
PALACE_CENTER_MOUNTAIN: dict[str, str] = {
    "坎": "子", "艮": "艮", "震": "卯", "巽": "巽",
    "离": "午", "坤": "坤", "兑": "酉", "乾": "乾",
}


def _plate(center: int, *, fly: int, mountain: str) -> dict[str, Any]:
    """一盘九宫 + 坐山所得星。

    **两个命中字段的粒度必须分开命名**（Q-018 遗留，2026-11-03 修正）：
    - ``wuhuang_hit_palace``：宫级——一宫三山同受（紫白的本来粒度）；
    - ``wuhuang_hit_mountain``：山级——只有宫心那一山算，与
      ``facts.wuhuang.year.hit_mountain`` 同义。

    历史坑：原字段只有一个 ``wuhuang_hit_mountain``，实现却是**宫级**，
    报告按「五黄到坐山」渲染 → 文案与判定粒度不符。改名后语义唯一。
    """
    palaces = fly_palaces(center, direction=fly)
    inverse = {star: palace for palace, star in palaces.items()}
    shan_palace = MOUNTAIN_PALACE.get(mountain)
    wuhuang_palace = inverse.get(5)
    erhei_palace = inverse.get(2)
    hit_palace = bool(shan_palace) and wuhuang_palace == shan_palace
    hit_mountain = hit_palace and shan_palace is not None and (
        PALACE_CENTER_MOUNTAIN.get(shan_palace) == mountain
    )
    return {
        "center": center,
        "palaces": palaces,
        "wuhuang_palace": wuhuang_palace,
        "erhei_palace": erhei_palace,
        "shan_palace": shan_palace,
        "shan_star": palaces.get(shan_palace) if shan_palace else None,
        "wuhuang_hit_palace": hit_palace,
        "wuhuang_hit_mountain": hit_mountain,
        "erhei_hit_palace": bool(shan_palace) and erhei_palace == shan_palace,
    }


def derive_zibai_hour(
    *,
    day_zhi: str,
    hour_zhi: str,
    yang_dun: bool,
    mountain_name: str,
    fly_caliber: str = "shun",
) -> dict[str, Any]:
    """时盘单算：只依赖「日支 + 时支 + 阴阳遁 + 坐山」。

    为什么要单独抽出来：``derive_facts`` 的日级缓存**不含时柱**（2026-11-02 的
    P0 就是跨时辰事实串味）。时盘必须在候选级（``overlay_hour_facts``）重算，
    而它所需的阴阳遁属日级事实，由日盘结果的 ``dun`` 字段传回 —— 这样时盘
    只有一个计算入口，且不会把首个子时的星带给其余十一个时辰。
    """
    if fly_caliber not in ("shun", "ni"):
        raise ValueError(f"未知飞布口径: {fly_caliber}")
    star = hour_center_star(day_zhi, hour_zhi, yang_dun=yang_dun)
    return {
        "dun": "阳遁" if yang_dun else "阴遁",
        **_plate(star, fly=1 if fly_caliber == "shun" else -1, mountain=mountain_name),
    }


def derive_zibai_facts(
    *,
    year_zhi: str,
    month_zhi: str,
    day_ganzhi: str,
    hour_zhi: str | None,
    local_date: date | None,
    terms: dict[int, dict[str, date]] | None,
    mountain_name: str,
    fly_caliber: str = "shun",
) -> dict[str, Any]:
    """展开 ``facts.zibai``（年/月/日/时四盘 + 坐山所得星）。

    ``fly_caliber``：``shun``（顺飞，默认）／``ni``（逆飞，《选择求真》日家说）。
    年、月两盘恒用顺飞（通书共识），口径只作用于日、时两盘。
    """
    if fly_caliber not in ("shun", "ni"):
        raise ValueError(f"未知飞布口径: {fly_caliber}")
    day_fly = 1 if fly_caliber == "shun" else -1

    out: dict[str, Any] = {"status": "待考证", "needs_human_review": []}
    review: list[str] = out["needs_human_review"]

    # ---- 年 ----
    if local_date is not None:
        zy = zibai_year_of(local_date, year_zhi)
        out["year"] = {"zibai_year": zy, **_plate(year_center_star(zy), fly=1, mountain=mountain_name)}
    else:
        out["year"] = {"zibai_year": None, "center": None}

    # ---- 月 ----
    # 节气月序：寅=1 … 丑=12（ZHI 序 子=0 → 寅=2）
    month_index = (ZHI.index(month_zhi) - 2) % 12 + 1
    out["month"] = {
        "month_index": month_index,
        **_plate(month_center_star(year_zhi, month_index), fly=1, mountain=mountain_name),
    }

    # ---- 日 ----
    if local_date is not None and terms:
        star, meta = day_center_star(day_ganzhi, local_date, terms)
        out["day"] = {**meta, **(dict(_plate(star, fly=day_fly, mountain=mountain_name)) if star else {"center": None})}
        if star is None:
            review.append("日盘缺节气数据，日紫白降级为 unknown")
    else:
        out["day"] = {"center": None, "error": "缺少用事日或节气日期"}
        review.append("日盘缺节气数据，日紫白降级为 unknown")

    # ---- 时 ----
    # 日级调用（derive_facts）传 hour_zhi=None，时盘留给候选级 overlay 重算；
    # 直接传时辰时按同一入口计算，保证两条路径同源。
    if hour_zhi and local_date is not None and terms:
        yang = _is_yang_dun(local_date, terms)
        out["hour"] = derive_zibai_hour(
            day_zhi=day_ganzhi[1],
            hour_zhi=hour_zhi,
            yang_dun=yang,
            mountain_name=mountain_name,
            fly_caliber=fly_caliber,
        )
    else:
        out["hour"] = {"center": None, "error": "未提供时辰（时盘由候选级叠加计算）"}

    out["caliber"] = {
        "fly": fly_caliber,
        "alternatives": (
            [{"fly": "ni", "note": "《选择求真》日家三元紫白作「逆飞八方」"}]
            if fly_caliber == "shun"
            else [{"fly": "shun", "note": "通行通书多作顺飞（洛书路径星数递增）"}]
        ),
        "year_boundary": "lichun",
        "month_base": "jieqi_month",
    }
    review.append("日/时盘的九宫飞布方向两说并存（顺飞／逆飞），本盘按口径 zibai_fly 计算")
    review.append("年紫白以立春换年；部分通书按正月初一，跨立春的日课结论会不同")
    return out
