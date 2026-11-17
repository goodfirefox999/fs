# -*- coding: utf-8 -*-
"""fengshui-168.com 图片下载器（受托人授权门控，与论坛一 images 命令同模式）。

合规口径:
- robots.txt `Disallow: /data/`，图片默认只登记不下载（download_status='SKIPPED_PENDING_AUTHORIZATION'）。
- 2026-11-04 委托人在会话中明确授权下载（"图片也要下载"）。本脚本仅在该授权下运行，
  打印醒目提示并 sleep(5)；代码中不存在自动提升授权的逻辑。
- 限速: 与深采同一 pace()（0.5 req/s，全站单桶），串行下载（并发=1）。
- 用途: 个人研究，不公开分发。license_note 同站内约定。

产出:
  data/fs168/images/{tid}/{position_index:02d}_{image_id}.jpg
  images 表: download_status / local_path / sha256 / width / height

用法:
  python scrapers/fs168_images.py [--limit N] [--force-failed]
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / 'scrapers'))
from fs168_digest import DATA, UA, load_session, pace, refresh_cookies_from_tabbit  # noqa: E402

DB_PATH = DATA / 'fs168.sqlite'
IMAGES_DIR = DATA / 'images'
LICENSE = '个人研究用途，不公开分发、不再传播。版权归原作者（天機易學論壇原作者）所有。'

CHALLENGE_MARKS = ('Just a moment', 'cf-challenge', 'challenge-platform', '_cf_chl')


def fetch_bytes(url: str, _refreshed: bool = False) -> tuple[bytes | None, str]:
    """返回 (数据, 状态)。状态: OK / DEAD(站点明确无此图) / CHALLENGE / ERROR。

    状态码用唯一标记解析：JPEG 等二进制体尾部可能含 \\n，不能按最后一个换行切。"""
    s = load_session()
    p = subprocess.run(
        ['curl', '-sS', '-L', '-m', '25', '--compressed', '-A', s.get('ua', UA),
         '-H', f"Cookie: {s.get('cookie', '')}", '-w', '\n__FS_CODE__%{http_code}', '-o', '-', url],
        capture_output=True, timeout=40)
    out = p.stdout
    i = out.rfind(b'__FS_CODE__')
    if i < 0:
        return None, 'ERROR'
    body = out[:i]
    try:
        code = int(out[i + len(b'__FS_CODE__'):].strip())
    except ValueError:
        code = 0
    if code == 200 and len(body) > 500 and not any(m.encode() in body[:2000] for m in CHALLENGE_MARKS):
        return body, 'OK'
    if code in (403, 503) or any(m.encode() in body[:2000] for m in CHALLENGE_MARKS):
        if not _refreshed:
            refresh_cookies_from_tabbit()
            return fetch_bytes(url, _refreshed=True)
        return None, 'CHALLENGE'
    if code in (404, 410):
        return None, 'DEAD'
    return None, 'ERROR'


def main(argv: list[str]) -> None:
    print('=' * 60)
    print('警告：robots.txt 禁止抓取 /data/ 目录（图片附件）。')
    print('继续执行表示使用者已确认获得站方授权（2026-11-04 委托人明确授权）。')
    print('5 秒后开始……')
    print('=' * 60, flush=True)
    time.sleep(5)

    limit = int(argv[argv.index('--limit') + 1]) if '--limit' in argv else 10 ** 9
    retry_failed = '--force-failed' in argv

    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("""CREATE TABLE IF NOT EXISTS images (
        tid INTEGER, pid TEXT, position_index INTEGER, image_id TEXT, url TEXT,
        download_status TEXT DEFAULT 'SKIPPED_PENDING_AUTHORIZATION',
        local_path TEXT, sha256 TEXT, width INTEGER, height INTEGER,
        license_note TEXT,
        PRIMARY KEY (tid, pid, position_index))""")
    statuses = ('SKIPPED_PENDING_AUTHORIZATION', 'PENDING') + (('FAILED',) if retry_failed else ())
    ph = ','.join('?' * len(statuses))
    rows = con.execute(
        f"SELECT tid, pid, position_index, image_id, url FROM images "
        f"WHERE download_status IN ({ph}) AND url != '' ORDER BY tid, position_index LIMIT ?",
        (*statuses, limit)).fetchall()
    print(f'待下载图片: {len(rows)}', flush=True)

    ok = dead = err = 0
    t0 = time.time()
    for k, (tid, pid, pos, image_id, url) in enumerate(rows, 1):
        tid_dir = IMAGES_DIR / str(tid)
        tid_dir.mkdir(parents=True, exist_ok=True)
        dest = tid_dir / f"{pos:02d}_{image_id}.jpg"
        data, status = fetch_bytes(url)
        if status == 'OK':
            try:
                from PIL import Image
                import io
                dest.write_bytes(data)
                with Image.open(io.BytesIO(data)) as im:
                    w, h = im.size
                con.execute(
                    "UPDATE images SET download_status='DONE', local_path=?, sha256=?, "
                    "width=?, height=?, license_note=? WHERE tid=? AND pid=? AND position_index=?",
                    (str(dest), hashlib.sha256(data).hexdigest(), w, h, LICENSE, tid, pid, pos))
                ok += 1
            except Exception:
                dest.unlink(missing_ok=True)
                con.execute("UPDATE images SET download_status='FAILED' WHERE tid=? AND pid=? AND position_index=?",
                            (tid, pid, pos))
                err += 1
        else:
            # 外站图床（非本站域名）返回 200 HTML 错误页时 PIL 校验必败——与论坛一同口径，
            # 标记 EXTERNAL_UNAVAILABLE 放弃，不再反复打扰第三方
            host_ok = 'fengshui-168.com' in url
            new_status = ('DEAD' if status == 'DEAD'
                          else 'FAILED' if (status == 'ERROR' and host_ok)
                          else 'EXTERNAL_UNAVAILABLE' if not host_ok else 'FAILED')
            con.execute("UPDATE images SET download_status=? WHERE tid=? AND pid=? AND position_index=?",
                        (new_status, tid, pid, pos))
            dead += status == 'DEAD'
            err += status != 'DEAD'
            if status == 'CHALLENGE' and k < len(rows):
                print('  [质询未解除，跳过后续以免无效请求]', flush=True)
                break
        con.commit()
        if k % 50 == 0:
            rate = k / max(time.time() - t0, 1)
            print(f'... {k}/{len(rows)} ok={ok} dead={dead} err={err} {rate:.2f} 图/s', flush=True)
        pace()
    con.commit()
    print(f'图片下载完成: ok={ok} dead={dead} err={err}', flush=True)
    con.close()


if __name__ == '__main__':
    main(sys.argv)
