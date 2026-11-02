"""事实缓存回归：同一日不同时辰不得共用事实（2026-11-02 P0）。

背景
----
``build_context`` 曾把「日级事实」整包缓存，理由是"derive_facts 无时辰参数"。
该前提是错的：``derive_facts`` 收到四柱（含时柱），``structure``/``xunkong.hits``/
``tongguan``/``sanhe_ju``/``doushou`` 都随时支变化。整包按日缓存 → 同日子时的事实
被其余 11 个时辰复用，金标准案例（乙未时）会凭空多出「未子相害」「卯子相刑」。

本文件锁三件事：
1. 同日子时/未时结构不同（缓存不串味）；
2. 缓存命中不影响结果（第二次调用与第一次一致）；
3. 叠加层只改时变键，日不变键保持同一对象（证明缓存确实在复用，不是整包重算）。
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app_zeri.schemas import CourseSpec, SiteSpec, TaskSpec, build_context

CST = ZoneInfo("Asia/Shanghai")
SITE = SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26)
TASK = TaskSpec(kind="修造", strictness="strict")


def _ctx(hour: int):
    return build_context(CourseSpec(dt=datetime(2027, 7, 11, hour, 0, tzinfo=CST)), SITE, TASK)


class TestCrossHourIsolation:
    def test_zi_and_wei_hours_differ(self) -> None:
        zi = _ctx(0)
        wei = _ctx(14)
        assert zi["course"]["bazi"].endswith("戊子")
        assert wei["course"]["bazi"].endswith("乙未")

        assert zi["facts"]["structure"]["max_repeat"] == 2
        assert wei["facts"]["structure"]["max_repeat"] == 3

        # 子时：未子相害 + 卯子相刑；未时：三未，无此二项
        assert zi["facts"]["structure"]["hai_pairs"], "子时应见未子相害"
        assert zi["facts"]["structure"]["xing_pairs"], "子时应见卯子相刑"
        assert wei["facts"]["structure"]["hai_pairs"] == []
        assert wei["facts"]["structure"]["xing_pairs"] == []

    def test_repeat_call_is_stable(self) -> None:
        first = _ctx(14)["facts"]["structure"]
        _ctx(0)  # 先污染一次日级缓存
        second = _ctx(14)["facts"]["structure"]
        assert first == second

    def test_hour_dependent_sections_are_recomputed(self) -> None:
        zi = _ctx(0)["facts"]
        wei = _ctx(14)["facts"]
        for key in ("structure", "xunkong", "tongguan", "sanhe_ju", "doushou"):
            assert zi[key] != wei[key], f"{key} 应随时辰变化"
        assert zi["doushou"]["stems"][3]["gan"] == "戊"
        assert wei["doushou"]["stems"][3]["gan"] == "乙"

    def test_day_level_sections_are_shared(self) -> None:
        """日不变部分必须复用同一对象，否则日级缓存形同虚设（性能回归）。"""
        zi = _ctx(0)["facts"]
        wei = _ctx(14)["facts"]
        for key in ("sansha", "taisui", "suipo", "yuepo", "xuankong", "tianxing", "donggong"):
            assert zi[key] is wei[key], f"{key} 应复用日级缓存对象"

    def test_yinfu_carries_current_hour_gans(self) -> None:
        """阴府候选虽不推断，但回显的四柱天干必须是本时辰的，不能是缓存里首个子时的。"""
        zi = _ctx(0)["facts"]["yinfu"]["candidates"]["gans"]
        wei = _ctx(14)["facts"]["yinfu"]["candidates"]["gans"]
        assert zi[3] == "戊"
        assert wei[3] == "乙"
        # 日级部分不得被叠加层写坏
        assert _ctx(14)["facts"]["yinfu"]["candidates"]["status"] == "有争议"
