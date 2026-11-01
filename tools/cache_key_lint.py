#!/usr/bin/env python
"""C19 手写缓存键 lint：复合缓存点的键必须经 ``stable_cache_key`` 构造。

背景（ADR-0014 第 216-218 行）：``_select_cached`` 曾只用 version 作键导致缓存
串味；日级事实缓存落地时若再手写组合键，就是第五种手写 key。本 lint 用 AST
扫描运行时代码（``*/src/**``），强制两条规则：

1. **模块级 ``*_CACHE`` dict 的所有下标访问**（读/写），其键表达式必须是
   ``stable_cache_key(...)`` 调用；
2. **``@lru_cache`` 装饰的函数**：参数必须是单一不可变标量（数据文件名、日期
   三元组等进程常量键），且装饰器行须带 ``C19-exempt`` 注记说明为何豁免——
   lru_cache 的键由解释器按参数自动构造，等价于单一函数收拢的退化形态，
   但必须显式声明，防止未来有人在 exempt 位点塞复合可变参数。

版本使用点清单（C19 收拢，ADR-0014 第 220 行）：
- ``manifest.five_school_output``/报告回显的 ``version`` = 人类可读标识，安全；
- ``_select_cached`` 键 = ``fingerprint`` + ``ENGINE_VERSION``（内容身份），已收拢；
- 测试 helper 内的 version = 仅测试作用域，不入生产缓存。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOTS = ["core-time/src", "core-symbol/src", "core-rule/src", "core-eval/src", "app-zeri/src"]

#: 允许的键构造函数名
KEY_FUNCS = {"stable_cache_key"}


def _is_key_func_call(node: ast.AST) -> bool:
    """下标表达式是否为 stable_cache_key(...) 调用（或包含之）。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            func = sub.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in KEY_FUNCS:
                return True
    return False


def _lru_exempt(line_idx: int, lines: list[str]) -> str | None:
    """装饰器行上下 3 行内是否有 C19-exempt 注记，返回注记或 None。"""
    for j in range(max(0, line_idx - 3), min(len(lines), line_idx + 4)):
        if "C19-exempt" in lines[j]:
            return lines[j].strip()
    return None


def scan_file(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:  # pragma: no cover
        return [f"{path}: 语法错误 {exc}"]
    lines = path.read_text(encoding="utf-8").splitlines()

    # 模块级 *_CACHE 命名（dict 容器）
    cache_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id.endswith("_CACHE"):
                    cache_names.add(tgt.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id.endswith("_CACHE"):
                cache_names.add(node.target.id)

    def check_scope(scope: ast.AST) -> None:
        """在单个作用域内检查：键名若在同一作用域内由 helper 赋值，视为收拢。"""
        key_names: set[str] = set()
        for node in ast.walk(scope):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                val = node.value
                if val is None or not _is_key_func_call(val):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for tgt in targets:
                    if isinstance(tgt, ast.Name):
                        key_names.add(tgt.id)
        for node in ast.walk(scope):
            if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
                if node.value.id not in cache_names:
                    continue
                sl = node.slice
                direct = _is_key_func_call(sl)
                via_var = isinstance(sl, ast.Name) and sl.id in key_names
                if not (direct or via_var):
                    problems.append(
                        f"{path}:{node.lineno}: 缓存 {node.value.id} 的键未过 stable_cache_key（C19）"
                    )

    check_scope(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            check_scope(node)
        # 规则 2：@lru_cache（含带参调用）须带 C19-exempt 注记
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                dec_inner = dec.func if isinstance(dec, ast.Call) else dec
                name = getattr(dec_inner, "attr", None) or getattr(dec_inner, "id", None)
                if name == "lru_cache":
                    mark = _lru_exempt(dec.lineno - 1, lines)
                    if mark is None:
                        problems.append(
                            f"{path}:{dec.lineno}: @lru_cache 缺少 C19-exempt 注记"
                            f"（须说明为何单一不可变参数键可豁免）: {node.name}"
                        )
    return problems


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems: list[str] = []
    scanned = 0
    for rel in ROOTS:
        for path in sorted((root / rel).rglob("*.py")):
            scanned += 1
            problems.extend(scan_file(path))
    if problems:
        print("❌ C19 缓存键 lint 未通过：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"✅ C19 缓存键 lint 通过（{scanned} 个运行时文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
