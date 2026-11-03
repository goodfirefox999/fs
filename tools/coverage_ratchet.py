#!/usr/bin/env python3
"""覆盖率 ratchet（包级 + 文件级）：整体 84% 不能替 app-zeri 68% 背书，
包级 68% 也不能替 cli.py 34% 背书。

背景（2026-11-03 评审十/十一回路）
----------------------------------
第一版 ratchet 只按包设地板，堵住了「整体 84% 掩盖 app-zeri 68%」；但包级
68% 仍允许 ``cli.py`` 停在 34%——只要 ``case_runner.py`` 从 44% 涨到 80%，
包级可能还是 68%，用户入口可以永远不测。这是同一类漏洞降了一级。

本工具因此同时检查两层：

1. **包级地板**：``modules.<name>.min``，低于即失败；
2. **文件级地板**：包内所有低于 ``target`` 的文件，必须在 ``files`` 里单列
   ``min``。新增低覆盖文件不会静默漏网——没登记就是失败，迫使作者显式决定
   「补测试还是登记缺口」。

配套规则：

- 基线**只许升不许降**；``--update`` 只打印上调建议（不自动写文件，避免覆盖
  YAML 里的取值理由），低于基线时拒绝 update；
- 基线过松（实测 - 基线 > 2pp）只告警不阻断，但每次 ``make cov`` 都看得见；
- ``min`` 是地板，``target`` 是目标，两者不是一回事（``min`` 可以高于目标，
  表示「已经超过目标，但不许掉回来」）。

用法::

    python tools/coverage_ratchet.py            # 检查（make cov 调用）
    python tools/coverage_ratchet.py --update   # 覆盖率提升后打印上调建议
    python tools/coverage_ratchet.py --baseline path/to/baseline.yaml

退出码：0 = 全部不低于地板；1 = 有模块/文件低于地板、缺文件级基线，
或基线配置不合法。
"""

from __future__ import annotations

import argparse
import io
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import coverage
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = ROOT / "tools" / "coverage_ratchet.yaml"
LOOSE_GAP_PP = 2.0

__all__ = [
    "Baseline",
    "FileSpec",
    "ModuleSpec",
    "Row",
    "build_rows",
    "discover_file_coverage",
    "failures",
    "load_baseline",
    "loose_baselines",
    "main",
    "measure",
    "missing_file_baselines",
    "render",
    "updated_baseline",
]


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    path: str
    minimum: int
    target: int


@dataclass(frozen=True)
class FileSpec:
    path: str
    minimum: int
    target: int


@dataclass(frozen=True)
class Baseline:
    modules: dict[str, ModuleSpec]
    files: dict[str, FileSpec]


@dataclass(frozen=True)
class Row:
    """一条地板：模块或文件。``actual`` 为 None 表示没有采集到数据。"""

    name: str
    path: str
    minimum: int
    target: int
    actual: float | None
    kind: str  # "module" | "file"
    error: str | None = None


def _pct(spec: dict[str, Any], key: str, where: str) -> int:
    value = spec.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        raise ValueError(f"{where}.{key} 必须是 0..100 的整数，得到 {value!r}")
    return value


def _module_for(path: str, modules: dict[str, ModuleSpec]) -> ModuleSpec | None:
    """按最长路径前缀归属模块（防止 core-rule 与 core-rule-extra 误配）。"""
    matches = [
        spec for spec in modules.values() if path == spec.path or path.startswith(spec.path + "/")
    ]
    return max(matches, key=lambda spec: len(spec.path)) if matches else None


