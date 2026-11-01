"""干支属性与干支关系（符号层，纯函数）。

铁律：本模块**禁止**输出吉凶宜忌。这里只提供"是什么关系"，不提供"好不好"。
关系的吉凶属性由 ``core-rule`` 的规则库声明，且必须带出处。

关于自刑（重要）
----------------
自刑为 **辰辰、午午、酉酉、亥亥** 四组。``未未`` 不是自刑。
四柱出现多个"未"只能作为"地支重复/伏吟类"结构提示处理，
且"伏吟"是否成立必须由流派规则解释（见 docs/adr/0003-rule-dsl.md）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

__all__ = [
    "GAN",
    "ZHI",
    "WUXING",
    "WUXING_ORDER",
    "GAN_WUXING",
    "ZHI_WUXING",
    "GAN_YINYANG",
    "ZHI_YINYANG",
    "SANHE",
    "SANHUI",
    "LIUHE",
    "LIUCHONG",
    "LIUHAI",
    "SANXING",
    "ZIXING",
    "PO",
    "GAN_HE",
    "GAN_CHONG",
    "wuxing_of_gan",
    "wuxing_of_zhi",
    "relation_between_zhi",
    "all_relations_between_zhi",
    "relation_between_gan",
    "sanhe_group_of",
    "same_group",
    "zhi_relations_in",
    "zhi_counts",
    "sanhe_present",
    "sanhui_present",
    "ZhiRelation",
    "Element",
]

Element = Literal["木", "火", "土", "金", "水"]

GAN = ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")
ZHI = ("子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥")

#: 六十甲子（甲子=0）。与 ``core_time.calendar.GANZHI60`` 必须一致，
#: 由 tests/unit/test_symbol_time_consistency.py 断言。
GANZHI60: tuple[str, ...] = tuple(GAN[i % 10] + ZHI[i % 12] for i in range(60))
WUXING: tuple[Element, ...] = ("木", "火", "土", "金", "水")
WUXING_ORDER = {e: i for i, e in enumerate(WUXING)}

GAN_WUXING: dict[str, Element] = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}
ZHI_WUXING: dict[str, Element] = {
    "子": "水", "丑": "土", "寅": "木", "卯": "木", "辰": "土", "巳": "火",
    "午": "火", "未": "土", "申": "金", "酉": "金", "戌": "土", "亥": "水",
}
GAN_YINYANG: dict[str, str] = {g: ("阳" if i % 2 == 0 else "阴") for i, g in enumerate(GAN)}
ZHI_YINYANG: dict[str, str] = {z: ("阳" if i % 2 == 0 else "阴") for i, z in enumerate(ZHI)}

#: 三合局：{地支集合: 化气五行}
SANHE: dict[frozenset[str], Element] = {
    frozenset("申子辰"): "水",
    frozenset("亥卯未"): "木",
    frozenset("寅午戌"): "火",
    frozenset("巳酉丑"): "金",
}

#: 三会方局
SANHUI: dict[frozenset[str], Element] = {
    frozenset("寅卯辰"): "木",
    frozenset("巳午未"): "火",
    frozenset("申酉戌"): "金",
    frozenset("亥子丑"): "水",
}

#: 六合
LIUHE: dict[frozenset[str], Element] = {
    frozenset("子丑"): "土",
    frozenset("寅亥"): "木",
    frozenset("卯戌"): "火",
    frozenset("辰酉"): "金",
    frozenset("巳申"): "水",
    frozenset("午未"): "土",
}

#: 六冲
LIUCHONG: frozenset[frozenset[str]] = frozenset(
    frozenset(p) for p in ("子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥")
)

#: 六害
LIUHAI: frozenset[frozenset[str]] = frozenset(
    frozenset(p) for p in ("子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌")
)

#: 三刑（不含自刑）：寅巳申、丑戌未 为三支互刑；子卯 为二支相刑
SANXING: frozenset[frozenset[str]] = frozenset(
    frozenset(p) for p in ("寅巳申", "丑戌未", "子卯")
)

#: 自刑：辰辰、午午、酉酉、亥亥。**未未不在其列。**
ZIXING: frozenset[str] = frozenset("辰午酉亥")

#: 相破
PO: frozenset[frozenset[str]] = frozenset(
    frozenset(p) for p in ("子酉", "丑辰", "寅亥", "卯午", "巳申", "未戌")
)

#: 天干五合
GAN_HE: dict[frozenset[str], Element] = {
    frozenset("甲己"): "土",
    frozenset("乙庚"): "金",
    frozenset("丙辛"): "水",
    frozenset("丁壬"): "木",
    frozenset("戊癸"): "火",
}

#: 天干相冲（阳干对阳干、阴干对阴干，隔四相冲）
GAN_CHONG: frozenset[frozenset[str]] = frozenset(
    frozenset(p) for p in ("甲庚", "乙辛", "丙壬", "丁癸")
)


def wuxing_of_gan(gan: str) -> Element:
    return GAN_WUXING[gan]


def wuxing_of_zhi(zhi: str) -> Element:
    return ZHI_WUXING[zhi]


def sanhe_group_of(zhi: str) -> frozenset[str]:
    """返回包含 ``zhi`` 的三合局地支集合。"""
    for group in SANHE:
        if zhi in group:
            return group
    raise KeyError(zhi)  # pragma: no cover


def same_group(zhi_a: str, zhi_b: str, kind: str = "sanhe") -> bool:
    """两地支是否同属某组（``sanhe`` / ``sanhui`` / ``chong`` 等）。"""
    table: dict[str, Iterable[frozenset[str]]] = {
        "sanhe": SANHE.keys(),
        "sanhui": SANHUI.keys(),
        "liuhe": LIUHE.keys(),
        "chong": LIUCHONG,
        "hai": LIUHAI,
        "xing": SANXING,
        "po": PO,
    }
    groups = table.get(kind)
    if groups is None:
        raise ValueError(f"未知分组类型: {kind}")
    return any(zhi_a in g and zhi_b in g for g in groups)


@dataclass(frozen=True)
class ZhiRelation:
    """一对地支的关系。``kind`` 取 冲/合/害/刑/破/自刑/三合/三会/同支/无。"""

    a: str
    b: str
    kind: str
    element: Element | None = None

    @property
    def is_conflict(self) -> bool:
        """结构性冲突（不含"合"）。仅为结构分类，不含吉凶判断。"""
        return self.kind in ("冲", "害", "刑", "破", "自刑")


def relation_between_zhi(a: str, b: str) -> ZhiRelation:
    """判定两支关系。同一对地支可同时具备多重关系，此处按固定优先级返回首要关系。

    优先级：自刑 > 三会 > 三合 > 冲 > 合 > 害 > 刑 > 破 > 同支 > 无。
    需要全部关系时用 ``all_relations_between_zhi``。
    """
    rels = all_relations_between_zhi(a, b)
    return rels[0] if rels else ZhiRelation(a, b, "无")


def all_relations_between_zhi(a: str, b: str) -> list[ZhiRelation]:
    """返回两支的**全部**关系（按优先级排序）。"""
    out: list[ZhiRelation] = []
    if a == b and a in ZIXING:
        out.append(ZhiRelation(a, b, "自刑"))
    if a == b:
        out.append(ZhiRelation(a, b, "同支"))
    pair = frozenset((a, b))
    for table, kind in ((SANHUI, "三会"), (SANHE, "三合"), (LIUHE, "合")):
        if pair in table and len(pair) == 2:
            out.append(ZhiRelation(a, b, kind, table[pair]))
    if pair in LIUCHONG:
        out.append(ZhiRelation(a, b, "冲"))
    if pair in LIUHAI:
        out.append(ZhiRelation(a, b, "害"))
    if any(pair <= group and len(pair) == 2 for group in SANXING):
        out.append(ZhiRelation(a, b, "刑"))
    if pair in PO:
        out.append(ZhiRelation(a, b, "破"))
    # 半合：三合局中任取两支（含生地/墓地之别，此处只作结构提示）
    for group, element in SANHE.items():
        if len(pair) == 2 and pair <= group:
            out.append(ZhiRelation(a, b, "半合", element))
    order = {
        "自刑": 0, "三会": 1, "三合": 2, "冲": 3, "合": 4, "半合": 5,
        "害": 6, "刑": 7, "破": 8, "同支": 9, "无": 10,
    }
    out.sort(key=lambda r: order[r.kind])
    return out


def relation_between_gan(a: str, b: str) -> ZhiRelation:
    """天干关系：合/冲/同干/无。"""
    pair = frozenset((a, b))
    if a == b:
        return ZhiRelation(a, b, "同干")
    if pair in GAN_HE:
        return ZhiRelation(a, b, "合", GAN_HE[pair])
    if pair in GAN_CHONG:
        return ZhiRelation(a, b, "冲")
    return ZhiRelation(a, b, "无")


def zhi_relations_in(zhis: Iterable[str]) -> list[ZhiRelation]:
    """四柱（或任意地支序列）内两两关系全表。"""
    seq = list(zhis)
    out: list[ZhiRelation] = []
    for i in range(len(seq)):
        for j in range(i + 1, len(seq)):
            for rel in all_relations_between_zhi(seq[i], seq[j]):
                if rel.kind != "无":
                    out.append(ZhiRelation(f"{seq[i]}{i}", f"{seq[j]}{j}", rel.kind, rel.element))
    return out


def zhi_counts(zhis: Iterable[str]) -> dict[str, int]:
    """地支出现次数（用于重复/伏吟类结构提示，不判断吉凶）。"""
    counts: dict[str, int] = {}
    for z in zhis:
        counts[z] = counts.get(z, 0) + 1
    return counts


def sanhe_present(zhis: Iterable[str]) -> list[tuple[frozenset[str], Element]]:
    """检测四柱中完整成立的三合局（三支齐现）。"""
    seq = set(zhis)
    return [(group, element) for group, element in SANHE.items() if group <= seq]


def sanhui_present(zhis: Iterable[str]) -> list[tuple[frozenset[str], Element]]:
    """检测完整三会方局。"""
    seq = set(zhis)
    return [(group, element) for group, element in SANHUI.items() if group <= seq]
