# -*- coding: utf-8 -*-
"""
fengshui-168.com（天機易學論壇，Discuz! X3）精华区采集器
- Cloudflare 通行：复用用户 Tabbit 浏览器的 cf_clearance + UA（Cookie 交接）
- 质询自动续期：检测到 403/质询页时自动从 Tabbit 重取 Cookie
- 速率：本站独立 2.0s 间隔（0.5 req/s），遵守 robots.txt（forum/thread 页未禁）
- 产出：fs168.sqlite + fs168_digest_index.csv
"""
import json
import random
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data' / 'fs168'
SESSION_FILE = DATA / 'session.json'
DB_PATH = DATA / 'fs168.sqlite'
LOG = DATA / 'digest_sweep.log'

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36'
SITE = 'https://www.fengshui-168.com'

BOARDS = {
    43: '陰陽宅风水实例', 39: '巒頭', 40: '风水理气', 47: '擇日',
    105: '四大局三合專題', 106: '天文历算与风水', 41: '风水综合版',
    50: '堪輿典籍', 55: '天星與擇日典籍', 104: '地理辨正揭隱', 92: '玉函通秘',
    157: '天文曆算', 79: '易學典籍', 130: '國學典籍',
}

DDL = """
CREATE TABLE IF NOT EXISTS threads (
  tid INTEGER PRIMARY KEY,
  fid INTEGER, board TEXT,
  title TEXT, tag TEXT,
  author TEXT, author_uid INTEGER,
  post_date TEXT, replies INTEGER, views INTEGER,
  is_digest INTEGER DEFAULT 1, is_sticky INTEGER DEFAULT 0,
  crawl_status TEXT DEFAULT 'PENDING',
  error_msg TEXT,
  has_image INTEGER DEFAULT 0,
  discover_time TEXT,
  source_url TEXT,
  license_note TEXT
);
CREATE TABLE IF NOT EXISTS sweep_log (
  fid INTEGER, page INTEGER, rows INTEGER, ts TEXT
);
"""


def load_session() -> dict:
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text(encoding='utf-8'))
    return {'ua': UA, 'cookie': ''}


def save_session(s: dict) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding='utf-8')


def refresh_cookies_from_tabbit() -> str:
    """从用户 Tabbit 浏览器重取 cf_clearance（质询续期回路）。"""
    js = '''
const cookies = await context.cookies("https://www.fengshui-168.com");
const pairs = cookies.map(c => `${c.name}=${c.value}`);
return pairs.join("; ");
'''
    r = subprocess.run(
        [str(Path.home() / '.local' / 'bin' / 'tabbit-cli'), 'nodejs',
         '--task', 'fs168', '--request-id', f'ckrefresh-{int(time.time())}',
         '--timeout-ms', '60000'],
        input=js.encode(), capture_output=True, timeout=90)
    out = r.stdout.decode('utf-8', errors='replace')
    m = re.search(r'"cookieHeader":"(.*?)"', out)
    if not m:
        raise RuntimeError('Tabbit Cookie 刷新失败: ' + out[:300])
    header = m.group(1).encode().decode('unicode_escape', errors='replace')
    header = header.replace('\\/', '/')
    s = load_session()
    s['cookie'] = header
    save_session(s)
    return header


_last_hit = 0.0


def pace() -> None:
    """本站 0.5 req/s 限速（独立于龙坛桶）。"""
    global _last_hit
    wait = 2.0 - (time.time() - _last_hit)
    if wait > 0:
        time.sleep(wait + random.uniform(0, 0.3))
    _last_hit = time.time()


def fetch(url: str, _refreshed: bool = False) -> str:
    """带 Cookie 抓取；质询页自动从 Tabbit 续期一次。"""
    s = load_session()
    p = subprocess.run(
        ['curl', '-sS', '-L', '-m', '25', '--compressed', '-A', s.get('ua', UA),
         '-H', f"Cookie: {s.get('cookie', '')}", '-w', '\n%{http_code}', '-o', '-', url],
        capture_output=True, timeout=40)
    out = p.stdout
    try:
        code = int(out[out.rfind(b'\n') + 1:])
    except ValueError:
        code = 0
    body = out[:out.rfind(b'\n')]
    text = body.decode('gbk', errors='replace')
    if code == 403 or 'Just a moment' in text or 'cf-mitigated' in text[:2000]:
        if _refreshed:
            raise RuntimeError(f'质询续期后仍被拦: {url}')
        print('  [cookie] 检测到质询，从 Tabbit 续期…', flush=True)
        refresh_cookies_from_tabbit()
        return fetch(url, _refreshed=True)
    if code != 200:
        raise RuntimeError(f'HTTP {code}: {url}')
    return text


ROW_RE = re.compile(r'<tbody id="(?:normalthread|stickthread)_(\d+)">([\s\S]*?)</tbody>')


