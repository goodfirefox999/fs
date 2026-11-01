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
| 规则库 | 52 条 = **10 条定义级**（结构判定，`severity=记录`，不影响 tier）+ **42 条待考证**（断言级） |
| 三态判定 / 分层向量 / 派别并列 / 四类冲突 | ✅ 已实现，金标准案例通过 |
| 复核器 / 生成器 / 报告 / manifest | ✅ 4380 候选 1.86 s（预算 2 s，余量 7%） |
| 稳健集 / 敏感集 | ✅ `--robustness`（坐向 ±uncertainty + 口径开关扰动矩阵） |
| 口径注册表 | ✅ 三煞（2 口径）/ 纳音（4 口径），报告回显 + 对比式提示 |
| 案例库 | ⚠️ 仅 1 条 A 级金标准案例；论坛案例（511 条）尚未结构化入库 |
| 变异测试抽查 | ✅ 8/8 变异被抓住（`make mutation`） |
| 服务化（FastAPI/PWA） | ❌ 未实现（M10） |

**当前能给出什么结论**：

- ✅ **结构判定**（定义级，`severity=记录`）：有无自刑/三刑/六害/相破/三见/旬空/干冲/三合 —— **确定**
- ⚠️ **否决判定**：三煞/冲山/岁破等命中即 `REJECTED` —— 但断言级规则尚无原文，
  报告标为 **「演示性不可用」，明确"不作为排除依据"**（不再写"确定排除"）
- ❌ **可发布的吉凶结论**：`publishable` 取决于**该事项的必需规则集**是否全部可判定

**验收信号（v0.3 新增）**：修造的必需集共 10 条，**已可判定 9 条**，只差 `ASSERT-REPEAT-001`
一条原文 —— 补齐它，`publishable` 第一次为 true。这就是 P0 考证的完成定义，
不再需要"把 42 条全考证完"。

## 目录结构

```
core-time/     事实层：节气、真太阳时、四柱、农历（禁止吉凶字段）
core-symbol/   符号层：干支关系、纳音、旬空、二十四山、派生事实（神煞方位）
core-rule/     规则层：DSL 解析/求值、生命周期、provenance、派别路由、规则库 YAML
core-eval/     判定层：三态、分层向量、分歧度、敏感性、排序、结构检测器
app-zeri/      应用层：CLI、复核器、生成器、报告、案例运行器
cases/         案例库：schema + 分级案例 + 原文快照
tests/         单元/属性/金标准/契约/性能
docs/          DEVELOPMENT.md + ADR + QUESTIONS.md
tools/         规则生成器、CI 门禁脚本
```

## 关键文档

- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) —— 完整规格（架构、DSL、算法、测试策略、红线）
- [`AGENTS.md`](AGENTS.md) —— AI Agent 工作指令（角色边界、硬禁止、提交规范）
- [`docs/QUESTIONS.md`](docs/QUESTIONS.md) —— **必须由人类裁定的问题清单**（当前 11 项）
- [`docs/adr/`](docs/adr) —— 11 份架构决策记录（0009 定义级 severity 白名单 / 0010 必需集发布 / 0011 时间基准两轴）
- [`CHANGELOG.md`](CHANGELOG.md) —— 变更与踩坑记录

## 开发

```bash
make test        # 全量测试（含性能）
make test-fast   # 跳过 slow 标记
make cov         # 覆盖率（门禁：整体 ≥80%）
make lint        # 规则库 lint（含规则清单一致性）
make mutation    # 变异测试抽查（验证测试真的能抓住错误）
make gate        # 全部 CI 门禁（测试 + lint + 签名 + 无网络扫描）
```

## 许可与数据

- 代码：内部使用。
- 规则出处：仅登记**公版古籍书名**，未录入任何现代出版物全文；`citation.quote` 为 `null` 表示"尚未核对原文"。
- 案例：`cases/raw_snapshots/` 为内部参考快照，不入公开分发。
