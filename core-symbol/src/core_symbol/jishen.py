"""吉神表：天德 / 月德 / 月德合 / 天赦（符号层，纯查表，不含吉凶）。

本模块只回答「本月之德落在何干（或何宫）、今日是否值德」，
**不说**「值德者必吉」。后者是断言级（``PUB-TIANDE-001`` 等），须原文与签名。

起例与来源
----------
- **天德**（《协纪辨方书·义例》）：口诀「正丁二坤宫，三壬四辛同，五乾六甲上，
  七癸八艮中，九丙十居乙，子巽丑庚从」。即按月建（寅=正月）取干或卦：
  寅丁、卯坤、辰壬、巳辛、午乾、未甲、申癸、酉艮、戌丙、亥乙、子巽、丑庚。
- **月德**：寅午戌月丙、亥卯未月甲、申子辰月壬、巳酉丑月庚
  （三合局五行之阳干）。
- **月德合**：月德干之五合 —— 丙辛、甲己、丁壬、乙庚（故丙→辛、甲→己、壬→丁、庚→乙）。
- **天赦**：春（寅卯辰月）戊寅日、夏（巳午未月）甲午日、
  秋（申酉戌月）戊申日、冬（亥子丑月）甲子日。

天德的「卦位」歧义（口径 ``tiande_guaxiang``）
--------------------------------------------
四个卦位对应哪一支，古今两说：

- 《渊海子平》系：坤＝申、乾＝亥、艮＝寅、巽＝巳；
- 《考原》系：坤＝未、乾＝戌、艮＝丑、巽＝辰。

两说在**卦宫**层面其实一致（未申同居坤宫、戌亥同居乾宫、丑寅同居艮宫、
辰巳同居巽宫），分歧只发生在「按单支取还是按整宫取」。故本模块默认口径
``gong_union``（整宫取两支并集，最贴近「坤宫」字面），另两说保留为命名口径，
报告强制回显本次取值与替代口径。

不职责
------
本层不判断「天德能否解三煞」「月德是否百事大吉」——那属规则层且各派强度不一。
"""

from __future__ import annotations

from typing import Any

from .ganzhi import GAN, ZHI

__all__ = [
    "TIAN_DE_TABLE",
    "GUA_ZHI",
    "TIAN_DE_GUA_CALIBERS",
    "YUE_DE_BY_JU",
    "YUE_DE_HE",
    "TIAN_SHE_BY_SEASON",
    "tiande_of_month",
    "yuande_of_month",
    "yuande_he_of_month",
    "tianshe_of_month",
    "derive_jishen_facts",
]

#: 天德：月建（子=0 … 亥=11）→ (类型, 值)。类型 ``gan`` 取日干，``gong`` 取卦宫。
TIAN_DE_TABLE: dict[str, tuple[str, str]] = {
    "寅": ("gan", "丁"),
    "卯": ("gong", "坤"),
    "辰": ("gan", "壬"),
    "巳": ("gan", "辛"),
    "午": ("gong", "乾"),
    "未": ("gan", "甲"),
    "申": ("gan", "癸"),
    "酉": ("gong", "艮"),
    "戌": ("gan", "丙"),
    "亥": ("gan", "乙"),
    "子": ("gong", "巽"),
    "丑": ("gan", "庚"),
}

#: 四维卦 → 所辖两支（后天八卦四隅宫）
GUA_ZHI: dict[str, tuple[str, ...]] = {
    "乾": ("戌", "亥"),
    "坤": ("未", "申"),
    "艮": ("丑", "寅"),
    "巽": ("辰", "巳"),
}

#: 天德卦位取支的三套口径：名称 → 卦对应的单一地支（整宫口径见 ``gong_union``）
TIAN_DE_GUA_CALIBERS: dict[str, dict[str, str]] = {
    "shen_hai_yin_si": {"坤": "申", "乾": "亥", "艮": "寅", "巽": "巳"},
    "wei_xu_chou_chen": {"坤": "未", "乾": "戌", "艮": "丑", "巽": "辰"},
}

#: 月德：月支三合局 → 阳干
YUE_DE_BY_JU: dict[str, str] = {
    "寅": "丙", "午": "丙", "戌": "丙",
    "亥": "甲", "卯": "甲", "未": "甲",
    "申": "壬", "子": "壬", "辰": "壬",
    "巳": "庚", "酉": "庚", "丑": "庚",
}

#: 月德合：月德干之五合（丙辛、甲己、丁壬、乙庚）
YUE_DE_HE: dict[str, str] = {"丙": "辛", "甲": "己", "壬": "丁", "庚": "乙"}

