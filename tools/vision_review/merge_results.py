# -*- coding: utf-8 -*-
"""合并各审校批次的 JSONL 结果 → ring_review.csv + 统计。

输入: data/review/results/slice_*_results.jsonl（每 ring 一行）
对照: data/review/ring_manifest.jsonl（应有 ring 全集）
输出:
  data/review/ring_review.csv        人工可读汇总（与 rings_ge3.csv 同风格的审查口径）
  data/review/missing_rings.txt      清单有而结果缺失的 ring（应為空）
  stdout 统计摘要
用法:
  python tools/vision_review/merge_results.py [--db]   # --db 额外写入 fs.sqlite 表 ring_review
"""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RESULTS = BASE / 'data' / 'review' / 'results'
MANIFEST = BASE / 'data' / 'review' / 'ring_manifest.jsonl'
CSV_OUT = BASE / 'data' / 'review' / 'ring_review.csv'
MISSING_OUT = BASE / 'data' / 'review' / 'missing_rings.txt'

VALID_VERDICTS = {'real_annotation', 'false_positive', 'uncertain'}
CSV_COLS = ['tid', 'image_id', 'ring_index', 'diameter_px', 'verdict', 'false_reason',
            'text_inside', 'text_adjacent', 'semantic_role', 'confidence', 'evidence', 'crop']


def main(write_db: bool = False) -> None:
    # 期望全集
    expect: dict[tuple[str, int], dict] = {}
    for line in MANIFEST.open(encoding='utf-8'):
        r = json.loads(line)
        for ring in r['rings']:
            expect[(r['image_id'], ring['ring_index'])] = {
                'tid': r['tid'], 'd': ring['d'], 'crop': ring['path']}

    got: dict[tuple[str, int], dict] = {}
    bad_lines = 0
    files = sorted(RESULTS.glob('slice_*_results.jsonl'))
    if not files:
        sys.exit('没有任何 slice_*_results.jsonl，先等批次跑完')
    for f in files:
        for line in f.open(encoding='utf-8'):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                key = (r['image_id'], int(r['ring_index']))
                if r.get('verdict') not in VALID_VERDICTS:
                    raise ValueError('bad verdict')
                got[key] = r
            except Exception:
                bad_lines += 1

    missing = [k for k in expect if k not in got]
    extra = [k for k in got if k not in expect]
    MISSING_OUT.write_text(
        '\n'.join(f'{k[0]} r{k[1]}' for k in sorted(missing)) or '(无缺失)', encoding='utf-8')

    rows = []
    for (image_id, ri), meta in sorted(expect.items(), key=lambda kv: (kv[1]['tid'], kv[0][0])):
        g = got.get((image_id, ri), {})
        rows.append({
            'tid': meta['tid'], 'image_id': image_id, 'ring_index': ri,
            'diameter_px': meta['d'],
            'verdict': g.get('verdict', 'MISSING'),
            'false_reason': g.get('false_reason') or '',
            'text_inside': g.get('text_inside') or '',
            'text_adjacent': g.get('text_adjacent') or '',
            'semantic_role': g.get('semantic_role') or '',
            'confidence': g.get('confidence', ''),
            'evidence': g.get('evidence', ''),
            'crop': meta['crop'],
        })
    with CSV_OUT.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLS)
        w.writeheader()
        w.writerows(rows)

    n = len(rows)
    cnt = {'real_annotation': 0, 'false_positive': 0, 'uncertain': 0, 'MISSING': 0}
    reasons: dict[str, int] = {}
    texted = 0
    roles: dict[str, int] = {}
    for r in rows:
        cnt[r['verdict']] += 1
        if r['false_reason']:
            reasons[r['false_reason']] = reasons.get(r['false_reason'], 0) + 1
        if r['text_inside'] or r['text_adjacent']:
            texted += 1
        if r['semantic_role']:
            roles[r['semantic_role']] = roles.get(r['semantic_role'], 0) + 1
    print(f'覆盖: {len(got)}/{len(expect)} rings（缺 {len(missing)}，多余 {len(extra)}，坏行 {bad_lines}）')
    print(f"真标注: {cnt['real_annotation']}  误检: {cnt['false_positive']}  "
          f"存疑: {cnt['uncertain']}  缺失: {cnt['MISSING']}")
    print('误检原因分布:', reasons)
    print(f'有文字的圈: {texted}；语义归类:', roles)
    print('CSV →', CSV_OUT)

    if write_db and missing == []:
        con = sqlite3.connect(str(BASE / 'data' / 'fs.sqlite'))
        con.execute("""CREATE TABLE IF NOT EXISTS ring_review (
            image_id TEXT, ring_index INTEGER, verdict TEXT, false_reason TEXT,
            text_inside TEXT, text_adjacent TEXT, semantic_role TEXT,
            confidence TEXT, evidence TEXT,
            PRIMARY KEY (image_id, ring_index))""")
        con.executemany(
            "INSERT OR REPLACE INTO ring_review VALUES (?,?,?,?,?,?,?,?,?)",
            [(r['image_id'], r['ring_index'], r['verdict'], r['false_reason'] or None,
              r['text_inside'] or None, r['text_adjacent'] or None,
              r['semantic_role'] or None, r['confidence'] or None, r['evidence'] or None)
             for r in rows if r['verdict'] != 'MISSING'])
        con.commit()
        con.close()
        print('已写入 fs.sqlite 表 ring_review')


if __name__ == '__main__':
    main('--db' in sys.argv)
