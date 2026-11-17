"""正五行扶山 facts（事实层，不做吉凶判断）。

口径
----
以坐山正五行为「我」，四柱天干／地支五行为「他」，逐项给出五种关系：

- 比和：同我
- 生入：他生我（进气）
- 克入：他克我（进气）
- 生出：我生他（退气）
- 克出：我克他（退气）

**本模块只输出关系与计数，不输出「吉／凶／分数」**：
生克档位如何映射到吉凶（以及是否区分大吉／大凶）属人类裁定，
登记为 Q-029；裁定前任何 grade 字段都不得进入规则或共识。

月令旺衰用四季旺相休囚死（当令者旺、我生者相、生我者休、克我者囚、我克者死），
只作审计信息，不参与计数。
"""

from __future__ import annotations

from typing import Any

from .ganzhi import wuxing_of_gan, wuxing_of_zhi
from .mountain import MOUNTAINS_24

__all__ = [
    "ELEMENTS",
    "SHAN_WUXING_24",
    "SHENG",
    "KE",
    "RELATIONS",
    "SEASON_OF_MONTH",
    "SEASON_ELEMENT",
    "SANHE_JU",
    "GAN_HE",
    "ZHI_HE",
    "ZHI_CHONG",
    "LIN_GUAN_DI_WANG",
    "relation_of",
    "month_stage_of",
    "derive_zhengwuxing_facts",
    "derive_bulong_facts",
    "derive_xiangzhu_facts",
]

ELEMENTS: tuple[str, ...] = ("木", "火", "土", "金", "水")

#: 二十四山正五行（子水…壬水；乾坤艮巽为四维）
SHAN_WUXING_24: dict[str, str] = {
    "子": "水", "癸": "水",
    "丑": "土", "艮": "土", "寅": "木", "甲": "木",
    "卯": "木", "乙": "木", "辰": "土", "巽": "木",
    "巳": "火", "丙": "火", "午": "火", "丁": "火",
    "未": "土", "坤": "土", "申": "金", "庚": "金",
    "酉": "金", "辛": "金", "戌": "土", "乾": "金",
    "亥": "水", "壬": "水",
}

SHENG: dict[str, str] = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE: dict[str, str] = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

RELATIONS: tuple[str, ...] = ("比和", "生入", "克入", "生出", "克出")

SEASON_OF_MONTH: dict[str, str] = {
    "寅": "春", "卯": "春", "辰": "四季",
    "巳": "夏", "午": "夏", "未": "四季",
    "申": "秋", "酉": "秋", "戌": "四季",
    "亥": "冬", "子": "冬", "丑": "四季",
}

SEASON_ELEMENT: dict[str, str] = {"春": "木", "夏": "火", "秋": "金", "冬": "水", "四季": "土"}

#: 三合局（土无三合局，传统以寄宫论，故不列）
SANHE_JU: dict[str, tuple[str, str, str]] = {
    "水": ("申", "子", "辰"),
    "木": ("亥", "卯", "未"),
    "火": ("寅", "午", "戌"),
    "金": ("巳", "酉", "丑"),
}

#: 天干五合 / 地支六合 / 地支六冲（定义级表，不含吉凶）
GAN_HE: dict[str, str] = {
    "甲": "己", "己": "甲",
    "乙": "庚", "庚": "乙",
    "丙": "辛", "辛": "丙",
    "丁": "壬", "壬": "丁",
    "戊": "癸", "癸": "戊",
}
ZHI_HE: dict[str, str] = {
    "子": "丑", "丑": "子",
    "寅": "亥", "亥": "寅",
    "卯": "戌", "戌": "卯",
    "辰": "酉", "酉": "辰",
    "巳": "申", "申": "巳",
    "午": "未", "未": "午",
}
ZHI_CHONG: dict[str, str] = {
    "子": "午", "午": "子",
    "丑": "未", "未": "丑",
    "寅": "申", "申": "寅",
    "卯": "酉", "酉": "卯",
    "辰": "戌", "戌": "辰",
    "巳": "亥", "亥": "巳",
}

