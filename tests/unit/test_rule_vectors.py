"""规则级测试向量：每条规则 ≥1 命中 + ≥1 不命中/unknown（文档第 10 节硬要求）。

向量文件由 ``tools/gen_rules.py`` 生成，位于 ``tests/cases/rule_tests/``。
每个向量只覆盖被引用路径，其余字段由金标准基准 ctx 提供（深合并）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core_rule.dsl import eval_condition

CASES_DIR = Path(__file__).resolve().parents[1] / "cases" / "rule_tests"
CASE_FILES = sorted(CASES_DIR.glob("*.yaml"))
EXPECTED_MAP = {"hit": True, "miss": False, "unknown": None}


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_case_files_exist() -> None:
    assert len(CASE_FILES) >= 80, f"规则测试向量不足：{len(CASE_FILES)}"


#: 已知限制向量（当前为空——DG/XK/TX 全部向量已可实测）
KNOWN_LIMIT_MISS: set[str] = set()

@pytest.mark.parametrize("case_path", CASE_FILES, ids=[p.stem for p in CASE_FILES])


def test_rule_vector(case_path: Path, registry, merged_ctx_factory) -> None:
    data = _load(case_path)
    rule = registry.ruleset.get(data["rule_id"])
    ctx = merged_ctx_factory(data["overrides"] or {})
    outcome = eval_condition(rule.condition, ctx)
    expected = EXPECTED_MAP[data["expected"]]
    if data["case_id"] in KNOWN_LIMIT_MISS:
        pytest.skip(
            f"{data['case_id']}: exists 类条件在有效课程/空容器上恒 True，"
            "MISS 需完整分析实现后重测（已知限制）"
        )
    assert outcome.value is expected, (
        f"{data['case_id']}: 期望 {data['expected']}，得到 {outcome.value}"
        f"（unknown_paths={outcome.unknown_paths}）"
    )


def test_every_rule_has_two_vectors(registry) -> None:
    """每条规则的 tests 字段必须指向真实存在的向量，且至少 2 项。"""
    existing = {p.stem for p in CASE_FILES}
    for rule in registry.ruleset.rules:
        assert len(rule.tests) >= 2, f"{rule.rule_id} tests 少于 2 项"
        for case_id in rule.tests:
            assert case_id in existing, f"{rule.rule_id} 引用的用例不存在: {case_id}"


def test_every_rule_has_hit_and_non_hit(registry) -> None:
    """每条规则至少一个 hit + 一个非 hit（miss 或 unknown）。"""
    by_rule: dict[str, set[str]] = {}
    for path in CASE_FILES:
        data = _load(path)
        by_rule.setdefault(data["rule_id"], set()).add(data["expected"])
    for rule in registry.ruleset.rules:
        kinds = by_rule.get(rule.rule_id, set())
        assert "hit" in kinds, f"{rule.rule_id} 缺少命中向量"
        assert kinds & {"miss", "unknown"}, f"{rule.rule_id} 缺少非命中向量"
