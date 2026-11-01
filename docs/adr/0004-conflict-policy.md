# ADR-0004：派别冲突策略——只呈现，不裁定

- 状态：已采纳
- 日期：2026-11-01
- 决策者：实现者（Agent），待人类复核

## 背景

同一日课在不同通书/流派下可以有不同结论。上游规格明确要求"多流派并存，冲突输出 CONFLICT，
不得伪造共识"，但未定义冲突的**判定口径**。

## 决策

定义三类冲突，全部**只登记、不裁定**：

| 类型 | 触发条件 | 语义 |
|---|---|---|
| `verdict_conflict` | 一派 state=不可用，另一派 state=可用 | 结论互斥，最严重 |
| `state_divergence` | 任意两派 state 不同（但非互斥） | 一般分歧，需并列呈现 |
| `policy_divergence` | 同一 category 在不同派别下 severity 不同 | 口径分歧（规则层面的差异） |

1. 冲突进入 `Evaluation.conflicts`，并计入 `vectors.conflict_count`。
2. `conflict_count > 0` 使 `tier` 至少为 `NEEDS_REVIEW`。
3. 报告必须**并列展示各派三态**，不得只显示综合结论。
4. `school_policy.yaml` 的 `participates_in_veto` 决定某派的"禁用"规则是否真的能否决；
   不参与否决的派（斗首、玄空）其禁用规则降级为 `note`。

## 理由

- 裁定"哪派对"属于考证者职责（见 AGENTS.md 角色表），Agent 不得代劳。
- 只呈现冲突，使用者（从业者）才能看到"这套规则在哪些点上不一致"，这正是产品的核心价值。
- 若强行裁定（如"取最严"），会掩盖真实分歧，属于"伪造共识"。

## 后果

- ✅ 金标准案例中 `public=存疑` vs `zhengwuxing=可用` 被正确标为 `state_divergence`。
- ⚠️ 冲突数量可能很多（派别越多越明显），报告需分页/折叠展示。
- ⚠️ "未时天德 vs 勾陈"这类**具体规则级**冲突，需要先有那两条规则才能检出；
  当前规则库缺这两条（无原文依据），已登记 `QUESTION-003`。

## 相关

- `core-eval/engine.py::_detect_conflicts`
- `tests/golden/test_golden_case.py::test_hour_divergence_is_conflict`
