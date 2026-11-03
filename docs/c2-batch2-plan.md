# C 第二批（verdict_type 标注）启动方案

> 状态：**D 桶已落（12 条，2026-11-03）；C/E/F 等 Q-024**。
> D 桶判定零变更，已验证（`test_verdict_baseline` 75→63 + `test_d_bucket_annotation`
> before/after 决策面/输出面 + 全量 `make test-fast`）。
> 为什么不动：`models.py::effective_verdict_type` 的注释写明「未标注返回 `unspecified`，
> **不猜** `vote`」——批量套机械规则会把"没人管过"伪装成"已分类"，
> 正是这条设计要防的事。下面第三节给出三个反例，证明机械套用确实会错。

## 一、前提核验：75 条待标注规则**不依赖** `dead_rule_scan` 输出

结论：**不依赖**。三条证据（均可复跑）：

| 证据 | 命令 / 方法 | 结果 |
|---|---|---|
| 规则层不引用工具 | `inspect.getsource(core_rule.loader)` 搜 `dead_rule_scan` / `dead_rule_baseline` | 均 `False` |
| 两个基线是不同文件、不同消费者 | `dead_rule_baseline.yaml`（死规则分类）vs `verdict_baseline.yaml`（未标注计数） | 互不引用 |
| 标注来源是规则文件字段 | `Rule.verdict_type` 由 YAML 的 `verdict_type:` 读入 | 与工具输出无关 |

计数复核（2026-11-03）：

```text
总规则 86；verdict_type 未标注 75
按派：public 47 / doushou 6 / donggong 5 / zhengwuxing 5 / sanhe 4 / tianxing 4 / xuankong_dagua 4
```

与 `core-rule/config/verdict_baseline.yaml` 的 `unlabeled_count: 75` 及 `per_school` 完全一致。

**因此 Q-023（`dead_rule_scan` 里的 `F841 ctxs`、未用 `az` 循环）不构成 C 第二批的阻塞**：
那两处代码在工具内部，其语义不明只影响"死规则扫描结果是否可信"，
不影响"规则该标什么 verdict_type"。

## 二、75 条分桶（机械判据，仅用于**排序**，不用于直接落标）

> 快照口径：下表是 D 桶落标**前**的 75 条分布；D 桶 12 条已落标，当前余 63 条。

| 桶 | 判据 | 条数 | 拟标 | 是否可直接落 |
|---|---|---:|---|---|
| A | `evaluable=False` | 0 | — | — |
| B | `engine_eligible=False` | 0 | `reference` | 是（但当前无此类） |
| C | `status=定义级`（severity=记录） | 10 | `reference`？ | **否**，见 §3.1 |
| D | `hard_veto=True 且 severity=禁用` | 12 | `gate` | 是（**判定零变更**） |
| E | `severity ∈ {可用, 推荐}` | 24 | `vote`？ | **否**，见 §3.2 |
| F | `severity=慎用` | 29 | `vote`？ | **否**，见 §3.2 |

### D 桶（12 条，唯一可零风险先做）

`DG-DASHA-001`、`DG-JINSHEN-001`、`PUB-CHONGMING-001`、`PUB-CHONGSHAN-001`、
`PUB-MING-SANSHA-001`、`PUB-SANSHA-001`、`PUB-SANSHA-002`、`PUB-SIJUE-001`、
`PUB-SILI-001`、`PUB-SUIPO-001`、`PUB-WUHUANG-001`、`PUB-YUEPO-001`

为什么零风险：`effective_verdict_type` 对 `hard_veto=True + severity=禁用`
**已经推断为 `gate`**（`models.py:168` 的注释：这是定义级推断）。补显式只是把
推断变成声明，`effective_verdict_type` 的返回值不变、判定结论与 tier 不变
（报告的「未归类」清单会少这 12 条，见下）。
做完后 `unlabeled_count` 75 → 63，需同步下调 `verdict_baseline.yaml`。

**行为锁（2026-11-03 评审追加）**：`tests/unit/test_d_bucket_annotation.py`。
它复制规则库、删掉 12 条的显式字段做 before，断言：

