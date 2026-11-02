"""十二黄黑道（青龙十二神）—— 纯查表 + 位移，事实层不含吉凶。

本模块补的是原先的**单星缺口**：本系统此前只认「勾陈」一颗黑道星
（``donggong_gouchen_heidao.json``，按月建查日支），既无法回答「今天是青龙还是白虎」，
也无法回答「这个时辰是不是黄道时」。十二神本身是固定起例，属最容易做对的一层。

起例
----
先定**青龙所临之支**，再顺行十二辰：

=================  =======================
月建（节气月）      青龙所临支
=================  =======================
子 / 午            申
丑 / 未            戌
寅 / 申            子
卯 / 酉            寅
辰 / 戌            辰
巳 / 亥            午
=================  =======================

口诀形：「子午临申地，丑未戌上行，寅申须加子，卯酉却居寅，辰戌龙位上，巳亥午中寻」。

青龙起后顺行十二神：

    青龙、明堂、天刑、朱雀、金匮、天德、白虎、玉堂、天牢、玄武、司命、勾陈

位次公式：``index = (目标支序 − 青龙起支序) mod 12``。

交叉校验（非自证）
------------------
既有 ``donggong_gouchen_heidao.json`` 逐月给出「勾陈日」的日支。用本模块的起例
（青龙起支顺行 11 位 = 勾陈）应当**逐月吻合**；12 个月全中才允许声明这条起例可信。
该断言写在 ``tests/unit/test_paijian_fixed.py::test_gouchen_cross_validation``。

**命名撞车警告**：黄道十二神里的「天德」又名「宝光」，与吉神表 ``jishen.tian_de``
（天德贵人，按月建取干或卦）**不是同一件事**，两者不可互相代入。

为什么不输出「黄道/黑道」标签
--------------------------
「黄道六神为吉、黑道六神为凶」是**断言**，不是结构。按 ADR-0009，事实层只回答
「值哪一神、第几位」（定义级），「好不好」由规则层以 ``in`` 算子表达：

    condition: {fact: facts.huangdao.day.star, op: in, value: [青龙, 明堂, 金匮, 天德, 玉堂, 司命]}

故本模块只导出 ``HUANG_DAO_STARS`` / ``HEI_DAO_STARS`` 两张**参考表**供规则作者使用，
不把它们写进 ``facts``。
"""

from __future__ import annotations

from typing import Any

from .ganzhi import ZHI

__all__ = [
    "HUANGDAO_STARS",
    "HUANG_DAO_STARS",
    "HEI_DAO_STARS",
    "QINGLONG_START_ZHI",
    "huangdao_index",
    "huangdao_of",
    "derive_huangdao_fact",
]

#: 十二神次序（青龙起，勾陈终）
HUANGDAO_STARS: tuple[str, ...] = (
    "青龙", "明堂", "天刑", "朱雀", "金匮", "天德",
    "白虎", "玉堂", "天牢", "玄武", "司命", "勾陈",
)

#: 月建 → 青龙所临之支
QINGLONG_START_ZHI: dict[str, str] = {
    "子": "申", "午": "申",
    "丑": "戌", "未": "戌",
    "寅": "子", "申": "子",
    "卯": "寅", "酉": "寅",
    "辰": "辰", "戌": "辰",
    "巳": "午", "亥": "午",
}

#: 黄道六神（**断言级参考表**，供规则层使用；事实层不输出该分组）
HUANG_DAO_STARS: frozenset[str] = frozenset({"青龙", "明堂", "金匮", "天德", "玉堂", "司命"})

#: 黑道六神（同上，断言级参考表）
HEI_DAO_STARS: frozenset[str] = frozenset({"天刑", "朱雀", "白虎", "天牢", "玄武", "勾陈"})


def huangdao_index(month_zhi: str, target_zhi: str) -> int:
    """返回十二神位次（0=青龙 … 11=勾陈）。"""
    if month_zhi not in QINGLONG_START_ZHI:
        raise ValueError(f"非法月支: {month_zhi}")
    if target_zhi not in ZHI:
        raise ValueError(f"非法目标支: {target_zhi}")
    start = QINGLONG_START_ZHI[month_zhi]
    return (ZHI.index(target_zhi) - ZHI.index(start)) % 12


def huangdao_of(month_zhi: str, target_zhi: str) -> str:
    """返回十二神名。``target_zhi`` 可为日支（日家）或时支（时家黄道时），同一公式。"""
    return HUANGDAO_STARS[huangdao_index(month_zhi, target_zhi)]


def derive_huangdao_fact(*, month_zhi: str, day_zhi: str) -> dict[str, Any]:
    """展开 ``facts.huangdao`` 的日家部分。

    时家部分（黄道吉时）由 ``overlay_hour_facts`` 用同一函数补 ``hour`` 子项。
    """
    idx = huangdao_index(month_zhi, day_zhi)
    return {
        "day": {
            "star": HUANGDAO_STARS[idx],
            "index": idx,
            "day_zhi": day_zhi,
            "qinglong_start": QINGLONG_START_ZHI[month_zhi],
        },
        "month_zhi": month_zhi,
        "status": "待考证",
        "note": (
            "青龙起例：子午临申、丑未戌上、寅申加子、卯酉居寅、辰戌龙位、巳亥午中，"
            "起后顺行十二神。黄道/黑道分组属断言级（不入事实层），参考表见 "
            "HUANG_DAO_STARS / HEI_DAO_STARS。"
        ),
    }
