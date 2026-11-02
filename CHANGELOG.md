# CHANGELOG

遵循 [Keep a Changelog](https://keepachangelog.com/)；版本号遵循语义化版本。

## [Unreleased] 评审回路（四）：分片独立验证 + grep 根因修正 + 防腐化补锁（2026-11-03）

### 分片验证：每个提交单独检出全绿（bisect 安全性不再是推理，是执行结论）

历史经一次受控重写（原链打 tag `backup/pre-rewrite-2026-11-03`，双 bundle 备份），
原因是片1 携带的仓库级断言 `TestRepoIsClean` 依赖引擎修复，**单独检出必然红**。
处置：该断言拆到 `tests/integration/test_c20_repo_clean.py`（随引擎修复落地），
工具片只保留 fixture 反证。每个 SHA 在独立 worktree 用 junitxml 验证
（pytest 汇总行在本沙箱不可见——见下节——junitxml 是权威数字来源）：

| SHA | 内容 | tests | failures/errors | rules lint |
|---|---|---|---|---|
| `8f2217f` | 片1 工具/门禁 | 865 | 0 / 0 | 通过 |
| `2b3229b` | 片2+3 代码 | 1142 | 0 / 0 | 通过 |
| `504de49` | 片4 文档 | 1142 | 0 / 0 | 通过 |
| `8e79f43` | 补丁应用（tip） | 1146 | 0 / 0 | 通过 |

### grep 假阴性根因修正：不是"判二进制"，是 toybox BRE 不支持 `\|`

字节级复查：全仓 .py **0 个 NUL、0 个非 UTF-8**——原诊断（"文件被判二进制"）是错的。
真根因：本沙箱 `grep --version` = **toybox 0.8.13**，BRE 的 `\|` 被当字面量 →
**静默零匹配**。对照实验（A/B/C/D/E，可 `tools/verify_claims.py --demo` 复跑）：
`grep -a "A\|B"` → 0 命中；`grep -aE "A|B"` → 16 命中。
Q-020/Q-021 的"宣称与树不一致"疑云就此解除：**两条宣称均属实**
（TestSanshaScope 4 例、TestJianxiangCaliber 5 例、jianxiang.yaml 两口径，全过）。
`docs/research/concurrent-write-forensics-2026-11-02.md` §6.6 已改写（保留误诊史）；
AGENTS 约束新增第 9 条（交替必须 `-E` 或 Python；跨环境异常空输出先打 `--version`）。

### 新增工具与门禁

- `tools/verify_claims.py`：宣称核对器，四列输出（宣称 → 实际路径 → 用例名 → 结果），
  Q-020/Q-021 归档见 `docs/research/q020-q021-verification.md`；退出码 0 = 全部核实。
- `dead_rule_scan.assert_buckets_exist`：REQUIRED_BUCKETS 五桶（vetoes/cautions/
  positives/demo_hits/reference）必须存在，引擎删桶/改名时**响亮失败**——
  补回 getattr 兜底换掉的硬失败（评审第二节）。真仓库零假设测试直接对照
  SchoolResult 的 dataclass 字段。
- `lint_static.check_demo_veto_wiring`（rules lint 第 e 项）：封死联调开关的三条
  腐化通路——`os.getenv("DEMO_VETO")` / `os.environ.get(...)` / `os.environ[...]`，
  及配置 YAML 携带 `demo_veto` 键。报告横幅（🚧 含演示否决）已存在，位置测试锁定。
- `tests/unit/test_verdict_baseline.py` + `core-rule/config/verdict_baseline.yaml`：
  verdict_type 迁移**棘轮**——全仓未标注数（当前 75/86）只减不增；减少也要求
  显式下调基线并勾选清单。清单落盘 `docs/c2-migration-checklist.md`。
- 报告「未归类规则」节：14 条**全部列出不截断**，每条附规则文件路径。
- demo 隔离 golden 快照：`tests/golden/demo_consensus_snapshot.json`
  （4 派 demo-only + 1 派沉默 + 1 派闸门 → 0/0，计票语义漂移会直接进 review diff）。
- `_total_rank` 锁补正向边界用例：单派内按 rank_score 排序**不**触发本锁（防误删锁）。
- `tools/new_question.py` 纪律：已归档编号永不复用；并发以提交时间为准、后到顺延，
  不做 --reserve 占位（空壳 Q 号比撞号更难清理）。
- Q-015 期限改**绝对日期**（2026-12-31 / 2027-02-28 / 不设期限）。

## [Unreleased] 共识度整数比 + C20 禁聚合门禁（ADR-0015，2026-11-02 深夜）

主题：**把"不要加权求和"从文档里的原则，变成 CI 会拦住你的门禁。**

### 变更（对外结构有增无删）

- **共识度改为整数比**：`five_school_output._consensus_detail` 新增
  `consensus_ratio`（`"4/5"`）、`voters`、`non_voters`（含 `reason`）、
  `gate_veto_schools`、`threshold`；**不再提供任何浮点共识分**。
  `_consensus` 字符串保留，取值集合不变（`favorable/unfavorable/mixed/neutral`）。
- **阈值外置**：新增 `core-rule/config/consensus.yaml`（`min_agree_num` / `min_agree_den`），
  按事项可覆写（**当前留空：事项级门槛属术数口径，待人工裁定**）；
  加载器拒绝浮点与布尔阈值（`0.6` 直接报错）。
- **投票分账**：闸门层（`layer: reject`）只否决**不计票**；参考层
  （`layer: reference`，斗首）不计票；`scoring` 层但本轮无判定者按**沉默派**处理，
  **不进分母**。三者全部写入 `non_voters` 并带原因。
- **排序键末位**：`-_mean_rank_score` → `-positive_count`（整数计数）。
- **tier 推导**去掉 `_total_rank`（跨派均值）。说明：`score_weight` 上限 1.0、
  分母为派数，该分支在 `positive>=1` 时恒不能单独成立，删除不改变可达分布。
- **报告**新增「共识度（整数比，**非总分**）」节：只出比值与名单，含每个未投票者的原因。

### 新增门禁 C20：禁聚合总分

- `tools/check_no_aggregate_score.py`：AST 扫描 `core-eval/src` + `app-zeri/src`，
  禁止 `/ len(...)`、`statistics.mean` 类调用、以及重建 `mean/average` 命名的函数；
  豁免须 `# lint-exempt: <≥8 字理由>`，`--list` 可逐个受审；已接入 `make gate`。
- 现有 5 处描述统计（分歧度 ×2、案例评测率 ×3）显式豁免，理由均写明"不进排序键"。

### 测试

- `tests/unit/test_no_aggregate_score_lint.py`（13 例：含"去掉除法即沉默"反证、
  空理由豁免被拒、仓库洁净、`sort_key` 无除法定点守卫）
- `tests/unit/test_consensus_ratio.py`（16 例：整数交叉相乘、配置拒浮点/拒布尔、
  投票与未投票名单互斥且覆盖全部参评派）
- `tests/unit/test_report_consensus_section.py`（7 例：报告不得出现浮点分值）

### 文档

- 新增 `docs/adr/0015-consensus-integer-ratio.md`（含"为什么不选 Borda"）
- `AGENTS.md` 硬禁止 11–14（共识整数比 / 阈值外置 / 投票分账 / 排序键只许计数）

## [Unreleased] 评审回路：死代码门禁 + 并发取证 + C 第一批（2026-11-02 深夜）

主题：**这轮最严重的不是新增规则，是"模块写了却没接上"和"仓库有第二个人在写"。**
两条都做成机器可查，不再靠"下次仔细点"。

### 新增门禁 1：死代码（`zeri rules lint` 第 14 项）

- `app-zeri/src/app_zeri/lint_static.py`：AST 扫描 `core-symbol/` 下全部公开 `derive_*`，
  要求**定义文件之外**至少一个调用点；同文件内被"活函数"间接调用算活（传递闭包），
  只被死函数调用仍算死。
- 同时检查"模块存在但没人 import"——`zibai.py` 事故的另一种形态。
- 反证测试：`tests/unit/test_lint_static.py`（15 例，含"构造违规必响 + 移除触发条件必沉默"）。
- 真仓库基线：当前 9 个 `derive_*` 全部可达、14 个符号层模块全部被 import。

### 新增门禁 2：登记一致性（同第 14 项）

- `coverage_gaps.yaml` 每条登记新增机器可核块：

  ```yaml
  implementation:
    status: unimplemented   # 或 implemented
    fact_roots: [wutu]
    derive: []
  ```

- 判据：标 `unimplemented` 却已注册事实/已有调用点 → fail；标 `implemented` 却查不到
  事实或调用点 → fail（后者正是本次事故形态）。
- 当前 7 条实现类登记全部自洽；`GAP-ZIBAI-DAYYUAN` 由「未实现」改写为「已实现但有口径未裁定」。

### C 第一批：判定类型三字段（只迁 10 条，不空迁 85 条）

- `Rule` 新增 `verdict_type`（gate/vote/reference）、`layer`、`engine_eligible`、
  `ineligible_reason`；未标注时按 `hard_veto + severity` 推断（老规则零改动能加载）。
- Loader 四条硬约束：枚举合法；`engine_eligible=false` 必须带理由；理由与 true 不得并存；
  `已考证/定义级` 不得标 false。
- 引擎新增 `reference` 桶：命中可见、不进 vetoes/cautions/positives，不影响
  state/tier/publishable/rank；报告新增「参考层」节并显示理由编码。
- 10 条新规则标注：五黄月盘 = gate（参评）；日/时盘 = gate 但 `day_yuan_undecided`（参考层）；
  年紫白四吉 = reference（`no_primary_source_four_auspicious`）；值宿吉/凶 = reference
  （`coarse_label_no_primary_source`）；天德/月德/月德合/天赦 = vote（不进否决层）。
- lint 两条不变式：`layer=reference` 不得 `engine_eligible`；参考层不得进必需集。
- 顺带修 `tools/dead_rule_scan.py` 的命中桶遗漏：`HIT_BUCKETS` 不含 `reference`，
  会把全部参考层规则误判成零命中（本轮 5 条）。

### Q-015：不干等，先跑影子数据

- `tools/zibai_yuan_shadow.py`：以「换节即换元」为激进上界，对 2025–2027 逐日比对两读法。
- 结果（`docs/research/q015-day-yuan-shadow.md`）：不一致率 **54%–99%**，星位差 1–4，
  六个节气段各上百天 —— 争议不是边界特例，而是整段计数起点不同。
- 结论只写"差多少"，不写"谁对"；B 明确标注"非抄本依据"。

### 并发写入：取证 + 流程化

- `docs/research/concurrent-write-forensics-2026-11-02.md`：以文件 mtime 定位他进程
  （`huangdao.py` 22:53、`jianchu.py` 22:52、`shensha.py` 22:55、`mountain.py` 22:56、
  `determinism_probe.py` 23:45），并记录 `ps` 在沙箱不可得。
- `tools/worktree_guard.py`：提交前列出改动并分「噪声/白名单/需确认」三组；
  `--strict` 供 pre-commit 用；不自动 add/commit（4 例纯函数测试）。
- 明确**单写者原则**与"新增 Q 前先 grep 最大编号"（本轮已发生 Q-018 被他进程占用）。

### 方法论沉淀

- `docs/research/verification-patterns.md`：把"找一条独立恒等式 + 全时段扫描 + 扰动反证"
  写成模板，列出 9 条已落地恒等式（值宿=星期、建除=月建/月破、紫白=洛书互逆、日柱=儒略日…），
  以及 5 个**没有恒等式**、只能等原典的模块（日盘起元、值宿吉凶、天德卦位、斗首吉凶、卦运）。

- **关于 117 文件的大提交（可检索说明）**：该提交把「A 共识计票」与「C 第一批契约」
  合并在一起，原因是按功能拆分会产生**检出后跑不过测试**的中间提交
  （engine 需要 `Rule.engine_eligible`、规则需要 loader 接受 `verdict_type`），
  对 `git bisect` 反而有害。按目录 review 用 `git show <sha> -- core-eval/`（或 core-rule/app-zeri）。
  **每个提交都单独检出跑过测试**，结论见下节「分片验证」。
### 评审回路（二）：热文件取证 + 三条反证测试 + 0/0 前置提示
- **`verdict_type` 未标注不再兜底为 `vote`**（补丁已应用）：`effective_verdict_type`
  返回 `unspecified`，`gate` 推断保留（硬否定只能是闸门）；loader 拒绝显式 `"unspecified"`；
  报告新增「未归类规则」节（本次评估涉及的规则 + 「未归类 ≠ 投票」说明）。

- **取证三个热文件**（`engine.py`/`ranker.py`/`arbitration.py`）：AST 证明
  `_total_rank`/`_mean_rank_score` 已从语法树消失（仅注释留史）；`consensus_ratio`/`non_voters`/
  `reference` 三套符号共存且贯通 → 不存在整文件覆盖。**不可证**的部分（逐行归属）已写明，
  不以"测试全绿"冒充。见 `docs/research/concurrent-write-forensics-2026-11-02.md` §6。
- **抓到真实覆盖形态**：`QUESTIONS.md` 里 Q-018/Q-020/Q-021 各出现两次（问题本体 + 另一会话的
  「处置更新」）。三处改为 `## 处置更新 · Q-nnn`，并新增 lint 不变式 `check_question_numbering`
  （重复/断号即失败，6 例反证）——这是"测试全绿但审计链已坏"的实例。
- **`_total_rank` 删除反证**（`tests/unit/test_no_total_rank.py`，10 例）：源码锁（AST 无该符号）
  + 行为锁（`sort_key` 末位是整数 `positive_count`，且对 `rank_score` 不敏感）。
- **共识分账测试**（`tests/unit/test_consensus_accounting.py`，10 例）：闸门只进
  `gate_veto_schools` 不计票；参考层必在 `non_voters` 且理由 `layer_reference`、不进分母；
  沉默派 `no_verdict` 不进分母；分母 == 「scoring 层且有判定」的派数。
- **0/0 强制提示**（`report.zero_voter_notice`）：无已考证规则投票时，结论紧后面输出
  「不构成择日结论」；有闸门否决时**先说不构成结论、再说谁否决**（顺序锁进测试）。
  演示票凑出的 1/1 同样触发——"有票"必须是真票。
- **待应用补丁**（`docs/patches/verdict-type-unspecified.md`）：`effective_verdict_type` 不再
  兜底为 `vote`，未标注返回 `unspecified`。因 `models.py` 是热文件，本轮只落文档、不改代码。
- **裁定一页纸**（`docs/research/decision-sheet-2026-11.md`）：Q-022 阴宅门槛 / Q-015 日盘起元
  （附 54%–99% 影子数据）/ Q-016 时禽，三项勾选 + 签名，含"不签会怎样"。

## [0.6.2] - 2026-11-02

主题：**把"偶发失败"从感觉变成判据** + 三条纪律落地（A 路线）+ 影子规则第一次真正跑起来（C 路线）。

### 取证：偶发失败的真因是**并发写入者**，不是哈希序

新增 `tools/determinism_probe.py`：对 5 个固定日课（含立春前后、立冬后、子时）走公开入口
（`build_context` → `evaluate`），把 facts 与判定摘要规范化后取 sha256 指纹。

| 实验 | 结果 |
|---|---|
| 20 个不同 `PYTHONHASHSEED`（0–19）跑探针 | **指纹全同**（20/20）→ 事实层与判定层不依赖集合/字典迭代序 |
| 另 4 个 seed（0/7/99/12345，改动后复测） | 全同 |

**结论**：产品入口的「同输入必同输出」**成立**，`PYTHONHASHSEED` 不是变量。

那偶发失败从哪来？在循环跑 `tests/unit + tests/golden` 的过程中抓到了直接证据：

| 时刻 | 观测 | 说明 |
|---|---|---|
| 00:05:23 | `tests/unit/test_rule_verdict_type.py` 出现（12 项，C 第一批契约测试） | 我没有创建这个文件 |
| 00:08:45 | `core-eval/src/core_eval/disagreement.py` 被改 | 当时我在跑 mtime 快照，未编辑任何文件 |
| 00:08:52 | `app-zeri/src/app_zeri/case_runner.py` 被改 | 同上 |
| 循环第 9 次 | 失败于**那个刚出现的新测试文件**（`test_ineligible_rejected_for_verified`，断言的是另一条 loader 错误的文案） | pytest 导入时文件还在写 |

**真因**：本次会话期间**有另一个写入者持续修改同一工作树**（`core-eval` 的
arbitration / disagreement / ranker、`core-rule` 的 models / `__init__`、
`app-zeri/case_runner.py` 等非本会话拥有的文件在运行中被改动）。
这同时解释了此前三个"像哈希序"的特征：

1. **每次失败落在不同测试**——因为每次 pytest 启动时的树不一样；
2. **单独跑不复现**——单独跑的时间窗里恰好没有写入；
3. **固定 `PYTHONHASHSEED=0` 后"好了"**——纯属巧合（那两次刚好没撞上写入）。

因此：**"偶发失败"不是算法缺陷，是实验方法缺陷**。产品侧不需要修改；
需要修改的是纪律——见下条。

### 纪律增补：稳定性实验必须冻结工作树

- `AGENTS.md` 补丁纪律第 7 条（新增）：跑"N 次重复/偶发复现"类实验期间**不得改动工作树**，
  也不得与他人共享同一工作树并行编辑；报"偶发率"时必须声明是否冻结。
- 本会话自身也踩了两次（第 5 次失败＝新增规则未登记基线；第 7 次失败＝对照实验把规则文件
  临时移走、shell 被 SIGTERM 打断未恢复）。**这两次都不该记在"产品 flake"账上**，
  已在本条更正，不再计入失败率。

> 上一版 CHANGELOG 曾把失败率归因为"并发跑多个 pytest 进程"，方向对了一半：
> 争用确实存在，但真正的写入者是**编辑器侧**而非测试侧。报数纪律同 AGENTS.md
> 计数来源条：结论必须来自受控实验。

### A 路线：三条纪律从文档变成门禁

- **`AGENTS.md` 硬禁止第 8/9 条**（新增）：死规则修复**不得**顺手改命中面；
  扩大/缩小 `hit_*` 范围必须走「QUESTION → 影子规则（`engine_eligible: false`）→
  观察一版 → 人类裁定」，不得直接改 `severity`/`condition`/默认值。
  这条是为 Q-018 而写的：它看起来"补个漏就完了"，补上就是改变行为分布。
- **`AGENTS.md` 硬禁止第 10 条**（新增）：确定性优先于新功能——禁止依赖 `set`/`dict`
  迭代序、数值用整数或整数比、口径组必须显式 `default`、改事实层必须跑探针。
- **数值纪律进 `docs/DEVELOPMENT.md` §5.2**，并配两条 lint 不变式（`rules lint`）：
  - `_check_calibers`：每个口径文件必须**显式**声明 `default`。原因：加载器缺省时会退化成
    `next(iter(calibers))`＝"YAML 第一个键"，让书写顺序变成语义（顺序依赖温床）。
  - `_check_no_float_literals`：规则条件里不得出现浮点字面量（含嵌套 `all`/`between`）。
    原因：浮点让判定依赖求值顺序与累加路径，`0.1+0.2≠0.3` 落在 `gte/between` 边界就翻面。
    当前 86 条规则实测 0 处违规。
- 两条不变式各配**反证测试**（构造违规样本→断言报警；移除触发条件→断言沉默），
  见 `tests/unit/test_lint_invariants.py`（9 项）。只断言"当前恰好为空"不算验证。

### C 路线：影子模式落在真实待裁项上（Q-018）

- 新增 `PUB-WUHUANG-PALACE-001`：`verdict_type: gate` + `engine_eligible: false` +
  `ineligible_reason: hit_range_pending_human`，条件为 `facts.wuhuang.year.hit_palace`
  （整宫三山）。与 `PUB-WUHUANG-001`（`hit_mountain`，宫心一山）的差值＝
  八干山是否计入五黄，正是 Q-018 的争议本体。
- 配套 2 个 RT 向量：HIT 向量刻意构造成 `hit_palace=true` 且 `hit_mountain=false`，
  把这个分歧点钉死在测试里。
- **影子模式语义测试** `tests/unit/test_shadow_rule.py`（5 项）：命中必须进 `reference` 桶
  （看得见），且**不得**进 `vetoes/cautions/positives/unknowns/structural/controversial/demo_hits`，
  且开/关命中后 `state`/`tier`/`publishable`/`vectors`/各派 `rank_score` **逐字相同**。
  ——"观察不投票"从此是机器可验证的，不是 docstring。
- 规则库 85 → **86 条**（待考证 73→74，public 57→58），`rules_manifest.yaml` 同步。

### Q-020 上锁：三煞不做宫级扩展（不加字段，加测试）

- `sansha_of` docstring 增图表明写：亥(322.5–337.5)/子(352.5–7.5)/丑(22.5–37.5) 之间
  留有空档 337.5–352.5°＝**壬山**；按八宫并集会扩到 9 山过宽，"按三山精确匹配"则壬山不算。
  **这是概念层不自洽，不是实现遗漏**，故不加 `hit_palace`。
- 锁定测试 `TestSanshaScope`（4 项）：三山必须命中；**壬山必须不命中**；
  三煞事实**不得出现** `hit_palace`/`palace_mountains`。
  没有这把锁，下一个"好心"的开发者会把它当漏判补上。

### Q-021 解耦：兼向阈值变成数值口径（默认不变）

- `CaliberSpec` 增 `params` 字段，承载**数值型**口径；新增 `calibers/jianxiang.yaml`
  两组口径（`zheng6_jian45`＝3.0° 默认 / `zheng9_jian3`＝4.5°）。
- `build_context` 读口径取 `threshold_deg` 传入 `jian_xiang`，并在 `site.jian_caliber`
  与 `site.jian_threshold_deg` 回显；`_day_key` 纳入口径名。
- **默认值保持 3.0，行为零变化**（金标准案例两说结论一致，故不受影响）。
  师傅裁定后改 config 即可，不用改代码、不用重跑测试。
- 测试 `TestJianxiangCaliber`（5 项）：默认 3.0；偏 3.5° 的坐向默认判「兼亥」、
  切到 4.5° 口径改判正针且 `shan_jia_zhi` 变 `None`；口径在 manifest 回显；非法口径报错。

### 未做（明确记录，避免被当成遗漏）

- **天星 4 条规则未改 `engine_eligible=false`**。它们当前 `severity: 可用`，
  只进 positives（可影响 `TIER_PREFERRED`）。改成不投票属**结论强度变更**，
  按新增的硬禁止第 8/9 条须走影子路径（先观察一版再裁定），不宜顺手动。
  已登记为下一轮 C 迁移的独立项。
- 75 条规则的 `verdict_type` 显式标注（当前 loader 允许 `None`＝"迁移期允许"）。
  属纯元数据、行为中性，可与上述天星项合并成一次迁移 PR。

### 第二失败源：`dead_rule_scan` 的超时余量太薄（独立于上面的并发写入）

这一条在上一版里被我写成"顺带一提的环境观察"，位置错了——它是**独立且会叠加的失败源**：

| 事实 | 数值 |
|---|---|
| 扫描窗口 | 5 事项 × 3 命主 fixture × 3 年 × 12 月 × 5 日 × **11 坐向** ≈ **29,700** 次 `build_context` |
| 单次实测 | **129.6 s**（此前只有 `>120 s` 的粗估，因为被 120 s 的工具超时打断过） |
| 测试给的超时 | 600 s（余量 ≈ 4.6×，看起来够，但机器上再有第二个大进程就不是了） |
| pytest 观感 | 超时与断言失败**都显示为 `FAILED`** —— 分不清"产品错了"还是"机器慢了" |

**处置一：结果缓存（129.6 s → 0.13 s，输出逐字节一致）**

- 键 = 工具自身 + 全部规则 YAML + 基线 + manifest + school_policy + 各包 `src/**/*.py`
  的 `(路径, 大小, mtime_ns)` + 窗口常量 + Python 版本。**任一输入变化即换键**，
  所以"改了规则却读到旧结论"不可能发生。
- 缓存落 `out/.cache/dead_rule_scan/<fp>.json`（`out/` 已被 .gitignore 忽略），
  原子替换写入；损坏/形状不对一律当**未命中**（宁可重算 130 s，不可拿错结果）。
- `--update-baseline` 与 `--no-cache` 直接绕过缓存。
- 反证测试 `tests/unit/test_dead_rule_scan_cache.py`（9 项）：改规则文件→键变、
  改窗口常量→键变、改引擎源码→键变、缓存损坏→未命中、缓存目录必须在 `out/` 下。

**处置二：探针/CI 区分 `TIMEOUT` 与 `FAILED`**

`tools/determinism_probe.py` 的退出码现在是判据：

| 码 | 含义 | 该做什么 |
|---|---|---|
| 0 | 指纹一致 | 通过 |
| 1 | **PRODUCT_FAIL**：跨 seed 指纹不一致 | 查产品 |
| 2 | **ENV_SUSPECT**：耗时 > 基线中位数 2× | 查机器（并发进程/换页），**不得**判产品不确定 |

- 新增 `--gate [seeds]`（默认 `0,1,2,3`）：一条命令跑完多 seed 比对，
  输出 `DETERMINISTIC: <指纹>`；不必再手写 shell 循环。
- 耗时基线滚动保存 `_BASELINE_SAMPLES=20` 个样本取中位数，落 `out/.cache/determinism_baseline.json`；
  基线缺失/损坏按首次运行处理（**不能**因为基线坏了就报 ENV_SUSPECT）。
- 测试 `tests/unit/test_determinism_gate.py`（9 项）：慢→2、快→0、损坏基线→0、
  单 seed 无效、门禁真跑两 seed 一致。

### 取证补充：写入者画像（内容级证据，不只是 mtime）

上一版只用了 mtime，这一轮补了**内容级**证据与时间线：

| 证据 | 结论 |
|---|---|
| `git log --all --since`、`git reflog`：HEAD 仍是 `64f5be5`（06:27 那次提交） | 会话期间**没有任何 git 写入**（无提交/无 reset/无 stash 变动） |
| `git worktree list`：仅 1 个 worktree；无 `.git/index.lock` | 不是多 worktree/锁竞争 |
| `tests/unit/test_rule_verdict_type.py` 在会话开始时的 `find` 清单里**不存在**，00:05:23 出现 | 内容级新建，不是 mtime 刷新 |
| `models.py` 新增 `effective_verdict_type` 属性；`Makefile` gate 新增 `tools/check_no_aggregate_score.py` | 写入内容与本路线图（A 的"禁综合分" + C 的 verdict 契约）**同向且连贯** |
| `.codeartsdoer`(.16:07) / `.zwork`(.11:41) / `.arts`(.15:26) 均数小时未动 | 不是这些工具在活动 |
| 00:12 取内容 md5 基线 → 00:16 复检：6 个可疑文件 md5 **全部未变**，mtime 停在 00:08:52 | 写入是一段**集中突发**，之后停止 |

**结论**：是一次**有主题、成体系的并行编辑**（新增 C 契约测试 + verdict 推断属性 + gate 钩子），
不是随机损坏、不是同步工具触碰、也没有走 git。最可能是另一个 agent 会话在同一工作树上
按同一份 A/C 路线图作业。**`ps`/`lsof` 在沙箱内被拒（operation not permitted），
进程身份无法由本会话确认**——需人类执行：

```bash
ps aux | grep -E "python|pytest|agent|cursor|claude" | grep -v grep
lsof +D /Users/panshi/Documents/trae_projects/风水/zeri 2>/dev/null | grep -vE "\.git/|__pycache__"
```

**在身份确认前不合 C**（按用户裁定）。本会话已停止对 6 个热文件的写入，
只动 `tools/*` 与新增测试文件。

## [0.6.1] - 2026-11-02

主题：**只审「死规则」那一层** —— 起例固定、结果唯一、没有派别辩解空间的排盘计算。
本轮不动任何规则的 `status`，不动任何权重，只修「取错输入」和「算错粒度」，
并把两条埋在派别数据文件里的固定起例提升为一等事实。

### 修复（P0，算错而非算不出）

- **年五黄与年紫白互相矛盾（方位相反）**：`shensha.wuhuang_year` 直接把**公历年**
  当紫白年用，而立春（2/3–2/5）才是紫白的换年点。后果是每年 1 月 1 日至立春之间，
  `facts.wuhuang.year` 取到的是**下一年**的入中星，与同一张盘上的 `facts.zibai.year`
  恰好相差两位五、方位相反。以 2027-01-15 为例：年紫白仍属 2026（一白入中、五黄在离/正南），
  旧实现报 2027（九紫入中、五黄在坎/正北）——一南一北，结论完全反。
  现改为 `wuhuang_year_of_date()` 唯一入口，紫白年由 `zibai.zibai_year_of` 判定，
  与年紫白同源；`_FLY_ORDER` / `_year_center_star` 两份重复实现一并删除，只留 `zibai` 一份。
- **四废日按公历月取季**：`registry._get_season` 用 3-5/6-8/9-11/12-2 判四季，而四废口诀
  「春庚申辛酉、夏壬子癸亥、秋甲寅乙卯、冬丙午丁巳」以**四立**为界。故立春（2/4）到 3/1、
  立冬（11/7）到 12/1 之间的日课会整段取错季节、查错表。改为按节气月支判季
  （`_season_of_month_zhi`）。实证：2027-02-10 庚申（寅月）旧实现查冬表 → 漏判，
  现判四废；2027-11-23 丙午（亥月）旧实现查秋表 → 漏判，现判四废。

### 新增（固定起例，纯结构事实，不进 severity）

- **建除十二神**提升为一等事实 `facts.jianchu.{day,hour}`（原先是 `facts.donggong.jianchu`，
  且董公 JSON 一缺就整段变 `None`——而建除与董公派其实无关）。位次公式
  `(目标支序 − 月建支序) mod 12`，唯一入口 `core_symbol/jianchu.py`。
- **十二黄黑道（青龙十二神）**新增 `facts.huangdao.{day,hour}`：原先系统只认「勾陈」一颗
  黑道星，既答不出「今天是青龙还是白虎」，也答不出「这个时辰是不是黄道时」。
  起例「子午临申、丑未戌上、寅申加子、卯酉归寅、辰戌龙位、巳亥午中」起青龙顺行十二神。
  **黄/黑分组不入事实层**（那是吉凶断言），只导出 `HUANG_DAO_STARS` / `HEI_DAO_STARS`
  两张参考表供规则层用 `in` 表达。
- **交叉校验**：新起例推出的勾陈位与既有 `donggong_gouchen_heidao.json` **逐月 12/12 吻合**
  ——两张独立录入的表彼此自洽（不等于已取得原典）。

### 变更（只加字段，不改规则）

- `facts.wuhuang.year` 增 `zibai_year` / `palace_mountains` / `hit_palace` / `hit_palace_facing`；
  `hit_mountain` 语义**保持不变**（仍是"宫心那一山"），以免规则行为被动漂移（QUESTION Q-018）。
- `facts.donggong` 增 `heidao_star`（十二神名）；`is_heidao` 语义不变（仍为"勾陈日"，QUESTION Q-019）。
- `facts.tiaohou` 去掉裸 `except Exception`：数据文件缺失时 `applied=None` 并写明原因，
  不再把"文件坏了"伪装成"该格无调候"。
- 无用事日时 `facts.wuhuang.year.*` 的命中字段给 `None` 而非 `False`——
  三值逻辑下得到 unknown，规则降级为存疑，不会伪装成"没有命中"。
- `mountain.__all__` 补 `jian_xiang` / `ZHI_MOUNTAIN_INDEX`（原先定义在模块内但对外不可见）；
  `jian_xiang` docstring 与默认阈值自相矛盾（写 9° 正针、却用 3.0 阈值）已澄清，
  两说登记为 QUESTION Q-021，**默认值不变**。

### 测试

- 新增 `tests/unit/test_paipan_fixed.py`（28 项）：建除两条恒等式（建日=月建日、
  破日=月破日）逐月遍历、黄黑道 12/12 勾陈交叉校验、五黄立春前后换年自洽、
  五黄宫级命中覆盖庚辛、四废季节两个"旧口径必错"的日期、时家逐时重算不串味。
- 全量：`pytest` 全绿；`rules lint` 通过（无引用/签名/结构问题）。

### 已知问题（未修，需环境或人类介入）

- **测试套件偶发非确定（未定位）**：本轮共跑 12 次全量 `pytest`，观测到 2 次失败，且
  **两次落在不同测试**——`test_engine.py::test_no_hit_means_ok_but_unknown_keeps_needs_review`
  报 `state=不可用`（预期"可用"，即某条否决规则在无命中时仍触发），以及
  `test_required_and_negative.py::TestAdr0014EvidenceCap::test_lint_check_id_groups_exact_sets`
  的子进程 `rules lint` 输出集合比对失败。两者单独跑、按目录组合跑均 8/8 复现不出；
  固定 `PYTHONHASHSEED=0` 连跑 2 次全绿，之后随机种子连跑 4 次也全绿——**样本不足以定因**，
  故只登记不修，避免用"猜一个原因"换掉真实原因。
- 初步判断方向（供下一轮排查）：两处都涉及"跨调用共享的可变状态或集合遍历序"。
  建议的取证方式：全量跑 N 次，失败时打印 `ev.per_school[*].vetoes` 的 rule_id 与
  `groups` 的实际集合差（当前断言消息吞掉了实际值，需要先改断言的消息体——属测试增强，
  须单独提交）。这与本项目"同输入必同输出"的红线直接相关，优先级高于任何新功能。

## [0.6.0] - 2026-11-02

主题：**把“躺在盘上的模块”接进引擎** —— 紫白四盘（含时盘）、二十八宿值日、天德/月德/天赦。
本轮全部为「事实层 + 口径 + 规则」的增量，**没有任何一条规则升级为已考证**。

### 修复（P0，一致性：死模块 + 文档与代码互相打脸）

- **`zibai.py` 是死代码**：`derive_zibai_facts` 自 Phase 10 写好后**从未被调用**，
  `facts.zibai` 不存在、无任何规则可引用；与此同时 `coverage_gaps.yaml` 写“紫白日/时未实现”、
  README 写“未实现”，三处状态互相矛盾。现接入 `derive_facts`（年/月/日）+
  `overlay_hour_facts`（时），并改写缺口条目为「日盘起元口径未裁定」（`GAP-ZIBAI-DAYYUAN`）。
- **时盘必须在候选级重算**：日级缓存键不含时柱（0.5.0 的 P0 形态）。
  `derive_zibai_hour` 抽成唯一入口，阴阳遁由日盘结果传回，避免“同日子时星串到午时”。
  回归护栏：`test_hour_plate_differs_across_hours_same_day`（子时六白 / 午时九紫）。

### 新增（Phase 11）

**紫白四盘接入**
- `facts.zibai.{year,month,day,hour}`：入中星、九宫分布、五黄/二黑宫位、坐山所得星、五黄是否到山。
- 口径 `zibai_fly`（顺飞/逆飞），只作用于日/时盘；年/月盘恒顺飞（通书共识）。
- 规则 4 条：`PUB-ZIBAI-MONTH/DAY/HOUR-001`（五黄到山，慎用）、`PUB-ZIBAI-JI-001`（年紫白四吉到山，推荐）。

**二十八宿值日**
- `core-symbol/core_symbol/xiu.py`：七元起宿（一元甲子起虚），锚点 `1996-01-28`
  （甲子日 + 星期日 + 虚宿，三重校验），公式 `宿序 = (10 + 距锚点天数) mod 28`。
- **机器自校验**：宿之七政（木金土日月火水，按宿序 mod 7）必须等于当日星期；
  逐日扫 1900-2100 共 73,414 天**零违例**。表错一位即在此暴露。
- 外部对算：2026-11-02 = 毕、2027-07-11 = 昴，与三个黄历站点各自一致。
- 规则 2 条：`PUB-XIU-XIONG-001`（慎用）/ `PUB-XIU-JI-001`（可用），吉凶标签取《玉匣记》
  十四/十四粗标签，`notes` 明写“粗化不等于精确”。

**吉神表**
- `core-symbol/core_symbol/jishen.py`：天德（干或卦宫）、月德、月德合、天赦。
- 口径 `tiande_guaxiang`（整宫并集/渊海单支/考原单支）：两说在卦宫层面一致，
  分歧只在“取单支还是整宫”，故默认整宫，另两说保留并在报告回显。
- 规则 4 条：`PUB-TIANDE-001`、`PUB-YUEDE-001`、`PUB-YUEDE-HE-001`、`PUB-TIANSHE-001`；
  一律 `hard_veto=false`，**不进否决层**（《协纪辨方书》有“虽吉星不能解”之文，专指岁破）。

**报告**
- 新增「盘面事实（值宿 / 紫白 / 吉神，非吉凶）」节：无规则命中时也展示值宿、四盘入中、
  五黄到山、本月德位。节末固定桥接说明“结构/盘面确定 ≠ 结论确定”。

### 变更

- `rules_manifest.yaml`：75 → 85 条；`待考证` 63 → 73；`public` 47 → 57。
- `coverage_gaps.yaml`：删除「紫白日/时未实现」（已闭环），新增
  `GAP-ZIBAI-DAYYUAN`（日盘起元口径）与 `GAP-XIU-SHISHI`（值宿时禽 + 逐事项宜忌）；
  机器行由 8 条变 9 条，对应的金标准断言同步。
- `tools/gen_rules_phase11.py`：本轮 10 条规则 + 20 个 RT 向量的一次性生成器（产物入库）。

### 踩坑记录

1. **RT 向量的 overrides 多套了一层 `facts:`**：`_overrides` 把 `facts.<path>` 拆成
   `root="facts"` 后又返回 `{"facts": {root: node}}`，实际写成 `facts.facts.*`。
   后果不是报错，而是**20 个向量全部静默 MISS**（路径取值落到基准值 False）。
   教训与 AGENTS「补丁必须 fail-fast」同源：生成器里加 `assert root == "facts"` 与回读断言。
2. **`_strip_hits` 夹具必须跟上事实面**：新增规则后金标准 ctx 自带命中（昴为凶宿、年紫白一白），
   “无命中→可用”的测试随即名不副实。扩展夹具时给值宿用了哨兵值（28 宿非吉即凶，无中立值）。
3. **新规则在 `--allow-unverified` 下进“演示命中”而非 positives**：这是 ADR-0014 决策 3 的
   既有语义，不是漏接；报告里能看到规则、解释与出处。

### 测试锚点

| 结论 | 锚点 |
|---|---|
| 值宿锚点三重校验 | `tests/unit/test_xiu.py::TestAnchor::test_anchor_is_jiazi_sunday_xu` |
| 星期恒等式 1900-2100 零违例 | `tests/unit/test_xiu.py::TestWeekdayInvariant::test_no_violation_1900_2100` |
| 外部黄历对算 | `tests/unit/test_xiu.py::TestExternalCrossCheck` |
| 月紫白口诀表 | `tests/unit/test_zibai_facts.py::TestMonthPlate::test_koujue_table` |
| 时盘跨时辰不串味 | `tests/unit/test_zibai_facts.py::TestDayHourPlates::test_hour_plate_differs_across_hours_same_day` |
| 口径切换只动日/时盘 | `tests/unit/test_zibai_facts.py::TestCaliber::test_ni_flips_day_and_hour_only` |
| 天德 12 月表 = 口诀 | `tests/unit/test_jishen.py::TestTianDe::test_table_matches_koujue` |
| 天德两说并集 == 整宫 | `tests/unit/test_jishen.py::TestTianDe::test_gua_calibers_cover_same_gong` |
| 月德只取阳干 | `tests/unit/test_jishen.py::TestYueDe::test_only_yang_stems` |
| 规则库计数与向量引用 | `zeri rules lint`（85 条 / 20 个新向量全部存在） |

### 已知限制（本轮不实现）

- 日盘起元：符头法未实现（`GAP-ZIBAI-DAYYUAN`）。
- 值宿时禽、值宿逐事项宜忌（`GAP-XIU-SHISHI`）。
- 乌兔太阳、河洛理数、奇门/六壬：按原登记不动。
- 全部 10 条新规则 `status: 待考证`、`citation.quote: null`——补原文与签名前不产生可发布结论。

## [0.5.0] - 2026-11-02

### 修复（P0，正确性：跨时辰事实串味）

- **`build_context` 的事实缓存键缺时柱**（真实 bug，非测试问题）。
  - 症状：同一天的 12 个时辰候选共用「当日首个子时」算出的 `facts`，
    14:00 的日课会拿到 00:00 的刑冲害关系。表现是金标准案例（乙未时）在跑过
    全年生成后突然丢失「三未重复」结构判定，反而多出不相干的害/刑。
  - 根因：缓存注释写「derive_facts 不含时辰参数」，但 `derive_facts` 收到的是
    **四柱**（含时柱），`facts.structure`（刑冲害破合/重复计数/三合局）、
    `facts.xunkong.hits`、`facts.tongguan`、`facts.sanhe_ju` 都随时支变化。
  - 后果：生成器给出的 tier 与结构判定按「当日首个子时」计，**跨时辰结论全错**；
    更隐蔽的是 `test_brute_force_matches_sampled` 因暴力对照走同一缓存而「一致通过」，
    形成假阴性。
  - 修复：键改为四柱全名（`candidate_facts`），并把注释改成「键必须含时柱」。
    实测 `derive_facts` 单次 ≈0.09 ms（星历/玄空内部按日 lru_cache），
    4380 候选的额外代价 ≈0.4 s。

### 新增（Phase 9：斗首五行）

- **`core-symbol/core_symbol/doushou.py`**：二十四山斗首五行表（≠正五行）、
  十干化气（五运）、五星定位（元辰/贪狼/廉贞/武曲/破军）、番化诀、
  三元格/三武格、得位（五行寄生十二宫）。
- **斗首规则包 6 条**（DS-HUAQI v2 + DS-SANYUAN/DS-SANWU/DS-POJUN/DS-LIANZHEN/DS-DEWEI）。
  - `DS-HUAQI-001` v1 用「天干五合」近似化气是**错误建模**，v2 改为查真化气计数。
- **`reference` 层**（`school_policy.layer` 新增取值）：斗首 `enabled: true` 但
  **不进默认路由**——spec §5 的「五派输出」是逐字契约，且斗首吉凶强度未考证，
  不应直接改 tier。用户显式 `schools=("doushou",)` 才评估。
- **口径 `doushou_tu_changsheng`**：土行长生位「申（土寄坤）/寅（土寄艮）」两说，
  默认 shen，报告强制回显，两说对土行得位可给出相反结论。
- **前端**：`packs/doushou.ts` + `DayDetail` 参考层表格（只给星名与生克，不给吉凶着色），
  `DayEvaluation.doushou` 与五派并列但不进仲裁权重。

### 变更

- `rules_manifest.yaml`：70 → 75 条；修正两处历史笔误（`sanhe` 4 条从未登记、
  `tianxing` 缩进错位成顶层键）。
- `dead_rule_baseline.yaml`：斗首 6 条登记为 `reference_layer_not_routed`
  （不是 unknown 门控，原因不同）。

### 已知限制（本轮不实现，已登记 coverage_gaps）

- **紫白日/时**：三元日紫白须以符头定上中下元，与「甲子日一白顺行」简法结论不同，
  未取得可核抄本前不实现（年紫白已有）。
- **乌兔太阳**：排山图/截法图排布未见可核抄本，口诀转述互相矛盾。
- **奇门/六壬**：用神取法决定结论，属占断体系，超出「可审计可反驳」定位。
- **河洛理数**：配卦口径未裁定，且与玄空大卦部分重叠。

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
