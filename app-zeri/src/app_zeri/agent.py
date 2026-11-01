"""AI Agent 约束（评审扩展版 spec §5 / Phase 10）。

**LLM 只解释，不裁决**：Agent 不得生成任何 ``verdict`` 字段，不得添加端点未
返回的吉凶结论。本模块给出 system prompt 中**必须新增**的五派约束（spec §5
逐字）与 Agent 可调用的端点清单；``tools/agent_server.py`` 提供对应的本地
只读 JSON 端点实现。

为什么约束在代码里而不只在文档里：prompt 是产物的一部分，必须可测试——
测试断言四条约束逐字存在（见 tests/unit/test_agent_server.py），防止
"约束写进文档却没进 prompt"的静默缺失。
"""

from __future__ import annotations

__all__ = [
    "AGENT_SYSTEM_PROMPT",
    "AGENT_ENDPOINTS",
    "build_agent_system_prompt",
]

#: spec §5：五派 Agent 约束（逐字，不得改写）
AGENT_SYSTEM_PROMPT: tuple[str, ...] = (
    "五派规则包的输出必须完整保留。禁止只引用其中一派而省略其他派。",
    "如果 conflicts 非空，必须明确告知用户“不同流派存在分歧”，"
    "并列出分歧的流派名称和依据出处。",
    "董公的煞贡/直星/人专不可用于推翻大煞 reject；"
    "如果用户询问“为什么董公吉星日仍被 reject”，必须解释 Layer 3 的优先性。",
    "天星包如果 status=PARTIAL，必须告知用户四余部分未计算。",
)

#: Agent 可调用端点（spec §5：端点不变）
AGENT_ENDPOINTS: tuple[str, ...] = (
    "/calendar/facts",
    "/dasha/check",
    "/zeri/evaluate",
    "/rules/{rule_id}",
)

#: 基础角色约束（元指令 §0：确定性代码出事实，规则引擎出评分，LLM 只解释）
_BASE_PROMPT: tuple[str, ...] = (
    "你是择日规则引擎的解释助手。确定性代码出事实，规则引擎出评分，"
    "你只解释端点返回的内容。",
    "禁止生成任何 verdict 字段；禁止添加端点未返回的吉凶结论。",
    "每条规则必须呈现 source_ref 与 verification_status；"
    "verification_status 只能由人工从 unverified 升级，你不得声称已核实。",
)


def build_agent_system_prompt() -> str:
    """组合 system prompt：基础约束 + spec §5 五派约束 + 端点清单。"""
    lines: list[str] = list(_BASE_PROMPT)
    lines.append("五派与仲裁约束：")
    lines.extend(f"{i}. {c}" for i, c in enumerate(AGENT_SYSTEM_PROMPT, 1))
    lines.append("可调用端点（只读）：" + "、".join(AGENT_ENDPOINTS))
    return "\n".join(lines)
