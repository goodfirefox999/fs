"""二十四山、坐向与分金（符号层，纯函数）。

角度约定
--------
方位角 ``azimuth`` 为罗盘读数，正北 0°，顺时针增大，取值 [0, 360)。
二十四山每山 15°，**山中心**依次为 0°(子)、15°(癸)、30°(丑) … 345°(壬)。

分金
----
一百二十分金为每山 5 分、每分 3°。本模块只做**机械角度映射**，不判定分金干支名称与吉凶；
分金取用体系（三合/玄空/正针）属争议项，见附录 B，必须配置化。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .ganzhi import ZHI

__all__ = [
    "MOUNTAINS_24",
    "ZHI_MOUNTAIN_INDEX",
    "Mountain",
    "normalize_azimuth",
    "mountain_of_azimuth",
    "mountain_by_name",
    "facing_of",
    "FenJin",
    "fenjin_of_azimuth",
    "jian_xiang",
    "angular_distance",
]

#: 二十四山，自子起顺时针
MOUNTAINS_24: tuple[str, ...] = (
    "子", "癸", "丑", "艮", "寅", "甲", "卯", "乙", "辰", "巽", "巳", "丙",
    "午", "丁", "未", "坤", "申", "庚", "酉", "辛", "戌", "乾", "亥", "壬",
)

#: 十二地支在二十四山中的位置（用于"坐山是否属某支"的判定）
ZHI_MOUNTAIN_INDEX: dict[str, int] = {z: MOUNTAINS_24.index(z) for z in ZHI}


def normalize_azimuth(az: float) -> float:
    """把任意角度归一到 [0, 360)。

    注意：浮点取模对极小负数可能返回 360.0，故显式钳到 0.0。
    """
    if not math.isfinite(az):
        raise ValueError("方位角必须是有限数值")
    value = az % 360.0
    return 0.0 if value >= 360.0 else value


def angular_distance(a: float, b: float) -> float:
    """两方位角的最小夹角（0-180）。"""
    d = abs(normalize_azimuth(a) - normalize_azimuth(b)) % 360.0
    return min(d, 360.0 - d)


@dataclass(frozen=True)
class Mountain:
    """坐山。``index`` 为二十四山序号（子=0）。"""

    index: int
    name: str
    center_deg: float
    azimuth: float

    @property
    def offset_deg(self) -> float:
        """实测方位角相对山中心的偏移（-7.5 ~ +7.5）。"""
        d = (self.azimuth - self.center_deg + 180.0) % 360.0 - 180.0
        return d

    def to_dict(self) -> dict[str, float | str | int]:
        return {
            "name": self.name,
            "index": self.index,
            "center_deg": self.center_deg,
            "azimuth": self.azimuth,
            "offset_deg": round(self.offset_deg, 4),
        }


def mountain_of_azimuth(az: float) -> Mountain:
    """方位角 → 坐山（四舍五入到最近山中心）。"""
    az_n = normalize_azimuth(az)
    index = int(round(az_n / 15.0)) % 24
    return Mountain(index=index, name=MOUNTAINS_24[index], center_deg=index * 15.0, azimuth=az_n)


def mountain_by_name(name: str) -> Mountain:
    if name not in MOUNTAINS_24:
        raise ValueError(f"非法山名: {name}")
    index = MOUNTAINS_24.index(name)
    return Mountain(index=index, name=name, center_deg=index * 15.0, azimuth=index * 15.0)


def facing_of(mountain: Mountain) -> Mountain:
    """坐山的对宫（向首）。"""
    index = (mountain.index + 12) % 24
    return Mountain(
        index=index,
        name=MOUNTAINS_24[index],
        center_deg=index * 15.0,
        azimuth=(mountain.azimuth + 180.0) % 360.0,
    )


@dataclass(frozen=True)
class FenJin:
    """分金槽位。``slot`` 取 0-4，对应山内自左（小角度）至右第几分。"""

    mountain: Mountain
    slot: int
    center_deg: float
    span_deg: float = 3.0

    def to_dict(self) -> dict[str, object]:
        return {
            "mountain": self.mountain.name,
            "slot": self.slot,
            "center_deg": round(self.center_deg, 4),
            "span_deg": self.span_deg,
        }


def fenjin_of_azimuth(az: float) -> FenJin:
    """方位角 → 分金槽位（每山 5 槽、每槽 3°）。"""
    m = mountain_of_azimuth(az)
    start = m.center_deg - 7.5
    slot = int(math.floor(((m.azimuth - start) % 360.0) / 3.0))
    slot = max(0, min(4, slot))
    return FenJin(mountain=m, slot=slot, center_deg=start + slot * 3.0 + 1.5)


def jian_xiang(mountain: Mountain, threshold_deg: float = 3.0) -> str | None:
    """判断是否"兼"相邻山。

    ``threshold_deg`` 是**正针带的一半宽度**：山心偏移 ``|offset| <= threshold`` 判正针（不兼），
    超出则兼相邻山。故默认 3.0° 对应「正针带 6°（±3°）、两侧各 4.5° 为兼」。

    该阈值属争议项，两说并存：

    - 9°/3°/3° 说（正针带 9°、两侧各 3° 兼、余 3° 落空亡）→ 对应 ``threshold=4.5``；
    - 6°/4.5°/4.5° 说（本条默认）→ ``threshold=3.0``。

    两说在 ``|offset|`` 落在 3°–4.5° 时会给出不同结论（默认判「兼」，另一说判「正针」），
    而兼向会改变山家地支、进而影响三合扶山等判定。**未裁定前不得改默认值**；
    调用方（``schemas.build_context``）应按需显式传入，并使报告回显取值。
    """
    off = mountain.offset_deg
    if abs(off) <= threshold_deg:
        return None
    neighbor = (mountain.index + (1 if off > 0 else -1)) % 24
    return MOUNTAINS_24[neighbor]
