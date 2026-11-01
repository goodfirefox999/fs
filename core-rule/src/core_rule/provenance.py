"""出处与可复现信息（provenance）。

铁律 3：每条判定必须带 provenance（规则 id、规则库版本、引文、参数快照）。

``Citation.quote`` 为空**不是**缺陷 —— 它精确表示"尚未核对原文"。
Agent 不得为了填满字段而编造卷次或引文（硬禁止第 1 条）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Citation", "Provenance", "stable_hash"]


def stable_hash(payload: Any) -> str:
    """对任意 JSON 可序列化对象求稳定哈希（键排序、紧凑分隔符）。"""
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Citation:
    """结构化引文。空字段表示"待补"，不是错误。

    ``kind`` 区分两类出处（ADR-0007）：

    - ``classic``：古籍原文。``status: 已考证`` 时必须填 ``quote`` + ``verified_by``。
    - ``spec``：内核规格条款。``status: 定义级`` 时使用，``quote`` 写明规格条款本身
      （如"自刑四组：辰辰、午午、酉酉、亥亥；未未不在其列"），不冒充古籍。
    """

    source: str
    kind: str = "classic"  # classic | spec | secondary
    edition: str | None = None
    juan: str | None = None
    #: 篇次（如「义例四」）。**比卷次稳**：不同版本对卷次划分记载有差异，
    #: 只记卷次容易对不上（评审 2026-11-01 第四轮指出）。
    pian: str | None = None
    #: 条目名（如「四离四绝」），便于在篇内定位。
    entry: str | None = None
    #: 引文性质：原文 / 白话转述 / 通行口径。
    #: **最大风险是把「通行口径」当「原文」录** —— 已考证必须 quote_kind=原文。
    quote_kind: str | None = None
    quote: str | None = None
    url_or_path: str | None = None
    verified_by: str | None = None
    verified_at: str | None = None
    #: 书目真实性（VERIFICATION_GUIDE 三）：authentic（官修/原著）｜disputed（托名/存疑）｜
    #: pseudepigraphic（确证托名）｜None=待核。可采性优先于真伪——托名不排除引用，
    #: 但不得声称"古法/原著"（评审第十三轮 GUIDE 三·三联动重审的判定字段）。
    book_authenticity: str | None = None
    confidence: str | None = None  # 高 / 中 / 低

    @property
    def has_quote(self) -> bool:
        return bool(self.quote and self.quote.strip())

    @property
    def is_verbatim(self) -> bool:
        """是否为古籍原文（而非白话转述或通行口径）。"""
        return self.quote_kind == "原文"

    @property
    def is_complete(self) -> bool:
        """是否具备"已考证"所需的完整引文。"""
        return bool(self.source and self.has_quote and self.verified_by)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source": self.source,
            "edition": self.edition,
            "juan": self.juan,
            "pian": self.pian,
            "entry": self.entry,
            "quote_kind": self.quote_kind,
            "quote": self.quote,
            "url_or_path": self.url_or_path,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at,
            "confidence": self.confidence,
            "book_authenticity": self.book_authenticity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Citation":
        return cls(
            source=data.get("source") or "",
            kind=data.get("kind") or "classic",
            edition=data.get("edition"),
            juan=data.get("juan"),
            pian=data.get("pian"),
            entry=data.get("entry"),
            quote_kind=data.get("quote_kind"),
            quote=data.get("quote"),
            url_or_path=data.get("url_or_path"),
            verified_by=data.get("verified_by"),
            verified_at=data.get("verified_at"),
            confidence=data.get("confidence"),
            book_authenticity=data.get("book_authenticity"),
        )


@dataclass(frozen=True)
class Provenance:
    """一次判定的完整溯源信息。"""

    rule_id: str
    rule_version: int
    school: str
    rule_lib_version: str
    citation: Citation
    params_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def params_hash(self) -> str:
        return stable_hash(self.params_snapshot)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "school": self.school,
            "rule_lib_version": self.rule_lib_version,
            "citation": self.citation.to_dict(),
            "params_hash": self.params_hash,
            "params_snapshot": self.params_snapshot,
        }
