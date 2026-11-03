#!/usr/bin/env python3
"""从 junitxml 输出标准汇总行：「X passed / Y failed / Z errors / S skipped in Ts」。

为什么需要这个工具（AGENTS 环境事实第 10 条）
------------------------------------------
本沙箱里 pytest 9.2.0 的 stdout 只剩进度点——header、collected、summary 行全部
不可见（连 `pytest --version` 的插件行都丢）。stdout 会被管道、tail、沙箱过滤，
XML 文件不会。所以：

- **报数的唯一权威来源 = junitxml**，解析 testsuite 的
  tests / failures / errors / skipped / time 属性；
- `passed = tests - failures - errors - skipped`：junit 的 ``tests`` 是**总数**，
  不能直接当 passed（否则 1220 passed + 1 skipped 会被报成 1221 passed）；
- `make test-fast` / `make test` 已默认落 `out/junit-*.xml` 并调用本工具收尾，
  「这次跑了多少、过了多少」不再依赖谁的终端能看见汇总行。

用法::

    python tools/summarize_junit.py out/junit-fast.xml        # 打印汇总行
    python tools/summarize_junit.py a.xml b.xml               # 多文件逐行
    python tools/summarize_junit.py out/junit-fast.xml --gate # 失败/错误>0 时退出码 1
    python tools/summarize_junit.py out/junit-perf-smoke.xml --perf  # 打印 perf_smoke_seconds

**skip 必须带原因可见**（评审十回路）：`make gate` 通过时的 skip 若不是「有意、
带原因、且知道补跑在哪」，下一个人会把「全绿」误读成「性能门禁也过了」。
所以有 skip 时额外打一行 `⚠️ N skipped`，并在原因里点名补跑位置。
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

__all__ = ["summarize", "skipped_details", "main"]


def summarize(path: Path) -> tuple[str, bool]:
    """返回 (汇总行, 是否全绿)。文件缺失/损坏按“证据不足”处理，不算绿。"""
    if not path.exists():
        return f"{path}: 文件不存在（测试可能根本没跑完）——不得引用任何口头数字", False
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        return f"{path}: XML 损坏（{e}）——测试进程可能在写盘前被终止", False
    ts = root.find("testsuite")
    if ts is None:
        return f"{path}: 无 testsuite 节点——不是 pytest junitxml？", False
    a = ts.attrib
    n, f, e, s = (int(a.get(k, 0)) for k in ("tests", "failures", "errors", "skipped"))
    t = float(a.get("time", 0))
    passed = n - f - e - s
    verdict = "✅" if (f == 0 and e == 0 and passed > 0) else "❌"
    line = (
        f"{verdict} {path.name}: {passed} passed / {f} failed / {e} errors"
        f" / {s} skipped in {t:.1f}s"
    )
    if s:
        # 有意 skip 必须可见：否则「全绿」会被读成「性能门禁也过了」
        line += f"\n⚠️ {s} skipped（非 pass）——原因见下方 ↳ 行；确认补跑步骤存在"
    return line, f == 0 and e == 0 and passed > 0


def perf_seconds(path: Path) -> float | None:
    """返回单个用例文件的总耗时（秒），供 CI 记录 ``perf_smoke_seconds``。

    性能冒烟的 junit 里只有一个用例，testsuite 的 time 就是它的实测耗时。
    """
    if not path.exists():
        return None
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return None
    ts = root.find("testsuite")
    if ts is None:
        return None
    try:
        return float(ts.get("time", ""))
    except ValueError:
        return None


def skipped_details(path: Path) -> list[str]:
    """返回被跳过用例的原因行（让 gate 输出里的 skip 不再是无名氏）。"""
    if not path.exists():
        return []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []
    details: list[str] = []
    for case in root.iter("testcase"):
        skipped = case.find("skipped")
        if skipped is None:
            continue
        name = "::".join(
            part for part in (case.get("classname"), case.get("name")) if part
        )
        reason = skipped.get("message") or skipped.get("type") or "(无原因)"
        details.append(f"  ↳ skipped: {name} — {reason}")
    return details


def main(argv: list[str] | None = None) -> int:
    args = [a for a in (argv or sys.argv[1:])]
    gate = "--gate" in args
    perf = "--perf" in args
    paths = [Path(a) for a in args if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    all_ok = True
    for p in paths:
        line, ok = summarize(p)
        print(line)
        for detail in skipped_details(p):
            print(detail)
        if perf:
            seconds = perf_seconds(p)
            if seconds is None:
                print(f"perf_smoke_seconds: 不可读（{p}）")
                all_ok = False
            else:
                # CI 逐次记录，便于观察 3.0s 档余量（连续 > 2.5s 需上浮阈值）
                print(f"perf_smoke_seconds: {seconds:.2f}")
        all_ok &= ok
    return 0 if (all_ok or not gate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
