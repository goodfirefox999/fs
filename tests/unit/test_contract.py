"""契约测试：输出必须通过 JSON Schema；报告必须含免责声明与证据链。"""

from __future__ import annotations

import json
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app_zeri.generator import generate
from app_zeri.report import DISCLAIMER, render_generation_markdown, render_json, render_markdown
from app_zeri.schemas import EVALUATION_SCHEMA, SiteSpec, TaskSpec, validate_schema
from app_zeri.verifier import verify

CST = ZoneInfo("Asia/Shanghai")


@pytest.fixture(scope="module")
def single():
    return verify(
        dt=datetime(2027, 7, 11, 14, 0, tzinfo=CST),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", strictness="strict"),
        allow_unverified=True,
    )


def test_evaluation_matches_schema(single) -> None:
    payload = single.evaluation.to_dict()
    errors = validate_schema(payload, EVALUATION_SCHEMA)
    assert errors == [], errors


def test_json_serializable(single) -> None:
    text = render_json(single)
    data = json.loads(text)
    assert data["evaluation"]["state"] in ("可用", "存疑", "不可用")


def test_schema_rejects_bad_state() -> None:
    bad = {
        "candidate": "x",
        "state": "大吉",
        "tier": "PREFERRED",
        "vectors": {"hard_fail_count": 0, "strong_avoid_count": 0,
                    "conflict_count": 0, "unknown_count": 0, "positive_count": 0},
        "per_school": {},
        "conflicts": [],
        "unknowns": [],
        "manifest": {"input_hash": "x", "rule_lib_version": "y", "engine_version": "z"},
    }
    errors = validate_schema(bad, EVALUATION_SCHEMA)
    assert any("不在枚举" in e for e in errors)


def test_schema_rejects_missing_required() -> None:
    errors = validate_schema({"candidate": "x"}, EVALUATION_SCHEMA)
    assert any("缺少必填字段" in e for e in errors)


def test_schema_rejects_extra_field(single) -> None:
    payload = single.evaluation.to_dict()
    payload["total_score"] = 99
    errors = validate_schema(payload, EVALUATION_SCHEMA)
    assert any("未声明字段" in e for e in errors), "输出不得夹带单一总分字段"


def test_markdown_has_disclaimer(single) -> None:
    md = render_markdown(single)
    assert "不构成工程安全" in md
    assert "不承诺准确率" in md


def test_markdown_has_manifest(single) -> None:
    md = render_markdown(single)
    assert "rule_lib_version" in md
    assert "input_hash" in md
    assert "engine_version" in md


def test_markdown_echoes_calendar_params(single) -> None:
    md = render_markdown(single)
    assert "day_boundary" in md
    assert "use_true_solar_time" in md


def test_generation_report(single) -> None:
    result = generate(
        start=date(2027, 7, 1),
        end=date(2027, 7, 7),
        site=SiteSpec(azimuth_deg=320.0, lon=113.26),
        task=TaskSpec(kind="修造", strictness="strict"),
        allow_unverified=True,
        top=5,
    )
    md = render_generation_markdown(result)
    assert "不构成工程安全" in md
    assert "分层排序" in md
    assert "非吉凶概率" in md
    assert result.total_candidates == 7 * 12


def test_generation_json_shape() -> None:
    result = generate(
        start=date(2027, 7, 1),
        end=date(2027, 7, 3),
        site=SiteSpec(azimuth_deg=320.0, lon=113.26),
        task=TaskSpec(kind="修造"),
        allow_unverified=True,
        top=3,
    )
    data = json.loads(render_json(result))
    assert "tier_histogram" in data
    assert "candidates" in data
    assert len(data["candidates"]) == 3
    assert "score" not in data


def test_disclaimer_text_is_stable() -> None:
    """免责声明是合规红线，改动必须显式审阅。"""
    assert "传统文化参考" in DISCLAIMER
    assert "不承诺准确率" in DISCLAIMER
    assert "化解" in DISCLAIMER
