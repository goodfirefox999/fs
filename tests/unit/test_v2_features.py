"""v0.2 新特性测试：定义级分层、unknown 三分类、冲突拆分、口径注册表、strictness、severity 覆盖。"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from core_eval import (
    STATE_BLOCKED,
    STATE_OK,
    STATE_UNSURE,
    TIER_NEEDS_REVIEW,
    TIER_REJECTED,
    EvalConfig,
    evaluate,
)
from core_eval.engine import (
    UNKNOWN_CALIBER,
    UNKNOWN_MISSING_INPUT,
    UNKNOWN_UNVERIFIED,
    classify_unknown,
)
from core_rule.calibers import CALIBER_NAYIN, CALIBER_SANSHA, load_caliber_sets
from core_rule.errors import DSLValidationError
from core_rule.loader import load_rule
from core_rule.models import Rule
from tests.conftest import deep_merge


# --------------------------------------------------------------------------- #
# 定义级分层
# --------------------------------------------------------------------------- #
class TestDefinitional:
    def test_definitional_rules_participate_without_allow_unverified(self, base_ctx, registry) -> None:
        """定义级规则不需要 --allow-unverified 就能参与。"""
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="strict"))
        assert ev.structural, "定义级结构应直接参与"
        assert all(j.definitional for j in ev.structural)

    def test_definitional_not_in_unknown(self, base_ctx, registry) -> None:
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="strict"))
        structural_ids = {j.rule_id for j in ev.structural}
        unknown_ids = {u["rule_id"] for u in ev.unknowns}
        assert not (structural_ids & unknown_ids)

    def test_definitional_does_not_count_toward_strong_avoid(self, base_ctx, registry) -> None:
        """定义级结构一律 severity=记录，**不进 strong_avoid**（ADR-0009 核心约束）。"""
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="strict"))
        assert ev.vectors["structural_count"] >= 1
        assert ev.vectors["structural_record_count"] == ev.vectors["structural_count"]
        assert ev.vectors["strong_avoid_count"] == ev.vectors["assertion_caution_count"]
        assert all(j.severity == "记录" for j in ev.structural)

    def test_definitional_severity_must_be_record(self, tmp_path: Path) -> None:
        """定义级 severity 只能是「记录」—— 慎用/可用/推荐 都是断言（ADR-0009）。"""
        for bad in ("慎用", "可用", "推荐", "禁用"):
            data = {
                "api_version": 1, "rule_id": "DEF-TEST-003", "version": 1, "school": "public",
                "category": "测试", "status": "定义级", "hard_veto": False, "severity": bad,
                "target": "day", "applies_to": {},
                "condition": {"fact": "facts.structure.max_repeat", "op": "gte", "value": 3},
                "citation": {"kind": "spec", "source": "spec §1", "quote": "条款"},
                "tests": ["A", "B"], "explanation": "x",
            }
            path = tmp_path / f"r-{bad}.yaml"
            path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
            with pytest.raises(DSLValidationError, match="只能是「记录」"):
                load_rule(path)

    def test_record_severity_only_for_definitional(self, tmp_path: Path) -> None:
        data = {
            "api_version": 1, "rule_id": "PUB-TEST-005", "version": 1, "school": "public",
            "category": "测试", "status": "待考证", "hard_veto": False, "severity": "记录",
            "target": "day", "applies_to": {},
            "condition": {"fact": "facts.structure.max_repeat", "op": "gte", "value": 3},
            "citation": {"source": "《某书》"},
            "tests": ["A", "B"], "explanation": "x",
        }
        path = tmp_path / "r.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        with pytest.raises(DSLValidationError, match="仅限 status=定义级"):
            load_rule(path)

    def test_definitional_cannot_be_veto(self, tmp_path: Path) -> None:
        """定义级规则不得是硬否决（否决是吉凶断言）。"""
        data = {
            "api_version": 1, "rule_id": "DEF-TEST-001", "version": 1, "school": "public",
            "category": "测试", "status": "定义级", "hard_veto": True, "severity": "禁用",
            "target": "day", "applies_to": {},
            "condition": {"fact": "facts.structure.max_repeat", "op": "gte", "value": 3},
            "citation": {"kind": "spec", "source": "spec §1", "quote": "条款"},
            "tests": ["A", "B"], "explanation": "x",
        }
        path = tmp_path / "r.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        with pytest.raises(DSLValidationError, match="不得为硬否决"):
            load_rule(path)

    def test_definitional_requires_spec_kind(self, tmp_path: Path) -> None:
        data = {
            "api_version": 1, "rule_id": "DEF-TEST-002", "version": 1, "school": "public",
            "category": "测试", "status": "定义级", "hard_veto": False, "severity": "慎用",
            "target": "day", "applies_to": {},
            "condition": {"fact": "facts.structure.max_repeat", "op": "gte", "value": 3},
            "citation": {"kind": "classic", "source": "《某书》", "quote": "某句"},
            "tests": ["A", "B"], "explanation": "x",
        }
        path = tmp_path / "r.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        with pytest.raises(DSLValidationError, match="kind 必须为 spec"):
            load_rule(path)

    def test_verified_requires_classic_kind(self, tmp_path: Path) -> None:
        data = {
            "api_version": 1, "rule_id": "PUB-TEST-002", "version": 1, "school": "public",
            "category": "测试", "status": "已考证", "hard_veto": False, "severity": "慎用",
            "target": "day", "applies_to": {},
            "condition": {"fact": "facts.structure.max_repeat", "op": "gte", "value": 3},
            "citation": {"kind": "spec", "source": "spec", "quote": "条款", "verified_by": "某人"},
            "tests": ["A", "B"], "explanation": "x",
        }
        path = tmp_path / "r.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        with pytest.raises(DSLValidationError, match="kind 必须为 classic"):
            load_rule(path)


# --------------------------------------------------------------------------- #
# unknown 三分类
# --------------------------------------------------------------------------- #
class TestUnknownClassification:
    def test_missing_input(self, base_ctx, registry) -> None:
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="strict"))
        reasons = {u["unknown_reason"] for u in ev.unknowns}
        assert UNKNOWN_MISSING_INPUT in reasons, "命主未提供应归为缺输入"

    def test_caliber_undecided(self, base_ctx, registry) -> None:
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="strict"))
        yinfu = [u for u in ev.unknowns if u["rule_id"] == "PUB-YINFU-001"]
        assert yinfu and yinfu[0]["unknown_reason"] == UNKNOWN_CALIBER
        assert "口径" in (yinfu[0]["remedy"] or "")

    def test_unverified_rule(self, base_ctx, registry) -> None:
        ctx = deep_merge(base_ctx, {"facts": {"suipo": {"hit_mountain": True}}})
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=False))
        suipo = [u for u in ev.unknowns if u["rule_id"] == "PUB-SUIPO-001"]
        assert suipo and suipo[0]["unknown_reason"] == UNKNOWN_UNVERIFIED
        assert "原文" in (suipo[0]["remedy"] or "")

    def test_counts_split(self, base_ctx, registry) -> None:
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="strict"))
        v = ev.vectors
        assert v["unknown_count"] == sum(v["unknown_by_reason"].values())
        assert v["unverified_hit_count"] == v["unknown_by_reason"].get(UNKNOWN_UNVERIFIED, 0)
        assert v["missing_input_count"] == v["unknown_by_reason"].get(UNKNOWN_MISSING_INPUT, 0)
        assert v["caliber_undecided_count"] == v["unknown_by_reason"].get(UNKNOWN_CALIBER, 0)

    def test_classify_direct(self, registry) -> None:
        rule = registry.ruleset.get("PUB-YINFU-001")
        reason, remedy = classify_unknown(
            rule, participation="输入不足", unknown_paths=("facts.yinfu.candidates.value",)
        )
        assert reason == UNKNOWN_CALIBER
        assert "口径" in remedy


# --------------------------------------------------------------------------- #
# 冲突拆分
# --------------------------------------------------------------------------- #
class TestConflictSplit:
    def test_state_divergence_still_works(self, base_ctx, registry) -> None:
        ev = evaluate(
            base_ctx, registry,
            EvalConfig(task_kind="修造", strictness="strict", schools=("public", "zhengwuxing"),
                       allow_unverified=True),
        )
        types = {c["type"] for c in ev.conflicts}
        assert types & {"state_divergence", "verdict_conflict"}
        for c in ev.conflicts:
            if c["type"] in ("state_divergence", "verdict_conflict"):
                assert c["scope"] == "school"
                assert "states" in c

    def test_rule_conflict_detected(self, base_ctx, registry) -> None:
        """同一派内两条规则对同一 target 互斥 → rule_conflict（独立于派别分歧）。"""
        from core_eval.engine import _detect_conflicts, SchoolResult
        from core_eval.engine import Judgment

        def _j(rid: str, sev: str, target: str = "mountain") -> Judgment:
            return Judgment(
                rule_id=rid, rule_version=1, school="public", category=rid, status="已考证",
                severity=sev, target=target, matched=True, participation="判定",
                hit_detail="", explanation="", citation={"source": "x"}, params_hash="h",
            )

        res = SchoolResult(
            school="public", state=STATE_OK,
            vetoes=[_j("A", "禁用")], positives=[_j("B", "推荐")],
        )
        conflicts = _detect_conflicts({"public": res})
        rc = [c for c in conflicts if c["type"] == "rule_conflict"]
        assert rc, "同派内禁用+推荐必须报 rule_conflict"
        assert rc[0]["rule_a"] == "A" and rc[0]["rule_b"] == "B"
        assert rc[0]["scope"] == "school"

    def test_fact_hash_consistent_across_schools(self, base_ctx, registry) -> None:
        ev = evaluate(
            base_ctx, registry,
            EvalConfig(task_kind="修造", strictness="strict", schools=("public", "zhengwuxing"),
                       allow_unverified=True),
        )
        hashes = {r.fact_hash for r in ev.per_school.values()}
        assert len(hashes) == 1, "各派必须看到相同的输入事实"


# --------------------------------------------------------------------------- #
# strictness 三档
# --------------------------------------------------------------------------- #
class TestStrictness:
    def _ctx(self, base_ctx):
        # 注入断言级慎用命中（时冲山：亥 vs 巳）
        return deep_merge(base_ctx, {"course": {"hour": {"zhi": "巳"}}})

    def test_normal_caution_is_unsure(self, base_ctx, registry) -> None:
        ev = evaluate(
            self._ctx(base_ctx), registry,
            EvalConfig(task_kind="修造", strictness="normal", allow_unverified=True),
        )
        assert ev.state == STATE_UNSURE
        assert ev.vectors["assertion_caution_count"] >= 1

    def test_strict_upgrades_caution_to_rejected(self, base_ctx, registry) -> None:
        ev = evaluate(
            self._ctx(base_ctx), registry,
            EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True),
        )
        assert ev.state == STATE_BLOCKED
        assert ev.tier == TIER_REJECTED

    def test_loose_downgrades_caution_to_note(self, base_ctx, registry) -> None:
        ev = evaluate(
            self._ctx(base_ctx), registry,
            EvalConfig(task_kind="修造", strictness="loose", allow_unverified=True),
        )
        assert ev.vectors["assertion_caution_count"] == 0
        assert ev.state in (STATE_OK, STATE_UNSURE)

    def test_strict_does_not_upgrade_structural(self, base_ctx, registry) -> None:
        """定义级结构不因 strict 档变成不可用（记录级不进任何判定通道）。"""
        ev = evaluate(
            base_ctx, registry,
            EvalConfig(task_kind="修造", strictness="strict", allow_unverified=False),
        )
        assert ev.vectors["structural_count"] >= 1
        assert ev.vectors["strong_avoid_count"] == 0
        assert ev.state == STATE_OK


# --------------------------------------------------------------------------- #
# severity_overrides
# --------------------------------------------------------------------------- #
class TestSeverityOverrides:
    def test_override_applied(self, registry) -> None:
        rule = registry.ruleset.get("PUB-SANSHA-001")
        patched = replace(rule, severity_overrides={"public": "慎用"})
        assert patched.severity_for("public") == "慎用"
        assert patched.severity_for("zhengwuxing") == rule.severity

    def test_loader_reads_overrides(self, tmp_path: Path) -> None:
        data = {
            "api_version": 1, "rule_id": "PUB-TEST-003", "version": 1, "school": "public",
            "category": "测试", "status": "待考证", "hard_veto": False, "severity": "禁用",
            "target": "day", "applies_to": {},
            "condition": {"fact": "facts.structure.max_repeat", "op": "gte", "value": 3},
            "citation": {"source": "《某书》"},
            "tests": ["A", "B"], "explanation": "x",
            "severity_overrides": {"public": "慎用"},
        }
        path = tmp_path / "r.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        rule = load_rule(path)
        assert rule.severity_overrides == {"public": "慎用"}

    def test_loader_rejects_bad_override(self, tmp_path: Path) -> None:
        data = {
            "api_version": 1, "rule_id": "PUB-TEST-004", "version": 1, "school": "public",
            "category": "测试", "status": "待考证", "hard_veto": False, "severity": "慎用",
            "target": "day", "applies_to": {},
            "condition": {"fact": "facts.structure.max_repeat", "op": "gte", "value": 3},
            "citation": {"source": "《某书》"},
            "tests": ["A", "B"], "explanation": "x",
            "severity_overrides": {"public": "大凶"},
        }
        path = tmp_path / "r.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        with pytest.raises(DSLValidationError, match="非法严重度"):
            load_rule(path)


# --------------------------------------------------------------------------- #
# 口径注册表
# --------------------------------------------------------------------------- #
class TestCalibers:
    def test_load_defaults(self) -> None:
        reg = load_caliber_sets()
        assert reg.chosen(CALIBER_SANSHA) == "direction_group"
        assert reg.chosen(CALIBER_NAYIN) == "undecided"
        assert not reg.is_decided(CALIBER_NAYIN)

    def test_selection_and_manifest(self) -> None:
        reg = load_caliber_sets().with_selection({CALIBER_SANSHA: "named_sansha"})
        assert reg.chosen(CALIBER_SANSHA) == "named_sansha"
        manifest = reg.to_manifest()
        assert manifest["selection"][CALIBER_SANSHA] == "named_sansha"
        assert "sets" in manifest

    def test_unknown_caliber_rejected(self) -> None:
        reg = load_caliber_sets()
        with pytest.raises(DSLValidationError, match="未声明的口径"):
            reg.with_selection({CALIBER_SANSHA: "not_exists"})

    def test_alternatives_listed(self) -> None:
        reg = load_caliber_sets()
        alts = reg.alternatives(CALIBER_NAYIN)
        names = {a["name"] for a in alts}
        assert {"undecided", "chuanshan", "fenjin", "zhengzhen"} <= names
        assert any(a["requires"] for a in alts), "每个口径必须说明缺什么"

    def test_facts_echo_caliber(self, base_ctx) -> None:
        assert base_ctx["facts"]["_calibers"][CALIBER_SANSHA] == "direction_group"
        assert base_ctx["_meta"]["calibers"]["selection"][CALIBER_NAYIN] == "undecided"

    def test_sansha_caliber_changes_by_name(self) -> None:
        from core_symbol import derive_facts, facing_of, mountain_of_azimuth

        m = mountain_of_azimuth(320.0)
        kwargs = dict(
            year_zhi="未", month_zhi="未", day_ganzhi="辛卯",
            gans=["丁", "丁", "辛", "乙"], zhis=["未", "未", "卯", "未"],
            mountain=m, facing=facing_of(m), shan_jia_zhi="亥",
        )
        coarse = derive_facts(**kwargs, sansha_caliber="direction_group")
        fine = derive_facts(**kwargs, sansha_caliber="named_sansha")
        assert coarse["sansha"]["year"]["by_name"] is None
        assert fine["sansha"]["year"]["by_name"]["灾煞"] == "酉"
        assert coarse["sansha"]["year"]["status"] == "有争议"
        assert fine["sansha"]["year"]["status"] == "待考证"

    def test_registry_with_calibers(self, registry) -> None:
        patched = registry.with_calibers({CALIBER_SANSHA: "named_sansha"})
        assert patched.calibers.chosen(CALIBER_SANSHA) == "named_sansha"
        assert registry.calibers.chosen(CALIBER_SANSHA) == "direction_group", "不得污染原注册表"


# --------------------------------------------------------------------------- #
# publishable
# --------------------------------------------------------------------------- #
class TestPublishable:
    def test_golden_not_publishable(self, base_ctx, registry) -> None:
        """金标准案例：必需集全为待考证 → 不可发布（与 tier 无关）。"""
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="normal"))
        assert ev.required_blockers, "必需集应有待考证阻塞项"
        assert ev.publishable is False
        assert ev.to_dict()["publishable"] is False

    def test_rejected_not_publishable(self, base_ctx, registry) -> None:
        ctx = deep_merge(base_ctx, {"facts": {"suipo": {"hit_mountain": True}}})
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True))
        assert ev.publishable is False


class TestRobustness:
    def test_report_structure(self) -> None:
        from app_zeri.robustness import RobustnessReport, default_perturbations

        perts = default_perturbations(2.0)
        assert len(perts) == 4
        names = [p.name for p in perts]
        assert any("+2" in n for n in names) and any("-2" in n for n in names)
        rep = RobustnessReport(perturbations=names, robust=["a"], sensitive=[])
        rep.stable_ratio = 1.0
        assert rep.is_fully_robust
        assert rep.to_dict()["radius_deg"] is None

    def test_assess_end_to_end(self) -> None:
        from datetime import date

        from app_zeri.generator import generate
        from app_zeri.schemas import SiteSpec, TaskSpec

        result = generate(
            start=date(2027, 7, 1), end=date(2027, 7, 5),
            site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26, angle_uncertainty_deg=3.0),
            task=TaskSpec(kind="修造", strictness="strict"),
            allow_unverified=True, top=4, with_robustness=True,
        )
        assert result.robustness is not None
        rb = result.robustness
        assert rb.radius_deg == 3.0
        assert len(rb.robust) + len(rb.sensitive) == len(result.ranked)
        assert rb.stable_ratio >= 0.0


# --------------------------------------------------------------------------- #
# 必需规则集与 publishable（ADR-0010）
# --------------------------------------------------------------------------- #
class TestRequiredRulesPublishable:
    def test_required_set_loaded(self, registry) -> None:
        """必需集只含 hard_veto 规则（准入条件一）；ASSERT-*（慎用）不得入集。

        ADR-0013：修造必需集 10 → 8（三煞占向、太岁占山因口径与原典相反移出）。
        """
        ids = registry.required_for("修造")
        assert len(ids) == 8
        assert "PUB-SANSHA-001" in ids
        assert "PUB-SANSHA-003" not in ids
        assert "PUB-TAISUI-001" not in ids
        assert not any(rid.startswith("ASSERT-") for rid in ids), (
            "ASSERT-* 是慎用级断言，按准入条件 hard_veto=true 不得进必需集（ADR-0012）"
        )

    def test_required_rules_all_exist(self, registry) -> None:
        for rid in registry.required_rules.all_rule_ids():
            assert rid in registry.ruleset.by_id, f"必需集引用了不存在的规则 {rid}"

    def test_all_unverified_required_block(self, base_ctx, registry) -> None:
        """必需规则未考证 → 即使求值为 False，其「不犯」结论也不可作为发布依据。"""
        ev = evaluate(base_ctx, registry, EvalConfig(task_kind="修造", strictness="normal"))
        assert len(ev.required_blockers) == len(ev.required_rule_ids)
        assert all("未考证" in b["reason"] for b in ev.required_blockers)
        assert ev.publishable is False

    def test_non_required_unverified_does_not_block(self, base_ctx, registry) -> None:
        """非必需规则待考证**不**阻塞：用只含定义级的必需集验证。

        构造：把必需集设为空集（退回严格口径）vs 设为只含定义级规则。
        前者会被"任何未考证命中"阻塞；后者只要求定义级可判定。
        """
        strict_ctx = deep_merge(
            base_ctx,
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
                }
            },
        )
        only_def = evaluate(
            strict_ctx, registry,
            EvalConfig(task_kind="修造", strictness="normal",
                       required_rule_ids=("DEF-REPEAT-001", "DEF-ZIXING-001")),
        )
        assert only_def.required_blockers == []
        # 非必需规则仍有 unknown（命主未提供、阴府口径未定等），但**不阻塞发布**
        assert only_def.vectors["unknown_count"] > 0
        assert only_def.tier != "REJECTED"
        assert only_def.publishable is True, "非必需 unknown 不得阻塞发布（ADR-0010）"

    def test_empty_required_uses_registry_default(self, base_ctx, registry) -> None:
        """显式传空集时由 registry 按 task_kind 注入（与 person_provided 联动）。"""
        ev = evaluate(
            base_ctx, registry,
            EvalConfig(task_kind="修造", strictness="normal", required_rule_ids=()),
        )
        assert ev.required_rule_ids == registry.required_for("修造", person_provided=False)

    def test_required_unknown_blocks(self, base_ctx, registry) -> None:
        """必需集内的规则若"输入不足"，也必须阻塞。"""
        ev = evaluate(
            base_ctx, registry,
            EvalConfig(task_kind="修造", strictness="normal",
                       required_rule_ids=("PUB-CHONGMING-001",)),  # 依赖 person.year_zhi
        )
        assert any(b["rule_id"] == "PUB-CHONGMING-001" for b in ev.required_blockers)
        assert ev.publishable is False


# --------------------------------------------------------------------------- #
# 变异测试暴露的缺口（每个对应一个存活变异）
# --------------------------------------------------------------------------- #
class TestMutationGaps:
    """这些用例是"变异测试发现测试没抓住"后补的，勿删。"""

    def test_demo_participation_marked(self, base_ctx, registry) -> None:
        """变异 `participation = "演示" → "判定"` 的守卫：演示命中必须标记为演示。"""
        ctx = deep_merge(base_ctx, {"facts": {"suipo": {"hit_mountain": True}}})
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="normal", allow_unverified=True))
        demo = [j for res in ev.per_school.values() for j in res.vetoes if j.rule_id == "PUB-SUIPO-001"]
        assert demo, "岁破占山应命中"
        assert demo[0].participation == "演示"
        assert demo[0].is_demo is True
        assert ev.vectors["demo_veto_count"] >= 1
        assert ev.vectors["verified_veto_count"] == 0

    def test_publishable_blocked_by_demo_in_required(self, base_ctx, registry) -> None:
        """变异 `if j.rule_id in required and participation != "判定"` 的守卫。

        用**慎用类**断言规则（ASSERT-REPEAT-001）构造：它在 normal 档下只判存疑，
        不会提前触发 tier==REJECTED 的短路，从而真正测到必需集循环。
        """
        ev = evaluate(
            base_ctx, registry,
            EvalConfig(task_kind="修造", strictness="normal", allow_unverified=True,
                       required_rule_ids=("ASSERT-REPEAT-001",)),
        )
        assert ev.tier != "REJECTED", "慎用类演示命中不应产生 REJECTED"
        assert any(
            j.rule_id == "ASSERT-REPEAT-001" and j.is_demo for j in ev.judgments
        ), "三见应作为演示命中"
        assert ev.publishable is False, "必需规则只是演示 → 不得发布"

    def test_tier_rank_ordering(self) -> None:
        """变异 `TIER_PREFERRED: 0 → 9` 的守卫：等级顺序必须严格递增。"""
        from core_eval.ranker import TIER_RANK

        assert TIER_RANK["PREFERRED"] < TIER_RANK["ACCEPTABLE"]
        assert TIER_RANK["ACCEPTABLE"] < TIER_RANK["NEEDS_REVIEW"]
        assert TIER_RANK["NEEDS_REVIEW"] < TIER_RANK["REJECTED"]
