"""``tools/check_proxy.py`` 的判据测试（2026-11-03 评审七回路）。

代理预检的价值在于**区分故障来源**，不是「能不能上网」：

- 环境变量在 + 经代理可达 → 绿；
- 环境变量在 + 代理挂 + 直连可达 → 报「环境/代理问题」，不是上游；
- 环境变量在 + 代理挂 + 直连也挂 → 才允许怀疑上游；
- 环境变量丢了 + 直连可达 → 绿但必须警告（静默直连正是要防的）；
- 环境变量丢了 + 直连也挂 → 红，并提示先确认环境变量。

每个用例都 mock 掉真实网络，只验证判定逻辑与文案指向。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "check_proxy", Path(__file__).resolve().parents[2] / "tools" / "check_proxy.py"
)
assert _SPEC and _SPEC.loader
proxy = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(proxy)


@pytest.fixture
def no_git_proxy(monkeypatch) -> None:
    monkeypatch.setattr(proxy, "git_proxy", lambda: (None, None))


def test_env_proxy_takes_priority() -> None:
    assert proxy.env_proxy({"https_proxy": "http://127.0.0.1:1", "http_proxy": "http://x"}) == (
        "https_proxy",
        "http://127.0.0.1:1",
    )


def test_safe_proxy_hides_credentials() -> None:
    assert proxy.safe_proxy("http://user:secret@127.0.0.1:62727") == "http://***@127.0.0.1:62727"
    assert proxy.safe_proxy("127.0.0.1:62727") == "127.0.0.1:62727"


def test_probe_nonzero_rc_keeps_rc_in_evidence(monkeypatch) -> None:
    """curl 可能先打印 200 再超时；证据必须带 rc，不能让人误读成可达。"""

    class Proc:
        returncode = 28
        stdout = "200"
        stderr = "Connection timed out"

    monkeypatch.setattr(proxy.subprocess, "run", lambda *a, **k: Proc())
    ok, evidence = proxy.probe("https://example.com")
    assert ok is False
    assert "200" in evidence and "rc=28" in evidence


class TestCheck:
    def test_proxy_reachable_reports_both_paths_and_route(
        self, monkeypatch, no_git_proxy, capsys
    ) -> None:
        monkeypatch.setattr(proxy, "env_proxy", lambda: ("https_proxy", "http://127.0.0.1:1"))
        calls: list[str | None] = []

        def fake_probe(url, *, proxy=None, timeout=10):  # noqa: ANN001
            calls.append(proxy)
            return True, "200"

        monkeypatch.setattr(proxy, "probe", fake_probe)
        assert proxy.check("https://github.com") == 0
        out = capsys.readouterr().out
        assert "env_proxy: 有（https_proxy=http://127.0.0.1:1）" in out
        assert "git_config_proxy: 无" in out
        assert "direct: 200  via_proxy: 200" in out
        assert "push_route: 当前将走 proxy（环境变量 https_proxy）" in out
        assert "✅" in out
        assert calls == [None, "http://127.0.0.1:1"], "直连与代理都要留下证据"

    def test_proxy_down_direct_up_points_at_proxy(self, monkeypatch, no_git_proxy, capsys) -> None:
        monkeypatch.setattr(proxy, "env_proxy", lambda: ("https_proxy", "http://127.0.0.1:1"))
        calls: list[str | None] = []

        def fake_probe(url, *, proxy=None, timeout=10):  # noqa: ANN001
            calls.append(proxy)
            return (False, "502") if proxy else (True, "200")

        monkeypatch.setattr(proxy, "probe", fake_probe)
        assert proxy.check("https://github.com") == 1
        out = capsys.readouterr().out
        assert "direct: 200  via_proxy: 502" in out
        assert "push_route: 当前将走 proxy（环境变量 https_proxy）" in out
        assert "问题在代理/环境变量，不是上游" in out
        assert calls == [None, "http://127.0.0.1:1"], "先探直连做对照，再探代理"

    def test_proxy_down_direct_down_mentions_upstream(self, monkeypatch, no_git_proxy, capsys) -> None:
        monkeypatch.setattr(proxy, "env_proxy", lambda: ("https_proxy", "http://127.0.0.1:1"))
        monkeypatch.setattr(proxy, "probe", lambda url, **kw: (False, "curl 超时"))
        assert proxy.check("https://github.com") == 1
        out = capsys.readouterr().out
        assert "direct: curl 超时  via_proxy: curl 超时" in out
        assert "上游/网络故障" in out

    def test_missing_env_but_direct_up_warns(self, monkeypatch, no_git_proxy, capsys) -> None:
        monkeypatch.setattr(proxy, "env_proxy", lambda: (None, None))
        monkeypatch.setattr(proxy, "probe", lambda url, **kw: (True, "200"))
        assert proxy.check("https://github.com") == 0
        out = capsys.readouterr().out
        assert "env_proxy: 无  git_config_proxy: 无" in out
        assert "direct: 200  via_proxy: 未配置" in out
        assert "push_route: 当前将走 direct" in out
        assert "未配置代理" in out
        assert "静默直连" in out

    def test_missing_env_and_direct_down_fails(self, monkeypatch, no_git_proxy, capsys) -> None:
        monkeypatch.setattr(proxy, "env_proxy", lambda: (None, None))
        monkeypatch.setattr(proxy, "probe", lambda url, **kw: (False, "curl 超时"))
        assert proxy.check("https://github.com") == 1
        assert "不要直接归因「上游挂了」" in capsys.readouterr().out

    def test_git_config_proxy_is_used(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(proxy, "env_proxy", lambda: (None, None))
        monkeypatch.setattr(proxy, "git_proxy", lambda: ("https.proxy", "http://127.0.0.1:2"))
        monkeypatch.setattr(proxy, "probe", lambda url, **kw: (True, "200"))
        assert proxy.check("https://github.com") == 0
        out = capsys.readouterr().out
        assert "push_route: 当前将走 proxy（git config https.proxy）" in out
        assert "git config https.proxy" in out

    def test_both_configured_reports_env_route(self, monkeypatch, capsys) -> None:
        """环境变量与 git config 同时存在时，报告实际优先的那条。"""
        monkeypatch.setattr(proxy, "env_proxy", lambda: ("https_proxy", "http://127.0.0.1:1"))
        monkeypatch.setattr(proxy, "git_proxy", lambda: ("https.proxy", "http://127.0.0.1:2"))
        monkeypatch.setattr(proxy, "probe", lambda url, **kw: (True, "200"))
        assert proxy.check("https://github.com") == 0
        out = capsys.readouterr().out
        assert "env_proxy: 有" in out and "git_config_proxy: 有" in out
        assert "push_route: 当前将走 proxy（环境变量 https_proxy）" in out
