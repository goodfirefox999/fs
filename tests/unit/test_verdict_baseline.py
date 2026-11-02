"""verdict_type 迁移棘轮（评审：否则「未归类」会变成永久状态）。

基线：``core-rule/config/verdict_baseline.yaml``（``unlabeled_count``）。

- 当前未标注数 **>** 基线 → 失败（出现回退：有人把已标注规则改回 null，
  或新增规则忘了归类）；失败信息要求回滚或上调基线并写明理由。
- 当前未标注数 **<** 基线 → 也失败（**这是好事**：C 第二批迁移有进展，
  应当下调基线并在 commit 里勾掉 `docs/c2-migration-checklist.md` 对应项）。

两条失败路径都强迫人碰一次基线文件，这正是设计意图：
让迁移进度经过显式确认，而不是在报告角落里悄悄漂移。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from core_rule.loader import load_ruleset

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = ROOT / "core-rule/config/verdict_baseline.yaml"


def _unlabeled_count() -> int:
    rs = load_ruleset(str(ROOT / "core-rule/rules"))
    return sum(1 for r in rs.rules if r.verdict_type is None)


def test_unlabeled_count_is_ratcheted() -> None:
    baseline = yaml.safe_load(BASELINE_PATH.read_text(encoding="utf-8"))
    expected: int = baseline["unlabeled_count"]
    current = _unlabeled_count()
    assert current <= expected, (
        f"未归类回退：当前 {current} > 基线 {expected}。"
        "若新增规则，请在同批提交里显式标注 verdict_type 或上调基线并写明理由。"
    )
    assert current >= expected, (
        f"迁移有进展：当前 {current} < 基线 {expected}。"
        "请下调 core-rule/config/verdict_baseline.yaml 的 unlabeled_count，"
        "并在 docs/c2-migration-checklist.md 勾掉已完成条目。"
    )


def test_baseline_file_is_self_consistent() -> None:
    """per_school 计数之和必须等于 unlabeled_count（防止手改基线时改漏）。"""
    baseline = yaml.safe_load(BASELINE_PATH.read_text(encoding="utf-8"))
    assert sum(baseline["per_school"].values()) == baseline["unlabeled_count"]
