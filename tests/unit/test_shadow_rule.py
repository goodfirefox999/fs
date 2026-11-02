"""影子规则语义测试（C 路线 + Q-018）：观察不投票。

「影子模式」必须可被机器验证，否则它只是一句 docstring：
1. 命中要**看得见**（进 `reference` 桶，报告能渲染）；
2. 命中**不得**改变任何强度桶与结论（state/tier/vectors/publishable）。

第 2 条是关键——如果影子规则的命中偷偷进了 positives/vetoes，
它就等于已经投票了，只是没人知道。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from core_eval import EvalConfig, evaluate
from core_rule import default_registry
from tests.conftest import deep_merge

TZ = ZoneInfo("Asia/Shanghai")
SHADOW_ID = "PUB-WUHUANG-PALACE-001"


def _ctx(hit_palace: bool) -> dict:
    from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
    from core_time import CalendarConfig

    ctx = build_context(
        course=CourseSpec(dt=datetime(2027, 7, 11, 14, 0, tzinfo=TZ)),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
        person=PersonSpec(),
        cal=CalendarConfig(),
    )
    return deep_merge(
        ctx,
        {"facts": {"wuhuang": {"year": {"hit_mountain": False, "hit_palace": hit_palace}}}},
    )


def _eval(ctx: dict):
    return evaluate(
        ctx,
        default_registry(),
        EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True, demo_veto=True),
    )


class TestShadowRule:
    def test_rule_is_declared_ineligible(self) -> None:
        rule = default_registry().ruleset.by_id.get(SHADOW_ID)
        assert rule is not None, "影子规则必须能被加载（否则只是躺在磁盘上）"
        assert rule.engine_eligible is False
        assert rule.ineligible_reason == "hit_range_pending_human"
        assert rule.verdict_type == "gate"

    def test_hit_is_visible_in_reference_bucket(self) -> None:
        """命中必须可见：进了 reference 桶，报告才渲染得出来。"""
        ev = _eval(_ctx(True))
        ref_ids = [j.rule_id for school in ev.per_school.values() for j in school.reference]
        assert SHADOW_ID in ref_ids

    def test_hit_does_not_leak_into_strength_buckets(self) -> None:
        """命中不得出现在任何会影响结论的桶里。"""
        ev = _eval(_ctx(True))
        for school, res in ev.per_school.items():
            for bucket in ("vetoes", "cautions", "positives", "unknowns", "structural", "controversial",
                           "demo_hits"):
                ids = [j.rule_id for j in (getattr(res, bucket, None) or [])]
                assert SHADOW_ID not in ids, f"{SHADOW_ID} 泄漏进 {school}.{bucket}"

    def test_hit_does_not_change_state_or_tier(self) -> None:
        """开关影子规则命中，结论必须逐字相同——这是"不投票"的定义。"""
        off = _eval(_ctx(False))
        on = _eval(_ctx(True))
        assert (on.state, on.tier, on.publishable) == (off.state, off.tier, off.publishable)
        assert on.vectors == off.vectors

    def test_hit_does_not_change_rank_order(self) -> None:
        """影子规则不得影响排序（各派 rank_score 是排序依据，必须一致）。"""
        on = {k: v.rank_score for k, v in _eval(_ctx(True)).per_school.items()}
        off = {k: v.rank_score for k, v in _eval(_ctx(False)).per_school.items()}
        assert on == off
