# 天星 4 条规则的影子观察方案（2026-11-03）

> 状态：**待人类批准后执行**。本文件定义"观察什么、观察多久、什么条件下才算数"，
> 防止"走影子观察"变成无限期搁置。
> 关联：`AGENTS.md` 硬禁止第 8/9 条、`docs/QUESTIONS.md` Q-014 之后的 C 路线。

## 一、为什么这 4 条要观察而不是直接翻

天星（`TX-JIAFU-001` / `TX-MOONDAO-001` / `TX-SANHEGONG-001` / `TX-SUNDAO-001`）
当前 `severity: 可用`、`hard_veto: false`、`status: 待考证`。

- 「可用」只进 `positives`，**不**进 vetoes/cautions；
- 但它会抬高 `positive_count`，从而**可能**把 tier 推到 `TIER_PREFERRED`；
- 也就是说：它不是"没影响"，而是"只往好的方向影响"。

把它改成 `engine_eligible: false` 等于**取消这份正向影响**，属结论强度变更。
按 `AGENTS.md` 第 8/9 条，不能直接翻，要走影子观察。

## 二、观察指标（三项，都是可机器算的）

以**同一批候选**（`gen --window` 一个月、`--top 20`、五派默认路由）为样本，
分别用「天星 eligible」与「天星 shadow」两套配置各跑一遍，比较：

| # | 指标 | 定义 | 记录方式 |
|---|---|---|---|
| M1 | `TIER_PREFERRED` 变化率 | `(P_eligible − P_shadow) / max(P_shadow, 1)`，P = 该 tier 的候选数 | 报告 manifest 增 `shadow_compare.tier_counts` |
| M2 | `state` 分布变化 | 各 state（可用/存疑/不可用）计数差，用**绝对差**而非比率（分母可能为 0） | 同上 |
| M3 | 与 vote 引擎同向率 | 取两套配置都给出 `positives` 的候选，计算天星命中与其余派别多数方向的一致率 | 需在对比脚本里算，输出到 `out/shadow/tianxing.json` |

**为什么是这三项**：M1 直接量化"正向影响有多大"；M2 防止出现"tier 没动但 state 翻了"
的暗改；M3 检验"天星到底是不是在说别人已经说过的话"——若同向率极高，它提供的
是冗余而非信息，那就更没有理由让它投票。

## 三、观察周期与样本量

- 一个发布周期，**或**累计 120 个真实案例（先到者为准）；
- 每个案例必须来自真实输入（非 RT 向量、非 bench 窗口）；
- 每 30 个案例出一份中间报告，避免最后一次性发现口径不对。

> 120 这个数字不是拍的：按当前 `gen` 的候选规模（单月 ≈ 4380 编排候选），
> 一个月窗口就足以覆盖 12 个月建 × 24 山 × 60 日的基本组合，
> 再多也不会增加结论稳定性，只会拖长观察期。

## 四、升级 / 不升级的判定

**升级为 `vote`（恢复参与）** 需同时满足：

1. M1 < 5%：天星的正向影响没有把 `TIER_PREFERRED` 显著推高；
2. M2 各 state 绝对差 ≤ 样本的 2%：没有出现"tier 没动但 state 翻了"；
3. M3 同向率不显著下降（与观察期前 30 个案例的基线相比，降幅 < 5 个百分点）；
4. 人工复核**零推翻**：抽查 20 个由天星单独支撑的 `PREFERRED` 候选，师傅判定无异议。

**保持 `engine_eligible: false`** 的情形（任一命中）：

- M1 ≥ 5%，或 M2 出现 state 翻转，或 M3 同向率下降 ≥ 5 个百分点；
- 人工复核推翻 ≥ 1 例；
- 观察期未满且样本 < 120。

保持关闭时，报告必须显式写：

> 天星仅参考，未参与投票。理由：星历精度未达闸门（紫气无对应、太阴短级数误差
> 0.24°–0.33°），且断法门派差异大。

## 五、落地顺序（不阻塞当前 C 合入）

1. 先在 `PUB-WUHUANG-PALACE-001` 上跑通影子语义（已完成：`tests/unit/test_shadow_rule.py`）；
2. 天星 4 条各加 `verdict_type: vote`、`engine_eligible: false`、
   `ineligible_reason: ephemeris_precision_below_gate`，并在 `notes` 写明观察期起止；
3. 加一个对比脚本 `tools/shadow_compare.py`（读两套配置 → 出 M1/M2/M3），
   本期不接线到 CI，先手工跑；
4. 观察期满后按第四节判定，**由人类签字**改 `engine_eligible`。

## 六、与 `verdict_type: null` 的关系（重要）

`null` 的语义必须是「**尚未归类**」，不能被自动推断成 vote/gate。当前 `models.py`
里有一个 `effective_verdict_type` 属性，会在 `verdict_type` 为空时按
`hard_veto and severity == "禁用"` 推断成 gate，其余推断成 vote——这与
"允许 null 表示未归类"直接冲突：

- 它让"没表态"看起来像"已表态"，等于隐式完成了一次未登记的语义归类；
- 报告无法区分"这条规则归类为 vote"和"这条规则没人管过"。

建议（**未应用，等热文件归属确认后再改**）：

1. `effective_verdict_type` 改为：`verdict_type` 为 `None` 时返回 `"unspecified"`，
   **不推断**；真正的路由继续按 `severity`/`hard_veto` 走（行为不变）；
2. `rules lint` 增两条**条件**约束：
   - `verdict_type == "vote"` → 必须存在参与排序的路径（当前为 `score_weight` 或
     positives 路由），否则报"声明为投票但无投票通道"；
   - `verdict_type == "gate"` → 必须 `hard_veto: true`，且 `score_weight` 必须为空
     （闸门不参与打分）；
   - `null` → 不参与上述校验，但计入 `verdict_type_unspecified: N` 机器行，
     并在报告"未归类"节列出——**显式承认还没想好**。
3. 迁移只给已有明确行为的规则填值，其余留 `null`，清单落
   `core-rule/config/verdict_type_backlog.yaml`（含每条的"为什么还没归类"）。

> 这一条的意义：把隐式约定变显式，**包括把"还没想好"也显式化**。
> 强制二选一会制造 75 次未登记的语义变更，比留空更危险。
