# -*- coding: utf-8 -*-
"""§7.4 衍生资产批处理：marks.geojson + marks_preview.png + 回填 image_asset。

设计取舍（都跟效率有关）：

- **多进程**：分割是纯 CPU 活（单图约 19 ms），10 核机器开 8 个进程，
  16k 张从「串行 5 分钟」压到「并行 40 秒」。进程池按 chunksize=32 派活，减少 IPC。
- **断点续传**：只捞 `marks_geojson_path IS NULL` 的行，跑一半中断也能接着跑。
  想重算就 `--force`。
- **预览按需**：`marks_preview.png` 只给「真的检出标注」的图写。全量 PNG 会把
  16k 张图撑出十几 GB，而没有标注的图看预览也没意义（`--preview all` 可强制全写）。
- **单写者**：worker 只算不写库，主进程每 200 条批量提交一次，避免和正在跑的
  图片下载进程抢 SQLite 写锁。

用法：
    python -m src.pipeline marks [--tid N] [--author-uid N] [--workers N]
                                 [--limit N] [--force] [--preview marks|all|none]
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

from . import marks, ocr

PREVIEW_MAX_SIDE = 900
BATCH_COMMIT = 200


def asset_paths(jpg: Path) -> tuple[Path, Path]:
    """与 .meta.json / .exif.json 同名的兄弟文件。"""
    return jpg.with_suffix('.marks.geojson'), jpg.with_suffix('.marks_preview.png')


def _process_one(task: tuple[str, str, bool, bool]) -> dict[str, Any]:
    """worker：单图分割 → 写文件 → 返回计数。异常不外抛，转成 status=error。"""
    path_str, preview_mode, force, want_ocr = task
    jpg = Path(path_str)
    gj, pv = asset_paths(jpg)
    t0 = time.perf_counter()
    try:
        res = marks.analyze(jpg)
    except Exception as exc:                       # 坏图不该拖垮整批
        return {'path': path_str, 'status': 'error', 'error': f'{type(exc).__name__}: {exc}'}

    feats = res['features']
    if force or not gj.exists():
        doc = marks.to_geojson(res, str(jpg))
        doc['properties']['counts'] = res['counts']
        doc['properties']['extra'] = res['extra']
        gj.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')

    wrote_preview = False
    want = preview_mode == 'all' or (preview_mode == 'marks' and feats)
    if want and (force or not pv.exists()):
        try:
            marks.preview(jpg, res, pv, max_side=PREVIEW_MAX_SIDE)
            wrote_preview = True
        except Exception:
            wrote_preview = False

    ocr_path = None
    if want_ocr and ocr.available():
        oj = jpg.with_suffix('.ocr.json')
        if force or not oj.exists():
            doc = ocr.ocr_image(jpg)
            oj.write_text(json.dumps(ocr.to_json(doc, str(jpg)), ensure_ascii=False),
                          encoding='utf-8')
            ocr_words = len(doc.get('words', []))
        else:
            ocr_words = 0
        ocr_path = str(oj)
    else:
        ocr_words = 0

    return {'path': path_str, 'status': 'ok', 'counts': res['counts'],
            'extra': res['extra'], 'features': len(feats),
            'geojson': str(gj), 'preview': wrote_preview, 'ocr': ocr_path,
            'ocr_words': ocr_words,
            'ms': (time.perf_counter() - t0) * 1000.0}


def select_targets(con: sqlite3.Connection, tid: int | None,
                   author_uid: int | None, limit: int | None,
                   force: bool, ocr_only: bool = False) -> list[tuple[str, str]]:
    """ocr_only=True 时改为「还没做 OCR 的图」，用于只补 ocr.json 的增量跑。"""
    sql = ("SELECT image_id, local_full_path FROM image_asset "
           "WHERE download_status='DONE' AND local_full_path IS NOT NULL")
    args: list[Any] = []
    if ocr_only:
        if not force:
            sql += " AND ocr_json_path IS NULL"
    elif not force:
        sql += " AND marks_geojson_path IS NULL"
    if tid is not None:
        sql += " AND tid=?"
        args.append(tid)
    if author_uid is not None:
        sql += " AND author_uid=?"
        args.append(author_uid)
    sql += " ORDER BY tid, position_index"
    if limit:
        sql += f" LIMIT {int(limit)}"
    rows = con.execute(sql, args).fetchall()
    out = []
    for image_id, path in rows:
        if path and os.path.exists(path):
            out.append((image_id, path))
    return out


def run_batch(con: sqlite3.Connection, targets: Iterable[tuple[str, str]],
              workers: int, preview_mode: str, force: bool,
              want_ocr: bool = False) -> dict[str, Any]:
    tasks = [(path, preview_mode, force, want_ocr) for _, path in targets]
    by_path = {path: image_id for image_id, path in targets}
    stats = {'total': len(tasks), 'ok': 0, 'error': 0, 'yellow': 0, 'cyan': 0,
             'white': 0, 'with_marks': 0, 'previews': 0, 'ocr_docs': 0,
             'ocr_words': 0, 'errors': []}
    if not tasks:
        return stats

    con.execute('PRAGMA busy_timeout=30000')
    t0 = time.perf_counter()
    buf: list[tuple[Any, ...]] = []

    def flush() -> None:
        if not buf:
            return
        con.executemany(
            "UPDATE image_asset SET marks_yellow_count=?, marks_white_count=?, "
            "marks_cyan_count=?, marks_geojson_path=?, "
            "ocr_json_path=COALESCE(?, ocr_json_path) WHERE image_id=?", buf)
        con.commit()
        buf.clear()

    with ProcessPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_process_one, t) for t in tasks]
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            image_id = by_path.get(r['path'])
            if r['status'] != 'ok':
                stats['error'] += 1
                if len(stats['errors']) < 10:
                    stats['errors'].append(r)
                continue
            c = r['counts']
            stats['ok'] += 1
            stats['yellow'] += c['yellow']
            stats['cyan'] += c['cyan']
            stats['white'] += c['white']
            stats['with_marks'] += 1 if r['features'] else 0
            stats['previews'] += 1 if r['preview'] else 0
            if r.get('ocr'):
                stats['ocr_docs'] += 1
                stats['ocr_words'] += r.get('ocr_words', 0)
            if image_id:
                buf.append((c['yellow'], c['white'], c['cyan'], r['geojson'],
                            r.get('ocr'), image_id))
            if len(buf) >= BATCH_COMMIT:
                flush()
            if done % 500 == 0 or done == len(tasks):
                rate = done / max(time.perf_counter() - t0, 1e-6)
                left = (len(tasks) - done) / max(rate, 1e-6)
                print(f'  ... {done}/{len(tasks)} ok={stats["ok"]} err={stats["error"]} '
                      f'{rate:.0f} 张/秒 预计剩余 {left:.0f}s', flush=True)
    flush()
    stats['elapsed_s'] = round(time.perf_counter() - t0, 1)
    return stats
