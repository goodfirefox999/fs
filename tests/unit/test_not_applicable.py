"""「不适用」参与状态：与「输入不足」区分，且不阻塞 publishable。

对应 QUESTION Q-026（四维山正针日冲山取法）。2026-11-04 起口径：
- 四维山（乾/坤/艮/巽）：取法未裁定 → ``not_applicable``，不进入 blocked_required；
- 地支山：取法未裁定 → ``input_insufficient``，不得以「不冲」静默放行；
- 裁定后地支山照常判定（命中仍按待考证规则只登记）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
from core_eval import UNKNOWN_NOT_APPLICABLE, EvalConfig, evaluate
from core_rule import default_registry
from core_rule.calibers import CALIBER_Q026_SISHAN_CHONG, load_caliber_sets
from core_time import CalendarConfig

DT = datetime(2027, 7, 14, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


def _ctx(azimuth: float, *, q026: str = "undecided") -> dict[str, Any]:
    creg = load_caliber_sets().with_selection({CALIBER_Q026_SISHAN_CHONG: q026})
    return build_context(
        course=CourseSpec(dt=DT),
        site=SiteSpec(azimuth_deg=azimuth, lat=23.13, lon=113.26),
        task=TaskSpec(kind="安葬", nodes=("安葬",), strictness="normal"),
        person=PersonSpec(),
        cal=CalendarConfig(),
        calibers=creg,
    )


def _ev(ctx: dict[str, Any], *, required: tuple[str, ...] = ("PUB-CHONGSHAN-001",)):
    return evaluate(
        ctx,
        default_registry(),
        EvalConfig(task_kind="安葬", strictness="normal", required_rule_ids=required),
    )


def _chongshan_bucket(ev) -> list:
    return [
        j
        for res in ev.per_school.values()
        for j in res.not_applicable
        if j.rule_id == "PUB-CHONGSHAN-001"
    ]


class TestSishanDayChong:
    def test_default_caliber_marks_sishan_not_applicable(self) -> None:
        """Q-026 未裁定：四维山标「不适用」，且不进入 blocked_required。"""
        ctx = _ctx(315.0)  # 乾山正针，无地支
        assert ctx["site"]["shan_jia_zhi"] is None
        ev = _ev(ctx)

        bucket = _chongshan_bucket(ev)
        assert len(bucket) == 1
        j = bucket[0]
        assert j.participation == "不适用"
        assert j.unknown_reason == UNKNOWN_NOT_APPLICABLE
        assert j.remedy and "Q-026" in j.remedy

        assert not any(u["rule_id"] == "PUB-CHONGSHAN-001" for u in ev.unknowns)
        assert not any(b["rule_id"] == "PUB-CHONGSHAN-001" for b in ev.required_blockers)
        assert [b["rule_id"] for b in ev.required_not_applicable] == ["PUB-CHONGSHAN-001"]
        assert ev.publishable is True, "不适用不得阻塞发布"

    def test_not_taboo_still_not_applicable(self) -> None:
        """裁定「四维山不忌日冲山」后仍是「不适用」，语义不变。"""
        ctx = _ctx(315.0, q026="not_taboo")
        ev = _ev(ctx)

        bucket = _chongshan_bucket(ev)
        assert len(bucket) == 1
        assert bucket[0].participation == "不适用"
        assert ev.publishable is True

    def test_zhi_mountain_default_is_input_insufficient(self) -> None:
        """地支山在取法未裁定时必须报「输入不足」，不得静默判不冲。"""
        ctx = _ctx(0.0)  # 子山
        assert ctx["site"]["shan_jia_zhi"] == "子"
        ev = _ev(ctx)

        assert _chongshan_bucket(ev) == []
        assert any(
            u["rule_id"] == "PUB-CHONGSHAN-001"
            and u["unknown_reason"] in ("missing_input", "caliber_undecided")
            for u in ev.unknowns
        )
        assert any(b["rule_id"] == "PUB-CHONGSHAN-001" for b in ev.required_blockers)
        assert ev.publishable is False

    def test_not_taboo_does_not_overreach_to_zhi_mountain(self) -> None:
        """口径只对四维山生效：子山照常判定（午日冲子 → 仅登记，不是不适用）。"""
        ctx = _ctx(0.0, q026="not_taboo")  # 子山
        assert ctx["site"]["shan_jia_zhi"] == "子"
        ev = _ev(ctx)

        assert _chongshan_bucket(ev) == []
        assert any(
            j.rule_id == "PUB-CHONGSHAN-001" and j.participation == "仅登记"
            for res in ev.per_school.values()
            for j in res.unknowns
        )

    def test_unknown_guard_falls_back_to_input_insufficient(self) -> None:
        """守卫条件求值失败时不得静默放行：退回「输入不足」。"""
        import copy

        ctx = copy.deepcopy(_ctx(315.0, q026="not_taboo"))
        del ctx["facts"]["_calibers"][CALIBER_Q026_SISHAN_CHONG]
        ev = _ev(ctx)

        assert _chongshan_bucket(ev) == []
        assert any(
            u["rule_id"] == "PUB-CHONGSHAN-001" and u["unknown_reason"] == "missing_input"
            for u in ev.unknowns
        )
        assert ev.publishable is False
