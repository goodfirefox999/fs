# -*- coding: utf-8 -*-
"""
fengshui-168.com 帖子深采器（F2）
- 输入: data/fs168/f2_list.csv（价值排序清单）
- 对每帖: 抓全部楼层页 → 原始 HTML gzip 归档 → 解析楼层 → 入库
- 图片: 仅登记 URL/附件元数据（robots.txt Disallow: /data/，图片二进制默认不下载）
- 断点续采: 跳过 threads.crawl_status='DONE'
- reparse 模式: 只用已归档的 raw 页面重建 posts 表，零网络请求
"""
import gzip
import html as _html
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fs168_digest import (DATA, SITE, fetch, init_db, load_session,  # noqa: E402
                          refresh_cookies_from_tabbit)

RAW = DATA / 'raw'
LICENSE = '个人研究用途，不公开分发、不再传播。版权归原作者（天機易學論壇原作者）所有。'

POSTS_DDL = """
CREATE TABLE IF NOT EXISTS posts (
  tid INTEGER, pid TEXT, floor INTEGER,
  author TEXT, uid INTEGER, post_time TEXT,
  content TEXT, images TEXT,
  page INTEGER DEFAULT 1,
  PRIMARY KEY (tid, pid)
);
CREATE INDEX IF NOT EXISTS idx_posts_tid ON posts(tid);
"""

POST_START = re.compile(r'<div id="post_(\d+)"')
ATTACH_URL = re.compile(r'href="([^"]*mod=attachment[^"]*)"[^>]*>([^<]{1,40})</a>')


def init_posts(con: sqlite3.Connection) -> None:
    con.executescript(POSTS_DDL)
    con.commit()


def _read_gz(path: Path) -> str:
    return gzip.open(path, 'rt', encoding='utf-8', errors='replace').read()


def _element(h: str, start: int, tag: str) -> str:
    """从 start 处的 <tag> 起，返回该元素内部 HTML（按同名标签嵌套计数）。"""
    open_at = h.find('>', start)
    if open_at < 0:
        return ''
    i = open_at + 1
    depth = 1
    for m in re.finditer(rf'<{tag}\b[^>]*>|</{tag}\s*>', h[i:], re.I):
        depth += -1 if m.group(0).startswith('</') else 1
        if depth == 0:
            return h[i:i + m.start()]
    return h[i:]


