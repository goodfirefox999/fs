"""D 桶 12 条「补显式 verdict_type」的零行为变更锁（2026-11-03 评审七回路）。

背景
----
C 第二批 D 桶把 12 条 ``hard_veto=True + severity=禁用`` 的规则补成显式
``verdict_type: gate``。当时的理由是 ``effective_verdict_type`` 本来就把这个组合
**推断**为 gate，所以「补显式 = 零行为变更」。

但推理成立不等于机器验证。本文件做两件事：

1. **锁住推断路径**：即使把显式字段删掉，12 条仍必须推出 ``gate``。
   这样以后有人改 ``effective_verdict_type`` 的推断逻辑，会立刻红。
2. **锁住行为面**：用「删掉 12 条 verdict_type 的临时规则库」做 before，
   对比 state/tier/vectors/报告文本。决策面与输出面必须逐字节一致。

一个必须说清的边界（评审口径修正）
----------------------------------
完整报告**不是**逐字节一致：报告里有两处「元数据」必然会变——

- 「未归类规则」节：这 12 条已标注，不再出现在待办清单里（这是落标的**目的**）；
- manifest 的 ``rule_lib_version``：规则 YAML 内容变了，内容哈希必然变。

因此本测试先归一化这两处，再断言**其余部分逐字节一致**；并额外断言
「未归类清单减少的集合」恰好等于「本次评估命中的 D 桶规则」——
把唯一允许的变化也钉死，防止它悄悄扩大。
"""

from __future__ import annotations

import importlib.util
import re
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
import yaml
from app_zeri.report import render_markdown
from app_zeri.schemas import CourseSpec, PersonSpec, SiteSpec, TaskSpec, build_context
from app_zeri.verifier import verify_context
from core_eval import EvalConfig, evaluate
from core_rule import RULES_DIR, default_registry
from core_time import CalendarConfig

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "determinism_probe_for_d_bucket", _ROOT / "tools" / "determinism_probe.py"
)
assert _SPEC and _SPEC.loader
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)

_TZ = ZoneInfo("Asia/Shanghai")

#: C 第二批 D 桶（docs/c2-batch2-plan.md §二）
D_BUCKET: tuple[str, ...] = (
    "DG-DASHA-001",
    "DG-JINSHEN-001",
    "PUB-CHONGMING-001",
    "PUB-CHONGSHAN-001",
    "PUB-MING-SANSHA-001",
    "PUB-SANSHA-001",
    "PUB-SANSHA-002",
    "PUB-SIJUE-001",
    "PUB-SILI-001",
    "PUB-SUIPO-001",
    "PUB-WUHUANG-001",
    "PUB-YUEPO-001",
)

#: 覆盖 D 桶命中面差异的两个日课（金标准 + 立春后，后者命中更多 D 桶规则）
_CASES = (
    ("金标准-2027-07-11", datetime(2027, 7, 11, 14, 0, tzinfo=_TZ), 320.0),
    ("立春后-2027-02-10", datetime(2027, 2, 10, 10, 0, tzinfo=_TZ), 5.0),
)


def _registry_without_d_annotations(tmp_path: Path):
    """复制规则库，删掉 D 桶 12 条的显式 verdict_type，得到「落标前」快照。"""
    rules_dir = tmp_path / "rules"
    shutil.copytree(RULES_DIR, rules_dir)
    for rule_id in D_BUCKET:
        matches = list(rules_dir.rglob(f"{rule_id}.yaml"))
        assert len(matches) == 1, f"{rule_id}: 期望唯一规则文件，实际 {len(matches)}"
        path = matches[0]
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data.get("verdict_type") == "gate", f"{rule_id}: D 桶当前应为显式 gate"
        data.pop("verdict_type")
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
    return default_registry(rules_dir=rules_dir)


def _eval(registry, dt: datetime, azimuth: float):
    ctx = build_context(
        course=CourseSpec(dt=dt),
        site=SiteSpec(azimuth_deg=azimuth, lat=23.13, lon=113.26),
        task=TaskSpec(kind="修造", nodes=("修造",), strictness="strict"),
        person=PersonSpec(),
        cal=CalendarConfig(),
    )
    ev = evaluate(
        ctx,
        registry,
        EvalConfig(task_kind="修造", strictness="strict", allow_unverified=True, demo_veto=True),
    )
    result = verify_context(ctx, registry=registry, allow_unverified=True, demo_veto=True)
    return ev, result


def _strip_unlabeled_section(report: str) -> str:
    start = report.find("## 未归类规则")
    if start < 0:
        return report
    end = report.find("\n## ", start + 5)
    return report[:start] + (report[end + 1 :] if end >= 0 else "")


def _rule_lib_version(report: str) -> str | None:
    match = re.search(r'"rule_lib_version": "([^"]+)"', report)
    return match.group(1) if match else None


