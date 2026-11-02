"""神煞与派生事实（符号层，纯函数）。

**状态约定（极重要）**
--------------------
本模块每个事实函数都返回 ``FactValue``，其中 ``status`` 标明该事实的考证状态：

- ``已考证``：有明确公版古籍原文支撑，且口径无争议 —— 目前**没有任何一项**达到此状态，
  需人类考证者逐条确认后手动升级。
- ``待考证``：口诀常见但原文/口径未核 —— 默认**不参与**正式判定，仅登记为 unknown。
- ``有争议``：存在两种以上通行口径 —— 必须配置化，并在报告中回显取值。

因此本模块**不构成任何规则断言**。Agent 不得把 ``待考证`` 自行升级为 ``已考证``
（见 docs/DEVELOPMENT.md 第 0 节硬禁止第 1 条与第 5.3 节签名要求）。

术语
----
"三煞""岁破""五黄"等均为传统方位概念，其推算依据需人类考证者核对原文后确认。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Literal

from .ganzhi import GAN, SANHE, ZHI
from .mountain import MOUNTAINS_24, Mountain, angular_distance
from .zibai import FLY_ORDER, PALACE_MOUNTAINS, year_center_star, zibai_year_of

__all__ = [
    "FactStatus",
    "FactValue",
    "sansha_of",
    "taisui_azimuth",
    "suipo_azimuth",
    "yuepo_azimuth",
    "wuhuang_year",
    "wuhuang_year_of_date",
    "wuhuang_month",
    "sili_sijue",
    "yinfu_candidates",
    "unverified_fact",
]

FactStatus = Literal["已考证", "待考证", "有争议"]


@dataclass(frozen=True)
class FactValue:
    """一个派生事实。``value`` 为 ``None`` 表示"本系统不提供该事实"。"""

    name: str
    value: Any
    status: FactStatus
    note: str
    citation_hint: str | None = None

    @property
    def available(self) -> bool:
        return self.value is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "status": self.status,
            "note": self.note,
            "citation_hint": self.citation_hint,
        }


# --------------------------------------------------------------------------- #
# 三煞
# --------------------------------------------------------------------------- #
#: 三合局 → 三煞所临之三山（顺序：劫煞、灾煞、岁煞）
#: 口诀形态："寅午戌煞北、申子辰煞南、亥卯未煞西、巳酉丑煞东"。
#: 具体山名与"劫/灾/岁"的对应关系存在流派差异，故整表标 待考证。
_SANSHA_TABLE: dict[frozenset[str], tuple[str, str, str]] = {
    frozenset("寅午戌"): ("亥", "子", "丑"),
    frozenset("申子辰"): ("巳", "午", "未"),
    frozenset("亥卯未"): ("申", "酉", "戌"),
    frozenset("巳酉丑"): ("寅", "卯", "辰"),
}
_SANSHA_NAMES = ("劫煞", "灾煞", "岁煞")


def _sanhe_group(zhi: str) -> frozenset[str]:
    for group in SANHE:
        if zhi in group:
            return group
    raise KeyError(zhi)  # pragma: no cover


def sansha_of(zhi: str, basis: str = "year", caliber: str = "direction_group") -> FactValue:
    """按年支或月支三合局求三煞所临三山。

    ``caliber`` 决定判到哪一层（见 ``core-rule/config/calibers/sansha.yaml``）：

    - ``direction_group``（默认）：只判方位组三山，``by_name`` 为 ``None``，
      状态标 ``有争议``（粗化版不得冒充精确）。
    - ``named_sansha``：给出劫/灾/岁对应，状态标 ``待考证``（需原文确认顺序）。

    **为什么不提供"宫级命中"（不要补这个"遗漏"）**——QUESTION Q-020
    ------------------------------------------------------------
    五黄可以按宫判（一宫三山，兑=庚酉辛），三煞**不能**，因为三山并起来不是一个宫：

    ==========  =====================  ==========================
    三山        各占 15°               说明
    ==========  =====================  ==========================
    亥          322.5° – 337.5°
    （空档）     337.5° – 352.5°       ← 正是**壬山**，不在三山之列
    子          352.5° – 7.5°
    丑          22.5°  – 37.5°
    ==========  =====================  ==========================

    于是两条路都错：按八宫并集（坎+乾+艮）会扩到 9 山，明显过宽；
    按"三山精确匹配"则壬山不算——与"煞北"的方位直觉不符。**这个不自洽属概念层，
    不是实现遗漏**。故只按三山判定，不做宫级扩展；若人类裁定三煞覆盖整方（含壬），
    应按 90° 扇区重判并一并纳入乾、艮两山，而不是给本函数加一个 ``hit_palace``。
    守护测试：``test_paipan_fixed.py::TestSanshaScope::test_ren_mountain_is_not_sansha_hit``。
    """
    group = _sanhe_group(zhi)
    mountains = _SANSHA_TABLE[group]
    direction = {
        frozenset("寅午戌"): "北",
        frozenset("申子辰"): "南",
        frozenset("亥卯未"): "西",
        frozenset("巳酉丑"): "东",
    }[group]
    order = [z for z in ZHI if z in group]
    if caliber == "direction_group":
        by_name = None
        status: FactStatus = "有争议"
        note = (
            "口径=direction_group：只判定到方位组（三山），不判具体煞名。"
            "三山与劫煞/灾煞/岁煞的一一对应、以及是否按年/月/日/时四层分别起煞，均未裁定。"
        )
    elif caliber == "named_sansha":
        by_name = dict(zip(_SANSHA_NAMES, mountains))
        status = "待考证"
        note = (
            "口径=named_sansha：给出劫/灾/岁对应，但三山顺序存在流派差异，需原文确认。"
        )
    else:
        raise ValueError(f"未知三煞口径: {caliber}")
    return FactValue(
        name=f"sansha.{basis}",
        value={
            "mountains": list(mountains),
            "by_name": by_name,
            "direction": direction,
            "group": order,
            "basis_zhi": zhi,
            "caliber": caliber,
        },
        status=status,
        note=note,
        citation_hint="《协纪辨方书》类公版通书中三煞条目（卷次与原文待补）",
    )


# --------------------------------------------------------------------------- #
# 太岁 / 岁破 / 月破
# --------------------------------------------------------------------------- #
def _zhi_azimuth(zhi: str) -> float:
    """地支所临方位（子=0°，每支 30°）。"""
    return ZHI.index(zhi) * 30.0


def taisui_azimuth(year_zhi: str) -> FactValue:
    """太岁方位（年支所临之方）。"""
    return FactValue(
        name="taisui.azimuth",
        value={"zhi": year_zhi, "azimuth_deg": _zhi_azimuth(year_zhi)},
        status="待考证",
        note="太岁按年支所临之方取；岁君具体占位宽度与是否以立春换年，需以原文核对。",
        citation_hint="公版通书太岁条目（原文待补）",
    )


def suipo_azimuth(year_zhi: str) -> FactValue:
    """岁破方位（太岁对冲）。"""
    az = (_zhi_azimuth(year_zhi) + 180.0) % 360.0
    zhi = ZHI[int(round(az / 30.0)) % 12]
    return FactValue(
        name="suipo.azimuth",
        value={"zhi": zhi, "azimuth_deg": az, "opposes": year_zhi},
        status="待考证",
        note="岁破取太岁对冲之方（年支六冲位）；是否与三煞重叠计算需以原文核对。",
        citation_hint="公版通书岁破条目（原文待补）",
    )


def yuepo_azimuth(month_zhi: str) -> FactValue:
    """月破方位（月建对冲）。"""
    az = (_zhi_azimuth(month_zhi) + 180.0) % 360.0
    zhi = ZHI[int(round(az / 30.0)) % 12]
    return FactValue(
        name="yuepo.azimuth",
        value={"zhi": zhi, "azimuth_deg": az, "opposes": month_zhi},
        status="待考证",
        note="月破取月建对冲之方；月建以节气换月还是农历月换月，属争议项（见 CalendarConfig）。",
        citation_hint="公版通书月破条目（原文待补）",
    )


# --------------------------------------------------------------------------- #
# 五黄（紫白）
# --------------------------------------------------------------------------- #
# 九宫飞泊顺序、年入中星、紫白年换年判定**统一取自 ``zibai``**（单一来源）。
# 曾在此处复制过一份 _FLY_ORDER + _year_center_star，与 zibai.py 各写一遍——
# 两份实现一旦漂移，同一个盘上的「年紫白」与「年五黄」就会给出互相矛盾的方位，
# 而五黄到山是择日里最常被引用的断语，方位相反等于结论相反。故此处只做委托。


def wuhuang_year(zibai_year: int) -> FactValue:
    """年五黄所临方位。参数为**紫白年**（立春换年），不是公历年。

    为什么强调：紫白以立春换年，而立春在 2 月 3-5 日之间。若传公历年，
    每年 1 月 1 日至立春之间的日课会取到下一年（尚未到）的入中星，
    五黄方位与 ``facts.zibai.year`` 恰好相差两位五（如 2027-01-15：
    年紫白仍属 2026 一白入中、五黄在离，而按公历年 2027 九紫入中、五黄在坎——
    一南一北，结论完全相反）。调用点请用 :func:`wuhuang_year_of_date`。
    """
    center = year_center_star(zibai_year)
    offset = (5 - center) % 9
    palace, az = FLY_ORDER[offset]
    return FactValue(
        name="wuhuang.year",
        value={
            "zibai_year": zibai_year,
            "center_star": center,
            "palace": palace,
            "azimuth": az,
            # 宫心所在之地支山（保持既有语义：**山**级精确命中）
            "mountain": None
            if az is None
            else MOUNTAINS_24[int(round(az / 15.0)) % 24],
            # 五黄到宫：一宫三山，宫级命中才是五黄的本来粒度
            "palace_mountains": list(PALACE_MOUNTAINS.get(palace, ())),
        },
        status="待考证",
        note=(
            "年五黄按紫白年飞星入中逆推（1864 一白入中基准，立春换年）。"
            "入中基准年、顺飞/逆飞、五黄是否忌向，均属争议项，需配置化。"
            "命中粒度有二：mountain 级（仅宫心那一山）与 palace 级（一宫三山，见 palace_mountains）。"
        ),
        citation_hint="紫白飞星类公版通书（原文待补）",
    )


def wuhuang_year_of_date(local_date: date, year_zhi: str) -> FactValue:
    """按**日课所在日期 + 年支**取年五黄，自动做立春换年（紫白年）。

    这是唯一推荐的入口：紫白年由 :func:`core_symbol.zibai.zibai_year_of` 判定
    （传入年支与公历年不符即说明尚未立春），与 ``facts.zibai.year`` 同源。
    """
    return wuhuang_year(zibai_year_of(local_date, year_zhi))



def wuhuang_month(year: int, month_zhi: str) -> FactValue:
    """月五黄所临方位（口径待考证，暂不提供数值）。"""
    return FactValue(
        name="wuhuang.month",
        value=None,
        status="有争议",
        note=(
            "月五黄起法存在「年上起月」与「月上起月」两种通行口径，且与月建口径耦合；"
            "未裁定前本系统不提供该事实，相关规则将降级为 unknown。"
        ),
        citation_hint=None,
    )


# --------------------------------------------------------------------------- #
# 四离四绝
# --------------------------------------------------------------------------- #
_SILI = ("春分", "秋分", "夏至", "冬至")
_SIJUE = ("立春", "立夏", "立秋", "立冬")


def sili_sijue(d: date, term_dates: dict[str, date], *, include_day_itself: bool = False) -> FactValue:
    """判定 ``d`` 是否为四离日或四绝日。

    ``term_dates`` 为 {节气名: 本地日期}，由 core-time 提供（本模块不自行计算天文量）。
    ``include_day_itself`` 为真时把节气当日也计入（口径争议，默认 False，即取前一日）。
    """
    hits: list[dict[str, str]] = []
    for name in _SILI:
        td = term_dates.get(name)
        if td is None:
            continue
        target = td if include_day_itself else td - timedelta(days=1)
        if d == target:
            hits.append({"term": name, "kind": "四离"})
    for name in _SIJUE:
        td = term_dates.get(name)
        if td is None:
            continue
        target = td if include_day_itself else td - timedelta(days=1)
        if d == target:
            hits.append({"term": name, "kind": "四绝"})
    return FactValue(
        name="sili_sijue",
        value={
            "hits": hits,
            "is_hit": bool(hits),
            "has_sili": any(h["kind"] == "四离" for h in hits),
            "has_sijue": any(h["kind"] == "四绝" for h in hits),
        },
        status="待考证",
        note=(
            "四离取二分二至前一日、四绝取四立前一日；"
            "亦有取节气当日或前一时辰者，故 include_day_itself 必须显式配置。"
        ),
        citation_hint="公版通书四离四绝条目（原文待补）",
    )


# --------------------------------------------------------------------------- #
# 阴府
# --------------------------------------------------------------------------- #
#: 天干化气五行：甲己化土、乙庚化金、丙辛化水、丁壬化木、戊癸化火
_HUAQI: dict[str, str] = {
    "甲": "土", "己": "土", "乙": "金", "庚": "金",
    "丙": "水", "辛": "水", "丁": "木", "壬": "木", "戊": "火", "癸": "火",
}
_KE: dict[str, str] = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}


def yinfu_candidates(mountain_nayin_element: str, gans: list[str]) -> FactValue:
    """阴府候选：日课天干化气克坐山纳音者。

    仅给出"候选天干"清单，**不判定是否成煞**（阴府成煞条件、单干/双干之别、
    是否只论日干等均待考证）。``value`` 为 ``None`` 时相关规则降级为 unknown。
    """
    if mountain_nayin_element not in _KE:
        raise ValueError(f"非法五行: {mountain_nayin_element}")
    hits = [g for g in gans if _KE.get(_HUAQI[g]) == mountain_nayin_element]
    return FactValue(
        name="yinfu.candidates",
        value={
            "hits": hits,
            "single_gan_hits": [g for g in hits if gans.count(g) == 1],
            "mountain_element": mountain_nayin_element,
            "gans": list(gans),
        },
        status="有争议",
        note=(
            "阴府以坐山纳音与日课天干化气生克取；"
            "「单干亦忌」与「须双干成煞」两说并存，且是否只论日干、是否兼看月时干，均未裁定。"
        ),
        citation_hint="阴府类公版通书条目（原文待补）",
    )


def unverified_fact(name: str, note: str) -> FactValue:
    """登记一个"本系统暂不提供"的事实（如都天煞、伏兵大祸、天地官符、大小月建）。"""
    return FactValue(name=name, value=None, status="待考证", note=note, citation_hint=None)


# --------------------------------------------------------------------------- #
# 方位命中判定（供规则层使用，纯几何）
# --------------------------------------------------------------------------- #
def mountain_hits_azimuth(mountain: Mountain, azimuth: float, tolerance_deg: float = 7.5) -> bool:
    """坐山是否落在 ``azimuth`` 的 ``tolerance_deg`` 邻域内（纯几何判定）。"""
    return angular_distance(mountain.center_deg, azimuth) <= tolerance_deg


def zhi_of_azimuth(azimuth: float) -> str:
    """方位角所属地支（每支 30°，自子起）。"""
    return ZHI[int(round(azimuth / 30.0)) % 12]


_ = (GAN, field, datetime)  # 保留引用
