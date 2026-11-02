#!/usr/bin/env python3
"""宣称核对器：把「另一会话/汇报声称已落地」的每一项变成可复跑的机器核对。

为什么存在
----------
2026-11-02 深夜核对 Q-020/Q-021 时，用 shell ``grep -rn "A\\|B"`` 得到空输出，
差一点据此写出「宣称与树不一致」。事后对照实验查明真相：

- 本沙箱的 ``grep`` 是 **toybox 0.8.13**（不是 GNU grep，也不是 BSD grep）；
- toybox 的 BRE **不支持 ``\\|`` 交替**，模式 ``A\\|B`` 被当作字面量 "A|B"；
- 于是**静默零匹配**——不报错、不提示，看起来就像"不存在"。

（全仓 .py 无 NUL 字节、无非法 UTF-8——最初"文件被判二进制"的诊断是错的。）

本脚本的存在意义：存在性核对一律走 Python 遍历，输出
「宣称 → 实际路径 → 用例名 → 结果」四列，可复跑、可归档。

用法::

    python tools/verify_claims.py            # 打印四列表格
    python tools/verify_claims.py --out PATH # 同上并写 markdown 文件
    python tools/verify_claims.py --demo     # 额外演示 BRE \\| 陷阱（应显示假阴性）

退出码：全部宣称核实 = 0；任一未核实 = 1。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VENV_PY = REPO / ".venv" / "bin" / "python"


@dataclass
class ClaimResult:
    claim_id: str
    claim: str
    actual_paths: list[str]
    test_names: list[str]
    passed: bool
    note: str = ""


@dataclass
class Claim:
    claim_id: str
    claim: str
    check: object  # Callable[[], ClaimResult]


def _run_pytest_collect_and_run(test_file: Path) -> tuple[list[str], bool]:
    """跑单个测试文件，返回 (用例全名列表, 全部通过)。用 junitxml 取权威结论。"""
    junit = Path("/tmp") / f"verify-claims-{test_file.stem}.xml"
    cmd = [
        str(VENV_PY), "-m", "pytest", str(test_file), "-q",
        f"--junitxml={junit}",
    ]
    env_path = ":".join(
        [str(REPO / d) for d in (
            "core-time/src", "core-symbol/src", "core-rule/src",
            "core-eval/src", "app-zeri/src",
        )] + [str(REPO)]
    )
    import os

    env = dict(os.environ, PYTHONPATH=env_path)
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
    names: list[str] = []
    failures = 0
    if junit.exists():
        ts = ET.parse(junit).getroot().find("testsuite")
        for tc in ts.iter("testcase"):
            names.append(f"{tc.attrib['classname']}::{tc.attrib['name']}")
            if tc.find("failure") is not None or tc.find("error") is not None:
                failures += 1
    return names, proc.returncode == 0 and failures == 0


def check_q020() -> ClaimResult:
    """Q-020「三煞范围已上锁」：TestSanshaScope 存在且 4 例全过。"""
    f = REPO / "tests/unit/test_paipan_fixed.py"
    text = f.read_text(encoding="utf-8")
    present = "class TestSanshaScope" in text
    names, all_pass = _run_pytest_collect_and_run(f)
    scope_tests = [n for n in names if "TestSanshaScope" in n]
    return ClaimResult(
        claim_id="Q-020",
        claim="三煞范围已上锁（TestSanshaScope，含「壬山不算三煞」）",
        actual_paths=[str(f.relative_to(REPO))] if present else [],
        test_names=scope_tests,
        passed=present and bool(scope_tests) and all_pass,
        note=f"该文件共 {len(names)} 例全部通过={all_pass}",
    )


def check_q021() -> ClaimResult:
    """Q-021「兼向已解耦为数值口径」：jianxiang.yaml 两口径 + TestJianxiangCaliber。"""
    y = REPO / "core-rule/config/calibers/jianxiang.yaml"
    f = REPO / "tests/unit/test_paipan_fixed.py"
    yaml_ok = False
    detail = ""
    if y.exists():
        import yaml

        data = yaml.safe_load(y.read_text(encoding="utf-8")) or {}
        calibers = data.get("calibers") or {}
        has_threshold = any(
            (spec.get("params") or {}).get("threshold_deg") is not None
            for spec in calibers.values()
        )
        caliber_count = len(calibers)
        yaml_ok = has_threshold and caliber_count >= 2
        detail = f"threshold_deg={has_threshold}, 口径数={caliber_count}"
    names, all_pass = _run_pytest_collect_and_run(f)
    jx_tests = [n for n in names if "TestJianxiangCaliber" in n]
    return ClaimResult(
        claim_id="Q-021",
        claim="兼向已解耦为数值口径（jianxiang.yaml + TestJianxiangCaliber）",
        actual_paths=[str(y.relative_to(REPO))] if y.exists() else [],
        test_names=jx_tests,
        passed=yaml_ok and bool(jx_tests) and all_pass,
        note=detail or "jianxiang.yaml 不存在",
    )


CLAIMS: list[Claim] = [
    Claim("Q-020", "三煞范围已上锁", check_q020),
    Claim("Q-021", "兼向已解耦为数值口径", check_q021),
]


def demo_grep_trap() -> list[str]:
    """演示 BRE ``\\|`` 陷阱：同一目录，``\\|`` 静默零匹配，``-E`` 正常命中。"""
    lines = ["## 附录：BRE `\\|` 陷阱演示（toybox grep，可复跑）", ""]
    tests_dir = REPO / "tests"
    bre = subprocess.run(
        ["grep", "-rla", "TestSanshaScope\\|jianxiang", str(tests_dir)],
        capture_output=True, text=True,
    )
    ext = subprocess.run(
        ["grep", "-rlaE", "TestSanshaScope|jianxiang", str(tests_dir)],
        capture_output=True, text=True,
    )
    ver = subprocess.run(["grep", "--version"], capture_output=True, text=True)
    lines.append(f"- grep 实现：`{ver.stdout.strip().splitlines()[0] if ver.stdout else '?'}`")
    lines.append(f"- BRE `A\\|B`：命中 {len(bre.stdout.splitlines())} 个文件（**静默零匹配 = 假阴性**）")
    lines.append(f"- `-E 'A|B'`：命中 {len(ext.stdout.splitlines())} 个文件（正确）")
    lines.append("")
    lines.append("**纪律：交替模式必须 `grep -E \"A|B\"` 或 Python 遍历；`\\|` 在 toybox/BSD grep 下静默零匹配。**")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=None, help="把四列表格写成 markdown")
    ap.add_argument("--demo", action="store_true", help="附加 BRE 陷阱演示")
    args = ap.parse_args()

    results = [c.check() for c in CLAIMS]

    lines = ["# 宣称核对（tools/verify_claims.py 可复跑输出）", ""]
    lines.append("| 宣称 | 实际路径 | 用例名 | 结果 |")
    lines.append("|---|---|---|---|")
    for r in results:
        paths = "<br>".join(f"`{p}`" for p in r.actual_paths) or "—"
        tests = "<br>".join(f"`{t}`" for t in r.test_names) or "—"
        verdict = "✅ 属实" if r.passed else "❌ 未核实"
        note = f"（{r.note}）" if r.note else ""
        lines.append(f"| {r.claim_id} {r.claim} {note} | {paths} | {tests} | {verdict} |")
    lines.append("")

    if args.demo:
        lines.extend(demo_grep_trap())

    text = "\n".join(lines)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"\n[written] {args.out}", file=sys.stderr)
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
