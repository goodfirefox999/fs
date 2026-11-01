"""纳音五行与旬空（符号层，纯函数）。

纳音表为公版传统表（六十甲子纳音），本模块只做查表，不判断吉凶。
"""

from __future__ import annotations

from dataclasses import dataclass

from .ganzhi import GAN, GANZHI60, ZHI, Element

__all__ = ["NAYIN_TABLE", "nayin_of", "nayin_element_of", "XUNKONG_TABLE", "xunkong_of", "xun_head_of", "XunKong"]

#: 六十甲子纳音（每两个干支共用一个纳音，共 30 项）
_NAYIN_PAIRS: tuple[tuple[str, Element], ...] = (
    ("海中金", "金"),
    ("炉中火", "火"),
    ("大林木", "木"),
    ("路旁土", "土"),
    ("剑锋金", "金"),
    ("山头火", "火"),
    ("涧下水", "水"),
    ("城头土", "土"),
    ("白蜡金", "金"),
    ("杨柳木", "木"),
    ("泉中水", "水"),
    ("屋上土", "土"),
    ("霹雳火", "火"),
    ("松柏木", "木"),
    ("长流水", "水"),
    ("沙中金", "金"),
    ("山下火", "火"),
    ("平地木", "木"),
    ("壁上土", "土"),
    ("金箔金", "金"),
    ("覆灯火", "火"),
    ("天河水", "水"),
    ("大驿土", "土"),
    ("钗钏金", "金"),
    ("桑柘木", "木"),
    ("大溪水", "水"),
    ("沙中土", "土"),
    ("天上火", "火"),
    ("石榴木", "木"),
    ("大海水", "水"),
)

#: 干支 → (纳音名, 纳音五行)
NAYIN_TABLE: dict[str, tuple[str, Element]] = {
    GANZHI60[i]: _NAYIN_PAIRS[i // 2] for i in range(60)
}


def nayin_of(ganzhi: str) -> str:
    """返回纳音名，如 ``甲子`` → ``海中金``。"""
    if len(ganzhi) != 2 or ganzhi not in NAYIN_TABLE:
        raise ValueError(f"非法干支: {ganzhi}")
    return NAYIN_TABLE[ganzhi][0]


def nayin_element_of(ganzhi: str) -> Element:
    """返回纳音五行。"""
    if len(ganzhi) != 2 or ganzhi not in NAYIN_TABLE:
        raise ValueError(f"非法干支: {ganzhi}")
    return NAYIN_TABLE[ganzhi][1]


@dataclass(frozen=True)
class XunKong:
    """一旬及其空亡二支。"""

    head: str  # 旬首，如 甲子
    index: int  # 旬首六十甲子序号
    empty: tuple[str, str]  # 空亡二支


#: 六旬空亡表
XUNKONG_TABLE: dict[str, XunKong] = {
    "甲子": XunKong("甲子", 0, ("戌", "亥")),
    "甲戌": XunKong("甲戌", 10, ("申", "酉")),
    "甲申": XunKong("甲申", 20, ("午", "未")),
    "甲午": XunKong("甲午", 30, ("辰", "巳")),
    "甲辰": XunKong("甲辰", 40, ("寅", "卯")),
    "甲寅": XunKong("甲寅", 50, ("子", "丑")),
}


def xun_head_of(ganzhi: str) -> str:
    """返回所在旬的旬首。"""
    idx = GANZHI60.index(ganzhi)
    return GANZHI60[(idx // 10) * 10]


def xunkong_of(ganzhi: str) -> XunKong:
    """返回所在旬的空亡信息。"""
    return XUNKONG_TABLE[xun_head_of(ganzhi)]


def xunkong_hit(ganzhi: str, zhi: str) -> bool:
    """``zhi`` 是否为 ``ganzhi`` 所在旬的空亡支。"""
    return zhi in xunkong_of(ganzhi).empty


_ = (GAN, ZHI)  # 保留引用
