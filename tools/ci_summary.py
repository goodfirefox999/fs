#!/usr/bin/env python3
"""把 ``out/junit-*.xml`` 汇总成 GitHub Step Summary——**失败项不能只活在 job log**。

事故形态（run #33）：slow bench 两次 9.02s / 9.36s 超出 9.0s 档，job 红；
但 Step Summary 只有 ``perf_smoke_seconds: 1.33``（冒烟通过），看 summary 的人
得到的是「冒烟明明过了怎么还红」。失败项被埋在 log 里，等于没有汇总。

做法：把「实际产物」与期望套件清单做**对称差**——期望有、产物没有报 ❌「缺失」，
产物有、期望没有报 ❌「未登记」，两个方向都不能静默。再逐个出「passed / failed /
errors / skipped + 耗时 + 判定」行，最后把每个 failure/error 的用例名、耗时、
首行消息列出来。没有 junit 产物时明确写「测试可能没跑」，不输出空白页。

用法::

    python tools/ci_summary.py --dir out >> "$GITHUB_STEP_SUMMARY"   # 默认 --scope ci
    python tools/ci_summary.py --dir out --scope local               # 本地调试

默认 ``--scope ci``（fail closed）：严格对称差——期望缺产物、产物未登记都报 ❌。
本地显式 ``--scope local``：只核对期望清单的缺失（以 ⚠️ 提示，未登记不报），
忽略 ``out/`` 里 test/golden 等历史遗留 junit——本地缺失不能静默，但也不能
把 CI 的严格口径变成天天出现的红灯。

本工具只做汇总，不改变退出码：阻断点仍是各自的测试/门禁步骤。
"""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path

__all__ = ["EXPECTED_SUITES", "collect", "render"]

# 期望套件清单 = CI 必须产出的 junit（cov 与 perf-smoke 来自 Makefile 的 cov 配方，
# bench 来自 ci.yml）。只靠 glob 扫目录有个盲区：bench 步骤提前挂掉时
# junit-bench.xml 根本不存在，它会从汇总表里消失、整页误显全绿——所以缺文件必须
# 显式成 ❌。反方向同样要报：workflow 新增第四个 junit 而忘了登记时，它不能
# 混进「全部通过」。两个方向都由 collect 的对称差处理；tests/unit/test_ci_summary.py
# 会解析 ci.yml 与 make cov 配方反查清单漂移。
EXPECTED_SUITES: dict[str, str] = {
    "cov": "junit-cov.xml",
    "bench": "junit-bench.xml",
    "perf-smoke": "junit-perf-smoke.xml",
}


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
                f"`{_case_name(case)}`（{float(case.get('time', 0) or 0):.2f}s）：{_first_line(message)}"
            )
    record["failure_details"] = failures_out
    skips: list[str] = []
    for case in root.iter("testcase"):
        node = case.find("skipped")
        if node is None:
            continue
        reason = node.get("message") or node.get("type") or "(无原因)"
        skips.append(f"`{_case_name(case)}`：{reason}")
    record["skip_details"] = skips
    return record


def collect(
    directory: Path,
    expected: dict[str, str] | None = EXPECTED_SUITES,
    scope: str = "ci",
) -> list[dict]:
    """按 scope 收集 junit；``expected=None`` 表示不按登记清单过滤（仅调试用）。

    - ``ci``（默认，fail closed）：严格对称差——期望缺产物报「缺失」，产物未登记
      报「未登记」。
    - ``local``：核对期望清单，缺失记为 ⚠️ 提示（本地未运行对应步骤时属正常）；
      未登记不报，忽略本地遗留的其它 junit。
    """
    if scope not in {"ci", "local"}:
        raise ValueError(f"未知 scope：{scope}（只支持 ci/local）")
    found = {path.name: path for path in sorted(directory.glob("junit-*.xml"))}
    if expected is None:
        return [_suite(path) for path in found.values()]
    if scope == "local":
        records: list[dict] = []
        for name in expected.values():
            if name in found:
                records.append(_suite(found[name]))
            else:
                records.append({"file": name, "missing_local": True})
        return records

    records = []
    for suite, name in expected.items():
        if name in found:
            records.append(_suite(found.pop(name)))
        else:
            records.append(
                {
                    "file": name,
                    "error": f"缺失：预期套件「{suite}」未产出 junit（该步骤可能提前失败或未执行）",
                }
            )
    for path in found.values():
        record = _suite(path)
        record["unregistered"] = (
            "未登记套件：产物存在但不在 EXPECTED_SUITES"
            "（新增套件须登记；本地历史 junit 请用 --scope local）"
        )
        records.append(record)
    return records


