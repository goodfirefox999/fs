"""案例库 schema（应用层，纯数据结构 + 校验）。

用途限定（必须写进 README 与报告页脚）
------------------------------------
案例只用于验证"实现是否符合宣称规则"，**不用于验证择日是否灵验**；
任何输出不得称为准确率，只能说"与作者判定吻合度"。

分级
----
A：输入完整、参数可推断、来源可查 → 进回归集
B：需假设 → 仅做分歧与缺口分析
C：残缺/来源不明 → 不统计
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml

__all__ = ["Case", "CaseSource", "CaseInput", "AuthorClaim", "load_case", "CaseError"]

Grade = Literal["A", "B", "C"]


class CaseError(Exception):
    """案例文件非法。"""


@dataclass(frozen=True)
class CaseSource:
    """来源与原文快照。``snapshot_path`` 必填 —— 防删帖，也防 Agent 编造出处。"""

    snapshot_path: str
    url: str | None = None
    collected_at: str | None = None
    license_note: str | None = None


@dataclass(frozen=True)
class CaseInput:
    course: datetime
    azimuth_deg: float
    task_kind: str
    lat: float = 0.0
    lon: float = 0.0
    nodes: tuple[str, ...] = ()
    strictness: str = "normal"
    person_year_zhi: str | None = None
    person_name: str | None = None
    fenjin: str | None = None


@dataclass(frozen=True)
class AuthorClaim:
    """作者原判。**原样保留，不参与判定**，仅用于一致性比对。"""

    raw: str
    verdict: str | None = None
    notes: str | None = None


@dataclass
class Case:
    case_id: str
    title: str
    grade: Grade
    source: CaseSource
    input: CaseInput
    author_claim: AuthorClaim
    params_assumed: tuple[str, ...] = ()
    expected: dict[str, Any] = field(default_factory=dict)
    notes: str | None = None
    path: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "grade": self.grade,
            "source": {
                "snapshot_path": self.source.snapshot_path,
                "url": self.source.url,
                "collected_at": self.source.collected_at,
                "license_note": self.source.license_note,
            },
            "input": {
                "course": self.input.course.isoformat(),
                "azimuth_deg": self.input.azimuth_deg,
                "task_kind": self.input.task_kind,
                "lat": self.input.lat,
                "lon": self.input.lon,
                "nodes": list(self.input.nodes),
                "strictness": self.input.strictness,
                "person_year_zhi": self.input.person_year_zhi,
                "person_name": self.input.person_name,
                "fenjin": self.input.fenjin,
            },
            "params_assumed": list(self.params_assumed),
            "author_claim": {
                "raw": self.author_claim.raw,
                "verdict": self.author_claim.verdict,
                "notes": self.author_claim.notes,
            },
            "expected": self.expected,
            "notes": self.notes,
        }


def _require(data: dict[str, Any], key: str, path: Path) -> Any:
    if key not in data or data[key] is None:
        raise CaseError(f"{path}: 缺少必填字段 {key}")
    return data[key]


def load_case(path: Path) -> Case:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise CaseError(f"{path}: 顶层必须是映射")

    for key in ("case_id", "title", "grade", "source", "input", "author_claim"):
        _require(raw, key, path)

    grade = raw["grade"]
    if grade not in ("A", "B", "C"):
        raise CaseError(f"{path}: grade 非法 {grade}")

    src = raw["source"]
    if not isinstance(src, dict) or not src.get("snapshot_path"):
        raise CaseError(f"{path}: source.snapshot_path 必填（原文快照，防删帖）")

    inp = raw["input"]
    if not isinstance(inp, dict):
        raise CaseError(f"{path}: input 必须是映射")
    for key in ("course", "azimuth_deg", "task_kind"):
        if key not in inp:
            raise CaseError(f"{path}: input 缺少 {key}")

    claim = raw["author_claim"]
    if not isinstance(claim, dict) or "raw" not in claim:
        raise CaseError(f"{path}: author_claim.raw 必填（原样保留作者断言）")

    return Case(
        case_id=str(raw["case_id"]),
        title=str(raw["title"]),
        grade=grade,
        source=CaseSource(
            snapshot_path=str(src["snapshot_path"]),
            url=src.get("url"),
            collected_at=src.get("collected_at"),
            license_note=src.get("license_note"),
        ),
        input=CaseInput(
            course=datetime.fromisoformat(str(inp["course"])),
            azimuth_deg=float(inp["azimuth_deg"]),
            task_kind=str(inp["task_kind"]),
            lat=float(inp.get("lat", 0.0)),
            lon=float(inp.get("lon", 0.0)),
            nodes=tuple(inp.get("nodes") or ()),
            strictness=str(inp.get("strictness", "normal")),
            person_year_zhi=inp.get("person_year_zhi"),
            person_name=inp.get("person_name"),
            fenjin=inp.get("fenjin"),
        ),
        author_claim=AuthorClaim(
            raw=str(claim["raw"]),
            verdict=claim.get("verdict"),
            notes=claim.get("notes"),
        ),
        params_assumed=tuple(raw.get("params_assumed") or ()),
        expected=raw.get("expected") or {},
        notes=raw.get("notes"),
        path=path,
    )
