#!/usr/bin/env python
"""Phase 10：AI Agent 本地只读 JSON 端点（评审扩展版 spec §5）。

**位置说明**：本文件在 ``tools/`` 而非 ``*/src/``——CI 的 no-network 门禁
规定引擎运行时代码（core-*/src、app-zeri/src）不得导入任何网络模块；
本服务是**引擎之上的本地适配器**（入站 HTTP → 引擎函数 → 出站 JSON），
不发起任何外联，因此归属工具层。引擎本体保持零网络依赖。

端点（spec §5：端点不变）：
- ``POST /calendar/facts``   历法与事实：四柱/节气/facts.* 全量结构事实
- ``POST /dasha/check``      Layer 3 大煞/冲命检查：rejected + reject_rules
- ``POST /zeri/evaluate``    全派评估：five_school_output + spec §4 仲裁结构
- ``GET  /rules/{rule_id}``  规则详情：condition/status/citation/severity
- ``GET  /healthz``          存活检查

请求体（POST 端点共用）::

    {
      "datetime": "2027-07-11T14:00:00+08:00",
      "site":  {"azimuth_deg": 320.0, "lat": 23.13, "lon": 113.26},
      "task":  {"kind": "修造", "strictness": "normal"},
      "person": {"year_zhi": "午"}          // 可选
    }

约束（spec 元指令）：本服务只做确定性计算与结构透出，**不调用任何大模型**；
Agent 拿到 JSON 后自行解释（约束见 app_zeri/agent.py，LLM 不得生成 verdict）。

用法::

    python tools/agent_server.py --port 8080        # 默认 127.0.0.1:8080
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
for pkg in ("core-time", "core-symbol", "core-rule", "core-eval", "app-zeri"):
    sys.path.insert(0, str(ROOT / pkg / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app_zeri.agent import AGENT_ENDPOINTS, build_agent_system_prompt  # noqa: E402
from app_zeri.schemas import build_context  # noqa: E402
from core_eval.arbitration import build_spec_output  # noqa: E402
from core_eval.engine import EvalConfig, evaluate  # noqa: E402
from core_rule.registry import default_registry  # noqa: E402

_REG = default_registry()


class _BadRequest(Exception):
    pass


def _parse_body(body: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    """请求体 → (ctx, cfg, site_spec, task_spec)。字段缺失即 400，不猜默认。"""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec
    from core_time import CalendarConfig

    try:
        dt = datetime.fromisoformat(body["datetime"])
    except (KeyError, ValueError) as exc:
        raise _BadRequest(f"datetime 缺失或非法（ISO 8601）: {exc}") from exc
    if dt.tzinfo is None:
        raise _BadRequest("datetime 必须带时区（如 +08:00）")
    site_raw = body.get("site") or {}
    task_raw = body.get("task") or {}
    for key in ("azimuth_deg", "lat", "lon"):
        if key not in site_raw:
            raise _BadRequest(f"site.{key} 缺失")
    if "kind" not in task_raw:
        raise _BadRequest("task.kind 缺失")
    person_raw = body.get("person")
    site = SiteSpec(azimuth_deg=float(site_raw["azimuth_deg"]),
                    lat=float(site_raw["lat"]), lon=float(site_raw["lon"]))
    task = TaskSpec(kind=str(task_raw["kind"]),
                    strictness=str(task_raw.get("strictness", "normal")))
    person = PersonSpec(**{k: v for k, v in (person_raw or {}).items()}) if person_raw else None
    cal = CalendarConfig()
    ctx = build_context(CourseSpec(dt=dt), site, task, person=person, cal=cal,
                        calibers=_REG.calibers)
    cfg = EvalConfig(task_kind=task.kind, strictness=task.strictness)
    return ctx, cfg, site, task


class ZeriHandler(BaseHTTPRequestHandler):
    """只读 JSON 适配器：无外联、无大模型调用、无状态。"""

    server_version = "zeri-agent/1.0"

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise _BadRequest("请求体为空")
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise _BadRequest(f"请求体不是合法 JSON: {exc}") from exc
        if not isinstance(body, dict):
            raise _BadRequest("请求体顶层必须是对象")
        return body

    # ---- GET ----
    def do_GET(self) -> None:  # noqa: N802（http.server 命名约定）
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            self._send(200, {"status": "ok", "engine": "zeri", "endpoints": list(AGENT_ENDPOINTS)})
            return
        if path.startswith("/rules/"):
            rule_id = path[len("/rules/"):].strip("/")
            rule = _REG.ruleset.by_id.get(rule_id)
            if rule is None:
                self._send(404, {"error": f"未知规则: {rule_id}"})
                return
            self._send(200, {
                "rule_id": rule.rule_id,
                "version": rule.version,
                "school": rule.school,
                "category": rule.category,
                "status": rule.status,           # verification status（人工升级）
                "severity": rule.severity,
                "hard_veto": rule.hard_veto,
                "evaluable": rule.evaluable,
                "condition": rule.condition,
                "citation": rule.citation.to_dict() if hasattr(rule.citation, "to_dict") else rule.citation,
                "explanation": rule.explanation,
                "notes": rule.notes,
            })
            return
        self._send(404, {"error": f"未知端点: {path}", "endpoints": list(AGENT_ENDPOINTS)})

    # ---- POST ----
    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        try:
            body = self._read_json()
            ctx, cfg, _site, _task = _parse_body(body)
            if path == "/calendar/facts":
                self._send(200, {
                    "course": ctx["course"], "time": ctx["time"],
                    "site": ctx["site"], "facts": ctx["facts"],
                    "calibers": (ctx["facts"] or {}).get("_calibers"),
                })
            elif path == "/dasha/check":
                ev = evaluate(ctx, _REG, cfg)
                reject_rules = [j.rule_id for res in ev.per_school.values() for j in res.vetoes]
                out = build_spec_output([(ev, ctx)])
                self._send(200, {
                    "date": ev.candidate,
                    "rejected": bool(reject_rules),
                    "reject_rules": reject_rules,
                    "arbitration": out,
                    "note": "Layer 3 reject 覆盖一切五派评分；董公吉星不能绕过（spec §3）",
                })
            elif path == "/zeri/evaluate":
                ev = evaluate(ctx, _REG, cfg)
                out = build_spec_output([(ev, ctx)])[  # 单候选 → scored/rejected 各一
                    "rejected_dates" if ev.tier == "REJECTED" else "scored_dates"
                ]
                self._send(200, {
                    "candidate": ev.candidate,
                    "state": ev.state,
                    "tier": ev.tier,
                    "five_school_output": ev.manifest.get("five_school_output"),
                    "arbitration": out[0] if out else None,
                    "conflicts": ev.conflicts,
                    "unknowns": ev.unknowns,
                    "vectors": ev.vectors,
                    "blocked_required": ev.blocked_required,
                })
            else:
                self._send(404, {"error": f"未知端点: {path}", "endpoints": list(AGENT_ENDPOINTS)})
        except _BadRequest as exc:
            self._send(400, {"error": str(exc)})
        except Exception as exc:  # noqa: BLE001 - 边界处兜底为 500 JSON
            self._send(500, {"error": f"内部错误: {type(exc).__name__}: {exc}"})

    def log_message(self, fmt: str, *args: Any) -> None:  # pragma: no cover
        sys.stderr.write("[zeri-agent] " + fmt % args + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="zeri AI Agent 本地只读端点")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ZeriHandler)
    print(f"zeri agent endpoints on http://{args.host}:{args.port}")
    print("system prompt constraints:")
    print(build_agent_system_prompt())
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
