# -*- coding: utf-8 -*-
"""fengshui-168.com（天機易學論壇，Discuz! X3）正文清洗器。

输入: data/fs168/raw/{tid}/p{n}.html.gz（fs168_threads 归档的原始 HTML）
输出（fs168.sqlite 新增两表，原始 posts 表不动——原始数据不修正原则）:
  posts_clean(tid, pid, content_clean, image_count)   清洗后正文，[[IMG:序号:文件名]] 占位图文绑定
  images(tid, pid, position_index, image_id, url, download_status)  正文图片登记（robots 禁 /data/，默认不下载）

清洗顺序沿用论坛一 v1 八步，Discuz 特化点：
  1. 删 attach_nopermission 游客提示块（实测每帖首楼一大段"马上注册"CTA）
  2. quote 块开头打【引用】标记（<div class="quote"><blockquote><font color=blue>…）
  3. aimg 游客缩略图 → 占位符（src 含 /data/attachment/）；表情/懒加载占位图删除

用法:
  python scrapers/fs168_clean.py [--tid N] [--limit N] [--force]
断点续传: posts_clean 已有的 tid 跳过；--force 重跑。
"""
from __future__ import annotations

import gzip
import html as _html
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data' / 'fs168'
RAW = DATA / 'raw'
DB_PATH = DATA / 'fs168.sqlite'

TD_OPEN = re.compile(r'<td class="t_f" id="postmessage_(\d+)">')
POST_DIV = re.compile(r'<div id="post_(\d+)"')
PCT_OPEN = re.compile(r'<div class="pct[ "]', re.I)
QUOTE_MARK = re.compile(r'<div class="quote"[^>]*>', re.I)


# Discuz 编辑痕迹：「本帖最后由 XXX 于 2026-1-1 12:00 编辑」（含无理由/有理由两种尾部）。
# 2026-11-26 实测 posts_clean 里 15.7 万行残留；龙坛线（PHPWind）无此形态。
DISCUZ_EDIT = re.compile(r"^[^\n]*本帖最后由[^\n]*编辑[^\n]*$", re.M)


def strip_attach_tips(s: str) -> str:
    """删除游客附件提示块（<div class="attach_nopermission">…</div>，按 div 配对取尾）。"""
    out = []
    pos = 0
    tip_open = re.compile(r'<div class="attach_nopermission', re.I)
    tag = re.compile(r"<div\b|</div", re.I)
    while True:
        m = tip_open.search(s, pos)
        if not m:
            out.append(s[pos:])
            return "".join(out)
        out.append(s[pos:m.start()])
        depth, i = 1, m.end()
        while i < len(s) and depth > 0:
            t = tag.search(s, i)
            if not t:
                i = len(s)
                break
            depth += -1 if t.group(0).lower().startswith("</") else 1
            i = t.end()
        close = s.find(">", i - 1)
        pos = close + 1 if close >= 0 else i
SCRIPT_STYLE = re.compile(r"<(script|style)\b[\s\S]*?</\1>", re.I)
HIDDEN = re.compile(r'<[a-z]+[^>]*display\s*:\s*none[^>]*>[\s\S]*?</[a-z]+>', re.I)
IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
IMG_SRC = re.compile(r'src="([^"]+)"', re.I)
BR = re.compile(r"<br\s*/?>", re.I)
BLOCK_END = re.compile(r"</(p|div|li|h[1-6]|tr|table|blockquote|td)>", re.I)
ANY_TAG = re.compile(r"<[^>]+>")
SPACES = re.compile(r"[ \t\u3000]+")
NEWLINES = re.compile(r"\n{3,}")

DDL = """
CREATE TABLE IF NOT EXISTS posts_clean (
  tid INTEGER, pid TEXT, content_clean TEXT, image_count INTEGER,
  PRIMARY KEY (tid, pid)
);
CREATE TABLE IF NOT EXISTS images (
  tid INTEGER, pid TEXT, position_index INTEGER, image_id TEXT, url TEXT,
  download_status TEXT DEFAULT 'SKIPPED_PENDING_AUTHORIZATION',
  local_path TEXT, sha256 TEXT, width INTEGER, height INTEGER,
  license_note TEXT,
  PRIMARY KEY (tid, pid, position_index)
);
"""