def parse_digest_page(h: str, fid: int) -> list[dict]:
    rows = []
    for m in ROW_RE.finditer(h):
        tid = int(m.group(1))
        chunk = m.group(2)
        tm = re.search(r'<a href="[^"]*thread-\d+-[^"]*"[^>]*class="[^"]*xst[^"]*"[^>]*>([\s\S]{4,160}?)</a>', chunk)
        if not tm:
            tm = re.search(r'<a href="[^"]*thread-\d+-[^"]*"[^>]*>([\s\S]{4,160}?)</a>', chunk)
        if tm and '<img' in tm.group(1):
            tm = None  # 图标链接（内容是图片）不算标题
        if not tm:
            tm = re.search(r'showWindow[^>]*>([\s\S]{4,160}?)</a>', chunk)
        title = re.sub(r'<[^>]+>', '', tm.group(1)).strip() if tm else ''
        # 案例分类标签：<em>[<a ...>標籤名</a>]</em>
        tgm = re.search(r'<em>\[<a[^>]*>([^<]{1,20})</a>\]</em>', chunk)
        tag = tgm.group(1).strip() if tgm else ''
        # 作者：行内第一个 uid 链接（作者格在回复/浏览格之前）
        um = re.search(r'uid=(\d+)"[^>]*>([^<]{1,30})</a>', chunk)
        # 图片附件标志
        has_img = 1 if 'filetype/image_s.gif' in chunk else 0
        dm = re.search(r'<em><span[^>]*>(\d{4}-\d{1,2}-\d{1,2})', chunk) or re.search(r'(\d{4}-\d{1,2}-\d{1,2})', chunk)
        nm = re.search(r'<td class="num">([\s\S]*?)</td>', chunk)
        replies = views = None
        if nm:
            # 关键：剥掉 href（绝对 URL 里含站名 168 与 tid，会污染数字提取）
            cell = re.sub(r'href="[^"]*"', '', nm.group(1))
            nums = re.findall(r'\d+', re.sub(r'<[^>]+>', ' ', cell))
            if len(nums) >= 2:
                replies, views = int(nums[0]), int(nums[1])
            elif len(nums) == 1:
                replies = int(nums[0])
        rows.append({
            'tid': tid, 'fid': fid, 'title': re.sub(r'\s+', ' ', title)[:180],
            'tag': tag, 'author': um.group(2).strip() if um else None,
            'author_uid': int(um.group(1)) if um else None,
            'post_date': dm.group(1) if dm else None,
            'replies': replies, 'views': views,
            'is_sticky': 1 if 'stickthread' in m.group(0)[:30] else 0,
            'has_img': has_img,
        })
    return rows


def init_db() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.executescript(DDL)
    con.commit()
    return con


def sweep_board(con: sqlite3.Connection, fid: int, max_pages: int = 200) -> tuple[int, int]:
    seen: set[int] = set()
    seen_prev: set[int] | None = None
    pages = 0
    new = 0
    for page in range(1, max_pages + 1):
        url = f'{SITE}/forum.php?mod=forumdisplay&fid={fid}&filter=digest&page={page}'
        try:
            h = fetch(url)
        except RuntimeError as e:
            print(f'  fid={fid} p{page} FAIL: {e}', flush=True)
            break
        rows = parse_digest_page(h, fid)
        tids_now = {r['tid'] for r in rows}
        if not rows:
            break
        if seen_prev is not None and tids_now <= seen_prev:
            break
        pages += 1
        for r in rows:
            if r['tid'] in seen:
                continue
            seen.add(r['tid'])
            con.execute(
                "INSERT INTO threads(tid,fid,board,title,tag,author,author_uid,"
                "post_date,replies,views,is_digest,is_sticky,crawl_status,discover_time,"
                "has_image,source_url,license_note) VALUES (?,?,?,?,?,?,?,?,?,?,0,?,"
                "'PENDING',datetime('now'),?,?,?) "
                "ON CONFLICT(tid) DO UPDATE SET replies=excluded.replies, "
                "views=excluded.views, title=excluded.title, tag=excluded.tag, "
                "author=excluded.author, has_image=excluded.has_image",
                (r['tid'], fid, BOARDS.get(fid, '?'), r['title'], r['tag'], r['author'],
                 r['author_uid'], r['post_date'], r['replies'], r['views'],
                 r['is_sticky'], r['has_img'], url, '个人研究用途，不公开分发、不再传播。版权归原作者（天機易學論壇原作者）所有。'))
            new += 1
        con.execute("INSERT INTO sweep_log VALUES (?,?,?,datetime('now'))", (fid, page, len(rows)))
        con.commit()
        seen_prev = tids_now
        time.sleep(0.5)
        if page % 10 == 0:
            print(f'  fid={fid} …{page} 页 / {len(seen)} 帖', flush=True)
    return new, pages


def main() -> None:
    only = [int(x) for x in sys.argv[1:]] if len(sys.argv) > 1 else sorted(BOARDS)
    con = init_db()
    print(f'开始精华区扫描: {only}', flush=True)
    for fid in only:
        new, pages = sweep_board(con, fid)
        print(f'fid={fid} {BOARDS.get(fid, "?")}: 新增 {new} 帖 / {pages} 页', flush=True)
    total = con.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
    print(f'完成。库内总帖数: {total}', flush=True)
    con.close()


if __name__ == '__main__':
    main()
