# ADR-0014：证据等级→否决力上限（D6' 不变式）、存疑不压 tier、有争议规则默认可评估

- 状态：**已实施**（2026-11-01 第九轮批准施工，同日完成；验收数据见文末"施工验收"节）
- 考证周期计数锚点（ADR-0013 D3）：tag `baseline-pre-adr0014` = 提交 `eac493d`；
  D3 上限计量单位为**提交区间**（自该 tag 起），非 PR（仓库无 PR 流程，评审第九轮第 8 条）
- **锚点有效性约定（评审第十轮）**：本文所有 `文件:行号` 仅为 `db11804` 时点快照，
  主键是**文件 + 符号/标记注释**；标记由 `test_adr0014_anchor_markers_present` 机器校验，
  漂移即测试失败并提示更新本文。位置有效性以 `git log --follow <file>` 为准
- 触发：
  - D6 只排"有争议"不排"待考证"——五黄在 strict 档下仍被升级（评审第五轮）
  - "待考证→MEDIUM_AVOID 上限"不可执行——tier 分量与 severity 词汇错位（评审第六轮）
  - ADR-0013 D1"保留为参考层慎用提示"只在 `--allow-unverified` 下成立（评审第五轮）
  - 存疑慎用压 tier 的设计张力未决（评审第七/八轮 → 决策 0）

## 决策 0：存疑慎用不参与 tier（**甲案，已勾选并实施**）

有争议规则的命中计入**独立计数** `controversial_caution_count`，只渲染提示，
**不进 cautions / strong_avoid，不改 tier**。

**依据（评审第九轮改述，替换原"tier 是另一种表达"的错误论证）**：
存疑规则的**证据强度不足以支撑任何结论强度（含 tier）**。cap 剥夺的是否决资格，
甲案剥夺的是结论影响力——二者是同一原则（**未通过出处核查的规则不得影响判定结果**）
在两个维度上的体现。理由二（H1/H2 未裁定期间，未裁定条件不得影响结论强度）为决定性条；
理由三与 ADR-0009 为**精神一致**而非同构（定义级是"结构事实不含价值判断"，
存疑级是"价值判断未经核实"——不是同一件事，只是都指向"不进结论"）。

**不变式（与 cap 同一判据，不绑 status 列表——评审第九轮第 2 条）**：
> 产品判定路径（participation=判定）上，计入 strong_avoid/tier 的慎用必须
> `status == "已考证"`；等价表述：**凡被 cap 压下来的规则，其慎用不参与 tier**。
> 实现：`severity_cap.participates_in_tier(rule)`，engine 与 cap 共用单一来源。

**用户可见后果（评审第九轮第 1 条）**：甲案下用户会看到 `tier=ACCEPTABLE + 慎用（口径存疑）`。
报告必须将 tier 与 publishable **联合显示**（`report.py` 结论行本就同行渲染），并在存在存疑命中时
追加"暂不采信——tier 不变、publishable 兜底"提示，不得分置两处让用户只看一半。

**联调例外 scope**：`demo_veto=True` 时演示命中按**声明** severity 路由（含 strict 升级、
含慎用→否决），恢复旧渲染视图——该路径 participation=演示、报告首行标注"不可作为发布依据"，
不属于上述不变式的"产品判定路径"。

## 决策 1：证据等级→否决力上限映射表（D6' 不变式）

| status | 生效 severity 上限（引擎强制） | veto 资格（**需同时 hard_veto: true**） | strict 升级 |
|---|---|---|---|
| 已考证 | 无上限（可达禁用） | 有 | 有 |
| 定义级 | 记录（固定，ADR-0009 白名单） | 无 | 无 |
| 有争议 | 慎用 | 无 | 无 |
| 待考证 | 慎用 | 无 | 无 |

- **不变式**：`strict 只强化"已确定"的判断`——升级条件要求 `status == "已考证"`；
  原 D6 的 `!= "有争议"` 特例删除（ADR-0013 已标 superseded）。
- **词汇修正记录**：MEDIUM_AVOID 是 tier 分量非 severity；待考证与有争议同档"慎用"。
- **cap 用 rank 比较**（`SEVERITY_RANK`，含「记录」=0），非 `== "禁用"` 特判；
  声明低于上限时原样保留。
- **veto 显式守卫**：路由条件为 `route_severity == "禁用" and rule.hard_veto`，
  route_severity 已过 cap——不依赖推导链。