def image_id_from_url(url: str) -> str:
    name = url.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[0]


def _td_span(h: str, open_end: int) -> int:
    """内容 td 的配对 </td> 位置（按 <td 嵌套计数，正文里引表格时不错切）。"""
    depth = 1
    i = open_end
    tag = re.compile(r"<td\b|</td", re.I)
    while i < len(h) and depth > 0:
        m = tag.search(h, i)
        if not m:
            return len(h)
        depth += -1 if m.group(0).lower().startswith("</") else 1
        i = m.end()
    close = h.find(">", i - 1)
    return close + 1 if close >= 0 else i


def clean_post_html(raw: str) -> tuple[str, list[dict]]:
    """单楼清洗 → (正文, 图片列表[{position_index, image_id, url}])。"""
    s = raw
    # 步骤1：删游客附件提示块（必须先于抽文本，否则整段 CTA 混入正文）
    s = strip_attach_tips(s)
    # 步骤2：删 script/style
    s = SCRIPT_STYLE.sub("", s)
    # 步骤3：删隐藏元素
    s = HIDDEN.sub("", s)
    # 步骤4：quote 块开头打标记
    s = QUOTE_MARK.sub("\n【引用】", s)
    # 步骤4b：删游客"登录/注册后可看大图"链接（aimg 占位符旁的固定噪声，实测每图一条）
    s = re.sub(r'<a href="member\.php\?mod=logging[^>]*>[^<]*</a>', "", s, flags=re.I)
    # 步骤5：图片 → 占位符（附件图登记，表情/懒加载图删除）
    images: list[dict] = []

    def _img(m: re.Match) -> str:
        src_m = IMG_SRC.search(m.group(0))
        src = src_m.group(1) if src_m else ""
        if "/data/attachment/" not in src:
            return ""          # 表情、按钮、懒加载占位图：丢弃
        images.append({"position_index": len(images) + 1,
                       "image_id": image_id_from_url(src), "url": src})
        return f"\n[[IMG:{len(images)}:{images[-1]['image_id']}]]\n"

    s = IMG_TAG.sub(_img, s)
    # 步骤6：块级标签 → 换行
    s = BR.sub("\n", s)
    s = BLOCK_END.sub("\n", s)
    # 步骤7：剥全部残余标签
    s = ANY_TAG.sub("", s)
    # 步骤8：实体反转义 + 空白归一化
    s = _html.unescape(s)
    s = SPACES.sub(" ", s)
    s = NEWLINES.sub("\n\n", s)
    # 步骤9：Discuz 编辑痕迹与 NBSP（2026-11-26：实测 15.7 万行残留）
    s = DISCUZ_EDIT.sub("", s)
    s = s.replace("\u00a0", " ")
    return s.strip(), images


def assert_clean(s: str) -> list[str]:
    bad: list[str] = []
    if "<" in s:
        bad.append("angle_bracket")
    if "javascript" in s.lower():
        bad.append("js_fragment")
    if "attach_nopermission" in s:
        bad.append("guest_tips")
    if "本帖最后由" in s:
        bad.append("discuz_edit_mark")
    if "\u00a0" in s:
        bad.append("nbsp")
    return bad


def _div_span(h: str, open_end: int) -> int:
    """div 的配对 </div> 之后位置。"""
    depth = 1
    i = open_end
    tag = re.compile(r"<div\b|</div", re.I)
    while i < len(h) and depth > 0:
        m = tag.search(h, i)
        if not m:
            return len(h)
        depth += -1 if m.group(0).lower().startswith("</") else 1
        i = m.end()
    close = h.find(">", i - 1)
    return close + 1 if close >= 0 else i


