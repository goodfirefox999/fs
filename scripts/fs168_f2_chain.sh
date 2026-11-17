#!/bin/bash
set -u
cd "$(dirname "$0")/.."
LOG=data/fs168/f2_chain.log
echo "[f2] 等待索引扫描结束… $(date '+%F %T')" >> "$LOG"
while ps aux | grep -q "[f]s168_digest.py"; do sleep 60; done
echo "[f2] 扫描结束，重建排名 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_rank.py >> "$LOG" 2>&1
echo "[f2] 启动深采 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py >> "$LOG" 2>&1
echo "[f2] 深采完成 $(date '+%F %T')" >> "$LOG"