- **声明/生效双显示**：`Judgment.declared_severity` 字段 + 报告"声明/生效严重度差异"行 +
  lint 逐条 warning（审计链不能断）。
- **severity 字段语义 = 考证后的目标值**：YAML 零迁移。

**cap 单一来源模块**：`core-rule/src/core_rule/severity_cap.py`
（`cap_severity` / `effective_severity` / `participates_in_tier` / `cap_warning`）。
三处调用点（施工实测）：

| 调用点 | 符号主键（行号为 db11804 快照备注） |
|---|---|
| ① 评估路由 | `core_eval/engine.py::_evaluate_school`——标记注释「ADR-0014 决策 1：单一来源 cap」处（db11804 时 L618）；veto 守卫 `route_severity == "禁用" and rule.hard_veto`（L683）；strict 分支 `participates_in_tier(rule)`（L692） |
| ② lint | `app_zeri/cli.py::cmd_rules_lint` 第 10 节——标记「ADR-0014 决策 1：声明/生效双显示」（db11804 时 L287-289）+ 机器行 `cap_applied/unverified_progress/quote_unsigned`（评审第十轮分组化）；预计算 `core_rule/loader.py::RuleSet.__post_init__`（L63-68） |
| ③ 报告 | `app_zeri/report.py::render_markdown`——"声明/生效严重度差异"行（L247-250）；关联：`:201` demo_veto 首行标注、`:242` 存疑命中提示、`:312` 未激活合并块 |

**load 期预计算**：`RuleSet.cap_applied_ids`（`loader.py` `__post_init__` 派生，
dc_replace 自动重算）；cap 警告按 run 聚合，不进 per-candidate 循环。

**lint 机器行按 check id 分组（基线，测试按组断言精确集合——评审第九/十轮）**：

| check id | 基线精确集合 | 语义 |
|---|---|---|
| `cap_applied` | PUB-CHONGMING-001, PUB-CHONGSHAN-001, PUB-MING-SANSHA-001, PUB-SANSHA-001, PUB-SANSHA-002, PUB-SIJUE-001, PUB-SILI-001, PUB-SUIPO-001, PUB-WUHUANG-001, PUB-YUEPO-001（10 条，待考证+声明禁用） | **scope=all_rules**（勿拿必需集 8 对 10——评审第十一轮）；声明>上限，生效被 cap（随签名消失） |
| `unverified_progress` | 当前与 cap_applied **恰好同集**（10 条）——语义不同：必需集待考证进度提示，组内规则可带任何 severity | 必需集考证进度面板 |
| `quote_unsigned` | PUB-SANSHA-003, PUB-TAISUI-001（2 条） | 已录引文未经人类签名 |
| `coverage_gaps` | GAP-TAISUI-FACING（1 条） | 已知未覆盖原文硬禁（coverage_gaps.yaml，C18 完成自动消除） |

修正记录：第六轮稿"6 条"为漏计；第九轮稿"10 条"未区分 check id——两组当前同集属巧合
（所有待考证必需规则恰为禁用级），**集合断言按 check id 分别进行**
（`test_lint_check_id_groups_exact_sets`），状态变化时失败信息直接指出是哪组、哪条。

## 决策 2：可行动性必须结构化——`source_status` / `doubt` 字段

否决力同档 ≠ 信息价值相同（unknown 三分类教训）。**文本级区分不可消费**：

- `Judgment` 新增 `source_status: verified|controversial|unverified|definitional`、
  `doubt: bool`、`declared_severity: str|None`——**全部带默认值**（旧构造点/旧 JSON 兼容，
  序列化测试断言）。
  **与"EvaluationItem"的关系（评审问询的澄清）**：代码库中不存在独立的 EvaluationItem 类——
  评审所指的报告/JSON 条目对象即 `Judgment`（JSON 条目 = `Judgment.to_dict()` 输出），
  本变更为**同一对象增字段，非替换**；全仓 `Judgment(` 构造点仅 2 处
  （`engine.py::_make_judgment` + `tests/unit/test_v2_features.py:194` fixture），
  关键字默认值保证两处均无需改动。
- participation 保持稳定 token `"判定"`，存疑由 `doubt: true` 表达（"判定（存疑）"只是渲染括注）。
- cap warning 文本只是 `source_status` 的渲染；T6/T7 全部结构化断言，禁中文子串匹配。
- 双向验证：T6 同时断言渲染层正确生成文案（禁子串匹配不禁渲染回归）。

