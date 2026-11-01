"""报告编排（应用层）：JSON 为事实源，Markdown 为人类可读视图。

硬性要求
--------
1. 每个结论必须带 ``rule_id`` 与出处（无引文时显式标"原文待补"）；
2. 报告页脚固定免责声明，且**不得**出现"准确率""灵验度""吉凶概率"等表述；
3. 必须回显全部争议口径（附录 B）与 manifest（可复现清单）；
4. 冲突与未知必须单独成节，不得折叠进结论。
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from core_eval import Evaluation, SchoolResult
from core_rule.registry import RuleRegistry

from .generator import GenResult
from .verifier import VerifyResult

__all__ = [
    "DISCLAIMER",
    "render_markdown",
    "render_generation_markdown",
    "render_json",
    "render_manifest_block",
]

DISCLAIMER = (
    "本报告为**传统文化参考与规则复核工具**输出，不构成工程安全、结构鉴定、医疗、法律或"
    "任何形式的专业意见；不承诺准确率，不做「灵验度」评分，不提供化解/符咒/法事建议。"
    "涉及健康与事故的问题请就医并依法维权。所有结论仅在所载规则库版本与参数快照下成立。"
)


def _fmt_citation(citation: dict[str, Any]) -> str:
    source = citation.get("source") or "（未载出处）"
    quote = citation.get("quote")
    juan = citation.get("juan")
    if quote:
        loc = f"卷{juan}" if juan else "卷次待补"
        return f"{source}（{loc}）：「{quote}」"
    return f"{source}（**原文待补**，未参与正式判定）"


def _judgment_rows(judgments: list[Any]) -> list[str]:
    if not judgments:
        return ["| — | — | — | — |", ]
    rows = ["| 规则 | 类别 | 严重度 | 依据 |", "|---|---|---|---|"]
    for j in judgments:
        rows.append(
            f"| `{j.rule_id}` | {j.category} | {j.severity} | {_fmt_citation(j.citation)} |"
        )
    return rows


def _school_block(res: SchoolResult) -> list[str]:
    lines: list[str] = []
    c = res.counts
    lines.append(f"### 派别：{res.school}")
    lines.append("")
    lines.append(f"- 三态结论：**{res.state}**")
    lines.append(
        f"- 分层计数：硬伤 {c['hard_fail_count']} / 强忌 {c['strong_avoid_count']} / "
        f"提示 {c['note_count']} / 正向 {c['positive_count']} / 未知 {c['unknown_count']}"
    )
    lines.append(f"- 评估规则数：{res.rules_evaluated}")
    if res.rank_score is not None:
        lines.append(f"- 正向权重均值：{res.rank_score:.2f}（**非吉凶概率**）")
    lines.append("")

    if res.vetoes:
        demo = [j for j in res.vetoes if j.is_demo]
        solid = [j for j in res.vetoes if not j.is_demo]
        lines.append("**否决项（命中即判不可用）**")
        lines.append("")
        if solid:
            lines.append("_确定命中（已考证/定义级）：_")
            lines.append("")
            lines.extend(_judgment_rows(solid))
            lines.append("")
        if not solid:
            lines.append(
                "_确定命中：当前无（已考证的否决规则 0 条；定义级规则 severity=记录，"
                "不参与否决）—— 这是规则库考证进度，不是「该日课无问题」。_"
            )
            lines.append("")
        if demo:
            lines.append("_演示命中（规则未考证，**不作为排除依据**）：_")
            lines.append("")
            lines.extend(_judgment_rows(demo))
            lines.append("")
        for j in res.vetoes:
            tag = "（演示）" if j.is_demo else ""
            lines.append(f"- `{j.rule_id}`{tag}：{j.hit_detail}")
        lines.append("")

    if res.cautions:
        lines.append("**强忌项（有则判存疑）**")
        lines.append("")
        lines.extend(_judgment_rows(res.cautions))
        lines.append("")
        for j in res.cautions:
            lines.append(f"- `{j.rule_id}`：{j.hit_detail}")
        lines.append("")

    # ADR-0014 决策 0：存疑命中——参与评估但暂不采信，不入否决/tier
    if res.controversial:
        lines.append(
            "**存疑命中（status=有争议：口径与建模存疑，暂不采信；"
            "不入否决、不影响 tier——ADR-0014 决策 0）**"
        )
        lines.append("")
        lines.extend(_judgment_rows(res.controversial))
        lines.append("")
        for j in res.controversial:
            lines.append(f"- `{j.rule_id}`：{j.hit_detail}")
        lines.append("")

    # ADR-0014 决策 3：演示命中恒开渲染（demo_veto=False 时不计入 state/tier）
    if res.demo_hits:
        lines.append(
            "**演示命中（规则未考证，不作为排除依据；未计入 state/tier——ADR-0014 决策 3）**"
        )
        lines.append("")
        lines.extend(_judgment_rows(res.demo_hits))
        lines.append("")
        for j in res.demo_hits:
            lines.append(f"- `{j.rule_id}`：{j.hit_detail}")
        lines.append("")

    if res.positives:
        lines.append("**正向证据**")
        lines.append("")
        lines.extend(_judgment_rows(res.positives))
        lines.append("")
        for j in res.positives:
            lines.append(f"- `{j.rule_id}`：{j.hit_detail}")
        lines.append("")

    if res.notes:
        lines.append("**提示项**")
        lines.append("")
        lines.extend(_judgment_rows(res.notes))
        lines.append("")

    if res.unknowns:
        lines.append("**未知（按原因分类，不得视为通过）**")
        lines.append("")
        lines.append("| 规则 | 类别 | 原因分类 | 解除条件 |")
        lines.append("|---|---|---|---|")
        for j in res.unknowns:
            lines.append(
                f"| `{j.rule_id}` | {j.category} | {_reason_label(j.unknown_reason)} | "
                f"{j.remedy or '—'} |"
            )
        lines.append("")
    return lines


def _reason_label(reason: str | None) -> str:
    return {
        "missing_input": "缺输入",
        "caliber_undecided": "口径未定",
        "unverified_rule": "规则未考证",
    }.get(reason or "", reason or "—")


def render_manifest_block(manifest: dict[str, Any], cal_manifest: dict[str, Any] | None = None) -> list[str]:
    lines = ["## 可复现清单（manifest）", "", "```json"]
    lines.append(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    if cal_manifest:
        lines.append("```")
        lines.append("")
        lines.append("**历法口径（争议项，全部回显）**")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(cal_manifest, ensure_ascii=False, indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")
    return lines


def render_markdown(result: VerifyResult, *, registry: RuleRegistry | None = None) -> str:
    """渲染单候选复核报告。"""
    ev: Evaluation = result.evaluation
    ctx = result.context
    course = ctx["course"]
    site = ctx["site"]
    time_ctx = ctx["time"]
    task = ctx["task"]

    lines: list[str] = []
    lines.append("# 择日复核报告")
    lines.append("")
    # ADR-0014 决策 3：demo_veto=True 时首行显著标注（结论不可作为发布依据）
    if (ev.manifest.get("config") or {}).get("demo_veto"):
        lines.append(
            "> 🚧 **含演示否决（--demo-veto）：演示命中已计入结论，"
            "本报告不可作为发布依据（ADR-0014 决策 3）。**"
        )
        lines.append("")
    lines.append(f"- 候选时刻：`{time_ctx['datetime']}`（{time_ctx['timezone']}）")
    lines.append(f"- 事项：{task['kind']}" + (f"（节点：{task['node']}）" if task.get("node") else ""))
    lines.append(f"- 严格档：{task['strictness']}")
    lines.append(f"- 四柱：**{course['bazi']}**")
    lines.append(f"- 农历：{time_ctx['lunar']}　月建节气：{time_ctx['jie']}")
    lines.append(
        f"- 坐向：坐 **{site['mountain']}** 向 **{site['facing']}**"
        f"（方位角 {site['azimuth']}°，偏移 {site['offset_deg']}°，兼：{site['jian'] or '正针'}）"
    )
    lines.append(
        f"- 山家地支：{site['shan_jia_zhi'] or '（四维山未兼，山家地支不可得）'}"
        f"　分金槽：{site['fenjin']['slot']}"
    )
    lines.append("")
    verified_veto = ev.vectors.get("verified_veto_count", 0)
    demo_veto = ev.vectors.get("demo_veto_count", 0)
    # 措辞三分：确定 / 演示命中 / 未知
    if ev.state == "不可用" and verified_veto > 0:
        verdict_label = "**不可用（确定）** —— 由已考证/定义级规则判定"
    elif ev.state == "不可用" and verified_veto == 0 and demo_veto > 0:
        verdict_label = (
            "**演示性不可用** —— 仅由未考证规则命中，"
            "**不作为排除依据**；补原文后方可据此排除"
        )
    elif ev.state == "存疑":
        verdict_label = "**存疑** —— 存在强忌或未消解冲突，详见下方分解"
    else:
        verdict_label = "**可用** —— 未触发否决层（不等于可发布）"

    lines.append(
        f"## 结论：{verdict_label}　推荐等级：**{ev.tier}**　"
        f"可发布：**{'是' if ev.publishable else '否'}**"
    )
    lines.append("")
    # GAP-TASKKIND-EMPTY 渲染（评审第十四轮产物四）：零规则事项的用户可见提示——
    # "事项声明支持"与"规则实际覆盖"的差额不能只躺在 coverage_gaps.yaml 里
    if registry is not None and sum(res.rules_evaluated for res in ev.per_school.values()) == 0:
        lines.append(
            "> ⚠️ **该事项暂无规则覆盖**（GAP-TASKKIND-EMPTY）：引擎对本次事项未评估任何规则，"
            "下述结论为空集结论，**不得解读为「无禁忌」**。"
        )
        lines.append("")
    # ADR-0014 决策 0：甲案的用户可见后果——tier 与 publishable 必须联合显示，不得分置
    if ev.vectors.get("controversial_count"):
        lines.append(
            "> ⚠️ **存疑命中提示**：有争议规则命中 = 暂不采信 —— tier 不变、"
            "publishable 兜底、不参与否决；明细见「存疑命中」节（ADR-0014 决策 0）。"
        )
        lines.append("")
    # ADR-0014 决策 1：声明/生效双显示（审计链）
    cap_ids = ev.vectors.get("cap_applied_ids") or []
    if cap_ids:
        lines.append(
            f"- 声明/生效严重度差异（ADR-0014 上限，考证签名后自动恢复）：{', '.join(f'`{i}`' for i in cap_ids)}"
        )
        lines.append("")
    if ev.publishable:
        lines.append(
            "> ℹ️ **「可发布」= 安全底线语义**：该事项的必需规则集已全部可判定，"
            "系统不会漏判这些规则覆盖的风险。"
            "它**不表示**规则集完备、也不表示该日期可用 —— "
            "未列入必需集的断言级规则仍可能命中（见「演示命中」），"
            "亦可能存在尚未建模的风险（如大煞、月五黄）。"
        )
        lines.append("")

    # 存疑原因分解（评审要求：否则「存疑」是黑箱）
    if ev.state == "存疑":
        lines.append(
            "存疑原因分解：强忌 {} ｜ 冲突 {} ｜ 未知 {}".format(
                ev.vectors.get("assertion_caution_count", 0),
                ev.vectors.get("conflict_count", 0),
                ev.vectors.get("unknown_count", 0),
            )
        )
        lines.append("")

    if not ev.publishable:
        blockers: list[str] = []
        if ev.required_rule_ids:
            rb = ev.required_blockers
            if rb:
                blockers.append(
                    f"必需集内 {len(rb)} 条规则尚不可判定（"
                    + "、".join(f"`{b['rule_id']}`" for b in rb[:4])
                    + ("…" if len(rb) > 4 else "")
                    + "）"
                )
        else:
            if ev.vectors.get("unverified_hit_count", 0):
                blockers.append(f"依赖 {ev.vectors['unverified_hit_count']} 条未考证规则")
            if ev.vectors.get("disputed_count", 0):
                blockers.append(f"{ev.vectors['disputed_count']} 条口径有争议")
        if ev.vectors.get("conflict_count", 0):
            blockers.append(f"{ev.vectors['conflict_count']} 处派别/规则冲突")
        if ev.tier in ("REJECTED", "NEEDS_REVIEW"):
            blockers.append(f"等级为 {ev.tier}")
        lines.append(
            "> ⚠️ **本次结论不可对外发布**：" + "；".join(blockers) + "。"
            "详见下方「未知」与「冲突」两节。"
        )
        lines.append("")
        # ADR-0014 决策 5：未激活状态合并说明（两个"未激活"不得让用户自己拼因果）
        verified_total: int | None = None
        verified_required: int | None = None
        if registry is not None:
            verified_total = sum(
                1 for r in registry.ruleset.rules if r.status == "已考证"
            )
            verified_required = sum(
                1
                for rid in ev.required_rule_ids
                if registry.ruleset.by_id.get(rid) is not None
                and registry.ruleset.by_id[rid].status in ("已考证", "定义级")
            )
        lines.append("**当前状态（未激活项合并说明）**：")
        lines.append("")
        lines.append(
            f"- 可发布=否：必需集 {len(ev.required_rule_ids)} 条中 "
            f"{verified_required if verified_required is not None else '?'} 条已考证（阻塞项见下表）"
        )
        if verified_total == 0:
            lines.append(
                "- strict 档未激活：已考证规则 0 条，从严能力待 P0 考证完成后生效"
                "（当前 strict 与 normal 在否决力上等价）"
            )
        lines.append(
            "- 共同原因：P0 考证未完成；补完必需集原文并签名后，publishable 与 strict 同时解锁"
        )
        lines.append("")

    # 必需集：还差什么才能发布（把报告变成操作指南）
    if ev.required_rule_ids:
        rb = ev.required_blockers
        lines.append(
            f"必需规则集（{task['kind']}）：共 {len(ev.required_rule_ids)} 条，"
            f"已可判定 {len(ev.required_rule_ids) - len(rb)} 条"
        )
        if rb:
            lines.append("")
            lines.append("| 尚未可判定的必需规则 | 状态 | 原因 |")
            lines.append("|---|---|---|")
            for b in rb:
                lines.append(f"| `{b['rule_id']}` | {b['status']} | {b['reason']} |")
        lines.append("")
    v = ev.vectors
    lines.append(
        f"分层向量：硬伤 {v['hard_fail_count']} ｜ 强忌 {v['strong_avoid_count']} ｜ "
        f"冲突 {v['conflict_count']} ｜ 未知 {v['unknown_count']} ｜ 提示 {v.get('note_count', 0)} ｜ "
        f"正向 {v['positive_count']}"
    )
    lines.append("")
    lines.append(f"派别分歧度：{result.disagreement:.3f}（0 = 各派一致；**非吉凶概率**）")
    lines.append("")

    lines.append("## 结构检测（独立于吉凶规则）")
    lines.append("")
    st = result.structure
    lines.append(f"- 地支计数：{json.dumps(st.zhi_counts(), ensure_ascii=False)}")
    lines.append(f"- 最大重复：{st.max_repeat} 见（**重复不等于伏吟，伏吟是否成立由流派规则解释**）")
    lines.append(f"- 自刑：{'是' if st.has_self_punishment else '否'}（仅辰辰/午午/酉酉/亥亥；**未未不是自刑**）")
    if st.hits:
        lines.append("")
        lines.append("| 结构 | 说明 |")
        lines.append("|---|---|")
        for h in st.hits:
            lines.append(f"| {h.kind} | {h.detail} |")
    lines.append("")

    lines.append("## 结构判定（定义级，已确定）")
    lines.append("")
    lines.append(
        "> 下列结论来自干支系统的算术推论（`citation.kind: spec`），"
        "**只是结构事实，不含吉凶判断**；它们已确定成立，不参与 unknown。"
    )
    lines.append(">")
    lines.append(
        "> ⚠️ **结构确定 ≠ 结论确定**：这些结构「意味着什么」（吉/凶/宜/忌）属于断言级规则，"
        "当前全部为 `待考证`，见下方「派别判定明细」。"
        "本节不得被解读为「这个日子有问题/没问题」。"
    )
    lines.append("")
    if ev.structural:
        lines.append("| 规则 | 类别 | 严重度 | 规格条款 |")
        lines.append("|---|---|---|---|")
        for j in ev.structural:
            clause = (j.citation.get("quote") or "—")
            if len(clause) > 60:
                clause = clause[:58] + "…"
            lines.append(f"| `{j.rule_id}` | {j.category} | {j.severity} | {clause} |")
        lines.append("")
        for j in ev.structural:
            lines.append(f"- `{j.rule_id}`：{j.hit_detail}")
        lines.append("")
    else:
        lines.append("- 无结构判定命中。")
        lines.append("")

    lines.append("## 派别判定明细（并列，不合并分数）")
    lines.append("")
    for res in ev.per_school.values():
        lines.extend(_school_block(res))
        lines.append("")

    lines.append("## 派别冲突")
    lines.append("")
    if ev.conflicts:
        for c in ev.conflicts:
            lines.append(f"- **{c['type']}**：{c.get('detail', '')}")
            if "states" in c:
                lines.append(f"  - 各派三态：{json.dumps(c['states'], ensure_ascii=False)}")
            if "severities" in c:
                lines.append(f"  - 各派严重度：{json.dumps(c['severities'], ensure_ascii=False)}")
    else:
        lines.append("- 本候选未检测到派别冲突。")
    lines.append("")

    lines.append("## 未知与证据缺口（按原因分类）")
    lines.append("")
    by_reason = ev.vectors.get("unknown_by_reason", {})
    if by_reason:
        lines.append(
            "统计：缺输入 {} ｜ 口径未定 {} ｜ 规则未考证 {}".format(
                by_reason.get("missing_input", 0),
                by_reason.get("caliber_undecided", 0),
                by_reason.get("unverified_rule", 0),
            )
        )
        lines.append("")
    if ev.unknowns:
        lines.append("| 规则 | 派别 | 原因分类 | 解除条件 |")
        lines.append("|---|---|---|---|")
        for u in ev.unknowns:
            lines.append(
                f"| `{u['rule_id']}` | {u['school']} | {_reason_label(u.get('unknown_reason'))} | "
                f"{u.get('remedy') or '—'} |"
            )
    else:
        lines.append("- 无。")
    lines.append("")

    lines.append("## 约定回显（四柱是在什么约定下算出来的）")
    lines.append("")
    time_ctx = ctx.get("time", {})
    lines.append("| 约定 | 本次取值 | 含义 |")
    lines.append("|---|---|---|")
    lines.append(
        f"| 年/月柱时间基准 | `{time_ctx.get('ym_time_ref', 'auto')}` | "
        "决定「交节时刻与哪个时间比较」 |"
    )
    lines.append(
        f"| 日/时柱时间基准 | `{time_ctx.get('hour_time_ref', 'auto')}` | "
        "决定「换日边界与时辰归属用哪个时间」 |"
    )
    lines.append(
        f"| 日界规则 | `{time_ctx.get('day_boundary')}` | "
        f"{'子初 23:00 换日' if time_ctx.get('day_boundary') == 'early' else '子正 00:00 换日'} |"
    )
    lines.append(
        f"| 真太阳时总开关 | `{time_ctx.get('use_true_solar_time')}` | "
        "`auto` 跟随此开关 |"
    )
    lines.append("")
    lines.append(
        f"本次四柱：**{course['bazi']}**（时柱参考时刻 `{ctx.get('time', {}).get('datetime')}`）"
    )
    lines.append("")

    lines.append("## 口径回显（争议项取值）")
    lines.append("")
    caliber_info = ctx.get("_meta", {}).get("calibers") or {}
    selection = caliber_info.get("selection") or {}
    if selection:
        lines.append("| 口径组 | 本次取值 | 说明 |")
        lines.append("|---|---|---|")
        for set_name, chosen in selection.items():
            spec = (caliber_info.get("sets", {}).get(set_name, {}).get("calibers", {}) or {}).get(chosen, {})
            lines.append(
                f"| {set_name} | `{chosen}` | {spec.get('status', '—')}：{spec.get('description', '')} |"
            )
        lines.append("")
        # 对比式提示：未裁定口径列出全部备选
        for set_name, chosen in selection.items():
            set_info = caliber_info.get("sets", {}).get(set_name, {})
            calibers = set_info.get("calibers", {})
            undecided = [n for n, sp in calibers.items() if sp.get("status") != "已考证"]
            if undecided:
                lines.append(f"- **{set_name}** 尚未裁定，可选口径：" + "、".join(
                    f"`{n}`（{calibers[n]['status']}）" for n in undecided
                ))
                for n in undecided:
                    req = calibers[n].get("requires") or []
                    if req:
                        lines.append(f"  - `{n}` 需要：{'；'.join(req)}")
        lines.append("")

    lines.extend(render_manifest_block(ev.manifest, ctx.get("_meta", {}).get("calendar_config")))
    lines.append("---")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append(f"_生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}_")
    return "\n".join(lines)


def render_generation_markdown(result: GenResult, *, registry: RuleRegistry | None = None) -> str:
    """渲染候选生成报告。"""
    lines: list[str] = []
    lines.append("# 择日候选生成报告")
    lines.append("")
    if result.no_solution_reason == "no_conclusion_pending_verification":
        lines.append(
            "> ⚠️ **本次无结论（非无解）**：候选未触发否决层，但依赖未考证规则或未定口径。"
            "补齐规则考证后重跑即可；**不得**把本结果当作「该窗口无可用日」。"
        )
        lines.append("")
    elif result.no_solution_reason == "all_rejected":
        lines.append(
            "> ⚠️ **本窗口全部候选被否决层排除**（真无解）。"
            "系统不会放宽硬约束来凑答案；如需放宽请显式 `--relax` 并保留本说明。"
        )
        lines.append("")
    elif result.no_solution_reason == "constraints_conflict":
        lines.append("> ⚠️ **约束互斥**：时间窗与每日时段/排除条件无交集，请检查输入。")
        lines.append("")
    lines.append(f"- 候选总数：{result.total_candidates}")
    lines.append(f"- 分层分布：{json.dumps(result.tier_histogram, ensure_ascii=False)}")
    lines.append(f"- 未触发否决层（state=可用）：{len(result.usable)} 个")
    lines.append(f"- 其中 tier 达 ACCEPTABLE/PREFERRED（可发布）：{len(result.publishable)} 个")
    lines.append(f"- Pareto 前沿规模：{result.pareto_size}")
    lines.append(f"- 全窗口派别分歧度：{result.disagreement:.3f}（**非吉凶概率**）")
    if result.relaxed:
        lines.append("")
        lines.append("> ⚠️ **本次结果使用了 --relax 放宽硬约束，不得作为正式结论发布。**")
    lines.append("")

    if result.no_solution:
        ns = result.no_solution
        lines.append("## 无解说明")
        lines.append("")
        lines.append(f"{ns.message}")
        lines.append("")
        lines.append(f"- 候选总数 {ns.total_candidates}，其中被否决 {ns.rejected}")
        lines.append("")
        lines.append("**被否决原因直方图（Top 15）**")
        lines.append("")
        lines.append("| 规则 | 命中次数 |")
        lines.append("|---|---|")
        for reason, count in list(ns.veto_reasons.items())[:15]:
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    lines.append("## 候选清单（分层排序，非单一总分）")
    lines.append("")
    lines.append("| # | 候选 | 三态 | 等级 | 硬伤 | 强忌 | 冲突 | 未知 | 正向 | 四柱 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(result.ranked, 1):
        ev = r.evaluation
        v = ev.vectors
        bazi = r.context["course"]["bazi"]
        lines.append(
            f"| {i} | {ev.candidate} | {ev.state} | {ev.tier} | {v['hard_fail_count']} | "
            f"{v['strong_avoid_count']} | {v['conflict_count']} | {v['unknown_count']} | "
            f"{v['positive_count']} | {bazi} |"
        )
    lines.append("")

    if result.robustness is not None:
        rb = result.robustness
        lines.append("## 稳健集 / 敏感集（扰动矩阵）")
        lines.append("")
        lines.append(f"- 扰动集：{'、'.join(rb.perturbations)}")
        lines.append(f"- 坐向误差半径：±{rb.radius_deg:g}°")
        lines.append(f"- 稳健集：{len(rb.robust)} 个　敏感集：{len(rb.sensitive)} 个")
        lines.append(f"- 稳定比例：{rb.stable_ratio:.0%}")
        lines.append("")
        if rb.robust:
            lines.append("**稳健集（所有扰动下 state 不变，可作推荐主体）**")
            lines.append("")
            for c in rb.robust[:20]:
                lines.append(f"- {c}")
            lines.append("")
        if rb.sensitive:
            lines.append("**敏感集（任一扰动下翻转，须单独复核）**")
            lines.append("")
            lines.append("| 候选 | 原结论 | 触发扰动 | 新结论 |")
            lines.append("|---|---|---|---|")
            for item in rb.sensitive[:20]:
                for f in item["flips"]:
                    lines.append(
                        f"| {item['candidate']} | {f['from']} | {f['perturbation']} | {f['to']} |"
                    )
            lines.append("")
        if rb.errors:
            lines.append(f"- 扰动执行错误：{json.dumps(rb.errors, ensure_ascii=False)}")
            lines.append("")

    if result.sensitivity is not None:
        lines.append("## 敏感性分析（口径一改是否翻转）")
        lines.append("")
        sens = result.sensitivity
        lines.append(f"- 结论稳定性：{'稳定' if sens.is_stable else '存在翻转'}")
        if sens.flips:
            lines.append("")
            lines.append("| 候选 | 扰动 | 原结论 | 新结论 |")
            lines.append("|---|---|---|---|")
            for f in sens.flips[:20]:
                lines.append(
                    f"| {f.candidate} | {f.perturbation} | {f.from_state}/{f.from_tier} | "
                    f"{f.to_state}/{f.to_tier} |"
                )
        if sens.errors:
            lines.append("")
            lines.append(f"- 重算错误：{json.dumps(sens.errors, ensure_ascii=False)}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"> {DISCLAIMER}")
    lines.append("")
    lines.append(f"_生成时间：{datetime.now().astimezone().isoformat(timespec='seconds')}_")
    return "\n".join(lines)


def render_json(result: VerifyResult | GenResult) -> str:
    return json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
