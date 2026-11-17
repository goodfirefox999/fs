"""报告编排（应用层）：JSON 为事实源，Markdown 为人类可读视图。

硬性要求
--------
1. 每个结论必须带 ``rule_id`` 与出处（无引文时显式标"原文待补"）；
2. 报告页脚固定免责声明，且**不得**出现"准确率""灵验度""吉凶概率"等表述；
3. 必须回显全部争议口径（附录 B）与 manifest（可复现清单）；
4. 冲突与未知必须单独成节，不得折叠进结论。
"""

from __future__ import annotations

import functools
import json
import re
from datetime import datetime
from typing import Any

from core_eval import (
    BLOCK_EVIDENCE_INSUFFICIENT,
    BLOCK_INPUT_INSUFFICIENT,
    BLOCK_PENDING_RULING,
    BLOCK_PENDING_VERIFICATION,
    Evaluation,
    SchoolResult,
)
from core_eval.engine import LITERATURE_NOTE_BY_SCHOOL, LITERATURE_STATUS_BY_SCHOOL
from core_rule.registry import RuleRegistry

from .generator import GenResult
from .verifier import VerifyResult

__all__ = [
    "DISCLAIMER",
    "render_markdown",
    "render_generation_markdown",
    "render_json",
    "render_manifest_block",
    "ephemeris_notice",
    "undetermined_notice",
    "zero_voter_notice",
    "consensus_notice",
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
    pian = citation.get("pian")
    if quote:
        parts = []
        if juan:
            parts.append(f"卷{juan}")
        if pian:
            parts.append(f"篇{pian}")
        loc = "·".join(parts) if parts else "卷次待补"
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


def _hit_ledger(ev: Evaluation) -> list[str]:
    """命中规则宜忌台账（事实层）。

    只回答「命中了什么、规则怎么声明、这条能不能用、证据到什么程度」，
    **不做等第比较、不给综合宜忌**（Q-030 未实现）。
    """
    grade_labels = {
        "A": "A（一手影印）",
        "B": "B（二手转述）",
        "C": "C（出处待定位）",
        "definitional": "定义级（规格）",
        "unrecorded": "未登记",
    }
    source_labels = {
        "verified": "已考证",
        "definitional": "定义级",
        "controversial": "有争议",
        "unverified": "待考证",
    }
    rows: list[tuple[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for school, res in ev.per_school.items():
        for j in (
            *res.vetoes,
            *res.cautions,
            *res.positives,
            *res.structural,
            *res.notes,
            *res.controversial,
            *res.demo_hits,
            *res.reference,
        ):
            key = (school, j.rule_id)
            if key in seen:
                continue
            seen.add(key)
            rows.append((school, j))
    if not rows:
        return ["- 本轮无命中规则。"]

    lines = [
        "| 派别 | 规则 | 类别 | 声明宜忌 | 参与状态 | 证据等级 | 原文状态 |",
        "|---|---|---|---|---|---|---|",
    ]
    for school, j in rows:
        severity = j.severity
        if j.declared_severity and j.declared_severity != j.severity:
            severity = f"{j.declared_severity}→{j.severity}"
        grade = grade_labels.get(j.evidence_grade_label, j.evidence_grade_label)
        source = source_labels.get(j.source_status or "", "—")
        lines.append(
            f"| `{school}` | `{j.rule_id}` | {j.category} | {severity} | "
            f"{j.participation} | {grade} | {source} |"
        )
    lines.append("")
    lines.append(
        "> 本表登记本次命中的全部规则（含神煞、结构与断言规则），只陈述其声明口径："
        "**不比较轻重、不输出综合宜忌；Q-030 等第仲裁未实现**。"
        "「A（一手影印）」只表示存在一手影印线索，不等于已签名；B/C 均未达投票门槛。"
    )
    return lines


def _school_block(res: SchoolResult) -> list[str]:
    lines: list[str] = []
    c = res.counts
    lines.append(f"### 派别：{res.school}")
    lines.append("")
    lines.append(f"- 三态结论：**{res.state}**")
    lines.append(
        f"- 分层计数：硬伤 {c['hard_fail_count']} / 强忌 {c['strong_avoid_count']} / "
        f"提示 {c['note_count']} / 正向 {c['positive_count']} / 未知 {c['unknown_count']} / "
        f"参考 {c.get('reference_count', 0)} / 不适用 {c.get('not_applicable_count', 0)}"
    )
    lines.append(f"- 评估规则数：{res.rules_evaluated}")
    _lit = LITERATURE_STATUS_BY_SCHOOL.get(res.school)
    if _lit:
        lines.append(
            f"- **文献状态：`{_lit}`**——{LITERATURE_NOTE_BY_SCHOOL[res.school]}"
        )
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

    # C 第一批：参考层命中（engine_eligible=false）——评估了、也渲染，但**不进任何强度桶**
    if res.reference:
        lines.append(
            "**参考层（`engine_eligible=false`：口径未裁定/无原典支撑，"
            "**不进否决、不计分、不影响 tier**）**"
        )
        lines.append("")
        lines.extend(_judgment_rows(res.reference))
        lines.append("")
        for j in res.reference:
            reason = j.ineligible_reason or "未注明"
            lines.append(f"- `{j.rule_id}`（{reason}）：{j.hit_detail}")
        lines.append("")

    # 「不适用」：规则声明本类输入管不到——不是未知，不阻塞发布
    if res.not_applicable:
        lines.append(
            "**不适用（规则声明本类输入不在适用范围内；"
            "不计未知、不影响 tier、不阻塞可发布）**"
        )
        lines.append("")
        for j in res.not_applicable:
            lines.append(f"- `{j.rule_id}`：{j.remedy or '规则已声明本类输入不适用'}")
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


def _cosmos_block(facts: dict[str, Any]) -> list[str]:
    """盘面事实（值宿/紫白/吉神）。**只陈述事实，不下吉凶判断。**

    为什么单独成节：这些量在「无规则命中」时也应当可见（用户查黄历首先看值宿与
    紫白入中），但它们本身不是结论；把结论与盘面混在一张表里，等于用事实的确定性
    给未考证的断言背书。
    """
    lines: list[str] = []
    missing = lambda v: "—" if v is None else v  # noqa: E731

    xiu = facts.get("xiu") or {}
    if xiu.get("day"):
        check = "通过" if xiu.get("weekday_consistent") else "**不通过（表疑有误）**"
        lines.append(
            f"- 值日星宿：**{xiu.get('full_name')}**（七政 {xiu.get('qizheng')}，第 {xiu.get('yuan')} 元；"
            f"星期恒等式校验：{check}）"
        )
    else:
        lines.append("- 值日星宿：—（缺用事日）")

    zb = facts.get("zibai") or {}
    centers = []
    for label, key in (("年", "year"), ("月", "month"), ("日", "day"), ("时", "hour")):
        plate = zb.get(key) or {}
        centers.append(f"{label} {missing(plate.get('center'))}")
    fly = (zb.get("caliber") or {}).get("fly", "—")
    lines.append(f"- 紫白入中：{' ｜ '.join(centers)}（日/时盘飞布口径：`{fly}`）")

    hits = []
    for label, key in (("年", "year"), ("月", "month"), ("日", "day"), ("时", "hour")):
        plate = zb.get(key) or {}
        hits.append(f"{label} {'是' if plate.get('wuhuang_hit_palace') else '否'}")
    # 粒度必须写进文案：紫白五黄到山是**宫级**（一宫三山同受），不是「只算宫心那一山」。
    # 历史上该字段名为 wuhuang_hit_mountain 而实现是宫级，文案照抄山名 → 名实不符（Q-018）。
    lines.append(f"- 五黄到坐山（宫级，一宫三山同受）：{' ｜ '.join(hits)}")

    js = facts.get("jishen") or {}
    td = js.get("tian_de") or {}
    yd = js.get("yue_de") or {}
    ts = js.get("tian_she") or {}
    if td:
        kind = "干" if td.get("kind") == "gan" else "卦宫"
        lines.append(
            f"- 天德：本月在 **{missing(td.get('target'))}**（{kind}）→ 今日"
            f"{'值' if td.get('hit') else '不值'}"
            + (f"（卦位口径 `{td.get('caliber')}`，备选见口径回显）" if td.get("kind") == "gong" else "")
        )
    if yd:
        lines.append(
            f"- 月德：**{missing(yd.get('gan'))}** → 今日{'值' if yd.get('hit') else '不值'}；"
            f"月德合 **{missing(yd.get('he_gan'))}** → 今日{'值' if yd.get('he_hit') else '不值'}"
        )
    if ts:
        lines.append(
            f"- 天赦：{missing(ts.get('season'))}季 **{missing(ts.get('day_ganzhi'))}** 日 → 今日"
            f"{'值' if ts.get('hit') else '不值'}"
        )
    lines.append("")
    lines.append(
        "> 本节每条都是**事实或算术**（值何宿、何星入中、本月德在何干），不含吉凶。"
        "「值德是否即吉」「凶宿是否即忌」属断言级规则，见下方派别判定明细；"
        "结构/盘面确定 ≠ 结论确定。"
    )
    return lines


def _consensus_block(fso: dict[str, Any]) -> list[str]:
    """共识度渲染：只给整数比与名单，**不给浮点分值**（ADR-0015）。

    「几成派别同向」是描述统计，不是吉凶概率；分母是**实际表态的派数**，
    闸门层/参考层/沉默派一律列在未投票名单里并写明原因。
    """
    detail = fso.get("_consensus_detail")
    if not isinstance(detail, dict):
        return ["- 本次评估未产出共识明细（旧版快照或单派评估）。"]
    threshold = detail.get("threshold") or {}
    num = threshold.get("min_agree_num", "?")
    den = threshold.get("min_agree_den", "?")
    ratio = detail.get("consensus_ratio", "0/0")
    votes = detail.get("votes") or {}
    favorable = votes.get("favorable") or []
    unfavorable = votes.get("unfavorable") or []
    voters = detail.get("voters") or []
    voter_grades = detail.get("voter_evidence_grades") or {}
    non_voters = detail.get("non_voters") or []
    gate_veto = detail.get("gate_veto_schools") or []
    undetermined = detail.get("undetermined") or {}

    lines = [
        f"**{ratio} 同向**（阈值 {num}/{den}，事项：{detail.get('task_kind') or '未指定'}）",
        "",
        f"- 结论态：`{detail.get('consensus')}`",
        f"- 参与投票（{len(voters)} 派）：{'、'.join(voters) if voters else '无'}",
        f"- 同向：{'、'.join(favorable) if favorable else '无'}",
        f"- 反对：{'、'.join(unfavorable) if unfavorable else '无'}",
    ]
    if voters:
        grade_text = "、".join(
            f"`{name}`={'/'.join(voter_grades.get(name) or ['unrecorded'])}" for name in voters
        )
        lines.append(f"- 投票证据等级：{grade_text}")
    if gate_veto:
        # 闸门否决会与"全票同向"同时出现（否决不参与计票），必须当场说清谁说了算，
        # 否则读者会看到"4/4 同向却是不可用"而以为程序自相矛盾。
        lines.insert(
            2,
            f"- **闸门否决（{'、'.join(gate_veto)}，不计票，直接否决）**：本候选不可用；"
            "下列比值仅记录投票派内部倾向，不构成可用性依据",
        )
    if non_voters:
        lines.append("- 未投票：")
        for nv in non_voters:
            reason_text = nv.get("detail") or _non_voter_reason(nv.get("reason"))
            lines.append(
                f"  - `{nv.get('school')}`（{nv.get('layer')}）：{reason_text}"
            )
    else:
        lines.append("- 未投票：无（全部派别均已表态）")
    undetermined_count = undetermined.get("undetermined_required_count", 0)
    if undetermined_count:
        kinds = "、".join(
            f"{undetermined.get(key, 0)} 条{label}"
            for key, label in (
                ("evidence_insufficient_count", "证据不足"),
                ("pending_ruling_count", "待裁定"),
                ("pending_verification_count", "待签名"),
                ("input_insufficient_count", "输入不足"),
                ("not_applicable_count", "不适用"),
            )
            if undetermined.get(key, 0)
        )
        lines.append(
            f"- 未判定：{undetermined_count} 条必需规则（{kinds or '原因见清单'}）；"
            "共识比只反映已判定规则"
        )
        for item in undetermined.get("rules") or []:
            lines.append(f"  - `{item.get('rule_id')}`（{item.get('kind')}）：{item.get('reason')}")
    lines.append("")
    lines.append(
        "> 该比值是「几成派别同向」的描述统计，**不是吉凶概率**；"
        "分母只数实际表态的派，沉默派与闸门/参考层不进分母。"
    )
    return lines


# C19-exempt：零参数缓存（键恒为 ()，无复合可变参数风险）；纯静态映射，
# 规则文件在进程生命周期内视为不变（与 load_ruleset 同一假设）。
@functools.lru_cache(maxsize=1)
def _rule_id_to_path() -> dict[str, str]:
    """rule_id → 规则文件相对路径（一次扫描缓存）。供「未归类」节展示归属。"""
    from pathlib import Path as _P

    # report.py 位于 <repo>/app-zeri/src/app_zeri/：parents[0]=app_zeri,
    # [1]=src, [2]=app-zeri, [3]=仓库根（src layout 多一层，别数错）
    root = _P(__file__).resolve().parents[3] / "core-rule" / "rules"
    if not root.exists():  # 打包/异构布局时静默降级为无路径
        return {}
    mapping: dict[str, str] = {}
    for yml in root.rglob("*.yaml"):
        try:
            text = yml.read_text(encoding="utf-8")
        except OSError:
            continue
        m = re.search(r"^rule_id:\s*([\w-]+)", text, flags=re.M)
        if m:
            mapping.setdefault(m.group(1), str(yml.relative_to(root.parents[1])))
    return mapping


def zero_voter_notice(ev: Evaluation) -> list[str]:
    """共识比无意义时的**强制提示**。

    当 ``voters`` 为空或只有演示票时，:func:`render_markdown` 会把结论标题本身
    改成「无参与投票的已判定规则」，本函数随后只补闸门否决等细节；独立调用
    （测试、其他渲染入口）时仍返回完整的「不构成结论」主提示。

    为什么不能只在分节里说明
    ------------------------
    全仓 0 条已考证规则，生产路径的命中全进 ``demo_hits``，于是投票派可能一个都没有
    （0/0）。这不是 bug，是**内容未考证**的真实状态。但它有个恶性读法：
    读者看到"4/4 同向"会以为四派都同意，而真实情况可能是"四派都没表态，且闸门已否决"。

    故此处只做一件事：把"本次没有已考证规则投票"这句话放在结论紧后面，
    先说不构成结论，再说比值为多少、谁否决的。
    """
    detail = (ev.manifest.get("five_school_output") or {}).get("_consensus_detail") or {}
    voters = detail.get("voters") or []
    ratio = detail.get("consensus_ratio") or "0/0"
    gate_veto = detail.get("gate_veto_schools") or []

    # 投票派非空也可能全是"演示命中"：必须先排除，否则会误报"有票"。
    verified_votes = sum(
        1
        for res in ev.per_school.values()
        for j in (*res.vetoes, *res.cautions, *res.positives)
        if j.participation == "判定"
    )
    if voters and verified_votes:
        return []

    lines = ["", "> ⛔ **无参与投票的已判定规则，以下仅为参考层展示**"
             f"（当前共识比 {ratio}，不构成择日结论）。"]
    if gate_veto:
        lines.append(
            f"> ⛔ 本候选被闸门否决（{'、'.join(gate_veto)}），投票派 0 派参与，比值无意义。"
        )
    return lines


def consensus_notice(ev: Evaluation) -> list[str]:
    """主结论区的共识摘要：投票派、每派证据等级、相反意见与文献正当性。

    0/0 无票场景由 :func:`zero_voter_notice` 负责，本函数不重复；这里只在
    **确有票**时出现，避免把"没票"说成"有共识"。
    """
    detail = (ev.manifest.get("five_school_output") or {}).get("_consensus_detail") or {}
    voters = detail.get("voters") or []
    if not voters:
        return []
    ratio = detail.get("consensus_ratio") or "0/0"
    grades = detail.get("voter_evidence_grades") or {}
    grade_text = "、".join(
        f"`{name}`={'/'.join(grades.get(name) or ['unrecorded'])}" for name in voters
    )
    lines = [
        "",
        f"> 🗳️ **共识 {ratio}**：参与投票 {len(voters)} 派（{'、'.join(voters)}）；"
        f"证据等级：{grade_text}。",
    ]
    for conflict in detail.get("conflicts") or []:
        if conflict.get("type") != "OPPOSITE_VERDICT":
            continue
        between = " vs ".join(conflict.get("between") or [])
        lines.append(
            f"> ⚠️ **门派意见相反（OPPOSITE_VERDICT）**：{between}；"
            "需人工复核，系统不自动裁决。"
        )
    for name in voters:
        status = LITERATURE_STATUS_BY_SCHOOL.get(name)
        if status == "disputed_by_xieji":
            lines.append(
                "> ⚠️ **文献正当性提示**：斗首结果仅作参考，"
                "协纪辨方书卷三十六·辨讹质疑其出处，不构成 A 级证据。"
            )
        elif status == "primary_source_missing":
            lines.append(
                "> ⚠️ **原典缺失提示**：玄空大卦缺一手影印原典"
                "（primary_source_missing），结果仅作参考，不构成 A 级证据。"
            )
    return lines


def undetermined_notice(ev: Evaluation) -> list[str]:
    """主结论的未判定计数（第四层）。

    共识比的分母只含已判定规则；不给这句话，读者会把"N 条必需规则没判"
    读成"N 条都判过且通过"。计数直接取自 engine 的 ``required_blockers`` /
    ``required_not_applicable``，报告不另算一套。
    """
    if not ev.required_rule_ids:
        return []
    blockers = ev.required_blockers
    not_applicable = ev.required_not_applicable
    if not blockers and not not_applicable:
        return []
    kinds = {
        kind: sum(1 for b in blockers if b.get("kind") == kind)
        for kind in (
            BLOCK_EVIDENCE_INSUFFICIENT,
            BLOCK_PENDING_RULING,
            BLOCK_PENDING_VERIFICATION,
            BLOCK_INPUT_INSUFFICIENT,
        )
    }
    extras = [
        f"{kinds[kind]} 条{label}"
        for kind, label in (
            (BLOCK_PENDING_RULING, "待裁定"),
            (BLOCK_PENDING_VERIFICATION, "待签名"),
            (BLOCK_INPUT_INSUFFICIENT, "输入不足"),
        )
        if kinds[kind]
    ]
    total = len(blockers) + len(not_applicable)
    text = (
        f"> ℹ️ **本次评估中 {total} 条必需规则未判定"
        f"（{kinds[BLOCK_EVIDENCE_INSUFFICIENT]} 条证据不足，"
        f"{len(not_applicable)} 条不适用"
    )
    if extras:
        text += "；另有 " + "、".join(extras)
    text += "），共识比仅反映已判定规则。**"
    return ["", text]


def ephemeris_notice(ev: Evaluation) -> list[str]:
    """星历降级且落在节气交界窗口时的强制提示（第五层）。

    manifest 已全字段透传；但 JSON 在报告末尾，读者常先看结论。此提示只
    在 ``second_precision_required=True`` 时出现——此时月柱可能翻转，所有
    非定义级命中已被引擎降为「证据不足」，结论不得作为发布依据。
    """
    ephem = ev.manifest.get("ephemeris") or {}
    if not ephem.get("second_precision_required"):
        return []
    nearest = ephem.get("nearest_jie") or "节气交界"
    distance = ephem.get("distance_to_jie_s")
    dist_text = f"仅 {distance:.1f} 秒" if isinstance(distance, (int, float)) else "秒级窗口内"
    backend = ephem.get("backend") or "未知"
    return [
        "",
        f"> ⚠️ **星历精度：本次使用降级星历（{backend}），候选距「{nearest}」{dist_text}，"
        "月柱可能翻转；命中的断言已按「证据不足」处理，本报告不得作为发布依据。**",
    ]


def _non_voter_reason(reason: str | None) -> str:
    return {
        "layer_reject": "闸门层，只否决不计票",
        "layer_reference": "参考层，不参与仲裁",
        "no_verdict": "本轮无判定（沉默派，不进分母）",
        "demo_only_not_voting": "仅有未考证规则的演示命中，不作为票（有判断、无票权）",
    }.get(reason or "", reason or "未说明")


def _reason_label(reason: str | None) -> str:
    return {
        "missing_input": "缺输入",
        "caliber_undecided": "口径未定",
        "unverified_rule": "规则未考证",
        "not_applicable": "不适用（不计未知）",
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

    zero_lines = zero_voter_notice(ev)
    if zero_lines:
        # 0/0 或仅有演示命中时，结论标题本身不得写成「可用」——那会让读者先看到
        # 一个没有票支撑的结论，再去看下面的免责声明。首行必须是「无参与投票」。
        detail = (ev.manifest.get("five_school_output") or {}).get("_consensus_detail") or {}
        ratio = detail.get("consensus_ratio") or "0/0"
        lines.append(
            f"## 结论：**无参与投票的已判定规则**（当前共识比 {ratio}，"
            f"以下仅为参考层展示，不构成择日结论）"
            f"　推荐等级：**{ev.tier}**　可发布：**{'是' if ev.publishable else '否'}**"
        )
        lines.append("")
        lines.append(f"> 系统状态（非择日结论）：{verdict_label}")
        lines.extend(zero_lines[2:])
    else:
        lines.append(
            f"## 结论：{verdict_label}　推荐等级：**{ev.tier}**　"
            f"可发布：**{'是' if ev.publishable else '否'}**"
        )
    # 第四层：主结论必须写明未判定计数，否则"没判"会被读成"判了且通过"
    lines.extend(undetermined_notice(ev))
    # 第六层：有票时显示投票派/证据等级/相反意见；无票仍由零票提示先说明
    lines.extend(consensus_notice(ev))
    # 第五层：降级星历落在节气交界窗口时，结论不可发布（manifest 里也有全字段）
    lines.extend(ephemeris_notice(ev))
    lines.append("")
    # GAP-TASKKIND-EMPTY 渲染（评审第十四轮产物四）：无事项专属规则的用户可见提示——
    # 通用规则（task_kinds:[]）恒覆盖一切事项，故判据是"显式含本事项的专属规则数==0"
    # 而非 rules_evaluated==0（初版判据在开业上 22 条通用规则前失效，已修正）
    if registry is not None:
        kind = task.get("kind", "")
        specific = sum(
            1 for r in registry.ruleset.rules
            if r.status != "弃用" and kind in r.applies_to.task_kinds
        )
        if specific == 0:
            n_universal = sum(res.rules_evaluated for res in ev.per_school.values())
            lines.append(
                f"> ℹ️ **事项「{kind}」无专属规则**（GAP-TASKKIND-EMPTY，产品级信息非缺陷）：本次评估"
                f"仅由 {n_universal} 条通用规则（task_kinds 为空的断言/结构规则）覆盖，"
                "无事项针对性判定——**不得解读为「该事项已按其特点查过忌宜」**。"
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
        na_count = len(ev.required_not_applicable)
        na_suffix = f"，{na_count} 条不适用（不阻塞）" if na_count else ""
        lines.append(
            f"- 可发布=否：必需集 {len(ev.required_rule_ids)} 条中 "
            f"{verified_required if verified_required is not None else '?'} 条已考证"
            f"{na_suffix}（阻塞项见下表）"
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
        na = ev.required_not_applicable
        lines.append(
            f"必需规则集（{task['kind']}）：共 {len(ev.required_rule_ids)} 条，"
            f"已可判定 {len(ev.required_rule_ids) - len(rb) - len(na)} 条"
            + (f"，不适用 {len(na)} 条（不阻塞）" if na else "")
        )
        if na:
            lines.append("")
            lines.append("| 不适用（不阻塞可发布） | 理由 |")
            lines.append("|---|---|")
            for b in na:
                lines.append(f"| `{b['rule_id']}` | {b['reason'] or '规则已声明本类输入不适用'} |")
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

    lines.append("## 盘面事实（值宿 / 紫白 / 吉神，**非吉凶**）")
    lines.append("")
    lines.extend(_cosmos_block(result.context.get("facts") or {}))
    lines.append("")

    lines.append("## 派别判定明细（并列，不合并分数）")
    lines.append("")
    for res in ev.per_school.values():
        lines.extend(_school_block(res))
        lines.append("")

    lines.append("## 神煞宜忌台账（事实层）")
    lines.append("")
    lines.extend(_hit_ledger(ev))
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

    lines.append("## 共识度（整数比，**非总分**）")
    lines.append("")
    lines.extend(_consensus_block(ev.manifest.get("five_school_output") or {}))
    lines.append("")

    unlabeled = sorted({j.rule_id for j in ev.judgments if j.verdict_type is None})
    if unlabeled:
        lines.append(
            f"## 未归类规则（本次评估涉及 {len(unlabeled)} 条；`verdict_type` 未标注，按 severity 路由）"
        )
        lines.append("")
        id_to_path = _rule_id_to_path()
        lines.append(f"共 {len(unlabeled)} 条（全部列出，不截断）：")
        lines.append("")
        for rid in unlabeled:
            path = id_to_path.get(rid)
            lines.append(f"- `{rid}`" + (f"（`{path}`）" if path else ""))
        lines.append("")
        lines.append(
            "> 未归类 ≠ 投票。这些规则当前按 `severity`/`hard_veto` 走既有路由，"
            "行为与标注前一致；C 第二批迁移时逐条定为 gate / vote / reference"
            "（清单见 `docs/c2-migration-checklist.md`，进度由 "
            "`core-rule/config/verdict_baseline.yaml` 棘轮锁定）。"
        )
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
        for set_name in selection:
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
