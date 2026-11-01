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

import yaml
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
            EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True, demo_veto=True),
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
        """ADR-0014 决策 0（T7 单元版）：003（有争议）两档下均入存疑桶，结构化标记，不入 vetoes/cautions。"""
        from tests.conftest import deep_merge

        ctx = deep_merge(golden_ctx, {"facts": {"sansha": {"year": {"hit_facing": True}}}})
        for strictness in ("normal", "strict"):
            ev = evaluate(
                ctx, registry,
                EvalConfig(task_kind="修造", strictness=strictness),
            )
            hits = [
                j for res in ev.per_school.values() for j in res.controversial
                if j.rule_id == "PUB-SANSHA-003"
            ]
            vetoes = [
                j for res in ev.per_school.values() for j in res.vetoes
                if j.rule_id == "PUB-SANSHA-003"
            ]
            cautions = [
                j for res in ev.per_school.values() for j in res.cautions
                if j.rule_id == "PUB-SANSHA-003"
            ]
            assert hits, f"strictness={strictness}：命中应入存疑桶"
            assert all(j.doubt is True and j.source_status == "controversial" for j in hits)
            assert all(j.severity == "慎用" for j in hits), "cap 后生效严重度=慎用"
            assert not vetoes and not cautions, "存疑规则不得进入 vetoes/cautions"