#: 五行十二长生的临官／帝旺位（阳干顺行；土寄宫有申/寅异说，故不列）
LIN_GUAN_DI_WANG: dict[str, tuple[str, str]] = {
    "木": ("卯", "寅"),
    "火": ("午", "巳"),
    "金": ("酉", "申"),
    "水": ("子", "亥"),
}


def relation_of(wo: str, ta: str) -> str:
    """返回「我」与「他」的五行关系。"""
    if wo not in ELEMENTS or ta not in ELEMENTS:
        raise ValueError(f"非法五行: {wo!r} / {ta!r}")
    if wo == ta:
        return "比和"
    if SHENG[ta] == wo:
        return "生入"
    if KE[ta] == wo:
        return "克入"
    if SHENG[wo] == ta:
        return "生出"
    if KE[wo] == ta:
        return "克出"
    raise ValueError(f"五行关系未覆盖: {wo!r} / {ta!r}")  # pragma: no cover


def month_stage_of(element: str, month_zhi: str) -> str:
    """五行在某月支的旺相休囚死。"""
    if element not in ELEMENTS:
        raise ValueError(f"非法五行: {element!r}")
    if month_zhi not in SEASON_OF_MONTH:
        raise ValueError(f"非法月支: {month_zhi!r}")
    season = SEASON_ELEMENT[SEASON_OF_MONTH[month_zhi]]
    if element == season:
        return "旺"
    if SHENG[season] == element:
        return "相"
    if SHENG[element] == season:
        return "休"
    if KE[element] == season:
        return "囚"
    if KE[season] == element:
        return "死"
    raise ValueError(f"旺衰未覆盖: {element!r} / {month_zhi!r}")  # pragma: no cover


def derive_zhengwuxing_facts(
    *,
    mountain: str,
    gans: list[str],
    zhis: list[str],
    month_zhi: str,
) -> dict[str, Any]:
    """展开 ``facts.zhengwuxing.fushan``。

    ``gans`` / ``zhis`` 顺序为年、月、日、时。缺项按实际长度输出，不补默认值。
    """
    if mountain not in SHAN_WUXING_24:
        raise ValueError(f"未知坐山: {mountain!r}")
    if len(gans) != len(zhis):
        # 静默截断会让缺失柱悄悄消失，宁可报错
        raise ValueError(f"天干地支数量不一致: {len(gans)} != {len(zhis)}")
    shan_element = SHAN_WUXING_24[mountain]
    season = SEASON_OF_MONTH[month_zhi]
    stage = month_stage_of(shan_element, month_zhi)

    gan_counts = {r: 0 for r in RELATIONS}
    zhi_counts = {r: 0 for r in RELATIONS}
    pillars: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = [
        {
            "step": 1,
            "what": "坐山正五行",
            "input": {"mountain": mountain},
            "output": {"element": shan_element},
        },
        {
            "step": 2,
            "what": "月令旺衰",
            "input": {"month_zhi": month_zhi, "season": season},
            "output": {"element": shan_element, "stage": stage},
        },
    ]

    labels = ("年", "月", "日", "时")
    for i, (gan, zhi) in enumerate(zip(gans, zhis)):
        try:
            ger = wuxing_of_gan(gan)
            zer = wuxing_of_zhi(zhi)
        except KeyError as exc:
            raise ValueError(f"非法干支: {gan!r} / {zhi!r}") from exc
        gan_rel = relation_of(shan_element, ger)
        zhi_rel = relation_of(shan_element, zer)
        gan_counts[gan_rel] += 1
        zhi_counts[zhi_rel] += 1
        pillar = {
            "label": labels[i] if i < len(labels) else str(i),
            "gan": gan,
            "gan_element": ger,
            "gan_relation": gan_rel,
            "zhi": zhi,
            "zhi_element": zer,
            "zhi_relation": zhi_rel,
        }
        pillars.append(pillar)
        audit.append(
            {
                "step": 3 + i,
                "what": f"{pillar['label']}柱生克",
                "input": {"gan": gan, "zhi": zhi, "shan_element": shan_element},
                "output": {"gan_element": ger, "zhi_element": zer, "gan_relation": gan_rel, "zhi_relation": zhi_rel},
            }
        )

    audit.append(
        {
            "step": 3 + len(pillars),
            "what": "关系计数",
            "input": {
                "gan_relations": [p["gan_relation"] for p in pillars],
                "zhi_relations": [p["zhi_relation"] for p in pillars],
            },
            "output": {"gan_counts": dict(gan_counts), "zhi_counts": dict(zhi_counts)},
        }
    )

    return {
        "shan": {"name": mountain, "element": shan_element, "month_stage": stage},
        "month": {"zhi": month_zhi, "season": season, "season_element": SEASON_ELEMENT[season]},
        "pillars": pillars,
        "gan_counts": gan_counts,
        "zhi_counts": zhi_counts,
        "audit_chain": audit,
        "status": "待考证",
        "note": "只给五行生克关系与月令旺衰，不判吉凶；档位分界待 Q-029 人类裁定",
    }


