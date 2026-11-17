#!/bin/bash
set -u
cd "$(dirname "$0")/.."
LOG=data/fs168/t2_chain.log
echo "[t2] 深采 4028 帖 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py crawl >> "$LOG" 2>&1
echo "[t2] 缺口页回填 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py fill >> "$LOG" 2>&1
echo "[t2] 重建楼层 + 核对 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py gaps >> "$LOG" 2>&1
echo "[t2] 全部完成 $(date '+%F %T')" >> "$LOG"