## 决策 3：演示语义三态化（渲染恒开；计入由 `demo_veto` 控制）

| 子项 | 状态 | 实现 |
|---|---|---|
| 渲染与开关解耦 | ✅ | 演示命中恒入 `demo_hits` 桶渲染（独立节）；`demo_veto=False` 时不入 vetoes/cautions/positives |
| CLI 依赖校验 | ✅ | `--demo-veto` 单独给出 → `cmd_verify`/`cmd_gen` 报错 **return 2**（不静默忽略）；T11 断言 |
| 开启时显著标注 | ✅ | `demo_veto=True` 报告**首行**"含演示否决……不可作为发布依据"（读 `manifest.config.demo_veto`） |
| 默认值断言 | ✅ | T13：`EvalConfig().demo_veto is False` |

- `demo_veto=True` 为显式联调例外：按**声明** severity 路由（禁用+hard_veto→演示否决、
  慎用→cautions、strict 升级照旧）——`case_runner` 案例库运行即走此视图（金标准期望不变）。
- `test_demo_not_rendered_as_definite` 语义不改写，加 `demo_veto=True` 配置（评审裁定）。

## 决策 4：severity=慎用 在 tier 中的位置（**已考证的**慎用命中）

代码事实：`engine.py` tier 派生 `strong_avoid>0 → NEEDS_REVIEW`；`strong_avoid = 断言级 cautions`。
按决策 0 分流后精确表述：**已考证的慎用命中计入 strong_avoid_count，tier 至多 NEEDS_REVIEW**；
有争议命中入 `controversial`（不入）；待考证 demo 命中 `demo_veto=False` 时不入。
（原稿漏"已考证的"限定，与决策 0 表面矛盾——评审第九轮第 2 条修正。）

## 决策 5：strict 能力未激活——动态统计 + 与 publishable 合并渲染

- 「无已考证规则可升级」由**动态统计**驱动（`verified_total == 0` 时显示，≥1 自动消失）——T15 断言。
- 与 `publishable=false` 合并为统一"当前状态（未激活项合并说明）"块：
  可发布=否（必需集 x/y 已考证）+ strict 未激活 + 共同原因行（report.py，仅 `not publishable` 分支）。

## 决策 6：非支配筛选的分组实现（perf 回归修复，评审第十一轮）

**触发**：`demo_veto=False` 改变了候选分布——基线时全候选 state=不可用 →
generator no_solution 短路，`pareto_front` 从未被调用；本 PR 后全候选 state=可用，
4380 个候选首次走进 O(n²) 逐对支配比较（1900 万次 ≈ 9s，A/B 实测 2.223s → 9.072s）。

**实现**：按 5 维向量分组，仅组代表间做支配筛选（O(u²)），`front.extend(全组)` 还原成员。
**等价条件（三条，缺一不成立）**：① `_dominates` 只读 5 维向量（`_vector_key` 即其完整输入）；
② 同向量候选互不支配（严格支配要求至少一维严格更优）→ 组内成员同命运；
③ 组间支配与代表间支配一致（支配是向量间的函数）。
**折叠处置**：成员**展开返回，不折叠**——下游 `rank(evals)` 独立排序全部候选，
`pareto_front` 的消费点仅 `pareto_size`（generator 统计 + report 显示规模）；
`test_pareto_grouped_equals_bruteforce` 用独立暴力 oracle 断言**成员 id 集合**相等
（非长度、非直方图），锁死展开实现。

**u 量化（2027 全年真实窗口实测）**：n=4380，**u=2**
（向量仅 (0,0,0,10,0)×2625 与 (0,0,0,11,0)×1755 两种，前者支配后者，pareto_size=2625）——
分组收益为数量级而非常数。**退化守卫**：`u > 1000` 时 `warnings.warn`（评分维度变多或
tier 分布变散会推高 u；提前警告而非等 perf 超预算才发现）；
bench_history 逐条记录 `pareto_size`（u 的下游代理）。
**夹具教训**：等价性测试的构造数据三次写错支配方向（strong_avoid 越小越好、
unknown 递增构成支配链）——独立暴力 oracle 先于手写期望给出正确答案，这正是"oracle 先行"的价值。

## 落地清单（✅ 全部完成，2026-11-01）

