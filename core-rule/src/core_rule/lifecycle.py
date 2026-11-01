"""规则生命周期状态机（规则层）。

::

    draft → 待考证 → 已考证
                  ↘ 有争议 →（人类裁定）→ 已考证 | 弃用
    已考证 →（原文复核发现错误）→ 待考证（必须升 version 并保留历史）

权限：Agent 只能创建 ``draft`` / ``待考证``。把状态改为 ``已考证`` / ``有争议`` / ``弃用``
的提交必须由人类签名（commit trailer ``Verified-By:``）。CI 检查见 tools/check_status_signature.py。
"""

from __future__ import annotations

from typing import Iterable

from .errors import LifecycleError, SignatureError
from .models import RuleStatus

__all__ = [
    "ALLOWED_TRANSITIONS",
    "HUMAN_ONLY_TARGETS",
    "can_transition",
    "assert_transition",
    "requires_signature",
    "assert_signature",
    "AGENT_ALLOWED_STATUSES",
]

#: 合法迁移表（含自身，表示"状态不变"）
#:
#: ``定义级`` 是独立分支：它由"是否属于干支算术推论"决定，与"是否有古籍原文"正交。
#: 定义级可以退回 ``待考证``（若发现它其实含吉凶断言），但不能直接跳到 ``已考证``。
ALLOWED_TRANSITIONS: dict[RuleStatus, frozenset[RuleStatus]] = {
    "draft": frozenset({"draft", "待考证", "定义级"}),
    "待考证": frozenset({"待考证", "定义级", "已考证", "有争议", "弃用"}),
    "定义级": frozenset({"定义级", "待考证", "弃用"}),
    "已考证": frozenset({"已考证", "待考证", "有争议", "弃用"}),
    "有争议": frozenset({"有争议", "已考证", "弃用", "待考证"}),
    "弃用": frozenset({"弃用", "待考证"}),
}

#: 只有人类可写入的目标状态。
#: ``定义级`` 不在此列 —— 它是"该规则是否只是算术推论"的技术判断，
#: 由 ``citation.kind: spec`` + 规格条款原文把关（见 ADR-0007），不需要古籍考证签名。
HUMAN_ONLY_TARGETS: frozenset[RuleStatus] = frozenset({"已考证", "有争议", "弃用"})

#: Agent 允许创建的初始状态
AGENT_ALLOWED_STATUSES: frozenset[RuleStatus] = frozenset({"draft", "待考证", "定义级"})


def can_transition(old: RuleStatus, new: RuleStatus) -> bool:
    return new in ALLOWED_TRANSITIONS.get(old, frozenset())


def assert_transition(old: RuleStatus, new: RuleStatus, *, rule_id: str | None = None) -> None:
    """校验状态迁移合法性。非法迁移抛 ``LifecycleError``。"""
    if not can_transition(old, new):
        prefix = f"[{rule_id}] " if rule_id else ""
        raise LifecycleError(f"{prefix}非法状态迁移: {old} → {new}")


def requires_signature(old: RuleStatus, new: RuleStatus) -> bool:
    """状态迁移是否需要人类签名。"""
    return new != old and new in HUMAN_ONLY_TARGETS


def assert_signature(
    old: RuleStatus,
    new: RuleStatus,
    *,
    signer: str | None,
    rule_id: str | None = None,
) -> None:
    """若迁移需要签名而 ``signer`` 为空，抛 ``SignatureError``。"""
    if requires_signature(old, new) and not (signer and signer.strip()):
        prefix = f"[{rule_id}] " if rule_id else ""
        raise SignatureError(
            f"{prefix}状态迁移 {old} → {new} 需人类签名（commit trailer `Verified-By:`），"
            "Agent 不得自行写入该状态"
        )


def validate_version_bump(
    old_version: int,
    new_version: int,
    *,
    content_changed: bool,
    rule_id: str | None = None,
) -> None:
    """规则内容变更必须升 version。"""
    if content_changed and new_version <= old_version:
        prefix = f"[{rule_id}] " if rule_id else ""
        raise LifecycleError(f"{prefix}规则内容已变更，version 必须递增（当前 {old_version} → {new_version}）")


def statuses_needing_review(statuses: Iterable[RuleStatus]) -> list[RuleStatus]:
    return [s for s in statuses if s in ("draft", "待考证", "有争议")]
