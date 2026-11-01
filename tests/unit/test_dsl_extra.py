"""补充测试：DSL 边界分支、符号层辅助接口、规则库统计接口。

目的是把 ``dsl.py`` 等核心模块的**分支覆盖**补到门禁要求（core-* ≥ 90% 为目标值）。
"""

from __future__ import annotations

import pytest

from core_rule.dsl import (
    EvalOutcome,
    collect_fact_paths,
    eval_condition,
    iter_atoms,
    resolve_path,
    validate_condition,
)
from core_rule.errors import DSLValidationError
from core_symbol.ganzhi import (
    GAN_WUXING,
    SANHUI,
    ZHI_WUXING,
    relation_between_zhi,
    same_group,
    sanhui_present,
    wuxing_of_gan,
    wuxing_of_zhi,
    zhi_relations_in,
)

CTX = {
    "site": {"mountain": "乾", "shan_jia_zhi": "亥"},
    "course": {"day": {"zhi": "卯"}},
    "facts": {
        "m": {"dict": {"a": 1}, "set": {"x", "y"}, "list": ["p", "q"], "n": 3, "s": "abc"},
        "none": {"v": None},
    },
}


class TestDslBranches:
    def test_in_with_dict(self) -> None:
        assert eval_condition({"fact": "site.mountain", "op": "in", "value": {"乾": 1}}, CTX).value is True

    def test_in_with_none_value(self) -> None:
        with pytest.raises(DSLValidationError):
            eval_condition({"fact": "site.mountain", "op": "in", "value": None}, CTX)

    def test_intersects_with_set(self) -> None:
        assert eval_condition({"fact": "facts.m.set", "op": "intersects", "value": ["x"]}, CTX).value is True

    def test_intersects_with_dict_keys(self) -> None:
        assert eval_condition(
            {"fact": "facts.m.dict", "op": "intersects", "value": ["a"]}, CTX
        ).value is True

    def test_intersects_with_scalar_raises(self) -> None:
        with pytest.raises(DSLValidationError):
            eval_condition({"fact": "facts.m.n", "op": "intersects", "value": [1]}, CTX)

    def test_between_requires_pair(self) -> None:
        with pytest.raises(DSLValidationError):
            eval_condition({"fact": "facts.m.n", "op": "between", "value": [1]}, CTX)

    def test_between_non_numeric(self) -> None:
        with pytest.raises(DSLValidationError):
            eval_condition({"fact": "facts.m.s", "op": "between", "value": [1, 2]}, CTX)

    def test_gte_non_numeric(self) -> None:
        with pytest.raises(DSLValidationError):
            eval_condition({"fact": "facts.m.s", "op": "gte", "value": 1}, CTX)

    def test_count_on_none_is_unknown(self) -> None:
        res = eval_condition({"fact": "facts.none.v", "op": "count_gte", "value": 1}, CTX)
        assert res.value is None

    def test_count_on_scalar_raises(self) -> None:
        with pytest.raises(TypeError):
            eval_condition({"fact": "facts.m.n", "op": "count_gte", "value": 1}, CTX)

    def test_same_group_unknown_path(self) -> None:
        res = eval_condition(
            {"fact": "site.shan_jia_zhi", "op": "same_group",
             "value": {"path": "person.missing", "kind": "sanhe"}},
            CTX,
        )
        assert res.value is None
        assert res.unknown_paths == ["person.missing"]

    def test_same_group_bad_value(self) -> None:
        with pytest.raises(DSLValidationError):
            eval_condition({"fact": "site.shan_jia_zhi", "op": "same_group", "value": "亥"}, CTX)

    def test_value_from_missing(self) -> None:
        res = eval_condition(
            {"fact": "site.mountain", "op": "eq", "value_from": "person.missing"}, CTX
        )
        assert res.value is None

    def test_eval_outcome_bool_forbidden(self) -> None:
        with pytest.raises(TypeError):
            bool(EvalOutcome(True))

    def test_iter_atoms(self) -> None:
        cond = {"all": [
            {"fact": "site.mountain", "op": "eq", "value": "乾"},
            {"not": {"fact": "course.day.zhi", "op": "eq", "value": "子"}},
        ]}
        atoms = list(iter_atoms(cond))
        assert len(atoms) == 2

    def test_iter_atoms_non_dict(self) -> None:
        assert list(iter_atoms("not-a-dict")) == []

    def test_collect_fact_paths(self) -> None:
        cond = {"all": [
            {"fact": "site.mountain", "op": "eq", "value": "乾"},
            {"fact": "site.shan_jia_zhi", "op": "same_group",
             "value": {"path": "course.day.zhi", "kind": "sanhe"}},
            {"fact": "facts.x", "op": "eq", "value_from": "facts.y"},
        ]}
        paths = collect_fact_paths(cond)
        assert "site.mountain" in paths
        assert "course.day.zhi" in paths
        assert "facts.y" in paths

    def test_validate_not_node(self) -> None:
        validate_condition({"not": {"fact": "site.mountain", "op": "exists"}})

    def test_validate_not_with_bad_body(self) -> None:
        with pytest.raises(DSLValidationError):
            validate_condition({"not": "x"})

    def test_validate_non_dict(self) -> None:
        with pytest.raises(DSLValidationError, match="必须是对象"):
            validate_condition(["a"])

    def test_validate_fact_not_str(self) -> None:
        with pytest.raises(DSLValidationError, match="fact 必须是字符串"):
            validate_condition({"fact": 123, "op": "eq", "value": 1})

    def test_validate_any_bad_body(self) -> None:
        with pytest.raises(DSLValidationError, match="非空数组"):
            validate_condition({"any": "x"})

    def test_validate_any_empty(self) -> None:
        with pytest.raises(DSLValidationError, match="非空数组"):
            validate_condition({"any": []})

    def test_validate_same_group_path_whitelist(self) -> None:
        with pytest.raises(DSLValidationError, match="命名空间越界"):
            validate_condition(
                {"fact": "site.mountain", "op": "same_group",
                 "value": {"path": "secrets.x", "kind": "sanhe"}}
            )

    def test_resolve_negative_index(self) -> None:
        assert resolve_path({"a": [1, 2]}, "a.-1") == (False, None)