def _floor_content(h: str, floor_start: int, floor_end: int) -> str | None:
    """楼内正文抽取：优先 td t_f 形态，兜底 pct div 形态（老模板/私密帖页实测）。"""
    m = TD_OPEN.search(h, floor_start, floor_end)
    if m:
        ce = _td_span(h, m.end())
        return h[m.end():ce]
    m2 = PCT_OPEN.search(h, floor_start, floor_end)
    if m2:
        gt = h.find(">", m2.end())             # 开标签可能还有后续属性，先吃到本标签的 '>'
        ce = _div_span(h, gt + 1)
        return h[gt + 1:ce]
    return None


def clean_thread(con: sqlite3.Connection, tid: int) -> tuple[int, int]:
    pages = sorted(RAW.glob(f"{tid}/p*.html.gz"),
                   key=lambda p: int(re.search(r"p(\d+)", p.name).group(1)))
    if not pages:
        return 0, 0
    n_posts = n_imgs = 0
    for p in pages:
        h = gzip.open(p, "rt", encoding="utf-8", errors="replace").read()
        posts = list(POST_DIV.finditer(h))
        for k, m in enumerate(posts):
            pid = m.group(1)
            floor_end = posts[k + 1].start() if k + 1 < len(posts) else len(h)
            raw = _floor_content(h, m.end(), floor_end)
            if raw is None:
                continue
            lt, gt = raw.rfind("<"), raw.rfind(">")
            if lt > gt:
                raw = raw[:lt]                     # 半截标签修剪
            text, images = clean_post_html(raw)
            bad = assert_clean(text)
            if bad:
                print(f"  [warn] tid={tid} pid={pid} 清洗残留: {bad}")
            con.execute("INSERT OR REPLACE INTO posts_clean VALUES (?,?,?,?)",
                        (tid, pid, text, len(images)))
            for im in images:
                # 只覆盖解析得到的元数据列；已下载图的 download_status / local_path /
                # sha256 / width / height 必须保留，否则重清洗会把已下图打回待下载。
                con.execute(
                    "INSERT INTO images (tid, pid, position_index, image_id, url, download_status) "
                    "VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(tid, pid, position_index) DO UPDATE SET "
                    "image_id=excluded.image_id, url=excluded.url",
                    (tid, pid, im["position_index"], im["image_id"],
                     im["url"], "SKIPPED_PENDING_AUTHORIZATION"))
            n_posts += 1
            n_imgs += len(images)
    return n_posts, n_imgs


def main(argv: list[str]) -> None:
    tid_filter = int(argv[argv.index("--tid") + 1]) if "--tid" in argv else None
    limit = int(argv[argv.index("--limit") + 1]) if "--limit" in argv else None
    force = "--force" in argv

    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA busy_timeout=30000")
    con.executescript(DDL)
    done = {r[0] for r in con.execute("SELECT DISTINCT tid FROM posts_clean")}
    rows = con.execute(
        "SELECT DISTINCT tid FROM posts ORDER BY tid").fetchall()
    targets = [r[0] for r in rows if tid_filter is None or r[0] == tid_filter]
    if not force:
        targets = [t for t in targets if t not in done]
    if limit:
        targets = targets[:limit]
    print(f"待清洗帖子: {len(targets)}（已完成 {len(done)}）", flush=True)

    t0 = time.time()
    n_posts = n_imgs = 0
    for k, tid in enumerate(targets, 1):
        p, i = clean_thread(con, tid)
        n_posts += p
        n_imgs += i
        con.commit()
        if k % 500 == 0:
            rate = k / (time.time() - t0)
            print(f"  进度 {k}/{len(targets)}  楼层 {n_posts}  图 {n_imgs}  "
                  f"{rate:.1f} 帖/s", flush=True)
    print(f"完成: {len(targets)} 帖 / {n_posts} 楼 / {n_imgs} 图，"
          f"耗时 {time.time() - t0:.0f}s")
    con.close()


if __name__ == "__main__":
    main(sys.argv)
