"""证据等级 → 严重度上限（ADR-0014 决策 1）—— **单一来源**。

engine（评估路由）、lint（声明/生效双显示）、report（审计链）三处共用本模块，
**不得**在任何其它位置重复实现 cap 判断（评审第八轮第 6 条）。

映射表（全部使用项目 severity 词汇；MEDIUM_AVOID 是 tier 分量，不可执行——评审第六轮）：

=====  =======  =====================
status  生效上限  说明
=====  =======  =====================
已考证  禁用     无上限（唯一可当发布门槛）
定义级  记录     ADR-0009 白名单
有争议  慎用     口径存疑，不得有结论强度
待考证  慎用     未考证/未签名，与有争议同档
=====  =======  =====================
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:  # pragma: no cover - 仅类型标注
    from .models import Rule

#: 严重度强度序（越大越强；「记录」为定义级专用，无吉凶强度，与推荐同档）
SEVERITY_RANK: Mapping[str, int] = {"推荐": 0, "可用": 1, "慎用": 2, "禁用": 3, "记录": 0}

#: 各 status 的生效严重度上限（rank 语义）
CAP_BY_STATUS: Mapping[str, str] = {
    "已考证": "禁用",
    "定义级": "记录",
    "有争议": "慎用",
    "待考证": "慎用",
}


def cap_severity(severity: str, status: str) -> str:
    """生效严重度 = min_by_rank(声明, status 上限)。

    声明低于上限时**原样保留**（rank 比较，而非 ``== "禁用"`` 特判——评审第八轮第 2 条）。
    """
    cap = CAP_BY_STATUS.get(status)
    if cap is None:
        return severity
    if SEVERITY_RANK.get(severity, 0) <= SEVERITY_RANK[cap]:
        return severity
    return cap


def effective_severity(rule: "Rule") -> str:
    """规则的生效严重度（声明经 status 上限 cap 后）。"""
    return cap_severity(rule.severity, rule.status)


def participates_in_tier(rule: "Rule") -> bool:
    """甲案不变式（ADR-0014 决策 0）：计入 strong_avoid/tier 的慎用必须 status=已考证。

    凡被 cap 压下来的规则（有争议/待考证）不得影响结论强度；
    ``demo_veto=True`` 的演示路径是显式联调例外（按声明 severity 路由，participation=演示）。
    """
    return rule.status == "已考证"


def cap_warning(rule: "Rule") -> str | None:
    """声明>上限时的分 status 文案；调用方按 run 聚合，**不进 per-candidate 循环**。"""
    eff = effective_severity(rule)
    if eff == rule.severity:
        return None
    kind = "口径存疑，引文见 citation" if rule.status == "有争议" else "未考证，无引文可核"
    return (
        f"{rule.rule_id}: 声明 severity={rule.severity} → 生效 {eff}"
        f"（{kind}；ADR-0014 上限，考证签名后自动恢复）"
    )
