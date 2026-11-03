#!/usr/bin/env python3
"""历史重写链的逐 SHA 独立验证（把 2026-11-03 的手工四步固化成机器门禁）。

为什么必须存在
--------------
重写历史后「tip 绿」不等于「链上每个提交检出后都绿」——bisect 的价值恰恰建立在
后者上。本轮重写时片1 就藏着一条「单独检出必红」的仓库级断言，靠逐 SHA 验证才抓到。
本脚本把那次的手工流程固化：对 ``<base>..<tip>`` 的**每一个** SHA 建临时 worktree、
跑测试（junitxml 权威数字）、断言 0 fail / 0 error，汇总成表，任何一档红即退出码 1。

用法::

    python tools/verify_rewrite_chain.py --base 64f5be5 --tip main
    python tools/verify_rewrite_chain.py --base 64f5be5 --tip HEAD --with-lint

说明：
- 每个 SHA 各建独立 worktree（不碰主工作区，避免 worktree_guard 误报脏状态）；
- 测试固定 ``-m "not slow"``（与 make test-fast 同口径）+ ``--junitxml``（AGENTS
  约束第 10 条：本沙箱 ``-q`` 下 pytest 汇总行不可见，XML 是唯一权威数字来源）；
- ``--with-lint`` 同时跑 ``rules lint``；
- SOP 全文见 ``docs/research/history-rewrite-sop.md``。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = REPO / ".venv" / "bin" / "python"
ENV_PATH = ":".join(
    str(REPO / d) for d in (
        "core-time/src", "core-symbol/src", "core-rule/src",
        "core-eval/src", "app-zeri/src",
    )
) + f":{REPO}"


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(list(args), cwd=cwd, capture_output=True, text=True)


def shas_between(base: str, tip: str) -> list[str]:
    r = sh("git", "rev-list", "--reverse", f"{base}..{tip}", cwd=REPO)
    if r.returncode != 0:
        raise SystemExit(f"rev-list 失败：{r.stderr.strip()}")
    return r.stdout.split()


def short(sha: str) -> str:
    return sh("git", "log", "-1", "--format=%h %s", sha, cwd=REPO).stdout.strip()[:60]


def verify_sha(sha: str, workroot: Path, with_lint: bool) -> tuple[bool, str]:
    import os

    wt = workroot / sha[:10]
    # 防御：上次被 SIGKILL 打断会留下残留 worktree（fatal: already exists）
    if wt.exists():
        sh("git", "worktree", "remove", "--force", str(wt), cwd=REPO)
        import shutil

        shutil.rmtree(wt, ignore_errors=True)
    up = sh("git", "worktree", "add", "--detach", str(wt), sha, cwd=REPO)
    if up.returncode != 0:
        return False, f"worktree 创建失败：{up.stderr.strip()[-120:]}"
    try:
        junit = workroot / f"junit-{sha[:10]}.xml"
        env_args = ["--junitxml", str(junit)]
        env = dict(os.environ, PYTHONPATH=ENV_PATH)  # worktree 无 PYTHONPATH 时收不到包
        r = subprocess.run(
            [str(PY), "-m", "pytest", "-m", "not slow", *env_args, "-p", "no:cacheprovider"],
            cwd=wt, capture_output=True, text=True, env=env,
        )
        if not junit.exists():
            return False, f"junitxml 未生成（pytest 退出码 {r.returncode}）{r.stderr.strip()[-120:]}"
        ts = ET.parse(junit).getroot().find("testsuite")
        a = ts.attrib
        n, f, e = int(a["tests"]), int(a["failures"]), int(a["errors"])
        ok = r.returncode == 0 and f == 0 and e == 0 and n > 0
        detail = f"{n} passed / {f} failed / {e} errors in {float(a['time']):.1f}s"
        if with_lint and ok:
            lr = subprocess.run(
                [str(PY), "-m", "app_zeri.cli", "rules", "lint"],
                cwd=wt, capture_output=True, text=True, env=env,
            )
            ok = lr.returncode == 0
            tail = [ln for ln in lr.stdout.splitlines() if ln.strip()][-1:]
            detail += f"；lint={'通过' if ok else (tail[0] if tail else '失败')}"
        return ok, detail
    finally:
        sh("git", "worktree", "remove", "--force", str(wt), cwd=REPO)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base", required=True, help="链基底（不含），如 64f5be5")
    ap.add_argument("--tip", required=True, help="链终点（含），如 main")
    ap.add_argument("--with-lint", action="store_true")
    args = ap.parse_args()

    shas = shas_between(args.base, args.tip)
    if not shas:
        print(f"[warn] {args.base}..{args.tip} 为空区间")
        return 2
    workroot = REPO.parent / ".rewrite-verify"
    workroot.mkdir(parents=True, exist_ok=True)

    print(f"验证 {args.base}..{args.tip}（{len(shas)} 个 SHA，junitxml 为权威数字）\n")
    all_ok = True
    for sha in shas:
        ok, detail = verify_sha(sha, workroot, args.with_lint)
        all_ok &= ok
        print(f"{'✅' if ok else '❌'} {sha[:8]}  {short(sha)}\n   {detail}")
    subprocess.run(["git", "worktree", "prune"], cwd=REPO, capture_output=True)
    print(f"\n结论：{'全链逐 SHA 独立绿' if all_ok else '存在红档，禁止 push/合并'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
