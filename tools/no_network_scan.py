"""CI 门禁：扫描运行时代码中的网络依赖（禁止联网 / 外部 API / 大模型调用）。

允许的例外：测试与工具脚本（``tests/``、``tools/``、``cases/``）可读本地文件；
**运行时代码**（``*/src/**``）不得出现网络客户端导入或 HTTP 调用。
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FORBIDDEN_MODULES = {
    "requests", "httpx", "urllib3", "aiohttp", "websockets", "socket",
    "http.client", "urllib.request", "ftplib", "smtplib", "telnetlib",
    "openai", "anthropic", "google.generativeai", "dashscope",
}
FORBIDDEN_CALLS = {"urlopen", "urlretrieve", "socket.socket"}

ROOTS = ["core-time/src", "core-symbol/src", "core-rule/src", "core-eval/src", "app-zeri/src"]


def scan_file(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:  # pragma: no cover
        return [f"{path}: 语法错误 {exc}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in FORBIDDEN_MODULES or alias.name.split(".")[0] in {
                    m.split(".")[0] for m in FORBIDDEN_MODULES
                }:
                    problems.append(f"{path}:{node.lineno}: 禁止导入网络模块 {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module in FORBIDDEN_MODULES or node.module.split(".")[0] in {
                m.split(".")[0] for m in FORBIDDEN_MODULES
            }:
                problems.append(f"{path}:{node.lineno}: 禁止导入网络模块 {node.module}")
        elif isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name in FORBIDDEN_CALLS:
                problems.append(f"{path}:{node.lineno}: 禁止调用 {name}")
    return problems


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    problems: list[str] = []
    scanned = 0
    for rel in ROOTS:
        for path in (root / rel).rglob("*.py"):
            scanned += 1
            problems.extend(scan_file(path))
    if problems:
        print("❌ 检测到运行时代码的网络依赖：")
        for p in problems:
            print(f"  - {p}")
        print("\n依据：docs/DEVELOPMENT.md 硬禁止第 5 条（运行时联网 / 调用大模型 API）。")
        return 1
    print(f"✅ 无网络依赖扫描通过（{scanned} 个运行时文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
