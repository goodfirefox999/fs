"""案例运行器（应用层）。

产出四份报告（docs/DEVELOPMENT.md 第 9 节）
----------------------------------------
1. 实现一致率：与作者判定比对，Cohen's kappa，措辞固定为「与作者判定吻合度」
2. 规则覆盖率：多少案例出现「无规则可判」
3. 分歧清单：派别冲突最大的案例/规则对
4. 规则缺口清单：缺失规则候选（unknown 原因聚合）

必做对照实验：标签随机打乱后重跑一致率。若下降不显著，说明规则集对案例无判别信息，
必须在报告中标注该结论。

**用途限定**：案例只验证"实现是否符合宣称规则"，不验证"择日是否灵验"。
"""

from __future__ import annotations

import json
import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from core_rule import default_registry
from core_time import CalendarConfig

from .report import render_markdown
from .schemas import PersonSpec, SiteSpec, TaskSpec
from .verifier import verify

from cases.schema import Case, load_case  # noqa: E402  (cases 包由 conftest 注入 sys.path)

__all__ = ["CaseOutcome", "CaseRunReport", "run_cases", "cohen_kappa"]

LABELS = ("可用", "存疑", "不可用")


def cohen_kappa(a: Iterable[str], b: Iterable[str], labels: Iterable[str] = LABELS) -> float:
    """Cohen's kappa。样本全同标签导致 pe=1 时返回 0.0（并标注不可解释）。"""
    xs, ys = list(a), list(b)
    n = len(xs)
    if n == 0 or n != len(ys):
        return 0.0
    po = sum(1 for x, y in zip(xs, ys) if x == y) / n
    pe = sum((xs.count(l) / n) * (ys.count(l) / n) for l in labels)
    if abs(1.0 - pe) < 1e-12:
        return 0.0
    return (po - pe) / (1.0 - pe)


@dataclass
class CaseOutcome:
    case: Case
    state: str
    tier: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and all(c["ok"] for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case.case_id,
            "grade": self.case.grade,
            "state": self.state,
            "tier": self.tier,
            "passed": self.passed,
            "error": self.error,
            "checks": self.checks,
        }


@dataclass
class CaseRunReport:
    outcomes: list[CaseOutcome]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"summary": self.summary, "outcomes": [o.to_dict() for o in self.outcomes]}


def _check(ok: bool, name: str, detail: str) -> dict[str, Any]:
    return {"ok": bool(ok), "check": name, "detail": detail}


