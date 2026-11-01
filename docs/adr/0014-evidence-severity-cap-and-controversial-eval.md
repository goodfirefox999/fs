# ADR-0014：证据等级→否决力上限（D6' 不变式）、存疑不压 tier、有争议规则默认可评估

- 状态：**已补订**（2026-11-01 第八轮验收单逐条落实，见文末对照表；终审按验收单对照即可批准施工，
  不需再看全文。**不得先码后审**。）
- 考证周期计数锚点（ADR-0013 D3）：仓库基线提交（git 首个 commit，含本 ADR）。
- 触发：
  - D6 只排"有争议"不排"待考证"——五黄在 strict 档下仍被升级（评审第五轮）
  - "待考证→MEDIUM_AVOID 上限"不可执行——tier 分量与 severity 词汇错位（评审第六轮）
  - ADR-0013 D1"保留为参考层慎用提示"只在 `--allow-unverified` 下成立（评审第五轮）
  - 存疑慎用压 tier 的设计张力未决（评审第七/八轮 → 决策 0）

## 决策 0：存疑慎用不参与 tier（**甲案，已勾选**）

有争议规则的命中计入**独立计数** `controversial_caution_count`（新增向量），只渲染提示，
**不进 cautions / strong_avoid，不改 tier**。理由：

1. cap 已剥夺其否决力，而 tier 是"否决力的另一种表达"——参考层不该有压 tier 的力量（D1 精神）；
2. H1/H2 未裁定期间，未裁定条件不得影响结论强度；
3. 与 ADR-0009 定义级分离原则同构："结构事实回答是什么，不回答好不好"；
   存疑命中回答"原文与建模的张力"，同样不回答好不好。

**连带红利**：默认档 tier 迁移按构造为零——C16 的 tier 迁移矩阵从风险评估降为**确认型 diff**
（非对角迁移非零即 bug），见 S2/C16。

## 决策 1：证据等级→否决力上限映射表（D6' 不变式）

| status | 生效 severity 上限（引擎强制） | veto 资格（**需同时 hard_veto: true**） | strict 升级 |
|---|---|---|---|
| 已考证 | 无上限（可达禁用） | 有 | 有 |
| 定义级 | 记录（固定，ADR-0009 白名单） | 无 | 无 |
| 有争议 | 慎用 | 无 | 无 |
| 待考证 | 慎用 | 无 | 无 |

- **不变式**：`strict 只强化"已确定"的判断`——升级条件要求 `status == "已考证"`；
  生效 severity 按映射表 cap。原 D6 的 `!= "有争议"` 特例删除（ADR-0013 已标 superseded）。
- **词汇修正记录**：MEDIUM_AVOID 是 tier 分量非 severity；待考证与有争议同档"慎用"。
- **cap 用 rank 比较，不用 `== "禁用"` 特判**：
  `effective = min(声明 severity, 上限[status], key=SEVERITY_RANK)`——声明低于上限时原样保留。
- **veto 显式守卫**：veto 分支条件改为 `effective_severity(rule) == "禁用" and rule.hard_veto`，
  不依赖"cap 后天然安全"的推导。
- **声明/生效双显示**：报告与 lint 同时输出 declared severity 与 effective severity
  （YAML 写禁用、引擎跑慎用，审计链不能断）。
- **severity 字段语义 = 考证后的目标值**：YAML 零迁移；lint 对声明>上限加 warning
  （预期命中：SANSHA-001/002、SUIPO、WUHUANG、YUEPO、CHONGSHAN 共 6 条待考证+禁用，属预期非 bug）。

**cap 单一来源模块**（engine / lint / 报告三处共用，不得出现第四处判断点）：

```python
# core-rule/src/core_rule/severity_cap.py
SEVERITY_RANK = {"推荐": 0, "可用": 1, "慎用": 2, "禁用": 3}   # 越大越强
CAP_BY_STATUS = {"已考证": "禁用", "定义级": "记录", "有争议": "慎用", "待考证": "慎用"}

def effective_severity(rule) -> str:
    """生效严重度 = min_by_rank(声明, status 上限)。RuleSet 构建期调用并缓存于 Rule。"""

def cap_warning(rule) -> str | None:
    """声明>上限时分 status 文案；run 级聚合，不进 per-candidate 循环。"""
```

