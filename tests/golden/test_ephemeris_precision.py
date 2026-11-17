"""节气精度对拍：Skyfield/DE440s vs Swiss Ephemeris 官方数据。

判据（用户口径）：任取一个节气交接时刻，与 Swiss Ephemeris 官方输出比对，
差值必须 < 1 秒；否则不得进入生产路径。

参考表 ``data/solar_terms_swisseph.json`` 由 Swiss Ephemeris 2.10.03 +
官方 ``sepl_18.se1`` 生成（生成方法见文件内 ``method`` 字段）。Swiss 与
Skyfield 是两套独立实现/星历，能同时对上才说明不是单一实现的自我循环。

分层断言
--------
- **TT 对拍**：2000-2100 全部 24×9 个节气，容差 0.1 s。TT 不含 ΔT 预测，
  因此可以直接检验星历与求根算法。
- **UTC 对拍**：仅 2000-2030，容差 1.0 s。2050/2100 的 UTC 差异来自 ΔT
  预测模型分歧（实测最大 24.4 s），不是星历误差，故只断言 TT。
- **后备路径标注**：VSOP87 必须显式 ``backend="vsop87"``，且 2026 立春与
  Skyfield 相差 > 1 s —— 它只能作为离线降级，不得冒充生产精度。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from core_time import equation_of_time, resolved_backend, terms_of_year

REFERENCE = Path(__file__).parent / "data" / "solar_terms_swisseph.json"
REF = json.loads(REFERENCE.read_text(encoding="utf-8"))
YEARS = sorted(int(y) for y in REF["years"])
UTC_KNOWN_YEARS = {y for y in YEARS if y <= 2030}

pytestmark = pytest.mark.skipif(
    resolved_backend() != "skyfield",
    reason="需要 Skyfield/DE440s 高精度后端（安装 high-precision extra 并提供 de440s.bsp）",
)


def _terms(year: int, backend: str | None = None):
    return {t.name: t for t in terms_of_year(year, "Asia/Shanghai", backend=backend)}


@pytest.mark.parametrize("year", YEARS)
def test_tt_within_tenth_of_second(year: int) -> None:
    """TT 时刻必须与 Swiss Ephemeris 官方数据相差 < 0.1 秒。"""
    terms = _terms(year)
    assert len(terms) == 24
    for name, ref in REF["years"][str(year)].items():
        term = terms[name]
        assert term.jd_tt is not None
        delta = abs(term.jd_tt - ref["jd_tt"]) * 86400.0
        assert delta < 0.1, f"{year}{name}: TT 偏差 {delta:.4f}s（容差 0.1s）"


@pytest.mark.parametrize("year", sorted(UTC_KNOWN_YEARS))
def test_utc_within_one_second(year: int) -> None:
    """UTC 时刻必须与 Swiss 官方输出相差 < 1 秒（仅限 ΔT 已知年份）。"""
    terms = _terms(year)
    for name, ref in REF["years"][str(year)].items():
        ref_utc = datetime.fromisoformat(ref["utc"].replace("Z", "+00:00"))
        delta = abs((terms[name].utc - ref_utc).total_seconds())
        assert delta < 1.0, f"{year}{name}: UTC 偏差 {delta:.4f}s（容差 1.0s）"


def test_equation_of_time_within_one_second() -> None:
    """均时差必须与 Swiss ``swe.time_equ`` 相差 < 1 秒（经度校正另算）。"""
    samples = REF["equation_of_time_minutes"]["samples"]
    assert len(samples) == 24
    for iso, expected_min in samples.items():
        at = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta_sec = abs(equation_of_time(at) - expected_min) * 60.0
        assert delta_sec < 1.0, f"{iso}: 均时差偏差 {delta_sec:.3f}s"


def test_vsop87_fallback_is_labeled_and_degraded() -> None:
    """VSOP87 后备必须显式标注，且其最大偏差远大于 1 秒。"""
    sky = _terms(2026, backend="skyfield")
    vsop = _terms(2026, backend="vsop87")
    assert all(t.backend == "skyfield" for t in sky.values())
    assert all(t.backend == "vsop87" for t in vsop.values())
    max_delta = max(
        abs((sky[name].utc - vsop[name].utc).total_seconds()) for name in sky
    )
    assert max_delta > 1.0, "VSOP87 后备与 DE440s 的最大差距应 >1s；若已收窄到 1s 内请更新结论"
    assert max_delta < 30.0, f"VSOP87 后备最大偏差 {max_delta:.2f}s，超出预期，需排查"


def test_reference_metadata_is_pinned() -> None:
    """参考表必须记录来源与星历文件哈希，避免“匿名真值”。"""
    assert "Swiss Ephemeris" in REF["source"]
    assert len(REF["ephemeris_file_sha256"]) == 64
    assert REF["flags"].startswith("SEFLG_SWIEPH")
    assert set(REF["years"]) == {str(y) for y in YEARS}