def derive_bulong_facts(
    *,
    long_element: str,
    zhis: list[str],
    month_zhi: str,
) -> dict[str, Any]:
    """展开补龙结构 facts：三合局是否齐全、月令是否三合月／临官帝旺。

    ``long_element`` 是入首龙五行（木火土金水）。**只回答结构是否成立**，
    不输出「补龙成功／吉凶／分值」——那些属 Q-029 之后的人类口径。
    土无三合局（传统寄宫），故土龙的 ``sanhe_ju`` 为 None，不伪造三合。
    """
    if long_element not in ELEMENTS:
        raise ValueError(f"非法入首龙五行: {long_element!r}")
    for zhi in zhis:
        try:
            wuxing_of_zhi(zhi)
        except KeyError as exc:
            raise ValueError(f"非法地支: {zhi!r}") from exc
    if month_zhi not in SEASON_OF_MONTH:
        raise ValueError(f"非法月支: {month_zhi!r}")

    ju = SANHE_JU.get(long_element)
    present = set(zhis)
    sanhe_complete = bool(ju) and set(ju) <= present
    sanhe_month = bool(ju) and month_zhi in ju
    stage = month_stage_of(long_element, month_zhi)

    office = LIN_GUAN_DI_WANG.get(long_element)
    if office is None:
        month_office = None
        office_note = "土寄宫有申/寅异说，临官帝旺未裁定，不输出"
    else:
        lin, di = office
        month_office = "临官" if month_zhi == lin else "帝旺" if month_zhi == di else None
        office_note = None

    audit = [
        {
            "step": 1,
            "what": "入首龙五行",
            "input": {"long_element": long_element},
            "output": {"element": long_element},
        },
        {
            "step": 2,
            "what": "三合局补龙",
            "input": {"zhis": list(zhis), "expected_ju": list(ju) if ju else None},
            "output": {
                "sanhe_ju": list(ju) if ju else None,
                "sanhe_complete": sanhe_complete,
            },
        },
        {
            "step": 3,
            "what": "月令三合／临官帝旺",
            "input": {"month_zhi": month_zhi, "sanhe_ju": list(ju) if ju else None},
            "output": {
                "sanhe_month": sanhe_month,
                "month_stage": stage,
                "month_office": month_office,
                "office_note": office_note,
            },
        },
    ]
    return {
        "long": {"element": long_element, "sanhe_ju": list(ju) if ju else None},
        "zhis": list(zhis),
        "month": {
            "zhi": month_zhi,
            "sanhe_month": sanhe_month,
            "month_stage": stage,
            "month_office": month_office,
            "office_note": office_note,
        },
        "sanhe_complete": sanhe_complete,
        "audit_chain": audit,
        "status": "待考证",
        "note": "只给补龙结构（三合局／月令），不判吉凶；档位与取舍待 Q-029 人类裁定",
    }


