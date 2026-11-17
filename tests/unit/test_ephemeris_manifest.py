"""Layer 5：星历 manifest 全字段透传 + 降级边界门。

验收口径（用户 Layer 5）：
- ``manifest.ephemeris`` 必须输出 backend/precision/ephemeris_file/valid_range/
  delta_t_s/fallback_reason；
- VSOP87 回退 → ``precision=degraded`` 且 ``fallback_reason`` 可查；
- DE440s 有效范围外必须显式报错，不得静默外推；
- 降级后端下距「节」不足 15 s 的候选，断言自动降为「证据不足」并阻塞
  ``publishable``（已签规则也不得投票）。
"""

from __future__ import annotations

import sys
from dataclasses import replace as dc_replace
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from app_zeri import schemas as app_schemas
from app_zeri.report import ephemeris_notice
from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
from core_eval import STATE_BLOCKED, EvalConfig, evaluate
from core_eval.engine import (
    BLOCK_EVIDENCE_INSUFFICIENT,
    PARTICIPATION_EVIDENCE_INSUFFICIENT,
    UNKNOWN_EVIDENCE_INSUFFICIENT,
)
from core_rule.loader import RuleSet
from core_rule.models import AppliesTo, Rule
from core_rule.policy import RequiredRuleSet
from core_rule.provenance import Citation, stable_hash
from core_rule.registry import RuleRegistry
from core_time import CalendarConfig
from core_time import ephemeris as ephemeris_mod
from core_time import jieqi as jieqi_mod
from core_time.ephemeris import (
    DE440S_VALID_RANGE_UTC,
    backend_audit,
    ensure_backend_range,
)
from core_time.jieqi import (
    JIE_BOUNDARY_WINDOW_S,
    SolarTerm,
    jie_boundary_risk,
)

CST = ZoneInfo("Asia/Shanghai")
MANIFEST_KEYS = {
    "backend",
    "precision",
    "ephemeris_file",
    "valid_range",
    "delta_t_s",
    "fallback_reason",
}


# --------------------------------------------------------------------------- #
# backend_audit：字段与降级原因
# --------------------------------------------------------------------------- #
class TestBackendAudit:
    def test_skyfield_fields_are_complete(self, monkeypatch) -> None:
        monkeypatch.setattr(ephemeris_mod, "resolved_backend", lambda: "skyfield")
        audit = backend_audit(datetime(2026, 6, 1, tzinfo=CST))
        assert set(audit) >= MANIFEST_KEYS, audit
        assert audit["backend"] == "skyfield"
        assert audit["precision"] == "high"
        assert audit["ephemeris_file"], "高精度路径必须回显星历文件"
        assert audit["valid_range"] == [
            DE440S_VALID_RANGE_UTC[0].date().isoformat(),
            DE440S_VALID_RANGE_UTC[1].date().isoformat(),
        ]
        assert audit["fallback_reason"] is None
        assert isinstance(audit["delta_t_s"], float)

    def test_vsop87_fallback_is_degraded_with_reason(self, monkeypatch) -> None:
        monkeypatch.setattr(ephemeris_mod, "resolved_backend", lambda: "vsop87")
        monkeypatch.setenv("ZERI_EPHEMERIS_BACKEND", "vsop87")
        audit = backend_audit(datetime(2026, 6, 1, tzinfo=CST))
        assert set(audit) >= MANIFEST_KEYS, audit
        assert audit["backend"] == "vsop87"
        assert audit["precision"] == "degraded"
        assert audit["ephemeris_file"] is None
        assert audit["valid_range"] == ["-2000", "6000"]
        assert "vsop87" in (audit["fallback_reason"] or "")

    def test_out_of_de440s_range_raises(self, monkeypatch) -> None:
        monkeypatch.setattr(ephemeris_mod, "resolved_backend", lambda: "skyfield")
        with pytest.raises(ValueError, match="DE440s"):
            backend_audit(datetime(1800, 1, 1, tzinfo=CST))
        with pytest.raises(ValueError, match="带时区"):
            ensure_backend_range(datetime(2026, 1, 1), backend="skyfield")

    def test_ensure_backend_range_skips_vsop87(self) -> None:
        # 降级后端精度已标 degraded，不做硬性范围拦截（越界是显式口径而非静默外推）
        assert ensure_backend_range(datetime(1800, 1, 1, tzinfo=CST), backend="vsop87") is None


