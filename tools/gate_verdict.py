#!/usr/bin/env python3
"""门禁三态汇总：pass / violation / undetermined。

口径（2026-11-04 第五层）
------------------------
- **pass（0）**：所有门禁步骤通过，且没有跳过/缺失/无法判定项；
- **violation（1）**：出现硬失败（测试 failed/errors、确定性 PRODUCT_FAIL 等）；
- **undetermined（4）**：没有硬失败，但存在「判不了」——pytest skip、
  determinism OUTPUT_FAIL / ENV_SUSPECT、junit 缺失或损坏、未登记套件。

关键约束：**skip 不算 pass**。旧口径把 skip 计入 passed，再用「全部通过」
盖过去，正是「没检查所以没红」。本工具把每一项无法判定写进
``out/undetermined.json``（CI 必须上传），并让 ``make gate`` 以 4 退出；
CI 对 4 不阻断，但 Step Summary 首行必须写明「本次有 N 项无法判定」。

用法::

    python tools/gate_verdict.py --scope local        # make gate
    python tools/gate_verdict.py --scope ci           # CI（含 bench 套件）
    python tools/gate_verdict.py --determinism-rc 0   # 单测：跳过真实探针
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DETERMINISM_GATE = ROOT / "tools" / "determinism_gate.py"
UNDETERMINED_NAME = "undetermined.json"

PASS = 0
VIOLATION = 1
UNDETERMINED = 4

__all__ = [
    "PASS",
    "VIOLATION",
    "UNDETERMINED",
    "UNDETERMINED_NAME",
    "classify_junit",
    "classify_determinism",
    "run",
    "main",
]


def _ci_summary():
    """按路径加载 tools/ci_summary.py（tools 不是 Python 包）。"""
    spec = importlib.util.spec_from_file_location(
        "ci_summary_for_gate", ROOT / "tools" / "ci_summary.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def classify_junit(directory: Path, *, scope: str) -> tuple[list[dict], list[dict]]:
    """把 junit 记录分类成 (violations, undetermined)，两类都不静默。"""
    ci = _ci_summary()
    expected = ci.local_expected() if scope == "local" else ci.EXPECTED_SUITES
    violations: list[dict] = []
    undetermined: list[dict] = []
    for record in ci.collect(directory, expected=expected, scope=scope):
        file = record["file"]
        if record.get("error"):
            undetermined.append(
                {"source": file, "kind": "missing_or_unreadable", "detail": record["error"]}
            )
            continue
        if record.get("missing_local"):
            undetermined.append(
                {"source": file, "kind": "missing_local", "detail": "本地未产出该套件（无法判定）"}
            )
            continue
        if record.get("unregistered"):
            undetermined.append(
                {"source": file, "kind": "unregistered_suite", "detail": record["unregistered"]}
            )
            continue
        if record["failed"] or record["errors"]:
            violations.append(
                {
                    "source": file,
                    "kind": "test_failure",
                    "detail": f"failed={record['failed']} errors={record['errors']}",
                }
            )
        if record["skipped"]:
            details = record.get("skip_details") or []
            detail = f"{record['skipped']} 个跳过（skip 不算 pass）"
            if details:
                # 只报数量会让验收无法逐项登记；用例名与原因必须落盘
                detail += "：" + "；".join(details)
            undetermined.append(
                {"source": file, "kind": "skipped", "detail": detail}
            )
        if record.get("undetermined"):
            undetermined.append(
                {
                    "source": file,
                    "kind": "undetermined",
                    "detail": f"{record['undetermined']} 项标记为无法判定",
                }
            )
    return violations, undetermined


def classify_determinism(
    out_dir: Path, *, rc: int, stderr: str = ""
) -> tuple[list[dict], list[dict]]:
    """确定性门禁三态：1=violation，4=undetermined，0=pass。"""
    if rc == 0:
        return [], []
    if rc == 1:
        return [
            {
                "source": "determinism",
                "kind": "product_fail",
                "detail": "PRODUCT_FAIL：不同 PYTHONHASHSEED 下决策指纹不一致",
            }
        ], []
    kind = "output_fail" if (out_dir / "output-fail.flag").exists() else "determinism_undetermined"
    return [], [
        {
            "source": "determinism",
            "kind": kind,
            "detail": (stderr.strip() or f"确定性探针退出码 {rc}")[-2000:],
        }
    ]


def _run_determinism(out_dir: Path, seeds: str, timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(DETERMINISM_GATE),
                "--out-dir",
                str(out_dir),
                "--seeds",
                seeds,
                "--timeout",
                str(timeout),
            ],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=timeout + 60,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return UNDETERMINED, f"无法执行确定性门禁：{exc}"
    if proc.stdout.strip():
        print(proc.stdout.strip())
    return proc.returncode, proc.stderr


def run(
    directory: Path,
    *,
    scope: str,
    determinism_rc: int,
    determinism_stderr: str = "",
) -> tuple[int, dict]:
    violations, undetermined = classify_junit(directory, scope=scope)
    det_violations, det_undetermined = classify_determinism(
        directory, rc=determinism_rc, stderr=determinism_stderr
    )
    violations += det_violations
    undetermined += det_undetermined

    verdict = "violation" if violations else ("undetermined" if undetermined else "pass")
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": scope,
        "verdict": verdict,
        "undetermined_count": len(undetermined),
        "violations": violations,
        "items": undetermined,
    }
    directory.mkdir(parents=True, exist_ok=True)
    (directory / UNDETERMINED_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if undetermined:
        print(f"本次有 {len(undetermined)} 项无法判定")
        for item in undetermined:
            print(f"  - [{item['kind']}] {item['source']}：{item['detail']}")
    else:
        print("本次无无法判定项")
    if violations:
        print(f"❌ 门禁违规 {len(violations)} 项（阻断）")
        for item in violations:
            print(f"  - [{item['kind']}] {item['source']}：{item['detail']}")

    rc = VIOLATION if violations else (UNDETERMINED if undetermined else PASS)
    print(
        f"门禁判定：{'violation' if rc == VIOLATION else 'undetermined' if rc == UNDETERMINED else 'pass'}"
        f"（退出码 {rc}）"
    )
    return rc, payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="门禁三态汇总（pass / violation / undetermined）")
    parser.add_argument("--dir", default=str(ROOT / "out"), help="junit 与 undetermined.json 的输出目录")
    parser.add_argument("--scope", choices=("local", "ci"), default="local")
    parser.add_argument("--seeds", default="0,1,2,3", help="传给确定性适配层的 seed 列表")
    parser.add_argument("--timeout", type=int, default=1800, help="确定性适配层超时秒数")
    parser.add_argument(
        "--determinism-rc",
        type=int,
        default=None,
        help="跳过真实确定性探针，直接采用给定退出码（仅单测用）",
    )
    args = parser.parse_args(argv)
    out_dir = Path(args.dir)
    if args.determinism_rc is None:
        det_rc, det_stderr = _run_determinism(out_dir, args.seeds, args.timeout)
    else:
        det_rc, det_stderr = args.determinism_rc, ""
    rc, _ = run(out_dir, scope=args.scope, determinism_rc=det_rc, determinism_stderr=det_stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
