"""工作区守卫：提交前把"谁改了哪些文件"摆到台面上。

背景（2026-11-02 并发写入事故）
------------------------------
Phase 11 执行期间，同一工作区有第二个 agent 在写 `huangdao.py`/`jianchu.py`，
并改了 `__init__.py`/`shensha.py`/`mountain.py`。合并后测试全绿——但那只是
"两边改动恰好不冲突"，不是"没有风险"。真实风险有三：

1. 未提交的他人改动被顺手 `git add -A` 裹进自己的 commit；
2. 对方基于旧版本写文件，产生**语法通过、逻辑冲突**的实现（本项目已出现：
   两套五黄命中粒度并存）；
3. 审计链断裂——报告里的 `input_hash` 只覆盖输入，不覆盖"哪一版工作树"。

用法
----
    python tools/worktree_guard.py                  # 列出改动，非白名单只警告（exit 0）
    python tools/worktree_guard.py --strict         # 非白名单即 exit 1（pre-commit 用）
    python tools/worktree_guard.py --allow "core-symbol/*" --allow "tests/*"

    # 作为 pre-commit 钩子（可选，需人工安装）：
    ln -sf ../../tools/worktree_guard.py .git/hooks/pre-commit

设计约束
--------
- 只读 `git status`，不写文件、不改索引；**不自动 add/commit**。
- 白名单用 fnmatch 通配，路径相对仓库根。
- 无 git 仓库时直接退出 0（避免把工具拷到别处就崩）。
"""

from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from pathlib import Path

__all__ = ["status_entries", "classify", "main"]

ROOT = Path(__file__).resolve().parents[1]

#: 生成物/缓存，永远不需要人工确认
NOISE_PATTERNS: tuple[str, ...] = (
    "*.pyc",
    "*/__pycache__/*",
    "tests/.tmp/*",
    "out/*",
    ".pytest_cache/*",
    ".ruff_cache/*",
    ".hypothesis/*",
    ".coverage",
    "tests/bench/bench_history.jsonl",
)


def _run_git(args: list[str]) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git 调用失败")
    return proc.stdout


def status_entries() -> list[tuple[str, str]]:
    """返回 ``[(状态, 路径)]``；状态取 porcelain 的两字符码（如 `` M`` / ``??``）。"""
    out: list[tuple[str, str]] = []
    for line in _run_git(["status", "--porcelain=v1"]).splitlines():
        if not line.strip():
            continue
        code, path = line[:2], line[3:].strip()
        if " -> " in path:  # 重命名：取新路径
            path = path.split(" -> ", 1)[1]
        out.append((code, path))
    return out


def _is_noise(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in NOISE_PATTERNS)


def _is_allowed(path: str, allow: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in allow)


def classify(
    entries: list[tuple[str, str]], allow: list[str]
) -> dict[str, list[str]]:
    """把改动分成 噪声 / 白名单 / 需确认 三组（纯函数，便于测试）。"""
    buckets: dict[str, list[str]] = {"noise": [], "allowed": [], "review": []}
    for _code, path in entries:
        if _is_noise(path):
            buckets["noise"].append(path)
        elif _is_allowed(path, allow):
            buckets["allowed"].append(path)
        else:
            buckets["review"].append(path)
    return buckets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="提交前工作区守卫（只读 git status）")
    parser.add_argument("--allow", action="append", default=[], help="白名单通配，可重复")
    parser.add_argument("--strict", action="store_true", help="非白名单即返回 1")
    parser.add_argument("--quiet", action="store_true", help="只输出摘要")
    args = parser.parse_args(argv)

    try:
        entries = status_entries()
    except RuntimeError as exc:
        print(f"跳过：{exc}")
        return 0

    buckets = classify(entries, args.allow)
    review = buckets["review"]

    if not args.quiet:
        for label, key in (("噪声（生成物/缓存）", "noise"), ("白名单", "allowed")):
            if buckets[key]:
                print(f"\n{label}：{len(buckets[key])} 个")
                for path in sorted(buckets[key]):
                    print(f"  · {path}")
        if review:
            print(f"\n⚠️  需人工确认：{len(review)} 个")
            for path in sorted(review):
                print(f"  · {path}")

    total = len(entries)
    if review:
        print(
            f"\n合计 {total} 项改动，其中 {len(review)} 项不在白名单。"
            "\n提示：提交前确认这些改动是否属于本次任务；"
            "并发会话写入的文件不应被 `git add -A` 裹进本次 commit。"
        )
        return 1 if args.strict else 0
    print(f"\n合计 {total} 项改动，全部在噪声/白名单内。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