| # | 项 | 落点 |
|---|---|---|
| C11 ✅ | `severity_cap.py` + `RuleSet.cap_applied_ids` 预计算 | core-rule |
| C12 ✅ | engine：cap 路由 + veto 守卫 + strict 不变式 + 决策 0 分流 + source_status/doubt/declared_severity + demo 三态 | core-eval/engine.py |
| C13 ✅ | `EvalConfig.demo_veto` + verifier/generator 透传 + CLI 依赖校验（exit 2） | app-zeri |
| C14 ✅ | 首行标注 + 存疑提示 + 未激活合并块 + 声明/生效差异行 + 存疑/演示两节渲染 | report.py |
| C15 ✅ | lint cap 双显示 warning + `cap_applied_ids` 机器行 + `_check_signatures` 纵深 | cli.py |
| C16 ✅ | tier 确认矩阵脚本（触发守卫） | tools/tier_migration_check.py |
| C17 ✅ | publishable 不变式测试 | T7/T12 合流实现 |
| T6–T17 ✅ | 13 个新测试 + 旧演示语义测试迁移（+demo_veto=True 保留原意图） | tests/ |
| S2 ✅ | gen 冒烟归因 diff（见下） | out/ |
| C18 ⬜ | **Q-012 前置工程项（进 C 系列依赖顺序，不散落 Q-012——评审第九轮要求）**：向首侧 fact 产出（`facts.taisui.hit_facing` 或等价）→ 解锁合并案/TAISUI-002 满足准入条件 4 → 进必需集 → Q-012 联动表执行。依赖顺序：**fact 补齐 → 合并案落地 → 联动表勾选生效**；fact 补齐前必需集维持 8（已登记于 required_rules.yaml 注释） | `core-symbol`（fact 产出）、`core-rule/rules/public/`（新规则） |

## 施工验收（2026-11-01 实测）

- **pytest**：not-slow 全绿 exit=0。**测试账目（评审第十一轮第二节更正，实测 collect 口径）**：
  eac493d=630 总（627 not-slow + 3 slow）→ 639661a +10（T 编号落 9 方法：T7/T12/T17 合流、
  T10 为改写不新增 + 序列化 1）→ db11804 +0（纯文档）→ ab689cd +3（lint_groups/anchors/
  fingerprint；**混合提交**，实含第十一轮部分产物——量化确认评审第十一轮第七节的指认）
  → 本轮 +1~3（pareto 等价性测试等）。当前 **641 not-slow / 644 总**，删除 0 条；
  T10 改写后的旧语义（待考证被 select 排除）仍被断言覆盖（`all(status in 已考证/有争议)` +
  `len(all) > len(default)`），无覆盖率收窄。
- **lint**：✅ 通过；`cap_applied_ids` 与 10 条基线**逐字一致**；另 2 条签名提示（003/TAISUI 引文待签名）。
- **S2 gen 冒烟归因**（2026-03 修造，基线 `out/baseline-gen-2026-03.json`）：
  候选 372→372；**结构层 diff**（tier 直方图 + 逐候选 vetoes 集合）合法来源仅 (a)：
  移除的 veto 全部为 `PUB-SANSHA-001`（待考证，演示否决消失）×20，**非法新增 veto = 0**；
  tier 372 REJECTED → 372 NEEDS_REVIEW 全部由 (a) 归因；(b) 有争议默认参与仅出现在渲染层
  （controversial 条目），不动 tier——与甲案一致。
  **(c) schema 字段新增**（评审第十轮补枚举）：`Judgment.to_dict` 新增
  source_status/doubt/declared_severity、SchoolResult 新增 controversial/demo_hits、
  Evaluation 新增 `schema_version: 2`（契约 schema 同步声明，test_contract 抓漏验证有效）——
  结构层 diff 只比较 veto 规则 id 集合（比较域白名单：仅 veto rule_id 集合 + tier 直方图），
  对新增键天然免疫。
  **版本与兼容的诚实措辞（评审第十一轮第五节）**：无 schema_version 的历史报告视为 v1，
  本次为 v2；bump 规则 = 新增可选字段升 minor（v2.x）、删改/语义变化升 major；
  **系统不读回 JSON，不提供"旧 JSON → 解析器"的向后解析保证**——序列化测试测的是
  "新对象 → dict 键形状"（旧键全保留 + 新键可选），schema_version 是未来引入解析器时的挂钩，
  不是已兑现的兼容承诺。