# --------------------------------------------------------------------------- #
# resolved_backend / _fallback_reason：每条回退路径都可查
# --------------------------------------------------------------------------- #
class TestBackendResolution:
    @staticmethod
    def _raw():
        # 绕过 lru_cache，逐条验证环境分支
        return ephemeris_mod.resolved_backend.__wrapped__()

    def test_invalid_env_rejected(self, monkeypatch) -> None:
        monkeypatch.setenv("ZERI_EPHEMERIS_BACKEND", "bogus")
        with pytest.raises(ValueError, match="非法"):
            self._raw()

    def test_explicit_vsop87(self, monkeypatch) -> None:
        monkeypatch.setenv("ZERI_EPHEMERIS_BACKEND", "vsop87")
        assert self._raw() == "vsop87"

    def test_auto_uses_skyfield_when_available(self, monkeypatch) -> None:
        from core_time import skyfield_ephemeris

        monkeypatch.setenv("ZERI_EPHEMERIS_BACKEND", "auto")
        monkeypatch.setattr(skyfield_ephemeris, "available", lambda: True)
        assert self._raw() == "skyfield"

    def test_auto_falls_back_when_unavailable(self, monkeypatch) -> None:
        from core_time import skyfield_ephemeris

        monkeypatch.setenv("ZERI_EPHEMERIS_BACKEND", "auto")
        monkeypatch.setattr(skyfield_ephemeris, "available", lambda: False)
        assert self._raw() == "vsop87"

    def test_forced_skyfield_unavailable_raises(self, monkeypatch) -> None:
        from core_time import skyfield_ephemeris

        monkeypatch.setenv("ZERI_EPHEMERIS_BACKEND", "skyfield")
        monkeypatch.setattr(skyfield_ephemeris, "available", lambda: False)
        with pytest.raises(RuntimeError, match="skyfield"):
            self._raw()

    def test_fallback_reason_explicit(self, monkeypatch) -> None:
        monkeypatch.setenv("ZERI_EPHEMERIS_BACKEND", "vsop87")
        assert ephemeris_mod._fallback_reason() == "explicit: ZERI_EPHEMERIS_BACKEND=vsop87"

    def test_fallback_reason_skyfield_not_installed(self, monkeypatch) -> None:
        monkeypatch.delenv("ZERI_EPHEMERIS_BACKEND", raising=False)
        monkeypatch.setitem(sys.modules, "skyfield", None)
        assert ephemeris_mod._fallback_reason() == "skyfield_not_installed"

    def test_fallback_reason_file_missing(self, monkeypatch, tmp_path) -> None:
        monkeypatch.delenv("ZERI_EPHEMERIS_BACKEND", raising=False)
        monkeypatch.setenv("ZERI_EPHEMERIS_PATH", str(tmp_path / "missing.bsp"))
        reason = ephemeris_mod._fallback_reason() or ""
        assert reason.startswith("ephemeris_file_missing: ")

    def test_fallback_reason_unknown_when_silently_degraded(self, monkeypatch, tmp_path) -> None:
        monkeypatch.delenv("ZERI_EPHEMERIS_BACKEND", raising=False)
        fake = tmp_path / "de440s.bsp"
        fake.write_bytes(b"placeholder")
        monkeypatch.setenv("ZERI_EPHEMERIS_PATH", str(fake))
        assert ephemeris_mod._fallback_reason() == "unknown"

    def test_audit_records_auto_missing_file_reason(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(ephemeris_mod, "resolved_backend", lambda: "vsop87")
        monkeypatch.delenv("ZERI_EPHEMERIS_BACKEND", raising=False)
        monkeypatch.setenv("ZERI_EPHEMERIS_PATH", str(tmp_path / "missing.bsp"))
        audit = backend_audit(datetime(2026, 6, 1, tzinfo=CST))
        assert audit["precision"] == "degraded"
        assert (audit["fallback_reason"] or "").startswith("ephemeris_file_missing: ")

    def test_solar_longitude_uses_skyfield_backend(self, monkeypatch) -> None:
        from core_time import skyfield_ephemeris

        monkeypatch.setattr(ephemeris_mod, "resolved_backend", lambda: "skyfield")
        monkeypatch.setattr(skyfield_ephemeris, "solar_longitude_deg", lambda jd_tt: 315.25)
        assert ephemeris_mod.solar_longitude_deg(0.0) == 315.25


# --------------------------------------------------------------------------- #
# jie_boundary_risk：只在降级后端 + 窗口内触发
# --------------------------------------------------------------------------- #
def _fake_term(moment: datetime) -> SolarTerm:
    return SolarTerm(
        name="立春",
        longitude=315,
        kind="jie",
        jd_ut=0.0,
        utc=moment.astimezone(ZoneInfo("UTC")),
        local=moment,
    )


class TestJieBoundaryRisk:
    def test_degraded_backend_inside_window_requires_precision(self, monkeypatch) -> None:
        boundary = datetime(2026, 2, 4, 4, 1, 51, tzinfo=CST)
        monkeypatch.setattr(jieqi_mod, "terms_of_year", lambda year, tz_name="Asia/Shanghai": (_fake_term(boundary),))
        inside = jie_boundary_risk(boundary + timedelta(seconds=5), "Asia/Shanghai", "vsop87")
        assert inside["second_precision_required"] is True
        assert inside["nearest_jie"] == "立春"
        assert inside["distance_to_jie_s"] == 5.0
        assert "月柱可能翻转" in (inside["second_precision_reason"] or "")

        outside = jie_boundary_risk(
            boundary + timedelta(seconds=JIE_BOUNDARY_WINDOW_S + 1),
            "Asia/Shanghai",
            "vsop87",
        )
        assert outside["second_precision_required"] is False
        assert outside["second_precision_reason"] is None

    def test_high_precision_backend_never_requires_precision(self, monkeypatch) -> None:
        boundary = datetime(2026, 2, 4, 4, 1, 51, tzinfo=CST)
        monkeypatch.setattr(jieqi_mod, "terms_of_year", lambda year, tz_name="Asia/Shanghai": (_fake_term(boundary),))
        risk = jie_boundary_risk(boundary, "Asia/Shanghai", "skyfield")
        assert risk["second_precision_required"] is False
        assert risk["nearest_jie"] is None

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValueError):
            jie_boundary_risk(datetime(2026, 2, 4, 4, 0))


