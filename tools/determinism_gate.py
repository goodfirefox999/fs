#!/usr/bin/env python3
"""确定性门禁的 CI 适配层：决策面阻断，输出面「带警告通过」。

为什么需要适配层
----------------
``tools/determinism_probe.py --gate`` 的退出码是判据（0/1/2/3），但 CI 只认 0/非 0：

- 若把 3 直接暴露给 make/CI，它会被当成普通失败，「可带警告发布」无法实现；
- 若吞掉所有非 0，1（产品坏）和 2（机器忙）也会被一起放过。

因此本工具**只降级 3**，并把「无声」变成可机查的 flag。

CI 口径（AGENTS.md 确定性门禁第 15 条，方案 1）
------------------------------------------------
=====  ============================================================
退出码  处置
=====  ============================================================
0      通过，清理旧 flag
3      写 ``out/output-fail.flag``（JSON），打印 ⚠️，返回 0（带警告通过）
1      原样返回（阻断）
2      原样返回（阻断，先查环境/重跑）
其他   按 2 处理（门禁自身异常，先排除调用方式）
=====  ============================================================

``make determinism`` 仍走原始探针（3 就是 3），供人工复核；只有 ``make gate``
使用本适配层。这样「原始判据」和「CI 处置」是两件事，不会互相污染。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "tools" / "determinism_probe.py"
FLAG_NAME = "output-fail.flag"
#: 与 tools/determinism_probe.py 的 ADAPTER_ENV 保持一致；只有本适配层可以置位。
ADAPTER_ENV = "ZERI_DETERMINISM_ADAPTER"

__all__ = ["ADAPTER_ENV", "FLAG_NAME", "arbitrate", "main"]


def flag_path(out_dir: Path | str) -> Path:
    return Path(out_dir) / FLAG_NAME


def arbitrate(probe_rc: int, stdout: str, stderr: str, out_dir: Path | str) -> int:
    """把探针退出码翻译成 CI 处置。**只降级 3**。"""
    flag = flag_path(out_dir)
    # 每次先清理旧 flag：否则上一次的 OUTPUT_FAIL 会贴到这一次的成功/产品失败上。
    flag.unlink(missing_ok=True)

    if probe_rc == 3:
        flag.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "kind": "OUTPUT_FAIL",
            "probe_rc": 3,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "probe_stdout": stdout[-4000:],
            "probe_stderr": stderr[-4000:],
            "disposition": "warn-and-pass",
        }
        flag.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if stderr.strip():
            print(stderr.strip(), file=sys.stderr)
        print(
            "⚠️  OUTPUT_FAIL（输出面）：决策一致但报告文本跨进程不稳定。\n"
            f"   已写 {flag}（机器可查）；本次按「带警告通过」处理，不得当作全绿。\n"
            "   人工复核后用 --level output --verbose 定位是 reasons 还是 conflicts 先漂。",
            file=sys.stderr,
        )
        return 0

    if probe_rc == 0:
        if stdout.strip():
            print(stdout.strip())
        return 0

    if probe_rc in (1, 2):
        label = "PRODUCT_FAIL（决策面）" if probe_rc == 1 else "ENV_SUSPECT（机器忙）"
        print(f"❌ 确定性门禁阻断：{label}", file=sys.stderr)
        if stderr.strip():
            print(stderr.strip(), file=sys.stderr)
        return probe_rc

    print(
        f"❌ 确定性门禁异常：探针返回未知退出码 {probe_rc}，按 ENV_SUSPECT(2) 处理。\n"
        "   先按 AGENTS.md 约束 11 做调用方式对照实验，再怀疑产品。",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="确定性门禁 CI 适配层（只降级 OUTPUT_FAIL）")
    parser.add_argument("--seeds", default="0,1,2,3", help="传给探针 --gate 的 seed 列表")
    parser.add_argument("--out-dir", default=str(ROOT / "out"), help="flag 输出目录（默认 out/）")
    parser.add_argument("--timeout", type=int, default=1800, help="探针子进程超时秒数")
    args = parser.parse_args(argv)

    # 先清旧 flag：即使探针超时/崩溃，也不能让上一次的 OUTPUT_FAIL 贴到这一次。
    flag_path(args.out_dir).unlink(missing_ok=True)

    env = os.environ.copy()
    env[ADAPTER_ENV] = "1"  # 放行探针的 CI 防绕过检查；只在本适配层内生效
    try:
        proc = subprocess.run(
            [sys.executable, str(PROBE), "--gate", args.seeds],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            env=env,
            timeout=args.timeout,
        )
    except subprocess.TimeoutExpired as exc:
        print(f"❌ 确定性探针超时（>{args.timeout}s）：按 ENV_SUSPECT(2) 处理。\n   {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"❌ 无法启动确定性探针：{exc}", file=sys.stderr)
        return 2

    return arbitrate(proc.returncode, proc.stdout, proc.stderr, args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