调用点：① RuleSet 构建期（loader/registry）预计算并缓存于 Rule；② engine 的 veto/strict
分支读缓存值；③ lint（C15）与报告（双显示）调同一函数。
**性能要求**：effective severity load 期预计算；cap 警告按 run 聚合。
**demo 例外**：`demo_veto=True` 的演示路由读**声明** severity（联调例外，显式注释，见决策 3）。

## 决策 2：可行动性必须结构化——`source_status` 字段

否决力同档 ≠ 信息价值相同（unknown 三分类教训，不得换位复发）。**文本级区分不可消费**：
JSON 下游（PDF/API/测试）只能字符串匹配中文文案，文案一改测试就碎。

- `Judgment`/`EvaluationItem` 新增 `source_status: verified | controversial | unverified | definitional`；
- participation 用稳定机器 token：`participation="判定"` + 新增 `doubt: bool` 字段
  （"判定（存疑）"只是渲染层括注）；
- cap warning 文本只是 `source_status` 的渲染，不是替代；
- T6/T7 用结构化断言（`source_status == "unverified"`），禁止中文子串匹配。

## 决策 3：演示语义三态化（渲染恒开；计入由 `demo_veto` 控制）

| 维度 | 要求 |
|---|---|
| 渲染 | 演示命中**始终渲染**（独立表「演示命中（不作为排除依据）」），不受开关影响——排考证优先级的雷达，关掉即自废 |
| 计入 state/tier | 由 `EvalConfig.demo_veto` 控制，**默认 False（不计入）**；True 时按**声明** severity 路由（禁用+hard_veto→演示否决进 vetoes；慎用→cautions），participation=演示 |
| 开启标注 | `demo_veto=True` 时报告首行显著标注「含演示否决，结论不可作为发布依据」+ `demo_evaluated` 标记 |
| CLI 依赖校验 | `--demo-veto` 必须依赖 `--allow-unverified`；单独给出 → **exit≠0**（`invalid_flag_combination`），不静默忽略、不隐式启用 |

与 cap 的交互：cap 只约束"判定/判定（存疑）"路径；演示路由是显式联调例外（读声明 severity）。
`test_demo_not_rendered_as_definite` 改用 `demo_veto=True` 验证渲染区分，语义不改写。

## 决策 4：severity=慎用 在 tier 中的位置（代码已定）+ 决策 0 分流

代码事实：`engine.py:291` 慎用命中计入 `strong_avoid_count`；`engine.py:885-888`
`strong_avoid>0 → TIER_NEEDS_REVIEW`（永不到 ACCEPTABLE/PREFERRED）。

按决策 0 分流后：**strong_avoid 仅来自已考证/定义级的慎用命中**；
有争议命中 → `controversial_caution_count`（渲染，不进 885-888 的任何分支）；
待考证 demo 命中 → demo_veto=False 时不计入。loose 档慎用进 notes（既有行为，保持）。

## 决策 5：strict 能力未激活——动态统计 + 与 publishable 合并渲染

- 「无已考证规则可升级」由引擎**动态统计**（`verified_rule_count == 0` 时显示，>0 自动消失），
  不写死字符串——P0 考证完成后自动失效。
- 与 `publishable=false` 的理由**合并渲染**为统一"未激活状态"块（两个未激活叠在一起，
  用户不应自己拼因果）：

```text
当前状态：
- publishable=false：必需集 8 条中 0 条已考证（阻塞项见上表）
- strict 档未激活：已考证规则 0 条，从严能力待 P0 考证完成后生效
- 共同原因：P0 考证未完成；补完必需集原文后，publishable 与 strict 同时解锁
```

## 状态跃迁提权（原则级，引用既有实现 + lint 纵深）

待考证 → 已考证 必须 `verified_by` 非空：loader 硬校验已实现（`loader.py:199-202`，
无签名拒绝加载）；lint 层保留对应 error 作纵深（已有"已考证必须有完整引文"检查）。
Agent 不得代签（AGENTS.md 第 1 条）。

## 落地清单（终审批准后一次 PR）

