# -*- coding: utf-8 -*-
"""fs168 合规限速回归：确保页面抓取的所有路径都经 0.5 req/s 桶。

背景：2026-11-17 审计发现 fs168_digest.fetch() 从未调用 pace()，
深采/补页/精华扫描三条路径全部裸奔，与 §2.1 的自宣称限速不符。
本测试用 monkeypatch 拦截 curl 子进程与 sleep，断言每次抓取都触发 pace。
"""
from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scrapers"))

import fs168_digest as digest  # noqa: E402


def test_fetch_always_calls_pace(monkeypatch):
    """fetch() 入口必须调用 pace()，含质询续期的递归路径。"""
    calls = []
    monkeypatch.setattr(digest, "pace", lambda: calls.append("pace"))
    monkeypatch.setattr(digest, "load_session", lambda: {"ua": "test", "cookie": ""})

    class Result:
        stdout = b"<html>ok</html>\n200"

    monkeypatch.setattr(digest.subprocess, "run", lambda *a, **kw: Result())
    digest.fetch("https://www.fengshui-168.com/forum.php?mod=viewthread&tid=1")
    assert calls == ["pace"], f"fetch 必须且只调用一次 pace，实际 {calls}"


def test_recursive_retry_also_paced(monkeypatch):
    """质询续期会递归调用 fetch，因此每个 HTTP 请求都要各自计数。"""
    calls = []
    monkeypatch.setattr(digest, "pace", lambda: calls.append("pace"))
    monkeypatch.setattr(digest, "load_session", lambda: {"ua": "test", "cookie": ""})
    monkeypatch.setattr(digest, "refresh_cookies_from_tabbit", lambda: None)

    class Challenge:
        stdout = b"Just a moment\n403"

    class Ok:
        stdout = b"<html>ok</html>\n200"

    results = iter([Challenge(), Ok()])
    monkeypatch.setattr(digest.subprocess, "run", lambda *a, **kw: next(results))
    digest.fetch("https://www.fengshui-168.com/forum.php?mod=viewthread&tid=1")
    assert len(calls) == 2, f"质询续期产生两次 HTTP 请求，应各有一次 pace，实际 {calls}"


def test_pace_interval(monkeypatch):
    """两次调用间隔不足 2s 时，pace 必须补足。"""
    sleeps = []
    clock = iter([100.0, 100.0, 101.0, 101.0])
    monkeypatch.setattr(digest.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(digest.random, "uniform", lambda a, b: 0.0)
    monkeypatch.setattr(digest.time, "time", lambda: next(clock))
    digest._last_hit = 0.0
    digest.pace()          # t=100，last=0 → wait 0，更新 last=100
    digest.pace()          # t=101，last=100 → wait 1.0
    assert sleeps and sleeps[0] >= 1.0, f"间隔不足 2s 时应补足，实际 sleep={sleeps}"
