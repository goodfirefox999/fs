#!/bin/bash
# 链式任务：等待图片下载结束 → 精华区全作者发现 → 深采 → 解析入库 → 报告
# 2026-11-01 委托人批准。全程遵守全局 2.0s 限速（各阶段内部保证）。
set -u
cd "$(dirname "$0")/.."
LOG=logs/chain_digest.log

echo "[chain] 启动于 $(date '+%F %T')，等待图片下载进程结束……" >> "$LOG"
while ps aux | grep -q "[s]rc.pipeline images"; do
  sleep 300
done
echo "[chain] 图片下载已结束 $(date '+%F %T')" >> "$LOG"

echo "[chain] === 阶段1: 精华区全作者发现 === $(date '+%F %T')" >> "$LOG"
.venv/bin/python -m src.pipeline discover_digest >> "$LOG" 2>&1

NEW=$(sqlite3 data/fs.sqlite "SELECT COUNT(*) FROM thread_index WHERE discover_source LIKE '%digest_all%' AND crawl_status='PENDING';")
echo "[chain] 发现新帖: $NEW" >> "$LOG"

if [ "$NEW" -gt 0 ]; then
  echo "[chain] === 阶段2: 深采精华区新帖 === $(date '+%F %T')" >> "$LOG"
  .venv/bin/python -m src.pipeline crawl >> "$LOG" 2>&1
  echo "[chain] === 阶段3: 解析入库 === $(date '+%F %T')" >> "$LOG"
  .venv/bin/python -m src.pipeline reparse >> "$LOG" 2>&1
else
  echo "[chain] 无新帖，跳过采集" >> "$LOG"
fi

echo "[chain] === 阶段4: 质检报告 === $(date '+%F %T')" >> "$LOG"
.venv/bin/python -m src.pipeline report >> "$LOG" 2>&1
echo "[chain] 全链完成 $(date '+%F %T')，见 data/collection_report.md" >> "$LOG"
