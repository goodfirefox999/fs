# ADR-0015：共识度用整数比，不用加权总分

- 状态：已采纳（2026-11-02）
- 取代：无
- 影响面：`core-eval/engine.py`（共识与 tier）、`core-eval/ranker.py`（排序键）、
  `core-rule/config/consensus.yaml`（新）、`app-zeri/report.py`（共识节）

## 背景

评审发现一份"多派共识择日"设计稿在最后一公里自我否决：
它在第 0 节禁止"把门派分数加权求和"，却在第 5.2 节给出

```
consensus_score = w1*方向 + 0.3*Borda归一 + 0.3*同向率 - 冲突罚分
```

这是同一个错误的改名版：权重是拍的、量纲是混的、累加后仍是"综合分"。
更隐蔽的是 **Borda**：它对"该派在本候选上无判定"的情形无法赋值，
若用中间名次补齐，等于替沉默派投了一张中立票。

仓库当时的实际状态也不干净：

| 位置 | 形态 | 问题 |
|---|---|---|
| `ranker.sort_key` 末位 | `-_mean_rank_score(ev)` | 各派 `rank_score` 的跨派均值 |
| `engine` tier 推导 | `_total_rank(per_school) >= 1.0` | 同一个跨派均值 |
| `engine` 共识判定 | `favorable_count >= 3` | magic number，分母隐含为固定 5 |
| 共识输出 | `_consensus: str` | 只有结论，没有"谁投票、谁没投、为什么" |

## 决策

1. **共识度 = 整数比** `consensus_ratio = "favorable/voters"`，全程整数交叉相乘判定：
   `favorable * den >= num * voters`。不产生任何浮点字段，下游无从加权。
2. **阈值外置**：`core-rule/config/consensus.yaml` 的 `min_agree_num` / `min_agree_den`，
   可按事项覆写。加载器拒绝浮点值（`0.6` 直接报错），从类型上堵死"顺手乘个权重"。
3. **投票分账**：
   - `layer: reject`（闸门）**只否决不计票**，一否决即 `unfavorable`；
   - `layer: reference`（参考层，如斗首）**不参与仲裁**；
   - `scoring` 层但本轮无任何判定者为**沉默派**，**不进分母**。
   三者一律进 `non_voters`，带 `reason`（`layer_reject` / `layer_reference` / `no_verdict`）。
4. **排序键末位改为整数计数** `-positive_count`（正向命中条数），不是分值。
5. **删掉 tier 推导里的 `_total_rank`**。附带说明：规则 `score_weight` 上限 1.0、
   分母为派数，该分支在 `positive >= 1` 时恒不能单独成立，删除不改变可达分布。
6. **机器强制**：`tools/check_no_aggregate_score.py`（C20）扫描 `core-eval/src`
   与 `app-zeri/src`，禁止 `/ len(...)`、`statistics.mean` 类调用、以及重建
   `mean/average` 命名的函数；豁免须写 `# lint-exempt: <理由>`（≥8 字），
   可用 `--list` 逐个复核。

## 为什么不选 Borda

- **覆盖率依赖**：Borda 要求每个引擎对同一批候选给出全序；某派在某候选无判定时
  (`rank_score=None`) 就无法赋值。候选越多、规则越稀，缺失越密。
- **尺度不可比**：三合的内部名次与斗首的内部名次之间没有共同单位。
- **沉默≠中立**：补齐缺失名次会系统性地把"没意见"算成"中间态度"，
  在 5 派里足以翻转结论。
- 本项目真正需要的不是"谁更吉"的排序，而是**"几成派别同向 + 谁反对 + 谁没表态"**，
  这恰好是整数能表达的东西。

## 后果

- 报告「共识度」节只出现 `4/5 同向（阈值 3/5）` 与两份名单，不再出现任何分值。
- `consensus_dates` 的判据随配置变化，报告必须回显本次阈值（已回显）。
- 五派全表态时，缺省 `3/5` 与旧口径 `favorable_count >= 3` **完全等价**；
  某派沉默时，分母缩小（旧口径会把它当成"没投赞成"而变相要求更高票数）。
- 事项级阈值表当前**留空**：不同事项该几成同向属术数口径，须人工裁定后填入。

## 验证

| 断言 | 锚点 |
|---|---|
| 均值会报警 | `tests/unit/test_no_aggregate_score_lint.py::TestDetectsAggregateMean` |
| 去掉除法即沉默（反证） | 同上 `test_same_sample_without_division_is_silent` |
| `sum(len(...))` 计数不误杀 | 同上 `test_integer_count_of_rules_is_allowed` |
| `sort_key` 无除法/无均值 | 同上 `test_sort_key_contains_no_division_and_no_mean` |
| 仓库无未豁免均值 | 同上 `test_repository_has_no_unexempted_mean` |
| 阈值拒绝浮点 | `core_rule.policy.load_consensus_config` 的 `DSLValidationError` |
| 整数比判定 | `tests/unit/test_consensus_ratio.py` |
| 报告只出整数比 | `tests/unit/test_report_consensus_section.py` |
