"""主流程编排与 CLI（文档 T9）。

子命令：
  discover            阶段A：tid 清单发现
  crawl [--limit N]   阶段B：抓全部分页并归档原始 HTML（gzip）
  reparse [--tid N]   离线重解析归档 HTML → 清洗 → 分块 → 抽取 → 入库
  images [--limit N]  阶段C：图片下载（受授权门控，默认关闭）
  report              阶段D：质检报告
  verify --tid N      对指定帖跑验收断言
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import db as dbm
from .clean import assert_clean, clean_floor_html
from .config import load_config
from .discover import run_discovery
from .extract_bearing import extract_bearings
from .extract_sections import analyze_sections, split_sections
from .http import AlertLogger, BrowserSession, HttpMetrics, decode_gb18030, is_valid_thread
from .images import ImageRegistry
from .parse_post import parse_page
from .report import build_report


def _session(cfg: Any) -> BrowserSession:
    metrics = HttpMetrics()
    alerts = AlertLogger(cfg.paths.logs_dir / "alerts.log")
    return BrowserSession(cfg.http, cfg.rate_limit, alerts, metrics)


def _archive_path(cfg: Any, fid: int | None, tid: int, page: int) -> Path:
    root = Path(cfg.paths.raw_dir) / str(fid or "unknown") / str(tid)
    root.mkdir(parents=True, exist_ok=True)
    return root / f"p{page}.html.gz"


def cmd_discover_digest(cfg: Any) -> int:
    """全作者精华区发现批次（2026-11-01 委托人批准），产出专家名册。"""
    from .discover import discover_digest_all

    with _session(cfg) as session:
        stats = discover_digest_all(
            session, cfg, roster_csv=cfg.paths.data_dir / "expert_roster.csv"
        )
        total_new = sum(n for n, _ in stats.values())
        print(f"精华区全作者发现完成: 新增 {total_new} 帖")
        print(json.dumps({str(k): v for k, v in stats.items()}, ensure_ascii=False))
        print(json.dumps(session.metrics.summary(), ensure_ascii=False))
    return 0


def cmd_discover(cfg: Any) -> int:
    with _session(cfg) as session:
        stats = run_discovery(cfg, session)
        print(f"discovery 统计: {json.dumps(stats, ensure_ascii=False)}")
        print(f"tid_manifest.csv -> {cfg.paths.manifest_csv}")
        print(json.dumps(session.metrics.summary(), ensure_ascii=False))
    return 0


def cmd_crawl(cfg: Any, limit: int | None, resume: bool) -> int:
    con = dbm.connect(cfg.paths.db_path)
    if not resume:
        # 进程崩溃后 RUNNING 会永久卡住：默认把上次残留的 RUNNING 视为失败重跑；
        # --resume 则保留 RUNNING 并把它纳入本次待抓集合（真正续跑）。
        con.execute(
            "UPDATE thread_index SET crawl_status='FAILED', "
            "error_msg='stale RUNNING (previous crash)' WHERE crawl_status='RUNNING'"
        )
        con.execute("UPDATE crawl_state SET status='FAILED' WHERE status='RUNNING'")
        con.commit()
    rows = _eligible_rows(con, cfg, resume=resume)
    if limit:
        rows = rows[:limit]
    print(f"待抓取帖子: {len(rows)}", flush=True)
    session = _session(cfg)
    license_note = cfg.license_note
    try:
        for k, row in enumerate(rows):
            tid = row["tid"]
            dbm.set_state(con, f"thread:{tid}", "RUNNING")
            try:
                pages = _crawl_thread(cfg, session, con, tid, row["fid"])
                con.execute(
                    "UPDATE thread_index SET crawl_status='DONE', crawl_time=datetime('now'), "
                    "error_msg=NULL, page_count=?, license_note=? WHERE tid=?",
                    (pages, license_note, tid),
                )
                con.commit()
                dbm.set_state(con, f"thread:{tid}", "DONE")
                print(f"[{k+1}/{len(rows)}] tid={tid} DONE pages={pages}", flush=True)
            except Exception as exc:
                con.execute(
                    "UPDATE thread_index SET crawl_status='FAILED', error_msg=? WHERE tid=?",
                    (str(exc)[:400], tid),
                )
                con.commit()
                dbm.set_state(con, f"thread:{tid}", "FAILED", last_error=str(exc)[:400])
                print(f"[{k+1}/{len(rows)}] tid={tid} FAILED: {exc}", flush=True)
    finally:
        session.close()
        con.close()
    return 0


def _eligible_rows(con: Any, cfg: Any, *, resume: bool = False) -> list[Any]:
    """v2 资格集合：in_scope、未完成、含图（或语料库），按 crawl_order 排序。"""
    order = cfg.target.crawl_order or (cfg.target.boards + cfg.target.corpus_boards)
    corpus = set(cfg.target.corpus_boards)
    statuses = "('PENDING','FAILED','RUNNING')" if resume else "('PENDING','FAILED')"
    rows = con.execute(
        "SELECT tid, fid, has_image, topic_pages FROM thread_index "
        f"WHERE in_scope=1 AND crawl_status IN {statuses}"
    ).fetchall()
    def rank(r: Any) -> tuple[int, int]:
        fid = r["fid"]
        prio = order.index(fid) if fid in order else 99
        if cfg.target.require_image and fid not in corpus and not r["has_image"]:
            return (200, -r["tid"])  # 无图帖降到最后（仍保留，宁可多采）
        return (prio, -r["tid"])     # 版块内从新到旧：模板-rich 帖优先入库
    return sorted(rows, key=rank)


def _crawl_thread(cfg: Any, session: BrowserSession, con: Any, tid: int, fid_hint: int | None) -> int:
    base = cfg.target.base_url
    allowed = set(cfg.target.boards) | set(cfg.target.corpus_boards)
    result = session.get_bytes(f"{base}/read.php?tid={tid}")
    html_text = decode_gb18030(result.body)
    if not is_valid_thread(html_text):
        con.execute(
            "UPDATE thread_index SET crawl_status='INVALID', error_msg='invalid thread' WHERE tid=?",
            (tid,),
        )
        con.commit()
        return 0
    first = parse_page(html_text, tid, 1)
    fid = first.fid or fid_hint
    if fid is not None and fid not in allowed:
        # 搜索路径带出的站外帖：标记后跳过，不浪费请求
        con.execute(
            "UPDATE thread_index SET crawl_status='OUT_OF_SCOPE', fid=?, error_msg=? WHERE tid=?",
            (fid, f"fid={fid} 不在目标版块", tid),
        )
        con.commit()
        return 0
    total = first.page_count
    out = _archive_path(cfg, fid, tid, 1)
    out.write_bytes(gzip.compress(result.body, mtime=0))
    pages = 1
    for page in range(2, total + 1):
        rp = session.get_bytes(f"{base}/read.php?tid={tid}&page={page}")
        rh = decode_gb18030(rp.body)
        if not is_valid_thread(rh):
            break
        (_archive_path(cfg, fid, tid, page)).write_bytes(gzip.compress(rp.body, mtime=0))
        pages += 1
    # 回填发现元数据
    op_time = None
    if first.floors and first.floors[0].post_time:
        op_time = first.floors[0].post_time
    con.execute(
        "UPDATE thread_index SET subject=?, fid=?, forum_name=?, post_time=?, "
        "author_name=? WHERE tid=?",
        (
            first.title or None, fid, first.forum_name, op_time,
            first.floors[0].author_name if first.floors else None, tid,
        ),
    )
    con.commit()
    return pages


def cmd_reparse(cfg: Any, tid_filter: int | None, force: bool = False) -> int:
    con = dbm.connect(cfg.paths.db_path)
    if tid_filter:
        rows = con.execute("SELECT tid FROM thread_index WHERE tid=?", (tid_filter,)).fetchall()
    elif force:
        # 全量：清洗/解析规则迭代后重跑全部 DONE 帖（离线，零网络请求）
        rows = con.execute(
            "SELECT tid FROM thread_index WHERE crawl_status='DONE' ORDER BY tid"
        ).fetchall()
    else:
        # 增量：只解析尚未入库的 DONE 帖（重复调用安全、成本低）
        rows = con.execute(
            "SELECT tid FROM thread_index WHERE crawl_status='DONE' "
            "AND tid NOT IN (SELECT DISTINCT tid FROM floor) ORDER BY tid"
        ).fetchall()
    print(f"重解析帖子: {len(rows)}", flush=True)
    n_ok = 0
    for k, row in enumerate(rows):
        try:
            _reparse_thread(cfg, con, row["tid"])
            # 单帖成功即提交：失败帖回滚后不留下半截 children。
            con.commit()
            n_ok += 1
            if (k + 1) % 10 == 0:
                print(f"... {k+1}/{len(rows)}")
        except Exception as exc:
            con.rollback()
            print(f"tid={row['tid']} REPARSE-FAIL: {exc}")
    con.commit()
    con.close()
    print(f"reparse 完成: {n_ok}/{len(rows)}")
    return 0


def _load_pages(cfg: Any, fid: int | None, tid: int) -> list[str]:
    root = Path(cfg.paths.raw_dir) / str(fid or "unknown") / str(tid)
    if not root.exists():
        # fid 回填后目录名可能带真实 fid：搜索全部
        for cand in Path(cfg.paths.raw_dir).glob(f"*/{tid}"):
            root = cand
            break
    pages: list[tuple[int, str]] = []
    for gz in sorted(root.glob("p*.html.gz")):
        num = int(gz.stem[1:].split(".")[0])
        pages.append((num, decode_gb18030(gzip.decompress(gz.read_bytes()))))
    return [h for _, h in sorted(pages)]


def _reparse_thread(cfg: Any, con: Any, tid: int) -> None:
    row = con.execute("SELECT fid FROM thread_index WHERE tid=?", (tid,)).fetchone()
    fid = row["fid"] if row else None
    pages_html = _load_pages(cfg, fid, tid)
    if not pages_html:
        raise RuntimeError("no archived pages")

    dbm.clear_thread_children(con, tid)
    all_floors: dict[str, Any] = {}
    page_of: dict[str, int] = {}
    title = forum_name = None
    thread_fid = fid
    paywalled = False
    for page_no, html_text in enumerate(pages_html, start=1):
        pp = parse_page(html_text, tid, page_no)
        title = pp.title or title
        forum_name = pp.forum_name or forum_name
        thread_fid = pp.fid or thread_fid
        paywalled = paywalled or pp.paywalled
        for fl in pp.floors:
            if fl.pid in all_floors:
                continue
            # 跨页楼层序号偏移：article 是全帖楼层号，直接可用
            all_floors[fl.pid] = fl
            page_of[fl.pid] = page_no
    floors = sorted(all_floors.values(), key=lambda f: f.floor_index)

    for fl in floors:
        registry = ImageRegistry(tid=tid, pid=fl.pid, fid=thread_fid or 0,
                                 author_uid=fl.author_uid or 0, refs=fl.images)
        content_clean = clean_floor_html(fl.raw_html, registry)
        fl.content_clean = content_clean
        violations = assert_clean(content_clean)
        if violations:
            print(f"  [warn] tid={tid} pid={fl.pid} 清洗残留: {violations}")
        plain = content_clean
        for ph in registry.refs:
            plain = plain.replace(f"[[IMG:{ph.position_index}:{ph.image_id}]]", "")
        con.execute(
            "INSERT OR REPLACE INTO floor(pid,tid,floor_index,author_uid,author_name,"
            "post_time,is_op,subject,author_meta_json,content_clean,content_plain_no_img,"
            "image_count,raw_html_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"{tid}_{fl.pid}", tid, fl.floor_index, fl.author_uid, fl.author_name,
                fl.post_time, 1 if fl.is_op else 0,
                fl.subject,
                json.dumps(fl.author_meta, ensure_ascii=False),
                content_clean, plain.strip(),
                len(fl.images),
                # 归档页必须记该楼层真正所在的那一页；老版本一律写 p1，
                # 导致 83% 的楼层无法回指原始 HTML（2026-11-02 修正）。
                str(_archive_path(cfg, thread_fid, tid, page_of.get(fl.pid, 1))),
            ),
        )
        for sc in fl.scores:
            con.execute(
                "INSERT INTO peer_score(tid,pid,score_type,score_value,rater_name,reason) "
                "VALUES (?,?,?,?,?,?)",
                (tid, f"{tid}_{fl.pid}", sc.score_type, sc.value, sc.rater, sc.reason),
            )
        for img in fl.images:
            # 重解析只更新"解析得到"的字段。老写法用 INSERT OR REPLACE 会把
            # download_status 打回 PENDING、抹掉 local_full_path/sha256/marks_*——
            # 重跑一次 reparse 就等于把上万张已下图片重新排队。这里改成 UPSERT 只覆盖
            # 元数据列，下载状态与衍生资产一律保留。
            con.execute(
                "INSERT INTO image_asset(image_id,tid,pid,position_index,fid,"
                "author_uid,thumb_url,full_url,caption_before,caption_after,"
                "download_status,license_note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(image_id) DO UPDATE SET "
                "tid=excluded.tid, pid=excluded.pid, position_index=excluded.position_index, "
                "fid=excluded.fid, author_uid=excluded.author_uid, "
                "thumb_url=excluded.thumb_url, full_url=excluded.full_url, "
                "caption_before=excluded.caption_before, caption_after=excluded.caption_after",
                (
                    f"{tid}_{img.image_id}", tid, f"{tid}_{img.pid}", img.position_index,
                    img.fid, img.author_uid, img.thumb_url, img.full_url,
                    img.caption_before, img.caption_after,
                    "SKIPPED_PENDING_AUTHORIZATION" if not cfg.authorization.image_download_approved
                    else "PENDING",
                    cfg.license_note,
                ),
            )

    # 结构化分块 + 罗盘抽取：仅 uid==1 楼层语料
    uid1_text = "\n\n".join(
        fl.content_clean for fl in floors
        if fl.author_uid == 1 or fl.is_op
    )
    sec = analyze_sections(uid1_text)
    # 用 split_sections 的 order（原实现恒写 0，section_order 字段形同虚设）。
    section_order = {s.name: s.order for s in split_sections(uid1_text)}
    for name, content in sec.sections.items():
        con.execute(
            "INSERT INTO section(tid,pid,section_name,section_order,content,item_count) "
            "VALUES (?,?,?,?,?,?)",
            (tid, f"{tid}_tpc", name, section_order.get(name, 0), content,
             len(sec.data_lines if name == "数据" else [])),
        )
        sid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        items: list[Any] = []
        if name == "浅析":
            items = sec.qianxi_items
        elif name in ("历史查证", "历史勘验"):
            items = [h.content for h in sec.history_items]
        for idx, item in enumerate(items, start=1):
            gen = None
            outcomes: list[str] = []
            if name in ("历史查证", "历史勘验"):
                h = sec.history_items[idx - 1]
                gen, outcomes = h.generation_ref, h.outcome_keywords
            con.execute(
                "INSERT INTO section_item(section_id,item_index,content,generation_ref,"
                "outcome_keywords) VALUES (?,?,?,?,?)",
                (sid, idx, item, gen, json.dumps(outcomes, ensure_ascii=False)),
            )
            if name in ("历史查证", "历史勘验"):
                verifiable = 1 if (gen or outcomes) else 0
                con.execute(
                    "INSERT INTO feedback_record(tid,pid,source_section,feedback_type,"
                    "generation_ref,outcome_text,verifiable,confidence) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (tid, f"{tid}_tpc", name, "A_历史勘验", gen, item, verifiable, "low"),
                )
        if name in ("调整方案", "实证效果") and content.strip():
            con.execute(
                "INSERT INTO feedback_record(tid,pid,source_section,feedback_type,"
                "outcome_text,verifiable,confidence) VALUES (?,?,?,?,?,0,'low')",
                (tid, f"{tid}_tpc", name, "B_调理反馈", content[:1000]),
            )

    # 罗盘观测：【数据】逐行优先，缺失则全文
    source_text = "\n".join(sec.data_lines) if sec.data_lines else uid1_text
    subject = title
    bearing_id_by_key: dict[tuple[str, float], int] = {}
    for obs in extract_bearings(source_text):
        con.execute(
            "INSERT INTO bearing_observation(tid,pid,section_name,subject,label,category,"
            "shan24,degree,shan_from_degree,offset_from_center,is_consistent,"
            "is_boundary_risk,is_gua_boundary_risk,raw_text,needs_review) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                tid, f"{tid}_tpc", "数据" if sec.data_lines else "全文", subject,
                obs.label, obs.category, obs.shan24, obs.degree, obs.shan_from_degree,
                obs.offset_from_center, int(obs.is_consistent), int(obs.is_boundary_risk),
                int(obs.is_gua_boundary_risk), obs.raw_text, int(obs.needs_review),
            ),
        )
        bid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        bearing_id_by_key[(obs.label, obs.degree)] = bid

    # 图注 ↔ 方位绑定（★核心监督信号）
    for img in [im for fl in floors for im in fl.images]:
        caption = f"{img.caption_before} {img.caption_after}"
        if not caption.strip():
            continue
        for (label, deg), bid in bearing_id_by_key.items():
            if len(label) >= 2 and label in caption:
                con.execute(
                    "INSERT INTO image_bearing_link(image_id,bearing_id,match_text,confidence) "
                    "VALUES (?,?,?,?)",
                    (f"{tid}_{img.image_id}", bid, label, 0.9),
                )

    con.execute(
        "UPDATE thread_index SET has_structured_template=?, template_richness=?, paywalled=? WHERE tid=?",
        (int(sec.has_structured_template), sec.template_richness, int(paywalled), tid),
    )
    # 不在 _reparse_thread 内提交：调用方按单帖 commit / rollback 控制原子性。


def _image_bytes_ok(data: bytes) -> bool:
    """传输截断的图片同样是 200 + 非 HTML 开头（站点断流），只能真解码才能判死。"""
    from io import BytesIO

    from PIL import Image
    try:
        with Image.open(BytesIO(data)) as im:
            im.load()
        return True
    except Exception:
        return False


def _fetch_row(row: Any, fetch_asset: Any) -> tuple[bytes | None, str, bool]:
    """按 full → thumb 顺序取一张图的字节流。返回 (数据, 实际用的 url, 是否死链)。"""
    dead = False
    for url in (row["full_url"], row["thumb_url"]):
        if not url:
            continue
        data, dead = fetch_asset(url)
        if data is not None and _image_bytes_ok(data):
            return data, url, False
        # full 是截断图时继续试 thumb：thumb 通常更小，能完整传完
    return None, "", dead


def _iter_fetched(rows: Any, fetch_asset: Any, conc: int) -> Any:
    """产出 (序号, 行, 数据, url, 死链)。concurrency>1 时用线程池预取，滑动窗口限流。

    为什么值得做：实测单张图端到端 8 秒（令牌桶 2s + 站点响应 5~6s），而全局桶的上限是
    30 张/分，串行只能跑到 7~8 张/分。站点是 IO 慢、不是桶满，所以并发抓取不违反
    §2.1「图片并发 ≤3 且仍受全局令牌桶约束」——桶由 SharedTokenBucket 的 flock 保证，
    每个线程各开各的 fd，跨线程同样串行。
    """
    if conc <= 1:
        for k, r in enumerate(rows):
            data, used, dead = _fetch_row(r, fetch_asset)
            yield k, r, data, used, dead
        return
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

    with ThreadPoolExecutor(max_workers=conc) as pool:
        it = iter(enumerate(rows))
        pending: dict[Any, Any] = {}
        for k, r in it:
            pending[pool.submit(_fetch_row, r, fetch_asset)] = (k, r)
            if len(pending) >= conc * 2:
                break
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for fut in done:
                k, r = pending.pop(fut)
                try:
                    data, used, dead = fut.result()
                except Exception:
                    data, used, dead = None, "", False
                yield k, r, data, used, dead
                nxt = next(it, None)
                if nxt is not None:
                    pending[pool.submit(_fetch_row, nxt[1], fetch_asset)] = nxt


def cmd_images(cfg: Any, limit: int | None, concurrency: int = 1,
               tid: int | None = None) -> int:
    if not cfg.authorization.image_download_approved:
        print("图片下载未授权：image_download_approved=false（/attachment/ 被 robots.txt 禁止）。"
              "仅登记 URL/图注，不做下载。")
        return 0
    print("=" * 60)
    print("警告：/attachment/ 目录被 robots.txt 禁止抓取。")
    print("继续执行表示使用者已确认获得站方授权（本次由委托人在指令中明确授权）。")
    print("5 秒后开始……")
    print("=" * 60)
    time.sleep(5)
    con = dbm.connect(cfg.paths.db_path)
    # 2026-11-02 实证：与另一进程（marks/crawl）并行时 UPDATE 立刻抛
    # `sqlite3.OperationalError: database is locked`（默认 busy timeout 为 0），
    # 整批中断。WAL 下写写仍互斥，必须显式等待。与 cmd_marks 保持同一口径。
    con.execute("PRAGMA busy_timeout=30000")
    rows = con.execute(
        "SELECT image_id, tid, position_index, pid, fid, author_uid, thumb_url, full_url, "
        "caption_before, caption_after FROM image_asset "
        "WHERE download_status IN ('PENDING','FAILED','SKIPPED_PENDING_AUTHORIZATION')"
        + (" AND tid=?" if tid is not None else "") +
        " ORDER BY CASE WHEN download_status='FAILED' THEN 1 ELSE 0 END, "
        "tid, position_index LIMIT ?",
        ((tid,) if tid is not None else ()) + (limit or 10**9,),
    ).fetchall()
    print(f"待下载图片: {len(rows)}", flush=True)
    session = _session(cfg)
    images_dir = Path(cfg.paths.images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)

    from PIL import Image

    def fetch_asset(url: str) -> tuple[bytes | None, bool]:
        """图片资产专用轻量抓取：返回 (数据, 是否永久死链)。

        理由：死外链（2007~2012 外站图床）在代理下每次连接要等到超时，
        沿用页面级 5 次重试会让单条死链阻塞 4~7 分钟。仍遵守全局令牌桶。
        本站附件已被服务器删除时返回 200 + 空体：重试没有意义，直接判定 DEAD。
        """
        for attempt in range(2):
            session.wait_turn()
            p = subprocess.run(
                ["curl", "-sS", "-m", "20", "--compressed", "-A", cfg.http.user_agent,
                 "-w", "\n%{http_code}", "-o", "-", url],
                capture_output=True, timeout=35)
            out = p.stdout
            try:
                code = int(out[out.rfind(b"\n") + 1:])
            except ValueError:
                code = 0
            body = out[:out.rfind(b"\n")]
            if code == 200 and len(body) > 1000 and body[:3] != b"<ht":
                return body, False
            if code == 200 and b"<ht" not in body[:6]:
                return None, True
            if code == 429:
                time.sleep(15)
                continue
            if attempt == 0:
                time.sleep(5)
        return None, False

    ok = err = 0
    conc = max(1, min(int(concurrency), 3))      # §2.1：图片并发上限 3
    if conc > 1:
        print(f"并发抓取: {conc}", flush=True)
    for k, r, data, used_url, dead in _iter_fetched(rows, fetch_asset, conc):
        composite = r["image_id"]            # f"{tid}_{hash}"
        _, _, img_hash = composite.partition("_")
        tid = r["tid"]
        tid_dir = images_dir / str(tid)
        tid_dir.mkdir(parents=True, exist_ok=True)
        dest = tid_dir / f"{r['position_index']:02d}_{img_hash}.jpg"
        if data is None:
            con.execute("UPDATE image_asset SET download_status=? WHERE image_id=?",
                        ("DEAD" if dead else "FAILED", composite))
            con.commit()
            err += 1
            if (k + 1) % 100 == 0:
                print(f"... {k+1}/{len(rows)} ok={ok} err={err}", flush=True)
            continue
        dest.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        width = height = None
        orig_w = orig_h = None
        software = None
        gps_present = 0
        gps_info: dict[str, str] = {}
        try:
            with Image.open(dest) as im:
                im.load()                      # 强制解码：断流截断在这里暴露
                width, height = im.size
                exif = im.getexif()
                software = exif.get(305)
                exif_ifd = exif.get_ifd(0x8769) if hasattr(exif, "get_ifd") else {}
                orig_w = exif_ifd.get(40962)
                orig_h = exif_ifd.get(40963)
                if hasattr(exif, "get_ifd"):
                    gps_raw = exif.get_ifd(34853)
                    if gps_raw:
                        gps_present = 1
                        gps_info = {str(kk): str(vv) for kk, vv in list(gps_raw.items())[:10]}
        except Exception:
            pass
        if width is None:
            # _fetch_row 已校验过，这里是落盘后的兜底：绝不把打不开的图记成 DONE
            dest.unlink(missing_ok=True)
            con.execute("UPDATE image_asset SET download_status='FAILED' WHERE image_id=?",
                        (composite,))
            con.commit()
            err += 1
            if (k + 1) % 100 == 0:
                print(f"... {k+1}/{len(rows)} ok={ok} err={err}", flush=True)
            continue
        # exif.json + meta.json（文档 T7.3/7.4）
        exif_payload = {
            "software": str(software) if software else None,
            "gps_present": bool(gps_present),
            "gps_info": gps_info,
            "exif_orig_width": orig_w,
            "exif_orig_height": orig_h,
        }
        (tid_dir / f"{r['position_index']:02d}_{img_hash}.exif.json").write_text(
            json.dumps(exif_payload, ensure_ascii=False, indent=1), encoding="utf-8")
        meta_payload = {
            "image_id": composite, "tid": tid, "pid": r["pid"],
            "position_index": r["position_index"], "fid": r["fid"],
            "author_uid": r["author_uid"],
            "thumb_url": r["thumb_url"], "full_url": r["full_url"],
            "downloaded_from": used_url,
            "width": width, "height": height, "sha256": sha,
            "caption_before": r["caption_before"], "caption_after": r["caption_after"],
            "exif": exif_payload,
            "license_note": cfg.license_note,
        }
        (tid_dir / f"{r['position_index']:02d}_{img_hash}.meta.json").write_text(
            json.dumps(meta_payload, ensure_ascii=False, indent=1), encoding="utf-8")
        con.execute(
            "UPDATE image_asset SET download_status='DONE', local_full_path=?, "
            "width=?, height=?, exif_orig_width=?, exif_orig_height=?, "
            "exif_software=?, exif_gps_present=?, sha256=? WHERE image_id=?",
            (str(dest), width, height, orig_w, orig_h,
             str(software) if software else None, gps_present, sha, composite),
        )
        con.commit()
        ok += 1
        if (k + 1) % 100 == 0:
            print(f"... {k+1}/{len(rows)} ok={ok} err={err}", flush=True)
    session.close()
    con.close()
    print(f"DONE ok={ok} err={err}", flush=True)
    return 0


def cmd_marks(cfg: Any, tid: int | None, author_uid: int | None, workers: int,
              limit: int | None, force: bool, preview: str, want_ocr: bool = False) -> int:
    """§7.4 衍生资产：颜色分割矢量化 + 预览图 + 回填 image_asset。"""
    from .marks_batch import run_batch, select_targets

    con = dbm.connect(cfg.paths.db_path)
    targets = select_targets(con, tid, author_uid, limit, force, ocr_only=want_ocr)
    scope = f"tid={tid}" if tid else (f"uid={author_uid}" if author_uid else "全站")
    print(f"待处理图片 {len(targets)} 张（{scope}，workers={workers}，preview={preview}）", flush=True)
    stats = run_batch(con, targets, workers, preview, force, want_ocr)
    summary = {k: v for k, v in stats.items() if k != 'errors'}
    print(json.dumps(summary, ensure_ascii=False))
    for e in stats.get('errors', []):
        print(f"  [err] {e.get('path')} {e.get('error')}")
    return 0


def cmd_bearings(cfg: Any, tid: int | None) -> int:
    """离线重抽取罗盘观测（T5 迭代用）：只读 floor.content_clean，不重爬、不重解 HTML。

    抽取规则改了以后不用整帖 reparse——方位观测只依赖正文文本，
    从库里重算 844 帖只要几秒，而 reparse 要重新解析 2.6 万个归档页。
    """
    con = dbm.connect(cfg.paths.db_path)
    con.execute('PRAGMA busy_timeout=30000')
    where = "WHERE tid=?" if tid else "WHERE tid IN (SELECT DISTINCT tid FROM floor)"
    tids = [r[0] for r in con.execute(f"SELECT tid FROM thread_index {where} ORDER BY tid",
                                      (tid,) if tid else ())]
    before = con.execute("SELECT COUNT(*) FROM bearing_observation").fetchone()[0]
    skip_jx = skip_astro = written = 0
    for k, t in enumerate(tids, start=1):
        rows = con.execute(
            "SELECT content_clean, author_uid, is_op FROM floor WHERE tid=? ORDER BY floor_index",
            (t,)).fetchall()
        uid1_text = "\n\n".join(r[0] for r in rows if (r[1] == 1 or r[2]) and r[0])
        if not uid1_text.strip():
            continue
        sec = analyze_sections(uid1_text)
        source_text = "\n".join(sec.data_lines) if sec.data_lines else uid1_text
        subject = con.execute("SELECT subject FROM thread_index WHERE tid=?", (t,)).fetchone()
        subject = subject[0] if subject else None
        st: dict[str, int] = {}
        obs_list = extract_bearings(source_text, st)
        skip_jx += st.get('skipped_jianxiang', 0)
        skip_astro += st.get('skipped_astro', 0)
        # 先删旧链接再删观测，避免 bearing_observation 重建后留下悬空 bearing_id。
        con.execute(
            "DELETE FROM image_bearing_link WHERE bearing_id IN "
            "(SELECT id FROM bearing_observation WHERE tid=?)",
            (t,),
        )
        con.execute("DELETE FROM bearing_observation WHERE tid=?", (t,))
        bearing_id_by_key: dict[tuple[str, float], int] = {}
        for obs in obs_list:
            con.execute(
                "INSERT INTO bearing_observation(tid,pid,section_name,subject,label,category,"
                "shan24,degree,shan_from_degree,offset_from_center,is_consistent,"
                "is_boundary_risk,is_gua_boundary_risk,raw_text,needs_review) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (t, f"{t}_tpc", "数据" if sec.data_lines else "全文", subject,
                 obs.label, obs.category, obs.shan24, obs.degree, obs.shan_from_degree,
                 obs.offset_from_center, int(obs.is_consistent), int(obs.is_boundary_risk),
                 int(obs.is_gua_boundary_risk), obs.raw_text, int(obs.needs_review)))
            bid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            bearing_id_by_key[(obs.label, obs.degree)] = bid
            written += 1
        # 重建图注↔方位绑定（与 _reparse_thread 同一规则），否则 old 链接被删后无替代。
        for img in con.execute(
            "SELECT image_id, caption_before, caption_after FROM image_asset WHERE tid=?",
            (t,),
        ).fetchall():
            caption = f"{img['caption_before'] or ''} {img['caption_after'] or ''}"
            if not caption.strip():
                continue
            for (label, _deg), bid in bearing_id_by_key.items():
                if len(label) >= 2 and label in caption:
                    con.execute(
                        "INSERT INTO image_bearing_link(image_id,bearing_id,match_text,confidence) "
                        "VALUES (?,?,?,?)",
                        (img["image_id"], bid, label, 0.9),
                    )
        if k % 200 == 0:
            con.commit()
            print(f"  ... {k}/{len(tids)} 帖，写入 {written} 条", flush=True)
    con.commit()
    after = con.execute("SELECT COUNT(*) FROM bearing_observation").fetchone()[0]
    review = con.execute("SELECT COUNT(*) FROM bearing_observation WHERE needs_review=1").fetchone()[0]
    print(json.dumps({"threads": len(tids), "before": before, "after": after,
                      "needs_review": review,
                      "skipped_jianxiang": skip_jx, "skipped_astro": skip_astro},
                     ensure_ascii=False))
    return 0


def _report_success_count(text: str) -> int | None:
    """从报告文本中提取「成功 N」；提取不到返回 None。"""
    import re as _re
    m = _re.search(r"成功\s*(\d+)", text)
    return int(m.group(1)) if m else None


def cmd_report(cfg: Any) -> int:
    con = dbm.connect(cfg.paths.db_path)
    text = build_report(con, cfg)

    # 一致性自检：报告生成后必须核对「成功帖数」与库内 DONE 数一致。
    # 原实现无自检，导致 11-04 扩展批后报告长期停在旧口径而无声滞后。
    reported = _report_success_count(text)
    db_done = con.execute(
        "SELECT COUNT(*) FROM thread_index WHERE crawl_status='DONE'"
    ).fetchone()[0]
    if reported != db_done:
        print(
            f"REPORT-INCONSISTENT: 报告写「成功 {reported if reported is not None else '?'}」，"
            f"库内 DONE={db_done}；拒绝写入滞后报告。",
            file=sys.stderr,
        )
        con.close()
        return 2

    Path(cfg.paths.report_path).write_text(text, encoding="utf-8")
    con.close()
    print(f"报告已写入 {cfg.paths.report_path}（DONE={db_done} 已核对）")
    return 0


def cmd_verify(cfg: Any, tid: int) -> int:
    con = dbm.connect(cfg.paths.db_path)
    checks: list[tuple[str, bool, str]] = []
    th = con.execute("SELECT * FROM thread_index WHERE tid=?", (tid,)).fetchone()
    checks.append(("thread indexed", th is not None, str(dict(th)) if th else "missing"))
    n_floors = con.execute("SELECT COUNT(*) FROM floor WHERE tid=?", (tid,)).fetchone()[0]
    checks.append(("floors >= 10", n_floors >= 10, f"floors={n_floors}"))
    n_imgs = con.execute("SELECT COUNT(*) FROM image_asset WHERE tid=?", (tid,)).fetchone()[0]
    if tid == 163913:
        checks.append(("images == 17", n_imgs == 17, f"images={n_imgs}"))
    n_scores = con.execute("SELECT COUNT(*) FROM peer_score WHERE tid=?", (tid,)).fetchone()[0]
    checks.append(("scores >= 8", n_scores >= 8, f"scores={n_scores}"))
    has_reason = con.execute(
        "SELECT COUNT(*) FROM peer_score WHERE tid=? AND reason LIKE '%判断准确%'", (tid,)
    ).fetchone()[0]
    checks.append(("reason 判断准确", has_reason >= 1, f"count={has_reason}"))
    n_bearings = con.execute("SELECT COUNT(*) FROM bearing_observation WHERE tid=?", (tid,)).fetchone()[0]
    checks.append(("bearings >= 11", n_bearings >= 11, f"bearings={n_bearings}"))
    if th:
        checks.append(("fid == 58", th["fid"] == 58, f"fid={th['fid']}"))
    ok = True
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name}  ({detail})")
        ok = ok and passed
    con.close()
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fengshui-collector")
    parser.add_argument("--config", default="config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("discover")
    sub.add_parser("discover_digest")
    p_crawl = sub.add_parser("crawl")
    p_crawl.add_argument("--limit", type=int, default=None)
    p_crawl.add_argument("--resume", action="store_true")
    p_reparse = sub.add_parser("reparse")
    p_reparse.add_argument("--tid", type=int, default=None)
    p_reparse.add_argument("--force", action="store_true")
    p_images = sub.add_parser("images")
    p_images.add_argument("--limit", type=int, default=None)
    p_images.add_argument("--concurrency", type=int, default=1)
    p_images.add_argument("--tid", type=int, default=None)
    p_marks = sub.add_parser("marks")
    p_marks.add_argument("--tid", type=int, default=None)
    p_marks.add_argument("--author-uid", type=int, default=None)
    p_marks.add_argument("--workers", type=int, default=8)
    p_marks.add_argument("--limit", type=int, default=None)
    p_marks.add_argument("--force", action="store_true")
    p_marks.add_argument("--preview", choices=("marks", "all", "none"), default="marks")
    p_marks.add_argument("--ocr", action="store_true")
    p_bear = sub.add_parser("bearings")
    p_bear.add_argument("--tid", type=int, default=None)
    sub.add_parser("report")
    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--tid", type=int, required=True)
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    if args.command == "discover":
        return cmd_discover(cfg)
    if args.command == "discover_digest":
        return cmd_discover_digest(cfg)
    if args.command == "crawl":
        return cmd_crawl(cfg, args.limit, args.resume)
    if args.command == "reparse":
        return cmd_reparse(cfg, args.tid, args.force)
    if args.command == "images":
        return cmd_images(cfg, args.limit, args.concurrency, args.tid)
    if args.command == "marks":
        return cmd_marks(cfg, args.tid, args.author_uid, args.workers,
                         args.limit, args.force, args.preview, args.ocr)
    if args.command == "bearings":
        return cmd_bearings(cfg, args.tid)
    if args.command == "report":
        return cmd_report(cfg)
    if args.command == "verify":
        return cmd_verify(cfg, args.tid)
    return 1


if __name__ == "__main__":
    sys.exit(main())
