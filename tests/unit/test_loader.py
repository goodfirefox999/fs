"""规则加载器与派别策略测试：非法规则必须被拒（"规则污染"红线第一道闸门）。"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from core_rule.errors import DSLValidationError
from core_rule.loader import load_rule, load_ruleset
from core_rule.policy import load_school_policy, load_task_kinds

BASE = {
    "api_version": 1,
    "rule_id": "PUB-TEST-001",
    "version": 1,
    "school": "public",
    "category": "测试类别",
    "status": "待考证",
    "hard_veto": True,
    "severity": "禁用",
    "target": "mountain",
    "applies_to": {"task_kinds": [], "node_kinds": [], "strictness_min": "normal"},
    "condition": {"fact": "facts.suipo.hit_mountain", "op": "eq", "value": True},
    "score_weight": None,
    "citation": {"source": "《协纪辨方书》", "quote": None},
    "tests": ["RT-A", "RT-B"],
    "explanation": "测试解释",
    "supersedes": None,
}


def _write(tmp_path: Path, **overrides) -> Path:
    data = {**BASE, **overrides}
    path = tmp_path / f"{data.get('rule_id', 'x')}.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


def test_valid_rule_loads(tmp_path: Path) -> None:
    rule = load_rule(_write(tmp_path))
    assert rule.rule_id == "PUB-TEST-001"
    assert rule.status == "待考证"
    assert rule.is_veto is True
    assert rule.is_participating is False


@pytest.mark.parametrize(
    "field",
    ["rule_id", "version", "school", "category", "status", "severity", "target",
     "condition", "citation", "explanation", "tests"],
)
def test_missing_required_field_rejected(tmp_path: Path, field: str) -> None:
    data = {k: v for k, v in BASE.items() if k != field}
    path = tmp_path / "r.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DSLValidationError, match="缺少必填字段"):
        load_rule(path)


@pytest.mark.parametrize("bad_id", ["pub-test-001", "PUBTEST001", "PUB-TEST-1", "X-TEST-001"])
def test_bad_rule_id_rejected(tmp_path: Path, bad_id: str) -> None:
    with pytest.raises(DSLValidationError, match="rule_id 格式非法"):
        load_rule(_write(tmp_path, rule_id=bad_id))


def test_bad_status_rejected(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="非法 status"):
        load_rule(_write(tmp_path, status="已确认"))


def test_bad_severity_rejected(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="非法 severity"):
        load_rule(_write(tmp_path, severity="大凶"))


def test_bad_target_rejected(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="非法 target"):
        load_rule(_write(tmp_path, target="universe"))


def test_veto_severity_consistency(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="hard_veto=true"):
        load_rule(_write(tmp_path, severity="推荐"))


def test_veto_cannot_have_score_weight(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="score_weight"):
        load_rule(_write(tmp_path, score_weight=1.0))


def test_tests_must_have_two(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="至少需要 2 项"):
        load_rule(_write(tmp_path, tests=["RT-A"]))


def test_tests_must_be_unique(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="重复"):
        load_rule(_write(tmp_path, tests=["RT-A", "RT-A"]))


def test_verified_requires_quote(tmp_path: Path) -> None:
    """已考证但无原文 → 拒绝（禁止无原文的已考证）。"""
    with pytest.raises(DSLValidationError, match="citation.quote"):
        load_rule(_write(tmp_path, status="已考证"))


def test_verified_requires_signer(tmp_path: Path) -> None:
    data = {
        **BASE,
        "status": "已考证",
        "citation": {"source": "《协纪辨方书》", "quote": "某句原文", "verified_by": None},
    }
    path = tmp_path / "r.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DSLValidationError, match="verified_by"):
        load_rule(path)


def test_verified_with_full_citation_ok(tmp_path: Path) -> None:
    data = {
        **BASE,
        "status": "已考证",
        "citation": {"source": "《协纪辨方书》", "quote": "某句原文", "quote_kind": "原文", "pian": "义例一", "verified_by": "考证者"},
    }
    path = tmp_path / "r.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    rule = load_rule(path)
    assert rule.is_participating is True


def test_citation_source_required(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="citation.source"):
        load_rule(_write(tmp_path, citation={"source": "", "quote": None}))


def test_condition_whitelist_enforced(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="命名空间越界"):
        load_rule(_write(tmp_path, condition={"fact": "secrets.x", "op": "eq", "value": 1}))


def test_empty_explanation_rejected(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="explanation"):
        load_rule(_write(tmp_path, explanation="   "))


def test_bad_strictness_min_rejected(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="strictness_min"):
        load_rule(_write(tmp_path, applies_to={"strictness_min": "ultra"}))


def test_bad_api_version_rejected(tmp_path: Path) -> None:
    with pytest.raises(DSLValidationError, match="api_version"):
        load_rule(_write(tmp_path, api_version=2))


def test_yaml_not_mapping_rejected(tmp_path: Path) -> None:
    path = tmp_path / "r.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(DSLValidationError, match="顶层必须是映射"):
        load_rule(path)


def test_duplicate_rule_id_across_files_rejected(tmp_path: Path) -> None:
    d = tmp_path / "rules" / "public"
    d.mkdir(parents=True)
    (d / "a.yaml").write_text(yaml.safe_dump(BASE, allow_unicode=True), encoding="utf-8")
    (d / "b.yaml").write_text(yaml.safe_dump(BASE, allow_unicode=True), encoding="utf-8")
    with pytest.raises(DSLValidationError, match="rule_id 重复"):
        load_ruleset(tmp_path / "rules")


def test_missing_dir_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_ruleset("/nonexistent/zeri/rules")


def test_ruleset_select_filters() -> None:
    """ADR-0014 C12：有争议规则默认参与评估（随已考证放行），待考证仍需 include_unverified。"""
    from core_rule import default_registry

    reg = default_registry()
    default_selected = reg.ruleset.select(include_unverified=False)
    default_ids = {r.rule_id for r in default_selected}
    assert "PUB-SANSHA-003" in default_ids and "PUB-TAISUI-001" in default_ids, (
        "有争议规则应默认被 select 放行（判定（存疑））"
    )
    assert all(r.status in ("已考证", "有争议") for r in default_selected)
    all_rules = reg.ruleset.select(include_unverified=True)
    assert len(all_rules) >= 40
    assert len(all_rules) > len(default_selected), "待考证规则仍需显式 include_unverified"


class TestSchoolPolicy:
    def test_load(self, tmp_path: Path) -> None:
        p = tmp_path / "policy.yaml"
        p.write_text(
            dedent(
                """
                api_version: 1
                schools:
                  public: {enabled: true, participates_in_veto: true}
                  doushou: {enabled: false, participates_in_veto: false}
                routing:
                  动土: [public]
                default_route: [public]
                """
            ),
            encoding="utf-8",
        )
        policy = load_school_policy(p)
        assert policy.route("动土") == ("public",)
        assert policy.route("未知事项") == ("public",)
        assert policy.veto_schools("动土") == ("public",)

    def test_unknown_school_in_routing_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "policy.yaml"
        p.write_text(
            dedent(
                """
                api_version: 1
                schools:
                  public: {enabled: true}
                routing:
                  动土: [not_declared]
                """
            ),
            encoding="utf-8",
        )
        with pytest.raises(DSLValidationError, match="未声明的派别"):
            load_school_policy(p)

    def test_missing_schools_section(self, tmp_path: Path) -> None:
        p = tmp_path / "policy.yaml"
        p.write_text("api_version: 1\n", encoding="utf-8")
        with pytest.raises(DSLValidationError, match="schools"):
            load_school_policy(p)

    def test_task_kinds_load(self) -> None:
        from core_rule.registry import CONFIG_DIR

        kinds = load_task_kinds(CONFIG_DIR / "task_kinds.yaml")
        assert len(kinds) == 24
        assert kinds["安葬"].default_strictness == "strict"
        assert kinds["修祠"].required_nodes

    def test_task_kind_bad_strictness(self, tmp_path: Path) -> None:
        p = tmp_path / "tk.yaml"
        p.write_text(
            "api_version: 1\ntask_kinds:\n  动土: {default_strictness: ultra}\n", encoding="utf-8"
        )
        with pytest.raises(DSLValidationError, match="default_strictness"):
            load_task_kinds(p)

    def test_task_kind_missing_section(self, tmp_path: Path) -> None:
        p = tmp_path / "tk.yaml"
        p.write_text("api_version: 1\n", encoding="utf-8")
        with pytest.raises(DSLValidationError, match="task_kinds"):
            load_task_kinds(p)