class TestGanzhiBranches:
    def test_wuxing_lookup(self) -> None:
        assert wuxing_of_gan("甲") == "木"
        assert wuxing_of_zhi("子") == "水"
        assert GAN_WUXING["癸"] == "水"
        assert ZHI_WUXING["亥"] == "水"

    @pytest.mark.parametrize(
        "a,b,kind",
        [("子", "丑", "合"), ("寅", "卯", "无"), ("辰", "辰", "自刑"), ("未", "未", "同支")],
    )
    def test_relation_primary_kind(self, a: str, b: str, kind: str) -> None:
        assert relation_between_zhi(a, b).kind == kind

    def test_sanhui_present(self) -> None:
        assert sanhui_present("寅卯辰")
        assert sanhui_present("寅卯") == []

    def test_zhi_relations_in(self) -> None:
        rels = zhi_relations_in(["未", "未", "卯", "未"])
        assert rels
        assert all(r.kind != "无" for r in rels)

    def test_same_group_all_kinds(self) -> None:
        for kind in ("sanhe", "sanhui", "liuhe", "chong", "hai", "xing", "po"):
            assert isinstance(same_group("子", "午", kind), bool)

    def test_sanhui_table(self) -> None:
        assert set(SANHUI) and len(SANHUI) == 4


class TestRuleSetApi:
    def test_get_and_schools(self, registry) -> None:
        rule = registry.ruleset.get("PUB-SANSHA-001")
        assert "三煞" in rule.category
        assert "public" in registry.ruleset.schools()

    def test_school_of(self, registry) -> None:
        assert registry.school_of("DS-HUAQI-001") == "doushou"

    def test_task_spec(self, registry) -> None:
        spec = registry.task_spec("安葬")
        assert spec is not None and spec.default_strictness == "strict"
        assert registry.task_spec("不存在") is None

    def test_stats(self, registry) -> None:
        stats = registry.stats()
        assert stats["total"] >= 40
        assert "by_status" in stats

    def test_select_by_school(self, registry) -> None:
        picked = registry.ruleset.select(schools=["doushou"], include_unverified=True)
        assert len(picked) == 1
        assert picked[0].school == "doushou"

    def test_select_excludes_deprecated(self, registry) -> None:
        # 当前库无弃用规则，但接口必须存在且可用
        assert all(r.status != "弃用" for r in registry.ruleset.select(include_unverified=True))

    def test_all_fact_paths(self, registry) -> None:
        from core_rule.loader import all_fact_paths

        paths = all_fact_paths(registry.ruleset.rules)
        assert any(p.startswith("facts.") for p in paths)
        assert any(p.startswith("site.") for p in paths)


class TestConfigBranches:
    def test_with_overrides(self) -> None:
        from core_time import CalendarConfig

        cfg = CalendarConfig()
        new = cfg.with_overrides(day_boundary="early", unknown_key=1)
        assert new.day_boundary == "early"
        assert new.timezone == cfg.timezone

    def test_extra_field_not_in_manifest(self) -> None:
        from core_time import CalendarConfig

        cfg = CalendarConfig(extra={"foo": "bar"})
        assert "extra" not in cfg.to_manifest()
