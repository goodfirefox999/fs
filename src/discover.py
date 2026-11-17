"""tid 清单发现（v2 架构，文档 §1.2）。

主路径   thread.php?fid={fid}&page={N} 列表页全量扫描：
         每行自带 tid/标题/作者uid+名/日期/回复/浏览/含图标记/主题页数/最后回复，
         一次扫描建立全站主题索引 + 版主 uid 映射（u.php 登录墙无需触碰）。
备用路径 search.php?authorid={uid}（全站）与 search.php?authorid={uid}&digest=1（精华）
         对每位版主跑两条，与列表页取并集；数量差写入 discovery_stats.discrepancy_note。
         实测陷阱：search 的 fid 参数被忽略（v2 §1.2(3)），不做版块内过滤。
资格判定 in_scope：fid ∈ boards∪corpus_boards 且（作者 ∈ 版主 或 fid ∈ corpus_boards）。
完整性断言：digest 搜索 < digest_search_expected → 显式告警（不得静默）。
"""
from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .config import AppConfig
from .db import connect, upsert_thread
from .http import BrowserSession, decode_gb18030

FORUM_NAMES: dict[int, str] = {
    58: "阴宅风水", 5: "择日择吉", 2: "阳宅家居",
    50: "问题-讨论-经验-理论-综合研究", 24: "峦头欣赏",
    51: "卫星图片", 55: "三元-三合-飞星-辅星-综合讨论",
    9: "风水择日资料",
}
TID_RE = re.compile(r"read\.php\?tid=(\d+)")
TR_SPLIT = re.compile(r"<tr\b")


@dataclass
class ListingRow:
    tid: int
    fid: int
    subject: str
    is_digest: bool
    is_pinned: bool
    has_image: bool
    topic_pages: int
    author_uid: int | None
    author_name: str | None
    post_date: str | None
    reply_count: int | None
    view_count: int | None
    last_reply_time: str | None
    last_replier: str | None


def parse_listing_rows(html_text: str, fid: int) -> list[ListingRow]:
    """解析列表页全部主题行（含置顶/公告；页内 tid 去重）。"""
    rows: list[ListingRow] = []
    seen: set[int] = set()
    for chunk in TR_SPLIT.split(html_text):
        td_m = re.search(r'id="td_(\d+)"', chunk)
        tid_m = re.search(r'read\.php\?tid=(\d+)"', chunk)
        raw_tid = td_m.group(1) if td_m else (tid_m.group(1) if tid_m else None)
        if not raw_tid:
            continue
        tid = int(raw_tid)
        if tid in seen:
            continue
        seen.add(tid)
        subject = ""
        sm = re.search(rf'id="a_ajax_{tid}"[^>]*>([\s\S]{{0,200}}?)</a>', chunk)
        if sm:
            subject = re.sub(r"<[^>]+>", "", sm.group(1)).strip()
        um = re.search(r'u\.php\?action=show&(?:amp;)?uid=(\d+)"[^>]*>([^<]{1,30})</a>', chunk)
        dm = re.search(r'<div class="f10 gray2">(\d{4}-\d{2}-\d{2})</div>', chunk)
        rm = re.search(r'<span class="s8">(\d+)</span>\s*/\s*(\d+)', chunk)
        lm = re.search(r'page=e&(?:amp;)?fpage=\d+#a">\s*([\d\- :]+?)\s*</a>', chunk)
        lby = re.search(r"by:\s*([^<]{1,30})</span>", chunk)
        pages = [int(n) for n in re.findall(
            rf"read\.php\?tid={tid}&(?:amp;)?fpage=\d+&(?:amp;)?page=(\d+)", chunk)]
        rows.append(ListingRow(
            tid=tid,
            fid=fid,
            subject=subject[:200],
            is_digest=bool(re.search(r"digest_\d\.gif", chunk)) or 'title="精华帖标志"' in chunk,
            is_pinned="headtopic" in chunk or 'title="置顶' in chunk,
            has_image="images/wind/file/img.gif" in chunk,
            topic_pages=max(pages) if pages else 1,
            author_uid=int(um.group(1)) if um else None,
            author_name=um.group(2).strip() if um else None,
            post_date=dm.group(1) if dm else None,
            reply_count=int(rm.group(1)) if rm else None,
            view_count=int(rm.group(2)) if rm else None,
            last_reply_time=lm.group(1).strip() if lm else None,
            last_replier=lby.group(1).strip() if lby else None,
        ))
    return rows


