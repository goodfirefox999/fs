"""CLI（应用层，零第三方依赖，用 argparse 实现）。

命令
----
``zeri verify``      复核单个日课
``zeri gen``         时间窗内生成候选
``zeri cases run``   运行案例库
``zeri rules lint``  校验规则库（DSL / 引用完整性 / 签名 / 覆盖率）
``zeri rules diff``  比较两版规则库

全局参数：``--allow-unverified``、``--school``（可多次）、``--param key=value``、``--json``、
``--fail-on-veto``（供 CI 使用）。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Sequence
from zoneinfo import ZoneInfo

import yaml

from core_rule import default_registry
from core_rule.loader import load_ruleset
from core_time import CalendarConfig

from .generator import generate
from .report import render_generation_markdown, render_json, render_markdown
from .schemas import PersonSpec, SiteSpec, TaskSpec
from .verifier import verify

__all__ = ["main", "build_parser"]


def _parse_dt(text: str, tz_name: str) -> datetime:
    """解析 ``YYYY-MM-DDTHH:MM[+08:00]``；无时区时按配置时区补齐。"""
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit(f"无法解析时间: {text}（示例：2027-07-11T14:00）") from exc
    return dt if dt.tzinfo else dt.replace(tzinfo=ZoneInfo(tz_name))


def _parse_date(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise SystemExit(f"无法解析日期: {text}（示例：2027-07-11）") from exc


def _load_yaml(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"{path} 顶层必须是映射")
    return data


def _site_from_args(args: argparse.Namespace) -> SiteSpec:
    data = _load_yaml(args.site)
    azimuth = args.azimuth if args.azimuth is not None else data.get("azimuth_deg")
    if azimuth is None:
        raise SystemExit("缺少坐向：请用 --azimuth 度数 或 --site site.yaml（含 azimuth_deg）")
    return SiteSpec(
        azimuth_deg=float(azimuth),
        lat=float(data.get("lat", 0.0)),
        lon=float(data.get("lon", 0.0)),
        mountain=data.get("mountain"),
        facing=data.get("facing"),
        fenjin=data.get("fenjin"),
        measure_method=str(data.get("measure_method", "unspecified")),
        angle_uncertainty_deg=float(data.get("angle_uncertainty_deg", 0.0)),
    )


def _person_from_args(args: argparse.Namespace) -> PersonSpec | None:
    data = _load_yaml(args.person)
    if not data:
        return None
    birth = data.get("birth_dt")
    return PersonSpec(
        name=data.get("name"),
        birth_dt=datetime.fromisoformat(birth) if birth else None,
        birth_lon=data.get("birth_lon"),
        birth_lat=data.get("birth_lat"),
        gender=data.get("gender"),
        year_zhi=data.get("year_zhi"),
        year_gz=data.get("year_gz"),
        lunar_override=bool(data.get("lunar_override", False)),
    )


def _cal_from_args(args: argparse.Namespace) -> CalendarConfig:
    overrides: dict[str, Any] = {}
    for item in args.param or []:
        if "=" not in item:
            raise SystemExit(f"--param 需形如 key=value，得到 {item}")
        key, value = item.split("=", 1)
        if value.lower() in ("true", "false"):
            overrides[key] = value.lower() == "true"
        else:
            try:
                overrides[key] = int(value)
            except ValueError:
                overrides[key] = value
    if args.true_solar_time:
        overrides["use_true_solar_time"] = True
    if args.day_boundary:
        overrides["day_boundary"] = args.day_boundary
    if args.year_boundary:
        overrides["year_boundary"] = args.year_boundary
    cal = CalendarConfig()
    return cal.with_overrides(**overrides) if overrides else cal


def _schools(args: argparse.Namespace) -> tuple[str, ...] | None:
    return tuple(args.school) if args.school else None


def _caliber_selection(args: argparse.Namespace) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in getattr(args, "caliber", None) or []:
        if "=" not in item:
            raise SystemExit(f"--caliber 需形如 key=value，得到 {item}")
        key, value = item.split("=", 1)
        out[key] = value
    return out


def _registry_with_calibers(args: argparse.Namespace):
    reg = default_registry()
    selection = _caliber_selection(args)
    return reg.with_calibers(selection) if selection else reg


# --------------------------------------------------------------------------- #
# 子命令实现
# --------------------------------------------------------------------------- #
def cmd_verify(args: argparse.Namespace) -> int:
    if args.demo_veto and not args.allow_unverified:
        print("错误：--demo-veto 必须与 --allow-unverified 同用（演示命中仅在联调模式存在，ADR-0014 决策 3）", file=sys.stderr)
        return 2
    cal = _cal_from_args(args)
    site = _site_from_args(args)
    person = _person_from_args(args)
    task = TaskSpec(kind=args.task, nodes=(args.node,) if args.node else (), strictness=args.strictness)
    result = verify(
        dt=_parse_dt(args.course, cal.timezone),
        site=site,
        task=task,
        person=person,
        node=args.node,
        cal=cal,
        registry=_registry_with_calibers(args),
        schools=_schools(args),
        allow_unverified=args.allow_unverified,
        demo_veto=args.demo_veto,
    )
    text = render_json(result) if args.json else render_markdown(result)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已写入 {args.out}", file=sys.stderr)
    else:
        print(text)
    if args.fail_on_veto and result.evaluation.vectors["hard_fail_count"] > 0:
        return 2
    return 0


def cmd_gen(args: argparse.Namespace) -> int:
    if args.demo_veto and not args.allow_unverified:
        print("错误：--demo-veto 必须与 --allow-unverified 同用（演示命中仅在联调模式存在，ADR-0014 决策 3）", file=sys.stderr)
        return 2
    cal = _cal_from_args(args)
    site = _site_from_args(args)
    person = _person_from_args(args)
    if "/" not in args.window:
        raise SystemExit("--window 需形如 2027-01-01/2027-12-31")
    start_s, end_s = args.window.split("/", 1)
    task = TaskSpec(kind=args.task, strictness=args.strictness, granularity=args.granularity)
    result = generate(
        start=_parse_date(start_s),
        end=_parse_date(end_s),
        site=site,
        task=task,
        person=person,
        node=args.node,
        cal=cal,
        registry=_registry_with_calibers(args),
        schools=_schools(args),
        allow_unverified=args.allow_unverified,
        demo_veto=args.demo_veto,
        top=args.top,
        with_sensitivity=args.sensitivity,
        with_robustness=args.robustness,
    )
    text = render_json(result) if args.json else render_generation_markdown(result)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已写入 {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


def cmd_rules_lint(args: argparse.Namespace) -> int:
    reg = default_registry()
    rs = reg.ruleset
    problems: list[str] = []

    # 1) 引用完整性：tests 指向的用例必须存在
    case_dir = Path(args.cases or "tests/cases/rule_tests")
    existing = {p.stem for p in case_dir.glob("*.yaml")} if case_dir.exists() else set()
    for rule in rs.rules:
        for case_id in rule.tests:
            if case_dir.exists() and case_id not in existing:
                problems.append(f"{rule.rule_id}: tests 引用的用例不存在 -> {case_id}")

    # 2) 已考证规则必须有完整引文
    for rule in rs.rules:
        if rule.status == "已考证" and not rule.citation.has_quote:
            problems.append(f"{rule.rule_id}: 已考证但 citation.quote 为空")

    # 3) veto 规则不得有 score_weight
    for rule in rs.rules:
        if rule.hard_veto and rule.score_weight is not None:
            problems.append(f"{rule.rule_id}: veto 规则不得设置 score_weight")

    # 4) 覆盖率：每条规则至少 2 个测试向量
    for rule in rs.rules:
        if len(rule.tests) < 2:
            problems.append(f"{rule.rule_id}: tests 少于 2 项")

    # 5) 派别一致性：规则 school 必须已在 school_policy 声明
    for rule in rs.rules:
        if rule.school not in reg.policy.schools:
            problems.append(f"{rule.rule_id}: school '{rule.school}' 未在 school_policy 声明")

    # 6) 规则清单一致性（防止"文档说 44 条、实际 52 条"的漂移）
    manifest_path = Path(args.manifest or "core-rule/config/rules_manifest.yaml")
    if manifest_path.exists():
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        stats_now = rs.stats()
        if manifest.get("expected_total") is not None and stats_now["total"] != manifest["expected_total"]:
            problems.append(
                f"规则总数 {stats_now['total']} 与 MANIFEST 声明 {manifest['expected_total']} 不一致"
            )
        for status, expected in (manifest.get("expected_by_status") or {}).items():
            actual = stats_now["by_status"].get(status, 0)
            if actual != expected:
                problems.append(f"status={status} 实际 {actual} 条，MANIFEST 声明 {expected} 条")
        for school, expected in (manifest.get("expected_by_school") or {}).items():
            actual = stats_now["by_school"].get(school, 0)
            if actual != expected:
                problems.append(f"school={school} 实际 {actual} 条，MANIFEST 声明 {expected} 条")

    # 7) 必需集准入四条 + 可判定闭合（Q-011 元规则，ADR-0012）
    problems.extend(_check_required_set(reg))

    # 8) 定义级 severity 白名单（ADR-0009 的 CI 兜底）
    for rule in rs.rules:
        if rule.status == "定义级" and rule.severity != "记录":
            problems.append(f"{rule.rule_id}: 定义级 severity 必须为「记录」，得到「{rule.severity}」")
        if rule.status != "定义级" and rule.severity == "记录":
            problems.append(f"{rule.rule_id}: severity=「记录」仅限定义级")

    # 9) 非阻断提示（warning，不影响返回码，ADR-0013）
    warnings: list[str] = []
    for rid in sorted(reg.required_rules.all_rule_ids()):
        wrule = rs.by_id.get(rid)
        if wrule is not None and wrule.status == "待考证":
            warnings.append(f"{rid} 待考证：补原文并签名后可解锁 publishable 进度")
    for rule in rs.rules:
        if rule.status != "定义级" and rule.citation.has_quote and not rule.citation.verified_by:
            warnings.append(
                f"{rule.rule_id}: citation.quote 已填但 verified_by 为空（未经人类签名，不得升级已考证）"
            )

    # 10) ADR-0014 决策 1：声明/生效双显示（cap 单一来源 core_rule.severity_cap）
    from core_rule.severity_cap import cap_warning

    for rid in sorted(rs.cap_applied_ids):
        rule = rs.by_id[rid]
        w = cap_warning(rule)
        if w:
            warnings.append(w)

    # 11) 状态跃迁提权（ADR-0014）：已考证必须有人类签名（loader 之外的 lint 纵深）
    problems.extend(_check_signatures(reg))

    # 12) C21 静态层（warn 不 error——评审第十二轮约束 2；动态层见 tools/dead_rule_scan.py）
    warnings.extend(_c21_static_warnings(reg))  # QUESTIONS 路径用默认（真文件）

    # 12b) evaluable=false 生命周期（评审第十四/十五轮，fixture 反证见测试）：
    #      blocked_by 指向的 Q 已裁定 → 豁免失效，规则必须恢复评估或显式废弃
    warnings.extend(_evaluable_expiry_warnings(reg))

    stats = rs.stats()
    print("规则库统计：")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"事项模板：{len(reg.task_kinds)} 个")
    print(f"派别：{', '.join(reg.policy.enabled_schools())}（启用） / {', '.join(reg.policy.schools)}（全部）")
    # 机器可读分组行（ADR-0014，评审第十/十一轮：按 check id 分组，测试按组断言精确集合。
    # 注意：cap_applied 与 unverified_progress 当前同集是**语料现状的结构重合**（所有待考证
    # 必需规则恰为禁用级），非定义相同——新增"待考证+慎用"必需规则即分叉。
    # cap_applied 作用域 = 全库（scope=all_rules），与必需集 8 条无关，勿拿 8 对 10。）
    groups = _lint_groups(reg)
    # 13) VERIFICATION_GUIDE 三·三联动重审的 lint 不变式（评审第十二/十三轮）：
    #     已考证规则引用 非authentic 书目 → 当轮重审清单（机器发现，不靠人记）
    groups["book_authenticity_review"] = _book_authenticity_review(reg)
    print(f"cap_applied: {json.dumps(groups['cap_applied'], ensure_ascii=False)}")
    print(f"unverified_progress: {json.dumps(groups['unverified_progress'], ensure_ascii=False)}")
    print(f"quote_unsigned: {json.dumps(groups['quote_unsigned'], ensure_ascii=False)}")
    print(f"book_authenticity_review: {json.dumps(groups['book_authenticity_review'], ensure_ascii=False)}")
    # 已知未覆盖的原文硬禁（coverage_gaps.yaml，Q-012/C18；机器可读闭环）
    gaps_path = Path("core-rule/config/coverage_gaps.yaml")
    if gaps_path.exists():
        gaps_data = yaml.safe_load(gaps_path.read_text(encoding="utf-8")) or {}
        gap_ids = [str(g.get("id")) for g in (gaps_data.get("gaps") or [])]
        print(f"coverage_gaps: {json.dumps(gap_ids, ensure_ascii=False)}")
        if gap_ids:
            warnings.append(
                "已知未覆盖原文硬禁 " + str(len(gap_ids)) + " 条：" + ", ".join(gap_ids)
                + "（见 coverage_gaps.yaml；C18 完成后自动消除）"
            )
    if warnings:
        print("\n提示（不阻断）：")
        for w in warnings:
            print(f"  - {w}")

    if problems:
        print("\n发现问题：")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("\n✅ lint 通过（无引用/签名/结构问题）")
    return 0


def _fact_roots(rule) -> set[str]:
    from core_rule.dsl import collect_fact_paths

    return {p.split(".")[0] for p in collect_fact_paths(rule.condition)}


def cmd_rules_reaudit(args: argparse.Namespace) -> int:
    """联动重审清单（VERIFICATION_GUIDE 三·三）：列出引用指定书目的全部规则与状态。

    降级/重审操作须人类签名确认，本命令只产出清单——自动发现，不自动改状态。
    """
    reg = default_registry()
    book = args.book
    hits = [
        r for r in reg.ruleset.rules
        if book in (r.citation.source or "")
    ]
    if not hits:
        print(f"无规则引用《{book}》")
        return 0
    print(f"引用《{book}》的规则 {len(hits)} 条（book_authenticity 变更时按 VERIFICATION_GUIDE 三·三当轮重审）：")
    print("")
    print("| 规则 | status | book_authenticity | quote_kind | verified_by |")
    print("|---|---|---|---|---|")
    for r in sorted(hits, key=lambda x: x.rule_id):
        auth = getattr(r.citation, "book_authenticity", None) or "待核"
        print(f"| `{r.rule_id}` | {r.status} | {auth} | {r.citation.quote_kind or '—'} | {r.citation.verified_by or '—'} |")
    need = [r.rule_id for r in hits if r.status == "已考证"
            and (getattr(r.citation, "book_authenticity", None) or "待核") != "authentic"]
    if need:
        print(f"\n⚠️ 需当轮重审（已考证 × 非 authentic 书目）：{need}")
        print("处置：降回 待考证（重审后再签）或修订 book_authenticity——两条路都须人类签名。")
    return 0


def _lint_groups(reg) -> dict[str, list[str]]:
    """lint 检查的机器可读分组（按 check id；供 cmd_rules_lint 打印与测试精确集合断言）。

    - cap_applied：全库 scope，声明 severity 高于 status 上限（ADR-0014 决策 1）
    - unverified_progress：必需集内待考证规则（考证进度面板，语义与 cap 无关）
    - quote_unsigned：已录引文未经人类签名（status=有争议/待考证）
    """
    rs = reg.ruleset
    return {
        "cap_applied": sorted(rs.cap_applied_ids),
        "unverified_progress": sorted(
            rid for rid in reg.required_rules.all_rule_ids()
            if rs.by_id.get(rid) is not None and rs.by_id[rid].status == "待考证"
        ),
        "quote_unsigned": sorted(
            rule.rule_id for rule in rs.rules
            if rule.status != "定义级" and rule.citation.has_quote and not rule.citation.verified_by
        ),
    }


CANDIDATE_NS = ("facts.", "time.", "course.")

QUESTIONS_PATH = Path("docs/QUESTIONS.md")


def _q_resolved(qid: str, questions_path: Path | None = None) -> bool:
    """QUESTIONS.md 中 Q-xxx 是否已裁定（section 含「已裁定」）。供豁免失效检查。"""
    path = questions_path or QUESTIONS_PATH
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    marker = f"## {qid} "
    i = text.find(marker)
    if i < 0:
        return False
    j = text.find("\n## ", i + 1)
    section = text[i:j if j > 0 else len(text)]
    return "已裁定" in section


def _evaluable_expiry_warnings(reg, questions_path: Path | None = None) -> list[str]:
    """evaluable=false 的豁免生命周期：blocked_by 指向的 Q 已裁定 → 豁免失效（warn）。"""
    out: list[str] = []
    for rule in reg.ruleset.rules:
        if getattr(rule, "evaluable", True):
            continue
        bb = str(rule.raw.get("blocked_by") or "")
        for token in bb.replace("、", " ").replace("+", " ").split():
            if token.startswith("Q-") and _q_resolved(token, questions_path):
                out.append(
                    f"{rule.rule_id}: evaluable=false 的阻塞项 {token} 已裁定——"
                    "豁免失效，恢复评估或显式废弃（VERIFICATION_GUIDE 三·三联动）"
                )
    return out


def _c21_static_warnings(reg, questions_path: Path | None = None) -> list[str]:
    """C21 静态层：候选特异因子检查（warn 级）。

    断言级规则 condition 必须引用至少一个候选派生路径
    （facts.* 引擎事实 / time.* 时刻派生 / course.* 四柱派生）；
    仅引用 site.* / person.*（用户输入，跨候选不变）= "每候选恒命中"的死规则形态。
    动态层（适用域内零命中）见 tools/dead_rule_scan.py + dead_rule_baseline.yaml。

    op=exists 豁免为**三重条件**（评审第十三轮：形态豁免过宽，缺任一照报）：
    ① op=exists；② explanation/notes 含 待裁定/占位/待启用 标记；
    ③ 口径问题已登记裁定队列（Q-013，notes 引用之）。
    **生命周期（评审第十五轮）**：Q-013 裁定完成 → 豁免失效，占位规则必须处置。
    实现备注：本豁免于 2026-11-01 补实现——此前 GUIDE 三·五声称已豁免而代码未落地
    （文档与实现不符，已修正；详见提交历史）。
    """
    from core_rule.dsl import collect_fact_paths

    q013_resolved = _q_resolved("Q-013", questions_path)
    out: list[str] = []
    for rule in reg.ruleset.rules:
        if rule.status == "定义级":
            continue
        paths = collect_fact_paths(rule.condition)
        if paths and not any(p.startswith(ns) for p in paths for ns in CANDIDATE_NS):
            marker = (rule.explanation or "") + (rule.notes or "")
            is_placeholder = (
                rule.condition.get("op") == "exists"
                and any(k in marker for k in ("待裁定", "占位", "待启用", "裁定口径"))
                and "Q-013" in marker
            )
            if is_placeholder and not q013_resolved:
                continue  # 就绪探测占位（设计意图即恒真）；Q-013 裁定后豁免失效
            suffix = "（Q-013 已裁定——占位豁免失效，须处置）" if is_placeholder else ""
            out.append(
                f"{rule.rule_id}: condition 仅引用用户输入（site/person），"
                f"无候选派生因子（facts/time/course）——C21 静态层{suffix}"
            )
    return out


def _check_signatures(reg) -> list[str]:
    """状态跃迁提权（ADR-0014）：已考证必须有人类签名。

    loader 已硬校验（无签名拒绝加载），本检查为 lint 层纵深——
    覆盖程序化构造的 ruleset（dc_replace 注入等）绕过 loader 的路径。
    Agent 署名黑名单（评审第十二轮：文档纪律升级为机器强制——
    "是不是人类"无法判定，但已知非人类署名可拒绝）。
    """
    # 评审第十五轮实测：\b 在 CJK 相邻时失效（"AI助手"无空格绕过）——
    # ASCII token 用显式边界 (?<![A-Za-z0-9])…(?![A-Za-z0-9])，中文词（机器人/千问/通义等）
    # 直接子串匹配（CJK 无词边界概念）。仍是启发式辅助（fail-open）；
    # 完备防线 = verified_by 结构校验（非空+日期+可联系锚点）+ status 变更权限
    # （CODEOWNERS/分支保护——已登记 coverage_gaps GAP-SIGNATURE-PERMISSION，阻塞待接）。
    import re as _re

    ascii_pat = _re.compile(
        r"(?<![A-Za-z0-9])(pytest|agent|ai|llm|bot|auto|qwen|gpt|claude)(?![A-Za-z0-9])",
        _re.IGNORECASE,
    )
    cjk_words = ("机器人", "千问", "通义", "智能体", "大模型")
    out: list[str] = []
    for rule in reg.ruleset.rules:
        if rule.status != "已考证":
            continue
        vb = (rule.citation.verified_by or "").strip()
        if not vb:
            out.append(f"{rule.rule_id}: status=已考证 但 verified_by 为空（状态跃迁提权，ADR-0014）")
        elif ascii_pat.search(vb) or any(w in vb for w in cjk_words):
            out.append(f"{rule.rule_id}: verified_by='{vb}' 疑似非人类署名（黑名单命中，须真人签名）")
    return out


def _book_authenticity_review(reg) -> list[str]:
    """VERIFICATION_GUIDE 三·三联动重审的机器发现（评审第十三轮产物二）。

    已考证规则引用 book_authenticity ∈ {缺省待核, disputed, pseudepigraphic} 的书目
    → 当轮重审清单（降级须人类签名确认，本函数只产出清单）。
    """
    out: list[str] = []
    for rule in reg.ruleset.rules:
        if rule.status != "已考证":
            continue
        auth = getattr(rule.citation, "book_authenticity", None) or "待核"
        if auth != "authentic":
            out.append(f"{rule.rule_id}: 引用《{rule.citation.source}》book_authenticity={auth} → 当轮重审")
    return out


def _check_required_set(reg) -> list[str]:
    """必需集准入四条 + 可判定闭合。

    任何一条不满足 → ``required_set_unresolvable``，并列出阻塞链。
    否则会出现"报告说必需集 9/10，但 publishable 恒 false"的荒诞状态。
    """
    problems: list[str] = []
    rs = reg.ruleset
    required = reg.required_rules
    criteria = required.criteria or {}
    allowed_targets = set(criteria.get("allowed_targets") or ["mountain", "facing", "day", "person"])
    forbidden_schools = set(criteria.get("forbidden_schools") or ["doushou", "xuankong"])
    require_veto = bool(criteria.get("require_hard_veto", True))

    def _check_group(rids, *, group: str, task_kind: str) -> None:
        for rid in rids:
            where = f"required_rules[{task_kind}].{group}"
            if rid not in rs.by_id:
                problems.append(f"required_set_unresolvable: {where} 引用了不存在的规则 {rid}")
                continue
            rule = rs.by_id[rid]
            if require_veto and not rule.hard_veto:
                problems.append(
                    f"required_set_unresolvable: {where} 的 {rid} 不是硬否决（hard_veto=false），"
                    "按准入条件不得进必需集"
                )
            if rule.target not in allowed_targets:
                problems.append(
                    f"required_set_unresolvable: {where} 的 {rid} target={rule.target} 不在允许集合"
                    f" {sorted(allowed_targets)}（hour 级规则换时辰即可规避，不构成必需）"
                )
            if rule.school in forbidden_schools:
                problems.append(
                    f"required_set_unresolvable: {where} 的 {rid} 属于参考层派别 {rule.school}"
                )
            if rule.status == "有争议":
                problems.append(
                    f"required_set_controversial: {where} 的 {rid} status=有争议，"
                    "出处核查未通过（ADR-0013），不得作为发布门槛"
                )
            if not getattr(rule, "evaluable", True):
                problems.append(
                    f"required_set_not_evaluable: {where} 的 {rid} evaluable=false"
                    "（起例未实现挂起，Q-014）——必需集规则必须可评估"
                )
            roots = _fact_roots(rule)
            if group == "core" and "person" in roots:
                problems.append(
                    f"required_set_unresolvable: {where} 的 {rid} 依赖 person.*，"
                    "应移到 person_dependent（否则用户不填命主时永久 unknown）"
                )
            if group == "person_dependent" and "person" not in roots:
                problems.append(
                    f"required_set_unresolvable: {where} 的 {rid} 不依赖 person.*，"
                    "应放在 core 组"
                )

    _check_group(required.core, group="core", task_kind="default")
    _check_group(required.person_dependent, group="person_dependent", task_kind="default")
    for task_kind, ov in required.overrides.items():
        if task_kind not in reg.task_kinds:
            problems.append(f"required_set_unresolvable: overrides 引用了未知事项 {task_kind}")
        _check_group(ov.get("add") or (), group="add", task_kind=task_kind)
        for rid in ov.get("remove") or ():
            if rid not in rs.by_id:
                problems.append(
                    f"required_set_unresolvable: required_rules[{task_kind}].remove 引用了不存在的规则 {rid}"
                )

    # 每个 task_kind 至少要有 1 条必需规则（否则 publishable 失去意义）
    for task_kind in reg.task_kinds:
        if not reg.required_for(task_kind):
            problems.append(f"required_set_unresolvable: 事项 {task_kind} 的必需集为空")
    return problems


def cmd_rules_diff(args: argparse.Namespace) -> int:
    old = load_ruleset(args.old)
    new = load_ruleset(args.new)
    old_ids, new_ids = set(old.by_id), set(new.by_id)
    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)
    changed = sorted(
        rid for rid in old_ids & new_ids if old.by_id[rid].to_dict() != new.by_id[rid].to_dict()
    )
    print(json.dumps(
        {
            "old_version": old.version,
            "new_version": new.version,
            "added": added,
            "removed": removed,
            "changed": changed,
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


def cmd_cases_run(args: argparse.Namespace) -> int:
    from .case_runner import run_cases

    report = run_cases(Path(args.cases_dir), grade=args.grade, out_dir=Path(args.out) if args.out else None)
    print(json.dumps(report.summary, ensure_ascii=False, indent=2))
    return 0 if report.summary.get("failed", 0) == 0 else 1


# --------------------------------------------------------------------------- #
# 解析器
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zeri", description="择日引擎（离线、确定性、可审计）")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--task", required=True, help="事项，如 修祠/动土/安葬")
        p.add_argument("--node", default=None, help="节点，如 上梁/安龛")
        p.add_argument("--strictness", default="normal", choices=["normal", "strict"])
        p.add_argument("--site", default=None, help="site.yaml（azimuth_deg/lat/lon/fenjin）")
        p.add_argument("--azimuth", type=float, default=None, help="坐山方位角（度）")
        p.add_argument("--person", default=None, help="person.yaml（year_zhi/birth_dt）")
        p.add_argument("--school", action="append", default=None, help="启用派别，可多次")
        p.add_argument("--allow-unverified", action="store_true", help="允许待考证规则参与判定（仅联调）")
        p.add_argument("--param", action="append", default=None, help="历法参数覆盖 key=value")
        p.add_argument(
            "--caliber", action="append", default=None,
            help="口径选择 key=value（如 nayin=chuanshan / sansha=named_sansha），可多次",
        )
        p.add_argument("--true-solar-time", action="store_true", help="启用真太阳时")
        p.add_argument("--day-boundary", choices=["early", "late"], default=None)
        p.add_argument("--year-boundary", choices=["lichun", "newyear"], default=None)
        p.add_argument("--json", action="store_true", help="输出 JSON")
        p.add_argument("--out", default=None, help="写入文件")

    p_verify = sub.add_parser("verify", help="复核单个日课")
    p_verify.add_argument("--course", required=True, help="日课时刻，如 2027-07-11T14:00")
    add_common(p_verify)
    p_verify.add_argument("--fail-on-veto", action="store_true", help="命中否决时返回码 2")
    p_verify.add_argument(
        "--demo-veto", action="store_true",
        help="演示命中计入否决（联调视图；须与 --allow-unverified 同用，ADR-0014 决策 3）",
    )
    p_verify.set_defaults(func=cmd_verify)

    p_gen = sub.add_parser("gen", help="生成候选")
    p_gen.add_argument("--window", required=True, help="2027-01-01/2027-12-31")
    p_gen.add_argument("--top", type=int, default=20)
    p_gen.add_argument("--granularity", default="day_hour", choices=["day", "day_hour"])
    p_gen.add_argument("--sensitivity", action="store_true", help="执行敏感性分析")
    p_gen.add_argument(
        "--robustness", action="store_true",
        help="执行稳健性评估（坐向 ±uncertainty + 口径开关），输出稳健集/敏感集",
    )
    p_gen.add_argument(
        "--demo-veto", action="store_true",
        help="演示命中计入否决（联调视图；须与 --allow-unverified 同用，ADR-0014 决策 3）",
    )
    add_common(p_gen)
    p_gen.set_defaults(func=cmd_gen)

    p_lint = sub.add_parser("rules", help="规则库操作")
    lint_sub = p_lint.add_subparsers(dest="rules_command", required=True)
    p_lint_cmd = lint_sub.add_parser("lint", help="校验规则库")
    p_lint_cmd.add_argument("--cases", default=None)
    p_lint_cmd.add_argument("--manifest", default=None, help="规则清单路径（默认 core-rule/config/rules_manifest.yaml）")
    p_lint_cmd.set_defaults(func=cmd_rules_lint)
    p_reaudit = lint_sub.add_parser("reaudit", help="联动重审清单：列出引用某书目的规则（GUIDE 三·三）")
    p_reaudit.add_argument("--book", required=True, help="书目名（含书名号可省）")
    p_reaudit.set_defaults(func=cmd_rules_reaudit)
    p_diff = lint_sub.add_parser("diff", help="比较两版规则库")
    p_diff.add_argument("old")
    p_diff.add_argument("new")
    p_diff.set_defaults(func=cmd_rules_diff)

    p_cases = sub.add_parser("cases", help="案例库")
    cases_sub = p_cases.add_subparsers(dest="cases_command", required=True)
    p_run = cases_sub.add_parser("run", help="运行案例")
    p_run.add_argument("--grade", default="A", choices=["A", "B", "C", "all"])
    p_run.add_argument("--cases-dir", default="cases")
    p_run.add_argument("--out", default=None)
    p_run.set_defaults(func=cmd_cases_run)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
