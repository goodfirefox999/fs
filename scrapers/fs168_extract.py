# -*- coding: utf-8 -*-
"""fs168（天機易學論壇）结构化抽取器（Phase 1.1）。

设计要点
--------
- 输入：fs168.sqlite 的 posts_clean 表（46,092 帖清洗正文，Phase 0 已补齐）。
- 复用龙坛的纯文本抽取函数（extract_bearings / analyze_sections / split_sections），
  它们无站点耦合；但产出写入独立的 fs168_* 表，不污染龙坛结构化数据。
- 不伪造图注绑定：fs168 的 posts.images JSON 只有 name/size，没有 caption_before/after，
  因此不生成 image_bearing_link，只在报告里明确标注该通道对 fs168 不可用。
- 全部为本地计算，零网络请求。

产出表：
  fs168_section(id, tid, pid, section_name, section_order, content, item_count)
  fs168_bearing(id, tid, pid, section_name, label, category, shan24, degree,
                shan_from_degree, offset_from_center, is_consistent,
                is_boundary_risk, is_gua_boundary_risk, raw_text, needs_review)
  fs168_extract_stat(tid PRIMARY KEY, n_floors, n_bearings, n_sections,
                     has_structured_template, template_richness, extract_time)

用法:
  python scrapers/fs168_extract.py [--limit N] [--force]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

from src.extract_bearing import extract_bearings  # noqa: E402
from src.extract_sections import analyze_sections, split_sections  # noqa: E402

DB_PATH = BASE / "data" / "fs168" / "fs168.sqlite"

DDL = """
CREATE TABLE IF NOT EXISTS fs168_section (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tid INTEGER, pid TEXT, section_name TEXT, section_order INTEGER,
  content TEXT, item_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_fsec_tid ON fs168_section(tid);

CREATE TABLE IF NOT EXISTS fs168_bearing (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tid INTEGER, pid TEXT, section_name TEXT,
  label TEXT, category TEXT, shan24 TEXT, degree REAL,
  shan_from_degree TEXT, offset_from_center REAL,
  is_consistent INTEGER, is_boundary_risk INTEGER, is_gua_boundary_risk INTEGER,
  raw_text TEXT, needs_review INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_fbear_tid ON fs168_bearing(tid);
CREATE INDEX IF NOT EXISTS idx_fbear_review ON fs168_bearing(needs_review, is_consistent);

CREATE TABLE IF NOT EXISTS fs168_extract_stat (
  tid INTEGER PRIMARY KEY,
  n_floors INTEGER, n_bearings INTEGER, n_sections INTEGER,
  has_structured_template INTEGER, template_richness INTEGER,
  extract_time TEXT
);
"""


# fs168 语料含大量天文历算讨论（黄赤交角 23.4°、北纬/东经、宿度、360° 周天），
# 龙坛的 DEG_ONLY 兜底会把它们全当罗盘方位。这里在调用侧加一层语义过滤：
# 只有「带山名」或「带明确罗盘/方位语义」的观测才入库，其余丢弃并记录在统计里。
_ASTRO_CONTEXT = (
    "北纬", "南纬", "东经", "西经", "黄赤", "赤道", "黄道", "自转轴", "倾斜",
    "冬至", "夏至", "春分", "秋分", "回归年", "恒星年", "岁差", "宿度", "周天",
)
_DIRECTION_CONTEXT = ("山", "向", "水口", "来龙", "砂", "坐", "朝", "案", "分金")


def _is_bearing_context(obs) -> bool:
    raw = getattr(obs, "raw_text", "") or ""
    if any(k in raw for k in _ASTRO_CONTEXT):
        return False
    # 有山名的一律保留（最高置信）；无山名则要求 label/raw 带罗盘语义。
    if getattr(obs, "shan24", None):
        return True
    label = getattr(obs, "label", "") or ""
    return any(k in (raw + label) for k in _DIRECTION_CONTEXT)


def _bearing_rows(tid: int, pid: str, section_name: str, text: str) -> list[tuple]:
    out = []
    for obs in extract_bearings(text):
        if not _is_bearing_context(obs):
            continue
        out.append((
            tid, pid, section_name,
            obs.label, obs.category, obs.shan24, obs.degree,
            obs.shan_from_degree, obs.offset_from_center,
            int(obs.is_consistent), int(obs.is_boundary_risk),
            int(obs.is_gua_boundary_risk), obs.raw_text,
            int(obs.needs_review),
        ))
    return out


def extract_thread(con: sqlite3.Connection, tid: int) -> tuple[int, int, int]:
    """抽取单帖；返回 (楼层数, 方位数, 段数)。调用方负责 commit/rollback。"""
    rows = con.execute(
        "SELECT pid, content_clean FROM posts_clean WHERE tid=? ORDER BY pid", (tid,)
    ).fetchall()
    if not rows:
        return 0, 0, 0

    con.execute("DELETE FROM fs168_section WHERE tid=?", (tid,))
    con.execute("DELETE FROM fs168_bearing WHERE tid=?", (tid,))

    total_floors = total_bearings = total_sections = 0
    template_richness = 0
    has_template = False

    for pid, content in rows:
        if not content:
            continue
        total_floors += 1
        sec = analyze_sections(content)
        order = {s.name: s.order for s in split_sections(content)}
        for name, body in sec.sections.items():
            con.execute(
                "INSERT INTO fs168_section(tid,pid,section_name,section_order,content,item_count) "
                "VALUES (?,?,?,?,?,?)",
                (tid, pid, name, order.get(name, 0), body,
                 len(sec.data_lines) if name == "数据" else 0),
            )
            total_sections += 1
            # 【数据】段逐行抽取；其余段落也扫一遍（fs168 无固定模板，方位散落正文）。
            text_for_bearing = body if name == "数据" else content
            br = _bearing_rows(tid, pid, name, text_for_bearing)
            con.executemany(
                "INSERT INTO fs168_bearing(tid,pid,section_name,label,category,shan24,degree,"
                "shan_from_degree,offset_from_center,is_consistent,is_boundary_risk,"
                "is_gua_boundary_risk,raw_text,needs_review) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                br,
            )
            total_bearings += len(br)
        if not sec.sections:
            br = _bearing_rows(tid, pid, "", content)
            con.executemany(
                "INSERT INTO fs168_bearing(tid,pid,section_name,label,category,shan24,degree,"
                "shan_from_degree,offset_from_center,is_consistent,is_boundary_risk,"
                "is_gua_boundary_risk,raw_text,needs_review) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                br,
            )
            total_bearings += len(br)
        template_richness = max(template_richness, sec.template_richness)
        has_template = has_template or sec.has_structured_template

    con.execute(
        "INSERT INTO fs168_extract_stat(tid,n_floors,n_bearings,n_sections,"
        "has_structured_template,template_richness,extract_time) "
        "VALUES (?,?,?,?,?,?,datetime('now')) "
        "ON CONFLICT(tid) DO UPDATE SET n_floors=excluded.n_floors,"
        "n_bearings=excluded.n_bearings,n_sections=excluded.n_sections,"
        "has_structured_template=excluded.has_structured_template,"
        "template_richness=excluded.template_richness,extract_time=excluded.extract_time",
        (tid, total_floors, total_bearings, total_sections,
         int(has_template), template_richness),
    )
    return total_floors, total_bearings, total_sections


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10 ** 9)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB_PATH)
    con.executescript(DDL)
    con.commit()
    if args.force:
        con.execute("DELETE FROM fs168_section")
        con.execute("DELETE FROM fs168_bearing")
        con.execute("DELETE FROM fs168_extract_stat")
        con.commit()

    done = {r[0] for r in con.execute("SELECT tid FROM fs168_extract_stat")}
    tids = [r[0] for r in con.execute("SELECT DISTINCT tid FROM posts_clean ORDER BY tid")
            if r[0] not in done]
    tids = tids[:args.limit]
    print(f"待抽取: {len(tids)} 帖（已完成 {len(done)}）", flush=True)

    t0 = time.time()
    n_ok = n_bear = n_sec = 0
    for k, tid in enumerate(tids, 1):
        try:
            _, nb, ns = extract_thread(con, tid)
            con.commit()
            n_ok += 1
            n_bear += nb
            n_sec += ns
        except Exception as exc:
            con.rollback()
            print(f"tid={tid} EXTRACT-FAIL: {str(exc)[:120]}", flush=True)
        if k % 2000 == 0:
            print(f"... {k}/{len(tids)} 方位={n_bear} 段={n_sec} "
                  f"{k / max(time.time() - t0, 1):.1f} 帖/s", flush=True)

    summary = {
        "processed": n_ok,
        "bearings": con.execute("SELECT COUNT(*) FROM fs168_bearing").fetchone()[0],
        "needs_review": con.execute("SELECT COUNT(*) FROM fs168_bearing WHERE needs_review=1").fetchone()[0],
        "sections": con.execute("SELECT COUNT(*) FROM fs168_section").fetchone()[0],
        "template_threads": con.execute(
            "SELECT COUNT(*) FROM fs168_extract_stat WHERE has_structured_template=1"
        ).fetchone()[0],
        "elapsed_s": round(time.time() - t0, 1),
        "image_bearing_link": "NOT_AVAILABLE: fs168 图注无 caption_before/after，链路不适用",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
