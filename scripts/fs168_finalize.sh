#!/bin/bash
set -u
cd "$(dirname "$0")/.."
LOG=data/fs168/f3_chain.log
while ps aux | grep -q "[f]s168_threads.py crawl"; do sleep 30; done
echo "[fin] 用修正后的页序重建全部楼层 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py reparse >> "$LOG" 2>&1
.venv/bin/python scrapers/fs168_threads.py gaps >> "$LOG" 2>&1
echo "[fin] 完成 $(date '+%F %T')" >> "$LOG"
