"""必需集闭合性、publishable 验收信号、确定命中的负向用例。

背景（2026-11-01 第三轮评审）：
- 「必需集必须可判定闭合，否则会出现『报告说 9/10，但 publishable 恒 false』的荒诞状态」
- 「负向用例不必等考证：用 fixture 注入合成已考证规则，跑真实金标准输入」

本文件用**合成规则**（`TEST-VERIFIED-001`，注明"测试专用"）验证"确定命中"渲染路径与
publishable 的 false→true 验收信号，不依赖真实考证进度。
"""

from __future__ import annotations

from dataclasses import replace as dc_replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app_zeri.report import render_markdown
from app_zeri.schemas import PersonSpec, SiteSpec, TaskSpec, build_context
from core_eval import (
    STATE_BLOCKED,
    STATE_OK,
    TIER_REJECTED,
    EvalConfig,
    evaluate,
)
from core_rule.dsl import collect_fact_paths
from core_rule.models import AppliesTo, Rule
from core_rule.provenance import Citation
from core_rule.registry import RuleRegistry
from core_time import CalendarConfig

CST = ZoneInfo("Asia/Shanghai")


def _strip_all_hits(ctx: dict) -> dict:
    """清空所有可能命中的 facts，用于构造"干净"候选。"""
    from tests.conftest import deep_merge

    return deep_merge(
        ctx,
        {
            "facts": {
                "structure": {
                    "max_repeat": 1,
                    "zixing_pairs": [], "chong_pairs": [], "hai_pairs": [], "po_pairs": [],
                    "xing_pairs": [], "gan_chong_pairs": [], "sanhe_groups": [],
                    "sanhe_with_mountain": [], "banhe_with_mountain": [],
                },
                "xunkong": {"hits": []},
                "suipo": {"hit_mountain": False, "hit_facing": False},
                "yuepo": {"hit_mountain": False, "hit_facing": False},
                "taisui": {"zhi": "未"},
                "wuhuang": {"year": {"hit_mountain": False, "hit_facing": False}},
                "sili_sijue": {"has_sili": False, "has_sijue": False, "is_hit": False, "hits": []},
                "sansha": {
                    "year": {"hit_mountain": False, "hit_facing": False},
                    "month": {"hit_mountain": False, "hit_facing": False},
                },
            }
        },
    )


def _synthetic_rule(*, status: str = "已考证", hit: bool = True, rule_id: str = "TEST-VERIFIED-001") -> Rule:
    """合成规则：**仅用于测试**，不是真实择日规则。

    ``citation.source`` 明确标注"测试专用"，``kind=classic`` + ``verified_by=pytest``
    以满足 `已考证` 的加载约束（这里直接构造 Rule 对象，不走 loader）。
    """
    return Rule(
        rule_id=rule_id,
        version=1,
        school="public",
        category="测试专用否决",
        status=status,  # type: ignore[arg-type]
        hard_veto=True,
        severity="禁用",
        target="mountain",
        applies_to=AppliesTo(),
        condition={"fact": "site.mountain", "op": "eq", "value": "乾" if hit else "子"},
        citation=Citation(
            source="测试专用（非古籍，仅用于验证确定命中路径）",
            kind="classic",
            quote="测试用原文占位",
            verified_by="pytest",
        ),
        explanation="合成规则：坐山为乾时判禁用（仅测试）",
        tests=("TEST-HIT", "TEST-MISS"),
    )


def _registry_with(registry: RuleRegistry, *rules: Rule) -> RuleRegistry:
    new_rules = registry.ruleset.rules + rules
    by_id = {**registry.ruleset.by_id, **{r.rule_id: r for r in rules}}
    # 动态构造时必须更新 version，否则缓存/清单会误判为同一规则库
    from core_rule.provenance import stable_hash

    ruleset = dc_replace(
        registry.ruleset,
        rules=new_rules,
        by_id=by_id,
        version="rl-" + stable_hash([(r.rule_id, r.version) for r in new_rules]),
    )
    return RuleRegistry(
        ruleset=ruleset,
        policy=registry.policy,
        task_kinds=registry.task_kinds,
        calibers=registry.calibers,
        required_rules=registry.required_rules,
    )


@pytest.fixture(scope="module")
def golden_ctx():
    return build_context(
        course=__import__("app_zeri.schemas", fromlist=["CourseSpec"]).CourseSpec(
            dt=datetime(2027, 7, 11, 14, 0, tzinfo=CST)
        ),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="normal"),
        person=PersonSpec(),
        cal=CalendarConfig(),
    )


