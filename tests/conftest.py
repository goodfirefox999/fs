"""pytest 公共配置：注入各包 src 到 sys.path（无需 pip install 即可跑测试）。

同时提供金标准案例的基准 ctx 与深合并工具，供规则级测试向量复用。
"""

from __future__ import annotations

import copy
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
for pkg in ("core-time", "core-symbol", "core-rule", "core-eval", "app-zeri"):
    src = ROOT / pkg / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """递归合并：``overrides`` 的 dict 与 base 深合并，其余类型直接替换。"""
    out = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


@pytest.fixture(scope="session")
def tz() -> ZoneInfo:
    return ZoneInfo("Asia/Shanghai")


@pytest.fixture(scope="session")
def golden_dt(tz: ZoneInfo) -> datetime:
    """金标准案例时刻：2027-07-11 14:00（未时）。"""
    return datetime(2027, 7, 11, 14, 0, tzinfo=tz)


@pytest.fixture(scope="session")
def registry():
    from core_rule import default_registry

    return default_registry()


@pytest.fixture(scope="session")
def base_ctx(golden_dt):
    """金标准案例基准 ctx（乾山巽向兼亥巳，修造，strict，命主未提供）。"""
    from app_zeri.schemas import PersonSpec, SiteSpec, TaskSpec, build_context
    from core_time import CalendarConfig

    return build_context(
        course=__import__("app_zeri.schemas", fromlist=["CourseSpec"]).CourseSpec(dt=golden_dt),
        site=SiteSpec(azimuth_deg=320.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
        person=PersonSpec(),
        cal=CalendarConfig(),
    )


@pytest.fixture(scope="session")
def merged_ctx_factory(base_ctx):
    def _factory(overrides: dict[str, Any]) -> dict[str, Any]:
        return deep_merge(base_ctx, overrides)

    return _factory


@pytest.fixture
def tmp_path():
    """覆盖内置 ``tmp_path``：沙箱环境禁止在系统临时目录建目录，故改在仓库内建。

    测试结束后立即清理，不留残留。
    """
    import shutil
    import tempfile

    base = ROOT / "tests" / ".tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(prefix="zeri-", dir=base))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