def load_baseline(path: Path | str = DEFAULT_BASELINE) -> Baseline:
    """读取包级 + 文件级基线；结构错误直接抛 ``ValueError``。"""
    p = Path(path)
    if not p.exists():
        raise ValueError(f"基线文件不存在: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    raw_modules = data.get("modules")
    if not isinstance(raw_modules, dict) or not raw_modules:
        raise ValueError(f"{p}: modules 必须是非空映射")

    modules: dict[str, ModuleSpec] = {}
    for name, spec in raw_modules.items():
        if not isinstance(spec, dict):
            raise ValueError(f"{p}: modules.{name} 必须是映射")
        module_path = spec.get("path")
        if not isinstance(module_path, str) or not module_path:
            raise ValueError(f"{p}: modules.{name}.path 必须是非空字符串")
        minimum = _pct(spec, "min", f"{p}: modules.{name}")
        target = _pct(spec, "target", f"{p}: modules.{name}")
        modules[name] = ModuleSpec(name=name, path=module_path, minimum=minimum, target=target)

    raw_files = data.get("files") or {}
    if not isinstance(raw_files, dict):
        raise ValueError(f"{p}: files 必须是映射")
    files: dict[str, FileSpec] = {}
    for file_path, spec in raw_files.items():
        if not isinstance(file_path, str) or not file_path.endswith(".py"):
            raise ValueError(f"{p}: files 的键必须是 .py 路径，得到 {file_path!r}")
        if not isinstance(spec, dict):
            raise ValueError(f"{p}: files.{file_path} 必须是映射")
        parent = _module_for(file_path, modules)
        if parent is None:
            raise ValueError(f"{p}: files.{file_path} 不在任何 modules 路径下")
        minimum = _pct(spec, "min", f"{p}: files.{file_path}")
        if minimum > parent.target:
            raise ValueError(
                f"{p}: files.{file_path}.min={minimum} 高于包目标 {parent.target}"
                "（文件地板不得高于目标，否则目标失去意义）"
            )
        files[file_path] = FileSpec(path=file_path, minimum=minimum, target=parent.target)

    return Baseline(modules=modules, files=files)


def measure(cov: coverage.Coverage, path: str) -> tuple[float | None, str | None]:
    """返回 (精确覆盖率, 错误)。``path`` 可以是包目录或单个 .py 文件。"""
    pattern = path if path.endswith(".py") else f"{path}/*"
    try:
        pct = cov.report(include=[pattern], file=io.StringIO())
    except coverage.exceptions.NoDataError:
        return None, "无覆盖率数据（该模块可能未被任何测试导入）"
    except Exception as exc:  # pragma: no cover - coverage 自身异常，报出来而不是吞掉
        return None, f"读取覆盖率失败：{exc}"
    return float(pct), None


def build_rows(baseline: Baseline, cov: coverage.Coverage) -> list[Row]:
    rows: list[Row] = []
    for name in sorted(baseline.modules):
        spec = baseline.modules[name]
        actual, error = measure(cov, spec.path)
        rows.append(
            Row(
                name=name,
                path=spec.path,
                minimum=spec.minimum,
                target=spec.target,
                actual=actual,
                kind="module",
                error=error,
            )
        )
    for path in sorted(baseline.files):
        spec = baseline.files[path]
        actual, error = measure(cov, path)
        rows.append(
            Row(
                name=path,
                path=path,
                minimum=spec.minimum,
                target=spec.target,
                actual=actual,
                kind="file",
                error=error,
            )
        )
    return rows


def discover_file_coverage(
    baseline: Baseline, cov: coverage.Coverage
) -> dict[str, float]:
    """扫描每个包下的全部 .py，返回 {相对路径: 覆盖率}。

    用文件系统枚举而不是 ``measured_files()``：一个从未被 import 的新模块
    不会出现在 measured_files 里，但它的覆盖率就是 0%——正是最该被抓住的
    情况。
    """
    seen: dict[str, float] = {}
    for module in baseline.modules.values():
        root = ROOT / module.path
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            actual, _ = measure(cov, rel)
            seen[rel] = 0.0 if actual is None else actual
    return seen


def missing_file_baselines(
    baseline: Baseline, measured: dict[str, float]
) -> list[str]:
    """包内低于 target 却没登记文件地板 = 失败（新增低覆盖文件不能漏网）。"""
    problems: list[str] = []
    for path in sorted(measured):
        parent = _module_for(path, baseline.modules)
        if parent is None:
            continue
        if measured[path] < parent.target and path not in baseline.files:
            problems.append(
                f"{path}: {measured[path]:.1f}% 低于包目标 {parent.target}%，"
                "但没有文件级地板（在 coverage_ratchet.yaml 的 files 下登记，"
                "或在提交信息里说明为何不登记）"
            )
    return problems


def failures(rows: list[Row]) -> list[str]:
    """低于地板的模块/文件（含无数据）都算失败。"""
    problems: list[str] = []
    for row in rows:
        if row.actual is None:
            problems.append(f"{row.name}: {row.error}（地板 {row.minimum}%）")
        elif row.actual < row.minimum:
            problems.append(
                f"{row.name}: {row.actual:.2f}% 低于地板 {row.minimum}%"
                "（只许升不许降：补测试，不要降地板）"
            )
    return problems


def loose_baselines(rows: list[Row], tolerance: float = LOOSE_GAP_PP) -> list[str]:
    """实测远高于地板（> tolerance）只告警：防止故意写低地板换绿色。"""
    warnings: list[str] = []
    for row in rows:
        if row.actual is None:
            continue
        gap = row.actual - row.minimum
        if gap > tolerance:
            warnings.append(
                f"{row.name}: 实测 {row.actual:.1f}%，地板 {row.minimum}%，"
                f"差距 {gap:.1f}pp（> {tolerance:g}pp，建议 --update 收紧）"
            )
    return warnings


def updated_baseline(baseline: Baseline, rows: list[Row]) -> tuple[Baseline, list[str]]:
    """``--update`` 的唯一合法动作：把地板抬到当前整数值，绝不下调。"""
    by_name = {row.name: row for row in rows}
    changes: list[str] = []
    modules = {name: spec for name, spec in baseline.modules.items()}
    files = {path: spec for path, spec in baseline.files.items()}

    for name, spec in modules.items():
        row = by_name.get(name)
        if row is None or row.actual is None:
            raise ValueError(f"{name}: 无实测值，不能上调地板")
        target = max(spec.minimum, math.floor(row.actual))
        if target > spec.minimum:
            changes.append(f"{name}: {spec.minimum}% → {target}%")
            modules[name] = ModuleSpec(
                name=name, path=spec.path, minimum=target, target=spec.target
            )

    for path, spec in files.items():
        row = by_name.get(path)
        if row is None or row.actual is None:
            raise ValueError(f"{path}: 无实测值，不能上调地板")
        target = max(spec.minimum, math.floor(row.actual))
        if target > spec.minimum:
            changes.append(f"{path}: {spec.minimum}% → {target}%")
            files[path] = FileSpec(path=path, minimum=target, target=spec.target)

    return Baseline(modules=modules, files=files), changes


def render(rows: list[Row]) -> str:
    lines = ["覆盖率 ratchet（包级 + 文件级，只许升不许降）："]

    def section(title: str, kind: str) -> None:
        subset = [row for row in rows if row.kind == kind]
        if not subset:
            return
        lines.append("")
        lines.append(f"  {title}")
        lines.append("    名称                                     当前     地板   目标   判定")
        for row in subset:
            current = "  -  " if row.actual is None else f"{row.actual:5.1f}%"
            ok = row.actual is not None and row.actual >= row.minimum
            mark = "✅" if ok else "❌"
            lines.append(
                f"    {row.name:<40} {current}  {row.minimum:3d}%  {row.target:3d}%   {mark}"
            )

    section("模块", "module")
    section("文件（低于包目标的文件必须单列地板）", "file")
    return "\n".join(lines)


def _payload(baseline: Baseline) -> dict[str, Any]:
    payload: dict[str, Any] = {"modules": {}, "files": {}}
    for name in sorted(baseline.modules):
        spec = baseline.modules[name]
        payload["modules"][name] = {
            "path": spec.path,
            "min": spec.minimum,
            "target": spec.target,
        }
    for path in sorted(baseline.files):
        spec = baseline.files[path]
        payload["files"][path] = {"min": spec.minimum}
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="覆盖率 ratchet（包级 + 文件级）")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="基线 YAML 路径")
    parser.add_argument(
        "--update",
        action="store_true",
        help="覆盖率提升后打印上调建议（只会升，不自动写文件）",
    )
    args = parser.parse_args(argv)
    # 固定到仓库根：coverage 的 include 路径与 .coverage 都是相对 cwd 解析的。
    os.chdir(ROOT)

    baseline_path = Path(args.baseline)
    try:
        baseline = load_baseline(baseline_path)
    except ValueError as exc:
        print(f"❌ 覆盖率基线配置非法：{exc}", file=sys.stderr)
        return 1

    cov = coverage.Coverage()
    try:
        cov.load()
    except coverage.exceptions.NoDataError:
        print(
            "❌ 没有 .coverage：先跑 `pytest --cov`（或 make cov），"
            "禁止读上一次遗留数据",
            file=sys.stderr,
        )
        return 1

    rows = build_rows(baseline, cov)
    print(render(rows))

    warnings = loose_baselines(rows)
    if warnings:
        print("\n⚠️ 基线过松（不阻断，但请确认不是故意写低）：")
        for warning in warnings:
            print(f"  - {warning}")

    # 文件级不变式：包内低于目标的文件都必须在 files 里登记。
    missing = missing_file_baselines(baseline, discover_file_coverage(baseline, cov))
    problems = failures(rows) + missing

    if args.update:
        # 低于地板或缺文件级基线时拒绝 update：否则「上调」会变成「把下降/漏洞
        # 写成新基线」的入口。
        if problems:
            print("❌ 当前覆盖率不满足基线，不能上调（先补测试或补登记）：", file=sys.stderr)
            for problem in problems:
                print(f"  - {problem}", file=sys.stderr)
            return 1
        try:
            updated, changes = updated_baseline(baseline, rows)
        except ValueError as exc:
            print(f"❌ 无法上调基线：{exc}", file=sys.stderr)
            return 1
        if changes:
            body = yaml.safe_dump(_payload(updated), allow_unicode=True, sort_keys=False)
            for change in changes:
                print(f"⬆️  {change}")
            print(
                f"\n把下列地板手改进 {baseline_path}（保留文件头注释；不自动写，"
                "避免覆盖取值理由）：\n"
            )
            print(body)
        else:
            print("地板无需上调（当前覆盖率未超过地板）。")
        return 0

    if problems:
        print("\n❌ 覆盖率 ratchet 失败：", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1
    print("\n✅ 包级与文件级覆盖率均不低于地板")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
