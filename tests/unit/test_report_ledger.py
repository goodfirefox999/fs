"""神煞宜忌台账（事实层）测试。

守两件事：
1. 台账必须把「命中了什么、参与状态、证据等级、原文状态」摆出来；
2. 台账**不得**变成等第比较或综合宜忌结论（Q-030 未实现）。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app_zeri.report import render_markdown
from app_zeri.schemas import PersonSpec, SiteSpec, TaskSpec
from app_zeri.verifier import verify
from core_rule.registry import default_registry

TZ = ZoneInfo("Asia/Shanghai")


def _render() -> str:
    reg = default_registry()
    result = verify(
        dt=datetime(2027, 7, 1, 9, 0, tzinfo=TZ),
        site=SiteSpec(azimuth_deg=315.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="安葬", nodes=("安葬",), strictness="strict"),
        person=PersonSpec(year_gz="庚戌"),
        registry=reg,
        schools=("doushou",),
        allow_unverified=True,
    )
    return render_markdown(result, registry=reg)


def _ledger(markdown: str) -> str:
    lines = markdown.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith("## 神煞宜忌台账")), None
    )
    assert start is not None, "报告缺少神煞宜忌台账节"
    block: list[str] = []
    for line in lines[start:]:
        if block and line.startswith("## "):
            break
        block.append(line)
    return "\n".join(block)


class TestHitLedger:
    def test_rows_carry_participation_and_grade(self) -> None:
        text = _ledger(_render())
        assert "| 派别 | 规则 | 类别 | 声明宜忌 | 参与状态 | 证据等级 | 原文状态 |" in text
        assert "| `doushou` | `DS-HUAQI-001` | 斗首化气 | 可用 | 演示 |" in text
        assert "C（出处待定位）" in text
        assert "待考证" in text

    def test_declares_fact_layer_boundary(self) -> None:
        text = _ledger(_render())
        assert "不比较轻重" in text
        assert "不输出综合宜忌" in text
        assert "Q-030" in text

    def test_no_aggregate_or_total_score(self) -> None:
        text = _ledger(_render())
        for forbidden in ("综合宜忌：", "等第：", "总分", "吉凶分", "综合评分"):
            assert forbidden not in text, f"台账出现综合判断字段：{forbidden}"
