#!/usr/bin/env python3
"""从 junitxml 输出标准汇总行：「X passed / Y failed / Z errors / S skipped in Ts」。

为什么需要这个工具（AGENTS 环境事实第 10 条）
------------------------------------------
本沙箱里 pytest 9.2.0 的 stdout 只剩进度点——header、collected、summary 行全部
不可见（连 `pytest --version` 的插件行都丢）。stdout 会被管道、tail、沙箱过滤，
XML 文件不会。所以：

- **报数的唯一权威来源 = junitxml**，解析 testsuite 的
  tests / failures / errors / skipped / time 属性；
- `make test-fast` / `make test` 已默认落 `out/junit-*.xml` 并调用本工具收尾，
  「这次跑了多少、过了多少」不再依赖谁的终端能看见汇总行。

用法::

    python tools/summarize_junit.py out/junit-fast.xml        # 打印汇总行
    python tools/summarize_junit.py a.xml b.xml               # 多文件逐行
    python tools/summarize_junit.py out/junit-fast.xml --gate # 失败/错误>0 时退出码 1
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

__all__ = ["summarize", "main"]


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
    verdict = "✅" if (f == 0 and e == 0 and n > 0) else "❌"
    line = (
        f"{verdict} {path.name}: {n} passed / {f} failed / {e} errors"
        f" / {s} skipped in {t:.1f}s"
    )
    return line, f == 0 and e == 0 and n > 0


def main(argv: list[str] | None = None) -> int:
    args = [a for a in (argv or sys.argv[1:])]
    gate = "--gate" in args
    paths = [Path(a) for a in args if not a.startswith("--")]
    if not paths:
        print(__doc__)
        return 2
    all_ok = True
    for p in paths:
        line, ok = summarize(p)
        print(line)
        all_ok &= ok
    return 0 if (all_ok or not gate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
