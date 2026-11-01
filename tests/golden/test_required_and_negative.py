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
        assert groups.get("coverage_gaps") == ["GAP-TAISUI-FACING"], "覆盖缺口机器行"

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
        b = dc_replace(
            _synthetic_rule(), version=1,
            condition={"fact": "site.mountain", "op": "eq", "value": "子"},
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
        实测抓到 1 条真违规（ZWX-XIANGSHOU-001 仅 person.*——同命主恒命中），
        其余全库规则引用 facts/time/course 路径。"""
        from app_zeri.cli import _c21_static_warnings

        warnings = _c21_static_warnings(registry)
        assert any("ZWX-XIANGSHOU-001" in w for w in warnings), warnings
        assert len(warnings) == 1, f"基线：静态警告恰 1 条（现 {len(warnings)}）——新增请核对是否真死规则"
        # 语义自检：site./person. 不在候选派生命名空间内
        assert not any("site.mountain".startswith(ns) for ns in ("facts.", "time.", "course."))

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
