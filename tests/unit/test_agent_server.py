"""Phase 10 测试：AI Agent 约束（spec §5）与本地只读端点。

- system prompt 四条五派约束**逐字**存在（spec §5 verbatim，不得改写）
- 端点清单齐全：/calendar/facts、/dasha/check、/zeri/evaluate、/rules/{rule_id}
- 端点行为：JSON 只读、字段缺失 400、未知规则 404、大煞 check 触达 Layer 3
- no-network 门禁兼容：服务器在 tools/（引擎 src 零网络导入）
"""

from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "app-zeri" / "src"))

from app_zeri.agent import AGENT_ENDPOINTS, AGENT_SYSTEM_PROMPT, build_agent_system_prompt  # noqa: E402

_BODY = {
    "datetime": "2027-07-11T14:00:00+08:00",
    "site": {"azimuth_deg": 320.0, "lat": 23.13, "lon": 113.26},
    "task": {"kind": "修造", "strictness": "normal"},
}


class TestAgentPrompt:
    """spec §5：System prompt 必须新增的四条约束（逐字）。"""

    def test_four_constraints_verbatim(self) -> None:
        assert len(AGENT_SYSTEM_PROMPT) == 4
        assert "五派规则包的输出必须完整保留。禁止只引用其中一派而省略其他派。" in AGENT_SYSTEM_PROMPT[0]
        assert "不同流派存在分歧" in AGENT_SYSTEM_PROMPT[1]
        assert "煞贡/直星/人专不可用于推翻大煞 reject" in AGENT_SYSTEM_PROMPT[2]
        assert "Layer 3 的优先性" in AGENT_SYSTEM_PROMPT[2]
        assert "status=PARTIAL" in AGENT_SYSTEM_PROMPT[3]
        assert "四余部分未计算" in AGENT_SYSTEM_PROMPT[3]

    def test_endpoints_listed(self) -> None:
        assert AGENT_ENDPOINTS == (
            "/calendar/facts", "/dasha/check", "/zeri/evaluate", "/rules/{rule_id}",
        )
        prompt = build_agent_system_prompt()
        for ep in AGENT_ENDPOINTS:
            assert ep in prompt
        # 元指令：LLM 只解释不裁决
        assert "只解释" in prompt and "不得生成" in prompt or "禁止生成" in prompt


@pytest.fixture(scope="module")
def server_url():
    from agent_server import ZeriHandler
    from http.server import ThreadingHTTPServer

    srv = ThreadingHTTPServer(("127.0.0.1", 0), ZeriHandler)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def _get(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _post(url: str, body: dict) -> tuple[int, dict]:
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class TestAgentEndpoints:
    def test_healthz_lists_endpoints(self, server_url) -> None:
        code, data = _get(f"{server_url}/healthz")
        assert code == 200 and data["status"] == "ok"
        for ep in AGENT_ENDPOINTS:
            assert ep in data["endpoints"]

    def test_calendar_facts(self, server_url) -> None:
        code, data = _post(f"{server_url}/calendar/facts", _BODY)
        assert code == 200
        assert data["course"]["bazi"]
        assert "facts" in data and "sansha" in data["facts"]
        assert data["calibers"], "口径回显必须透出（报告纪律）"

    def test_calendar_facts_missing_field_400(self, server_url) -> None:
        bad = {"datetime": "2027-07-11T14:00:00+08:00", "site": {"azimuth_deg": 1.0}}
        code, data = _post(f"{server_url}/calendar/facts", bad)
        assert code == 400 and "site.lat" in data["error"]

    def test_naive_datetime_400(self, server_url) -> None:
        bad = dict(_BODY, datetime="2027-07-11T14:00:00")
        code, data = _post(f"{server_url}/calendar/facts", bad)
        assert code == 400 and "时区" in data["error"]

    def test_rules_endpoint(self, server_url) -> None:
        code, data = _get(f"{server_url}/rules/DG-DASHA-001")
        assert code == 200
        assert data["school"] == "donggong" and data["hard_veto"] is True
        assert data["citation"]["source"], "规则详情必须带 source_ref"
        code2, data2 = _get(f"{server_url}/rules/NO-SUCH-999")
        assert code2 == 404

    def test_zeri_evaluate_shape(self, server_url) -> None:
        code, data = _post(f"{server_url}/zeri/evaluate", _BODY)
        assert code == 200
        assert data["tier"] in ("REJECTED", "NEEDS_REVIEW", "ACCEPTABLE", "PREFERRED")
        fso = data["five_school_output"]
        schools = [k for k in fso if not k.startswith("_")]
        assert {"zhengwuxing", "sanhe", "donggong", "xuankong_dagua", "tianxing"} <= set(schools)
        arb = data["arbitration"]
        assert {"date", "school_results", "consensus", "conflicts"} <= set(arb)

    def test_dasha_check_layer3_note(self, server_url) -> None:
        code, data = _post(f"{server_url}/dasha/check", _BODY)
        assert code == 200
        assert data["rejected"] in (True, False)
        assert "Layer 3" in data["note"]

    def test_unknown_endpoint_404(self, server_url) -> None:
        code, data = _get(f"{server_url}/nope")
        assert code == 404


class TestNoNetworkBoundary:
    """引擎 src 零网络导入；服务器只在 tools/（no_network_scan 的 ROOTS 之外）。"""

    def test_server_not_in_src(self) -> None:
        src = ROOT / "app-zeri" / "src" / "app_zeri"
        assert not (src / "server.py").exists(), "HTTP 服务不得进入引擎 src（no_network 门禁）"

    def test_scan_passes_with_agent_module(self) -> None:
        import subprocess

        r = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "no_network_scan.py")],
            capture_output=True, text=True, timeout=120,
        )
        assert r.returncode == 0, r.stdout + r.stderr
