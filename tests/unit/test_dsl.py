"""规则 DSL 测试：算子全覆盖、三值逻辑、深度限制、白名单、非法 DSL 必须被拒。"""

from __future__ import annotations

import pytest

from core_rule.dsl import (
    ALLOWED_ROOTS,
    MAX_DEPTH,
    OPS,
    condition_depth,
    eval_condition,
    resolve_path,
    validate_condition,
)
from core_rule.errors import DSLValidationError

CTX = {
    "course": {"day": {"zhi": "卯", "gan": "辛"}, "hour": {"zhi": "未", "gan": "乙"}},
    "site": {"mountain": "乾", "shan_jia_zhi": "亥", "azimuth": 320.0},
    "person": {"year_zhi": "丑"},
    "task": {"kind": "修造", "strictness": "strict"},
    "time": {"month_zhi": "未"},
    "facts": {
        "structure": {
            "max_repeat": 3,
            "zixing_pairs": [],
            "chong_pairs": [{"a": "卯", "b": "酉"}],
            "repeated": {"未": 3},
            "sanhe_with_mountain": [{"group": ["亥", "卯", "未"]}],
        },
        "sansha": {"year": {"mountains": ["申", "酉", "戌"], "hit_mountain": False}},
        "nullable": {"value": None},
        "empty": {"value": []},
    },
}


class TestResolvePath:
    def test_simple(self) -> None:
        assert resolve_path(CTX, "site.mountain") == (True, "乾")

    def test_list_index(self) -> None:
        assert resolve_path(CTX, "facts.sansha.year.mountains.0") == (True, "申")

    def test_missing(self) -> None:
        assert resolve_path(CTX, "site.not_there") == (False, None)

    def test_out_of_range(self) -> None:
        assert resolve_path(CTX, "facts.sansha.year.mountains.9") == (False, None)

    def test_through_scalar(self) -> None:
        assert resolve_path(CTX, "site.mountain.x") == (False, None)


class TestOperators:
    """算子全覆盖：每个 OPS 至少一个正例 + 一个反例。"""

    @pytest.mark.parametrize(
        "cond,expected",
        [
            ({"fact": "site.mountain", "op": "eq", "value": "乾"}, True),
            ({"fact": "site.mountain", "op": "eq", "value": "巽"}, False),
            ({"fact": "site.mountain", "op": "ne", "value": "巽"}, True),
            ({"fact": "site.mountain", "op": "ne", "value": "乾"}, False),
            ({"fact": "site.mountain", "op": "in", "value": ["乾", "巽"]}, True),
            ({"fact": "site.mountain", "op": "in", "value": ["坤", "艮"]}, False),
            ({"fact": "site.mountain", "op": "nin", "value": ["坤", "艮"]}, True),
            ({"fact": "site.mountain", "op": "nin", "value": ["乾"]}, False),
            ({"fact": "facts.sansha.year.mountains", "op": "intersects", "value": ["酉"]}, True),
            ({"fact": "facts.sansha.year.mountains", "op": "intersects", "value": ["子"]}, False),
            ({"fact": "facts.structure.max_repeat", "op": "gte", "value": 3}, True),
            ({"fact": "facts.structure.max_repeat", "op": "gte", "value": 4}, False),
            ({"fact": "facts.structure.max_repeat", "op": "lte", "value": 3}, True),
            ({"fact": "facts.structure.max_repeat", "op": "lte", "value": 2}, False),
            ({"fact": "facts.structure.max_repeat", "op": "between", "value": [2, 4]}, True),
            ({"fact": "facts.structure.max_repeat", "op": "between", "value": [4, 6]}, False),
            ({"fact": "site.mountain", "op": "exists"}, True),
            ({"fact": "facts.nullable.value", "op": "exists"}, None),
            ({"fact": "facts.empty.value", "op": "exists"}, False),
            ({"fact": "site.shan_jia_zhi", "op": "same_group",
              "value": {"path": "course.day.zhi", "kind": "sanhe"}}, True),
            ({"fact": "site.shan_jia_zhi", "op": "same_group",
              "value": {"path": "course.hour.zhi", "kind": "sanhe"}}, True),
            ({"fact": "facts.structure.chong_pairs", "op": "count_gte", "value": 1}, True),
            ({"fact": "facts.structure.zixing_pairs", "op": "count_gte", "value": 1}, False),
            ({"fact": "facts.structure.zixing_pairs", "op": "count_eq", "value": 0}, True),
        ],
    )
    def test_operator(self, cond: dict, expected: bool | None) -> None:
        assert eval_condition(cond, CTX).value is expected

    def test_all_ops_covered(self) -> None:
        used = {
            "eq", "ne", "in", "nin", "intersects", "gte", "lte", "between",
            "exists", "same_group", "count_gte", "count_eq",
        }
        assert used == set(OPS), f"算子未全覆盖：{set(OPS) - used}"

    @pytest.mark.parametrize(
        "value,expected",
        [([3, 5], True), ([2, 3], True), ([4, 5], False), ([1, 2], False)],
    )
    def test_between_inclusive_boundaries(self, value: list[int], expected: bool) -> None:
        """between 必须**包含**边界（变异测试发现过这里没测边界）。"""
        cond = {"fact": "facts.structure.max_repeat", "op": "between", "value": value}
        assert eval_condition(cond, CTX).value is expected

    def test_same_group_kind_matters(self) -> None:
        """变异 `kind = "sanhe"` 的守卫：不同 kind 必须给出不同结论。"""
        # 子午 是冲，不是三合
        cond_chong = {"fact": "site.shan_jia_zhi", "op": "same_group",
                      "value": {"path": "course.day.zhi", "kind": "chong"}}
        cond_sanhe = {"fact": "site.shan_jia_zhi", "op": "same_group",
                      "value": {"path": "course.day.zhi", "kind": "sanhe"}}
        ctx = {"site": {"shan_jia_zhi": "子"}, "course": {"day": {"zhi": "午"}}}
        assert eval_condition(cond_chong, ctx).value is True
        assert eval_condition(cond_sanhe, ctx).value is False

    def test_value_from(self) -> None:
        cond = {"fact": "site.shan_jia_zhi", "op": "eq", "value_from": "time.month_zhi"}
        assert eval_condition(cond, CTX).value is False
        assert eval_condition(cond, {**CTX, "time": {"month_zhi": "亥"}}).value is True


