#!/bin/bash
# 立即执行的并行链：精华区全作者发现 → 深采 → 解析 → 增量图片 → 报告
# 与图片下载进程共享令牌桶（config.rate_limit.shared_bucket_file），合计 ≤0.5 req/s。
set -u
cd "$(dirname "$0")/.."
LOG=logs/chain_digest.log

echo "[chain-now] === 阶段1: 精华区全作者发现 === $(date '+%F %T')" >> "$LOG"
.venv/bin/python -m src.pipeline discover_digest >> "$LOG" 2>&1

NEW=$(sqlite3 data/fs.sqlite "SELECT COUNT(*) FROM thread_index WHERE discover_source LIKE '%digest_all%' AND crawl_status='PENDING';")
echo "[chain-now] 发现新帖: $NEW $(date '+%F %T')" >> "$LOG"

if [ "$NEW" -gt 0 ]; then
  echo "[chain-now] === 阶段2: 深采精华区新帖 === $(date '+%F %T')" >> "$LOG"
  .venv/bin/python -m src.pipeline crawl >> "$LOG" 2>&1
  echo "[chain-now] === 阶段3: 解析入库 === $(date '+%F %T')" >> "$LOG"
  .venv/bin/python -m src.pipeline reparse >> "$LOG" 2>&1
fi

echo "[chain-now] === 阶段4: 等待独立图片进程结束后补增量图片 === $(date '+%F %T')" >> "$LOG"
while ps aux | grep -q "[s]rc.pipeline images"; do sleep 120; done
.venv/bin/python -m src.pipeline images >> "$LOG" 2>&1

echo "[chain-now] === 阶段5: 质检报告 === $(date '+%F %T')" >> "$LOG"
.venv/bin/python -m src.pipeline report >> "$LOG" 2>&1
echo "[chain-now] 全链完成 $(date '+%F %T')" >> "$LOG"
