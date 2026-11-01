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
from .tianxing import derive_tianxing_facts
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

    # ---- 玄空大卦 facts（Phase 7 收尾：先天圆图 384 爻 + 两元八运 + 卦气/抽爻）----
    facts["xuankong"] = derive_xuankong_facts(mountain=mountain, facing=facing, local_date=local_date)

    # ---- 天星 facts（Phase 8 收尾：pyswisseph 真星历 + 到山到向 + 三合照 + 升殿）----
    facts["tianxing"] = derive_tianxing_facts(
        mountain_name=mountain.name,
        facing_name=facing.name if facing is not None else None,
        local_date=local_date,
    )

    # ---- 口径回显（报告必须展示本次用了哪个口径）----
    facts["_calibers"] = {
        "sansha": sansha_caliber,
        "nayin": nayin_caliber,
        "xuankong": facts["xuankong"]["caliber"],
        "tianxing": facts["tianxing"]["caliber"],
    }

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

    # ---- 正五行调候 facts（Phase 4 收尾：引用 qiongtong_biaojian_120.json）----
    facts.setdefault("tiaohou", {})
    try:
        import json as _json
        _tiao_path = Path(__file__).resolve().parent.parent.parent.parent / "core-rule" / "config" / "data" / "qiongtong_biaojian_120.json"
        _tiao_data = _json.loads(_tiao_path.read_text(encoding="utf-8"))
        _day_gan = gans[0] if gans else "甲"
        _month_key = {"子": "子", "丑": "丑", "寅": "寅", "卯": "卯", "辰": "辰",
                      "巳": "巳", "午": "午", "未": "未", "申": "申", "酉": "酉",
                      "戌": "戌", "亥": "亥"}.get(month_zhi, "寅")
        _tiao_entry = _tiao_data.get("tiaohou_120", {}).get(_day_gan, {}).get(_month_key)
        facts["tiaohou"] = {
            "applied": _tiao_entry is not None,
            "adjust_gan": _tiao_entry.split(",") if _tiao_entry else [],
            "day_gan": _day_gan,
            "month_zhi": month_zhi,
            "detail": _tiao_entry,
            "status": "待考证",
        }
    except Exception:
        facts["tiaohou"] = {"applied": None, "status": "待考证"}

    # ---- 正五行通关 facts（Phase 4 收尾：四柱五行计数 + 相战检测）----
    WUXING_MAP = {"甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土",
                  "庚":"金","辛":"金","壬":"水","癸":"水"}
    _wuxing_count = {"木":0,"火":0,"土":0,"金":0,"水":0}
    for g in gans:
        if g in WUXING_MAP:
            _wuxing_count[WUXING_MAP[g]] += 1
    for z in zhis:
        _gz_wx = {"子":"水","丑":"土","寅":"木","卯":"木","辰":"土","巳":"火",
                  "午":"火","未":"土","申":"金","酉":"金","戌":"土","亥":"水"}
        if z in _gz_wx:
            _wuxing_count[_gz_wx[z]] += 1
    # 相战检测：两五行计数均 >= 2 且相克
    _xk = {"木":"土","土":"水","水":"火","火":"金","金":"木"}
    _conflicts = []
    for wx1, wx2 in [("木","金"),("金","木"),("水","火"),("火","水"),("木","土"),("土","木")]:
        if _wuxing_count.get(wx1,0) >= 2 and _wuxing_count.get(wx2,0) >= 2:
            _conflicts.append(f"{wx1}{wx2}战")
    # 通关五行：金木战取水，水火战取木，木土战取火，土水战取金，木金战取水(金克木→水通)
    _tongguan_map = {"金木":"水","木金":"水","水火":"木","火水":"木",
                     "木土":"火","土木":"火","土水":"金","水土":"金"}
    _tongguan = None
    for pair in _conflicts:
        key = pair.replace("战","")
        if key in _tongguan_map:
            _tongguan = _tongguan_map[key]
            break
    facts.setdefault("tongguan", {
        "conflicts": _conflicts, "tongguan_element": _tongguan,
        "wuxing_count": _wuxing_count, "status": "待考证",
    })

    # ---- 三合局判定 facts（Phase 5）----
    SANHE_JU = {"申子辰":"水","亥卯未":"木","寅午戌":"火","巳酉丑":"金"}
    ZHI_IN_JU = {}
    for ju_name, wx in SANHE_JU.items():
        for z in ju_name:
            ZHI_IN_JU[z] = ju_name
    # 日课地支（四柱地支）在哪个三合局
    _day_ju = set()
    for z in zhis:
        if z in ZHI_IN_JU:
            _day_ju.add(ZHI_IN_JU[z])
    # 坐山支在哪个三合局
    _shan_ju = ZHI_IN_JU.get(shan_jia_zhi) if shan_jia_zhi else None
    # 三合局判定：日课地支有 ≥2 个同局 + 坐山支同局 → 成局
    _sanhe_ju_result = "平"
    if _shan_ju and _shan_ju in _day_ju:
        _ju_zhi_count = sum(1 for z in zhis if ZHI_IN_JU.get(z) == _shan_ju)
        if _ju_zhi_count >= 3:
            _sanhe_ju_result = "旺"
        elif _ju_zhi_count >= 1 and shan_jia_zhi in ZHI_IN_JU:
            _sanhe_ju_result = "待"
    facts.setdefault("sanhe_ju", {
        "result": _sanhe_ju_result, "day_ju": sorted(_day_ju),
        "shan_ju": _shan_ju, "status": "待考证",
    })

    # ---- 禄马贵人到山 facts（Phase 5）----
    _lu_ma_gui_data = None
    try:
        import json as _json
        _lmg_path = Path(__file__).resolve().parent.parent.parent.parent / "core-rule" / "config" / "data" / "lu_ma_gui_ren.json"
        _lu_ma_gui_data = _json.loads(_lmg_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    facts.setdefault("lumaguiren", {"to_shan": None, "to_ming": None, "status": "待考证"})
    if _lu_ma_gui_data and shan_jia_zhi:
        # 查日课天干的禄神是否=坐山
        _day_gan_0 = gans[0] if gans else ""
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
