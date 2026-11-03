"""``tests/conftest.py`` 的「性能未验证」提示锁（评审十回路）。

事故形态：``make cov`` 会在无插桩进程里补跑性能冒烟，但开发者习惯直接
``pytest --cov``——此时冒烟被 skip，且**没有任何独立进程补跑**，本地性能门禁
静默消失，看到的是「全绿」。conftest 的 terminal summary 必须把这件事喊出来。

这里直接调用钩子传入假 reporter/config，不启子进程：
一是快，二是沙箱对子进程环境有保护策略，直接单测语义更稳。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("zeri_conftest", _ROOT / "tests" / "conftest.py")
assert _SPEC and _SPEC.loader
conftest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(conftest)


class _Reporter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write_line(self, text: str, **kwargs) -> None:
        self.lines.append(text)


class _Config:
    """最小 config：只提供 getoption。"""

    def __init__(self, cov: bool) -> None:
        self._cov = cov

    def getoption(self, name: str):
        if name in ("cov_source", "cov"):
            return ["app_zeri"] if self._cov else None
        raise ValueError(name)


def test_warns_when_cov_but_no_standalone_smoke(monkeypatch) -> None:
    monkeypatch.delenv("ZERI_PERF_SMOKE_STANDALONE", raising=False)
    reporter = _Reporter()
    conftest.pytest_terminal_summary(reporter, 0, _Config(cov=True))

    blob = "\n".join(reporter.lines)
    assert "没有独立进程补跑" in blob, "直接 pytest --cov 时必须提示性能未验证"
    assert "make cov" in blob, "提示必须指向补跑入口"


def test_quiet_when_standalone_flag_set(monkeypatch) -> None:
    """make cov 的独立冒烟进程会设 ZERI_PERF_SMOKE_STANDALONE，不应误报。"""
    monkeypatch.setenv("ZERI_PERF_SMOKE_STANDALONE", "1")
    reporter = _Reporter()
    conftest.pytest_terminal_summary(reporter, 0, _Config(cov=True))
    assert not reporter.lines


def test_quiet_without_coverage(monkeypatch) -> None:
    monkeypatch.delenv("ZERI_PERF_SMOKE_STANDALONE", raising=False)
    reporter = _Reporter()
    conftest.pytest_terminal_summary(reporter, 0, _Config(cov=False))
    assert not reporter.lines, "无插桩时冒烟会真跑，不该有提示"
