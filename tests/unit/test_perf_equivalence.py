"""性能优化的等价性守卫（2026-11-26）。

本轮对判定引擎做常数开销优化（provenance 哈希按规则预序列化、citation 字典缓存、
Judgment 加 slots）。这类优化最大的风险是「快了但字节变了」——哈希值一变，
确定性探针、档案对比、跨版本 diff 全部失去比较基准。

本文件锁两条不变式：
1. 快路径哈希与 ``stable_hash`` **逐字节一致**（含中文、嵌套、转义字符）；
2. 经引擎 ``_make_judgment`` 产生的 Judgment，其 ``params_hash`` 用独立重算的
   ``stable_hash`` 验证仍然一致（守卫「引擎真的走了等价路径」）。
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from core_rule.provenance import stable_hash


def _ref_hash(condition, target, severity, input_hash) -> str:
    """独立重算：不经过任何快路径，直接对四键字典做 stable_hash。"""
    return stable_hash(
        {
            "condition": condition,
            "input_hash": input_hash,
            "severity": severity,
            "target": target,
        }
    )


class TestParamsHashFast:
    """params_hash_fast 与 stable_hash 逐字节一致（键序：condition<input_hash<severity<target）。"""

    def test_flat_condition(self) -> None:
        from core_rule.provenance import params_hash_fast

        cond = {"fact": "facts.suipo.hit_mountain", "op": "eq", "value": True}
        fast = params_hash_fast(cond, "mountain", "禁用", "abc123")
        assert fast == _ref_hash(cond, "mountain", "禁用", "abc123")

    def test_nested_and_unicode(self) -> None:
        from core_rule.provenance import params_hash_fast

        cond = {
            "all": [
                {"fact": "facts.sansha.year.mountains", "op": "contains", "value": "寅"},
                {"any": [{"fact": "facts.day.ganzhi", "op": "eq", "value": "甲子"}]},
            ],
            "备注": ["嵌套中文", {"键": 3.5}],
        }
        fast = params_hash_fast(cond, "day", "慎用", "deadbeef00")
        assert fast == _ref_hash(cond, "day", "慎用", "deadbeef00")

    def test_string_condition_and_escape_chars(self) -> None:
        from core_rule.provenance import params_hash_fast

        # input_hash 含引号/反斜杠/换行时必须走与 json.dumps 相同的转义
        fast = params_hash_fast("simple", "target", "可用", '哈"希\\测\n试')
        assert fast == _ref_hash("simple", "target", "可用", '哈"希\\测\n试')

    def test_condition_str_is_serialized_verbatim(self) -> None:
        from core_rule.provenance import params_hash_fast

        cond = "甲子"  # condition 也可能是纯字符串
        fast = params_hash_fast(cond, "day", "记录", "0f0f")
        assert fast == _ref_hash(cond, "day", "记录", "0f0f")

    def test_unsafe_condition_falls_back_and_still_matches(self) -> None:
        from core_rule.provenance import params_hash_fast

        cond = {"when": date(2027, 1, 1)}  # date 不是 JSON 安全类型 → 走回退
        fast = params_hash_fast(cond, "day", "可用", "ff00")
        # 回退路径 = stable_hash(原字典)（其 default=str 行为保持）
        assert fast == _ref_hash(cond, "day", "可用", "ff00")

    def test_cache_reuse_does_not_leak_between_rules(self) -> None:
        """同 condition 对象被两条 target 不同的规则共用时，哈希必须互不相同。"""
        from core_rule.provenance import params_hash_fast

        shared = {"fact": "facts.x", "op": "eq", "value": 1}
        h1 = params_hash_fast(shared, "mountain", "禁用", "aa")
        h2 = params_hash_fast(shared, "day", "禁用", "aa")
        assert h1 != h2


class TestEngineJudgmentsUseEquivalentHash:
    """引擎产出的 Judgment.params_hash 用独立重算验证（守卫引擎真的走了等价路径）。"""

    def test_every_judgment_params_hash_matches_reference(self, base_ctx, registry) -> None:
        from core_eval.engine import _make_judgment

        rule = next(r for r in registry.ruleset.rules if r.status == "定义级")
        j = _make_judgment(
            rule,
            ctx=base_ctx,
            rule_lib_version=registry.ruleset.version,
            participation="判定",
            input_hash="cafe1234",
            school=rule.school,
            severity=rule.severity,
        )
        assert j.params_hash == _ref_hash(
            rule.condition, rule.target, rule.severity, "cafe1234"
        )
        # 同一规则换 input_hash，哈希必须变化（缓存不得跨输入串味——C19 的语义要求）
        j2 = _make_judgment(
            rule,
            ctx=base_ctx,
            rule_lib_version=registry.ruleset.version,
            participation="判定",
            input_hash="cafe5678",
            school=rule.school,
            severity=rule.severity,
        )
        assert j2.params_hash != j.params_hash

    def test_judgment_is_frozen_and_slots_clean(self) -> None:
        """slots 化后：frozen 语义保持，实例无 __dict__（内存收益的前提）。"""
        from core_eval.engine import Judgment

        assert Judgment.__dataclass_params__.frozen is True
        assert not hasattr(Judgment(  # type: ignore[call-arg]
            rule_id="x", rule_version=1, school="s", category="c", status="待考证",
            severity="记录", target="day", matched=False, participation="判定",
            hit_detail="", explanation="", citation={}, params_hash="",
        ), "__dict__")