def scan_board(session: BrowserSession, cfg: AppConfig, fid: int,
               max_pages: int = 900) -> tuple[list[ListingRow], int]:
    """扫描版块列表页至末页（置顶帖跨页重复，按 tid 去重）。"""
    base = cfg.target.base_url
    seen: set[int] = set()
    rows: list[ListingRow] = []
    fetched = 0
    for page in range(1, max_pages + 1):
        url = f"{base}/thread.php?fid={fid}&page={page}"
        result = session.get_bytes(url)
        html_text = decode_gb18030(result.body)
        page_rows = parse_listing_rows(html_text, fid)
        if not page_rows:
            break
        fetched += 1
        fresh = 0
        for r in page_rows:
            if r.tid in seen:
                continue
            seen.add(r.tid)
            rows.append(r)
            if not r.is_pinned:
                fresh += 1
        if fresh == 0 and page > 1:
            break  # 整页只有置顶/公告 → 已到末页
    return rows, fetched


def discover_digest_all(session: BrowserSession, cfg: AppConfig,
                        max_pages_per_board: int = 60,
                        roster_csv: Path | None = None) -> dict[int, tuple[int, int]]:
    """全作者精华区发现（2026-11-01 委托人批准的扩展批次）。

    对 7 大板块逐页翻 thread.php?fid={fid}&search=digest，不过滤作者：
    - 越界页检测：内容与上一页完全一致（服务器把超范围页钳制到末页）→ 停止
    - 已存在的帖子（版主精华已采）只补标记，不覆盖 discover_source
    - 新帖入库 in_scope=1, discover_source='digest_all', crawl_status='PENDING'
    - 附带产出专家名册 roster_csv（uid, name, digest_count）→ 第二轮定向扩展用
    返回 {fid: (新发现帖数, 实际翻页数)}。
    """
    from collections import Counter

    con = connect(cfg.paths.db_path)
    license_note = cfg.license_note
    roster: Counter[tuple[int, str]] = Counter()
    stats: dict[int, tuple[int, int]] = {}
    for fid in cfg.target.boards:
        seen: set[int] = set()
        seen_prev: set[int] | None = None
        pages = 0
        new_threads = 0
        for page in range(1, max_pages_per_board + 1):
            url = f"{cfg.target.base_url}/thread.php?fid={fid}&search=digest&page={page}"
            result = session.get_bytes(url)
            html_text = decode_gb18030(result.body)
            rows = parse_listing_rows(html_text, fid)
            tids_now = {r.tid for r in rows}
            if not rows:
                break
            if seen_prev is not None and tids_now <= seen_prev:
                break                      # 越界页被钳制到末页
            pages += 1
            for r in rows:
                if r.tid in seen:
                    continue
                seen.add(r.tid)
                if r.author_uid is not None and r.author_name:
                    roster[(r.author_uid, r.author_name)] += 1
                row = con.execute(
                    "SELECT in_scope FROM thread_index WHERE tid=?", (r.tid,)
                ).fetchone()
                if row is not None:
                    if not row["in_scope"]:
                        con.execute(
                            "UPDATE thread_index SET in_scope=1, is_digest=1, "
                            "discover_source=discover_source || '+digest_all' WHERE tid=?",
                            (r.tid,),
                        )
                        new_threads += 1          # 0→1 转 in_scope 同样算待采新增
                    continue
                con.execute(
                    "INSERT INTO thread_index(tid,subject,fid,forum_name,author_uid,"
                    "author_name,post_time,last_reply_time,reply_count,is_digest,"
                    "page_count,discover_source,crawl_status,has_image,is_pinned,"
                    "view_count,topic_pages,in_scope,source_url,license_note) "
                    "VALUES (?,?,?,?,?,?,?,?,?,1,?,'digest_all','PENDING',?,?,?,?,1,?,?)",
                    (
                        r.tid, r.subject or None, fid, FORUM_NAMES.get(fid),
                        r.author_uid, r.author_name, r.post_date, r.last_reply_time,
                        r.reply_count, r.topic_pages, int(r.has_image), int(r.is_pinned),
                        r.view_count, r.topic_pages,
                        f"{cfg.target.base_url}/read.php?tid={r.tid}", license_note,
                    ),
                )
                new_threads += 1
            seen_prev = tids_now
            con.commit()
        stats[fid] = (new_threads, pages)
        print(f"  fid={fid} {FORUM_NAMES.get(fid, '?')}: 精华 {len(seen)} 帖"
              f"（新增 {new_threads}）/ {pages} 页", flush=True)
    if roster_csv is not None:
        roster_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(roster_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["uid", "用户名", "精华帖数"])
            for (uid, name), n in roster.most_common():
                w.writerow([uid, name, n])
        print(f"专家名册 -> {roster_csv}（{len(roster)} 位作者）", flush=True)
    con.commit()
    con.close()
    return stats


