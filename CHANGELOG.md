# CHANGELOG

遵循 [Keep a Changelog](https://keepachangelog.com/)；版本号遵循语义化版本。

## [0.4.0] - 2026-11-01

针对第三轮评审的 P0：**必需集准入与可判定闭合**、**publishable 语义边界**、
**负向用例与验收信号**、**两轴组合边界**。

### 破坏性变更

- **必需集结构重写**（ADR-0012）：`required_rules.yaml` 改为
  `default.core` + `default.person_dependent` + `overrides[task_kind]`。
  - 修造 10 条（全 `hard_veto`），有命主时 12 条
  - 嫁娶/纳采 只剩 2 条（四离四绝）—— 12 类共用一组是错的
- **`ASSERT-REPEAT-001` 移出必需集**（选 A）：它是 `severity=慎用`、`hard_veto=false`，
  按准入条件 1 本不该进集；且"三见为滞"来源性质存疑，不宜作发布门槛。
- **`required_blockers` 语义收紧**：未考证的必需规则**即使求值为 False 也算阻塞**
  （"不犯"的结论基于未考证条件，不可作发布依据）。
  基准案例现在显示"必需集 10 条，已可判定 0 条"，而不是之前的"10/10"。

### 新增

**必需集准入四条 + 可判定闭合 lint**
- `_check_required_set()`：校验 hard_veto / target / school / person 依赖分组 / 事项覆盖
- 违反报 `required_set_unresolvable` 并列出阻塞链

**publishable 语义边界（安全底线）**
- `required_rules.yaml` 注释与报告显式声明"可发布 ≠ 可用"
- 报告新增「约定回显」节（ym_time_ref / hour_time_ref / day_boundary 组合）
- 报告「结构判定」节加桥接说明："结构确定 ≠ 结论确定"
- 报告「确定命中」空表加状态说明（"当前无"不等于"没问题"）
- manifest 显示 input_hash / facts_hash 前 8 位，便于人工对比两次运行

**负向用例与验收信号（不依赖真实考证）**
- `tests/golden/test_required_and_negative.py`：
  - 合成已考证否决规则 → 断言"确定命中"/`不可用（确定）`/`REJECTED`
  - 合成待考证规则 → 断言只渲染"演示性不可用"
  - **把 10 条必需规则全部替换为已考证 → `publishable is True`**（验收信号）
- `TestRequiredSetMeta`：每条必需规则必须 hard_veto / 非 hour / 非参考层 / 不依赖 person

**两轴组合边界**
- `test_mixed_year_changed_day_not`：2021 立春 22:58，民用时 23:10 + 真太阳时 22:29
  → **年柱已换（辛丑）、日柱未换（壬午）** 的合法组合
- 全真太阳时 → 年柱庚子；全民用时 → 年柱辛丑 + 日柱癸未
- 报告「约定回显」同时列出两条基准

**变异矩阵分级**
- `--level core`（10 个，PR 门禁）/ `--level full`（26 个，nightly）
- 自动写 `docs/mutation-report.md`（存活列表留档，存活即失败）
- 容量目标合并为单一 2s（删除 3s 阈值，避免两个数互相矛盾）

### 修复

- **规则选择缓存串味**（真实 bug）：`_select_cached` 的 key 只用 `ruleset.version`，
  动态构造的 RuleSet 复用同一 version 时，合成规则被带到后续评估。
  → key 加入 `ruleset.rule_ids`（预计算元组，避免 456k 次字符串操作开销）。
- **`RuleSet.rule_ids` 预计算**：性能从超预算恢复到 1.7s 量级。

### 已知限制

- 必需集 10 条全部待考证 → `publishable` 仍为 false（正确状态）
- 日级事实缓存未做（性能余量约 15%）
- `remedy_fields` / `--explain-missing` 未做
- 单规则隔离用例只覆盖变异暴露的缺口，未做全量 52 条
- CLI JSON schema 测试未加

## [0.3.0] - 2026-11-01

针对 2026-11-01 第二轮评审的 P0/P1 改造。核心：**定义级不再携带吉凶 severity**、
**publishable 基于必需集**、**时间基准可拆分**、**变异矩阵扩到 26 个**。

### 破坏性变更（行为变更，非纯 bugfix）

- **定义级 severity 只能是「记录」**（ADR-0009，推翻 ADR-0007 的 severity 设计）。
  10 条 `DEF-*` 从 `慎用/可用` 改为 `记录`，**不再进入 strong_avoid、不影响 tier**。
  对应吉凶主张拆为 8 条 `ASSERT-*`（待考证）。规则 44 → **52**。
- **默认时间基准回到 `civil`**（ADR-0011）：v0.2 曾把四柱统一到 `hour_ref`；
  v0.3 拆成 `ym_time_ref` / `hour_time_ref` 两个独立配置，默认 `auto`（= 跟随
  `use_true_solar_time`，默认 False 即全民用时）。混合口径成为可选项而非硬编码。

### 新增

**定义级 severity 白名单（P0）**
- 新增 severity 值 `记录`（定义级专用，不在吉凶序列内，`SEVERITY_ORDER = -1`）
- 加载期三条硬校验 + `rules lint` CI 兜底
- 8 条 `ASSERT-*`：自刑为凶 / 相冲为凶 / 三刑为凶 / 六害为凶 / 相破为凶 /
  三见为滞 / 旬空为凶 / 干冲为凶（全部 `待考证`，`citation.quote: null`）

**报告措辞三分（P0）**
- `participation` 新增 `演示`：`--allow-unverified` 下命中的待考证规则标为"演示命中"
- 结论措辞：`不可用（确定）` / `演示性不可用（不作为排除依据）` / `存疑` / `可用`
- 否决项表格分「确定命中」与「演示命中」两组
- 「存疑」给出原因分解：强忌 n ｜ 冲突 n ｜ 未知 n

**必需规则集与 publishable（P1，评审强调"别跳"）**
- `core-rule/config/required_rules.yaml`：14 个事项的必需规则（修造等 12 项共用同一套 10 条）
- `publishable` 改为"必需集全部可判定 + 无冲突 + 非 REJECTED"，非必需 unknown **不阻塞**
- 报告新增「必需规则集：共 10 条，已可判定 9 条」+ 未可判定项清单
- **验收信号**：修造只差 `ASSERT-REPEAT-001` 一条原文即可第一次 `publishable=true`

**时间基准拆分与 fact_hash（P0）**
- `CalendarConfig.ym_time_ref` / `hour_time_ref`（`auto|civil|true_solar`）
- 年/月柱用 `ym_ref`，日/时柱用 `hour_ref`；**日柱换日跟随 `hour_ref`**
- `fact_hash` 纳入完整约定（日界/时间基准/口径），避免"同 fact 不同口径"误判一致
- `tests/golden/test_boundary_and_convention.py`：8 个边界用例（含真太阳时前后移导致换日翻转）

**变异矩阵扩到 26 个（P2）**
- 覆盖：算子边界（in/gte/between/count_gte/same_group kind）、三态转换、tier 分支、
  冲突检测、unknown 分类、定义级白名单、publishable 必需集、演示标记、
  节气黄经、置闰、五虎遁/五鼠遁、旬空表、纳音表、二十四山顺序、分歧度公式、排序方向
- **过程中又发现 6 个测试缺口**（publishable 必需集短路、unknown 分类串味、
  same_group kind 被忽略、二十四山只抽查首尾、TIER_RANK 顺序、演示标记无断言），已补测
- 现 **26/26 全部被抓住**

**CI 增补**
- `rules lint` 新增：必需规则引用完整性、定义级 severity 白名单、规则清单一致性
- `core-rule/config/rules_manifest.yaml`：52 条（42 待考证 + 10 定义级）

### 修复

- **四柱时间基准**：v0.2 的"统一到 hour_ref"改为可配置的两轴（见 ADR-0011），
  默认回到惯例口径；日柱换日仍严格跟随 `hour_ref`（同一量同一基准）。
- **`_convention_hash` 抽出**：供 engine 与测试复用，避免两处逻辑漂移。

### 已知限制

- 断言级 42 条仍 `待考证`；修造链路差 1 条（`ASSERT-REPEAT-001`）即可 publishable
- 日级事实缓存未做（性能余量约 7%，1.86s/2s）
- `loose` 档仍无 CLI 入口
- 必需集选取本身是人的判断（Q-011 待确认）
- 三级剪枝、FastAPI/PWA（M10）未实现

## [0.2.0] - 2026-11-01

针对 2026-11-01 评审意见的十条改造。核心目标：让已有成果**可见**、让结论**可信**、防止**回退**。

### 新增

**定义级规则分层（ADR-0007）—— 评审第 1 条**
- 新增 `status: 定义级` 与 `citation.kind: spec|classic`，区分"干支算术推论"与"吉凶断言"
- 10 条结构规则迁移为 `DEF-*`（自刑/六冲/三刑/六害/相破/重复/旬空/干冲/三合/山家三合）
- `Evaluation.structural` 独立字段 + 报告「结构判定（定义级，已确定）」节
- 加载期三条硬约束：`citation.kind=spec` + 规格条款 + 不得为硬否决（防"断言伪装成定义"）
- 规则总数 42 → 44（34 待考证 + 10 定义级），测试向量 84 → 88

**unknown 三分类（评审第 4 条）**
- `missing_input` / `caliber_undecided` / `unverified_rule` + 每条的 `remedy`（解除条件）
- `vectors.unknown_by_reason` 分开统计；报告「未知」节按原因分类并给出行动指引

**无解 / 无结论区分（评审第 7 条）**
- `NoSolutionReason` 三值：`all_rejected` / `no_conclusion_pending_verification` / `constraints_conflict`
- `Evaluation.publishable` 与 `GenResult.is_publishable` 作为布尔位进 JSON
- 报告首行显式标注"本次无结论（非无解），不得当作该窗口无可用日"

**冲突拆分（评审第 2 条）**
- 新增 `rule_conflict`（同一派内两条规则互相抵消），携带 `rule_a/rule_b/severities/citations`
- 与 `state_divergence`（派别间不一致）语义分离，不再混用
- 各派记录 `fact_hash`，不一致时引擎直接抛错（防分歧度被输入差异污染）

**口径注册表（评审第 3 条）**
- `core-rule/config/calibers/{sansha,nayin}.yaml` + `CaliberRegistry`
- 三煞：`direction_group`（方位组，标"有争议"）vs `named_sansha`（判到劫/灾/岁，标"待考证"）
- 纳音：`undecided`（默认，不推断）/ `chuanshan` / `fenjin` / `zhengzhen`
- 未裁定口径给出**对比式提示**：每个可选值 + 状态 + `requires`（缺什么表）
- 报告「口径回显」节强制展示；CLI `--caliber key=value`

**稳健集 / 敏感集（评审第 5 条 / 建议 ①）**
- `--robustness`：坐向 ±angle_uncertainty + 真太阳时 + 日界 扰动矩阵
- 输出稳健集（state 不变）/ 敏感集（翻转 + 触发原因）+ `radius_deg`

**strictness 三档语义 + severity 按派别覆盖（评审第 4 条）**
- `strict`：断言级慎用升级为否决；`normal`：存疑；`loose`：降为提示
- `severity_overrides: {school: severity}`，加载期校验不得把否决降成"推荐"
- ADR-0008 记录与评审建议的差异（normal 保留"存疑"而非降到 ACCEPTABLE）

**节气回归面与边界交叉（评审第 6 条 / 建议 ②）**
- `tests/golden/test_solar_terms_regression.py`：11 个权威锚点（±2 分钟）
- 1900-2100 每 10 年 × 24 节气**求解器自检**（代回黄经偏差 < 1e-4°）
- 1900-2100 立春**回归年线性**校验（相邻年差 365.2422±0.2 天，抓算法失稳）
- 立春 ±10 分钟 × 日界(早/晚) × 真太阳时(开/关) **交叉用例**

**变异测试抽查（评审第 8 条 / 建议 ④）**
- `tools/mutation_check.py`：8 处定点变异（in→nin、>=→>、between 边界、自刑表塞"未"、
  三煞方位错位、禁用不判不可用、日柱偏移、unknown 不拉 tier）
- 首轮发现 **2 处存活**（between 边界、unknown 拉 tier），已补测；现 8/8 全部被抓住

**性能与门禁（评审第 9/10 条）**
- 规则选择预索引（`_SELECT_CACHE`，key 含 ruleset.version）
- `tests/bench/bench_history.jsonl` 基准追踪 + 回归阈值（历史中位数 1.5×）
- 新增「已考证模拟」压测（`allow_unverified=True` 全规则参与，阈值 3s）
- 规则清单 `core-rule/config/rules_manifest.yaml` + `rules lint` 校验总数/状态/派别分布
  （防"文档说 44 条、磁盘 52 条"的漂移）

### 修复

- **四柱时间基准不统一**：真太阳时开启时，年/月柱用民用时、时柱用真太阳时，内部矛盾。
  现四柱统一基于"命理时间"（`hour_ref`）。由 `test_true_solar_time_shifts_year_boundary` 守住。
- **`jie_before` 全量排序**：每次遍历 3 年 72 节气并排序 → 改为只查本年/上年（性能）。
- **`stable_hash(ctx)` 逐规则调用**：131k 次 JSON 序列化 → 每候选一次。
- **`_term_dates` 未缓存**：每候选重建 24 项 dict → `lru_cache`。

### 已知限制

- 断言级 34 条仍 `待考证`（缺原文），`publishable` 恒为 false —— 这是正确状态
- `loose` 档无 CLI 入口（风险高，需显式加参数）
- 性能余量约 7%（1.86s / 2s），优化路径：日级事实缓存（未做）
- 三级剪枝、FastAPI/PWA（M10）仍未实现

## [0.1.0] - 2026-11-01

首个可运行版本。覆盖 M0-M9（M10 服务化未实现）。

### 新增

**事实层 core-time**
- VSOP87D 截断太阳视黄经（L0 64 项 … L5 1 项）+ 章动 + 光行差 + FK5 修正，精度 < 5″
- 节气牛顿迭代反解（24 节气，容差 0.5 s），实测与权威历书差 ~15 s
- ΔT 锚点线性插值（Espenak & Meeus）
- 真太阳时（经度时差 + 均时差）
- 四柱：年界（立春/正月初一）、月界（节气/农历月）、日界（子初/子正）全部可配置
- 农历定朔定气 + 无中气置闰，正确处理闰十一月（2033 闰冬月已验证）

**符号层 core-symbol**
- 干支关系全表（三合/三会/六合/六冲/六害/三刑/相破/自刑/半合）
- 纳音（60 项）、旬空（六旬）
- 二十四山、兼向判定（3° 阈值）、分金槽位（每山 5 槽）
- 派生事实注册表：三煞/太岁/岁破/月破/年五黄/四离四绝/旬空（提供），
  月五黄/阴府/都天煞/伏兵大祸/天地官符/大小月建/杨公忌/重丧/三丧/妨翁姑/妨父母（不提供）

**规则层 core-rule**
- DSL：`all/any/not` + 12 算子 + 三值逻辑（Kleene）+ 深度限制 + 命名空间白名单
- 生命周期状态机（5 态 + 迁移表 + 签名要求）
- 加载期校验：字段/枚举/条件树/引文完整性/tests 数量/rule_id 格式
- 派别策略与事项模板（24 项）全部数据化
- 42 条规则 YAML（全部 `待考证`）+ 84 条规则级测试向量

**判定层 core-eval**
- 三态判定（唯一权威定义）+ 分层向量 + 四级 tier
- 派别并列（`per_school`，不合并分数）
- 三类冲突检测（verdict_conflict / state_divergence / policy_divergence）
- 分歧度公式（`1 - 众数频次/派数`，口径固定）
- 敏感性分析（真太阳时/日界/年界/坐向 ±3°）
- 分层排序 + Pareto 前沿
- 独立结构检测器（自刑仅辰辰/午午/酉酉/亥亥，未未不是自刑）

**应用层 app-zeri**
- CLI：`verify` / `gen` / `rules lint` / `rules diff` / `cases run`
- 复核器、生成器（全量评估 + 无解说明）
- Markdown/JSON 报告 + manifest（输入哈希/规则库版本/引擎版本/历法口径）
- 案例运行器（四份报告 + Cohen's kappa + 打乱对照）
- 输出 JSON Schema + 极简契约校验器

**工程**
- 438 个测试（单元/属性/金标准/契约/性能），覆盖率 83%
- 金标准案例 GS-2027-0711（四柱/三合扶山/三未非自刑/阴府 unknown/tier 非 PREFERRED）
- CI 门禁：测试 + 覆盖率 + 规则 lint + status 签名 + 无网络扫描 + 性能预算
- 6 份 ADR + 9 项 QUESTION 登记

### 修复（开发期踩坑，记录以防回归）

- **均时差公式系数混用**：Meeus 28.3 的 L0 有"每儒略世纪 36000.76983°"与
  "每儒略千年 360007.6982779°"两个版本，初期混用导致 EoT 偏差约 400 分钟
  （真太阳时把 23:30 算成 15:30）。已修正并在 `ephemeris.py` 注释中标注。
- **农历闰月月号错位**：闰月沿用"下一月"月号，导致 2020 报闰五月（应闰四月）。
  改为"沿用上一月月号"，并重构为 `_cycle_months`（以冬至月为十一月）以支持年末闰月。
- **事实键名冲突**：`facts.taisui` 的 value 含 `azimuth`（数值），与规则想访问的
  `azimuth.zhi`（子结构）冲突，导致太岁规则永远 unknown。改为 `azimuth_deg`。
- **三值逻辑误用**：阴府规则写成 `all[exists(value), count_gte(hits,1)]`，
  因 `False ∧ unknown = False` 导致"事实不可得"被误判为"不命中"。改为单原子 `exists`。
- **性能**：`stable_hash(ctx)` 曾逐规则调用（131k 次 JSON 序列化），4380 候选耗时 3.6 s。
  改为每候选算一次 + `jie_before` 只查本年/上年 + `_term_dates` 缓存 → 1.49 s。
- **Pareto/排序传参错误**：生成器把 `VerifyResult` 传给期望 `Evaluation` 的排序函数。
- **结构检测半合 `next()` 抛 StopIteration**：未判空即取三合局。
- **方位角浮点边界**：`-1e-43 % 360` 返回 360.0，违反 [0,360) 不变量。

### 已知限制

- 规则库 42 条全部 `待考证`，系统默认不产生正式结论（见 Q-001）
- 月五黄、阴府、都天煞等 11 项事实不提供（见 Q-002~Q-006）
- 未实现三级剪枝（当前为全量评估，性能仍达标）
- 未实现 FastAPI/PWA（M10）
- 案例库仅 1 条 A 级案例（见 Q-009）
- 历史时区变更不支持
- 覆盖率 `core-eval/sensitivity.py` 与 `app-zeri` 部分分支未覆盖（见 Q-008）

### 未实现（按规格属后续里程碑）

- M10：FastAPI 服务、PWA、案例库浏览界面、PDF 报告导出
- 三级剪枝（年/月级粗筛）
- `--relax` 放宽硬约束流程
- 多节点同日/异日约束求解
