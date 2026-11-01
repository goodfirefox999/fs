# ADR-0008：strictness 三档语义与 severity 按派别覆盖

- 状态：已采纳
- 日期：2026-11-01
- 决策者：评审意见（2026-11-01）+ 实现者
- 触发：评审指出「`strictness` 目前是什么语义必须钉死」与
  「同一条规则在不同流派下 severity 可能不同，规则库是否支持覆盖」。

## 背景

原实现的 `strictness` 只用于 `applies_to.strictness_min` 过滤（strict 档多启用几条加严规则），
**没有定义它对 tier 的影响**。同时规则只有单一 `severity`，无法表达
"三煞在严格派是否决、在宽派是强忌"。

## 决策一：strictness 三档语义

| 档位 | 断言级 `慎用` 命中 | 定义级结构 `慎用` 命中 | `strictness_min=strict` 规则 |
|---|---|---|---|
| `strict` | **升级为否决** → state=不可用 / tier=REJECTED | 仍为存疑（结构不因严格档变成不可用） | 启用 |
| `normal`（默认） | 存疑 → tier=NEEDS_REVIEW | 存疑 | 不启用 |
| `loose` | 降为提示，不改变 state | 存疑（结构事实与档位无关） | 不启用 |

**关键取舍**：`strict` 只升级**断言级**强忌，不升级**定义级**结构。
理由：结构事实回答"是什么"，不回答"好不好"；把它升级为否决等于让"事实"产生吉凶后果，
违反 ADR-0007 的分层原则。

> 与评审建议的差异：评审建议 `normal` 档"强忌命中降为 ACCEPTABLE 但标注"。
> 本实现保留 `normal` = 存疑（NEEDS_REVIEW），因为三态里的"存疑"需要一个明确触发条件；
> 若 normal 直接降到 ACCEPTABLE，"存疑"就只剩 unknown 一个来源，三态退化为两态。
> 该差异已在此记录，可由人类裁定推翻。

## 决策二：severity 按派别覆盖

规则新增可选字段：

```yaml
severity: 禁用            # 默认严重度
severity_overrides:
  zhengwuxing: 慎用       # 正五行派下降为强忌
  doushou: 可用           # 斗首派下仅作参考
```

引擎在 `_evaluate_school` 里用 `rule.severity_for(school)` 取实际严重度。
加载期校验：

- `severity_overrides` 必须是 `{school: severity}` 映射；
- 值必须在 `SEVERITIES` 枚举内；
- veto 规则的覆盖值只能是 `禁用/慎用`（不得把否决降成"推荐"）。

## 后果

- ✅ `strictness` 有了可验证的行为差异（`test_v2_features.py::TestStrictness` 三档各一测）。
- ✅ 多流派可以在**同一条规则**上表达严重度分歧，而不必复制规则。
- ✅ `policy_divergence` 冲突检测现在能捕捉"严重度分歧"（原先只能捕捉"命中与否"）。
- ⚠️ `severity_overrides` 是新的攻击面：若某派把否决降为"可用"，等于架空否决层。
  已用加载期校验 + `test_v2_features.py::TestSeverityOverrides` 双重约束。
- ⚠️ `loose` 档目前无 CLI 入口（`--strictness` 只接受 normal/strict），
  因为"loose"在实务中风险高；如需启用应显式加参数并保留报告警示。