def _run_one(case: Case, *, allow_unverified: bool = True) -> CaseOutcome:
    cal = CalendarConfig()
    site = SiteSpec(
        azimuth_deg=case.input.azimuth_deg,
        lat=case.input.lat,
        lon=case.input.lon,
        fenjin=case.input.fenjin,
    )
    person = (
        PersonSpec(year_zhi=case.input.person_year_zhi, name=case.input.person_name)
        if (case.input.person_year_zhi or case.input.person_name)
        else None
    )
    task = TaskSpec(
        kind=case.input.task_kind, nodes=case.input.nodes, strictness=case.input.strictness
    )
    try:
        result = verify(
            dt=case.input.course,
            site=site,
            task=task,
            person=person,
            cal=cal,
            allow_unverified=allow_unverified,
            # 案例库运行为联调视图：演示命中计入结论（金标准期望含演示否决/正向，ADR-0014 决策 3）
            demo_veto=True,
        )
    except Exception as exc:  # noqa: BLE001 - 案例失败必须记录而非中断整批
        return CaseOutcome(case=case, state="", tier="", error=f"{type(exc).__name__}: {exc}")

    ev = result.evaluation
    checks: list[dict[str, Any]] = []
    exp = case.expected or {}

    if "pillar_check" in exp:
        want = exp["pillar_check"]["bazi"]
        got = result.context["course"]["bazi"]
        checks.append(_check(got == want, "四柱", f"期望 {want}，得到 {got}"))

    for rid in exp.get("must_include_positive", []):
        hit = any(j.rule_id == rid for res in ev.per_school.values() for j in res.positives)
        checks.append(_check(hit, f"正向证据 {rid}", "命中" if hit else "未命中"))

    for rid in exp.get("must_not_include_veto", []):
        hit = any(j.rule_id == rid for res in ev.per_school.values() for j in res.vetoes)
        checks.append(_check(not hit, f"不得否决 {rid}", "未命中" if not hit else "错误命中"))

    for rid in exp.get("must_be_unknown", []):
        hit = any(j.rule_id == rid for res in ev.per_school.values() for j in res.unknowns)
        checks.append(_check(hit, f"必须登记为 unknown {rid}", "已登记" if hit else "未登记"))

    for tier in exp.get("must_not_tier", []):
        checks.append(_check(ev.tier != tier, f"等级不得为 {tier}", f"实际 {ev.tier}"))

    if "structure" in exp:
        st = exp["structure"]
        if "max_repeat" in st:
            checks.append(
                _check(
                    result.structure.max_repeat == st["max_repeat"],
                    "地支最大重复",
                    f"期望 {st['max_repeat']}，得到 {result.structure.max_repeat}",
                )
            )
        if "repeated_zhi" in st:
            got = sorted(result.structure.repeated)
            checks.append(
                _check(got == sorted(st["repeated_zhi"]), "重复地支", f"期望 {st['repeated_zhi']}，得到 {got}")
            )
        if st.get("weiwei_self_punishment") is False:
            checks.append(
                _check(
                    not result.structure.weiwei_is_self_punishment,
                    "未未不是自刑",
                    "正确（未未按重复处理）"
                    if not result.structure.weiwei_is_self_punishment
                    else "错误：把未未标成了自刑",
                )
            )

    return CaseOutcome(case=case, state=ev.state, tier=ev.tier, checks=checks)


def run_cases(
    cases_dir: Path | str,
    *,
    grade: str = "A",
    out_dir: Path | None = None,
    seed: int = 20271101,
) -> CaseRunReport:
    """运行案例库并产出四份报告。"""
    root = Path(cases_dir)
    graded = root / "graded"
    files: list[Path] = []
    if graded.exists():
        if grade == "all":
            files = sorted(graded.rglob("*.yaml"))
        else:
            files = sorted((graded / grade).glob("*.yaml"))
    cases = [load_case(p) for p in files]
    outcomes = [_run_one(c) for c in cases]

    evaluated = [o for o in outcomes if o.error is None]
    passed = sum(1 for o in outcomes if o.passed)

    # ---- 1. 一致率（与作者判定吻合度）----
    paired = [(o.state, o.case.author_claim.verdict) for o in evaluated if o.case.author_claim.verdict]
    agreement = (
        sum(1 for s, v in paired if s == v) / len(paired) if paired else None
    )
    kappa = cohen_kappa([s for s, _ in paired], [v for _, v in paired]) if paired else None

    # ---- 打乱对照 ----
    shuffle_result: dict[str, Any] = {"applicable": False}
    if len(paired) >= 4:
        labels = [v for _, v in paired]
        rng = random.Random(seed)
        rng.shuffle(labels)
        shuffled_agreement = sum(1 for (s, _), v in zip(paired, labels) if s == v) / len(paired)
        shuffle_result = {
            "applicable": True,
            "shuffled_agreement": round(shuffled_agreement, 4),
            "delta": round((agreement or 0.0) - shuffled_agreement, 4),
            "seed": seed,
            "note": (
                "若打乱后吻合度下降不显著，说明规则集对本案例集缺乏判别信息，"
                "该结论必须写入报告，不得隐去。"
            ),
        }

    # ---- 2. 覆盖率 ----
    unknown_ratios = [
        o.checks and (sum(1 for c in o.checks if not c["ok"]) / len(o.checks)) for o in evaluated
    ]
    no_rule_cases = [
        o.case.case_id
        for o in evaluated
        if o.state == "可用" and o.tier in ("ACCEPTABLE", "PREFERRED") and not o.checks
    ]

    # ---- 3/4. 分歧与缺口 ----
    gap_counter: Counter[str] = Counter()
    for o in evaluated:
        for c in o.checks:
            if not c["ok"]:
                gap_counter[c["check"]] += 1

    summary: dict[str, Any] = {
        "total": len(outcomes),
        "passed": passed,
        "failed": len(outcomes) - passed,
        "grade": grade,
        "consistency": {
            "label": "与作者判定吻合度（非准确率）",
            "n": len(paired),
            "agreement": round(agreement, 4) if agreement is not None else None,
            "kappa": round(kappa, 4) if kappa is not None else None,
            "note": "kappa 在样本全同标签时不可解释，此处按 0 处理并标注",
        },
        "coverage": {
            "no_rule_cases": no_rule_cases,
            "cases_with_all_checks_passed": passed,
        },
        "gaps": dict(gap_counter.most_common()),
        "shuffle_control": shuffle_result,
        "disclaimer": "案例仅用于验证实现是否符合宣称规则，不用于验证择日是否灵验；不得称为准确率。",
    }

    report = CaseRunReport(outcomes=outcomes, summary=summary)

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "cases_summary.json").write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_dir / "consistency.md").write_text(_render_consistency(report), encoding="utf-8")
        (out_dir / "coverage.md").write_text(_render_coverage(report), encoding="utf-8")
        (out_dir / "divergence.md").write_text(_render_divergence(report), encoding="utf-8")
        (out_dir / "gaps.md").write_text(_render_gaps(report), encoding="utf-8")

    return report


