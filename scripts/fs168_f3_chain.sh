#!/bin/bash
set -u
cd "$(dirname "$0")/.."
LOG=data/fs168/f3_chain.log
echo "[f3] 阶段1 缺口页回填 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py fill >> "$LOG" 2>&1
echo "[f3] 阶段2 新清单深采 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py crawl >> "$LOG" 2>&1
echo "[f3] 阶段3 覆盖核对 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py gaps >> "$LOG" 2>&1
echo "[f3] 全部完成 $(date '+%F %T')" >> "$LOG"