def derive_xiangzhu_facts(
    *,
    person_ganzhi: str,
    gans: list[str],
    zhis: list[str],
) -> dict[str, Any]:
    """展开相主关系 facts：主命干支与四柱的冲／合／生／克。

    ``person_ganzhi`` 为主命干支（如 ``庚戌``）。只输出关系与计数，
    不输出「相主吉凶／档位／分值」。五行关系以**主命为「我」**。
    """
    if not isinstance(person_ganzhi, str) or len(person_ganzhi) != 2:
        raise ValueError(f"主命干支必须是两字: {person_ganzhi!r}")
    if len(gans) != len(zhis):
        raise ValueError(f"天干地支数量不一致: {len(gans)} != {len(zhis)}")

    person_gan, person_zhi = person_ganzhi[0], person_ganzhi[1]
    try:
        person_gan_element = wuxing_of_gan(person_gan)
        person_zhi_element = wuxing_of_zhi(person_zhi)
    except KeyError as exc:
        raise ValueError(f"非法主命干支: {person_ganzhi!r}") from exc

    labels = ("年", "月", "日", "时")
    pillars: list[dict[str, Any]] = []
    counts = {"gan_he": 0, "zhi_he": 0, "zhi_chong": 0}
    audit: list[dict[str, Any]] = [
        {
            "step": 1,
            "what": "主命五行",
            "input": {"person_ganzhi": person_ganzhi},
            "output": {"gan_element": person_gan_element, "zhi_element": person_zhi_element},
        }
    ]
    for i, (gan, zhi) in enumerate(zip(gans, zhis)):
        try:
            gan_element = wuxing_of_gan(gan)
            zhi_element = wuxing_of_zhi(zhi)
        except KeyError as exc:
            raise ValueError(f"非法干支: {gan!r} / {zhi!r}") from exc
        gan_he = GAN_HE.get(person_gan) == gan
        zhi_he = ZHI_HE.get(person_zhi) == zhi
        zhi_chong = ZHI_CHONG.get(person_zhi) == zhi
        counts["gan_he"] += int(gan_he)
        counts["zhi_he"] += int(zhi_he)
        counts["zhi_chong"] += int(zhi_chong)
        pillar = {
            "label": labels[i] if i < len(labels) else str(i),
            "gan": gan,
            "gan_element": gan_element,
            "gan_relation": relation_of(person_gan_element, gan_element),
            "gan_he": gan_he,
            "zhi": zhi,
            "zhi_element": zhi_element,
            "zhi_relation": relation_of(person_zhi_element, zhi_element),
            "zhi_he": zhi_he,
            "zhi_chong": zhi_chong,
        }
        pillars.append(pillar)
        audit.append(
            {
                "step": 2 + i,
                "what": f"{pillar['label']}柱与主命关系",
                "input": {
                    "person_ganzhi": person_ganzhi,
                    "gan": gan,
                    "zhi": zhi,
                },
                "output": {
                    "gan_relation": pillar["gan_relation"],
                    "gan_he": gan_he,
                    "zhi_relation": pillar["zhi_relation"],
                    "zhi_he": zhi_he,
                    "zhi_chong": zhi_chong,
                },
            }
        )
    audit.append(
        {
            "step": 2 + len(pillars),
            "what": "关系计数",
            "input": {"pillars": [p["label"] for p in pillars]},
            "output": dict(counts),
        }
    )
    return {
        "person": {
            "ganzhi": person_ganzhi,
            "gan_element": person_gan_element,
            "zhi_element": person_zhi_element,
        },
        "pillars": pillars,
        "counts": counts,
        "audit_chain": audit,
        "status": "待考证",
        "note": "只给冲／合／生／克关系，不判吉凶；相主档位待 Q-029 人类裁定",
    }


def _validate_tables() -> None:
    if set(SHAN_WUXING_24) != set(MOUNTAINS_24):
        raise RuntimeError(f"二十四山正五行表未覆盖: {sorted(set(MOUNTAINS_24) - set(SHAN_WUXING_24))}")
    if set(SHAN_WUXING_24.values()) - set(ELEMENTS):
        raise RuntimeError("二十四山正五行表含非法五行")
    if set(SHENG) != set(ELEMENTS) or set(KE) != set(ELEMENTS):
        raise RuntimeError("生克表未覆盖五行")
    if set(SANHE_JU) - set(ELEMENTS):
        raise RuntimeError("三合局表含非法五行")
    if set(GAN_HE) != set("甲乙丙丁戊己庚辛壬癸") or len(GAN_HE) != 10:
        raise RuntimeError("天干五合表未覆盖十干")
    if set(ZHI_HE) != set(SEASON_OF_MONTH) or set(ZHI_CHONG) != set(SEASON_OF_MONTH):
        raise RuntimeError("地支六合／六冲表未覆盖十二支")


_validate_tables()
