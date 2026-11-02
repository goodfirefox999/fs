"""派生事实注册表（符号层）。

职责
----
1. 集中登记本系统提供/不提供的派生事实及其考证状态，供报告回显与 ``zeri rules lint`` 检查。
2. 把 ``core-time`` 的四柱与 ``Site`` 输入展开成 DSL 可访问的 ``facts.*`` 命名空间。

**不职责**：任何吉凶判断。facts 只描述"方位/关系/是否命中"，不说"宜/忌"。

命名空间约定（DSL 白名单见 core-rule/dsl.py）
--------------------------------------------
``facts.<fact>.<sub>.<field>`` 例如 ``facts.sansha.year.mountains``。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

from .ganzhi import (
    GAN,
    SANHE,
    ZHI,
    all_relations_between_zhi,
    relation_between_gan,
    relation_between_zhi,
    sanhe_present,
    zhi_counts,
)
from .mountain import MOUNTAINS_24, Mountain, mountain_of_azimuth
from .doushou import derive_doushou_facts
from .huangdao import derive_huangdao_fact, huangdao_index, huangdao_of
from .jianchu import derive_jianchu_fact, jianchu_index, jianchu_of
from .jishen import derive_jishen_facts
from .tianxing import derive_tianxing_facts
from .xiu import qizheng_of_date, weekday_consistent, xiu_of_date, yuan_of_date
from .zibai import derive_zibai_facts, derive_zibai_hour, zibai_year_of
from .xuankong import derive_xuankong_facts
from .nayin import nayin_element_of, xunkong_of
from .shensha import (
    FactStatus,
    FactValue,
    sansha_of,
    sili_sijue,
    suipo_azimuth,
    taisui_azimuth,
    wuhuang_month,
    wuhuang_year_of_date,
    yinfu_candidates,
    yuepo_azimuth,
)

__all__ = [
    "FACT_REGISTRY",
    "FactSpec",
    "derive_facts",
    "overlay_hour_facts",
    "structure_facts",
    "tongguan_facts",
    "sanhe_ju_facts",
    "fact_status_summary",
    "unavailable_facts",
]


@dataclass(frozen=True)
class FactSpec:
    """一条派生事实的登记项。"""

    name: str
    status: FactStatus
    note: str
    provider: str


#: 全部派生事实登记表。``provider`` 为"本系统提供"或"本系统不提供"。
FACT_REGISTRY: tuple[FactSpec, ...] = (
    FactSpec("sansha.year", "待考证", "年支三合局所临三煞方位", "本系统提供"),
    FactSpec("sansha.month", "待考证", "月支三合局所临三煞方位", "本系统提供"),
    FactSpec("taisui.azimuth", "待考证", "太岁方位", "本系统提供"),
    FactSpec("suipo.azimuth", "待考证", "岁破方位", "本系统提供"),
    FactSpec("yuepo.azimuth", "待考证", "月破方位", "本系统提供"),
    FactSpec("wuhuang.year", "待考证", "年五黄方位（紫白）", "本系统提供"),
    FactSpec("wuhuang.month", "有争议", "月五黄方位（口径未裁定）", "本系统不提供"),
    FactSpec("sili_sijue", "待考证", "四离四绝日", "本系统提供"),
    FactSpec("yinfu.candidates", "有争议", "阴府候选天干（不成煞判定）", "本系统提供候选"),
    FactSpec("xunkong", "已考证", "旬空（六十甲子旬空表，公版表）", "本系统提供"),
    FactSpec("dutiansha", "待考证", "都天煞", "本系统不提供"),
    FactSpec("fubing_dahuo", "待考证", "伏兵大祸", "本系统不提供"),
    FactSpec("tianguan_difu", "待考证", "天地官符", "本系统不提供"),
    FactSpec("damonthly_jian", "待考证", "大小月建", "本系统不提供"),
    FactSpec("yangongji", "有争议", "杨公忌日", "本系统不提供"),
    FactSpec("sang.zhongsang", "待考证", "重丧日", "本系统不提供"),
    FactSpec("sang.sansang", "待考证", "三丧日", "本系统不提供"),
    FactSpec("jiaqu.fangwenggu", "待考证", "妨翁姑", "本系统不提供"),
    FactSpec("jiaqu.fangfumu", "待考证", "妨父母", "本系统不提供"),
    FactSpec("xiujiu.jiayan", "待考证", "修旧宅加严项", "本系统不提供"),
    # 斗首五行（Phase 9）：纯查表，不依赖星历
    FactSpec("doushou.shan.element", "待考证", "坐山斗首五行（≠正五行）", "本系统提供"),
    FactSpec("doushou.stems", "待考证", "四柱天干化气五行与五星定位", "本系统提供"),
    FactSpec("doushou.counts", "待考证", "五星计数（元辰/贪狼/廉贞/武曲/破军）", "本系统提供"),
    FactSpec("doushou.sanyuan", "待考证", "三元格（三重元辰）", "本系统提供"),
    FactSpec("doushou.sanwu", "待考证", "三武格（三重武财）", "本系统提供"),
    FactSpec("doushou.shan.dewei", "有争议", "山家得位（土长生口径未裁定）", "本系统提供"),
    # 紫白四盘（Phase 11）：年/月/日/时入中星 + 九宫飞布 + 坐山所得星
    FactSpec("zibai.year", "待考证", "年紫白入中星与九宫（立春换年）", "本系统提供"),
    FactSpec("zibai.month", "待考证", "月紫白入中星与九宫（节气月，逐月逆退）", "本系统提供"),
    FactSpec("zibai.day", "待考证", "日紫白入中星与九宫（三元日，顺/逆飞口径）", "本系统提供"),
    FactSpec("zibai.hour", "待考证", "时紫白入中星与九宫（日支组起星）", "本系统提供"),
    # 二十八宿值日（Phase 11）：七元起宿，锚点 1996-01-28 甲子虚宿
    FactSpec("xiu.day", "待考证", "二十八宿值日（七元起宿；星期恒等式自校验 + 两例黄历对算）", "本系统提供"),
    # 吉神表（Phase 11）：天德/月德/月德合/天赦
    FactSpec("jishen.tian_de", "有争议", "天德（卦位取支口径未裁定）", "本系统提供"),
    FactSpec("jishen.yue_de", "待考证", "月德与月德合", "本系统提供"),
    FactSpec("jishen.tian_she", "待考证", "天赦日（四季干支）", "本系统提供"),
    # 建除十二神 / 十二黄黑道：纯位移起例（月建起建、月建起青龙，顺行）
    FactSpec("jianchu.day", "待考证", "建除十二神（日家；位次=日支−月建）", "本系统提供"),
    FactSpec("jianchu.hour", "待考证", "建除十二神（时家；位次=时支−月建）", "本系统提供"),
    FactSpec("huangdao.day", "待考证", "十二黄黑道（日家；青龙起例顺行十二神）", "本系统提供"),
    FactSpec("huangdao.hour", "待考证", "十二黄黑道（时家，即黄道吉时）", "本系统提供"),
)


def unavailable_facts() -> list[str]:
    """返回本系统不提供数值的事实名（相关规则将降级为 unknown）。"""
    return [spec.name for spec in FACT_REGISTRY if spec.provider == "本系统不提供"]


def fact_status_summary() -> dict[str, int]:
    """按状态统计事实数量，写入报告 manifest。"""
    summary: dict[str, int] = {}
    for spec in FACT_REGISTRY:
        summary[spec.status] = summary.get(spec.status, 0) + 1
    return summary


def _hits(mountains: list[str], mountain: Mountain, facing: Mountain | None) -> dict[str, bool]:
    return {
        "hit_mountain": mountain.name in mountains,
        "hit_facing": facing is not None and facing.name in mountains,
    }


# --------------------------------------------------------------------------- #
# 时柱相关事实（供「日级缓存 + 时柱叠加」复用）
#
# 为什么单独抽出来：``derive_facts`` 收的是**四柱**，其中 structure / 旬空 hits /
# 通关 / 三合局 / 斗首 都随时支变化。若按日缓存整包 facts，同一天 12 个时辰会
# 共用首个子时的结果（2026-11-02 真实 P0）。抽成函数后，日级缓存只存日不变部分，
# 时变部分逐候选叠加——既正确又不牺牲性能（4380 候选从 5.4s 回到 2.7s 量级）。
# 这些函数是**唯一**计算入口，derive_facts 与叠加层都调它们，不另写一套。
# --------------------------------------------------------------------------- #
def structure_facts(*, gans: list[str], zhis: list[str], shan_jia_zhi: str | None) -> dict[str, Any]:
    """干支关系结构检测（纯关系，不含吉凶）。"""
    counts = zhi_counts(zhis)
    combined = list(zhis) + ([shan_jia_zhi] if shan_jia_zhi else [])
    relations: list[dict[str, Any]] = []
    for i in range(len(zhis)):
        for j in range(i + 1, len(zhis)):
            for rel in all_relations_between_zhi(zhis[i], zhis[j]):
                if rel.kind == "无":
                    continue
                relations.append(
                    {"a": zhis[i], "b": zhis[j], "pos": [i, j], "kind": rel.kind, "element": rel.element}
                )

    def _pairs(kind: str) -> list[dict[str, Any]]:
        return [r for r in relations if r["kind"] == kind]

    banhe_with_mountain: list[dict[str, Any]] = []
    if shan_jia_zhi:
        for z in dict.fromkeys(zhis):
            rel = relation_between_zhi(shan_jia_zhi, z)
            if rel.kind != "半合":
                continue
            group = next(g for g in SANHE if {shan_jia_zhi, z} <= g)
            banhe_with_mountain.append(
                {"a": shan_jia_zhi, "b": z, "element": rel.element, "group": sorted(group)}
            )

    return {
        "zhi_counts": counts,
        "repeated": {z: c for z, c in counts.items() if c >= 2},
        "max_repeat": max(counts.values()) if counts else 0,
        "sanhe_groups": [
            {"group": sorted(group), "element": element} for group, element in sanhe_present(zhis)
        ],
        "shan_jia_zhi": shan_jia_zhi,
        "sanhe_with_mountain": [
            {"group": sorted(group), "element": element, "mountain_zhi": shan_jia_zhi}
            for group, element in sanhe_present(combined)
            if shan_jia_zhi and shan_jia_zhi in group
        ],
        "banhe_with_mountain": banhe_with_mountain,
        "relations": relations,
        # 分类聚合：供规则以 count_gte 判定（避免规则里写遍历逻辑）
        "zixing_pairs": _pairs("自刑"),
        "chong_pairs": _pairs("冲"),
        "hai_pairs": _pairs("害"),
        "po_pairs": _pairs("破"),
        "xing_pairs": _pairs("刑"),
        "he_pairs": _pairs("合"),
        "sanhe_pairs": _pairs("三合"),
        "gan_chong_pairs": [
            {"a": gans[i], "b": gans[j], "pos": [i, j]}
            for i in range(len(gans))
            for j in range(i + 1, len(gans))
            if relation_between_gan(gans[i], gans[j]).kind == "冲"
        ],
        "gan_he_pairs": [
            {"a": gans[i], "b": gans[j], "pos": [i, j]}
            for i in range(len(gans))
            for j in range(i + 1, len(gans))
            if relation_between_gan(gans[i], gans[j]).kind == "合"
        ],
        "gan_count": {g: gans.count(g) for g in GAN if g in gans},
        "zhi_set": list(dict.fromkeys(zhis)),
    }


_WUXING_OF_GAN: dict[str, str] = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}
_WUXING_OF_ZHI: dict[str, str] = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}
#: 通关五行：金木战取水、水火战取木、木土战取火、土水战取金
_TONGGUAN_OF: dict[str, str] = {
    "金木": "水", "木金": "水", "水火": "木", "火水": "木",
    "木土": "火", "土木": "火", "土水": "金", "水土": "金",
}


def tongguan_facts(*, gans: list[str], zhis: list[str]) -> dict[str, Any]:
    """四柱五行计数 + 相战检测 + 通关五行（正五行）。"""
    wuxing_count = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for g in gans:
        if g in _WUXING_OF_GAN:
            wuxing_count[_WUXING_OF_GAN[g]] += 1
    for z in zhis:
        if z in _WUXING_OF_ZHI:
            wuxing_count[_WUXING_OF_ZHI[z]] += 1
    conflicts: list[str] = []
    for wx1, wx2 in (("木", "金"), ("金", "木"), ("水", "火"), ("火", "水"), ("木", "土"), ("土", "木")):
        if wuxing_count.get(wx1, 0) >= 2 and wuxing_count.get(wx2, 0) >= 2:
            conflicts.append(f"{wx1}{wx2}战")
    tongguan = None
    for pair in conflicts:
        key = pair.replace("战", "")
        if key in _TONGGUAN_OF:
            tongguan = _TONGGUAN_OF[key]
            break
    return {
        "conflicts": conflicts,
        "tongguan_element": tongguan,
        "wuxing_count": wuxing_count,
        "status": "待考证",
    }


_SANHE_JU: dict[str, str] = {"申子辰": "水", "亥卯未": "木", "寅午戌": "火", "巳酉丑": "金"}
_ZHI_IN_JU: dict[str, str] = {z: ju for ju, _wx in _SANHE_JU.items() for z in ju}


def sanhe_ju_facts(*, zhis: list[str], shan_jia_zhi: str | None) -> dict[str, Any]:
    """三合局判定：日课地支与坐山支同局 → 旺/待/平。"""
    day_ju = {_ZHI_IN_JU[z] for z in zhis if z in _ZHI_IN_JU}
    shan_ju = _ZHI_IN_JU.get(shan_jia_zhi) if shan_jia_zhi else None
    result = "平"
    if shan_ju and shan_ju in day_ju:
        ju_zhi_count = sum(1 for z in zhis if _ZHI_IN_JU.get(z) == shan_ju)
        if ju_zhi_count >= 3:
            result = "旺"
        elif ju_zhi_count >= 1 and shan_jia_zhi in _ZHI_IN_JU:
            result = "待"
    return {"result": result, "day_ju": sorted(day_ju), "shan_ju": shan_ju, "status": "待考证"}


def overlay_hour_facts(
    base: dict[str, Any],
    *,
    gans: list[str],
    zhis: list[str],
    shan_jia_zhi: str | None,
    day_ganzhi: str,
    month_zhi: str,
    mountain_name: str,
    doushou_tu_changsheng: str,
    zibai_fly: str = "shun",
) -> dict[str, Any]:
    """把「日级事实」叠加成「候选级事实」。

    只替换随时支变化的键，其余键共享引用（只读）。**不得**在这里写入
    与时辰无关的字段，否则日级缓存失去意义。
    """
    facts = dict(base)
    facts["structure"] = structure_facts(gans=gans, zhis=zhis, shan_jia_zhi=shan_jia_zhi)
    xk = xunkong_of(day_ganzhi)
    facts["xunkong"] = {
        "day": {"head": xk.head, "empty": list(xk.empty)},
        "hits": [z for z in zhis if z in xk.empty],
        "status": "已考证",
        "note": "旬空按日柱所在旬取，公版表",
    }
    facts["tongguan"] = tongguan_facts(gans=gans, zhis=zhis)
    facts["sanhe_ju"] = sanhe_ju_facts(zhis=zhis, shan_jia_zhi=shan_jia_zhi)
    facts["doushou"] = derive_doushou_facts(
        mountain_name=mountain_name,
        gans=list(gans),
        month_zhi=month_zhi,
        tu_changsheng=doushou_tu_changsheng,
    )
    # 时紫白必须在此重算：日级缓存不含时柱（见 derive_facts 里的 zibai 注释）。
    zibai = dict(base.get("zibai") or {})
    day_plate = zibai.get("day") or {}
    hour_zhi = zhis[3] if len(zhis) >= 4 else None
    if hour_zhi and day_plate.get("dun"):
        zibai["hour"] = derive_zibai_hour(
            day_zhi=day_ganzhi[1],
            hour_zhi=hour_zhi,
            yang_dun=day_plate["dun"] == "阳遁",
            mountain_name=mountain_name,
            fly_caliber=zibai_fly,
        )
    else:
        zibai["hour"] = {"center": None, "error": "日盘阴阳遁不可得，时盘不判定"}
    facts["zibai"] = zibai
    # 时家建除 / 黄道时：与日家同一公式，只是把「日支」换成「时支」。
    # 必须在候选级重算——日级缓存不含时柱（2026-11-02 P0 的同类形态）。
    hour_zhi_all = zhis[3] if len(zhis) >= 4 else None
    jc = dict(base.get("jianchu") or {})
    if hour_zhi_all:
        jc["hour"] = {
            "star": jianchu_of(month_zhi, hour_zhi_all),
            "index": jianchu_index(month_zhi, hour_zhi_all),
            "hour_zhi": hour_zhi_all,
        }
    facts["jianchu"] = jc
    hd = dict(base.get("huangdao") or {})
    if hour_zhi_all:
        hd["hour"] = {
            "star": huangdao_of(month_zhi, hour_zhi_all),
            "index": huangdao_index(month_zhi, hour_zhi_all),
            "hour_zhi": hour_zhi_all,
        }
    facts["huangdao"] = hd
    yinfu = dict(base.get("yinfu") or {})
    candidates = dict(yinfu.get("candidates") or {})
    candidates["gans"] = list(gans)
    yinfu["candidates"] = candidates
    facts["yinfu"] = yinfu
    return facts



def derive_facts(
    *,
    year_zhi: str,
    month_zhi: str,
    day_ganzhi: str,
    gans: list[str],
    zhis: list[str],
    mountain: Mountain,
    facing: Mountain | None = None,
    shan_jia_zhi: str | None = None,
    local_date: date | None = None,
    term_dates: dict[str, date] | None = None,
    term_dates_prev: dict[str, date] | None = None,
    include_term_day_itself: bool = False,
    sansha_caliber: str = "direction_group",
    nayin_caliber: str = "undecided",
    nayin_alternatives: list[dict[str, Any]] | None = None,
    doushou_tu_changsheng: str = "shen",
    zibai_fly: str = "shun",
    tiande_caliber: str = "gong_union",
) -> dict[str, Any]:
    """展开 ``facts.*`` 命名空间。

    ``shan_jia_zhi`` 为"山家地支"：坐山若为十二地支山则取本山，若兼向则取兼山
    （如 乾山兼亥 → 亥）。它用于三合扶山检测，属**结构事实**，不含吉凶。

    所有子项均为纯数据（dict/list/str/float/bool），可 JSON 序列化，
    以便写入报告的 params_snapshot 并复现。
    """
    facts: dict[str, Any] = {}

    # ---- 三煞 ----
    for basis, zhi in (("year", year_zhi), ("month", month_zhi)):
        sv: FactValue = sansha_of(zhi, basis=basis, caliber=sansha_caliber)
        data = dict(sv.value)
        data.update(_hits(data["mountains"], mountain, facing))
        data["status"] = sv.status
        data["note"] = sv.note
        facts.setdefault("sansha", {})[basis] = data

    # ---- 太岁 / 岁破 / 月破 ----
    ts = taisui_azimuth(year_zhi)
    facts["taisui"] = {**ts.value, "status": ts.status, "note": ts.note}

    sp = suipo_azimuth(year_zhi)
    facts["suipo"] = {
        **sp.value,
        "hit_mountain": mountain.name == sp.value["zhi"],
        "hit_facing": facing is not None and facing.name == sp.value["zhi"],
        "status": sp.status,
        "note": sp.note,
    }

    yp = yuepo_azimuth(month_zhi)
    facts["yuepo"] = {
        **yp.value,
        "hit_mountain": mountain.name == yp.value["zhi"],
        "hit_facing": facing is not None and facing.name == yp.value["zhi"],
        "status": yp.status,
        "note": yp.note,
    }

    # ---- 五黄 ----
    # 必须按**紫白年**（立春换年）取，否则 1 月 1 日至立春之间会取到下一年的入中星，
    # 与 facts.zibai.year 相差两位五、方位相反。见 shensha.wuhuang_year_of_date 的说明。
    if local_date is not None:
        wh = wuhuang_year_of_date(local_date, year_zhi)
        wh_data = dict(wh.value)
        # 山级：仅宫心那一山（既有语义，PUB-WUHUANG-001 依赖此字段，勿改）
        wh_data["hit_mountain"] = wh_data.get("mountain") == mountain.name
        wh_data["hit_facing"] = facing is not None and wh_data.get("mountain") == facing.name
        # 宫级：一宫三山同受五黄（五黄的本来粒度）。新增字段，不替换上面两个。
        palace_mountains = wh_data.get("palace_mountains") or []
        wh_data["hit_palace"] = mountain.name in palace_mountains
        wh_data["hit_palace_facing"] = facing is not None and facing.name in palace_mountains
        wh_data["status"] = wh.status
        wh_data["note"] = wh.note
    else:
        # 无用事日 ⇒ 紫白年（立春换年）不可确定。命中字段给 None 而非 False：
        # 三值逻辑下 `eq true` 得到 unknown，规则降级为「存疑」，
        # 不会伪装成「没有命中」——静默通过是本项目明令禁止的。
        wh_data = {
            "zibai_year": None,
            "center_star": None,
            "palace": None,
            "azimuth": None,
            "mountain": None,
            "palace_mountains": [],
            "hit_mountain": None,
            "hit_facing": None,
            "hit_palace": None,
            "hit_palace_facing": None,
            "status": "待考证",
            "note": "缺少用事日，无法确定紫白年（立春换年），年五黄降级为 unknown",
        }
    facts["wuhuang"] = {"year": wh_data, "month": wuhuang_month(0, month_zhi).to_dict()}

    # ---- 四离四绝 ----
    if local_date is not None and term_dates:
        sili = sili_sijue(local_date, term_dates, include_day_itself=include_term_day_itself)
        facts["sili_sijue"] = {**sili.value, "status": sili.status, "note": sili.note}
    else:
        facts["sili_sijue"] = {
            "hits": [],
            "is_hit": None,
            "status": "待考证",
            "note": "缺少节气日期，无法判定四离四绝",
        }

    # ---- 阴府 ----
    # 阴府须以"坐山纳音"为据，而坐山纳音取决于分金干支取用体系（穿山七十二龙 /
    # 一百二十分金 / 正针三合），该体系属争议项且未裁定。故本系统**不推断**阴府，
    # 只把状态显式暴露为「有争议 / 不提供」，使相关规则降级为 unknown，而非静默通过。
    facts["yinfu"] = {
        "caliber": nayin_caliber,
        "candidates": {
            "value": None,
            "hits": [],
            "single_gan_hits": [],
            "mountain_element": None,
            "gans": list(gans),
            "status": "有争议",
            "note": (
                "阴府以坐山纳音与日课天干化气生克取；坐山纳音的取用体系"
                f"（当前口径={nayin_caliber}）未裁定，故本系统不推断阴府，"
                "相关规则一律降级为 unknown。"
            ),
            # 对比式 unknown：列出各口径各自缺什么，用户可据此决定补哪张表
            "alternatives": list(nayin_alternatives or []),
        }
    }

    # ---- 旬空 ----
    xk = xunkong_of(day_ganzhi)
    facts["xunkong"] = {
        "day": {"head": xk.head, "empty": list(xk.empty)},
        "hits": [z for z in zhis if z in xk.empty],
        "status": "已考证",
        "note": "旬空按日柱所在旬取，公版表",
    }

    # ---- 结构检测（纯关系，不含吉凶） ----
    facts["structure"] = structure_facts(gans=gans, zhis=zhis, shan_jia_zhi=shan_jia_zhi)

    # ---- 玄空大卦 facts（Phase 7 收尾：先天圆图 384 爻 + 两元八运 + 卦气/抽爻）----
    facts["xuankong"] = derive_xuankong_facts(mountain=mountain, facing=facing, local_date=local_date)

    # ---- 斗首五行 facts（Phase 9：斗首五行表 + 十干化气 + 五星 + 番化 + 得位）----
    # 斗首五行 ≠ 正五行（甲山斗首属水、甲干化气属土），必须独立成表。
    facts["doushou"] = derive_doushou_facts(
        mountain_name=mountain.name,
        gans=list(gans),
        month_zhi=month_zhi,
        tu_changsheng=doushou_tu_changsheng,
    )

    # ---- 天星 facts（Phase 8 收尾：pyswisseph 真星历 + 到山到向 + 三合照 + 升殿）----
    facts["tianxing"] = derive_tianxing_facts(
        mountain_name=mountain.name,
        facing_name=facing.name if facing is not None else None,
        local_date=local_date,
    )

    # ---- 紫白四盘（Phase 11：月/日/年三盘在日级，时盘由 overlay 重算）----
    # 时盘**不得**在此计算：日级缓存不含时柱，写进来就会把首个子时的星
    # 带给其余十一个时辰（2026-11-02 P0 的同类形态）。
    _terms_by_year: dict[int, dict[str, date]] = {}
    if local_date is not None:
        if term_dates:
            _terms_by_year[local_date.year] = term_dates
        if term_dates_prev:
            _terms_by_year[local_date.year - 1] = term_dates_prev
    facts["zibai"] = derive_zibai_facts(
        year_zhi=year_zhi,
        month_zhi=month_zhi,
        day_ganzhi=day_ganzhi,
        hour_zhi=None,
        local_date=local_date,
        terms=_terms_by_year or None,
        mountain_name=mountain.name,
        fly_caliber=zibai_fly,
    )

    # ---- 二十八宿值日（Phase 11：七元起宿，纯周期算术）----
    if local_date is not None:
        _xiu = xiu_of_date(local_date)
        facts["xiu"] = {
            "day": _xiu.name,
            "full_name": _xiu.full_name,
            "index": _xiu.index,
            "qizheng": _xiu.qizheng,
            "yuan": yuan_of_date(local_date),
            "weekday_consistent": weekday_consistent(local_date),
            "status": "待考证",
            "note": "七元起宿（一元甲子起虚），锚点 1996-01-28 甲子·星期日·虚宿；星期恒等式自校验。",
        }
    else:
        facts["xiu"] = {"day": None, "status": "待考证", "note": "缺少用事日，值宿不判定"}

    # ---- 吉神表（Phase 11：天德/月德/月德合/天赦）----
    facts["jishen"] = derive_jishen_facts(
        month_zhi=month_zhi,
        day_ganzhi=day_ganzhi,
        tiande_caliber=tiande_caliber,
    )

    # ---- 口径回显（报告必须展示本次用了哪个口径）----
    facts["_calibers"] = {
        "sansha": sansha_caliber,
        "nayin": nayin_caliber,
        "xuankong": facts["xuankong"]["caliber"],
        "tianxing": facts["tianxing"]["caliber"],
        "doushou_tu_changsheng": doushou_tu_changsheng,
        "zibai_fly": zibai_fly,
        "tiande_guaxiang": tiande_caliber,
    }

    # ---- 建除十二神 / 十二黄黑道（一等事实，不依赖任何派别数据文件）----
    # 这两项是纯位移起例（月建起建、月建起青龙，顺行），属最容易做对的一层，
    # 原先只作为 facts.donggong 的子项存在：董公 JSON 一旦缺失就整段变 None，
    # 而它们与董公派其实无关。现提升为独立事实，董公块改为引用同一函数。
    facts["jianchu"] = derive_jianchu_fact(month_zhi=month_zhi, day_zhi=day_ganzhi[1])
    facts["huangdao"] = derive_huangdao_fact(month_zhi=month_zhi, day_zhi=day_ganzhi[1])

    # ---- 董公择日 facts（Phase 6，评审扩展版 spec §2.3）----
    facts.setdefault("donggong", {})
    _dg = facts["donggong"]
    _dg_data = _load_donggong_data()
    if _dg_data is not None:
        day_gz = day_ganzhi  # 如 "甲子"
        year_stem = gans[0] if gans else ""
        month_branch = month_zhi
        # 三星值日
        sanxing = _dg_data.get("sanxing", {}).get("days", {}).get(day_gz, "无")
        _dg["star"] = sanxing
        # 金神七煞
        jinshen_days = _dg_data.get("jinshen", {}).get("by_year_stem", {}).get(year_stem, [])
        _dg["is_jinshen"] = day_gz in jinshen_days
        # 大煞 reject（受死/四废/往亡/十恶大败）
        _is_dasha = False
        dasha_detail = _dg_data.get("dasha", {})
        # 受死
        shou_si = dasha_detail.get("shou_si", {}).get("by_month", {}).get(month_branch, [])
        if day_gz[-1] in shou_si:
            _is_dasha = True
        # 十恶大败
        shie = dasha_detail.get("shi_e_da_bai", {}).get("by_year_stem", {}).get(year_stem, [])
        if day_gz in shie:
            _is_dasha = True
        # 四废（按季节）
        # 季节必须按**节气月**判：四废口诀是「春庚申辛酉、夏壬子癸亥、秋甲寅乙卯、
        # 冬丙午丁巳」，四季以四立（立春/立夏/立秋/立冬）为界。曾按公历月
        # 3-5/6-8/9-11/12-2 取季，立春（2/4）到 3/1、立冬（11/7）到 12/1 之间的
        # 日课会取错季节、查错四废日表。
        _season = _season_of_month_zhi(month_branch)
        sifei = dasha_detail.get("si_fei", {}).get("by_season", {}).get(_season, [])
        if day_gz in sifei:
            _is_dasha = True
        _dg["is_dasha"] = _is_dasha
        # 勾陈黑道
        heidao = _dg_data.get("heidao", {}).get("by_month_branch", {}).get(month_branch, [])
        # 注意：字段名 is_heidao 的历史语义是「**勾陈日**」（单星），不是「黑道日」。
        # DG-GOUCHEN-001 的出处是勾陈条，故保留该语义不动；
        # 十二神全名见 donggong.heidao_star 与一等事实 facts.huangdao（QUESTION Q-019）。
        _dg["is_heidao"] = day_gz[-1] in heidao
        _dg["heidao_star"] = facts["huangdao"]["day"]["star"]
        # 建除十二神：与 facts.jianchu 同源（唯一计算入口 core_symbol.jianchu）。
        #   此处保留 facts.donggong.jianchu 路径以兼容既有规则 DG-JIANCHU-001。
        _dg["jianchu"] = facts["jianchu"]["star"]
        _dg["status"] = "待考证"
    else:
        _dg["star"] = None
        _dg["is_jinshen"] = None
        _dg["is_dasha"] = None
        _dg["is_heidao"] = None
        # 十二神与建除不依赖董公数据文件，缺文件也照算（不再静默降级为 None）。
        _dg["heidao_star"] = facts["huangdao"]["day"]["star"]
        _dg["jianchu"] = facts["jianchu"]["star"]
        _dg["status"] = "待考证"

    # ---- 正五行调候 facts（Phase 4 收尾：引用 qiongtong_biaojian_120.json）----
    # 数据缺失时显式降级（applied=None → 相关规则 unknown），不再用裸 except 吞异常：
    # 吞异常会把「数据文件坏了」伪装成「该格无调候」，两者在报告里必须可区分。
    _tiao_data = _load_data_file("qiongtong_biaojian_120.json")
    # gans 顺序为年、月、日、时；调候按日干取，不能用年干（gans[0]）。
    _day_gan = gans[2] if len(gans) >= 3 else "甲"
    if _tiao_data is None:
        facts["tiaohou"] = {
            "applied": None,
            "day_gan": _day_gan,
            "month_zhi": month_zhi,
            "status": "待考证",
            "note": "调候数据文件 qiongtong_biaojian_120.json 缺失或损坏，调候降级为 unknown",
        }
    else:
        _tiao_entry = _tiao_data.get("tiaohou_120", {}).get(_day_gan, {}).get(month_zhi)
        facts["tiaohou"] = {
            "applied": _tiao_entry is not None,
            "adjust_gan": _tiao_entry.split(",") if _tiao_entry else [],
            "day_gan": _day_gan,
            "month_zhi": month_zhi,
            "detail": _tiao_entry,
            "status": "待考证",
        }

    # ---- 正五行通关 facts（Phase 4 收尾：四柱五行计数 + 相战检测）----
    facts["tongguan"] = tongguan_facts(gans=gans, zhis=zhis)

    # ---- 三合局判定 facts（Phase 5）----
    facts["sanhe_ju"] = sanhe_ju_facts(zhis=zhis, shan_jia_zhi=shan_jia_zhi)

    # ---- 禄马贵人到山 facts（Phase 5）----
    _lu_ma_gui_data = _load_data_file("lu_ma_gui_ren.json")
    facts.setdefault("lumaguiren", {"to_shan": None, "to_ming": None, "status": "待考证"})
    if _lu_ma_gui_data and shan_jia_zhi:
        # 查日课天干的禄神是否=坐山
        # 禄神/贵人按日干取（gans[2]）；年干仅用于年家神煞（如金神七煞）。
        _day_gan_0 = gans[2] if len(gans) >= 3 else ""
        _lu = _lu_ma_gui_data.get("lu_shen", {}).get(_day_gan_0)
        _lu_to_shan = _lu == shan_jia_zhi if _lu else False
        # 查贵人
        _gr = _lu_ma_gui_data.get("tian_yi_gui_ren", {}).get(_day_gan_0, [])
        _gr_to_shan = shan_jia_zhi in _gr if _gr else False
        # 查驿马（按年支三合局）
        _year_zhi_ma = _lu_ma_gui_data.get("yi_ma", {}).get(year_zhi, None) if year_zhi else None
        _ma_to_shan = _year_zhi_ma == shan_jia_zhi if _year_zhi_ma else False
        facts["lumaguiren"] = {
            "to_shan": _lu_to_shan or _gr_to_shan or _ma_to_shan,
            "lu_to_shan": _lu_to_shan, "gr_to_shan": _gr_to_shan,
            "ma_to_shan": _ma_to_shan,
            "lu": _lu, "gui_ren": _gr, "yi_ma": _year_zhi_ma,
            "status": "待考证",
        }

    # ---- 不提供的事实：显式登记为 None，避免"静默通过" ----
    for spec in FACT_REGISTRY:
        if spec.provider != "本系统不提供":
            continue
        root = spec.name.split(".")[0]
        facts.setdefault(root, {"value": None, "status": spec.status, "note": spec.note})

    return facts


# C19-exempt: 单一不可变参数（进程常量数据/日历换算），键由解释器按参数构造，无复合串味面
@lru_cache(maxsize=32)
def _load_data_file(filename: str) -> dict[str, Any] | None:
    """读取 ``core-rule/config/data`` 下的 JSON 数据文件（进程级缓存）。

    查表型数据（董公/调候/禄马贵人等）按调用方约定**只读**；缓存避免逐候选
    文件 IO（4380 候选曾因此多耗 ~1.7s）。文件缺失/损坏返回 None 并缓存。
    """
    import json
    path = Path(__file__).resolve().parent.parent.parent.parent / "core-rule" / "config" / "data" / filename
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _load_donggong_data() -> dict[str, Any] | None:
    """加载董公择日 JSON 数据（合并 4 个文件为一个 dict，经缓存）。"""
    sanxing = _load_data_file("donggong_sanxing_60jiazi.json")
    jinshen = _load_data_file("donggong_jinshen_qisha.json")
    dasha = _load_data_file("donggong_dasha_reject.json")
    heidao = _load_data_file("donggong_gouchen_heidao.json")
    if sanxing is None and jinshen is None and dasha is None and heidao is None:
        return None
    return {"sanxing": sanxing, "jinshen": jinshen, "dasha": dasha, "heidao": heidao}


def _season_of_month_zhi(month_zhi: str) -> str:
    """节气月支 → 季节（四立为界：寅卯辰春、巳午未夏、申酉戌秋、亥子丑冬）。

    四废、天赦等"按季"的起例都必须走这里，而不是公历月——公历月与节气季
    在四立前后各差 2-4 周，足以让一张季表整段取错。
    """
    if month_zhi in ("寅", "卯", "辰"):
        return "spring"
    if month_zhi in ("巳", "午", "未"):
        return "summer"
    if month_zhi in ("申", "酉", "戌"):
        return "autumn"
    if month_zhi in ("亥", "子", "丑"):
        return "winter"
    raise ValueError(f"非法月支: {month_zhi}")


def _mountain_is_branch(mountain: Mountain) -> bool:
    """坐山是否为十二地支山（四维山 乾坤艮巽 无纳音）。"""
    return mountain.name in ZHI


_ = (MOUNTAINS_24, mountain_of_azimuth, Callable, nayin_element_of, yinfu_candidates)