class TestNegativeWithSyntheticVerifiedRule:
    """负向用例：合成已考证规则 → 确定命中 / REJECTED（不依赖真实考证）。"""

    def test_deterministic_veto_marks_definite(self, golden_ctx, registry) -> None:
        reg = _registry_with(registry, _synthetic_rule())
        ev = evaluate(golden_ctx, reg, EvalConfig(task_kind="修造", strictness="normal"))

        hits = [j for res in ev.per_school.values() for j in res.vetoes if j.rule_id == "TEST-VERIFIED-001"]
        assert hits, "合成已考证规则应命中"
        assert hits[0].participation == "判定", "已考证规则必须是「判定」，不是「演示」"
        assert hits[0].is_demo is False
        assert ev.state == STATE_BLOCKED
        assert ev.tier == TIER_REJECTED
        assert ev.vectors["verified_veto_count"] >= 1
        assert ev.vectors["demo_veto_count"] == 0

    def test_report_renders_definite_group(self, golden_ctx, registry) -> None:
        from app_zeri.verifier import VerifyResult
        from core_eval import detect_structure

        reg = _registry_with(registry, _synthetic_rule())
        ev = evaluate(golden_ctx, reg, EvalConfig(task_kind="修造", strictness="normal"))
        result = VerifyResult(
            evaluation=ev,
            context=golden_ctx,
            structure=detect_structure(
                zhis=["未", "未", "卯", "未"], gans=["丁", "丁", "辛", "乙"], shan_jia_zhi="亥"
            ),
        )
        md = render_markdown(result)
        assert "不可用（确定）" in md, "已考证否决命中必须渲染为「不可用（确定）」"
        assert "确定命中（已考证/定义级）" in md
        assert "TEST-VERIFIED-001" in md

    def test_demo_not_rendered_as_definite(self, golden_ctx, registry) -> None:
        """未考证规则命中只能渲染为「演示性不可用」。"""
        ev = evaluate(
            golden_ctx, registry,
            EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True),
        )
        assert ev.vectors["verified_veto_count"] == 0
        assert ev.vectors["demo_veto_count"] >= 1
        from app_zeri.verifier import VerifyResult
        from core_eval import detect_structure

        result = VerifyResult(
            evaluation=ev,
            context=golden_ctx,
            structure=detect_structure(zhis=["未", "未", "卯", "未"], gans=["丁", "丁", "辛", "乙"]),
        )
        md = render_markdown(result)
        assert "演示性不可用" in md
        assert "不可用（确定）" not in md


class TestRequiredSetMeta:
    """必需集元测试：每条必需规则都必须"可判定闭合"，且能满足 publishable。"""

    def test_required_set_is_resolvable(self, registry) -> None:
        """core 组不得依赖 person.*（否则不填命主时永久 unknown）。"""
        for rid in registry.required_for("修造"):
            rule = registry.ruleset.by_id[rid]
            roots = {p.split(".")[0] for p in collect_fact_paths(rule.condition)}
            assert "person" not in roots, f"{rid} 依赖 person.*，应移到 person_dependent"

    def test_required_rules_are_hard_veto(self, registry) -> None:
        for rid in registry.required_for("修造"):
            rule = registry.ruleset.by_id[rid]
            assert rule.hard_veto is True, f"{rid} 不是硬否决，按准入条件不得进必需集"
            assert rule.target != "hour", f"{rid} 是 hour 级，换时辰即可规避"
            assert rule.school not in ("doushou", "xuankong")

    def test_person_dependent_only_when_person_provided(self, registry) -> None:
        without = registry.required_for("修造", person_provided=False)
        with_person = registry.required_for("修造", person_provided=True)
        assert len(with_person) > len(without)
        assert "PUB-CHONGMING-001" in with_person
        assert "PUB-CHONGMING-001" not in without

    def test_task_overrides_differ(self, registry) -> None:
        """嫁娶不涉坐山，必需集必须比修造窄（12 类共用同一组是错的）。"""
        build = set(registry.required_for("修造"))
        marry = set(registry.required_for("嫁娶"))
        assert marry < build, "嫁娶必需集应是修造的严格子集"
        assert "PUB-SANSHA-001" not in marry

    def test_all_unverified_blocks_publishable(self, golden_ctx, registry) -> None:
        """当前状态：10 条必需规则全待考证 → 全部阻塞（安全底线语义）。"""
        ev = evaluate(golden_ctx, registry, EvalConfig(task_kind="修造", strictness="normal"))
        assert len(ev.required_blockers) == len(ev.required_rule_ids)
        assert ev.publishable is False

    def test_satisfied_required_set_enables_publishable(self, golden_ctx, registry) -> None:
        """**验收信号**：把必需集全部替换为已考证版本 → publishable=True。

        这模拟"补完 P0 六条 + 其余必需规则的原文"之后的第一次真实解锁，
        不依赖真实考证进度（合成规则明确标注"测试专用"）。
        """
        required = registry.required_for("修造")
        verified_rules = []
        for rid in required:
            original = registry.ruleset.by_id[rid]
            verified_rules.append(
                dc_replace(
                    original,
                    status="已考证",
                    citation=Citation(
                        source=original.citation.source, kind="classic",
                        quote="测试用原文占位（模拟考证完成）", verified_by="pytest",
                    ),
                )
            )
        reg = _registry_with(registry, *verified_rules)
        ctx = _strip_all_hits(golden_ctx)
        ev = evaluate(ctx, reg, EvalConfig(task_kind="修造", strictness="normal"))

        assert ev.required_rule_ids, "必需集不应为空"
        assert ev.required_blockers == [], f"仍有阻塞：{ev.required_blockers}"
        assert ev.tier != TIER_REJECTED
        assert ev.publishable is True, "必需集全可判定却不可发布 —— 验收信号失效"

    def test_synthetic_verified_rule_unlocks_blocker(self, golden_ctx, registry) -> None:
        """模拟"补齐原文"：把一条待考证必需规则替换为已考证版本 → 阻塞消失。"""
        rid = "PUB-SUIPO-001"
        original = registry.ruleset.by_id[rid]
        verified = dc_replace(
            original,
            status="已考证",
            citation=Citation(
                source=original.citation.source, kind="classic",
                quote="测试用原文占位", verified_by="pytest",
            ),
        )
        reg = _registry_with(registry, verified)
        ctx = _strip_all_hits(golden_ctx)
        ev = evaluate(ctx, reg, EvalConfig(task_kind="修造", strictness="normal"))
        assert all(b["rule_id"] != rid for b in ev.required_blockers)


