"""玄空大卦 facts（评审扩展版 spec §2.4）：先天圆图 384 爻 + 两元八运 + 卦气/抽爻。

所有起例在本模块**真实计算**，不做"每运 20 年"之类的等宽简化。口径逐条显式
声明在返回值 ``caliber`` 字段并在 ``facts._calibers`` 回显；流派分歧处一律挂
``needs_human_review``，不静默取一边。

口径清单
--------
1. **圆图排布**：伏羲先天六十四卦圆图，「乾起于午中、坤尽于子中」——
   乾初爻自正南 180° 起沿东半圆（180°→0°，经卯）依初→上顺布至复上爻；
   姤初爻自正南 180° 起沿西半圆（180°→360°，经酉）依初→上顺布至坤上爻。
   每卦 5.625°、每爻 0.9375°，共 64×6=384 爻。半开区间 [start, end)；
   180° 整点归西半（姤初）。卦界对齐子午线的罗盘亦有"卦心对午"一说 →
   needs_human_review。
2. **卦运**：64 别卦卦运取其内卦（下三爻）经卦运数（张心言《地理辨正疏》
   方图行运之说），数据文件 ``xuankong_64gua.json`` 标注 unverified。
3. **大卦元运**：上元甲子年起一运，按各经卦运年期（阳爻 9 年、阴爻 6 年，
   三爻和）逐年累计，上元 90 年＋下元 90 年＝180 年周期，无五运。
   锚定年（以最近上元甲子为锚）流派有异说 → needs_human_review。
4. **卦气配合**：以坐山卦与向首卦的**卦运数**论合十／合五／合十五／合生成
   （河图数关系，``xuankong_hetu.json``）。日课四柱配卦属流派分歧，
   未实现 → needs_human_review，相关维度输出 None。
5. **抽爻换象**：取坐山山心所临之爻（384 爻精度）抽变（阳变阴／阴变阳）
   得变卦；丁/财以变卦内外卦经卦运数配河图关系判定：生成数 → 丁爻
   （ding_score=1），合十/合五/合十五 → 财爻（cai_score=1）——两格分列，
   不合并（spec §2.4 硬性输出）。丁财定义他派另说 → needs_human_review。

事实中不含吉凶断语，只含结构事实与当旺比对；吉凶由规则层（status=待考证、
confidence=低）表达。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .mountain import MOUNTAINS_24, Mountain

__all__ = [
    "DEG_PER_YAO",
    "current_dayun",
    "yao_at_bearing",
    "shan_center_bearing",
    "guaqi_relation",
    "changed_gua_name",
    "derive_xuankong_facts",
]

#: 每爻角度：360 / 384
DEG_PER_YAO: float = 360.0 / 384  # 0.9375

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "core-rule" / "config" / "data"


# C19-exempt: 单一不可变参数（进程常量数据/日历换算），键由解释器按参数构造，无复合串味面
@lru_cache(maxsize=1)
def _load_64gua() -> dict[str, Any]:
    return json.loads((_DATA_DIR / "xuankong_64gua.json").read_text(encoding="utf-8"))


# C19-exempt: 单一不可变参数（进程常量数据/日历换算），键由解释器按参数构造，无复合串味面
@lru_cache(maxsize=1)
def _load_yunyun() -> dict[str, Any]:
    return json.loads((_DATA_DIR / "xuankong_yunyun.json").read_text(encoding="utf-8"))


# 大卦运顺序（无五运）：上元一二三四 → 下元六七八九
_YUN_ORDER: tuple[str, ...] = ("一运", "二运", "三运", "四运", "六运", "七运", "八运", "九运")


@dataclass(frozen=True)
class YaoCell:
    """圆图上的一爻。``n`` 为东半全局序（0=乾初），``k`` 为西半全局序（0=姤初）。"""

    gua: str
    yao: int  # 1=初 … 6=上
    start_deg: float
    end_deg: float
    half: str  # east | west
    yang: bool


def shan_center_bearing(name: str) -> float:
    """二十四山山心方位角（子=0°，顺时针每山 15°）。"""
    if name not in MOUNTAINS_24:
        raise ValueError(f"非二十四山名: {name}")
    return float(MOUNTAINS_24.index(name) * 15)


def yao_at_bearing(bearing: float) -> YaoCell:
    """方位角所临之爻（384 爻精度）。

    口径：半开区间 [start, end)；东半圆爻 n 的区间为
    ``[180-(n+1)w, 180-nw)``（n=0 为乾初），西半圆爻 k 的区间为
    ``[180+kw, 180+(k+1)w)``（k=0 为姤初）。180° 整点归西半（姤初），
    0°/360° 整点归东半（复上）。
    """
    b = bearing % 360.0
    w = DEG_PER_YAO
    order = _load_64gua()["circle_order"]
    hexagrams = _load_64gua()["hexagrams"]
    if b < 180.0:
        # 东半：乾初(179.0625-180) … 复上(0-0.9375)
        n = min(191, int((180.0 - b) / w))
        gua = order[n // 6]
        start = 180.0 - (n + 1) * w
        return YaoCell(gua=gua, yao=n % 6 + 1, start_deg=start, end_deg=start + w,
                       half="east", yang=hexagrams[gua]["binary"][n % 6] == "1")
    # 西半：姤初(180-180.9375) … 坤上(359.0625-360)
    k = min(191, int((b - 180.0) / w))
    idx = 32 + k // 6
    gua = order[idx]
    start = 180.0 + k * w
    return YaoCell(gua=gua, yao=k % 6 + 1, start_deg=start, end_deg=start + w,
                   half="west", yang=hexagrams[gua]["binary"][k % 6] == "1")


def current_dayun(year: int) -> dict[str, Any]:
    """当前大卦元运（两元八运，阳爻 9 年阴爻 6 年，180 年周期）。

    锚定口径：以 1864 年（上元甲子、180 年大卦运周期首年）为一运首年，
    向后依各经卦运年期累计；2044 年起进入下一周期。流派亦有以三元九运
    对齐锚定者 → ``needs_human_review``。
    """
    yunyun = _load_yunyun()["yuan_yun"]
    # 两元八运的公认年表以 1864 年（甲子）为起点：一运 1864-1881，
    # 九运 2017-2043，2044 年起循环。不能用「任意甲子」取锚——180 年内含
    # 三个甲子，只有 1864/2044/2224… 是周期首年。
    anchor = year - ((year - 1864) % 180)
    offset = year - anchor
    acc = 0
    for yname in _YUN_ORDER:
        spec = yunyun[yname]
        years = int(spec["years"])
        if offset < acc + years:
            return {
                "yun": _yun_number(yname),
                "yun_name": yname,
                "gua": spec["gua"],
                "period": spec["period"],
                "years": years,
                "start_year": anchor + acc,
                "end_year": anchor + acc + years - 1,
                "anchor_year": anchor,
                "offset_in_yun": offset - acc,
            }
        acc += years
    raise AssertionError("unreachable: 180 年周期内必有一运在位")  # pragma: no cover


_CN_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _yun_number(yname: str) -> int:
    return _CN_DIGIT[yname.replace("运", "")]


def guaqi_relation(a: int, b: int) -> str | None:
    """两卦运数的河图关系：合十／合十五／合五／合生成；比和与无关系返回 None。

    比和（同运当旺）归 ``wangqi`` 规则表达，不在此重复计数。
    """
    if a == b:
        return None
    s = a + b
    if s == 10:
        return "合十"
    if s == 15:
        return "合十五"
    if s == 5:
        return "合五"
    if {a, b} in ({1, 6}, {2, 7}, {3, 8}, {4, 9}):
        return "合生成"
    return None


def changed_gua_name(binary: str, yao: int) -> str:
    """抽爻换象：翻转第 ``yao`` 爻（1=初 … 6=上）后所得变卦名。"""
    if not 1 <= yao <= 6:
        raise ValueError(f"爻位越界: {yao}")
    chars = list(binary)
    i = yao - 1
    chars[i] = "0" if chars[i] == "1" else "1"
    flipped = "".join(chars)
    hexagrams = _load_64gua()["hexagrams"]
    for name, g in hexagrams.items():
        if g["binary"] == flipped:
            return name
    raise AssertionError(f"变卦二进制不在 64 卦表内: {flipped}")  # pragma: no cover


def _ding_cai_scores(changed_gua: dict[str, Any]) -> tuple[int, int]:
    """变卦的丁爻/财爻计分（spec §2.4：丁/财分列，不合并）。

    以变卦**内卦与外卦的经卦运数**配河图关系：
    - 配生成数（1-6/2-7/3-8/4-9）→ 丁爻（旺丁），ding_score=1
    - 合十（和 10）/合五（和 5）/合十五（和 15）→ 财爻（旺财），cai_score=1
    两格互斥（生成对与合十对不相交）；纯卦（内外同卦）两格皆 0。
    """
    inner = _load_64gua()["hexagrams"][changed_gua["lower"]]["guayun"]
    outer = _load_64gua()["hexagrams"][changed_gua["upper"]]["guayun"]
    ding = 1 if {inner, outer} in ({1, 6}, {2, 7}, {3, 8}, {4, 9}) else 0
    cai = 1 if inner != outer and inner + outer in (5, 10, 15) else 0
    return ding, cai


def derive_xuankong_facts(
    *,
    mountain: Mountain,
    facing: Mountain | None,
    local_date: Any | None,
) -> dict[str, Any]:
    """展开 ``facts.xuankong.*``（结构事实 + 当旺比对，无吉凶断语）。"""
    hexagrams = _load_64gua()["hexagrams"]

    dayun = current_dayun(local_date.year) if local_date is not None else None

    sit_bearing = shan_center_bearing(mountain.name)
    sit_cell = yao_at_bearing(sit_bearing)
    sit = hexagrams[sit_cell.gua]

    face_cell: YaoCell | None = None
    face: dict[str, Any] | None = None
    if facing is not None:
        face_bearing = shan_center_bearing(facing.name)
        face_cell = yao_at_bearing(face_bearing)
        face = hexagrams[face_cell.gua]

    cur_yun = dayun["yun"] if dayun else None

    # ---- 卦运当旺：坐山卦运 == 当前大卦运 ----
    guayun_current: dict[str, Any] | None = None
    if dayun is not None:
        guayun_current = {
            "current_yun": cur_yun,
            "current_yun_name": dayun["yun_name"],
            "current_gua": dayun["gua"],
            "current_period": dayun["period"],
            "dayun_start_year": dayun["start_year"],
            "dayun_end_year": dayun["end_year"],
            "sitting_gua": sit_cell.gua,
            "sitting_guayun": sit["guayun"],
            "sitting_yao": sit_cell.yao,
            "matched": sit["guayun"] == cur_yun,
        }

    # ---- 旺气到山到向 ----
    daoxiang: bool | None = None
    if face is not None and cur_yun is not None:
        daoxiang = face["guayun"] == cur_yun
    wangqi: dict[str, Any] | None = None
    if cur_yun is not None:
        wangqi = {
            "current_yun": cur_yun,
            "daoshan": sit["guayun"] == cur_yun,
            "daoxiang": daoxiang,
            "facing_gua": face_cell.gua if face_cell else None,
        }

    # ---- 卦气配合：坐/向两卦卦运的河图关系 ----
    guaqi: dict[str, Any] | None = None
    if cur_yun is not None:
        guaqi = {
            "sitting_guayun": sit["guayun"],
            "facing_guayun": face["guayun"] if face else None,
            "relation": guaqi_relation(sit["guayun"], face["guayun"]) if face else None,
            "course_gua_relation": None,  # 日课配卦流派分歧，未实现
        }

    # ---- 抽爻换象：坐山山心所临之爻抽变（丁爻/财爻分列，spec §2.4 硬性输出）----
    #   丁爻：变卦内卦与外卦配**生成数**（1-6/2-7/3-8/4-9）→ 旺丁
    #   财爻：变卦内卦与外卦**合十/合五/合十五** → 旺财
    #   两格分别计分输出，不得合并为单一吉凶（spec §2.4）。
    chouyao: dict[str, Any] | None = None
    if cur_yun is not None:
        changed = changed_gua_name(sit["binary"], sit_cell.yao)
        changed_g = hexagrams[changed]
        ding, cai = _ding_cai_scores(changed_g)
        chouyao = {
            "sitting_gua": sit_cell.gua,
            "yao_pos": sit_cell.yao,
            "yao_yang": sit_cell.yang,
            "changed_gua": changed,
            "changed_guayun": changed_g["guayun"],
            "matched_dayun": changed_g["guayun"] == cur_yun,
            "ding_score": ding,
            "cai_score": cai,
        }

    return {
        "guayun_current": guayun_current,
        "wangqi": wangqi,
        "guaqi": guaqi,
        "chouyao": chouyao,
        "caliber": {
            "circle": "先天圆图：乾起于午中沿东半至复，姤起于午中沿西半至坤；384 爻每爻 0.9375°，半开区间，180° 归姤初",
            "guayun": "别卦卦运取内卦经卦运数（张心言方图行运）",
            "dayun": "上元甲子起一运，阳爻9年阴爻6年累计，180 年周期，无五运",
            "guaqi": "以坐/向两卦卦运论河图关系（合十/合五/合十五/合生成）",
            "chouyao": "山心之爻抽变得变卦；丁=内外卦配生成数，财=合十/五/十五（张心言系河图口径）",
        },
        "needs_human_review": [
            "圆图卦界对齐方式（乾起午中 vs 卦心对午）两说",
            "大卦元运锚定年（上元甲子 vs 与三元九运对齐）两说",
            "日课四柱配卦流派分歧——卦气/抽爻的课卦维度未实现",
            "卦运数据源 verification_status=unverified",
        ],
        "status": "待考证",
    }