def discover_author_topics(session: BrowserSession, cfg: AppConfig, uid: int,
                           digest_only: bool = False, max_pages: int = 60) -> dict[int, str]:
    """作者搜索：返回 {tid: discover_source}，翻页至空页。

    注意（v2 §1.2(3)）：search.php 结果为全站范围；版块归属在 crawl 阶段
    由帖子自身解析后再过滤。
    """
    base = cfg.target.base_url
    suffix = "&digest=1" if digest_only else ""
    source = "search_digest" if digest_only else "search_author"
    found: dict[int, str] = {}
    for page in range(1, max_pages + 1):
        url = (f"{base}/search.php?step=2&keyword=&authorid={uid}"
               f"&seekfid=all{suffix}&page={page}")
        result = session.get_bytes(url)
        html_text = decode_gb18030(result.body)
        tids = [int(t) for t in TID_RE.findall(html_text)]
        new = [t for t in dict.fromkeys(tids) if t not in found]
        if not new:
            break
        for tid in new:
            found[tid] = source
    return found


def run_discovery(cfg: AppConfig, session: BrowserSession) -> dict[str, int]:
    """v2 发现主流程。返回统计 dict。"""
    alerts = session._alerts  # noqa: SLF001 - 同包内部复用
    con = connect(cfg.paths.db_path)
    target_boards = set(cfg.target.boards) | set(cfg.target.corpus_boards)

    # 1) 版块列表页全量扫描
    mod_names = {n.strip() for n in cfg.target.moderators}
    name_to_uid: dict[str, int] = {k: v for k, v in cfg.target.known_uids.items()}
    all_rows: dict[int, ListingRow] = {}
    board_pages: dict[int, int] = {}
    for fid in cfg.target.crawl_order:
        rows, pages = scan_board(session, cfg, fid)
        board_pages[fid] = pages
        for r in rows:
            prev = all_rows.get(r.tid)
            if prev is None or (not prev.is_digest and r.is_digest):
                all_rows[r.tid] = r
        for r in rows:
            if r.author_name in mod_names and r.author_uid is not None:
                name_to_uid.setdefault(r.author_name, r.author_uid)
        print(f"  fid={fid} {FORUM_NAMES.get(fid, '?')}: {len(rows)} 主题 / {pages} 页", flush=True)

    resolved = {n: name_to_uid[n] for n in mod_names if n in name_to_uid}
    missing_mods = sorted(mod_names - set(resolved))
    if missing_mods:
        alerts.write("MODERATOR_UNRESOLVED",
                     f"以下版主在列表扫描中未出现（检查名称拼写）：{missing_mods}")
    mod_uids = set(resolved.values())
    print(f"版主 uid 解析 {len(resolved)}/{len(mod_names)}: {resolved}", flush=True)

    # 2) 全站索引入库 + in_scope 标记
    for r in all_rows.values():
        is_mod = r.author_uid in mod_uids
        in_scope = int((r.fid in target_boards) and (is_mod or r.fid in cfg.target.corpus_boards))
        upsert_thread(con, {
            "tid": r.tid,
            "subject": r.subject or None,
            "fid": r.fid,
            "forum_name": FORUM_NAMES.get(r.fid),
            "author_uid": r.author_uid,
            "author_name": r.author_name,
            "post_time": r.post_date,
            "last_reply_time": r.last_reply_time,
            "last_replier": r.last_replier,
            "reply_count": r.reply_count,
            "is_digest": int(r.is_digest),
            "page_count": r.topic_pages,
            "discover_source": "fid_listing",
            "crawl_status": "PENDING",
            "has_image": int(r.has_image),
            "is_pinned": int(r.is_pinned),
            "view_count": r.view_count,
            "topic_pages": r.topic_pages,
            "in_scope": in_scope,
            "source_url": f"{cfg.target.base_url}/read.php?tid={r.tid}",
            "license_note": cfg.license_note,
        })
    con.commit()

    # 3) 每位版主：作者全帖搜索 + 精华搜索（并集补漏 + discrepancy）
    license_note = cfg.license_note
    stats_rows: list[tuple[str | None, int | None, int, int, int, int, int, str]] = []
    for name in sorted(mod_names):
        uid = resolved.get(name)
        if uid is None:
            stats_rows.append((name, None, 0, 0, 0, 0, 0, "uid 未解析"))
            continue
        search_all = discover_author_topics(session, cfg, uid, digest_only=False)
        search_dig = discover_author_topics(session, cfg, uid, digest_only=True)
        union = set(search_all) | set(search_dig)
        in_scope_hits = 0
        for tid in sorted(union):
            source = search_all.get(tid) or search_dig.get(tid) or "search_author"
            row = con.execute(
                "SELECT fid, in_scope FROM thread_index WHERE tid=?", (tid,)
            ).fetchone()
            if row is None:
                con.execute(
                    "INSERT OR IGNORE INTO thread_index(tid, author_uid, is_digest,"
                    " discover_source, crawl_status, source_url, license_note, in_scope)"
                    " VALUES (?,?,?,?,'PENDING',?,?,0)",
                    (tid, uid, 1 if source == "search_digest" else 0, source,
                     f"{cfg.target.base_url}/read.php?tid={tid}", license_note),
                )
                continue
            if not row["in_scope"] and row["fid"] in target_boards:
                # 列表行漏解析作者格时，搜索路径可补标
                con.execute(
                    "UPDATE thread_index SET in_scope=1, discover_source="
                    "discover_source || '+' || ? WHERE tid=?",
                    (source, tid),
                )
                in_scope_hits += 1
            elif row["in_scope"]:
                in_scope_hits += 1
        con.commit()
        listing_n = con.execute(
            "SELECT COUNT(*) FROM thread_index WHERE author_uid=? AND fid IN "
            f"({','.join(str(f) for f in target_boards)})",
            (uid,),
        ).fetchone()[0]
        expected = cfg.target.digest_search_expected.get(name)
        notes = []
        if expected is not None and len(search_dig) < expected:
            notes.append(f"digest 搜索 {len(search_dig)} < 期望 {expected}（接口上限/口径差，不得假设完整）")
            alerts.write("DISCOVER_SHORTFALL", f"{name}: {notes[-1]}")
        note = "; ".join(notes) if notes else "listing/search/digest 见各列"
        stats_rows.append((name, uid, listing_n, len(search_all),
                           len(search_dig), in_scope_hits, len(union), note))

    con.executemany(
        "INSERT OR REPLACE INTO discovery_stats(name,uid,listing_topics,search_topics,"
        "search_digest,search_in_scope,union_topics,discrepancy_note) "
        "VALUES (?,?,?,?,?,?,?,?)",
        stats_rows,
    )
    con.executemany(
        "INSERT OR REPLACE INTO moderators(uid,name,boards,resolved_from) VALUES (?,?,?,?)",
        [(uid, name, ",".join(str(f) for f in cfg.target.boards), "fid_listing")
         for name, uid in sorted(resolved.items(), key=lambda x: x[1])],
    )
    con.commit()

    # 4) manifest CSV（仅 in_scope）
    eligible = con.execute(
        "SELECT tid, subject, fid, post_time, reply_count, discover_source "
        "FROM thread_index WHERE in_scope=1 ORDER BY tid"
    ).fetchall()
    _write_manifest(cfg, eligible)

    total = con.execute("SELECT COUNT(*) FROM thread_index").fetchone()[0]
    con.close()
    print(f"发现完成: 全站索引 {total} 条，in_scope {len(eligible)} 条", flush=True)
    return {
        "index_total": total,
        "in_scope": len(eligible),
        "board_pages": sum(board_pages.values()),
        "moderators_resolved": len(resolved),
    }


def _write_manifest(cfg: AppConfig, rows: list[sqlite3.Row]) -> None:
    path = Path(cfg.paths.manifest_csv)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["tid", "标题", "版块fid", "发表时间", "回复数", "来源"])
        for r in rows:
            w.writerow([r["tid"], r["subject"], r["fid"] or "", r["post_time"] or "",
                        r["reply_count"] or 0, r["discover_source"]])
