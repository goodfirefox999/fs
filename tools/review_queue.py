# -*- coding: utf-8 -*-
"""needs_review 复核闭环：给两库方位表加复核列 + 导出人工复核清单。

Phase 1.6：龙坛 806 条、fs168 1,454 条待复核观测此前没有任何状态字段，
数据资产在贬值。本脚本：
1. 幂等 ALTER TABLE 加 review_status / reviewed_at / reviewer / review_note；
2. 导出 CSV 清单，按优先级排序（山名矛盾 > 骑线 > 大空亡 > 未分类），
   供人工逐条填写后回灌。

用法:
  python tools/review_queue.py --apply-schema     # 加列（幂等）
  python tools/review_queue.py --export           # 导出 CSV
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DBS = {
    "longtan": (BASE / "data" / "fs.sqlite", "bearing_observation"),
    "fs168": (BASE / "data" / "fs168" / "fs168.sqlite", "fs168_bearing"),
}
OUT_DIR = BASE / "data" / "review"

COLUMNS = [
    ("review_status", "TEXT DEFAULT 'PENDING'"),
    ("reviewed_at", "TEXT"),
    ("reviewer", "TEXT"),
    ("review_note", "TEXT"),
]


def apply_schema() -> None:
    for site, (path, table) in DBS.items():
        if not path.exists():
            print(f"{site}: 库不存在，跳过")
            continue
        con = sqlite3.connect(path)
        existing = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        changed = []
        for name, ddl in COLUMNS:
            if name not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
                changed.append(name)
        con.commit()
        con.close()
        print(f"{site}.{table}: 新增列 {changed or '（已存在）'}")


def export() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for site, (path, table) in DBS.items():
        if not path.exists():
            continue
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(f"""
            SELECT id, tid, pid, label, category, shan24, degree,
                   shan_from_degree, offset_from_center,
                   is_consistent, is_boundary_risk, is_gua_boundary_risk,
                   raw_text, needs_review, review_status
            FROM {table} WHERE needs_review=1
            ORDER BY
              CASE
                WHEN is_consistent=0 THEN 0
                WHEN is_boundary_risk=1 THEN 1
                WHEN is_gua_boundary_risk=1 THEN 2
                ELSE 3
              END,
              tid, id
        """).fetchall()
        out = OUT_DIR / f"{site}_review_queue.csv"
        with out.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["id", "tid", "pid", "label", "category", "shan24", "degree",
                        "shan_from_degree", "offset", "is_consistent",
                        "is_boundary_risk", "is_gua_boundary_risk",
                        "raw_text", "review_status", "reviewer", "review_note"])
            for r in rows:
                w.writerow([
                    r["id"], r["tid"], r["pid"], r["label"], r["category"],
                    r["shan24"], r["degree"], r["shan_from_degree"],
                    r["offset_from_center"], r["is_consistent"],
                    r["is_boundary_risk"], r["is_gua_boundary_risk"],
                    r["raw_text"], r["review_status"] or "PENDING", "", "",
                ])
        con.close()
        print(f"{site}: 导出 {len(rows)} 条 → {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply-schema", action="store_true")
    ap.add_argument("--export", action="store_true")
    args = ap.parse_args()
    if args.apply_schema:
        apply_schema()
    if args.export:
        export()
    if not args.apply_schema and not args.export:
        ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
