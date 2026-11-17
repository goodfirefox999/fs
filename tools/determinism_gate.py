#!/usr/bin/env python3
"""确定性门禁的 CI 适配层：**三态**（pass / violation / undetermined）。

为什么需要适配层
----------------
``tools/determinism_probe.py --gate`` 的退出码是判据（0/1/2/3），但 CI 只认 0/非 0。
三态口径（2026-11-04 第五层）把「判不了」从「通过」里拆出来：

- 0：通过；
- 1（PRODUCT_FAIL）：硬违规，必须阻断；
- 3（OUTPUT_FAIL）/ 2（ENV_SUSPECT）/ 未知码：**无法判定**，返回 4，
  写 ``out/output-fail.flag`` 并交由 ``tools/gate_verdict.py`` 汇总进
  ``out/undetermined.json``。不得再降级为 0——「带警告通过」就是静默绿。

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

__all__ = ["ADAPTER_ENV", "FLAG_NAME", "EXIT_UNDETERMINED", "arbitrate", "main"]

#: 三态门禁的「无法判定」退出码（与 gate_verdict 共用）。
EXIT_UNDETERMINED = 4


def flag_path(out_dir: Path | str) -> Path:
    return Path(out_dir) / FLAG_NAME


def arbitrate(probe_rc: int, stdout: str, stderr: str, out_dir: Path | str) -> int:
    """把探针退出码翻译成三态处置。**只放行 0；3/2/未知码一律无法判定。**"""
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
            "disposition": "undetermined",
        }
        flag.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if stderr.strip():
            print(stderr.strip(), file=sys.stderr)
        print(
            "⚠️  UNDETERMINED（OUTPUT_FAIL）：决策一致但报告文本跨进程不稳定。\n"
            f"   已写 {flag}；本次不是全绿，退出码 {EXIT_UNDETERMINED}，"
            "由 gate_verdict 汇总进 out/undetermined.json。",
            file=sys.stderr,
        )
        return EXIT_UNDETERMINED

    if probe_rc == 0:
        if stdout.strip():
            print(stdout.strip())
        return 0

    if probe_rc == 1:
        print("❌ 确定性门禁阻断：PRODUCT_FAIL（决策面）", file=sys.stderr)
        if stderr.strip():
            print(stderr.strip(), file=sys.stderr)
        return 1

    label = "ENV_SUSPECT（机器忙）" if probe_rc == 2 else f"未知退出码 {probe_rc}"
    print(
        f"⚠️  UNDETERMINED：{label}——本次无法判定，不是通过。\n"
        "   按 AGENTS.md 约束 11 做调用方式对照实验并重跑；"
        f"退出码 {EXIT_UNDETERMINED}。",
        file=sys.stderr,
    )
    return EXIT_UNDETERMINED


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
        print(
            f"⚠️  UNDETERMINED：确定性探针超时（>{args.timeout}s），"
            f"退出码 {EXIT_UNDETERMINED}。\n   {exc}",
            file=sys.stderr,
        )
        return EXIT_UNDETERMINED
    except OSError as exc:
        print(
            f"⚠️  UNDETERMINED：无法启动确定性探针（{exc}），退出码 {EXIT_UNDETERMINED}。",
            file=sys.stderr,
        )
        return EXIT_UNDETERMINED

    return arbitrate(proc.returncode, proc.stdout, proc.stderr, args.out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
