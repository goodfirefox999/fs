"""生命周期测试：状态迁移、签名要求、version 递增。"""

from __future__ import annotations

import pytest

from core_rule.errors import LifecycleError, SignatureError
from core_rule.lifecycle import (
    AGENT_ALLOWED_STATUSES,
    ALLOWED_TRANSITIONS,
    HUMAN_ONLY_TARGETS,
    assert_signature,
    assert_transition,
    can_transition,
    requires_signature,
    validate_version_bump,
)


def test_agent_can_create_draft_pending_definitional() -> None:
    """定义级不需要古籍签名（它是"是否只是算术推论"的技术判断），但需要 spec 条款。"""
    assert AGENT_ALLOWED_STATUSES == frozenset({"draft", "待考证", "定义级"})


def test_human_only_targets() -> None:
    assert HUMAN_ONLY_TARGETS == frozenset({"已考证", "有争议", "弃用"})


@pytest.mark.parametrize(
    "old,new,ok",
    [
        ("draft", "待考证", True),
        ("draft", "定义级", True),
        ("定义级", "待考证", True),
        ("定义级", "已考证", False),
        ("draft", "已考证", False),
        ("待考证", "已考证", True),
        ("待考证", "有争议", True),
        ("已考证", "待考证", True),
        ("已考证", "弃用", True),
        ("弃用", "待考证", True),
        ("弃用", "已考证", False),
        ("有争议", "已考证", True),
    ],
)
def test_transition_table(old: str, new: str, ok: bool) -> None:
    assert can_transition(old, new) is ok  # type: ignore[arg-type]


def test_illegal_transition_raises() -> None:
    with pytest.raises(LifecycleError, match="非法状态迁移"):
        assert_transition("draft", "已考证", rule_id="PUB-X-001")


def test_requires_signature() -> None:
    assert requires_signature("待考证", "已考证")
    assert requires_signature("已考证", "弃用")
    assert not requires_signature("待考证", "待考证")
    assert not requires_signature("draft", "待考证")


def test_signature_required_blocks_agent() -> None:
    with pytest.raises(SignatureError, match="Verified-By"):
        assert_signature("待考证", "已考证", signer=None, rule_id="PUB-X-001")


def test_signature_present_passes() -> None:
    assert_signature("待考证", "已考证", signer="考证者-张", rule_id="PUB-X-001")


def test_signature_not_required_for_draft_to_pending() -> None:
    assert_signature("draft", "待考证", signer=None)


def test_version_bump_required_on_change() -> None:
    with pytest.raises(LifecycleError, match="version 必须递增"):
        validate_version_bump(1, 1, content_changed=True, rule_id="PUB-X-001")


def test_version_bump_ok() -> None:
    validate_version_bump(1, 2, content_changed=True)
    validate_version_bump(1, 1, content_changed=False)


def test_all_statuses_covered_by_transition_table() -> None:
    from core_rule.models import RULE_STATUSES

    assert set(ALLOWED_TRANSITIONS) == set(RULE_STATUSES)