- 12 条删掉显式字段后，`effective_verdict_type` 仍推断为 `gate`；
- 决策面（`_eval_summary`）与输出面（`_eval_output`）逐字节一致；
- 报告除两处元数据外逐字节一致：
  1. 「未归类规则」节少了这 12 条（落标的**目的**）；
  2. manifest 的 `rule_lib_version`（YAML 内容变了，内容哈希必变）。
- 「未归类清单减少的集合」恰好等于「本次评估命中的 D 桶规则」，多删/少删都红。

> 口径修正：完整报告**不是**逐字节一致。落标前这 12 条会在「未归类规则」节出现，
> 落标后消失——这是标注行为本身，不是判定行为。把这两处元数据归一化后，
> 其余报告文本必须逐字节一致；测试同时钉死唯一允许的差异集合。

### C/E/F 三桶（63 条）不能机械落标

## 三、三个反例：机械套用会标错

### 3.1 C 桶（定义级 10 条）：`reference` 还是"结构性判定"？

定义级规则（`DEF-*`）**参与**评估、进 `structural` 桶、计入 `structural_count`，
只是 `severity=记录` 不影响 tier。三种类型里它既不是 `gate` 也不是 `vote`，
但叫 `reference`（"只展示不判定"）又会低估它的确定性——
它恰恰是**唯一"确定"的那类结论**。

这是**分类学问题，不是规则问题**，需要人类定：定义级要不要第四种类型
（如 `structural`）？在定之前标 `reference` 会污染类型语义。
**已并入 Q-024**（2026-11-03 评审：与条件性 `verdict_type` 同属"单值枚举表达不了语义"，
合并裁定，避免拆成两个互相依赖的题）。

### 3.2 F 桶里混着"只标记不判定"的规则

| 规则 | 声明 severity | 实际语义（原文） | 机械判据会标成 | 应为 |
|---|---|---|---|---|
| `SH-CHONGSHAN-MARKER-001` | 慎用 | 「冲山/冲命已由 Layer 3 前置 reject……**本条仅输出标记，不重复评分**」 | `vote`（负向） | `reference` |
| `PUB-XIANGSHOU-001` | 慎用 | 「日课天干与命主关系需人工复核（**本规则仅作提示**）」 | `vote`（负向） | `reference` |

这两条按 severity 分桶必错。它们的存在说明：**`severity` 不是 `verdict_type` 的充分条件**——
severity 说的是"多重"，verdict_type 说的是"算不算票"。

### 3.3 E 桶里混着"吉凶方向靠分支"的规则

`DG-JIANCHU-001`（建除十二神）声明 `severity=可用`，但说明写「命中破/闭（一般不利）」——
同一条规则在不同命中上是正还是负，取决于命中的是"建/成/开"还是"破/闭"。
单一 `vote` 标注无法表达，需要先决定：拆成两条规则，还是允许 vote 带方向字段。

## 四、建议执行顺序

| 步 | 内容 | 前置 | 风险 |
|---|---|---|---|
| 1 | ✅ 已做：落 D 桶 12 条 `gate` + 下调棘轮 75→63 | 无 | 无（实测零变更） |
| 2 | 人类定 C 桶类型学（是否新增 `structural`）；**DG-JIANCHU 类走 Q-024** | 裁定 | 定错会污染类型语义 |
| 3 | 逐个复核 E/F 中"只标记/双向"的规则，改标 `reference` 或拆分 | 上一步 | 中 |
| 4 | 余下按 severity 落 `vote`，每批 ≤15 条，跑全量 + 棘轮 | 上一步 | 低 |

**不建议**一次标完 75 条：第 3 步之前，机械标注的错误率至少 2/75（§3.2 两条已确认），
且错误形态是"把不投票的规则标成投票"，会让共识分母虚高——正是 ADR-0015 要防的。

## 五、验收

- `unlabeled_count` 单调下降，`verdict_baseline.yaml` 同步；
- `docs/c2-migration-checklist.md` 勾选同步；
- 每批提交后 `make test-fast` + `make lint` 全绿；
- 报告里 `unspecified` 计数下降但**不为零**前，不得声称"标注完成"。