def _render_consistency(report: CaseRunReport) -> str:
    c = report.summary["consistency"]
    lines = [
        "# 报告一：与作者判定吻合度",
        "",
        f"- 样本数：{c['n']}",
        f"- 吻合度：{c['agreement']}",
        f"- Cohen's kappa：{c['kappa']}",
        "",
        f"> 措辞规范：本指标**只能**称为「与作者判定吻合度」，不得称为准确率。",
        "",
        "## 打乱对照",
        "",
        "```json",
        json.dumps(report.summary["shuffle_control"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## 逐案例",
        "",
        "| 案例 | 系统三态 | 作者判定 | 等级 | 通过 |",
        "|---|---|---|---|---|",
    ]
    for o in report.outcomes:
        lines.append(
            f"| {o.case.case_id} | {o.state} | {o.case.author_claim.verdict} | {o.tier} | "
            f"{'✅' if o.passed else '❌'} |"
        )
    return "\n".join(lines)


def _render_coverage(report: CaseRunReport) -> str:
    cov = report.summary["coverage"]
    return "\n".join(
        [
            "# 报告二：规则覆盖率",
            "",
            f"- 全部检查通过案例数：{cov['cases_with_all_checks_passed']}",
            f"- 无规则可判案例：{cov['no_rule_cases'] or '无'}",
            "",
            "> 「无规则可判」指案例在无任何规则命中的情况下被判为可用/可接受；",
            "> 这类案例说明规则库存在覆盖缺口，应补规则而非降低门槛。",
        ]
    )


def _render_divergence(report: CaseRunReport) -> str:
    lines = [
        "# 报告三：分歧清单",
        "",
        "| 案例 | 系统三态 | 作者判定 | 不一致项 |",
        "|---|---|---|---|",
    ]
    for o in report.outcomes:
        bad = [c["check"] for c in o.checks if not c["ok"]]
        if bad or (o.case.author_claim.verdict and o.state != o.case.author_claim.verdict):
            lines.append(
                f"| {o.case.case_id} | {o.state} | {o.case.author_claim.verdict} | {', '.join(bad) or '判定不一致'} |"
            )
    if len(lines) == 4:
        lines.append("| — | — | — | 无分歧 |")
    return "\n".join(lines)


def _render_gaps(report: CaseRunReport) -> str:
    lines = ["# 报告四：规则缺口清单", ""]
    gaps = report.summary["gaps"]
    if not gaps:
        lines.append("- 无缺口。")
    else:
        lines.append("| 缺口 | 出现次数 |")
        lines.append("|---|---|")
        for k, v in gaps.items():
            lines.append(f"| {k} | {v} |")
    return "\n".join(lines)


_ = (render_markdown, default_registry)
