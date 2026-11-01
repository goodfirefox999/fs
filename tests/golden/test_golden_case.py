"""金标准回归：GS-2027-0711（乾山巽向兼亥巳·换修天面·2027-07-11 未时）。

本文件是**阻断合并**的门禁测试。它逐条对应 docs/DEVELOPMENT.md 第 6.3 节与第 10.1 节
对"上一案例"的硬性要求：

1. 四柱 = 丁未 丁未 辛卯 乙未
2. 亥卯未三合扶山 → 正向证据（AUSPICIOUS 等价物）
3. 年/月/时三未重复 → 结构提示；**未未不得标自刑**
4. 阴府 → 必须 UNKNOWN，不得静默通过
5. 未时流派分歧 → 必须 CONFLICT（结构化呈现，不得单方面认定）
6. 推荐等级不得为 PREFERRED
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app_zeri.case_runner import _run_one
from app_zeri.report import DISCLAIMER, render_markdown
from app_zeri.schemas import PersonSpec, SiteSpec, TaskSpec
from app_zeri.verifier import verify
from cases.schema import load_case

CST = ZoneInfo("Asia/Shanghai")
CASE_PATH = Path(__file__).resolve().parents[2] / "cases" / "graded" / "A" / "GS-2027-0711.yaml"


@pytest.fixture(scope="module")
def golden():
    return verify(
        dt=datetime(2027, 7, 11, 14, 0, tzinfo=CST),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
        person=PersonSpec(),
        schools=("public", "zhengwuxing"),
        allow_unverified=True,
    )


def test_pillars_exact(golden) -> None:
    assert golden.context["course"]["bazi"] == "丁未 丁未 辛卯 乙未"


def test_site_resolution(golden) -> None:
    site = golden.context["site"]
    assert site["mountain"] == "乾"
    assert site["facing"] == "巽"
    assert site["jian"] == "亥"
    assert site["shan_jia_zhi"] == "亥"


def test_sanhe_fushan_is_positive(golden) -> None:
    ids = {j.rule_id for res in golden.evaluation.per_school.values() for j in res.positives}
    assert "PUB-SANHEFU-001" in ids, f"三合扶山必须作为正向证据，实际正向：{ids}"
    groups = golden.context["facts"]["structure"]["sanhe_with_mountain"]
    assert groups and groups[0]["group"] == ["亥", "卯", "未"]


def test_three_wei_repeat_not_zixing(golden) -> None:
    st = golden.structure
    assert st.max_repeat == 3
    assert st.repeated == {"未": 3}
    assert st.has_self_punishment is False
    assert st.weiwei_is_self_punishment is False
    structural_ids = {j.rule_id for j in golden.evaluation.structural}
    veto_ids = {j.rule_id for res in golden.evaluation.per_school.values() for j in res.vetoes}
    assert "DEF-ZIXING-001" not in structural_ids, "未未不得被判为自刑"
    assert "PUB-ZIXING-001" not in veto_ids


def test_repeat_registered_as_structural(golden) -> None:
    """三未重复必须进「结构判定」节（定义级，确定），并计入 strong_avoid 影响 tier。"""
    ids = {j.rule_id for j in golden.evaluation.structural}
    assert "DEF-REPEAT-001" in ids, "三未重复应作为定义级结构判定登记"
    assert golden.evaluation.vectors["structural_count"] >= 1
    # 定义级一律 severity=记录，不得进 strong_avoid（ADR-0009）
    assert all(j.severity == "记录" for j in golden.evaluation.structural)
    assert golden.evaluation.vectors["structural_record_count"] == golden.evaluation.vectors["structural_count"]


def test_yinfu_must_be_unknown(golden) -> None:
    unknown_ids = {u["rule_id"] for u in golden.evaluation.unknowns}
    assert "PUB-YINFU-001" in unknown_ids, "阴府必须登记为 unknown，不得静默通过"
    # 且不得出现在任何派的否决/强忌里
    decided = {
        j.rule_id
        for res in golden.evaluation.per_school.values()
        for j in res.vetoes + res.cautions + res.positives
    }
    assert "PUB-YINFU-001" not in decided


def test_hour_divergence_is_conflict(golden) -> None:
    """未时流派分歧必须以 CONFLICT 结构化呈现。"""
    types = {c["type"] for c in golden.evaluation.conflicts}
    assert types & {"state_divergence", "verdict_conflict"}
    states = [c["states"] for c in golden.evaluation.conflicts if "states" in c]
    assert states, "冲突必须携带各派三态，便于并列呈现"
    assert any(len(set(s.values())) > 1 for s in states)


def test_tier_not_preferred(golden) -> None:
    assert golden.evaluation.tier != "PREFERRED"
    assert golden.evaluation.tier in ("NEEDS_REVIEW", "REJECTED")


def test_disagreement_computed(golden) -> None:
    assert 0.0 < golden.disagreement < 1.0


def test_report_contains_evidence_and_disclaimer(golden) -> None:
    md = render_markdown(golden)
    assert DISCLAIMER.split("；")[0][:20] in md
    assert "PUB-SANHEFU-001" in md
    assert "manifest" in md
    assert "未未不是自刑" in md
    assert "非吉凶概率" in md
    # 免责声明里出现「不承诺准确率」是合规要求；此处只禁止把指标表述为准确率
    for forbidden in ("灵验度评分", "吉凶概率为", "准确率为", "预测准确"):
        assert forbidden not in md


def test_case_file_runs_clean() -> None:
    """案例文件本身必须能跑通全部 expected 断言。"""
    case = load_case(CASE_PATH)
    outcome = _run_one(case)
    assert outcome.error is None, outcome.error
    assert outcome.passed, [c for c in outcome.checks if not c["ok"]]


def test_case_declares_assumptions() -> None:
    """A 级案例必须显式列出全部人为假设（禁止隐式假设）。"""
    case = load_case(CASE_PATH)
    assert case.grade == "A"
    assert len(case.params_assumed) >= 3
    assert case.source.snapshot_path
    assert (CASE_PATH.parents[2] / case.source.snapshot_path).exists()


def test_bazi_under_alternative_boundaries() -> None:
    """真太阳时/日界改变时，四柱可能变化 —— 必须能被敏感性分析检出。"""
    from core_time import CalendarConfig

    base = verify(
        dt=datetime(2027, 7, 11, 23, 30, tzinfo=CST),
        site=SiteSpec(azimuth_deg=320.0, lon=113.26),
        task=TaskSpec(kind="修造", strictness="strict"),
        cal=CalendarConfig(day_boundary="late"),
        allow_unverified=True,
    )
    early = verify(
        dt=datetime(2027, 7, 11, 23, 30, tzinfo=CST),
        site=SiteSpec(azimuth_deg=320.0, lon=113.26),
        task=TaskSpec(kind="修造", strictness="strict"),
        cal=CalendarConfig(day_boundary="early"),
        allow_unverified=True,
    )
    assert base.context["course"]["day"]["zhi"] != early.context["course"]["day"]["zhi"]
