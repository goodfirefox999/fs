# -*- coding: utf-8 -*-
"""从 Wayback 论坛素材导出 zeri Case（案例库通道 Phase 1.2）。

设计纪律（对应 cases/schema.py 的反编造约束）：
1. 只导出「本地有原文快照」的条目 —— snapshot_path 必填，绝不用猜测路径；
2. 坐向按二十四山中心度换算，换算依据写进 params_assumed，不冒充精确观测；
3. 无快照的条目不伪造 Case，只输出 pending_snapshots.csv 待补清单；
4. 全部导出为 C 级（残缺/来源为机会性快照），不统计、不进回归集。

用法:
  python tools/export_cases.py [--out DIR] [--limit N]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SOURCE_JSONL = BASE.parent / "data" / "cases" / "forum_scrape" / "forum_cases_extract.jsonl"
SOURCE_DIR = BASE.parent / "data" / "cases" / "forum_scrape"
DEFAULT_OUT = BASE / "cases" / "graded" / "C"

SHAN_CENTER = {
    "子": 0, "癸": 15, "丑": 30, "艮": 45, "寅": 60, "甲": 75,
    "卯": 90, "乙": 105, "辰": 120, "巽": 135, "巳": 150, "丙": 165,
    "午": 180, "丁": 195, "未": 210, "坤": 225, "申": 240, "庚": 255,
    "酉": 270, "辛": 285, "戌": 300, "乾": 315, "亥": 330, "壬": 345,
}
# 兼容「戌山辰向」（山名后带「山」）与「坐戌向辰兼乾巽」（坐+山名+向）两种写法。
SEAT_FIRST = re.compile(r"(?:坐\s*)?([\u4e00-\u9fa5])\s*(?:山|向)")

LICENSE = "个人研究用途，不公开分发。原文版权归论坛原作者；来源为 Internet Archive 机会性快照。"


def seat_degrees(siting: str | None) -> tuple[float | None, str | None]:
    """从「坐戌向辰兼乾巽」等文本取坐山中心度；返回 (度数, 说明)。"""
    if not siting:
        return None, None
    first = siting.split("|")[0].strip()
    m = SEAT_FIRST.search(first)
    if not m:
        return None, None
    shan = m.group(1)
    if shan not in SHAN_CENTER:
        return None, None
    return float(SHAN_CENTER[shan]), shan


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def yaml_quote(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def export_one(row: dict, snapshot_rel: str, out_dir: Path, deg: float, shan: str) -> Path:
    tid = int(row["tid"])
    course = parse_time(row.get("first_time"))
    if course is None:
        raise ValueError("first_time 缺失或不可解析")
    case_id = f"WB-{tid}"
    title = row.get("title") or f"Wayback tid={tid}"
    siting = row.get("siting") or ""
    raw_claim = "\n".join([
        title,
        f"原文坐向描述：{siting}",
        f"峦头术语计数：{json.dumps(row.get('terms') or {}, ensure_ascii=False)}",
        f"地名线索：{'、'.join(row.get('places') or [])[:200]}",
    ])

    lines = [
        f"case_id: {case_id}",
        f"title: {yaml_quote(title)}",
        "grade: C",
        "source:",
        f"  snapshot_path: {yaml_quote(snapshot_rel)}",
        f"  url: {yaml_quote(row['wayback_url']) if row.get('wayback_url') else 'null'}",
        f"  collected_at: {yaml_quote(datetime.now().strftime('%Y-%m-%d'))}",
        f"  license_note: {yaml_quote(LICENSE)}",
        "input:",
        f"  course: {yaml_quote(course.isoformat() + '+08:00')}",
        f"  azimuth_deg: {deg}",
        "  task_kind: 勘察记录",
        "  lat: 0.0",
        "  lon: 0.0",
        "  nodes: []",
        "  strictness: normal",
        "  person_year_zhi: null",
        "  person_name: null",
        f"  fenjin: {yaml_quote(row['fenjin']) if row.get('fenjin') else 'null'}",
        "params_assumed:",
        f"  - {yaml_quote(f'坐向取自原文「{siting.split(chr(124))[0].strip()}」，按「{shan}」山中心度 {deg:.0f}° 换算，非实测罗盘读数。')}",
        "  - 经纬度未知（原文仅文字地名），lat/lon 置 0，不参与真太阳时计算。",
        "  - 事主生肖与日课四柱缺失，相主与大煞类规则不得据此判定。",
        "  - 来源为 Wayback 机会性快照，不代表原帖全量；仅作通道验证，不进回归集。",
        "author_claim:",
        "  raw: |",
    ]
    lines += [f"    {ln}" for ln in raw_claim.splitlines()]
    lines += [
        "  verdict: null",
        "  notes: 作者未给单一吉凶结论；术语计数仅作作者关注点的客观记录。",
        "expected: {}",
        "notes: |",
        "  本案例由 tools/export_cases.py 自动生成，用途是验证「论坛素材 → zeri Case」通道。",
        "  等级 C：原文快照为机会性抓取，输入不完整；任何规则判定结果都不得当真值。",
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{case_id}.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--limit", type=int, default=10 ** 9)
    args = ap.parse_args()

    rows = [json.loads(line) for line in SOURCE_JSONL.read_text(encoding="utf-8").splitlines() if line.strip()]
    out_dir = Path(args.out)
    exported: list[Path] = []
    pending: list[tuple[str, str, str]] = []

    for row in rows:
        tid = int(row["tid"])
        snapshot = SOURCE_DIR / "samples" / f"tid_{tid}.html"
        deg, shan = seat_degrees(row.get("siting"))
        if not snapshot.exists():
            pending.append((str(tid), "缺本地原文快照", row.get("siting") or ""))
        elif deg is None:
            pending.append((str(tid), "坐向不可解析为度数", row.get("siting") or ""))
        elif len(exported) >= args.limit:
            pending.append((str(tid), "本次 limit 未导出", row.get("siting") or ""))
        else:
            rel = f"../../../../data/cases/forum_scrape/samples/tid_{tid}.html"
            try:
                exported.append(export_one(row, rel, out_dir, deg, shan))
            except ValueError as exc:
                pending.append((str(tid), str(exc), row.get("siting") or ""))

    manifest = BASE / "cases" / "pending_snapshots.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tid", "missing_reason", "siting_raw"])
        w.writerows(pending)

    print(json.dumps({
        "source_rows": len(rows),
        "exported": [p.name for p in exported],
        "pending": len(pending),
        "manifest": str(manifest),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