class TestAdr0013SourceAudit:
    """ADR-0013：出处核查处置——003/TAISUI 移出必需集、D6 strict 退出、YAML 链路验收。"""

    BANNED = ("PUB-SANSHA-003", "PUB-TAISUI-001")

    def test_required_set_rejects_controversial_status(self, registry) -> None:
        """status=有争议 的规则进必需集 → lint 报 required_set_controversial（ADR-0013 D4）。"""
        from app_zeri.cli import _check_required_set
        from core_rule.policy import RequiredRuleSet

        rr = RequiredRuleSet(
            core=("PUB-SANSHA-003",),
            criteria={
                "require_hard_veto": True,
                "allowed_targets": ["mountain", "facing", "day", "person"],
                "forbidden_schools": ["doushou", "xuankong"],
            },
        )
        reg = dc_replace(registry, required_rules=rr)
        problems = _check_required_set(reg)
        assert any("required_set_controversial" in p for p in problems), problems

    def test_xiuzao_required_set_eight_rules(self, registry) -> None:
        """修造必需集 10 → 8（移出三煞占向、太岁占山）。"""
        build = registry.required_for("修造")
        assert len(build) == 8, build
        for rid in self.BANNED:
            assert rid not in build

    def test_sansha_taisui_not_in_any_required_set(self, registry) -> None:
        """遍历全部事项（含 person_provided），两条规则不得出现在任何必需集。"""
        banned = set(self.BANNED)
        for kind in registry.task_kinds:
            ids = set(registry.required_for(kind, person_provided=True))
            assert not (banned & ids), f"{kind}: {banned & ids} 不应出现在必需集"

    def test_public_yaml_loads_as_disposed(self) -> None:
        """T4（第五节 2 修复承诺）：走标准加载器验收 C1/C2 的 YAML 改动。

        合成注入测试只证明引擎行为；YAML 字段拼错、hard_veto 写成字符串、
        citation 缺 pian，只有 loader 级测试能抓到。
        """
        from core_rule.loader import load_rule

        root = Path(__file__).resolve().parents[2]
        for rid in self.BANNED:
            rule = load_rule(root / f"core-rule/rules/public/{rid}.yaml")
            assert rule.status == "有争议", rid
            assert rule.hard_veto is False, rid
            assert rule.citation.pian, rid
            assert rule.citation.quote_kind == "原文", rid

    def test_sansha003_hit_registers_caution_not_veto(self, golden_ctx, registry) -> None:
        """D6：normal 与 strict 两档下 003 命中均为慎用登记，均不进 vetoes。"""
        from tests.conftest import deep_merge

        ctx = deep_merge(golden_ctx, {"facts": {"sansha": {"year": {"hit_facing": True}}}})
        for strictness in ("normal", "strict"):
            ev = evaluate(
                ctx, registry,
                EvalConfig(task_kind="修造", strictness=strictness, allow_unverified=True),
            )
            vetoes = [
                j for res in ev.per_school.values() for j in res.vetoes
                if j.rule_id == "PUB-SANSHA-003"
            ]
            cautions = [
                j for res in ev.per_school.values() for j in res.cautions
                if j.rule_id == "PUB-SANSHA-003"
            ]
            assert not vetoes, f"strictness={strictness}：有争议规则不得升级为否决"
            assert cautions, f"strictness={strictness}：命中应登记为慎用"