def to_text(block: str) -> str:
    """楼层 HTML → 正文文本（保留换行，登录门控标注为占位）。"""
    s = re.sub(r'<script[\s\S]*?</script>', '', block, flags=re.I)
    s = re.sub(r'<style[\s\S]*?</style>', '', s, flags=re.I)
    s = re.sub(r'<ignore_js_op>[\s\S]*?</ignore_js_op>', ' ', s, flags=re.I)
    s = re.sub(r'<div class="locked">[\s\S]*?</div>', '[回复可见，需登录]', s, flags=re.I)
    s = re.sub(r'<div class="attach_nopermission[\s\S]*?</span>\s*</div>',
               '[附件需登录]', s, flags=re.I)
    s = re.sub(r'<div class="quote">[\s\S]*?<blockquote>', '\n【引用】', s, flags=re.I)
    s = re.sub(r'<br\s*/?>', '\n', s, flags=re.I)
    s = re.sub(r'</(p|div|td|tr|li|h\d)>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = _html.unescape(s)
    s = re.sub(r'\[hide\][\s\S]*?\[/hide\]', '[需登录可见]', s)
    s = re.sub(r'[ \t\u3000\xa0]+', ' ', s)
    s = re.sub(r'\n{3,}', '\n\n', s).strip()
    return s


def parse_thread_page(h: str) -> dict:
    """Discuz X 帖子页 → 楼层列表 + 总页数。"""
    starts = [(m.start(), m.group(1)) for m in POST_START.finditer(h)]
    floors = []
    for k, (pos, pid) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(h)
        chunk = h[pos:end]
        cm = re.search(rf'<td[^>]*id="postmessage_{pid}"', chunk)
        content = to_text(_element(chunk, cm.start(), 'td')) if cm else ''
        # 图片：游客态只有 aid + 附件下载令牌，登录后可见 data/attachment 直链
        imgs: dict[str, dict] = {}
        for m in re.finditer(r'id="aimg_(\d+)_menu"', chunk):
            tail = chunk[m.start():m.start() + 1200]
            nm = re.search(r'<p><strong>([^<]*)</strong>', tail)
            sz = re.search(r'<em class="xg1">\(([^,)]*)', tail)
            ur = re.search(r'href="([^"]*mod=attachment[^"]*)"', tail)
            imgs[m.group(1)] = {
                'aid': m.group(1),
                'name': _html.unescape(nm.group(1)).strip() if nm else '',
                'size': sz.group(1).strip() if sz else '',
                'url': _html.unescape(ur.group(1)) if ur else ''}
        for m in re.finditer(r'<img[^>]*>', chunk):
            tag = m.group(0)
            src_m = re.search(r'src="([^"]+)"', tag)
            aid_m = re.search(r'\baid="(\d+)"', tag)
            if not src_m:
                continue
            src = _html.unescape(src_m.group(1))
            if 'none.gif' in src or 'static/image' in src or 'avatar.php' in src:
                continue
            key = aid_m.group(1) if aid_m else src
            if key in imgs:
                imgs[key].setdefault('src', src)
            else:
                imgs[key] = {'aid': aid_m.group(1) if aid_m else '',
                             'name': '', 'size': '', 'url': '', 'src': src}
        for url in re.findall(r'(?:file|zoomfile)="([^"]*(?:data/attachment|/attachment/)[^"]*)"', chunk):
            imgs.setdefault('direct:' + url, {'aid': '', 'name': '', 'size': '', 'url': _html.unescape(url)})
        for url, label in ATTACH_URL.findall(chunk):
            if any(v.get('url') == _html.unescape(url) for v in imgs.values()):
                continue
            imgs['attach:' + url] = {'aid': '', 'name': _html.unescape(label).strip(),
                                     'size': '', 'url': _html.unescape(url)}
        img_list = list(imgs.values())
        um = re.search(r'<div class="authi">[\s\S]{0,220}?uid=(\d+)"[^>]*>([^<]{1,40})</a>', chunk) \
            or re.search(r'uid=(\d+)"[^>]*class="xi2">([^<]{1,40})</a>', chunk)
        tm = re.search(r'id="authorposton{}"?>?\s*发表于\s*([^<]+)<'.format(pid), chunk) \
            or re.search(r'发表于\s*([0-9]{4}-[0-9]{1,2}-[0-9]{1,2}[^<]*)', chunk)
        floors.append({
            'pid': pid, 'content': content, 'images': img_list,
            'uid': int(um.group(1)) if um else None,
            'author': um.group(2).strip() if um else None,
            'post_time': re.sub(r'\s+', ' ', tm.group(1)).strip() if tm else None,
            'is_op': k == 0,
        })
    # 2026-11-02 修：原正则限定 `class="pg"` 后 900 字符内出现 `<span title="共 N 页"`，
    # 但 Discuz 的大帖分页器先铺 10 个页码链接（每个 ~90 字符）；页数越多，
    # 该 span 越靠后 → 超过 900 就判成「只有 1 页」，于是只抓了 p1。
    # 实测 56 帖（全是回复数百的高价值案例帖）因此漏采 926 页，最大 tid=12995 共 37 页只存 1 页。
    # 注意：不能再退化成裸 `共 N 页`——侧栏「相关帖子」的标题里就有「…共76页」，
    # 会让 tid=253072 这种 1 页帖被判成 76 页。故降级路径必须锁在 pager 容器内。
    mp = (
        re.search(r'<span title="共 (\d+) 页"', h)
        or re.search(r'<span class="pgs"[\s\S]{0,4000}?共\s*(\d+)\s*页', h)
    )
    return {'floors': floors, 'total_pages': int(mp.group(1)) if mp else 1}


def store_thread(con: sqlite3.Connection, tid: int, pages: list[str],
                 page_nums: list[int] | None = None) -> tuple[int, int]:
    """多页 HTML → posts 表；返回 (楼层数, 图片登记数)。"""
    all_floors: dict[str, dict] = {}
    for i, h in enumerate(pages):
        page_no = page_nums[i] if page_nums else i + 1
        for f in parse_thread_page(h)['floors']:
            cur = all_floors.get(f['pid'])
            if cur is None or (cur['content'] == '' and f['content']):
                all_floors[f['pid']] = dict(f, page=page_no)
    ordered = sorted(all_floors.values(), key=lambda x: int(x['pid']))
    n_img = 0
    for floor, f in enumerate(ordered, 1):
        n_img += len(f['images'])
        con.execute(
            'INSERT OR REPLACE INTO posts(tid,pid,floor,author,uid,post_time,content,'
            'images,page) VALUES (?,?,?,?,?,?,?,?,?)',
            (tid, f['pid'], floor, f['author'], f['uid'], f['post_time'],
             f['content'], json.dumps(f['images'], ensure_ascii=False), f['page']))
    con.commit()
    return len(ordered), n_img


def archived_pages(tid: int) -> list[str]:
    d = RAW / str(tid)
    if not d.is_dir():
        return []
    files = sorted(d.glob('p*.html.gz'),
                   key=lambda p: int(re.match(r'p(\d+)', p.name).group(1)))
    return [_read_gz(p) for p in files]


def archived_page_nums(tid: int) -> list[int]:
    d = RAW / str(tid)
    if not d.is_dir():
        return []
    return sorted(int(re.match(r'p(\d+)', p.name).group(1)) for p in d.glob('p*.html.gz'))


def reparse(con: sqlite3.Connection) -> int:
    """离线：用归档页重建全部楼层文本，并校正 crawl_status。"""
    tids = [int(p.name) for p in RAW.iterdir() if p.is_dir() and p.name.isdigit()]
    tids.sort()
    tot_f = tot_i = 0
    empty = 0
    for tid in tids:
        pages = archived_pages(tid)
        if not pages:
            continue
        nf, ni = store_thread(con, tid, pages, archived_page_nums(tid))
        tot_f += nf
        tot_i += ni
        if nf == 0:
            empty += 1
        else:
            con.execute("UPDATE threads SET crawl_status='DONE' WHERE tid=?", (tid,))
        if tid % 100 == 0:
            print(f'... reparse {tid} 累计楼层={tot_f} 图={tot_i} 零楼层={empty}', flush=True)
    con.commit()
    print(f'reparse 完成: 帖={len(tids)} 楼层={tot_f} 图片登记={tot_i} 零楼层={empty}', flush=True)
    return tot_f


def gap_report(con: sqlite3.Connection) -> None:
    """已采帖的实际楼层 vs 索引回复数，找出还差尾页的帖。"""
    rows = con.execute("""
        SELECT t.tid, t.replies, COUNT(p.pid) FROM threads t
        LEFT JOIN posts p ON p.tid=t.tid WHERE t.crawl_status='DONE'
        GROUP BY t.tid""").fetchall()
    short = [(r[0], r[1] or 0, r[2]) for r in rows if (r[1] or 0) + 1 > r[2] * 1.0]
    short = [x for x in short if x[1] + 1 - x[2] >= 2]
    print(f'楼层缺口帖: {len(short)}（索引回复数明显大于已存楼层）', flush=True)
    for tid, rep, got in sorted(short, key=lambda x: x[1] - x[2], reverse=True)[:10]:
        print(f'  tid={tid} 回复={rep} 楼层={got}', flush=True)


def crawl_thread(con: sqlite3.Connection, tid: int) -> tuple[int, int]:
    raw_dir = RAW / str(tid)
    raw_dir.mkdir(parents=True, exist_ok=True)
    h1 = fetch(f'{SITE}/forum.php?mod=viewthread&tid={tid}')
    (raw_dir / 'p1.html.gz').write_bytes(gzip.compress(h1.encode('utf-8'), mtime=0))
    # 2026-11-02：原帖被删时站点返回 `提示信息 / 没有找到帖子`（24KB，状态码 200），
    # 无条件写盘会让该帖以 0 楼层混进 DONE（实测 5 帖：71355/72042/104805/132994/160899）。
    # 判据用「有没有楼层 div」而不是文本关键字，兼容改成繁体/异体的提示语。
    if 'id="post_' not in h1:
        con.execute("UPDATE threads SET crawl_status='FAILED', "
                    "error_msg='没有找到帖子（原帖已删或不可见）' WHERE tid=?", (tid,))
        con.commit()
        return 0, 0
    pages = [h1]
    for page in range(2, min(parse_thread_page(h1)['total_pages'], 60) + 1):
        hp = fetch_page(tid, page)
        if hp is None:
            break
        (raw_dir / f'p{page}.html.gz').write_bytes(gzip.compress(hp.encode('utf-8'), mtime=0))
        pages.append(hp)
    nf, ni = store_thread(con, tid, pages)
    con.execute("UPDATE threads SET crawl_status='DONE' WHERE tid=?", (tid,))
    con.commit()
    return nf, ni


def fetch_page(tid: int, page: int) -> str | None:
    """取帖子第 page 页：先规范 URL，再退回 mod 形式；两路都失败返回 None。"""
    for url in (f'{SITE}/thread-{tid}-{page}-1.html',
                f'{SITE}/forum.php?mod=viewthread&tid={tid}&page={page}'):
        try:
            h = fetch(url)
        except RuntimeError:
            continue
        # 2026-11-02：站点会以 HTTP 200 返回 13 字节的 `Access Denied` 页（WAF/防盗链），
        # fetch 只看状态码，于是「拿到的空壳」被当成成功页写盘 →
        # tid=151007 / 163813 的 p2 就是这样变成 0 楼层且无人察觉。
        # 判据：无楼层 div + 体积极小 + 命中 Access Denied 任一即视为失败。
        if len(h) < 3000 or 'Access Denied' in h[:600] or 'id="post_' not in h:
            continue
        return h
    return None


def expected_pages(tid: int) -> int:
    """已归档 p1 声明的总页数。"""
    p1 = RAW / str(tid) / 'p1.html.gz'
    if not p1.exists():
        return 0
    return parse_thread_page(_read_gz(p1))['total_pages']


def fill_gaps(con: sqlite3.Connection, limit: int = 10 ** 9) -> None:
    """补齐已采帖缺失的页（尾页未抓 / 中间页失败 / 空壳页被删后重抓）。

    2026-11-02 改为按「缺哪些页码」而不是「现有几页 + 1」：
    原来 `start = have + 1` 假设页档连续，一旦中间某页失败（如 Access Denied 空壳），
    后面即使有 p3 也会被判成「页齐」，缺口永远补不上。
    """
    tids = [r[0] for r in con.execute(
        'SELECT tid FROM threads WHERE crawl_status IN (\'DONE\',\'FAILED\') ORDER BY tid')]
    todo = []
    for tid in tids:
        nums = set(archived_page_nums(tid))
        want = min(expected_pages(tid), 60) if nums else 1
        missing = [p for p in range(1, max(want, 1) + 1) if p not in nums]
        if missing:
            todo.append((tid, missing))
    todo = todo[:limit]
    print(f'缺口回填: {len(todo)} 帖需补页（缺页合计 '
          f'{sum(len(m) for _, m in todo)}）', flush=True)
    fixed = 0            # 页数补齐的帖
    partial = 0          # 抓了一部分就断了
    failed_pages = 0
    for k, (tid, missing) in enumerate(todo):
        d = RAW / str(tid)
        d.mkdir(parents=True, exist_ok=True)
        if 1 in missing:
            try:
                h1 = fetch(f'{SITE}/forum.php?mod=viewthread&tid={tid}')
                (d / 'p1.html.gz').write_bytes(gzip.compress(h1.encode('utf-8'), mtime=0))
                missing = [p for p in missing if p != 1]
                want = min(parse_thread_page(h1)['total_pages'], 60)
                missing = sorted(p for p in range(2, want + 1)
                                 if p not in set(archived_page_nums(tid)))
            except RuntimeError as e:
                print(f'  tid={tid} p1 FAIL {e}', flush=True)
                continue
        miss = 0
        # 2026-11-02：原来单页失败直接 break 且不打印，日志只写「修复 N/N」，
        # 看上去成功、实际只存了 p1（首轮 56 帖只补成 40 帖，16 帖静默落空）。
        # 改为逐页记录失败；连续 3 页失败才放弃该帖（区分偶发 302 与站点限流）。
        for page in missing:
            if page == 1:
                continue
            hp = fetch_page(tid, page)
            if hp is None:
                miss += 1
                failed_pages += 1
                print(f'  tid={tid} p{page}/{max(missing)} FAIL', flush=True)
                if miss >= 3:
                    print(f'  tid={tid} 连续 {miss} 页失败，放弃该帖', flush=True)
                    break
                continue
            miss = 0
            (d / f'p{page}.html.gz').write_bytes(gzip.compress(hp.encode('utf-8'), mtime=0))
        nf, ni = store_thread(con, tid, archived_pages(tid), archived_page_nums(tid))
        if nf:
            con.execute("UPDATE threads SET crawl_status='DONE', error_msg=NULL WHERE tid=?",
                        (tid,))
            con.commit()
        nums = set(archived_page_nums(tid))
        want = min(expected_pages(tid), 60) if nums else 1
        if all(p in nums for p in range(1, want + 1)):
            fixed += 1
        elif nums:
            partial += 1
        if (k + 1) % 10 == 0:
            print(f'... 缺口 {k+1}/{len(todo)} 页齐={fixed} 半截={partial}', flush=True)
    print(f'缺口回填完成: 页齐 {fixed} / 半截 {partial} / 总 {len(todo)}'
          f'（失败页 {failed_pages}）', flush=True)
    reparse(con)


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'crawl'
    con = init_db()
    init_posts(con)
    if mode == 'reparse':
        reparse(con)
        gap_report(con)
        con.close()
        return
    if mode == 'gaps':
        gap_report(con)
        con.close()
        return
    if mode == 'fill':
        fill_gaps(con, int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 9)
        gap_report(con)
        con.close()
        return
    if mode == 'all':
        # 全量深采：threads 表全部 PENDING（2026-11-04 委托人指示"剩余 40,648 帖继续采集"），
        # 按热度（回复+浏览）降序，价值最高的先采
        tids = [r[0] for r in con.execute(
            "SELECT tid FROM threads WHERE crawl_status='PENDING' "
            "ORDER BY replies + views DESC, tid")]
        src_n = len(tids)
    else:
        limit = int(mode) if mode.isdigit() else 10 ** 9
        import csv
        with open(DATA / 'f2_list.csv', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
        tids = [int(r['tid']) for r in rows][:limit]
        src_n = len(tids)
    done_before = {r[0] for r in con.execute(
        "SELECT tid FROM threads WHERE crawl_status='DONE'")}
    todo = [t for t in tids if t not in done_before]
    print(f'F2 深采: {len(todo)} 帖（来源={"threads全表" if mode == "all" else "价值清单"} {src_n}，'
          f'已完成 {src_n - len(todo)}）', flush=True)
    ok = fail = tot_f = tot_i = 0
    for k, tid in enumerate(todo):
        try:
            nf, ni = crawl_thread(con, tid)
            ok += 1
            tot_f += nf
            tot_i += ni
            if (k + 1) % 20 == 0:
                print(f'... {k+1}/{len(todo)} ok={ok} fail={fail} '
                      f'累计楼层={tot_f} 图={tot_i}', flush=True)
        except Exception as e:
            fail += 1
            print(f'tid={tid} FAIL: {str(e)[:120]}', flush=True)
            try:
                con.execute(
                    "UPDATE threads SET crawl_status='FAILED', error_msg=? WHERE tid=?",
                    (str(e)[:200], tid))
                con.commit()
            except Exception:
                pass
        time.sleep(0.2)
    print(f'F2 完成 ok={ok} fail={fail} 楼层={tot_f} 图={tot_i}', flush=True)
    gap_report(con)
    con.close()


if __name__ == '__main__':
    main()
