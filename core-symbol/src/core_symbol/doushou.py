"""斗首五行 facts（Phase 9）。

斗首以「山家斗首五行」为**我**，以日课四柱天干**化气五行**为**他**，按生克定五星：

================  ========  ==========================================
关系              星        别称（吉凶）
================  ========  ==========================================
同我              元辰      元辰（吉）
生我              贪狼      贪官（次吉／平，流派不一）
我生              廉贞      廉子（凶）
我克              武曲      武财（吉）
克我              破军      破鬼（大凶）
================  ========  ==========================================

**斗首五行 ≠ 正五行**——这是新手最易错处。甲山正五行属木，斗首五行属**水**；
甲干正五行属木，化气属**土**。两张表必须分开建模（本模块只做斗首一张，
正五行在 ``registry.py`` 的调候/通关 facts 里另算）。

口径与不确定性（全部显式，不静默）
----------------------------------
1. **斗首五行表**：口诀「壬子巽巳辛戌土，艮寅丁未木，癸丑丙午乾亥火，坤申甲卯水，
   乙庚辰酉金」。该表为通行本，但「壬子同属土」「甲卯同属水」等与传统五行冲突处
   正是斗首特色，非笔误。
2. **化气**：五运「甲己化土、乙庚化金、丙辛化水、丁壬化木、戊癸化火」，无争议。
3. **得位**：化气五行于月令逢长生／冠带／临官／帝旺。五行寄生十二宫中
   **土的长生位有「申」（土寄坤）与「寅」（土寄艮）两说**，故做成口径
   ``doushou_tu_changsheng``，默认 ``shen``，另一说在 ``alternatives`` 里回显。
4. **番化**：元辰→元辰、武财→贪官、贪官→破鬼、破鬼→廉子、廉子→武财。
   番化的**用法**（是否以番化后之星再论吉凶、番化链长度取几重）流派差异大，
   本模块只输出番化链**供参考**，不让它进入任何 severity 判定。
5. **吉凶强度**：元辰／武财为吉、破军为凶是通说；**贪狼（贪官）与廉贞（廉子）
   的吉凶各本不一**（有以贪狼为次吉、有以为凶），故本模块只给星名与关系，
   吉凶由规则层以 ``待考证`` 承载，不由 facts 断言。

因此本模块的 ``status`` 恒为 ``待考证``，且 ``needs_human_review`` 列出待裁定项。
"""

from __future__ import annotations

from typing import Any

from .ganzhi import GAN, ZHI

__all__ = [
    "DOUSHOU_ELEMENT",
    "HUAQI_ELEMENT",
    "FANHUA",
    "STAR_ALIAS",
    "derive_doushou_facts",
]

#: 二十四山斗首五行（口诀：壬子巽巳辛戌土／艮寅丁未木／癸丑丙午乾亥火／
#: 坤申甲卯水／乙庚辰酉金）。与正五行不同，**不得**用 mountain_element 代替。
DOUSHOU_ELEMENT: dict[str, str] = {
    "壬": "土", "子": "土", "巽": "土", "巳": "土", "辛": "土", "戌": "土",
    "艮": "木", "寅": "木", "丁": "木", "未": "木",
    "癸": "火", "丑": "火", "丙": "火", "午": "火", "乾": "火", "亥": "火",
    "坤": "水", "申": "水", "甲": "水", "卯": "水",
    "乙": "金", "庚": "金", "辰": "金", "酉": "金",
}

#: 十干化气（五运）：甲己化土、乙庚化金、丙辛化水、丁壬化木、戊癸化火。
HUAQI_ELEMENT: dict[str, str] = {
    "甲": "土", "己": "土",
    "乙": "金", "庚": "金",
    "丙": "水", "辛": "水",
    "丁": "木", "壬": "木",
    "戊": "火", "癸": "火",
}

#: 星名 → 别称（贪狼/贪官、廉贞/廉子、武曲/武财、破军/破鬼 同星异名）
STAR_ALIAS: dict[str, str] = {
    "元辰": "元辰",
    "贪狼": "贪官",
    "廉贞": "廉子",
    "武曲": "武财",
    "破军": "破鬼",
}

#: 番化诀：元辰化元辰、武财化贪官、贪官化破鬼、破鬼化廉子、廉子化武财。
#: 键为别称（与口诀用词一致），值亦为别称。
FANHUA: dict[str, str] = {
    "元辰": "元辰",
    "武财": "贪官",
    "贪官": "破鬼",
    "破鬼": "廉子",
    "廉子": "武财",
}

_SHENG: dict[str, str] = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
_KE: dict[str, str] = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

#: 五行寄生十二宫的长生支。土取「申」（土寄坤）为默认口径，另一说见 _TU_YIN。
_CHANGSHENG: dict[str, str] = {"木": "亥", "火": "寅", "金": "巳", "水": "申", "土": "申"}
_TU_YIN: dict[str, str] = {"土": "寅"}

_STAGES: tuple[str, ...] = (
    "长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养",
)
#: 得位：长生／冠带／临官／帝旺 四位为旺相
_DEWEI_STAGES: frozenset[str] = frozenset({"长生", "冠带", "临官", "帝旺"})


def _relation(wo: str, ta: str) -> tuple[str, str]:
    """返回 ``(关系, 星名)``。``wo``=山家斗首五行，``ta``=天干化气五行。"""
    if ta == wo:
        return "同我", "元辰"
    if _SHENG.get(ta) == wo:
        return "生我", "贪狼"
    if _SHENG.get(wo) == ta:
        return "我生", "廉贞"
    if _KE.get(wo) == ta:
        return "我克", "武曲"
    return "克我", "破军"


