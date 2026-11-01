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
from .nayin import nayin_element_of, xunkong_of
from .shensha import (
    FactStatus,
    FactValue,
    sansha_of,
    sili_sijue,
    suipo_azimuth,
    taisui_azimuth,
    wuhuang_month,
    wuhuang_year,
    yinfu_candidates,
    yuepo_azimuth,
)

__all__ = [
    "FACT_REGISTRY",
    "FactSpec",
    "derive_facts",
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
    include_term_day_itself: bool = False,
    sansha_caliber: str = "direction_group",
    nayin_caliber: str = "undecided",
    nayin_alternatives: list[dict[str, Any]] | None = None,
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
    wh = wuhuang_year(local_date.year if local_date else 2000)
    wh_data = dict(wh.value)
    wh_data["hit_mountain"] = wh_data.get("mountain") == mountain.name
    wh_data["hit_facing"] = facing is not None and wh_data.get("mountain") == facing.name
    wh_data["status"] = wh.status
    wh_data["note"] = wh.note
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
    facts["structure"] = {
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

    # ---- 口径回显（报告必须展示本次用了哪个口径）----
    facts["_calibers"] = {"sansha": sansha_caliber, "nayin": nayin_caliber}

    # ---- 天星 facts（Phase 8，须 Swiss Ephemeris/skyfield——当前 unknown）----
    facts.setdefault("tianxing", {
        "sun_daoshan": None, "moon_daoshan": None,
        "sanhe_gongzhao": None, "jiafu": None,
        "status": "待考证",
        "note": "天星七政四余到山到向——须真实星历计算（Swiss Ephemeris/skyfield），当前未集成",
    })

    # ---- 玄空大卦 facts（Phase 7，起例待实现→unknown）----
    facts.setdefault("xuankong", {
        "guayun_current": None, "chouyao": None,
        "guaqi_peihe": None, "wangqi_daoshan": None,
        "status": "待考证",
        "note": "玄空大卦 64 卦圆图/卦运/抽爻换象/卦气配合——起例待实现",
    })

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
        if local_date:
            _season = _get_season(local_date.month)
            sifei = dasha_detail.get("si_fei", {}).get("by_season", {}).get(_season, [])
            if day_gz in sifei:
                _is_dasha = True
        _dg["is_dasha"] = _is_dasha
        # 勾陈黑道
        heidao = _dg_data.get("heidao", {}).get("by_month_branch", {}).get(month_branch, [])
        _dg["is_heidao"] = day_gz[-1] in heidao
        _dg["status"] = "待考证"
    else:
        _dg["star"] = None
        _dg["is_jinshen"] = None
        _dg["is_dasha"] = None
        _dg["is_heidao"] = None
        _dg["status"] = "待考证"

    # ---- 不提供的事实：显式登记为 None，避免"静默通过" ----
    for spec in FACT_REGISTRY:
        if spec.provider != "本系统不提供":
            continue
        root = spec.name.split(".")[0]
        facts.setdefault(root, {"value": None, "status": spec.status, "note": spec.note})

    return facts


def _load_donggong_data() -> dict[str, Any] | None:
    """加载董公择日 JSON 数据（合并 4 个文件为一个 dict）。"""
    import json
    data_dir = Path(__file__).resolve().parent.parent.parent.parent / "core-rule" / "config" / "data"
    try:
        sanxing = json.loads((data_dir / "donggong_sanxing_60jiazi.json").read_text(encoding="utf-8"))
        jinshen = json.loads((data_dir / "donggong_jinshen_qisha.json").read_text(encoding="utf-8"))
        dasha = json.loads((data_dir / "donggong_dasha_reject.json").read_text(encoding="utf-8"))
        heidao = json.loads((data_dir / "donggong_gouchen_heidao.json").read_text(encoding="utf-8"))
        return {"sanxing": sanxing, "jinshen": jinshen, "dasha": dasha, "heidao": heidao}
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _get_season(month: int) -> str:
    """公历月 → 季节（四废日按季节查）。"""
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def _mountain_is_branch(mountain: Mountain) -> bool:
    """坐山是否为十二地支山（四维山 乾坤艮巽 无纳音）。"""
    return mountain.name in ZHI


_ = (MOUNTAINS_24, mountain_of_azimuth, Callable, nayin_element_of, yinfu_candidates)
