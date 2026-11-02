"""演示命中的计票隔离测试（ADR-0014 决策 3 / ADR-0015）。

要证明的是**结构性隔离**，不是"某处 if 过滤对了"
------------------------------------------------
坏形态：演示命中先混进计票，再靠 `if not is_demo: continue` 过滤掉——
下一次重构删掉那行，票就悄悄变真，没有任何断言会红。

本项目的实际形态：演示命中被路由到独立的 ``demo_hits`` 桶后 ``continue``，
计票只读 ``vetoes/cautions/positives``；因此"只有演示命中"的派在计票阶段**根本没有判定**，
只会落进 ``non_voters``，理由必须是 ``demo_only_not_voting``（有判断、无票权），
而不是 ``no_verdict``（沉默）——两者语义不同，混同会掩盖考证进度。

金标准候选恰好是最好的样本：4 派有演示命中、1 派完全沉默、闸门 1 派。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from core_eval import EvalConfig, evaluate
from core_rule import default_registry

TZ = ZoneInfo("Asia/Shanghai")


def _ctx():
    from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
    from core_time import CalendarConfig

    return build_context(
        course=CourseSpec(dt=datetime(2027, 7, 11, 14, 0, tzinfo=TZ)),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
        person=PersonSpec(),
        cal=CalendarConfig(),
    )


def _eval(*, demo_veto: bool = False):
    return evaluate(
        _ctx(),
        default_registry(),
        EvalConfig(
            task_kind="修造",
            strictness="strict",
            allow_unverified=True,
            demo_veto=demo_veto,
        ),
    )


def _detail(ev) -> dict:
    return ev.manifest["five_school_output"]["_consensus_detail"]


class TestDemoOnlyCandidate:
    def test_fixture_really_has_demo_hits(self) -> None:
        """先证明样本不是空的：否则下面的"0/0"是废话。"""
        ev = _eval()
        with_demo = [n for n, r in ev.per_school.items() if r.demo_hits]
        assert len(with_demo) >= 3, f"样本应有多派演示命中，实际 {with_demo}"

    def test_zero_voters_and_zero_ratio(self) -> None:
        d = _detail(_eval())
        assert d["voters"] == []
        assert d["consensus_ratio"] == "0/0"
        assert d["votes"]["favorable"] == [] and d["votes"]["unfavorable"] == []

    def test_demo_only_reason_differs_from_silent(self) -> None:
        """4 派「有演示命中但不算票」 vs 1 派「真沉默」——理由必须分开。"""
        ev = _eval()
        reasons = {nv["school"]: nv["reason"] for nv in _detail(ev)["non_voters"]}
        # 只取 scoring 层：闸门/参考层的理由优先级更高（layer_* 先于 demo_*），
        # 这是有意的分层——先回答"这派有没有票权"，再回答"它为什么没投"。
        scoring = {n for n, spec in default_registry().policy.schools.items() if spec.layer == "scoring"}
        demo_only = {
            n
            for n, r in ev.per_school.items()
            if n in scoring and r.demo_hits and not (r.vetoes or r.cautions or r.positives)
        }
        silent = {n for n, r in ev.per_school.items() if not (
            r.vetoes or r.cautions or r.positives or r.demo_hits
        )}
        assert demo_only and silent, "样本需同时含两类"
        for name in demo_only:
            assert reasons[name] == "demo_only_not_voting", f"{name} 应标'有判断无票权'"
        for name in silent:
            assert reasons[name] == "no_verdict", f"{name} 应标'沉默'"

    def test_demo_hits_never_enter_vote_lists(self) -> None:
        d = _detail(_eval())
        for bucket in ("favorable", "unfavorable"):
            assert d["votes"][bucket] == []

    def test_report_explains_the_new_reason(self) -> None:
        from app_zeri.report import _non_voter_reason

        text = _non_voter_reason("demo_only_not_voting")
        assert text and text != "demo_only_not_voting"
        assert "不作为票" in text


class TestExplicitDemoVetoException:
    """`--demo-veto` 是显式联调开关：它允许演示命中按声明严重度路由。

    这不是隔离失效，而是**有意的例外**——所以必须与默认路径分开断言，
    否则"哪天默认路径也这样"就没人发现。
    """

    def test_default_path_and_demo_veto_differ(self) -> None:
        default = _detail(_eval(demo_veto=False))
        forced = _detail(_eval(demo_veto=True))
        assert default["consensus_ratio"] == "0/0"
        # 联调模式下演示命中进入强度桶，因而出现投票派——这是开关的定义，不是 bug
        assert forced["voters"], "demo_veto 下应至少出现一个投票派（否则开关没生效）"
        assert forced["consensus_ratio"] != default["consensus_ratio"]

    def test_zero_voter_notice_still_fires_under_demo_veto(self) -> None:
        """联调模式下票也是演示票，报告的 0/0 提示必须仍然出现。"""
        from app_zeri.report import zero_voter_notice

        assert zero_voter_notice(_eval(demo_veto=True)), (
            "demo_veto 下若出现'有票'假象而未提示，等于用联调开关伪造共识"
        )
