#!/usr/bin/env python3
"""校验 GitHub workflow YAML 的语法（不校验 GitHub 语义）。

背景（2026-11-03 评审八回路）
-----------------------------
修复了一处 ``C19:`` 步骤名未加引号导致的无效 YAML。修一个不等于全文件合法：
YAML 的 ``key: value`` 里只要 value 含 ``: ``，就可能被解析成嵌套映射或直接
报错。这里对 ``.github/workflows/*.yml`` 做一次全文件 ``yaml.safe_load``，
让「修了某一个」变成「所有 workflow 都过语法检查」。

为什么不覆盖 ``core-rule/config/*.yaml`` 与 ``calibers/*.yaml``（2026-11-03 确认）：
这些文件**有运行时 loader**，语法坏了会当场报错，不需要第二遍语法检查——
``school_policy`` / ``task_kinds`` / ``required_rules`` / ``consensus`` /
``calibers`` 由 ``core_rule.default_registry()`` 在 ``make lint`` 中 ``safe_load``，
``rules_manifest`` / ``coverage_gaps`` 由 ``rules lint`` 读取，
``dead_rule_baseline`` 由 ``tools/dead_rule_scan.py`` 读取，``verdict_baseline``
由 ``tests/unit/test_verdict_baseline.py`` 读取；这两个测试都没有 ``slow`` 标记，
在 ``make test-fast`` 与 ``make cov`` 的 ``-m 'not slow'`` 里都会跑，不存在
「只在全量测试才校验」的窗口。而 workflow YAML **没有 loader 读**：
写坏了 GitHub 只是不跑，没有任何错误输出——所以这里只管它。

用法::

    python tools/check_yaml.py
    python tools/check_yaml.py .github/workflows/ci.yml path/to/other.yml

退出码：0 = 全部可解析；1 = 至少一个文件解析失败或没有可检查的文件。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOB = ".github/workflows/*.y*ml"

__all__ = ["check", "default_paths", "main"]


def default_paths() -> list[Path]:
    return sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))


def check(paths: list[Path]) -> list[str]:
    """返回错误列表；空列表表示全部通过。"""
    errors: list[str] = []
    if not paths:
        return ["没有找到可校验的 YAML 文件"]
    for path in paths:
        display = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        try:
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
        except OSError as exc:
            errors.append(f"{display}: 无法读取：{exc}")
            continue
        except yaml.YAMLError as exc:
            errors.append(f"{display}: YAML 语法错误：{exc}")
            continue
        if data is None:
            errors.append(f"{display}: 空文件（至少应有一个顶层键）")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="校验 GitHub workflow YAML 语法")
    parser.add_argument(
        "paths",
        nargs="*",
        help=f"要检查的文件（默认 {DEFAULT_GLOB}）",
    )
    args = parser.parse_args(argv)

    paths = [Path(p) for p in args.paths] if args.paths else default_paths()
    errors = check(paths)
    if errors:
        print("❌ YAML 校验失败：", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    for path in paths:
        display = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        print(f"✅ {display}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
