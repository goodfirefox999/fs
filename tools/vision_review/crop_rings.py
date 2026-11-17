# -*- coding: utf-8 -*-
"""黄圈待审图预处理：圈局部裁剪放大 + 批处理清单生成。

输入: data/fs.sqlite image_asset (marks_yellow_count>0) + 同名 .marks.geojson
输出:
  data/review/crops/{tid}/{stem}_r{i}.png   每个黄圈一张放大裁剪图（周边留 2.2 倍直径上下文）
  data/review/ring_manifest.jsonl           每图一行，供读图审校批处理消费

裁剪+放大依据: VLM 输入会被降采样（resolution curse），1100px 原图里 15~30px 的圈内
小字直接读必糊；裁出局部放大到 ~640px 恢复有效分辨率。
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np

BASE = Path(__file__).resolve().parents[2]   # tools/vision_review/x.py → 项目根
os.chdir(BASE)                               # 统一相对路径，规避中文绝对路径的兼容问题
DB = Path('data') / 'fs.sqlite'
CROPS = BASE / 'data' / 'review' / 'crops'
MANIFEST = BASE / 'data' / 'review' / 'ring_manifest.jsonl'


def rings_of(gj_path: Path) -> list[dict[str, Any]]:
    """从 marks.geojson 取黄色环状标注（Point + shape=ring/ellipse）。"""
    try:
        d = json.loads(gj_path.read_text())
    except Exception:
        return []
    feats = d.get('features', []) if isinstance(d, dict) else d
    out: list[dict[str, Any]] = []
    for f in feats:
        if f.get('color') != 'yellow':
            continue
        props = f.get('properties', {})
        if props.get('shape') not in ('ring', 'ellipse'):
            continue
        coords = f.get('geometry', {}).get('coordinates') or [None]
        if not coords or coords[0] is None:
            continue
        out.append({'cx': round(float(coords[0]), 1), 'cy': round(float(coords[1]), 1),
                    'd': float(props.get('diameter_px') or 20),
                    'zone': props.get('zone', 'content'),
                    'uncertain': bool(props.get('uncertain', False))})
    return out


def crop_ring(bgr: np.ndarray, cx: float, cy: float, d: float) -> np.ndarray | None:
    H, W = bgr.shape[:2]
    m = max(2.2 * d, 45.0)
    x0, x1 = max(0, int(cx - m)), min(W, int(cx + m))
    y0, y1 = max(0, int(cy - m)), min(H, int(cy + m))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    roi = bgr[y0:y1, x0:x1]
    scale = min(10.0, max(2.0, 640.0 / max(roi.shape[:2])))
    return cv2.resize(roi, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def main(limit: int | None = None) -> None:
    try:
        con = sqlite3.connect(str(DB))
    except sqlite3.OperationalError:
        con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)   # 只读兜底
    rows = con.execute(
        "SELECT image_id, tid, local_full_path, caption_before, caption_after "
        "FROM image_asset WHERE marks_yellow_count>0 ORDER BY tid, position_index"
    ).fetchall()
    con.close()
    CROPS.mkdir(parents=True, exist_ok=True)
    n_crops = 0
    with MANIFEST.open('w', encoding='utf-8') as mf:
        for image_id, tid, jpg_path, cap_b, cap_a in rows:
            jpg = Path(jpg_path)
            if not jpg.exists():
                continue
            rings = rings_of(jpg.with_name(jpg.stem + '.marks.geojson'))
            if not rings:
                continue
            bgr = cv2.imread(str(jpg), cv2.IMREAD_COLOR)
            if bgr is None:
                continue
            outdir = CROPS / str(tid)
            outdir.mkdir(parents=True, exist_ok=True)
            crops = []
            for i, r in enumerate(rings):
                roi = crop_ring(bgr, r['cx'], r['cy'], r['d'])
                if roi is None:
                    continue
                p = outdir / f"{jpg.stem}_r{i}.png"
                cv2.imwrite(str(p), roi)
                crops.append({'ring_index': i, 'path': str(p), **r})
                n_crops += 1
            preview = jpg.with_name(jpg.stem + '.marks_preview.png')
            ocrj = jpg.with_suffix('.ocr.json')
            ocr_text = ''
            if ocrj.exists():
                try:
                    ocr_text = json.loads(ocrj.read_text()).get('text', '')
                except Exception:
                    pass
            rec = {'image_id': image_id, 'tid': tid, 'jpg': str(jpg),
                   'preview': str(preview) if preview.exists() else None,
                   'caption_before': cap_b, 'caption_after': cap_a,
                   'tesseract_text': ocr_text, 'rings': crops}
            mf.write(json.dumps(rec, ensure_ascii=False) + '\n')
            if limit and n_crops >= limit:
                break
    print('manifest records:', sum(1 for _ in MANIFEST.open()), 'crops:', n_crops)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