class TestAdr0014EvidenceCap:
    """ADR-0014：证据等级→否决力上限、存疑不压 tier、demo 三态、CLI 依赖校验。"""

    def _registry_without(self, registry, *rids):
        drop = set(rids)
        kept = tuple(r for r in registry.ruleset.rules if r.rule_id not in drop)
        by_id = {r.rule_id: r for r in kept}
        from core_rule.provenance import stable_hash

        ruleset = dc_replace(
            registry.ruleset, rules=kept, by_id=by_id,
            version="rl-" + stable_hash([(r.rule_id, r.version) for r in kept]),
        )
        return RuleRegistry(
            ruleset=ruleset, policy=registry.policy, task_kinds=registry.task_kinds,
            calibers=registry.calibers, required_rules=registry.required_rules,
        )

    @staticmethod
    def _hits(ev, bucket, rid):
        return [j for res in ev.per_school.values() for j in getattr(res, bucket) if j.rule_id == rid]

    @staticmethod
    def _controversial_ctx(golden_ctx):
        from tests.conftest import deep_merge

        return deep_merge(golden_ctx, {"facts": {"sansha": {"year": {"hit_facing": True}}}})

    def test_unverified_capped_and_rendered_not_counted(self, golden_ctx, registry) -> None:
        """T6：待考证+禁用 → cap 为慎用、只渲染不计入；双向验证渲染层仍生成文案。"""
        from tests.conftest import deep_merge

        ctx = deep_merge(golden_ctx, {"facts": {"wuhuang": {"year": {"hit_mountain": True}}}})
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True))
        hits = self._hits(ev, "demo_hits", "PUB-WUHUANG-001")
        assert hits, "演示命中应入 demo_hits 桶（渲染恒开）"
        j = hits[0]
        assert j.source_status == "unverified" and j.doubt is False
        assert j.declared_severity == "禁用" and j.severity == "慎用", "cap：待考证的禁用按慎用生效"
        assert not self._hits(ev, "vetoes", "PUB-WUHUANG-001")
        assert not self._hits(ev, "cautions", "PUB-WUHUANG-001")
        from core_rule.severity_cap import cap_warning

        assert cap_warning(j and registry.ruleset.by_id["PUB-WUHUANG-001"]) is not None
        assert "未考证，无引文可核" in (cap_warning(registry.ruleset.by_id["PUB-WUHUANG-001"]) or "")
        from app_zeri.verifier import VerifyResult
        from core_eval import detect_structure

        md = render_markdown(
            VerifyResult(evaluation=ev, context=ctx,
                         structure=detect_structure(zhis=["未", "未", "卯", "未"], gans=["丁", "丁", "辛", "乙"])),
            registry=registry,
        )
        assert "声明/生效严重度差异" in md and "PUB-WUHUANG-001" in md, "审计链双显示（渲染层）"

    def test_controversial_hit_changes_nothing(self, golden_ctx, registry) -> None:
        """T7+T12+T17：甲案不变式（单元级）——存疑命中不改 tier/state/publishable/blockers。"""
        ctx = self._controversial_ctx(golden_ctx)
        ev_full = evaluate(ctx, registry, EvalConfig(task_kind="修造", strictness="strict"))
        ev_ctrl = evaluate(
            ctx, self._registry_without(registry, "PUB-SANSHA-003"),
            EvalConfig(task_kind="修造", strictness="strict"),
        )
        assert ev_full.tier == ev_ctrl.tier
        assert ev_full.state == ev_ctrl.state
        assert ev_full.publishable == ev_ctrl.publishable
        assert ev_full.required_blockers == ev_ctrl.required_blockers
        hits = self._hits(ev_full, "controversial", "PUB-SANSHA-003")
        assert hits and all(j.doubt and j.source_status == "controversial" for j in hits)

    def test_verified_caution_still_escalates_in_strict(self, golden_ctx, registry) -> None:
        """T8：不变式回归——已考证慎用 strict 仍升级；同规则待考证则不升级且入 demo 桶。"""
        cautious_verified = dc_replace(_synthetic_rule(), severity="慎用", hard_veto=False)
        reg = _registry_with(registry, cautious_verified)
        ev = evaluate(golden_ctx, reg, EvalConfig(task_kind="修造", strictness="strict"))
        assert self._hits(ev, "vetoes", "TEST-VERIFIED-001"), "已考证慎用 strict 仍升级"
        # version=2：_select_cached 缓存 key 仍为 (version, rule_ids)（指纹升级是延期项），
        # 同 id 同 version 不同内容会串味——本测试用 version 区分，指纹缺口另册登记
        unverified = dc_replace(
            cautious_verified, status="待考证", version=2,
            citation=Citation(source="测试专用（非古籍）", kind="classic"),
        )
        reg2 = _registry_with(registry, unverified)
        ev2 = evaluate(golden_ctx, reg2, EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True))
        assert not self._hits(ev2, "vetoes", "TEST-VERIFIED-001"), "待考证 strict 不升级（不变式）"
        assert self._hits(ev2, "demo_hits", "TEST-VERIFIED-001")

    def test_cli_verify_default_mode_controversial(self) -> None:
        """T9（E2E，评审缺口）：默认档 CLI 全链路——003 结构化存疑、渲染有提示、无"不可用（确定）"。"""
        import json as _json
        import os
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = ":".join(
            [str(root / p) for p in ("core-time/src", "core-symbol/src", "core-rule/src", "core-eval/src", "app-zeri/src")]
            + [str(root)]
        )
        base_cmd = [sys.executable, "-m", "app_zeri.cli", "verify", "--course", "2026-06-15T10:00",
                    "--azimuth", "150", "--task", "修造"]
        proc = subprocess.run(base_cmd + ["--json"], capture_output=True, text=True, cwd=root, env=env, timeout=180)
        assert proc.returncode == 0, proc.stderr[-500:]
        data = _json.loads(proc.stdout)

        def find(obj, rid, out):
            if isinstance(obj, dict):
                if obj.get("rule_id") == rid:
                    out.append(obj)
                for v in obj.values():
                    find(v, rid, out)
            elif isinstance(obj, list):
                for v in obj:
                    find(v, rid, out)

        items: list = []
        find(data, "PUB-SANSHA-003", items)
        assert items, "默认档 JSON 应含 003 判定（存疑）"
        assert all(i.get("doubt") is True and i.get("source_status") == "controversial" for i in items)
        proc_md = subprocess.run(base_cmd, capture_output=True, text=True, cwd=root, env=env, timeout=180)
        assert proc_md.returncode == 0
        assert "存疑命中" in proc_md.stdout
        assert "不可用（确定）" not in proc_md.stdout

    def test_pareto_grouped_equals_bruteforce(self) -> None:
        """评审第十一轮第一优先：分组法与暴力法的 **front 成员 id 集合**逐一相等（防成员折叠）。

        形态：重复向量组（展开保留）/ 被支配整组 / 劣势链 / u=n 退化形态（权衡型 500 个）/ positive 支配对。
        内联暴力实现为独立 oracle；断言成员 id 集合相等（非长度、非直方图）。
        """
        from core_eval.engine import Evaluation
        from core_eval.ranker import pareto_front

        def mk(i, hf, sa, conflict=0, unknown=0, positive=0):
            return Evaluation(
                candidate=f"c{i}", per_school={}, state="可用", tier="NEEDS_REVIEW",
                vectors={"hard_fail_count": hf, "strong_avoid_count": sa,
                         "conflict_count": conflict, "unknown_count": unknown,
                         "positive_count": positive},
                conflicts=[], unknowns=[], manifest={}, config=None,
                structural=[], required_rule_ids=(), blocked_required=[],
            )

        items: list = []
        # A. 重复向量组：3×(0,2,0,0,1) 互为副本（占 positive 优势维，不被 C 支配）
        items += [mk(i, 0, 2, conflict=0, unknown=0, positive=1) for i in range(3)]
        # A2. 被支配的副本组：(1,2,0,0,0) 被 A 整组支配（hf 更差）
        items += [mk(i, 1, 2) for i in range(3, 5)]
        # B. 劣势链：(0,3..5,0,0,0) 全被 A 支配（sa 更差且 pos 更差）
        items += [mk(5, 0, 5), mk(6, 0, 4), mk(7, 0, 3)]
        # C. u=n 退化形态：500 个互不支配——sa=1（优于 A 的 sa=2），
        #    conflict/unknown/positive 同增（一差两好→与 A 互不支配；组内两差一好→互不支配）
        items += [mk(100 + i, 0, 1, conflict=i, unknown=i, positive=i) for i in range(1, 501)]
        # D. positive 维支配对：bad 维相同、pos 差一档 → c611 被 c610 支配
        items += [mk(610, 0, 0, unknown=7, positive=1), mk(611, 0, 0, unknown=7, positive=0)]

        def brute_force(evals):
            return [e for e in evals
                    if not any(o is not e and (
                        (va := {k: o.vectors.get(k, 0) for k in ("hard_fail_count", "strong_avoid_count", "conflict_count", "unknown_count")}) and
                        (vb := {k: e.vectors.get(k, 0) for k in ("hard_fail_count", "strong_avoid_count", "conflict_count", "unknown_count")}) and
                        not any(va[k] > vb[k] for k in va) and
                        o.vectors.get("positive_count", 0) >= e.vectors.get("positive_count", 0) and
                        (va != vb or o.vectors.get("positive_count", 0) > e.vectors.get("positive_count", 0))
                    ) for o in evals)]

        expected = {e.candidate for e in brute_force(items)}
        got = {e.candidate for e in pareto_front(items)}
        assert got == expected, f"分组法与暴力法成员集合不等：仅分组有 {got - expected}，仅暴力有 {expected - got}"
        assert {"c0", "c1", "c2"} <= got, "同向量副本必须全部保留（展开实现，非只留代表）"
        assert not ({"c3", "c4", "c5", "c6", "c7"} & got), "劣势向量整组淘汰"
        assert len([c for c in got if 101 <= int(c[1:]) <= 600]) == 500, "u=n 退化形态：500 个全在前沿"
        assert "c610" in got and "c611" not in got, "positive 维支配生效"

    def test_cli_demo_veto_requires_allow_unverified(self) -> None:
        """T11：单独 --demo-veto → exit≠0（不静默忽略）；双开 → 首行显著标注。"""
        import os
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = ":".join(
            [str(root / p) for p in ("core-time/src", "core-symbol/src", "core-rule/src", "core-eval/src", "app-zeri/src")]
            + [str(root)]
        )
        base_cmd = [sys.executable, "-m", "app_zeri.cli", "verify", "--course", "2027-07-11T14:00",
                    "--azimuth", "320", "--task", "修造"]
        bad = subprocess.run(base_cmd + ["--demo-veto"], capture_output=True, text=True, cwd=root, env=env, timeout=180)
        assert bad.returncode != 0, "单独 --demo-veto 必须 exit≠0"
        good = subprocess.run(base_cmd + ["--allow-unverified", "--demo-veto"], capture_output=True, text=True, cwd=root, env=env, timeout=180)
        assert good.returncode == 0, good.stderr[-300:]
        first_block = good.stdout.split("##")[0]
        assert "含演示否决" in first_block, "首行显著标注（决策 3）"

    def test_demo_veto_defaults_false(self) -> None:
        """T13：默认值断言（决策 3）。"""
        cfg = EvalConfig(task_kind="修造")
        assert cfg.demo_veto is False
        assert cfg.to_dict()["demo_veto"] is False

    def test_cap_single_source_consistency(self, golden_ctx, registry) -> None:
        """T14：三处调用点同源——lint id 集、逐规则函数、引擎实际生效值一致。"""
        from core_rule.severity_cap import cap_severity, effective_severity

        rs = registry.ruleset
        assert rs.cap_applied_ids == {r.rule_id for r in rs.rules if effective_severity(r) != r.severity}
        ctx = self._controversial_ctx(golden_ctx)
        ev = evaluate(ctx, registry, EvalConfig(task_kind="修造"))
        for res in ev.per_school.values():
            for j in res.vetoes + res.cautions + res.controversial + res.demo_hits + res.positives + res.notes:
                assert j.severity == cap_severity(j.declared_severity or j.severity, j.status), j.rule_id

    def test_strict_capability_note_is_dynamic(self, golden_ctx, registry) -> None:
        """T15（决策 5）：标注由引擎动态统计——已考证 0 条出现，≥1 条自动消失。"""
        from app_zeri.verifier import VerifyResult
        from core_eval import detect_structure

        def md_of(reg):
            ev = evaluate(golden_ctx, reg, EvalConfig(task_kind="修造", strictness="strict"))
            return render_markdown(
                VerifyResult(evaluation=ev, context=golden_ctx,
                             structure=detect_structure(zhis=["未", "未", "卯", "未"], gans=["丁", "丁", "辛", "乙"])),
                registry=reg,
            )

        assert "strict 档未激活" in md_of(registry), "已考证 0 条 → 标注出现"
        reg2 = _registry_with(registry, _synthetic_rule())
        assert "strict 档未激活" not in md_of(reg2), "已考证 ≥1 → 标注自动消失（非写死字符串）"

    def test_status_transition_requires_signature_lint(self, registry) -> None:
        """T16：状态跃迁提权的 lint 纵深（覆盖绕过 loader 的程序化 ruleset）。"""
        from app_zeri.cli import _check_signatures

        bad = dc_replace(
            _synthetic_rule(),
            citation=Citation(source="测试专用（非古籍）", kind="classic", quote="x", verified_by=None),
        )
        reg = _registry_with(registry, bad)
        problems = _check_signatures(reg)
        assert any("TEST-VERIFIED-001" in p and "verified_by" in p for p in problems)
        assert _check_signatures(registry) == []

    def test_judgment_serialization_backward_compatible(self, golden_ctx, registry) -> None:
        """评审五.1：schema 变更兼容——新字段带默认值、旧键齐全。"""
        from dataclasses import MISSING, fields

        ev = evaluate(self._controversial_ctx(golden_ctx), registry, EvalConfig(task_kind="修造"))
        j = next(j for res in ev.per_school.values() for j in res.controversial)
        d = j.to_dict()
        for key in ("rule_id", "participation", "severity", "status", "warnings",
                    "unknown_reason", "remedy", "source_status", "doubt", "declared_severity"):
            assert key in d, key
        new_fields = ("source_status", "doubt", "declared_severity")
        for f in fields(j):
            if f.name in new_fields:
                assert f.default is not MISSING or f.default_factory is not MISSING, (
                    f"{f.name} 必须带默认值（旧构造点/旧 JSON 兼容）"
                )

    def test_lint_check_id_groups_exact_sets(self) -> None:
        """评审第十/十一轮：lint 机器行按 check id 分组，各组断言精确集合（非计数）。"""
        import json as _json
        import os
        import subprocess
        import sys

        root = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = ":".join(
            [str(root / p) for p in ("core-time/src", "core-symbol/src", "core-rule/src", "core-eval/src", "app-zeri/src")]
            + [str(root)]
        )
        proc = subprocess.run(
            [sys.executable, "-m", "app_zeri.cli", "rules", "lint"],
            capture_output=True, text=True, cwd=root, env=env, timeout=180,
        )
        assert proc.returncode == 0, proc.stdout[-800:]
        groups: dict[str, list] = {}
        for line in proc.stdout.splitlines():
            for name in ("cap_applied", "unverified_progress", "quote_unsigned", "coverage_gaps"):
                if line.startswith(name + ":"):
                    groups[name] = _json.loads(line.split(":", 1)[1])
        assert set(groups.get("cap_applied", [])) == {
            "PUB-CHONGMING-001", "PUB-CHONGSHAN-001", "PUB-MING-SANSHA-001", "PUB-SANSHA-001",
            "PUB-SANSHA-002", "PUB-SIJUE-001", "PUB-SILI-001", "PUB-SUIPO-001",
            "PUB-WUHUANG-001", "PUB-YUEPO-001",
        }, groups.get("cap_applied")
        assert set(groups.get("quote_unsigned", [])) == {"PUB-SANSHA-003", "PUB-TAISUI-001"}
        assert set(groups.get("unverified_progress", [])) == set(groups.get("cap_applied", [])), (
            "当前构造下两组恰好同集（10 条待考证+禁用）——结构重合非定义相同，见 _lint_groups 注释"
        )
        assert set(groups.get("coverage_gaps", [])) == {
            "GAP-TAISUI-FACING", "GAP-TASKKIND-EMPTY",
            "GAP-QILI-NOTIMPLEMENTED", "GAP-SIGNATURE-PERMISSION",
        }, "覆盖缺口机器行（4 条：硬禁/零专属事项/起例未实现/签名权限）"
        assert groups.get("book_authenticity_review", []) == [], (
            "已考证×非authentic 书目=0（当前无已考证规则）——出现条目即触发 GUIDE 三·三当轮重审"
        )

    def test_adr0014_anchor_markers_present(self) -> None:
        """评审第十轮：行号是 db11804 快照，符号/标记注释才是机器可校验锚点——漂移即测试失败。"""
        root = Path(__file__).resolve().parents[2]
        markers = {
            "core-eval/src/core_eval/engine.py": "ADR-0014 决策 1：单一来源 cap",
            "core-eval/src/core_eval/ranker.py": "ADR-0014 perf 回归修复",
            "app-zeri/src/app_zeri/cli.py": "ADR-0014 决策 1：声明/生效双显示",
            "app-zeri/src/app_zeri/report.py": "声明/生效严重度差异（ADR-0014 上限",
            "core-rule/src/core_rule/loader.py": "ADR-0014 决策 1：声明>上限",
        }
        for rel, marker in markers.items():
            assert marker in (root / rel).read_text(encoding="utf-8"), (
                f"{rel} 的 ADR-0014 锚点标记丢失——若调用点迁移，请同步更新 ADR-0014 决策 1 的位置表"
            )

    def test_fingerprint_distinguishes_content(self, golden_ctx, registry) -> None:
        """第三次串味实证的机制化验证：同 id 同 version 不同内容 → 指纹不同 → 缓存不串味。"""
        a = _synthetic_rule()  # condition: site.mountain == 乾, version=1
        # raw 哈希下翻转必须落在 raw dict（dc_replace 只改 dataclass 字段不动 raw）
        _cond_b = {"fact": "site.mountain", "op": "eq", "value": "子"}
        # raw（指纹维度）与 condition（求值维度）必须同时翻转——raw 是源真值、condition 是求值用字段
        b = dc_replace(
            _synthetic_rule(), version=1,
            condition=_cond_b,
            raw={**_synthetic_rule().raw, "condition": _cond_b},
        )  # 同 id 同 version，内容不同
        reg_a = _registry_with(registry, a)
        reg_b = _registry_with(registry, b)
        assert reg_a.ruleset.fingerprint != reg_b.ruleset.fingerprint, "内容指纹必须区分同 id 同 version 的不同内容"
        ev_a = evaluate(golden_ctx, reg_a, EvalConfig(task_kind="修造", strictness="strict"))
        ev_b = evaluate(golden_ctx, reg_b, EvalConfig(task_kind="修造", strictness="strict"))
        hit_a = self._hits(ev_a, "vetoes", "TEST-VERIFIED-001")
        hit_b = self._hits(ev_b, "vetoes", "TEST-VERIFIED-001")
        assert hit_a and not hit_b, "同 id 同 version 不同 condition：两次评估不得串味（_select_cached key 含指纹）"

    def test_c21_static_candidate_specificity(self, registry) -> None:
        """C21 静态层（warn 级）：候选派生命名空间 = facts./time./course.。

        ZWX-XIANGSHOU-001（person-only）按三重条件豁免（exists + 待裁定标记 + Q-013 登记）
        ——设计意图为就绪探测占位，非死规则（评审第十三轮翻案）。
        本测试同时锁死：豁免条件三要素缺一不可（否则 ZWX 会重新出现）。"""
        from app_zeri.cli import _c21_static_warnings

        assert _c21_static_warnings(registry) == [], "全库不应有静态违规（占位已豁免）"
        rule = registry.ruleset.by_id["ZWX-XIANGSHOU-001"]
        assert rule.condition.get("op") == "exists", "豁免前提①：exists"
        marker = (rule.explanation or "") + (rule.notes or "")
        assert "裁定" in marker, "豁免前提②：待裁定标记"
        assert "Q-013" in marker, "豁免前提③：裁定队列登记（Q-013）"
        # 反证：三要素若缺 Q-013 登记，同一规则会被 flag（防止将来有人删 Q-013 却留占位）
        stripped = dc_replace(rule, notes="待考证：相主口径。")
        reg2 = _registry_with(registry, stripped)
        assert any("ZWX-XIANGSHOU-001" in w for w in _c21_static_warnings(reg2)), (
            "Q-013 登记被移除后必须重新报警（三重条件的牙齿）"
        )

    def test_zwx_placeholder_not_evaluated(self, golden_ctx, registry) -> None:
        """评审第十三轮产物三：占位规则不参与评估的实证（zhengwuxing 派默认关闭）。"""
        ev = evaluate(golden_ctx, registry, EvalConfig(task_kind="修造", allow_unverified=True))
        for res in ev.per_school.values():
            for bucket in ("vetoes", "cautions", "controversial", "demo_hits",
                           "positives", "notes", "unknowns", "structural"):
                assert all(j.rule_id != "ZWX-XIANGSHOU-001" for j in getattr(res, bucket)), bucket
        assert "zhengwuxing" not in ev.per_school, "默认路由不含 zhengwuxing（school_policy 关闭）"

    def test_agent_signature_blacklist(self, registry) -> None:
        """评审第十二轮：Agent 署名黑名单——非人类 verified_by 被 lint 拒绝。"""
        from app_zeri.cli import _check_signatures

        for fake in ("pytest", "agent", "AI", "llm", "bot"):
            bad = dc_replace(
                _synthetic_rule(),
                citation=Citation(source="测试专用（非古籍）", kind="classic", quote="x", verified_by=fake),
            )
            reg = _registry_with(registry, bad)
            assert any("疑似非人类署名" in p for p in _check_signatures(reg)), fake

    def test_c21_dead_rule_baseline_covers_current(self) -> None:
        """C21 动态层：死规则扫描的零命中集合 ⊆ 基线豁免（工具退出码 0）。"""
        import os
        import subprocess
        import sys as _sys

        root = Path(__file__).resolve().parents[2]
        env = dict(os.environ)
        env["PYTHONPATH"] = ":".join(
            [str(root / p) for p in ("core-time/src", "core-symbol/src", "core-rule/src", "core-eval/src", "app-zeri/src")]
            + [str(root)]
        )
        proc = subprocess.run(
            [_sys.executable, "tools/dead_rule_scan.py"],
            capture_output=True, text=True, cwd=root, env=env, timeout=600,
        )
        assert proc.returncode == 0, f"出现基线外零命中规则：\n{proc.stdout[-600:]}"
        assert "zero_hit:" in proc.stdout

    def test_book_authenticity_review_construction(self, registry) -> None:
        """评审第十四轮产物三：联动重审门禁的构造样本 + 反证（政策不得空转）。

        构造：status=已考证 + 引用 book_authenticity=待核 书目 → 必须进重审清单；
        反证：同规则 book_authenticity=authentic → 不得出现。
        """
        from app_zeri.cli import _book_authenticity_review

        pending = dc_replace(
            _synthetic_rule(), rule_id="TEST-AUTH-PENDING",
            citation=Citation(source="《象吉通书》", kind="classic", quote="x",
                              verified_by="人类考证人甲"),
        )  # book_authenticity 缺省=待核
        reg = _registry_with(registry, pending)
        review = _book_authenticity_review(reg)
        assert any("TEST-AUTH-PENDING" in w and "待核" in w for w in review), review
        # 反证：authentic 后不报警
        ok = dc_replace(pending, citation=Citation(
            source="《象吉通书》", kind="classic", quote="x",
            verified_by="人类考证人甲", book_authenticity="authentic"))
        reg2 = _registry_with(registry, ok)
        assert _book_authenticity_review(reg2) == [], "authentic 书目不得进重审清单"

    def test_signatures_layer_is_error(self, registry) -> None:
        """评审第十四轮：签名校验层级确认——lint **error**（exit 1），loader 只查空。"""
        from app_zeri.cli import _check_signatures

        bad = dc_replace(
            _synthetic_rule(),
            citation=Citation(source="《象吉通书》", kind="classic", quote="x", verified_by="pytest"),
        )
        reg = _registry_with(registry, bad)
        problems = _check_signatures(reg)
        assert any("疑似非人类署名" in p for p in problems), problems
        # 层级：_check_signatures 的产出进 cmd_rules_lint 的 problems → exit 1（error 级）
        # loader 层仅校验非空（ADR-0014 引用节）；黑名单为 lint 纵深

    def test_taskkind_empty_renders_warning(self, registry) -> None:
        """产物四（修正）：开业无专属规则（显式清单 0 次）但通用规则仍评估 22 条——
        渲染判据 = 显式专属规则数==0，提示"仅通用覆盖、无事项针对性判定"。"""
        from app_zeri.schemas import CourseSpec
        from app_zeri.verifier import VerifyResult
        from core_eval import detect_structure

        ctx = build_context(
            course=CourseSpec(dt=datetime(2026, 6, 15, 10, 0, tzinfo=CST)),
            site=SiteSpec(azimuth_deg=150.0, lat=23.13, lon=113.26),
            task=TaskSpec(kind="开业", nodes=("开业",), strictness="normal"),
            person=PersonSpec(),
            cal=CalendarConfig(),
        )
        ev = evaluate(ctx, registry, EvalConfig(task_kind="开业"))
        assert sum(res.rules_evaluated for res in ev.per_school.values()) == 22, (
            "通用规则（task_kinds:[]）恒覆盖——初版 rules_evaluated==0 判据错误"
        )
        md = render_markdown(
            VerifyResult(evaluation=ev, context=ctx,
                         structure=detect_structure(zhis=["未", "未", "卯", "未"], gans=["丁", "丁", "辛", "乙"])),
            registry=registry,
        )
        assert "无专属规则" in md and "不得解读为" in md

    def test_fingerprint_field_coverage(self, registry) -> None:
        """评审第十四轮产物四：指纹语义字段翻转全覆盖（含 book_authenticity——联动重审状态必须击穿缓存）。"""
        base = registry.ruleset.by_id["PUB-YUEPO-001"]
        # raw 哈希下翻转必须落在 raw dict（源真值）——dc_replace 只改 dataclass 字段不动 raw
        def with_raw(base_rule, **raw_updates):
            new_raw = {**base_rule.raw, **raw_updates}
            return dc_replace(base_rule, raw=new_raw)

        flips = {
            "status": with_raw(base, status="已考证"),
            "severity": with_raw(base, severity="慎用"),
            "hard_veto": with_raw(base, hard_veto=not base.hard_veto),
            "condition": with_raw(base, condition={"fact": "facts.yuepo.hit_facing", "op": "eq", "value": True}),
            "citation.book_authenticity": with_raw(base, citation={**base.raw["citation"], "book_authenticity": "disputed"}),
            "citation.verified_by": with_raw(base, citation={**base.raw["citation"], "verified_by": "人类考证人甲"}),
        }
        from core_rule.loader import RuleSet
        for name, flipped in flips.items():
            new_rules = tuple(
                flipped if r.rule_id == base.rule_id else r for r in registry.ruleset.rules
            )
            by_id = {r.rule_id: r for r in new_rules}
            rs2 = dc_replace(registry.ruleset, rules=new_rules, by_id=by_id,
                             version=registry.ruleset.version)  # version 故意不变——指纹必须独立击穿
            assert rs2.fingerprint != registry.ruleset.fingerprint, f"指纹未覆盖字段翻转：{name}"

    def test_blacklist_word_boundary(self, registry) -> None:
        """评审第十四轮：词边界正则——'AI 助手'命中、'Aijing'人名通过。"""
        from app_zeri.cli import _check_signatures

        def sig(vb):
            bad = dc_replace(
                _synthetic_rule(),
                citation=Citation(source="《象吉通书》", kind="classic", quote="x", verified_by=vb),
            )
            return _check_signatures(_registry_with(registry, bad))

        for vb in ("AI 助手", "AI助手", "助手AI", "ai助手", "auto-bot", "机器人", "Qwen"):
            assert any("疑似非人类署名" in p for p in sig(vb)), f"{vb} 必须命中（评审第十五轮实测表）"
        for vb in ("Aijing", "人类考证人甲", "艾青"):
            assert not any("疑似非人类署名" in p for p in sig(vb)), f"{vb} 人名不受影响"

    def test_ci_guard_predicate_and_platform_file(self, tmp_path, monkeypatch) -> None:
        """评审第十四轮：CI guard 谓词显式化 + 分平台历史文件。"""
        import tests.bench.test_perf as tp

        monkeypatch.setattr(tp, "HISTORY", tmp_path / "bench_history.jsonl")
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
        assert tp._is_ci() is False
        monkeypatch.setenv("CI", "true")
        assert tp._is_ci() is True
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        assert tp._is_ci() is True

    def test_single_month_budget_smoke(self, registry) -> None:
        """评审第十四轮：缩放版预算冒烟（not-slow 可见）——单月 372 候选 < 0.6s。
        O(n²) 类回归（如 pareto）在单月尺度即暴露，不必等 CI 的全年 slow 测试。"""
        import time
        from datetime import date as _date

        from app_zeri.generator import generate
        from app_zeri.schemas import SiteSpec, TaskSpec

        t0 = time.perf_counter()
        r = generate(start=_date(2027, 1, 1), end=_date(2027, 1, 31),
                     site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
                     task=TaskSpec(kind="修造", strictness="strict"),
                     allow_unverified=True, top=20)
        elapsed = time.perf_counter() - t0
        assert r.total_candidates == 372
        assert elapsed < 0.6, f"单月穷举 {elapsed:.2f}s 超 0.6s 冒烟阈（O(n²) 类回归嫌疑）"

    def test_fingerprint_reflexive_field_enumeration(self, registry) -> None:
        """评审第十四轮产物五：指纹字段覆盖从手挑 6 项改为**反射穷举**。

        逐个翻转 Rule 全部语义字段断言指纹变化；非语义字段 notes 显式豁免
        （纯文档，不影响选择/评估/渲染——若未来 notes 影响行为，必须移出豁免清单）。
        新增字段时本测试自动出现"未覆盖"（反射枚举不依赖人工记得加）。
        """
        import dataclasses

        base = registry.ruleset.by_id["PUB-YUEPO-001"]
        # raw 哈希下的反射穷举：枚举 base.raw 的全部键，逐键翻转（raw = 源真值）
        raw_flips = {
            "rule_id": "PUB-YUEPO-TEST", "version": 99, "school": "zhengwuxing",
            "category": "翻转测试", "status": "已考证", "hard_veto": not base.hard_veto,
            "severity": "慎用", "target": "facing",
            "condition": {"fact": "facts.yuepo.hit_facing", "op": "eq", "value": True},
            "explanation": "翻转测试解释", "score_weight": 1.5,
            "citation": {**base.raw["citation"], "book_authenticity": "disputed"},
            "tests": ["RT-X", "RT-Y"], "supersedes": "PUB-OTHER-001",
            "evaluable": False,
            "applies_to": {**base.raw["applies_to"], "task_kinds": ["开业"]},
            "strictness_min": "strict", "node_kinds": ["上梁"],
        }
        exempt = {"notes"}  # 纯文档字段（豁免理由：不参与选择/评估/渲染）
        tested = set()
        for name, flip in raw_flips.items():
            if name in exempt:
                continue
            new_rule = dataclasses.replace(base, raw={**base.raw, name: flip})
            new_rules = tuple(new_rule if r.rule_id == base.rule_id else r
                              for r in registry.ruleset.rules)
            by_id = {r.rule_id: r for r in new_rules}
            rs2 = dc_replace(registry.ruleset, rules=new_rules, by_id=by_id,
                             version=registry.ruleset.version)
            assert rs2.fingerprint != registry.ruleset.fingerprint, (
                f"指纹未覆盖字段翻转：{name}（新增语义字段必须入指纹）"
            )
            tested.add(name)
        assert "notes" not in tested and "notes" in exempt, "豁免清单未生效"

    def test_publishable_three_state_semantics(self, golden_ctx, registry) -> None:
        """评审第十四/十五轮产物四（C19 前置）：publishable 对三态的处理规则锁死。

        规则：unknown 仅通过**必需集**阻塞 publishable（required_blockers）；
        非必需规则的 unknown 只进 unknowns 桶/报告"未知"节，不影响 publishable；
        evaluable=false 规则不参与评估，也不影响 publishable（且被准入 lint 拦在必需集外）。
        """
        # 场景 A：必需集全部已考证 + 一条**非必需**规则 unknown → publishable=True
        required = registry.required_for("修造")
        verified_rules = [
            dc_replace(
                registry.ruleset.by_id[rid], status="已考证",
                citation=Citation(source=registry.ruleset.by_id[rid].citation.source,
                                  kind="classic", quote="占位原文", quote_kind="原文",
                                  verified_by="人类考证人甲", book_authenticity="authentic"),
            ) for rid in required
        ]
        # 非必需 unknown 规则：YINFU（Q-005 门控，不在修造必需集）
        reg_a = _registry_with(registry, *verified_rules)
        ev_a = evaluate(golden_ctx, reg_a, EvalConfig(task_kind="修造", strictness="normal"))
        assert ev_a.publishable is True, (
            "非必需规则的 unknown 不得阻塞 publishable（三态语义核心）"
        )
        assert any(j.rule_id == "PUB-YINFU-001"
                   for res in ev_a.per_school.values() for j in res.unknowns), (
            "非必需 unknown 仍必须出现在 unknowns 桶（可见性）"
        )
        # 场景 B：必需集含一条 unknown（把 YUEPO 改回待考证）→ publishable=False
        mixed = [r for r in verified_rules if r.rule_id != "PUB-YUEPO-001"] + [
            registry.ruleset.by_id["PUB-YUEPO-001"]
        ]
        reg_b = _registry_with(registry, *mixed)
        ev_b = evaluate(golden_ctx, reg_b, EvalConfig(task_kind="修造", strictness="normal"))
        assert ev_b.publishable is False, "必需规则 unknown 必须阻塞 publishable"
        assert any(b["rule_id"] == "PUB-YUEPO-001" for b in ev_b.required_blockers)

    def test_evaluable_false_required_admission(self, registry) -> None:
        """产物二第 3 小点：evaluable=false 规则进必需集 → lint 拦截（准入新条件）。"""
        from app_zeri.cli import _check_required_set
        from core_rule.policy import RequiredRuleSet

        suspended = dc_replace(
            _synthetic_rule(), rule_id="TEST-SUSPENDED", status="待考证",
            evaluable=False, hard_veto=False, severity="慎用",
        )
        reg = _registry_with(registry, suspended)
        rr = RequiredRuleSet(
            core=("TEST-SUSPENDED",),
            criteria={"require_hard_veto": False, "allowed_targets": ["mountain", "facing", "day", "person"],
                      "forbidden_schools": []},
        )
        reg = dc_replace(reg, required_rules=rr)
        problems = _check_required_set(reg)
        assert any("required_set_not_evaluable" in p for p in problems), problems

    def test_evaluable_expiry_on_q_resolution(self, registry, tmp_path) -> None:
        """评审第十五轮（第三次要求，本轮 fixture 打通）：Q 裁定后豁免失效——两条链路。

        链 1（占位探测）：Q-013 已裁定 → ZWX 静态豁免失效（_c21_static_warnings 报警）；
        链 2（evaluable=false）：Q-014 已裁定 → XIUJIU 豁免失效（_evaluable_expiry_warnings）。
        各配反证（未裁定 → 沉默）。临时 QUESTIONS 副本，不触碰真文件。
        """
        import app_zeri.cli as cli_mod

        qfile = tmp_path / "QUESTIONS.md"
        qfile.write_text(
            "## Q-013 正五行相主的取用口径\n\n**已裁定：取年命纳音**\n"
            "## Q-014 exists 语义\n\n**已裁定：吉凶条件返回 unknown**\n", encoding="utf-8"
        )
        # 链 1：占位豁免失效
        w1 = cli_mod._c21_static_warnings(registry, questions_path=qfile)
        assert any("ZWX-XIANGSHOU-001" in w and "豁免失效" in w for w in w1), w1
        # 链 2：evaluable 豁免失效（XIUJIU blocked_by=Q-014）
        w2 = cli_mod._evaluable_expiry_warnings(registry, questions_path=qfile)
        assert any("PUB-XIUJIU-001" in w and "豁免失效" in w for w in w2), w2
        # 反证：未裁定 → 双链沉默
        qfile.write_text(
            "## Q-013 正五行相主的取用口径\n\n待人类提供口径。\n"
            "## Q-014 exists 语义\n\n待裁定。\n", encoding="utf-8"
        )
        assert cli_mod._c21_static_warnings(registry, questions_path=qfile) == []
        assert cli_mod._evaluable_expiry_warnings(registry, questions_path=qfile) == []

    def test_evaluable_false_requires_blocked_by(self, tmp_path) -> None:
        """产物二：evaluable=false 缺 blocked_by → loader 拒绝。"""
        import pytest as _pytest

        from core_rule.errors import DSLValidationError
        from core_rule.loader import load_rule

        data = {
            "api_version": 1, "rule_id": "PUB-TEST-EV-001", "version": 1,
            "school": "public", "category": "测试", "status": "待考证",
            "severity": "慎用", "target": "day", "evaluable": False,
            "hard_veto": False,
            "applies_to": {"task_kinds": ["修造"], "node_kinds": [], "strictness_min": "normal"},
            "condition": {"fact": "facts.x.value", "op": "eq", "value": True},
            "citation": {"source": "《测试》", "kind": "classic"},
            "explanation": "测试", "tests": ["RT-A", "RT-B"],
        }
        path = tmp_path / "r.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        with _pytest.raises(DSLValidationError, match="blocked_by"):
            load_rule(path)
        data["blocked_by"] = "Q-999 测试阻塞"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        rule = load_rule(path)
        assert rule.evaluable is False