# --------------------------------------------------------------------------- #
# build_context：审计字段与边界字段合并进 _meta.ephemeris
# --------------------------------------------------------------------------- #
def test_build_context_ephemeris_is_full_audit_and_boundary(monkeypatch) -> None:
    audit = {
        "backend": "vsop87",
        "precision": "degraded",
        "ephemeris_file": None,
        "valid_range": ["-2000", "6000"],
        "delta_t_s": 69.1,
        "fallback_reason": "explicit: ZERI_EPHEMERIS_BACKEND=vsop87",
    }
    boundary = {
        "second_precision_required": True,
        "second_precision_reason": "测试窗口",
        "nearest_jie": "立春",
        "nearest_jie_at": "2026-02-04T04:01:51+08:00",
        "distance_to_jie_s": 3.0,
        "boundary_window_s": 15.0,
    }
    monkeypatch.setattr(app_schemas, "backend_audit", lambda dt: dict(audit))
    monkeypatch.setattr(app_schemas, "jie_boundary_risk", lambda dt, tz, backend: dict(boundary))
    ctx = build_context(
        CourseSpec(dt=datetime(2026, 2, 4, 4, 1, 54, tzinfo=CST)),
        SiteSpec(azimuth_deg=320.0),
        TaskSpec(kind="修造"),
    )
    ephem = ctx["_meta"]["ephemeris"]
    assert set(ephem) >= MANIFEST_KEYS
    assert ephem["backend"] == "vsop87"
    assert ephem["second_precision_required"] is True
    assert ephem["nearest_jie"] == "立春"
    assert ephem["distance_to_jie_s"] == 3.0


# --------------------------------------------------------------------------- #
# 报告：降级边界必须在结论区可见（不能只藏在 manifest JSON 里）
# --------------------------------------------------------------------------- #
def test_ephemeris_notice_only_when_boundary_required() -> None:
    class _Fake:
        manifest = {"ephemeris": {"second_precision_required": False}}

    assert ephemeris_notice(_Fake()) == []

    _Fake.manifest = {
        "ephemeris": {
            "second_precision_required": True,
            "backend": "vsop87",
            "nearest_jie": "小寒",
            "distance_to_jie_s": 0.1,
        }
    }
    lines = ephemeris_notice(_Fake())
    text = lines[-1]
    assert "小寒" in text
    assert "0.1" in text
    assert "不得作为发布依据" in text


# --------------------------------------------------------------------------- #
# 引擎：降级边界门把已签命中降为证据不足并阻塞 publishable
# --------------------------------------------------------------------------- #
def _ephem_rule(rule_id: str = "TEST-EPHEM-001", *, hit: bool = True) -> Rule:
    """合成已考证规则（仅测试）：坐山乾 → 推荐。"""
    condition = {"fact": "site.mountain", "op": "eq", "value": "乾" if hit else "子"}
    citation = Citation(
        source="测试专用（非古籍，仅用于验证星历闸门）",
        kind="classic",
        quote="测试用原文占位",
        verified_by="pytest",
    )
    return Rule(
        rule_id=rule_id,
        version=1,
        school="public",
        category="测试专用星历门",
        status="已考证",
        hard_veto=False,
        severity="推荐",
        target="mountain",
        applies_to=AppliesTo(),
        condition=condition,
        citation=citation,
        explanation="合成规则：坐山为乾时判推荐（仅测试）",
        tests=("TEST-HIT",),
        raw={
            "rule_id": rule_id,
            "version": 1,
            "school": "public",
            "category": "测试专用星历门",
            "status": "已考证",
            "hard_veto": False,
            "severity": "推荐",
            "target": "mountain",
            "condition": condition,
            "citation": {"source": citation.source, "kind": citation.kind},
        },
    )


