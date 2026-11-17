"""SQLite 数据层：Schema（文档 T8 DDL）+ 连接管理 + 断点状态。

新增（文档附录 A 建议）：thread_index.survey_trip_id（考察批次聚类，暂留空）。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS thread_index (
  tid INTEGER PRIMARY KEY,
  subject TEXT, fid INTEGER, forum_name TEXT,
  author_uid INTEGER, author_name TEXT,
  post_time TEXT, last_reply_time TEXT, reply_count INTEGER,
  is_digest INTEGER, page_count INTEGER,
  discover_source TEXT,
  crawl_status TEXT DEFAULT 'PENDING',
  crawl_time TEXT, error_msg TEXT,
  has_structured_template INTEGER, template_richness INTEGER,
  paywalled INTEGER DEFAULT 0,
  survey_trip_id TEXT,
  source_url TEXT, license_note TEXT,
  has_image INTEGER, is_pinned INTEGER,
  view_count INTEGER, topic_pages INTEGER, last_replier TEXT,
  in_scope INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS moderators (
  uid INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  boards TEXT,
  resolved_from TEXT
);

CREATE TABLE IF NOT EXISTS discovery_stats (
  name TEXT PRIMARY KEY,
  uid INTEGER,
  listing_topics INTEGER,
  search_topics INTEGER,
  search_digest INTEGER,
  search_in_scope INTEGER,
  union_topics INTEGER,
  discrepancy_note TEXT
);

CREATE TABLE IF NOT EXISTS floor (
  pid TEXT PRIMARY KEY, tid INTEGER, floor_index INTEGER,
  author_uid INTEGER, author_name TEXT, post_time TEXT, is_op INTEGER,
  subject TEXT,
  author_meta_json TEXT,
  content_clean TEXT, content_plain_no_img TEXT,
  image_count INTEGER, raw_html_path TEXT,
  FOREIGN KEY(tid) REFERENCES thread_index(tid)
);

CREATE TABLE IF NOT EXISTS section (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tid INTEGER, pid TEXT, section_name TEXT, section_order INTEGER,
  content TEXT, item_count INTEGER
);

CREATE TABLE IF NOT EXISTS section_item (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  section_id INTEGER, item_index INTEGER, content TEXT,
  generation_ref TEXT,
  outcome_keywords TEXT
);

CREATE TABLE IF NOT EXISTS bearing_observation (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tid INTEGER, pid TEXT, section_name TEXT,
  subject TEXT,
  label TEXT, category TEXT,
  shan24 TEXT, degree REAL, shan_from_degree TEXT,
  offset_from_center REAL,
  is_consistent INTEGER, is_boundary_risk INTEGER, is_gua_boundary_risk INTEGER,
  raw_text TEXT, needs_review INTEGER DEFAULT 0,
  FOREIGN KEY(tid) REFERENCES thread_index(tid)
);

CREATE TABLE IF NOT EXISTS image_asset (
  image_id TEXT PRIMARY KEY, tid INTEGER, pid TEXT, position_index INTEGER,
  fid INTEGER, author_uid INTEGER,
  thumb_url TEXT, full_url TEXT, local_full_path TEXT, local_thumb_path TEXT,
  caption_before TEXT, caption_after TEXT,
  width INTEGER, height INTEGER,
  exif_orig_width INTEGER, exif_orig_height INTEGER,
  exif_software TEXT, exif_gps_present INTEGER,
  sha256 TEXT, download_status TEXT,
  marks_yellow_count INTEGER, marks_white_count INTEGER, marks_cyan_count INTEGER,
  marks_geojson_path TEXT, ocr_json_path TEXT,
  license_note TEXT
);

CREATE TABLE IF NOT EXISTS image_bearing_link (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  image_id TEXT, bearing_id INTEGER, match_text TEXT, confidence REAL
);

CREATE TABLE IF NOT EXISTS peer_score (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tid INTEGER, pid TEXT, score_type TEXT, score_value INTEGER,
  rater_name TEXT, reason TEXT
);

CREATE TABLE IF NOT EXISTS feedback_record (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tid INTEGER, pid TEXT, source_section TEXT,
  feedback_type TEXT,
  generation_ref TEXT, person_ref TEXT, outcome_text TEXT,
  verifiable INTEGER,
  delay_months INTEGER, confidence TEXT
);

CREATE TABLE IF NOT EXISTS crawl_state (
  task_key TEXT PRIMARY KEY,
  status TEXT, attempts INTEGER, last_error TEXT, updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_ti_author ON thread_index(author_uid, is_digest);
CREATE INDEX IF NOT EXISTS idx_bo_tid ON bearing_observation(tid);
CREATE INDEX IF NOT EXISTS idx_bo_review ON bearing_observation(needs_review, is_consistent);
CREATE INDEX IF NOT EXISTS idx_ia_tid ON image_asset(tid);
CREATE INDEX IF NOT EXISTS idx_ia_status ON image_asset(download_status);
CREATE INDEX IF NOT EXISTS idx_floor_tid ON floor(tid, floor_index);
"""

CHILD_TABLES = ("floor", "bearing_observation", "peer_score", "feedback_record")


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(DDL)
    con.commit()
    return con


def clear_thread_children(con: sqlite3.Connection, tid: int) -> None:
    """reparse 前清空该帖派生数据（thread_index 保留发现元数据）。

    **不删除 image_asset**：下载状态（download_status / local_full_path / sha256 /
    marks_*）是昂贵的衍生资产，reparse 用 UPSERT 只刷新解析得到的元数据列。
    删掉整表会让重跑 reparse 把已下载图片重新排队（并丢失本地路径）。
    """
    # 先清链接，再删被引用行，避免中间态悬空引用。
    con.execute(
        "DELETE FROM image_bearing_link WHERE bearing_id IN "
        "(SELECT id FROM bearing_observation WHERE tid=?)",
        (tid,),
    )
    con.execute(
        "DELETE FROM image_bearing_link WHERE image_id IN "
        "(SELECT image_id FROM image_asset WHERE tid=?)",
        (tid,),
    )
    for table in CHILD_TABLES:
        con.execute(f"DELETE FROM {table} WHERE tid=?", (tid,))
    con.execute(
        "DELETE FROM section_item WHERE section_id IN "
        "(SELECT id FROM section WHERE tid=?)",
        (tid,),
    )
    con.execute("DELETE FROM section WHERE tid=?", (tid,))


def upsert_thread(con: sqlite3.Connection, row: dict[str, Any]) -> None:
    cols = sorted(row.keys())
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "tid")
    sql = (
        f"INSERT INTO thread_index ({','.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(tid) DO UPDATE SET {updates}"
    )
    con.execute(sql, [row[c] for c in cols])


def get_state(con: sqlite3.Connection, task_key: str) -> sqlite3.Row | None:
    row: sqlite3.Row | None = con.execute(
        "SELECT * FROM crawl_state WHERE task_key=?", (task_key,)
    ).fetchone()
    return row


def set_state(con: sqlite3.Connection, task_key: str, status: str,
              attempts: int = 0, last_error: str | None = None) -> None:
    con.execute(
        "INSERT INTO crawl_state(task_key,status,attempts,last_error,updated_at) "
        "VALUES(?,?,?,?,datetime('now')) "
        "ON CONFLICT(task_key) DO UPDATE SET status=excluded.status, "
        "attempts=excluded.attempts, last_error=excluded.last_error, "
        "updated_at=excluded.updated_at",
        (task_key, status, attempts, last_error),
    )
    con.commit()
