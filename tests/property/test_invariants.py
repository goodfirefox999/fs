"""属性测试（hypothesis）：历法不变量、求值器纯函数性、幂等性。

对应 docs/DEVELOPMENT.md 第 6.7 节"不变量（属性测试必测）"：
六十甲子循环闭合、节气严格单调、节气区间无缝无重叠、方位角归一、真太阳时连续、同输入幂等。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from hypothesis import given, settings
from hypothesis import strategies as st

from core_rule.dsl import eval_condition
from core_symbol import GANZHI60, MOUNTAINS_24, mountain_of_azimuth, normalize_azimuth
from core_time import (
    compute_four_pillars,
    jd_tt_from_jd_ut,
    jd_ut_from_jd_tt,
    julian_day_from_datetime,
    terms_of_year,
    true_solar_time,
)
from core_time.calendar import GAN, ZHI, ganzhi_index

CST = ZoneInfo("Asia/Shanghai")


@settings(max_examples=200, deadline=None)
@given(st.integers(min_value=-3600, max_value=3600))
def test_sexagenary_cycle_closed(i: int) -> None:
    gz = GANZHI60[i % 60]
    assert ganzhi_index(gz[0], gz[1]) == i % 60
    assert GAN.index(gz[0]) == i % 10
    assert ZHI.index(gz[1]) == i % 12
    # 周期 60
    assert GANZHI60[(i + 60) % 60] == GANZHI60[i % 60]


@settings(max_examples=60, deadline=None)
@given(st.integers(min_value=1900, max_value=2100))
def test_solar_terms_strictly_monotonic(year: int) -> None:
    terms = terms_of_year(year, "Asia/Shanghai")
    assert len(terms) == 24
    for a, b in zip(terms, terms[1:]):
        assert a.jd_ut < b.jd_ut
    # 无缝：相邻间隔在 (14, 16.5) 天
    for a, b in zip(terms, terms[1:]):
        assert 14.0 < (b.jd_ut - a.jd_ut) < 16.5


@settings(max_examples=60, deadline=None)
@given(st.integers(min_value=1900, max_value=2100))
def test_terms_do_not_overlap_between_years(year: int) -> None:
    cur = terms_of_year(year, "Asia/Shanghai")
    nxt = terms_of_year(year + 1, "Asia/Shanghai")
    assert cur[-1].jd_ut < nxt[0].jd_ut


@settings(max_examples=300, deadline=None)
@given(st.floats(min_value=-1000, max_value=1000, allow_nan=False, allow_infinity=False))
def test_azimuth_normalized(az: float) -> None:
    norm = normalize_azimuth(az)
    assert 0.0 <= norm < 360.0
    m = mountain_of_azimuth(az)
    assert m.name in MOUNTAINS_24
    assert -7.5 <= m.offset_deg <= 7.5


@settings(max_examples=200, deadline=None)
@given(
    st.floats(min_value=-170.0, max_value=170.0, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0.0, max_value=300.0, allow_nan=False, allow_infinity=False),
)
def test_true_solar_time_continuous(lon: float, hours: float) -> None:
    at = datetime(2027, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hours)
    t1 = true_solar_time(at, lon)
    t2 = true_solar_time(at + timedelta(seconds=1), lon)
    assert 0.9 < (t2 - t1).total_seconds() < 1.1


@settings(max_examples=200, deadline=None)
@given(st.integers(min_value=1950, max_value=2050), st.integers(min_value=0, max_value=364))
def test_four_pillars_idempotent(year: int, day_offset: int) -> None:
    """同输入必同输出（确定性）。"""
    dt = datetime(year, 1, 1, 12, 0, tzinfo=CST) + timedelta(days=day_offset)
    a = compute_four_pillars(dt)
    b = compute_four_pillars(dt)
    assert a.bazi == b.bazi
    assert a.to_dict() == b.to_dict()


@settings(max_examples=100, deadline=None)
@given(st.integers(min_value=1950, max_value=2050), st.integers(min_value=0, max_value=364))
def test_pillar_ganzhi_index_consistent(year: int, day_offset: int) -> None:
    dt = datetime(year, 1, 1, 12, 0, tzinfo=CST) + timedelta(days=day_offset)
    p = compute_four_pillars(dt)
    for pillar in p.pillars:
        assert GANZHI60[pillar.index] == pillar.name
        assert pillar.gan == GAN[pillar.index % 10]
        assert pillar.zhi == ZHI[pillar.index % 12]


@settings(max_examples=100, deadline=None)
@given(st.integers(min_value=1900, max_value=2100))
def test_jd_roundtrip(year: int) -> None:
    jd_tt = julian_day_from_datetime(datetime(year, 6, 15, 12, tzinfo=timezone.utc))
    jd_ut = jd_ut_from_jd_tt(jd_tt)
    assert abs(jd_ut_from_jd_tt(jd_tt) - jd_ut) < 1e-6
    assert abs(jd_tt_from_jd_ut(jd_ut) - jd_tt) < 1e-6


@settings(max_examples=100, deadline=None)
@given(st.integers(min_value=0, max_value=59), st.integers(min_value=0, max_value=59))
def test_evaluator_is_pure(a: int, b: int) -> None:
    """求值器是纯函数：不改 ctx、结果稳定。"""
    import copy

    ctx = {
        "course": {"day": {"zhi": GANZHI60[a][1]}},
        "site": {"mountain": "乾", "shan_jia_zhi": ZHI[a % 12]},
        "facts": {"structure": {"max_repeat": a % 5, "zixing_pairs": []}},
    }
    snapshot = copy.deepcopy(ctx)
    cond = {
        "all": [
            {"fact": "facts.structure.max_repeat", "op": "gte", "value": 1},
            {"fact": "site.shan_jia_zhi", "op": "same_group",
             "value": {"path": "course.day.zhi", "kind": "sanhe"}},
        ]
    }
    r1 = eval_condition(cond, ctx)
    r2 = eval_condition(cond, ctx)
    assert r1.value is r2.value
    assert ctx == snapshot, "求值器不得修改 ctx"


@settings(max_examples=100, deadline=None)
@given(st.text(min_size=1, max_size=8))
def test_illegal_root_always_rejected(path: str) -> None:
    from core_rule.dsl import validate_condition
    from core_rule.errors import DSLValidationError

    root = path.split(".")[0]
    if root in {"course", "site", "person", "task", "time", "facts"}:
        return
    try:
        validate_condition({"fact": path, "op": "exists"})
    except DSLValidationError:
        return
    raise AssertionError(f"非法命名空间未被拒绝: {path}")
