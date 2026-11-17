# -*- coding: utf-8 -*-
"""双端确定性底座对拍：Python zeri 生成基准 → TS 逐条比对。

范围（zeri/docs/ts-parity.md §3 中「当前可行」的部分）：
  二十四山归一：0~359.9° 每 0.1°，共 3600 点，输出山名。

用法：
  python tools/parity_snapshot.py            # 生成 Python 侧基准 JSON
  （TS 侧测试 tests/parity-mountain.test.ts 读取该文件逐条比对）

纪律：本脚本只调用纯函数，不访问网络、不改规则库。规则判定层的对拍
必须等 Python 侧 citation.verified_by 非空后才允许（见 ts-parity.md §4）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "core-symbol" / "src"))

from core_symbol.mountain import mountain_of_azimuth  # noqa: E402

OUT = BASE / "tests" / "fixtures" / "parity-mountain.json"


def main() -> int:
    rows = []
    # 每 0.1° 一点，避免浮点累加误差：用整数 i 表示 i/10 度。
    for i in range(3600):
        deg = i / 10.0
        m = mountain_of_azimuth(deg)
        name = getattr(m, "name", None) or str(m)
        rows.append([deg, name])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "_source": "zeri/core-symbol mountain.mountain_of_azimuth",
        "_note": "双端确定性底座对拍基准；规则判定层不在本快照范围内",
        "rows": rows,
    }, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"points": len(rows), "out": str(OUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