def _normalize_metadata(report: str) -> str:
    """归一化三类**必然**随标注/运行变化的元数据，其余部分不得有差异。

    本测试不是「删掉两节再比」：

    - 「未归类规则」节的差异由调用方精确断言为「本次命中的 D 桶规则」，
      不多不少；若未来差异集合变大，该断言必红。
    - ``rule_lib_version`` 在调用方断言**必须变化**（YAML 内容变了，内容哈希
      不变反而说明版本计算没覆盖规则内容），这里只把它换成占位符以比较其余全文。
    - 生成时间是墙钟，与判定无关，只做占位符归一化。
    """
    text = _strip_unlabeled_section(report)
    text = re.sub(r"_生成时间：.*_", "_生成时间：<normalized>_", text)
    text = re.sub(r'"rule_lib_version": "[^"]*"', '"rule_lib_version": "<normalized>"', text)
    return text


def _unlabeled_ids(report: str) -> set[str]:
    start = report.find("## 未归类规则")
    if start < 0:
        return set()
    end = report.find("\n## ", start + 5)
    section = report[start : end if end >= 0 else len(report)]
    ids: set[str] = set()
    for line in section.splitlines():
        m = re.match(r"- `([A-Z0-9-]+)`", line)
        if m:
            ids.add(m.group(1))
    return ids


def test_all_twelve_are_explicit_gate_and_inference_still_agrees() -> None:
    """显式值、推断值、以及推断路径本身，三条必须同时成立。"""
    registry = default_registry()
    for rule_id in D_BUCKET:
        rule = registry.ruleset.by_id[rule_id]
        assert rule.verdict_type == "gate", f"{rule_id}: 应已显式标注 gate"
        assert rule.hard_veto is True, f"{rule_id}: D 桶判据 hard_veto=True 不成立"
        assert rule.severity == "禁用", f"{rule_id}: D 桶判据 severity=禁用 不成立"
        assert rule.effective_verdict_type == "gate"
        # 反证：删掉显式字段，推断路径仍必须给出同一个值。
        assert replace(rule, verdict_type=None).effective_verdict_type == "gate"


@pytest.mark.parametrize("name,dt,azimuth", _CASES)
def test_before_after_decision_and_output_are_identical(tmp_path: Path, name, dt, azimuth) -> None:
    after_reg = default_registry()
    before_reg = _registry_without_d_annotations(tmp_path)

    ev_after, result_after = _eval(after_reg, dt, azimuth)
    ev_before, result_before = _eval(before_reg, dt, azimuth)

    # 决策面与输出面都按确定性探针的同一套摘要比较（避免自创口径）。
    assert probe._eval_summary(ev_after) == probe._eval_summary(ev_before), f"{name}: 决策面变了"
    assert probe._eval_output(ev_after) == probe._eval_output(ev_before), f"{name}: 输出面变了"
    # 显式再钉一次 tier 分布/向量，失败信息比摘要 diff 更好读。
    assert (ev_after.state, ev_after.tier, ev_after.publishable) == (
        ev_before.state,
        ev_before.tier,
        ev_before.publishable,
    ), f"{name}: 三态/tier/publishable 变了"
    assert ev_after.vectors == ev_before.vectors, f"{name}: 分层向量变了"

    report_after = render_markdown(result_after, registry=after_reg)
    report_before = render_markdown(result_before, registry=before_reg)

    # rule_lib_version 必须变：规则 YAML 内容变了，内容哈希应与之一致地变化。
    # 若这里相等，说明版本没有覆盖规则内容，归一化就会掩盖一个真实缺陷。
    #
    # **前提（2026-11-03 评审确认）**：`rule_lib_version` 来自
    # `loader.load_ruleset()` 对每条规则 raw YAML 做 `stable_hash` 后的库级哈希
    # （见 `lib_version = "rl-" + stable_hash(...)`）。本断言依赖「内容哈希」这一
    # 语义；若未来改成手动递增版本号，此断言需同步调整——否则会从
    # 「内容变了版本必变」退化成「有人记得改版本号」。
    version_before = _rule_lib_version(report_before)
    version_after = _rule_lib_version(report_after)
    assert version_before and version_after, f"{name}: 报告缺少 rule_lib_version"
    assert version_before != version_after, f"{name}: 规则内容已变但 rule_lib_version 未变"

    assert _normalize_metadata(report_after) == _normalize_metadata(report_before), (
        f"{name}: 除「未归类」、rule_lib_version、生成时间外，报告不应有任何差异"
    )

    # 唯一允许的变化：未归类清单里少了「本次评估命中的 D 桶规则」，且不能多删。
    hit_d = {j.rule_id for j in ev_after.judgments if j.rule_id in D_BUCKET}
    before_ids = _unlabeled_ids(report_before)
    after_ids = _unlabeled_ids(report_after)
    assert before_ids - after_ids == hit_d, (
        f"{name}: 未归类清单减少的集合与命中集合不一致；"
        f"多删={sorted((before_ids - after_ids) - hit_d)} 少删={sorted(hit_d - (before_ids - after_ids))}"
    )
    assert after_ids <= before_ids, f"{name}: 落标后不应新增未归类项"
