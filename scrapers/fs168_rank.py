# -*- coding: utf-8 -*-
"""F2 价值排序：从标题索引生成深采清单 f2_list.csv"""
import math
import sqlite3
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / 'data' / 'fs168'
con = sqlite3.connect(DATA / 'fs168.sqlite')
con.row_factory = sqlite3.Row
rows = con.execute("""
SELECT tid, fid, board, title, views, replies, has_image, tag,
  CASE board
    WHEN '陰陽宅风水实例' THEN 3.0 WHEN '巒頭' THEN 2.0 WHEN '擇日' THEN 2.0
    WHEN '风水理气' THEN 1.5 WHEN '四大局三合專題' THEN 1.5 WHEN '天文历算与风水' THEN 1.2
    WHEN '风水综合版' THEN 1.0 ELSE 0.3 END AS bw,
  (CASE WHEN title LIKE '%反饋%' OR title LIKE '%反馈%' THEN 4 ELSE 0 END
   + CASE WHEN title LIKE '%應驗%' OR title LIKE '%应验%' THEN 4 ELSE 0 END
   + CASE WHEN title LIKE '%葬後%' OR title LIKE '%葬后%' THEN 3 ELSE 0 END
   + CASE WHEN title LIKE '%祖%' THEN 2 ELSE 0 END
   + CASE WHEN title LIKE '%名墓%' OR title LIKE '%古墓%' THEN 2 ELSE 0 END
   + CASE WHEN title LIKE '%考%' THEN 1 ELSE 0 END
   + CASE WHEN title GLOB '*坐*向*' THEN 3 ELSE 0 END
   + CASE WHEN title LIKE '%龍%' OR title LIKE '%龙%' THEN 1 ELSE 0 END
   + CASE WHEN tag IN ('名墓考證','陰宅勘驗','陽宅勘驗','龍局賞析','尋龍點穴','古師鈐記') THEN 3 ELSE 0 END) AS kw
FROM threads WHERE views IS NOT NULL AND views != tid
""").fetchall()
scored = []
for r in rows:
    views, reps = r['views'] or 0, r['replies'] or 0
    s = r['bw'] * (math.log10(views + 10) * 2 + math.log10(reps + 1) * 1.5
                   + r['kw'] * 2 + (2 if r['has_image'] else 0))
    scored.append((s, r['tid'], r['fid'], r['title'] or '', views, reps,
                   r['has_image'], r['tag'] or ''))
scored.sort(reverse=True)

# T2 政策：A 层＝全部带案例标签的帖（分類即 taxonomy，不占配额）；
# B 层＝各板块按价值分补足配额。
quota = {43: 750, 39: 400, 40: 250, 47: 250, 105: 100, 106: 100, 41: 150}
total_cap = 5500
picked, used, seen = [], {}, set()
for s, tid, fid, title, views, reps, has_img, tag in scored:
    if tid in seen:
        continue
    tier_a = bool(tag)
    if not tier_a and (fid not in quota or used.get(fid, 0) >= quota[fid]):
        continue
    if not tier_a:
        used[fid] = used.get(fid, 0) + 1
    seen.add(tid)
    picked.append((tid, fid, round(s, 1), title[:44], views, reps, has_img, tag))
    if len(picked) >= total_cap:
        break
with open(DATA / 'f2_list.csv', 'w', encoding='utf-8') as f:
    f.write('rank,tid,fid,score,title,views,replies,has_image,tag\n')
    for i, p in enumerate(picked, 1):
        f.write(f'{i},{p[0]},{p[1]},{p[2]},"{p[3]}",{p[4]},{p[5]},{p[6]},{p[7]}\n')
n_tag = sum(1 for p in picked if p[7])
done = {r[0] for r in con.execute("SELECT tid FROM threads WHERE crawl_status='DONE'")}
todo = [p for p in picked if p[0] not in done]
print(f'清单: {len(picked)} 帖（带标签 {n_tag}）| 待新采 {len(todo)} | '
      f'板块分布: {used} | 含图: {sum(p[6] for p in picked)}')