def render(records: list[dict], scope: str = "ci") -> str:
    lines = ["## CI 测试汇总", ""]
    if not records:
        lines.append(
            "⚠️ 未找到任何 junit 产物（`out/junit-*.xml`）——测试可能没跑或提前退出。"
            "本页不是绿色证明，请先看 job log 的失败步骤。"
        )
        return "\n".join(lines)

    missing = [record["file"] for record in records if record.get("error")]
    missing_local = [record["file"] for record in records if record.get("missing_local")]
    unregistered = [record["file"] for record in records if record.get("unregistered")]
    failed = [
        record["file"]
        for record in records
        if not record.get("error")
        and not record.get("missing_local")
        and not record.get("unregistered")
        and not record["ok"]
    ]
    if missing or failed or unregistered:
        reasons: list[str] = []
        if failed:
            reasons.append(f"{len(failed)} 个套件失败（{'、'.join(f'`{name}`' for name in failed)}）")
        if missing:
            reasons.append(
                f"{len(missing)} 个套件缺失或不可读（{'、'.join(f'`{name}`' for name in missing)}）"
            )
        if unregistered:
            reasons.append(
                f"{len(unregistered)} 个套件未登记（{'、'.join(f'`{name}`' for name in unregistered)}）"
            )
        lines.append(f"**判定：❌ {'；'.join(reasons)}——本页不是绿色证明。**")
    elif missing_local:
        lines.append(
            f"**判定：⚠️ 本地宽松模式：已核对缺失（{len(missing_local)} 个预期套件未产出，"
            "仅提示，本地未运行对应步骤时属正常），未核对未登记。**"
        )
    elif scope == "local":
        lines.append("**判定：✅ 本地宽松模式：已核对缺失（无缺失），未核对未登记。**")
    else:
        lines.append(f"**判定：✅ 全部 {len(records)} 个套件通过。**")
    lines.append("")

    lines.append("| 套件 | passed | failed | errors | skipped | 耗时 | 判定 |")
    lines.append("|---|---|---|---|---|---|---|")
    for record in records:
        if record.get("error"):
            lines.append(f"| `{record['file']}` | - | - | - | - | - | ❌ {record['error']} |")
            continue
        if record.get("missing_local"):
            lines.append(
                f"| `{record['file']}` | - | - | - | - | - | ⚠️ 缺失（本地未运行该步骤时属正常） |"
            )
            continue
        if record.get("unregistered"):
            verdict = "❌ 未登记"
        else:
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

    if missing_local:
        lines += ["", "### 本地缺失（仅提示，不阻断）"]
        for name in missing_local:
            lines.append(f"- `{name}`：本地未产出；若刚跑过对应步骤，请检查它是否失败。")

    unregistered_details = [
        (record["file"], record["unregistered"])
        for record in records
        if record.get("unregistered")
    ]
    if unregistered_details:
        lines += ["", "### 未登记套件（须登记到 EXPECTED_SUITES）"]
        for file, detail in unregistered_details:
            lines.append(f"- {detail}（{file}）")

    skips = [(record["file"], detail) for record in records for detail in record.get("skip_details", [])]
    if skips:
        lines += ["", "### 跳过项（非 pass）"]
        for file, detail in skips:
            lines.append(f"- {detail}（{file}）")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="汇总 out/junit-*.xml 为 GitHub Step Summary")
    parser.add_argument("--dir", default="out", help="junit 产物目录（默认 out）")
    parser.add_argument(
        "--scope",
        choices=("ci", "local"),
        default="ci",
        help="ci=严格对称差（默认，缺失/未登记都报）；local=宽松，缺失仅 ⚠️ 提示、不报未登记",
    )
    args = parser.parse_args(argv)
    print(render(collect(Path(args.dir), scope=args.scope), scope=args.scope))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
