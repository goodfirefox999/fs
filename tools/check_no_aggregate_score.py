#!/usr/bin/env python
"""禁聚合总分 lint（C20）：判定层不得出现"跨派平均分"。

背景
----
AGENTS 硬禁止第 2 条写着「不得把三态判定压缩成单一总分；不得跨派别合成综合吉凶分」。
但这条在 2026-11-02 之前只是**约定**：``ranker.sort_key`` 的末位就放着
``-mean_rank_score``（各派 ``rank_score`` 的跨派均值），``engine`` 的 tier 推导里还有一个
``_total_rank``（同样是跨派均值）。两条都活得很好，因为没有人能在 CI 上抓住它们。

本 lint 把约定换成契约。它只查一件事：**判决层里有没有"除以人数/派数"的均值**。

为什么允许 ``sum()`` 却不允许 ``sum(x)/len(x)``
------------------------------------------------
- ``sum(len(r.vetoes) for r in per_school.values())`` = 否决**条数**。计数是事实，
  而且正是"共识用整数比、不用权重"的合规形态（ADR-0015）。
- ``sum(scores) / len(scores)`` = 均值。它把不同派别、不同加权项的分值当同一把尺子，
  一旦存在，下游必然拿它当"综合吉凶分"展示。
因此判据是**分母**：出现 ``/ len(...)`` 或 ``.mean(...)`` 即视为均值。

豁免
----
行内或上一行标注 ``# lint-exempt: <理由>``，理由不得为空且不少于 8 个字符。
豁免必须能回答"这个均值为什么不会进排序键"。不写理由的豁免视同违规。

适用范围
--------
``core-eval/src``（判定层）、``app-zeri/src``（应用层）。
``core-time`` / ``core-symbol`` 是事实层，本来就不该出现分数聚合，不在扫描面内。

用法
----
    python tools/check_no_aggregate_score.py           # 扫描，有违规即退出码 1
    python tools/check_no_aggregate_score.py --list    # 列出全部豁免点及其理由
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

ROOTS = ["core-eval/src", "app-zeri/src"]

#: 视同均值的统计函数（``statistics`` 与常见数组库）
MEAN_CALLS = {"mean", "fmean", "geometric_mean", "harmonic_mean", "average", "nanmean"}

#: 函数名里出现这些词即视为在重建均值工具
MEAN_NAME_TOKENS = ("mean", "average")

EXEMPT_MARK = "lint-exempt:"
MIN_REASON_LEN = 8


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    detail: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: [{self.code}] {self.detail}"


def _exempt_reason(lines: list[str], line_no: int) -> str | None:
    """取豁免理由：优先本行，其次上一行。返回 None 表示未豁免。"""
    for idx in (line_no - 1, line_no - 2):  # 1-based → 0-based，本行与上一行
        if idx < 0 or idx >= len(lines):
            continue
        raw = lines[idx]
        if EXEMPT_MARK not in raw:
            continue
        reason = raw.split(EXEMPT_MARK, 1)[1].strip()
        return reason if len(reason) >= MIN_REASON_LEN else ""
    return None


def _is_len_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "len"
        and len(node.args) == 1
        and not node.keywords
    )


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def scan_source(text: str, rel_path: str) -> list[Finding]:
    """扫描一段源码，返回违规点（不含豁免判定后的过滤）。"""
    try:
        tree = ast.parse(text, filename=rel_path)
    except SyntaxError as exc:
        return [Finding(rel_path, exc.lineno or 0, "C20-syntax", f"语法错误: {exc.msg}")]

    lines = text.splitlines()
    findings: list[Finding] = []

    def report(node: ast.AST, code: str, detail: str) -> None:
        line_no = getattr(node, "lineno", 0)
        reason = _exempt_reason(lines, line_no)
        if reason is None:
            findings.append(Finding(rel_path, line_no, code, detail))
        elif reason == "":
            findings.append(
                Finding(
                    rel_path,
                    line_no,
                    "C20-empty-exempt",
                    f"豁免理由为空或过短（须 >= {MIN_REASON_LEN} 字符）",
                )
            )

    for node in ast.walk(tree):
        # 规则 a：任何「除以 len(...)」都是均值
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            if _is_len_call(node.right):
                report(
                    node,
                    "C20-mean",
                    "出现 `/ len(...)`：这是跨派/跨样本均值，属禁止的聚合分；"
                    "改用整数比（如 consensus_ratio）或计数",
                )
        # 规则 b：statistics.mean / np.mean / 任何 .mean(...)
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in MEAN_CALLS:
                report(
                    node,
                    "C20-mean-call",
                    f"调用了均值函数 `{name}(...)`；判定层禁止均值，改用计数或整数比",
                )
        # 规则 c：不许重建一个叫 mean/average 的函数
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            lowered = node.name.lower()
            if any(tok in lowered for tok in MEAN_NAME_TOKENS):
                report(
                    node,
                    "C20-mean-def",
                    f"定义了均值语义的函数 `{node.name}`；判定层禁止重建均值工具",
                )

    return findings


def scan_repo(root: Path | None = None) -> list[Finding]:
    base = root or Path(__file__).resolve().parents[1]
    findings: list[Finding] = []
    for rel in ROOTS:
        for path in sorted((base / rel).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel_path = str(path.relative_to(base))
            findings.extend(scan_source(path.read_text(encoding="utf-8"), rel_path))
    return findings


def list_exemptions(root: Path | None = None) -> list[str]:
    """列出仓库内全部豁免点，便于评审逐个复核理由。"""
    base = root or Path(__file__).resolve().parents[1]
    out: list[str] = []
    for rel in ROOTS:
        for path in sorted((base / rel).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel_path = str(path.relative_to(base))
            for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if EXEMPT_MARK in raw:
                    reason = raw.split(EXEMPT_MARK, 1)[1].strip()
                    out.append(f"{rel_path}:{i}: {reason}")
    return out


def main(argv: list[str]) -> int:
    base = Path(__file__).resolve().parents[1]
    if "--list" in argv:
        rows = list_exemptions(base)
        print(f"豁免点 {len(rows)} 处：")
        for row in rows:
            print(f"  - {row}")
        return 0

    findings = scan_repo(base)
    if not findings:
        exempt = len(list_exemptions(base))
        print(f"✅ C20 通过：判定层未发现聚合均值（豁免 {exempt} 处，用 --list 复核理由）")
        return 0

    print(f"❌ C20 失败：发现 {len(findings)} 处聚合均值/均值工具")
    for f in findings:
        print(f"  {f.format()}")
    print("\n修复方式：改为整数计数或整数比；确属描述统计（不进排序键）的，")
    print(f"在同行或上一行加 `# {EXEMPT_MARK} <不少于 {MIN_REASON_LEN} 字的理由>`。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