| # | 项 | 文件 |
|---|---|---|
| C11 | `severity_cap.py` 单一来源模块 + RuleSet 构建期预计算缓存 | `core-rule/src/core_rule/severity_cap.py`、`loader.py` |
| C12 | engine：veto 显式守卫 + strict 不变式 + 决策 0 分流（controversial 计数）+ doubt 字段 | `core-eval/src/core_eval/engine.py` |
| C13 | `EvalConfig.demo_veto`（默认 False）+ CLI `--demo-veto` 依赖校验（exit≠0） | `core-eval`、`app-zeri/cli.py` |
| C14 | 统一"未激活状态"块（动态统计 + 与 publishable 合并渲染；并入 C9） | `app-zeri/report.py` |
| C15 | lint：声明/生效双显示 + 声明>上限 warning（6 条预期命中） | `app-zeri/cli.py` |
| C16 | tier 迁移**确认型**矩阵脚本：12 个月 × 3–4 坐向窗口集，默认档期望零非对角迁移，非零即 bug | `tools/` |
| C17 | publishable 不变式测试（T12）配套 | tests/golden |
| T6 | 五黄 strict（allow_unverified + demo_veto=False）命中：source_status=="unverified"、不在 vetoes/cautions、演示表渲染、cap_warning 存在 | tests/golden |
| T7 | 003 默认档命中：participation=="判定"、doubt is True、source_status=="controversial"、不在 vetoes/cautions、**tier 与无 003 对照 run 相同** | tests/golden |
| T8 | 已考证+禁用 strict → 仍进 vetoes（不变式回归） | tests/golden |
| T9 | E2E：向三煞日课（2026 丙午、坐巳向亥）CLI verify 默认档 → 报告含 003 慎用提示（结构化字段断言）、无"不可用"类目、tier 不因 003 改变 | tests/golden |
| T10 | `select()`：有争议默认选入、待考证不选入 | tests/unit |
| T11 | `demo_veto=True`（+allow_unverified）→ 演示否决进 vetoes、REJECTED 可达、首行标注；单独 `--demo-veto` → exit≠0 | tests/golden + CLI |
| T12 | publishable 不变式：003 命中时 publishable/required_blockers 与无 003 对照 run 完全一致 | tests/golden |
| S2 | gen 冒烟 diff 验收标准（**枚举合法变化来源**）：(a) 演示否决在 demo_veto=False 下的否决→非否决迁移；(b) 有争议默认参与产生的**渲染层**新增慎用项（甲案下不动 tier）。其他变化 → 失败。同时记录 perf 数字，判定用相对基线劣化百分比（绝对秒数换机器即假失败） | out/、`tools/` |

## 与 ADR-0012 / 0013 的关系

- ADR-0012 准入四条不变；`required_blockers` 走 status，不受 cap 与决策 0 影响
  （**publishable 语义不变**——必需集里的待考证规则靠"未考证"阻塞发布）。
- ADR-0013 D6 已标 **superseded by 本 ADR**（不静默改写）；D1"参考层慎用提示"由 C12
  兑现为默认行为，且按决策 0 不携带 tier 影响。

---

## 附：第八轮验收单对照

| 验收项 | 处置 |
|---|---|
| 第一节勾选（甲/乙） | 甲，见决策 0 |
| 第二节三态化 | 见决策 3（渲染恒开/计入受控/开启标注/CLI 依赖校验） |
| 1 veto 需同时 hard_veto | §一表格注明 |
| 2 cap 用 rank 比较 | §一 + severity_cap.py |
| 3 veto 显式守卫 | §一 + C12 |
| 4 声明/生效双显示 | §一 + C15 |
| 5 lint 声明>上限 warn（6 条预期） | §一 + C15 |
| 6 cap 单一来源三处共用 | §一 severity_cap.py |
| 7 load 期预计算 + run 级聚合 | §一 性能要求 |
| 8 participation 机器 token | §二 doubt 字段 |
| 9 状态跃迁提权 | 「状态跃迁提权」节（loader 既有 + lint 纵深） |
| 10 ADR-0013 D6 标 superseded | 已在 ADR-0013 落注 |
| 11 决策 5 动态统计 | §决策 5 |
| 缺口 1 tier 迁移矩阵 | C16（甲案下降为确认型） |
| 缺口 2 publishable 不变式 | C17/T12 |
| 缺口 3 perf 相对基线 + git 锚点 | S2 + 本文头部锚点（基线提交） |
| Q-012 向首 fact 前置工程项 | 已更新 ADR-0013 联动表（补齐前必需集维持 8） |
