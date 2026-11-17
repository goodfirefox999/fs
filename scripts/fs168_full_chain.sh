#!/bin/bash
# fs168 全链：图片补下 → 深采全部剩余帖 → 缺口回填 → 核对 → 新增图片再补一轮
# 全程单进程，共享 0.5 req/s 限速；所有阶段断点续跑，中断后重新执行本脚本即可继续
set -u
cd "$(dirname "$0")/.."
LOG=data/fs168/full_chain.log
echo "[chain] 开始 $(date '+%F %T')" >> "$LOG"

echo "[chain] 阶段1 存量图片下载 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_images.py >> "$LOG" 2>&1

echo "[chain] 阶段2 深采剩余帖 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py all >> "$LOG" 2>&1

echo "[chain] 阶段3 缺口页回填 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py fill >> "$LOG" 2>&1

echo "[chain] 阶段4 楼层重建核对 $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_threads.py gaps >> "$LOG" 2>&1

echo "[chain] 阶段5 新增图片下载（含失败重试） $(date '+%F %T')" >> "$LOG"
.venv/bin/python scrapers/fs168_images.py --force-failed >> "$LOG" 2>&1

echo "[chain] 全部完成 $(date '+%F %T')" >> "$LOG"
