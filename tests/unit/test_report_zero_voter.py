"""报告「0/0 无票」强制提示测试。

背景
----
全仓 0 条已考证规则时，共识比恒为 0/0 或全由演示命中凑成。旧报告把这件事
藏在「共识度」小节里，读者在结论区先看到"可用/4 派同向"，再看小节才知道没有一票是真的。
本测试锁三件事：

1. **位置**：提示必须紧贴 `## 结论` 之后、任何分节之前（"第一行"的机器化）；
2. **措辞顺序**：先"不构成择日结论"，后"谁否决了"——顺序颠倒会让师傅误读为四派同意；
3. **不误报**：真有已考证规则投票时，提示必须消失（否则会变成永久噪音，被读者忽略）。
"""

from __future__ import annotations

from types import SimpleNamespace

from app_zeri.report import zero_voter_notice


def _res(*, verdicts: int = 0, verified: bool = False) -> SimpleNamespace:
    """构造一个派别结果：verdicts 条判定，participation 由 verified 决定。"""
    bucket = [
        SimpleNamespace(participation="判定" if verified else "演示") for _ in range(verdicts)
    ]
    return SimpleNamespace(vetoes=bucket, cautions=[], positives=[])


def _ev(*, voters: list[str], gate: list[str], per_school: dict, ratio: str = "0/0"):
    return SimpleNamespace(
        per_school=per_school,
        manifest={
            "five_school_output": {
                "_consensus_detail": {
                    "consensus_ratio": ratio,
                    "voters": voters,
                    "gate_veto_schools": gate,
                }
            }
        },
    )


class TestNoticeContent:
    def test_zero_voters_emits_notice(self) -> None:
        ev = _ev(voters=[], gate=[], per_school={"public": _res()})
        text = "\n".join(zero_voter_notice(ev))
        assert "0/0" in text
        assert "不构成择日结论" in text
        assert "无参与投票的已考证规则" in text

    def test_gate_veto_line_follows_main_notice(self) -> None:
        ev = _ev(voters=[], gate=["public"], per_school={"public": _res(verdicts=2)})
        lines = [x for x in zero_voter_notice(ev) if x.strip()]
        assert len(lines) == 2
        assert "不构成择日结论" in lines[0], "第一句必须是'不构成结论'，不能先说否决"
        assert "闸门否决" in lines[1] and "public" in lines[1]

    def test_gate_veto_wording_says_ratio_meaningless(self) -> None:
        ev = _ev(voters=[], gate=["public"], per_school={"public": _res(verdicts=2)})
        assert "比值无意义" in "\n".join(zero_voter_notice(ev))


class TestNoFalsePositive:
    def test_verified_votes_suppress_notice(self) -> None:
        ev = _ev(
            voters=["sanhe"],
            gate=[],
            per_school={"sanhe": _res(verdicts=1, verified=True)},
            ratio="1/1",
        )
        assert zero_voter_notice(ev) == []

    def test_demo_only_votes_still_emit_notice(self) -> None:
        """投票派非空、但全是演示命中 —— 仍属"无已考证规则投票"，必须提示。"""
        ev = _ev(
            voters=["sanhe"],
            gate=[],
            per_school={"sanhe": _res(verdicts=1, verified=False)},
            ratio="1/1",
        )
        text = "\n".join(zero_voter_notice(ev))
        assert "1/1" in text
        assert "不构成择日结论" in text

    def test_missing_detail_is_treated_as_zero(self) -> None:
        ev = SimpleNamespace(per_school={"public": _res()}, manifest={})
        assert "0/0" in "\n".join(zero_voter_notice(ev))


class TestPositionInReport:
    def test_notice_precedes_all_sections(self) -> None:
        """集成：真报告里提示必须在「结论」之后、「派别判定明细」之前。"""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from app_zeri.schemas import PersonSpec, SiteSpec, TaskSpec
        from app_zeri.verifier import verify
        from app_zeri.report import render_markdown

        tz = ZoneInfo("Asia/Shanghai")
        result = verify(
            dt=datetime(2027, 7, 11, 14, 0, tzinfo=tz),
            site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
            task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
            person=PersonSpec(),
            allow_unverified=True,
        )
        text = render_markdown(result)
        pos_conclusion = text.find("## 结论")
        pos_notice = text.find("不构成择日结论")
        pos_schools = text.find("## 派别判定明细")
        assert pos_notice > pos_conclusion >= 0
        assert 0 < pos_notice < pos_schools, "提示必须出现在任何分节之前"
