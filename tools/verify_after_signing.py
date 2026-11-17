#!/usr/bin/env python3
"""签名后验收脚本（预写；不接入 CI）。

用途：把「签完之后应该看到什么」固化成可复跑的断言，避免签完又靠肉眼判断。

用法::

    python tools/verify_after_signing.py --mode liuhe
    python tools/verify_after_signing.py --mode publishable

两种模式
--------
``liuhe``
    2027-07-14T09:00、安葬、乾山 315°、主命庚戌。
    前提：``SH-LIUHE-001`` 已由人类签名（status=已考证 + evidence.grade=A +
    quote_verified=true）。断言共识为 1/1、唯一投票派为三合、证据等级 A；
    同时 ``publishable`` 必须仍为 False（三煞两条尚缺证据）。
    报告结论区块不得出现「0/0」或「无参与投票」。

``publishable``
    2027-05-28T12:00、安葬 strict、子山 0°（十二地支山）。
    选例理由：巳月、非四离四绝、年／月三煞均不及子，属「未触发否决」的干净样本。
    断言 ``blocked_required`` 不再有 ``pending_ruling``；若必需规则全部可判定或
    不适用，则 ``publishable`` 必须为 True；若仍有阻塞，则必须为 False，
    并逐条打印缺什么证据。

退出码：断言全部满足 = 0；任一不满足 = 1（并打印实际值）。
签名前运行会失败——这是预期，不是脚本故障。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
for _pkg in ("core-time", "core-symbol", "core-rule", "core-eval", "app-zeri"):
    _src = str(REPO_ROOT / _pkg / "src")
    if _src not in sys.path:
        sys.path.insert(0, _src)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app_zeri.report import render_markdown  # noqa: E402
from app_zeri.schemas import PersonSpec, SiteSpec, TaskSpec  # noqa: E402
from app_zeri.verifier import VerifyResult, verify  # noqa: E402
from core_eval.engine import Evaluation  # noqa: E402
from core_rule.registry import RuleRegistry, default_registry  # noqa: E402

TZ = ZoneInfo("Asia/Shanghai")
ZHI_MOUNTAINS = "子丑寅卯辰巳午未申酉戌亥"
BLOCK_HINT = {
    "pending_ruling": "先完成对应裁定（evidence.blocking_ruling）",
    "pending_verification": "A 级原文已核，缺人类签名（verified_by + commit trailer）",
    "evidence_insufficient": "缺 A/B 级影印逐字引文或 quote_verified，未达投票门槛",
    "input_insufficient": "补输入或口径（规则已签但本轮判不了）",
}


def _consensus_detail(ev: Evaluation) -> dict[str, Any]:
    return (ev.manifest.get("five_school_output") or {}).get("_consensus_detail") or {}


def _conclusion_block(markdown: str) -> str:
    lines = markdown.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## 结论")), None)
    if start is None:
        return ""
    block: list[str] = []
    for line in lines[start:]:
        if block and line.startswith("## "):
            break
        block.append(line)
    return "\n".join(block)


def _fmt(value: Any) -> str:
    return repr(value)


def _run_liuhe(reg: RuleRegistry) -> int:
    print("[liuhe] 2027-07-14T09:00 乾山315° 安葬 strict 主命庚戌")
    result = verify(
        dt=datetime(2027, 7, 14, 9, 0, tzinfo=TZ),
        site=SiteSpec(azimuth_deg=315.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="安葬", nodes=("安葬",), strictness="strict"),
        person=PersonSpec(year_gz="庚戌"),
        registry=reg,
    )
    ev = result.evaluation
    detail = _consensus_detail(ev)
    markdown = render_markdown(result, registry=reg)
    conclusion = _conclusion_block(markdown)

    grades = (detail.get("voter_evidence_grades") or {}).get("sanhe")
    checks = [
        ("consensus_ratio", detail.get("consensus_ratio"), "1/1", detail.get("consensus_ratio") == "1/1"),
        ("voters", detail.get("voters"), ["sanhe"], detail.get("voters") == ["sanhe"]),
        ("voter_evidence_grades['sanhe']", grades, "A", grades == "A" or grades == ["A"]),
        ("publishable", ev.publishable, False, ev.publishable is False),
        (
            "报告结论区块出现 0/0",
            "0/0" in conclusion,
            False,
            "0/0" not in conclusion,
        ),
        (
            "报告结论区块出现「无参与投票」",
            "无参与投票" in conclusion,
            False,
            "无参与投票" not in conclusion,
        ),
    ]
    failed = 0
    for name, actual, expected, ok in checks:
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name} = {_fmt(actual)}（期望 {_fmt(expected)}）")
        failed += 0 if ok else 1
    if failed:
        print(f"\nFAIL: {failed} 项不满足（签名未完成时出现此结果属预期）")
        print("--- 报告结论区块 ---")
        print(conclusion or "（未找到结论区块）")
        return 1
    print("\nPASS: 六合签名后的共识断言全部满足；publishable 仍为 False（三煞待证）")
    return 0


def _evidence_gap(rule: Any) -> str:
    evidence = getattr(rule, "evidence", None)
    if evidence is None:
        return "规则无 evidence 块（待考证），需先补影印出处"
    parts = [f"grade={evidence.grade}", f"quote_verified={evidence.quote_verified}"]
    if evidence.blocking_ruling:
        parts.append(f"blocking_ruling={evidence.blocking_ruling}")
    return "、".join(parts)


def _run_publishable(reg: RuleRegistry) -> int:
    print("[publishable] 2027-05-28T12:00 子山0° 安葬 strict")
    print("  选例理由：巳月、非四离四绝；年三煞未及子，月三煞为寅卯辰；未触发否决。")
    result = verify(
        dt=datetime(2027, 5, 28, 12, 0, tzinfo=TZ),
        site=SiteSpec(azimuth_deg=0.0, lat=23.13, lon=113.26),
        task=TaskSpec(kind="安葬", nodes=("安葬",), strictness="strict"),
        registry=reg,
    )
    assert isinstance(result, VerifyResult)
    ev = result.evaluation
    mountain = result.context["site"]["mountain"]
    vetoes = [j.rule_id for res in ev.per_school.values() for j in res.vetoes]
    blockers = list(ev.blocked_required)
    pending = [b for b in blockers if b.get("kind") == "pending_ruling"]

    failed = 0
    print(f"  坐山 = {mountain}（十二地支山：{'是' if mountain in ZHI_MOUNTAINS else '否'}）")
    if mountain not in ZHI_MOUNTAINS:
        print(f"  [FAIL] 验收样本必须是十二地支山，实际 {mountain}")
        failed += 1
    print(f"  否决命中 = {vetoes or '无'}")
    if vetoes:
        print("  [FAIL] 验收样本不应触发否决")
        failed += 1

    if blockers:
        print(f"  blocked_required（{len(blockers)} 条）：")
        for b in blockers:
            rule = reg.ruleset.by_id.get(b["rule_id"])
            print(
                f"    - {b['rule_id']} status={b.get('status')} kind={b.get('kind')} "
                f"detail={b.get('detail')}"
            )
            print(f"      缺证据：{BLOCK_HINT.get(b.get('kind'), '未知')}；{_evidence_gap(rule)}")
    else:
        print("  blocked_required：无")

    print(f"  required_rule_ids = {list(ev.required_rule_ids)}")
    print(f"  required_not_applicable = {[x['rule_id'] for x in ev.required_not_applicable]}")
    print(f"  tier = {ev.tier}　publishable = {ev.publishable}")

    if pending:
        print(f"\nFAIL: blocked_required 仍有 pending_ruling {len(pending)} 条")
        failed += 1
    if blockers and ev.publishable:
        print("\nFAIL: 仍有阻塞项但 publishable=True（口径不一致）")
        failed += 1
    if not blockers and not ev.publishable:
        print("\nFAIL: 必需规则已全部可判定/不适用，但 publishable=False")
        print(f"  冲突：{ev.conflicts or '无'}")
        failed += 1
    if failed:
        return 1
    if blockers:
        print("\nPASS: 无 pending_ruling；publishable=False 的原因已逐条列出（证据未齐）")
    else:
        print("\nPASS: 必需规则全部可判定/不适用，publishable=True")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="签名后验收（liuhe / publishable）")
    parser.add_argument("--mode", choices=("liuhe", "publishable"), required=True)
    args = parser.parse_args(argv)
    reg = default_registry()
    if args.mode == "liuhe":
        return _run_liuhe(reg)
    return _run_publishable(reg)


if __name__ == "__main__":
    raise SystemExit(main())
