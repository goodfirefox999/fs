#!/usr/bin/env python3
"""把 ``out/junit-*.xml`` 汇总成 GitHub Step Summary——**失败项不能只活在 job log**。

事故形态（run #33）：slow bench 两次 9.02s / 9.36s 超出 9.0s 档，job 红；
但 Step Summary 只有 ``perf_smoke_seconds: 1.33``（冒烟通过），看 summary 的人
得到的是「冒烟明明过了怎么还红」。失败项被埋在 log 里，等于没有汇总。

做法：扫描目录下所有 junit 文件，逐个出「passed / failed / errors / skipped +
耗时 + 判定」行，再把每个 failure/error 的用例名、耗时、首行消息列出来。
没有 junit 产物时明确写「测试可能没跑」，不输出空白页。

用法::

    python tools/ci_summary.py --dir out >> "$GITHUB_STEP_SUMMARY"

本工具只做汇总，不改变退出码：阻断点仍是各自的测试/门禁步骤。
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

__all__ = ["collect", "render"]


def _case_name(case: ET.Element) -> str:
    return "::".join(part for part in (case.get("classname"), case.get("name")) if part) or "(未命名)"


def _first_line(text: str | None) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return "(无消息)"


def _suite(path: Path) -> dict:
    """解析单个 junit；损坏/缺失也返回一条可见记录，不静默跳过。"""
    record: dict = {"file": path.name, "error": None}
    if not path.exists():
        record["error"] = "文件不存在"
        return record
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        record["error"] = f"XML 损坏（{exc}）"
        return record
    ts = root.find("testsuite")
    if ts is None:
        record["error"] = "无 testsuite 节点"
        return record
    attr = ts.attrib
    tests, failures, errors, skipped = (
        int(attr.get(key, 0)) for key in ("tests", "failures", "errors", "skipped")
    )
    record.update(
        tests=tests,
        passed=tests - failures - errors - skipped,
        failed=failures,
        errors=errors,
        skipped=skipped,
        time=float(attr.get("time", 0) or 0),
    )
    record["ok"] = failures == 0 and errors == 0 and record["passed"] > 0
    failures_out: list[str] = []
    for case in root.iter("testcase"):
        for tag in ("failure", "error"):
            node = case.find(tag)
            if node is None:
                continue
            message = node.get("message") or node.text
            failures_out.append(
                f"- `{_case_name(case)}`（{float(case.get('time', 0) or 0):.2f}s）：{_first_line(message)}"
            )
    record["failure_details"] = failures_out
    skips: list[str] = []
    for case in root.iter("testcase"):
        node = case.find("skipped")
        if node is None:
            continue
        reason = node.get("message") or node.get("type") or "(无原因)"
        skips.append(f"- `{_case_name(case)}`：{reason}")
    record["skip_details"] = skips
    return record


def collect(directory: Path) -> list[dict]:
    return [_suite(path) for path in sorted(directory.glob("junit-*.xml"))]


def render(records: list[dict]) -> str:
    lines = ["## CI 测试汇总", ""]
    if not records:
        lines.append(
            "⚠️ 未找到任何 junit 产物（`out/junit-*.xml`）——测试可能没跑或提前退出。"
            "本页不是绿色证明，请先看 job log 的失败步骤。"
        )
        return "\n".join(lines)

    lines.append("| 套件 | passed | failed | errors | skipped | 耗时 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    for record in records:
        if record.get("error"):
            lines.append(f"| `{record['file']}` | - | - | - | - | - | ❌ {record['error']} |")
            continue
        verdict = "✅" if record["ok"] else "❌"
        lines.append(
            f"| `{record['file']}` | {record['passed']} | {record['failed']} | "
            f"{record['errors']} | {record['skipped']} | {record['time']:.1f}s | {verdict} |"
        )

    failures = [
        (record["file"], detail)
        for record in records
        for detail in record.get("failure_details", [])
    ]
    lines += ["", "### 失败项" if failures else "### 失败项：无"]
    if failures:
        for file, detail in failures:
            lines.append(f"- {detail}（{file}）")
    else:
        lines.append("无 failed / errors。")

    skips = [(record["file"], detail) for record in records for detail in record.get("skip_details", [])]
    if skips:
        lines += ["", "### 跳过项（非 pass）"]
        for file, detail in skips:
            lines.append(f"- {detail}（{file}）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="汇总 out/junit-*.xml 为 GitHub Step Summary")
    parser.add_argument("--dir", default="out", help="junit 产物目录（默认 out）")
    args = parser.parse_args(argv)
    print(render(collect(Path(args.dir))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