#: 天赦：季（按节气月支）→ 日干支
TIAN_SHE_BY_SEASON: dict[str, tuple[str, ...]] = {
    "春": ("寅", "卯", "辰"),
    "夏": ("巳", "午", "未"),
    "秋": ("申", "酉", "戌"),
    "冬": ("亥", "子", "丑"),
}
TIAN_SHE_DAY: dict[str, str] = {"春": "戊寅", "夏": "甲午", "秋": "戊申", "冬": "甲子"}


def tiande_of_month(month_zhi: str) -> tuple[str, str]:
    """月建 → (``gan``|``gong``, 干或卦名)。"""
    if month_zhi not in TIAN_DE_TABLE:
        raise ValueError(f"非法月支: {month_zhi}")
    return TIAN_DE_TABLE[month_zhi]


def yuande_of_month(month_zhi: str) -> str:
    """月建 → 月德之干。"""
    if month_zhi not in YUE_DE_BY_JU:
        raise ValueError(f"非法月支: {month_zhi}")
    return YUE_DE_BY_JU[month_zhi]


def yuande_he_of_month(month_zhi: str) -> str:
    """月建 → 月德合之干。"""
    return YUE_DE_HE[yuande_of_month(month_zhi)]


def tianshe_of_month(month_zhi: str) -> tuple[str, str]:
    """月建 → (季, 天赦日干支)。"""
    for season, zhis in TIAN_SHE_BY_SEASON.items():
        if month_zhi in zhis:
            return season, TIAN_SHE_DAY[season]
    raise ValueError(f"非法月支: {month_zhi}")


def _tiande_zhi_set(gong: str, caliber: str) -> tuple[str, ...]:
    """卦位 → 该口径下命中的日支集合。"""
    if caliber == "gong_union":
        return GUA_ZHI[gong]
    mapping = TIAN_DE_GUA_CALIBERS.get(caliber)
    if mapping is None:
        raise ValueError(f"未知天德卦位口径: {caliber}")
    return (mapping[gong],)


def derive_jishen_facts(
    *,
    month_zhi: str,
    day_ganzhi: str,
    tiande_caliber: str = "gong_union",
) -> dict[str, Any]:
    """展开 ``facts.jishen``。

    返回的每个 ``hit`` 都是**结构事实**（今日是否恰值该德），不含吉凶。
    ``caliber``/``alternatives`` 用于报告回显：换口径可能改变 ``hit``。
    """
    if len(day_ganzhi) != 2 or day_ganzhi[0] not in GAN or day_ganzhi[1] not in ZHI:
        raise ValueError(f"非法日干支: {day_ganzhi}")
    day_gan, day_zhi = day_ganzhi[0], day_ganzhi[1]

    # ---- 天德 ----
    kind, target = tiande_of_month(month_zhi)
    if kind == "gan":
        tian_de = {
            "kind": "gan",
            "target": target,
            "gong": None,
            "zhi_set": [],
            "hit": day_gan == target,
        }
    else:
        zhi_set = _tiande_zhi_set(target, tiande_caliber)
        tian_de = {
            "kind": "gong",
            "target": target,
            "gong": target,
            "zhi_set": list(zhi_set),
            "hit": day_zhi in zhi_set,
        }
    tian_de["caliber"] = tiande_caliber
    # 只有落在四维卦的月份才有取支歧义；天德为干的月份，口径不影响结论，
    # 因此 alternatives 留空（不是漏填——空表示「本月无歧义」）。
    tian_de["alternatives"] = (
        [
            {"caliber": name, "zhi": list(_tiande_zhi_set(target, name))}
            for name in ("gong_union", *TIAN_DE_GUA_CALIBERS)
        ]
        if kind == "gong"
        else []
    )

    # ---- 月德 / 月德合 ----
    de_gan = yuande_of_month(month_zhi)
    he_gan = YUE_DE_HE[de_gan]
    yue_de = {
        "gan": de_gan,
        "hit": day_gan == de_gan,
        "he_gan": he_gan,
        "he_hit": day_gan == he_gan,
    }

    # ---- 天赦 ----
    season, she_day = tianshe_of_month(month_zhi)
    tian_she = {
        "season": season,
        "day_ganzhi": she_day,
        "hit": day_ganzhi == she_day,
    }

    return {
        "tian_de": tian_de,
        "yue_de": yue_de,
        "tian_she": tian_she,
        "status": "待考证",
        "note": "天德/月德/天赦按月建（节气月）取；值德之吉凶强度属断言级，见 PUB-TIANDE-001 等。",
    }
