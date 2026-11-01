#!/usr/bin/env python3
"""评审第十四轮：cap/评估语义文件变更而 ENGINE_VERSION 未 bump → 提醒（warn 不阻断）。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMANTIC = ("core-eval/src/core_eval/engine.py", "core-eval/src/core_eval/ranker.py",
            "core-rule/src/core_rule/severity_cap.py", "core-rule/src/core_rule/models.py")
base = sys.argv[1] if len(sys.argv) > 1 else "HEAD~1"
changed = subprocess.run(["git", "diff", "--name-only", base, "HEAD"],
                         capture_output=True, text=True, cwd=ROOT).stdout.split()
touched = [f for f in SEMANTIC if f in changed]
if touched:
    print(f"⚠️ 语义文件已变更但请确认 ENGINE_VERSION 是否需要 bump：{touched}")
    print("   （bump 规则见 ADR-0014 决策 1；指纹/缓存 key 依赖此版本号）")
else:
    print("语义文件未变更，ENGINE_VERSION 无需 bump")
sys.exit(0)  # warn 不阻断
