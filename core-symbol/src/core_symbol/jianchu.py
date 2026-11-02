"""建除十二神（十二建星）——纯算术，不含吉凶。

为什么这一支能做成「确定」
------------------------
建除是**纯位移**：以月建（节气月之支）为「建」，日支（或时支）与之相差几位就顺数几位——

    建、除、满、平、定、执、破、危、成、收、开、闭

位次公式：``index = (目标支序 − 月建支序) mod 12``。没有查表、没有口径分歧，
换任何一个实现都得到同一结果。这也是它常被写成「今天破日」这类通书行的原因。

两条可机器自校验的恒等式（见 ``tests/unit/test_paijian_fixed.py``）
--------------------------------------------------------------
1. **建日即月建日**：日支 == 月支 ⟺ index == 0（建）。
2. **破日即月破日**：index == 6 ⟺ 日支冲月支（六冲）。
   第二条尤其有用——它把建除与「月破」这条独立起例的神煞锁在一起，两者错位即暴露。

口径（口径分歧只有一处）
------------------------
月建的取法：本系统用**节气月**（立春起寅，与年柱/月柱同界），与通书建星一致。
另有按农历月（正月初一换月）的旧法，闰月归属亦有别说；本模块不选，由调用方传入
``month_zhi``，口径在调用点（``core-time`` 的月柱）已经确定并回显。

不职责
------
不判断「建日宜出行、破日忌动土」——那是断言级（``DG-JIANCHU-001`` 等），须原文与签名。
本模块只回答「今日值哪一建」。
"""

from __future__ import annotations

from typing import Any

from .ganzhi import ZHI

__all__ = [
    "JIANCHU_STARS",
    "JIANCHU_PO_INDEX",
    "jianchu_index",
    "jianchu_of",
    "derive_jianchu_fact",
]

#: 十二建星次序（建起，闭终）。次序本身是定义，不含吉凶。
JIANCHU_STARS: tuple[str, ...] = (
    "建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭",
)

#: 「破」在建除序列中的位次 7（0-based 6）——等于六冲的半周，故破日恒为月破日。
JIANCHU_PO_INDEX: int = JIANCHU_STARS.index("破")


def jianchu_index(month_zhi: str, target_zhi: str) -> int:
    """返回建除位次（0=建 … 11=闭）。"""
    if month_zhi not in ZHI:
        raise ValueError(f"非法月支: {month_zhi}")
    if target_zhi not in ZHI:
        raise ValueError(f"非法目标支: {target_zhi}")
    return (ZHI.index(target_zhi) - ZHI.index(month_zhi)) % 12


def jianchu_of(month_zhi: str, target_zhi: str) -> str:
    """返回建除星名。``target_zhi`` 可为日支（日家）或时支（时家），同一公式。"""
    return JIANCHU_STARS[jianchu_index(month_zhi, target_zhi)]


def derive_jianchu_fact(*, month_zhi: str, day_zhi: str) -> dict[str, Any]:
    """展开 ``facts.jianchu``（日家建除）。

    时家建除由 ``overlay_hour_facts`` 以同一函数补 ``hour`` 子项，不另写一套。
    """
    idx = jianchu_index(month_zhi, day_zhi)
    return {
        "star": JIANCHU_STARS[idx],
        "index": idx,
        "month_zhi": month_zhi,
        "day_zhi": day_zhi,
        "is_jian": idx == 0,
        "is_po": idx == JIANCHU_PO_INDEX,
        "status": "待考证",
        "note": (
            "月建起建、日支顺数（位次 = 日支序 − 月建支序 mod 12）；月建取节气月。"
            "建星吉凶属断言级（DG-JIANCHU-001），不在事实层判定。"
        ),
    }
