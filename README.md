# 择日引擎（Zeri Engine）

离线、确定性、可审计的择日计算与复核工具。给定「人 + 地 + 事 + 时间窗」，输出**结构化判定**与**可复现报告**。

> **定位**：民俗时间管理与规则复核工具。不承诺准确率，不做「灵验度」评分，不提供化解/符咒/法事；
> 不替代工程安全、结构鉴定、医疗或法律意见。

---

## 这个项目解决什么问题

市面上的"黄历程序"通常做两件事：把吉神凶煞加成一个总分，然后给一个"上吉"。
本项目**明确拒绝**这种做法，改为：

| 维度 | 做法 |
|---|---|
| 硬约束 | 三煞、冲山、岁破、月破、四离四绝等**先过滤**，吉神不能抵消硬伤 |
| 单一总分 | **禁止**。输出分层向量 `hard_fail / strong_avoid / conflict / unknown / positive` |
| 多流派 | **并存**。同一日课可以是「A 派通过、B 派冲突、C 派未知」，不伪造共识 |
| 可溯源 | 每条判定带 `rule_id + version + 引文 + 参数哈希`；无原文的规则只能标 `待考证` |
| 定义级 vs 断言级 | **分离**。干支算术推论（六冲/自刑/重复）标 `定义级`，出处是内核规格；吉凶主张必须古籍原文 |
| 未知 | **必须暴露且分类**：缺输入 / 口径未定 / 规则未考证，各带解除条件 |
| 口径 | 争议项做成**命名注册表**，报告强制回显"本次用了哪个口径"，未裁定时给出对比式提示 |
| 可复现 | 同输入必同输出；报告含 `input_hash + rule_lib_version + engine_version + 历法口径快照` |

## 30 秒上手

```bash
# 复核一个已有日课（金标准案例，含口径选择）
python3 -m app_zeri.cli verify \
  --course 2027-07-11T14:00 --azimuth 320 \
  --task 修造 --strictness strict --allow-unverified \
  --caliber sansha=named_sansha

# 在时间窗内生成候选（分层排序 + 敏感性 + 稳健集）
python3 -m app_zeri.cli gen \
  --window 2027-07-01/2027-08-31 --site site.yaml \
  --task 修造 --top 20 --sensitivity --robustness

# 规则库自检（DSL / 引用完整性 / 签名 / 派别声明 / 规则清单一致性）
python3 -m app_zeri.cli rules lint
```

需要把各包加入 `PYTHONPATH`（或 `uv sync` 后安装）：

```bash
export PYTHONPATH=core-time/src:core-symbol/src:core-rule/src:core-eval/src:app-zeri/src:.
```

## 当前状态（诚实披露）

| 项 | 状态 |
|---|---|
| 历法内核（节气/四柱/农历/闰月/真太阳时） | ✅ 节气误差 ~15 s；1900-2100 回归面 + 边界交叉已测 |
| 规则库 | 86 条 = **10 条定义级**（结构判定，`severity=记录`，不影响 tier）+ **2 条有争议** + **74 条待考证**（断言级） |
| 派别 | 五派并列（正五行/三合/董公/玄空大卦/天星）+ **斗首（参考层，默认不入路由）** |
| 紫白四盘 | ✅ 年/月/日/时入中星 + 九宫飞布 + 五黄到山；飞布方向口径 `zibai_fly`（顺/逆）；年五黄按立春换年（与年紫白同源） |
| 建除 / 黄黑道 | ✅ 日家 + 时家；建除两条恒等式（建日=月建日、破日=月破日）逐月自校；十二神与既有勾陈表 12/12 交叉吻合 |
| 二十八宿值日 | ✅ 七元起宿 + 星期恒等式自校验（1900-2100 零违例）+ 三站黄历对算；**值宿吉凶标签为粗化** |
| 吉神表 | ✅ 天德（卦位口径 `tiande_guaxiang` 三选一）/ 月德 / 月德合 / 天赦 |
| 确定性门禁 | ✅ `tools/determinism_probe.py` 两级指纹（决策面/输出面分开断言）多 seed 一致（20/20）；`make gate` 对输出面漂移写 `out/output-fail.flag`（带警告通过），决策面/机器忙仍阻断；CI 中直接调 `make determinism`/原始探针会以 64 拒绝；条件禁浮点、口径必须显式 `default`（`rules lint` 两条不变式 + 反证测试） |
| 覆盖率门禁 | ✅ `make gate` 先经 `make cov` 用 `pytest --cov` 新鲜采集，再 `coverage report --fail-under=80`；当前 84%；**包级 + 文件级 ratchet**（`tools/coverage_ratchet.py`）：app-zeri 68%、cli.py 34%、case_runner.py 44%、report.py 76% 均有地板，包内低于目标的文件没登记地板也会失败；无 `|| true`；旧 `.coverage` 不得作为数据源 |
| 死代码门禁 | ✅ `rules lint` 第 14 项：`derive_*` 必须有定义文件外的调用点（传递闭包）、符号层模块必须被 import；`coverage_gaps.yaml` 的 `implementation` 声明与代码事实双向核对 |
| 判定类型（C 第一批） | ✅ `verdict_type`(gate/vote/reference) + `engine_eligible` + 理由编码；参考层命中可见但不进 state/tier/publishable（当前 23 条已标，63 条待批量迁移） |
| 影子规则 | ✅ 1 条（`PUB-WUHUANG-PALACE-001`，`engine_eligible: false` 只观察不计分）；"观察不投票"有语义测试 |
| 三态判定 / 分层向量 / 派别并列 / 四类冲突 | ✅ 已实现，金标准案例通过 |
| 复核器 / 生成器 / 报告 / manifest | ✅ 4380 候选 ≈3.2 s（预算 3.5 s；逐候选叠加时柱后上调，见 CHANGELOG 0.5.0） |
| 稳健集 / 敏感集 | ✅ `--robustness`（坐向 ±uncertainty + 口径开关扰动矩阵） |
| 口径注册表 | ✅ 三煞（2 口径）/ 纳音（4 口径）/ 斗首土长生（2 口径）/ 紫白飞布（2 口径）/ 天德卦位（3 口径） |
| 案例库 | ⚠️ 仅 1 条 A 级金标准案例；论坛案例（511 条）尚未结构化入库 |
| 变异测试抽查 | ✅ 28/28 变异被抓住（`make mutation`） |
| 服务化（FastAPI/PWA） | ❌ 未实现（M10） |