- **C16 矩阵**：2026 全年 12 月 × 4 坐向，**48 格全对角**；有争议命中 22 次，
  **分规则：PUB-TAISUI-001 × 11、PUB-SANSHA-003 × 11，按坐向分布 = 全部在 180°**
  ——这不是脚本缺陷而是**规则结构**：坐太岁山 ⟺ 向首=岁破 ⟺ 岁破∈三煞方位组（direction_group
  口径），两规则命中坐向天然重合，多坐向无法分开覆盖。零迁移的完备性证明由**单元级等价测试**
  （机制对任意向量分布成立）承担，C16 是集成确认——两级证明各司其职（评审第十一轮第六节）。
  bench_history 已改**先记后断**（`passed` 标记随行入史）——消除"历史只含存活者"的偏差，
  相对门禁（下一批）不得建立在幸存者中位数上（评审第十一轮第六节）。
- **perf：评审的怀疑是对的——4.1× 是真实回归，已定位并修复（"环境噪声"归因撤回）**。
  同解释器同机 A/B（5 次中位）：基线 `eac493d` **2.223s** vs 施工后 **9.072s**；
  单月对照仅 1.22× → 超线性，与单次评估无关。根因：`ranker.pareto_front` 为 **O(n²)**
  逐对支配比较——基线时全候选 state=不可用 → `generator.py` no_solution 短路，pareto
  **从未被调用**；本 PR 使演示否决消失 → 全候选 state=可用 → 4380 个首次进入 O(n²) 路径。
  **修复**：按 5 维向量分组、仅组代表间筛选（同向量互不支配且同组同命运，语义与逐对严格等价）。
  修复后（3 次中位）：demo_veto=False **1.895s**、True **1.878s**——预算 2.0s 达标，比基线快 ~15%。
  bench 全绿（含两预算测试）。教训登记：**"环境噪声"归因在被二分排除前是未证实结论**
  （与"9/10 是假的"同类错误，第二次犯——评审第十轮第三节）。
- **ruleset_fingerprint：第三次串味实证 → 本轮机制化（不再排下一批）**。
  `_select_cached` key 同时并入 `ENGINE_VERSION`（评估/cap 语义版本，现为 0.2.0）——
  **改动 cap/评估语义必须 bump**，否则持久化缓存（日级事实缓存）跨语义版本投毒
  （评审第十一轮第四节）。
  生产影响判定：CLI 单次进程每次重建 ruleset 不受影响；**但 `loader.py` 的 version
  只是 (rule_id, version) 哈希**——热加载/服务化场景同 id 同 version 改内容（ADR-0013
  即改 YAML 未 bump version）必然串味。修复：`RuleSet.fingerprint`（`__post_init__` 派生，
  覆盖 id/version/status/severity/hard_veto/condition 内容哈希），`_select_cached` key 首位
  加入；`test_fingerprint_distinguishes_content` 断言同 id 同 version 不同 condition
  指纹不同且评估不串味。**统一 cache_key 收拢（所有缓存点过单一函数 + 手写 key lint）登记为 C19**，
  本轮先堵实测点；**C19 是日级事实缓存的硬前置**（评审第十一轮第四节：否则缓存 key 是
  第五种手写 key），两件必须同一依赖链：C19 → 日级缓存 → perf 相对门禁 → Q-012。
  **遗留登记**：coverage_gaps 目前只进 lint 机器行，**报告未渲染**（用户看不到"必需集 8 条"
  与"原文硬禁"的差额）——随 C14 报告项补；`version` 使用点收拢进 C19 清单
  （manifest/报告回显=人类可读标识，安全；`_select_cached`=已改指纹；测试 helper=仅测试）。
  **提交拆分约定**（评审第十一轮第七节）：影响行为分布的变更（如本轮 pareto）与机制化补强
  后续拆分提交，便于回归二分。

## 与 ADR-0012 / 0013 的关系

- ADR-0012 准入四条不变；`required_blockers` 走 status，不受 cap 与决策 0 影响
  （**publishable 语义不变**——T7/T12 以对照 run 断言）。
- ADR-0013 D6 已标 **superseded by 本 ADR**；D1"参考层慎用提示"由 C12 兑现为默认行为，
  且按决策 0 不携带 tier 影响。
- 已知未覆盖（联动 Q-012）：向太岁硬禁（P3/P5，A 级原文支撑）在 H1 裁定后仍无机器实现
  （向首侧 fact 缺失，准入条件 4 阻止入集）——必需集维持 8，期间系统不拦向太岁日课；
  已登记于 required_rules.yaml 注释与 Q-012 联动表。
