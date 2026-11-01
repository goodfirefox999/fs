"""结构检测器（判定层，独立于吉凶规则）。

设计约束（docs/DEVELOPMENT.md 第 6.2 节 + 第二份文档第 2 条纠正）：

1. 结构检测**必须独立实现**，不得混在吉神/凶煞规则里；
2. 输出只描述"结构是什么"，不含吉凶；吉凶由规则库声明；
3. 自刑仅 **辰辰、午午、酉酉、亥亥**；``未未`` 不是自刑，只能作为"地支重复"结构提示；
4. "伏吟"是否成立由流派规则解释，本检测器只给出"重复次数"这一客观量。

本模块被 ``engine`` 用于生成结构类 Judgment，也被 ``tests/property`` 直接测试。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core_symbol.ganzhi import (
    LIUCHONG,
    LIUHAI,
    PO,
    SANHE,
    SANHUI,
    SANXING,
    ZIXING,
    Element,
    all_relations_between_zhi,
    relation_between_gan,
)

__all__ = ["StructureHit", "StructureReport", "detect_structure", "ZIXING_SET"]

#: 自刑四支（辰辰、午午、酉酉、亥亥）。未未不在此列。
ZIXING_SET: frozenset[str] = ZIXING


@dataclass(frozen=True)
class StructureHit:
    """一条结构命中。``kind`` 为结构类别，不含吉凶。"""

    kind: str
    detail: str
    members: tuple[str, ...] = ()
    positions: tuple[int, ...] = ()
    element: Element | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "detail": self.detail,
            "members": list(self.members),
            "positions": list(self.positions),
            "element": self.element,
        }


@dataclass
class StructureReport:
    """结构检测总报告。"""

    zhis: tuple[str, ...]
    gans: tuple[str, ...]
    shan_jia_zhi: str | None = None
    hits: list[StructureHit] = field(default_factory=list)

    def of_kind(self, *kinds: str) -> list[StructureHit]:
        return [h for h in self.hits if h.kind in kinds]

    @property
    def max_repeat(self) -> int:
        counts = self.zhi_counts()
        return max(counts.values()) if counts else 0

    def zhi_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for z in self.zhis:
            counts[z] = counts.get(z, 0) + 1
        return counts

    @property
    def repeated(self) -> dict[str, int]:
        return {z: c for z, c in self.zhi_counts().items() if c >= 2}

    @property
    def has_self_punishment(self) -> bool:
        """是否出现自刑（仅辰辰/午午/酉酉/亥亥）。"""
        return any(h.kind == "自刑" for h in self.hits)

    @property
    def weiwei_is_self_punishment(self) -> bool:
        """显式断言：未未不是自刑。供测试直接引用，防止回归。"""
        return any(h.kind == "自刑" and h.members == ("未", "未") for h in self.hits)

    def to_dict(self) -> dict[str, Any]:
        return {
            "zhis": list(self.zhis),
            "gans": list(self.gans),
            "shan_jia_zhi": self.shan_jia_zhi,
            "zhi_counts": self.zhi_counts(),
            "repeated": self.repeated,
            "max_repeat": self.max_repeat,
            "has_self_punishment": self.has_self_punishment,
            "hits": [h.to_dict() for h in self.hits],
        }


def detect_structure(
    zhis: list[str] | tuple[str, ...],
    gans: list[str] | tuple[str, ...],
    shan_jia_zhi: str | None = None,
) -> StructureReport:
    """检测四柱（或任意干支序列）中的结构关系。

    返回的 ``hits`` 按固定顺序排列：三会 → 三合 → 半合 → 冲 → 合 → 害 → 刑 → 自刑 → 破 → 重复。
    该顺序**不代表轻重**，仅为可复现。
    """
    report = StructureReport(zhis=tuple(zhis), gans=tuple(gans), shan_jia_zhi=shan_jia_zhi)
    zhi_seq = list(zhis)

    # 三会 / 三合（需三支齐现）
    for group, element in SANHUI.items():
        if group <= set(zhi_seq):
            report.hits.append(
                StructureHit(
                    kind="三会",
                    detail=f"{''.join(sorted(group))}三会{element}局",
                    members=tuple(sorted(group)),
                    element=element,
                )
            )
    for group, element in SANHE.items():
        if group <= set(zhi_seq):
            report.hits.append(
                StructureHit(
                    kind="三合",
                    detail=f"{''.join(sorted(group))}三合{element}局",
                    members=tuple(sorted(group)),
                    element=element,
                )
            )

    # 两两关系
    for i in range(len(zhi_seq)):
        for j in range(i + 1, len(zhi_seq)):
            for rel in all_relations_between_zhi(zhi_seq[i], zhi_seq[j]):
                if rel.kind in ("无", "三会", "三合"):
                    continue
                report.hits.append(
                    StructureHit(
                        kind=rel.kind,
                        detail=f"{zhi_seq[i]}{zhi_seq[j]}{rel.kind}",
                        members=(zhi_seq[i], zhi_seq[j]),
                        positions=(i, j),
                        element=rel.element,
                    )
                )

    # 天干关系
    for i in range(len(gans)):
        for j in range(i + 1, len(gans)):
            rel = relation_between_gan(gans[i], gans[j])
            if rel.kind in ("合", "冲"):
                report.hits.append(
                    StructureHit(
                        kind=f"干{rel.kind}",
                        detail=f"{gans[i]}{gans[j]}干{rel.kind}",
                        members=(gans[i], gans[j]),
                        positions=(i, j),
                        element=rel.element,
                    )
                )

    # 重复（伏吟候选，不含吉凶）
    for z, c in report.zhi_counts().items():
        if c >= 2:
            positions = tuple(i for i, x in enumerate(zhi_seq) if x == z)
            report.hits.append(
                StructureHit(
                    kind="重复",
                    detail=f"{z}见{c}次",
                    members=(z,),
                    positions=positions,
                )
            )

    # 山家三合（扶山结构，不含吉凶）
    if shan_jia_zhi:
        combined = set(zhi_seq) | {shan_jia_zhi}
        for group, element in SANHE.items():
            if group <= combined and shan_jia_zhi in group:
                report.hits.append(
                    StructureHit(
                        kind="山家三合",
                        detail=f"山家{shan_jia_zhi}与日课成{''.join(sorted(group))}三合{element}局",
                        members=tuple(sorted(group)),
                        element=element,
                    )
                )
        for z in dict.fromkeys(zhi_seq):
            pair = {shan_jia_zhi, z}
            if len(pair) != 2:
                continue
            group = next((g for g in SANHE if pair <= g), None)
            if group is not None:
                report.hits.append(
                    StructureHit(
                        kind="山家半合",
                        detail=f"山家{shan_jia_zhi}与{z}半合",
                        members=(shan_jia_zhi, z),
                    )
                )

    order = {
        "三会": 0, "三合": 1, "半合": 2, "冲": 3, "合": 4, "害": 5, "刑": 6,
        "自刑": 7, "破": 8, "干合": 9, "干冲": 10, "重复": 11,
        "山家三合": 12, "山家半合": 13,
    }
    report.hits.sort(key=lambda h: (order.get(h.kind, 99), h.positions, h.detail))
    return report


_ = (LIUCHONG, LIUHAI, PO, SANXING)  # 关系表由 core_symbol 统一维护，此处仅引用