def _stage_of(element: str, month_zhi: str, tu_changsheng: str) -> tuple[str | None, int | None]:
    """五行在某月支的十二宫位次。返回 ``(宫位名, 位次)``；未知返回 ``(None, None)``。"""
    if element == "土" and tu_changsheng == "yin":
        start = _TU_YIN["土"]
    else:
        start = _CHANGSHENG.get(element)
    if start is None or month_zhi not in ZHI:
        return None, None
    pos = (ZHI.index(month_zhi) - ZHI.index(start)) % 12
    return _STAGES[pos], pos


def derive_doushou_facts(
    *,
    mountain_name: str,
    gans: list[str],
    month_zhi: str,
    tu_changsheng: str = "shen",
) -> dict[str, Any]:
    """展开 ``facts.doushou``。

    ``gans`` 为四柱天干（年、月、日、时）。斗首以**四柱天干**论，不取地支。

    返回结构（全部 JSON 可序列化，可写入报告 params_snapshot）::

        shan.element / shan.changsheng / shan.stage / shan.dewei
        stems[i] = {position, gan, huaqi, relation, star, alias, fanhua,
                    stage, dewei}
        counts = {元辰: n, 贪狼: n, 廉贞: n, 武曲: n, 破军: n}
        sanyuan (三重元辰) / sanwu (三重武财)
        caliber = {tu_changsheng: shen|yin}
        status = 待考证
    """
    if tu_changsheng not in ("shen", "yin"):
        raise ValueError(f"未知土长生口径: {tu_changsheng}")

    shan_el = DOUSHOU_ELEMENT.get(mountain_name)
    shan_stage, shan_pos = (
        _stage_of(shan_el, month_zhi, tu_changsheng) if shan_el else (None, None)
    )

    positions = ("年", "月", "日", "时")
    stems: list[dict[str, Any]] = []
    counts: dict[str, int] = {"元辰": 0, "贪狼": 0, "廉贞": 0, "武曲": 0, "破军": 0}

    for idx, gan in enumerate(gans):
        huaqi = HUAQI_ELEMENT.get(gan)
        if shan_el is None or huaqi is None:
            stems.append(
                {
                    "position": positions[idx] if idx < len(positions) else f"#{idx}",
                    "gan": gan,
                    "huaqi": huaqi,
                    "relation": None,
                    "star": None,
                    "alias": None,
                    "fanhua": None,
                    "stage": None,
                    "dewei": None,
                }
            )
            continue
        relation, star = _relation(shan_el, huaqi)
        alias = STAR_ALIAS[star]
        stage, _pos = _stage_of(huaqi, month_zhi, tu_changsheng)
        counts[star] += 1
        stems.append(
            {
                "position": positions[idx] if idx < len(positions) else f"#{idx}",
                "gan": gan,
                "huaqi": huaqi,
                "relation": relation,
                "star": star,
                "alias": alias,
                "fanhua": FANHUA[alias],
                "stage": stage,
                "dewei": (stage in _DEWEI_STAGES) if stage else None,
            }
        )

    sanyuan = counts["元辰"] >= 3
    sanwu = counts["武曲"] >= 3

    needs_human_review: list[str] = []
    if shan_el is None:
        needs_human_review.append(f"山名 {mountain_name} 不在二十四山斗首五行表内")
    if tu_changsheng == "shen":
        needs_human_review.append(
            "土的长生位取「申」（土寄坤）；另有「寅」（土寄艮）一说，见 caliber.alternatives"
        )
    needs_human_review.append("贪狼（贪官）与廉贞（廉子）的吉凶各本不一，facts 不断言吉凶")
    needs_human_review.append("番化链仅作参考，不参与 severity 判定")

    return {
        "shan": {
            "element": shan_el,
            "changsheng": (_TU_YIN["土"] if (shan_el == "土" and tu_changsheng == "yin")
                           else _CHANGSHENG.get(shan_el) if shan_el else None),
            "stage": shan_stage,
            "position": shan_pos,
            "dewei": (shan_stage in _DEWEI_STAGES) if shan_stage else None,
        },
        "stems": stems,
        "counts": counts,
        "sanyuan": sanyuan,
        "sanwu": sanwu,
        "caliber": {
            "tu_changsheng": tu_changsheng,
            "alternatives": [
                {"tu_changsheng": "yin", "note": "土寄艮，土长生在寅"}
            ] if tu_changsheng == "shen" else [
                {"tu_changsheng": "shen", "note": "土寄坤，土长生在申"}
            ],
        },
        "status": "待考证",
        "needs_human_review": needs_human_review,
    }


def _validate_tables() -> None:
    """表完整性硬校验（导入即执行）：二十四山全覆盖、十天干全覆盖、五关系闭合。

    用显式 raise 而非 assert——``python -O`` 会移除 assert，表残缺将静默变成
    "该山无斗首五行"的 unknown，正是本项目禁止的静默降级。
    """
    missing = set(DOUSHOU_ELEMENT) ^ {
        "子", "癸", "丑", "艮", "寅", "甲", "卯", "乙", "辰", "巽", "巳", "丙",
        "午", "丁", "未", "坤", "申", "庚", "酉", "辛", "戌", "乾", "亥", "壬",
    }
    if missing:
        raise RuntimeError(f"斗首五行表未覆盖二十四山（差异：{sorted(missing)}）")
    if set(HUAQI_ELEMENT) != set(GAN):
        raise RuntimeError("化气表必须覆盖十天干")
    if set(STAR_ALIAS) != {"元辰", "贪狼", "廉贞", "武曲", "破军"}:
        raise RuntimeError("五星别名表不完整")
    if set(FANHUA) != set(STAR_ALIAS.values()):
        raise RuntimeError("番化表必须覆盖五星全部别称")


_validate_tables()