class TestThreeValuedLogic:
    def test_missing_fact_is_unknown(self) -> None:
        res = eval_condition({"fact": "person.nonexistent", "op": "eq", "value": 1}, CTX)
        assert res.value is None
        assert res.unknown_paths == ["person.nonexistent"]

    def test_null_value_is_unknown(self) -> None:
        res = eval_condition({"fact": "facts.nullable.value", "op": "eq", "value": 1}, CTX)
        assert res.value is None

    def test_all_with_false_and_unknown_is_false(self) -> None:
        """Kleene 逻辑：False ∧ unknown = False。"""
        cond = {"all": [
            {"fact": "site.mountain", "op": "eq", "value": "巽"},
            {"fact": "person.missing", "op": "eq", "value": 1},
        ]}
        assert eval_condition(cond, CTX).value is False

    def test_all_with_only_unknown_is_unknown(self) -> None:
        cond = {"all": [
            {"fact": "site.mountain", "op": "eq", "value": "乾"},
            {"fact": "person.missing", "op": "eq", "value": 1},
        ]}
        assert eval_condition(cond, CTX).value is None

    def test_any_with_true_and_unknown_is_true(self) -> None:
        cond = {"any": [
            {"fact": "site.mountain", "op": "eq", "value": "乾"},
            {"fact": "person.missing", "op": "eq", "value": 1},
        ]}
        assert eval_condition(cond, CTX).value is True

    def test_any_with_only_unknown_is_unknown(self) -> None:
        cond = {"any": [
            {"fact": "site.mountain", "op": "eq", "value": "巽"},
            {"fact": "person.missing", "op": "eq", "value": 1},
        ]}
        assert eval_condition(cond, CTX).value is None

    def test_not_unknown_is_unknown(self) -> None:
        cond = {"not": {"fact": "person.missing", "op": "eq", "value": 1}}
        assert eval_condition(cond, CTX).value is None

    def test_not_true_is_false(self) -> None:
        cond = {"not": {"fact": "site.mountain", "op": "eq", "value": "乾"}}
        assert eval_condition(cond, CTX).value is False

    def test_nested(self) -> None:
        cond = {"all": [
            {"any": [
                {"fact": "site.mountain", "op": "eq", "value": "乾"},
                {"fact": "site.mountain", "op": "eq", "value": "巽"},
            ]},
            {"not": {"fact": "facts.structure.max_repeat", "op": "gte", "value": 5}},
        ]}
        assert eval_condition(cond, CTX).value is True


class TestValidation:
    def test_root_whitelist(self) -> None:
        assert ALLOWED_ROOTS == frozenset({"course", "site", "person", "task", "time", "facts"})

    @pytest.mark.parametrize("root", ["secrets", "db", "env", "core_time"])
    def test_illegal_root_rejected(self, root: str) -> None:
        with pytest.raises(DSLValidationError, match="命名空间越界"):
            validate_condition({"fact": f"{root}.x", "op": "eq", "value": 1})

    def test_unknown_op_rejected(self) -> None:
        with pytest.raises(DSLValidationError, match="未知算子"):
            validate_condition({"fact": "site.mountain", "op": "gt", "value": 1})

    def test_missing_value_rejected(self) -> None:
        with pytest.raises(DSLValidationError, match="缺少 value"):
            validate_condition({"fact": "site.mountain", "op": "eq"})

    def test_depth_limit(self) -> None:
        node: dict = {"fact": "site.mountain", "op": "eq", "value": "乾"}
        for _ in range(MAX_DEPTH):
            node = {"all": [node]}
        with pytest.raises(DSLValidationError, match="深度超过"):
            validate_condition(node)

    def test_depth_within_limit(self) -> None:
        node: dict = {"fact": "site.mountain", "op": "eq", "value": "乾"}
        for _ in range(MAX_DEPTH - 1):
            node = {"all": [node]}
        validate_condition(node)
        assert condition_depth(node) == MAX_DEPTH

    def test_mixed_combinators_rejected(self) -> None:
        with pytest.raises(DSLValidationError, match="不得混用"):
            validate_condition({"all": [], "any": []})

    def test_empty_all_rejected(self) -> None:
        with pytest.raises(DSLValidationError, match="非空数组"):
            validate_condition({"all": []})

    def test_unknown_field_rejected(self) -> None:
        with pytest.raises(DSLValidationError, match="未知字段"):
            validate_condition({"fact": "site.mountain", "op": "eq", "value": 1, "magic": 2})

    def test_same_group_requires_path(self) -> None:
        with pytest.raises(DSLValidationError, match="same_group"):
            validate_condition({"fact": "site.mountain", "op": "same_group", "value": "亥"})

    def test_value_from_whitelist(self) -> None:
        with pytest.raises(DSLValidationError, match="value_from"):
            validate_condition(
                {"fact": "site.mountain", "op": "eq", "value_from": "secrets.x"}
            )