**当前能给出什么结论**：

- ✅ **结构判定**（定义级，`severity=记录`）：有无自刑/三刑/六害/相破/三见/旬空/干冲/三合 —— **确定**
- ⚠️ **否决判定**：三煞/冲山/岁破等命中即 `REJECTED` —— 但断言级规则尚无原文，
  报告标为 **「演示性不可用」，明确"不作为排除依据"**（不再写"确定排除"）
- ❌ **可发布的吉凶结论**：`publishable` 取决于**该事项的必需规则集**是否全部可判定

**验收信号**：修造的必需集共 **8 条**（ADR-0012 拆分后），当前**已可判定 0 条** ——
不是实现缺失，而是 8 条全部 `待考证`、`quote` 为空，按 ADR-0014「未考证的必需规则即使
求值为 False 也算阻塞」一律计入阻塞。**补齐这 8 条的原文与签名，`publishable` 第一次为 true。**
这就是 P0 考证的完成定义，不需要"把所有待考证规则都考证完"。

## 目录结构

```
core-time/     事实层：节气、真太阳时、四柱、农历（禁止吉凶字段）
core-symbol/   符号层：干支关系、纳音、旬空、二十四山、紫白四盘、二十八宿、吉神表、派生事实
core-rule/     规则层：DSL 解析/求值、生命周期、provenance、派别路由、规则库 YAML
core-eval/     判定层：三态、分层向量、分歧度、敏感性、排序、结构检测器
app-zeri/      应用层：CLI、复核器、生成器、报告、案例运行器
cases/         案例库：schema + 分级案例 + 原文快照
tests/         单元/属性/金标准/契约/性能
docs/          DEVELOPMENT.md + ADR + QUESTIONS.md + research/（调研记录与证据等级）
tools/         规则生成器、CI 门禁脚本
```

## 关键文档

- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) —— 完整规格（架构、DSL、算法、测试策略、红线）
- [`AGENTS.md`](AGENTS.md) —— AI Agent 工作指令（角色边界、硬禁止、提交规范）
- [`docs/QUESTIONS.md`](docs/QUESTIONS.md) —— **必须由人类裁定的问题清单**（当前 17 项）
- [`docs/research/2026-11-xiu-jishen-zibai.md`](docs/research/2026-11-xiu-jishen-zibai.md) —— 紫白/值宿/吉神的检索式、来源等级与机器自校验方式
- [`docs/adr/`](docs/adr) —— 11 份架构决策记录（0009 定义级 severity 白名单 / 0010 必需集发布 / 0011 时间基准两轴）
- [`CHANGELOG.md`](CHANGELOG.md) —— 变更与踩坑记录

## 开发

```bash
make test        # 全量测试（含性能）
make test-fast   # 跳过 slow 标记
make cov         # 覆盖率（门禁：整体 ≥80% + 包级/文件级 ratchet）
make lint        # 规则库 lint（含规则清单一致性）
make mutation    # 变异测试抽查（验证测试真的能抓住错误）
make gate        # 全部 CI 门禁（YAML + 覆盖率 + lint + 签名 + 无网络扫描）
```

## 许可与数据

- 代码：内部使用。
- 规则出处：仅登记**公版古籍书名**，未录入任何现代出版物全文；`citation.quote` 为 `null` 表示"尚未核对原文"。
- 案例：`cases/raw_snapshots/` 为内部参考快照，不入公开分发。