def _registry_with(registry: RuleRegistry, rule: Rule) -> RuleRegistry:
    rules = registry.ruleset.rules + (rule,)
    by_id = {**registry.ruleset.by_id, rule.rule_id: rule}
    by_school: dict[str, list[Rule]] = {}
    for r in rules:
        by_school.setdefault(r.school, []).append(r)
    ruleset = RuleSet(
        rules=rules,
        by_id=by_id,
        by_school={k: tuple(v) for k, v in by_school.items()},
        version="rl-" + stable_hash([(r.rule_id, r.version) for r in rules]),
    )
    required = RequiredRuleSet(
        core=(rule.rule_id,),
        criteria=registry.required_rules.criteria,
    )
    return dc_replace(registry, ruleset=ruleset, required_rules=required)


@pytest.fixture(scope="module")
def ephem_ctx():
    return build_context(
        course=CourseSpec(dt=datetime(2027, 7, 11, 14, 0, tzinfo=CST)),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="normal"),
        person=PersonSpec(),
        cal=CalendarConfig(),
    )


def _flag_boundary(ctx: dict, required: bool) -> dict:
    out = {**ctx, "_meta": {**ctx["_meta"], "ephemeris": dict(ctx["_meta"]["ephemeris"])}}
    out["_meta"]["ephemeris"]["second_precision_required"] = required
    out["_meta"]["ephemeris"]["second_precision_reason"] = (
        "星历降级（vsop87，与 DE440s 相差约 7 s），距「立春」仅 3.0 s，月柱可能翻转" if required else None
    )
    return out


class TestEphemerisGateInEngine:
    def test_high_precision_keeps_verified_hit_voting(self, ephem_ctx, registry) -> None:
        reg = _registry_with(registry, _ephem_rule())
        ev = evaluate(
            _flag_boundary(ephem_ctx, False),
            reg,
            EvalConfig(task_kind="修造", strictness="normal"),
        )
        hits = [j for res in ev.per_school.values() for j in res.positives if j.rule_id == "TEST-EPHEM-001"]
        assert hits and hits[0].participation == "判定"
        assert [b for b in ev.required_blockers if b["rule_id"] == "TEST-EPHEM-001"] == []
        assert ev.publishable is True

    def test_degraded_boundary_downgrades_signed_hit(self, ephem_ctx, registry) -> None:
        reg = _registry_with(registry, _ephem_rule())
        ev = evaluate(
            _flag_boundary(ephem_ctx, True),
            reg,
            EvalConfig(task_kind="修造", strictness="normal"),
        )
        assert not [j for res in ev.per_school.values() for j in res.positives if j.rule_id == "TEST-EPHEM-001"], (
            "降级边界窗口内的命中不得进入正票桶"
        )

        unknown = [u for u in ev.unknowns if u["rule_id"] == "TEST-EPHEM-001"]
        assert len(unknown) == 1
        assert unknown[0]["reason"] == PARTICIPATION_EVIDENCE_INSUFFICIENT
        assert unknown[0]["unknown_reason"] == UNKNOWN_EVIDENCE_INSUFFICIENT
        assert any("星历精度闸门" in w for w in unknown[0]["warnings"])

        blockers = [b for b in ev.required_blockers if b["rule_id"] == "TEST-EPHEM-001"]
        assert len(blockers) == 1
        assert blockers[0]["kind"] == BLOCK_EVIDENCE_INSUFFICIENT
        assert "Skyfield" in blockers[0]["detail"]
        assert ev.state != STATE_BLOCKED, "未判定不得冒充确定否决"
        assert ev.publishable is False, "证据不足必须阻塞发布"

    def test_degraded_boundary_blocks_signed_required_miss(self, ephem_ctx, registry) -> None:
        """已签规则本轮未命中，边界窗口内也不得算「已判定通过」。"""
        reg = _registry_with(registry, _ephem_rule(hit=False))

        high = evaluate(
            _flag_boundary(ephem_ctx, False),
            reg,
            EvalConfig(task_kind="修造", strictness="normal"),
        )
        assert [b for b in high.required_blockers if b["rule_id"] == "TEST-EPHEM-001"] == []
        assert high.publishable is True

        degraded = evaluate(
            _flag_boundary(ephem_ctx, True),
            reg,
            EvalConfig(task_kind="修造", strictness="normal"),
        )
        blockers = [b for b in degraded.required_blockers if b["rule_id"] == "TEST-EPHEM-001"]
        assert len(blockers) == 1
        assert blockers[0]["kind"] == BLOCK_EVIDENCE_INSUFFICIENT
        assert blockers[0]["reason"] == "未判定（ephemeris_precision）"
        assert degraded.publishable is False
