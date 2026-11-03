# 择日引擎（Zeri Engine）开发文档 v1.0

> 本文档合并了两份上游规格（《择日引擎 Zeri Engine 开发文档 v1.0》与《择日决策支持系统 开发文档 v1.0》），
> 并在冲突处给出裁定与理由（见第 2.4 节与 `docs/adr/`）。
> **面向对象**：AI 编程 Agent（实现者）+ 人类（考证者/裁定者）。

---

## 0. 角色定义（先读这一节）

你是**实现者**，不是考证者。

| 你负责 | 你不负责（必须停下来问人） |
|---|---|
| 代码、DSL 草稿、测试、报告、文档、重构 | 判定某条择日规则是否成立 |
| 历算算法实现与数值验证 | 选择派别立场、裁定派别冲突 |
| 把人类给定的原文引文结构化 | 编造或推测古籍出处 |
| 发现规格矛盾并上报 | 自行修改 `status: 已考证` 的规则 |

**硬禁止（违反即视为任务失败）：**

1. 编造规则、口诀、出处、卷次。不确定就写 `status: 待考证` 并输出 `QUESTION` 块。
2. 把三态判定压缩成单一总分；跨派别合成"综合吉凶分"。
3. 在事实层（`core-time`/`core-symbol`）出现"吉/凶/宜/忌"字样。
4. 判定层自行计算天文量（必须调 `core-time`）。
5. 运行时联网、调用大模型 API、依赖外部服务。
6. 跳过测试、削弱测试、为通过测试而改测试断言。
7. 超出任务范围改动（顺手重构、顺手升级依赖）。

**每个任务的固定流程**：读规格 → 写测试（红）→ 实现（绿）→ 更新文档 → 填自审清单 → 提交。

---

## 1. 产品定义与边界

**是什么：** 离线、确定性、可审计的择日计算与复核工具。给定"人 + 地 + 事 + 时间窗"，
输出结构化判定与可复现报告。

**两个核心产品形态：**

- **复核器（Verifier）**：输入已有日课 → 输出命中规则明细、三态结论、派别分歧。
- **生成器（Generator）**：输入约束 → 在时间窗内穷举筛选 → 输出可用集与分层排序。

**明确不做：**

- 不承诺准确率、不做"灵验度"评分。
- 不做付费"化解/符咒/法事"任何环节。
- 不输出自然语言自由生成的断语（只允许模板化解释）。
- 不做移动端；先 CLI + 库，后期 FastAPI + PWA（M10，未实现）。

**非功能要求：**

- 全离线（CI 有 `tools/no_network_scan.py` 强制）；
- 同输入必同输出（含随机种子固定）；
- 单次一年窗口全量穷举 < 3.5 s（52 规则时代为 2 s；Phase 4–8 五派 facts + 真星历后实测 ≈2.4 s；Phase 9 修掉「事实按日缓存」后逐候选叠加时柱，实测 ≈3.2 s——见 CHANGELOG 0.5.0）；
- 所有结论可回溯到规则 id + 版本 + 引文。

---

## 2. 架构与分层铁律

```
app-zeri/          应用层：CLI、报告编排、用例运行器（只组合，不写计算）
core-eval/         判定层：三态评估、分歧度、敏感性分析、排序、结构检测
core-rule/         规则层：DSL 解析、规则库、版本与生命周期、出处追溯、派别路由
core-symbol/       符号层：干支、神煞、二十四山、分金、纳音、旬空（纯函数）
core-time/         事实层：节气、真太阳时、时区、太阳黄经、儒略日、农历
cases/             案例库：结构化案例 + 原文快照 + 分级
tests/             单元/属性/金标准回归/契约/性能
docs/              本文档 + ADR + 争议项登记
```

### 2.1 铁律

1. **Fact 与 Judgment 物理隔离**，跨层只能单向依赖（上→下）。
2. **判定层不得计算天文**，一律经 `core-time` 接口。
3. **每条判定必须带 provenance**（规则 id、规则库版本、引文、参数快照）。
4. **规则即数据**：新增规则 = 新增 YAML + 测试，不改引擎代码（除非新增算子）。
5. **争议项必须显式配置化**，并在报告中回显本次取值。
6. **未知必须暴露**：输入缺失、依据未核、口径未裁定 → 一律 `unknown`，不得静默通过。

### 2.2 依赖方向

```
app-zeri → core-eval → core-rule → core-symbol
                                 ↘ core-time
```

`core-symbol` 不直接 import `core-time`：节气日期、四柱干支由调用方以参数注入
（`derive_facts(..., term_dates=..., year_zhi=...)`）。这样符号层可独立测试，也避免循环依赖。

### 2.3 零第三方依赖策略

核心五包仅依赖标准库（`datetime`/`math`/`dataclasses`/`json`/`hashlib`/`zoneinfo`）。
唯一外部依赖是 `pyyaml`（规则库解析）。**未采用 pydantic**：数据模型用 `dataclass` + 显式校验函数，
理由见 `docs/adr/0001-architecture.md`。

### 2.4 两份上游规格的冲突裁定

| 冲突点 | Zeri Engine | 决策支持系统 | 本实现裁定 |
|---|---|---|---|
| 判定输出 | 三态 `不可用/可用/存疑` | 四级 `REJECTED/NEEDS_REVIEW/ACCEPTABLE/PREFERRED` | **两者并存**：`state` 用三态，`tier` 用四级；`tier` 由分层向量推导，不引入新语义 |
| 排序 | 字典序 `(否决派数, caution 数, rank 均值)` | Pareto 分层 | **两者并存**：`sort_key` 用字典序，`pareto_front` 提供非支配集 |
| 结构检测位置 | 未明确 | 必须独立实现 | 独立模块 `core-eval/structure.py`，不混入吉凶规则 |
| 规则状态 | `draft/待考证/已考证/有争议/弃用` | `DRAFT/REVIEWED/PUBLISHED/DEPRECATED` | 采用 Zeri 的五态（更细），并在 `lifecycle.py` 给出迁移表 |
| 历算库 | `skyfield` | Skyfield/Astropy | **自实现 VSOP87 截断**，理由见 ADR-0002（离线可复现、无二进制星历依赖） |
| 服务化 | FastAPI + PWA | 同 | 未实现（M10） |

---

## 3. 目录结构

```
pyproject.toml            # workspace 根 + pytest/coverage/ruff/mypy 配置
AGENTS.md                 # 第 12 节内容（独立抽出）
core-time/src/core_time/{ephemeris,jieqi,lunar,calendar,solar_time,config}.py
core-symbol/src/core_symbol/{ganzhi,nayin,mountain,shensha,registry}.py
core-rule/src/core_rule/{dsl,loader,lifecycle,models,policy,provenance,registry,errors}.py
core-rule/rules/{public,doushou,xuankong,zhengwuxing}/*.yaml
core-rule/config/{task_kinds.yaml,school_policy.yaml}
core-eval/src/core_eval/{engine,structure,disagreement,ranker,sensitivity}.py
app-zeri/src/app_zeri/{cli,verifier,generator,report,case_runner,schemas}.py
cases/{schema.py,graded/{A,B,C}/,raw_snapshots/}
tests/{unit,property,golden,bench,conftest.py}
tools/{gen_rules,check_status_signature,no_network_scan}.py
docs/{DEVELOPMENT.md,QUESTIONS.md,adr/}
```

---

## 4. 数据模型

### 4.1 输入三对象

**Person（命主）** —— 全部字段可选；缺失时相主类规则降级 `unknown`。

| 字段 | 类型 | 说明 |
|---|---|---|
| name | str? | 可匿名 |
| birth_dt | datetime? | 本地时间，用于推算年命 |
| birth_lon / birth_lat | float? | 用于真太阳时 |
| gender | str? | 男/女 |
| year_zhi / year_gz | str? | 人工覆盖（优先于推算） |
| lunar_override | bool | 农历/闰月归属人工指定 |

**Site（地点与坐向）**

| 字段 | 类型 | 说明 |
|---|---|---|
| azimuth_deg | float | 实测方位角 [0,360) |
| mountain / facing | str? | 由角度推算，可覆盖 |
| fenjin | str? | 分金（可空，空则相关规则降级"存疑"） |
| lat, lon | float | 天文与真太阳时 |
| measure_method | str | 罗盘/GPS/图纸 |
| angle_uncertainty_deg | float | 误差估计，驱动扰动报警 |

**Task（事项）**

| 字段 | 类型 | 说明 |
|---|---|---|
| kind | enum | 见 4.2 |
| nodes | list[str] | 节点：动土/上梁/安龛/入座… |
| window | (datetime, datetime) | 候选时间窗 |
| granularity | enum | day / day_hour |
| strictness | enum | normal / strict（修旧宅、宗祠默认 strict） |
| extra_constraints | dict | 用户附加硬约束 |

### 4.2 TaskKind 枚举（24 项）

`动土 修造 上梁 竖柱 安门 安灶 入宅 移徙 安葬 破土 立碑 修坟 修祠 安龛 升座 开光 嫁娶 纳采 出行 签约 开业 交易 求医 祭祀`

每个 kind 在 `core-rule/config/task_kinds.yaml` 声明：`required_nodes`、`applicable_rule_tags`、
`default_strictness`、`forbidden_rule_tags`。

### 4.3 输出模型

**Judgment（单条判定）**

```
rule_id, rule_version, school, category, status, severity, target,
matched(bool), participation(判定/仅登记/输入不足), hit_detail,
citation(结构体), explanation(模板), params_hash, unknown_paths, warnings
```

**Citation（引文，结构化）**

```
source, edition, juan, pian, quote(原文), url_or_path,
verified_by, verified_at, confidence(高/中/低)
```

`quote: null` **不是缺陷**，它精确表示"尚未核对原文"。禁止为填满字段而编造卷次。

**Evaluation（一次评估）**

```
state: 不可用 | 可用 | 存疑
tier:  REJECTED | NEEDS_REVIEW | ACCEPTABLE | PREFERRED
vetoes / cautions / notes / positives / unknowns: list[Judgment]
per_school: dict[school, SchoolResult]      # 各派并列，不合成
conflicts: list[{type, detail, states/severities}]
vectors: {hard_fail_count, strong_avoid_count, conflict_count,
          unknown_count, note_count, positive_count, positive_vector, feasibility_vector}
manifest: {input_hash, facts_hash, rule_lib_version, engine_version, config, schools, rule_counts}
```

**三态判定规则（唯一权威定义）：**

- 任一 `severity=禁用` 且 `hard_veto=true` 命中 → `不可用`
- 否则存在 `慎用` 命中（断言级或定义级结构）→ `存疑`
- 否则 → `可用`

**规则状态决定参与方式（ADR-0007）：**

| status | 出处要求 | 是否参与判定 | 结论去向 |
|---|---|---|---|
| `定义级` | `citation.kind: spec` + 规格条款 | **直接参与** | `structural`（severity 只能是 `记录`，**不影响 tier**） |
| `已考证` | `citation.kind: classic` + 原文 + 签名 | **直接参与** | veto / caution / positive |
| `待考证`/`有争议` | 可空 | 默认不参与 | `unknown`（reason=`unverified_rule`） |
| `draft` | 可空 | 不参与 | 不评估 |

`--allow-unverified` 放行 `待考证/有争议` 参与判定并标 warning，**但报告仍标"不可对外发布"**。

**unknown 三分类（评审要求，必须分开统计）：**

| reason | 含义 | 解除条件 |
|---|---|---|
| `missing_input` | 缺输入（命主未提供、分金为空） | 补输入即可判定 |
| `caliber_undecided` | 口径未裁定（坐山纳音体系、月五黄起法） | 需先定口径（见第 7.3 节） |
| `unverified_rule` | 规则未考证 | 需补原文并签名 |

**分层向量（`Evaluation.vectors`）：**

```
hard_fail_count / strong_avoid_count / assertion_caution_count / structural_caution_count /
structural_neutral_count / conflict_count / unknown_count / unknown_by_reason /
unverified_hit_count / disputed_count / missing_input_count / caliber_undecided_count /
note_count / positive_count / positive_vector / feasibility_vector
```

`publishable`（布尔位，进 JSON 与报告首行）：

- **有必需集时**（`required_rules.yaml`）：`tier != REJECTED` 且 无冲突 且
  **必需集内全部 `participation == "判定"`**（无演示、无输入不足）。
  非必需规则的 unknown/待考证只降级为「参考层缺失」，**不阻塞发布**（ADR-0010）。
- **无必需集时**：退回严格口径（`unverified_hit_count = 0` 且 `disputed_count = 0` 且无冲突）。

> **为什么改**：若要求"全库规则都已考证"，`publishable` 会永久 false，考证工作失去验收信号。
> 修造必需集 10 条，当前已可判定 9 条 —— 补齐 `ASSERT-REPEAT-001` 一条原文即可第一次 true。

**tier 推导（不含新语义，只做分层）：**

- `hard_fail > 0` → `REJECTED`
- 否则 `strong_avoid / conflict / unknown > 0` → `NEEDS_REVIEW`
- 否则 `positive >= 2` 或 `positive >= 1 且正向权重均值 >= 1.0` → `PREFERRED`
- 否则 → `ACCEPTABLE`

---

## 5. 规则 DSL 规范

### 5.1 文件字段

```yaml
api_version: 1
rule_id: PUB-SANSHA-001        # 全局唯一，前缀=派别缩写，支持多段
version: 1                      # 规则内容变更即 +1
school: public                  # public|zhengwuxing|doushou|xuankong|custom
category: 三煞占山（年）
status: 待考证                  # draft|待考证|定义级|已考证|有争议|弃用
hard_veto: true
severity: 禁用                  # 禁用|慎用|可用|推荐
target: mountain                # mountain|facing|day|hour|person|node
applies_to:
  task_kinds: [动土, 修造, ...]
  node_kinds: []
  strictness_min: normal
condition:                      # 见 5.2
  fact: facts.sansha.year.hit_mountain
  op: eq
  value: true
score_weight: null              # 仅排序层用；veto 规则必须为 null
severity_overrides:             # 可选：按派别覆盖严重度（ADR-0008）
  zhengwuxing: 慎用
citation:
  source: 《协纪辨方书》
  quote: null                   # status=已考证 时不得为空
  verified_by: null
tests: [RT-PUB-SANSHA-001-HIT, RT-PUB-SANSHA-001-MISS]   # 至少 2 项，须真实存在
explanation: "坐山{site.mountain}落于年支三合局所临三煞之方，按本规则判为禁用。"
supersedes: null
```

### 5.2 条件语法（唯一求值器，禁止旁路）

**组合节点：** `{all: [...]}` / `{any: [...]}` / `{not: {...}}`，可嵌套，**深度 ≤ 4**。

**原子节点：** `{fact: <点路径>, op: <算子>, value: <标量|列表|区间>}`
或 `{fact: ..., op: ..., value_from: <另一条路径>}`（值来自上下文，用于"坐山 vs 三煞方位"这类动态比较）。

| op | 语义 |
|---|---|
| eq / ne | 标量比较 |
| in / nin | 集合归属（value 可为 list/dict/str） |
| intersects | 两集合有交集 |
| gte / lte / between | 数值比较（between 含边界） |
| exists | 字段非空（`None`/空集合/空串为假） |
| same_group | 同属某干支组：`value: {path: ..., kind: sanhe\|sanhui\|liuhe\|chong\|hai\|xing\|po}` |
| count_gte / count_eq | 集合长度比较 |

**允许的 fact 根命名空间（白名单，越界在加载期即报错）：**

`course.*`、`site.*`、`person.*`、`task.*`、`time.*`、`facts.*`

**求值要求：** 纯函数、无副作用、可对缺失字段返回 `unknown`（不得抛异常吞掉）；
`unknown` 导致该规则判定降级为"存疑"并在报告标注"输入不足"。

**数值纪律（整数比，2026-11-02 增补）：**

| 要求 | 理由 | 门禁 |
|---|---|---|
| 条件里**不得**出现浮点字面量，数值比较用整数或整数比（`3:2`、`60/40`、`15/45`） | 浮点让判定依赖求值顺序与累加路径，`0.1+0.2≠0.3` 一旦落在 `gte/between` 边界就会翻面；择日本质是"过线/不过线" | `rules lint` 的 `_check_no_float_literals`（含嵌套） |
| 口径组必须**显式**声明 `default` | 缺省时加载器退化为 `next(iter(calibers))`＝"YAML 第一个键"，让书写顺序变成语义 | `rules lint` 的 `_check_calibers` |
| 数值型口径用 `params` 承载常数 | 同一口径只是常数不同（兼向阈值 3.0°/4.5°）时改 config 即换口径，不必改代码 | `calibers/*.yaml` 的 `params` 字段 |

> 两条门禁都配了**反证测试**（构造违规样本断言报警 + 移除触发条件断言沉默），
> 见 `tests/unit/test_lint_invariants.py`。只断言"当前恰好为空"不算验证。

**三值逻辑（Kleene）：**

- `all`：任一 False → False；否则任一 None → None；否则 True
- `any`：任一 True → True；否则任一 None → None；否则 False
- `not`：True→False，False→True，None→None

> **陷阱**：`False ∧ unknown = False`。若希望"事实不可得即 unknown"，条件只能依赖该事实本身，
> 不能与另一个会返回 False 的原子做 `all`（本项目在 `PUB-YINFU-001` 上踩过此坑）。

### 5.3 规则生命周期状态机

```
draft → 待考证 → 已考证
              ↘ 有争议 →（人类裁定）→ 已考证 | 弃用
已考证 →（原文复核发现错误）→ 待考证（必须升 version 并保留历史）
```

**权限：** Agent 只能创建 `draft/待考证`；把状态改为 `已考证/有争议/弃用` 的提交必须由人类签名
（commit trailer `Verified-By:`）。CI 检查：`tools/check_status_signature.py`。

### 5.4 派别包与路由

- 每派一个目录，独立加载，互不引用。
- `core-rule/config/school_policy.yaml` 声明：启用哪些派、各派是否默认参与否决、权重、场景路由。
- **路由必须是数据**：`task_kind → 参与派别列表`，禁止在代码里写 if-else。
- 争议大的派（斗首、玄空大卦）默认 `participates_in_veto: false`，只进参考层。

---

## 6. 历算内核规格（core-time）

| 项 | 实现 | 精度 |
|---|---|---|
| 太阳视黄经 | VSOP87D 地球 L 序列截断（L0 64 项…L5 1 项）+ 章动 + 光行差 + FK5 修正 | < 5″ |
| 节气时刻 | 牛顿迭代反解 λ=15°k，输出 UTC + 本地双份 | 实测与权威历书差 ~15 s |
| ΔT | Espenak & Meeus 锚点线性插值（1800-2200） | ≤ 40 s |
| 真太阳时 | 经度时差 + 均时差（Meeus 28.3） | 均时差 ±10 s |
| 农历 | 定朔（Meeus 49 章，含 14 项行星摄动）+ 定气置闰 | 朔日判定误差 < 1 min |
| 四柱 | 年界/月界/日界全部可配置 | — |

**争议口径（全部配置化，报告回显）：**

- `use_true_solar_time`：默认 `False`
- `day_boundary`：`early`（子初 23:00 换日）/ `late`（子正 00:00 换日，默认）
- `year_boundary`：`lichun`（默认）/ `newyear`
- `month_boundary`：`jieqi`（默认）/ `lunar`
- 闰月归属：可配置 + 可人工覆盖
- `timezone`：默认 `Asia/Shanghai`；历史时区变更不做（已知限制）

**不变量（属性测试必测，`tests/property/test_invariants.py`）：**

六十甲子循环闭合；节气严格单调；节气区间无缝无重叠；方位角归一 [0,360)；
真太阳时跨经度连续；同输入幂等；求值器纯函数（不改 ctx）。

**派生事实注册表（`core-symbol/registry.py`）：**

| 事实 | 状态 | 提供方 |
|---|---|---|
| 三煞（年/月） | 待考证 | 本系统提供 |
| 太岁 / 岁破 / 月破方位 | 待考证 | 本系统提供 |
| 年五黄（按**紫白年**立春换年；山级 `hit_mountain` + 宫级 `hit_palace`） | 待考证 | 本系统提供 |
| 月五黄 | 有争议 | **不提供**（口径未裁定） |
| 四离四绝 | 待考证 | 本系统提供 |
| 阴府候选 | 有争议 | **不推断**（坐山纳音取用体系未裁定） |
| 旬空 | 已考证 | 本系统提供（公版表） |
| 斗首五行 / 化气 / 五星 / 三元三武 / 得位 | 待考证（得位有争议） | 本系统提供（参考层） |
| 玄空大卦：卦运 / 旺气 / 卦气 / 抽爻 | 待考证 | 本系统提供 |
| 天星：七政到山到向 / 三合照 / 升殿 | 待考证 | 本系统提供（紫气缺，`PARTIAL`） |
| 紫白：年/月/日/时四盘 | 待考证 | 本系统提供 |
| 二十八宿值日 | 待考证 | 本系统提供（星期恒等式自校验） |
| 吉神：天德 / 月德 / 月德合 / 天赦 | 待考证（天德有争议） | 本系统提供 |
| **建除十二神（日家 / 时家）** | 待考证 | 本系统提供（纯位移） |
| **十二黄黑道（日家 / 时家）** | 待考证 | 本系统提供（纯位移；黄/黑分组不入事实） |
| 都天煞 / 伏兵大祸 / 天地官符 / 大小月建 / 杨公忌 / 重丧 / 三丧 / 妨翁姑 / 妨父母 / 修旧宅加严 | 待考证 | **不提供** |

"不提供"的事实一律以 `value: null` 显式登记，相关规则求值为 `unknown`，**不得静默通过**。
缺输入时命中字段给 `None`（→ unknown）而非 `False`，避免把"判不了"伪装成"没命中"。
登记项必须真的落地到 `facts.*`（守护测试：`test_paipan_fixed.py::test_every_registered_fact_root_is_materialized`）。

---

## 7. 判定引擎算法（core-eval）

**流水线（严格按序）：**

1. **输入校验与规范化**：补全派生字段，记录所有人工覆盖项。
2. **候选枚举**：按 `granularity` 生成候选；`day` 粒度取 12:00 单点且不评估时级规则。
3. **事实展开**：为每个候选计算 `facts.*`（`core_symbol.derive_facts`）。
4. **规则匹配**：按 `applies_to` 过滤 → 逐条求值 → 生成 Judgment（含 unknown 处理）。
5. **三态判定**：按 4.3 定义，逐派计算。
6. **派别并列**：`per_school` 各派独立三态，**不合并分数**；综合 state 取各派最严。
7. **共识集与排序**：共识度是**整数比** `favorable/voters`（阈值读
   `core-rule/config/consensus.yaml`，闸门层/参考层/沉默派不进分母，见 ADR-0015）；
   排序键见 `ranker.sort_key`，末位是整数计数 `positive_count`，**不得为均值**。
8. **分歧度**：`disagreement(t) = 1 - 众数频次/派数`；全局为候选集均值。
9. **敏感性分析**：对 `use_true_solar_time`、`day_boundary`、`year_boundary`、`坐向 ±3°`
   各做一次重算，输出"结论翻转清单"。
10. **报告与 manifest**：输入哈希 + 规则库版本 + 参数快照，保证可复现。

**冲突检测（四类，只登记不裁定）：**

| 类型 | scope | 触发条件 | 语义 |
|---|---|---|---|
| `rule_conflict` | school | **同一派内**两条规则对同一 target 一条判禁用、一条判推荐/可用 | 规则互相抵消（如"天德吉 vs 勾陈凶"） |
| `verdict_conflict` | school | 派别间一派不可用、一派可用 | 结论互斥 |
| `state_divergence` | school | 派别间三态不同（非互斥） | 一般分歧 |
| `policy_divergence` | school | 同一 category 在不同派别下 severity 不同 | 口径分歧 |

`rule_conflict` 与 `state_divergence` **语义不同，不得混用**：
前者是"同一派内规则互相抵消"，后者是"派别之间不一致"。
前者携带 `rule_a / rule_b / severities / citations`，报告可直接并列双方出处。

各派必须看到**完全相同的输入事实**：`per_school[school].fact_hash` 必须一致，
否则分歧度指标被输入不一致污染，引擎直接抛错。

**性能预算：** 365 天 × 12 时 = 4380 候选，单机 < 3.5 s（52 规则时代 2 s；五派 facts + 真星历后 ≈2.4 s；逐候选时柱叠加后 ≈3.2 s；防回归靠相对门禁 中位数×1.5）；
用暴力全量解作为对照实现，比对结果完全一致（`tests/bench/test_perf.py`）。

**已知债务（中长期）：CI slow bench 的绝对秒数在追 runner 抖动。**
2026-11-03 一天内：7.0s 档被 6.59/7.34 打穿 → 9.0s 档被 9.02/9.36 打穿 →
13.0s 档（9.36 × 1.39）。本地 10 个样本稳定 3.06–3.42s，说明不是产品回归，
而是 job-to-job runner 比值在 2.03–2.88× 之间漂。根因：CI 每次是全新 workspace，
`bench_history.ci.jsonl` 只 upload 为 artifact、**没有 restore**，所以相对门禁
（历史中位数 ×1.5）在 CI 里没有基线、实际是失效的，只剩绝对秒数兜底。
目标形态：用 `actions/cache` 恢复 CI 历史（按 OS/解释器分键），以**历史成功
run 中位数 ×1.5** 为主门禁；绝对秒数只作 O(n²) 兜底（当前回归线 CI 口径 ~26s）。
触发条件：下一次 13.0s 档在没有本地回归证据时再被打穿，先实现相对门禁，
不得继续上调绝对档。

---

## 8. 生成器与复核器规格

**复核器**：输入日课 → 单候选评估 → 报告。支持"仅校验不排序"。

**生成器**：输入约束 → 三级剪枝（年/月级粗筛 → 日级 → 时级）→ 全量评估 → Top-K（默认 20）。

- 剪枝不得改变结果集（用暴力对照验证）。
- 支持"排除集"（用户指定不可用日期）、"必须包含节点"、"多节点同日/异日"约束。
- 输出必须包含"无解说明"：若可用集为空，给出被否决原因直方图，
  **不得放宽硬约束来凑答案**（放宽需显式 `--relax` 并在报告大字标注）。

**CLI（已实现）：**

```
zeri verify --course 2027-07-11T14:00 --azimuth 320 --task 修造 --out report.md
zeri gen --window 2027-01-01/2027-12-31 --azimuth 320 --task 动土 --top 20 --sensitivity
zeri cases run --grade A --out out/
zeri rules lint
zeri rules diff <old_dir> <new_dir>
```

全局参数：`--allow-unverified`、`--school`（可多次）、`--param key=value`、`--json`、
`--fail-on-veto`（供 CI 使用）、`--true-solar-time`、`--day-boundary`、`--year-boundary`。

**后期 FastAPI（未实现）**：`POST /verify`、`POST /generate`、`GET /rules`，请求体即第 4 节 schema。

---

## 9. 案例库与回归体系

**用途限定（写进 README 与报告页脚）：** 案例只用于验证"实现是否符合宣称规则"，
**不用于验证择日是否灵验**；任何输出不得称为准确率，只能说"与作者判定吻合度"。

**分级：** A（输入完整、参数可推断、来源可查）→ 进回归集；B（需假设）→ 仅做分歧与缺口分析；
C（残缺/来源不明）→ 不统计。

**schema（`cases/schema.py`）：** 必含 `source.snapshot_path`（原文快照，防删帖）、
`params_assumed`（显式列出所有人为假设）、`author_claim`（原样保留，不参与判定）、`reproducibility.grade`。

**运行器产出四份报告：**

1. 与作者判定吻合度（Cohen's kappa，措辞固定）
2. 规则覆盖率（多少案例出现"无规则可判"）
3. 分歧清单
4. 规则缺口清单

**必做对照实验：** 标签随机打乱后重跑吻合度；若下降不显著，说明规则集对案例无判别信息，
必须在报告中标注该结论（`case_runner.py` 已实现）。

---

## 10. 测试策略与当前覆盖率

| 类型 | 位置 | 要求 | 状态 |
|---|---|---|---|
| 单元 | tests/unit | 每条规则 ≥1 命中 + ≥1 不命中；DSL 算子全覆盖 | ✅ 84 向量 / 42 规则 |
| 属性 | tests/property | 第 6 节不变量；求值器纯函数与幂等 | ✅ hypothesis |
| 金标准回归 | tests/golden | 古籍明确判吉/判凶课例；失败即阻断 | ✅ GS-2027-0711 |
| 契约 | tests/unit/test_contract.py | 输出必过 JSON Schema | ✅ 含"禁止夹带单一总分字段"断言 |
| 性能 | tests/bench | 4380 候选 < 3.5 s（相对门禁 ×1.5）；暴力对照一致 | ✅ ≈3.2 s |
| 扰动 | tests/unit/test_sensitivity.py | 坐向 ±3°、真太阳时开关翻转可检出 | ✅ |

**覆盖率现状（`make cov` 实测）：**

| 包 | 覆盖率（2026-11-03 fresh） | 包级地板 | 目标 |
|---|---|---|---|
| core-time | 96.2% | 96% | 90% |
| core-symbol | 94.3% | 94% | 90% |
| core-rule | 92.0% | 92% | 90% |
| core-eval | 92.8%（engine 92%、ranker 84.5%、disagreement 87%） | 92% | 90% |
| app-zeri | 68.1%（cli 34.1%、case_runner 44.4%、report 76.8%） | 68% | 80% |
| **整体** | **84%**（1226 个非 slow 测试；`make cov` 新鲜采集） | — | ≥80% |

**文件级地板（包内低于目标的文件必须单列）：**

| 文件 | 覆盖率 | 地板 | 目标 |
|---|---|---|---|
| `app-zeri/cli.py` | 34.1% | 34% | 80% |
| `app-zeri/case_runner.py` | 44.4% | 44% | 80% |
| `app-zeri/report.py` | 76.8% | 76% | 80% |
| `core-rule/severity_cap.py` | 85.2% | 85% | 90% |
| `core-rule/calibers.py` | 87.4% | 87% | 90% |
| `core-eval/ranker.py` | 84.5% | 84% | 90% |
| `core-eval/disagreement.py` | 87.0% | 86% | 90% |
| `core-symbol/jishen.py` | 87.9% | 87% | 90% |

> **门禁口径（2026-11-03 修正）**：`make gate` 必须先经 `make cov` 用
> `pytest --cov` 重新写 `.coverage`，再 `coverage report --fail-under=80`；
> 不得只读上一次遗留的 `.coverage`，不得跟 `|| true`。事故实证：旧数据报
> 75%，fresh 实测 84%——旧数据会让「下降」和「通过」不可区分。
> 测试锚点 `tests/unit/test_gate_wiring.py`。
>
> **两层 ratchet（2026-11-03 评审十/十一回路）**：整体 84% 过线时 `app-zeri`
> 68% 不会阻断；只看包级 68% 时 `cli.py` 34% 也不会阻断（case_runner 涨回去
> 就能把包级拉平）。`tools/coverage_ratchet.py` 因此设两层地板：包级 `min`
> 与文件级 `min`，低于任一层即失败；包内低于 `target` 的文件**没有文件级地板
> 也算失败**。`make cov` 每次打印两张表。
>
> **min / target 语义**：`min` 是地板（只许升不许降），`target` 是目标；
> `min` 可以高于 target（core-time 96 > 90，表示已超过目标但不许掉回来）。
> 覆盖率提升后按 `python tools/coverage_ratchet.py --update` 的建议上调地板
> （不自动写文件，避免覆盖取值理由）；手工下调须在提交信息说明理由。
> 实测 - 地板 > 2pp 会告警「基线过松」，但不阻断。
> 测试锚点 `tests/unit/test_coverage_ratchet.py`。
>
> **版本与收紧条件**：CI 与本地 venv 已统一到 Python 3.14.2（此前 3.12/3.14
> 的分支计数差异迫使留 1pp 余量）。本轮地板取 `floor(实测)`；若未来版本再次
> 分叉，收紧条件为**连续 10 次 CI 与本地差值 < 0.3pp**，否则保留 1pp 余量并在
> CHANGELOG 记「已知宽松」。`app-zeri` 68% 与 `cli.py` 34% 仍是真实风险，
> 缺口见 Q-008，不以降地板掩盖。
>
> **性能冒烟不在 coverage 插桩下计时**：单月 372 候选的 2.0s 断言跑在
> `pytest --cov` 里会被插桩放大（CI 实测 2.07–2.62s），不是 O(n²)。`make cov`
> 末尾用独立无插桩进程补跑一次（`out/junit-perf-smoke.xml`）；本地预算 2.0s、
> CI 3.0s，O(n²) 回归实测 ~9s 仍会被抓住。`cov` 把覆盖率阈值、性能冒烟、ratchet
> 三项都跑完再汇总退出码——前者失败不会让后者静默消失。CI 覆盖率步骤直接
> `make cov PYTHON=python`，避免与本地接线漂移。

**变异测试抽查（`make mutation`）**：**28 处**定点变异，覆盖算子边界（in/gte/between/count_gte/
same_group kind）、三态转换、tier 分支、冲突检测、unknown 分类、定义级白名单、
publishable 必需集、演示标记、节气黄经、置闰、五虎遁/五鼠遁、旬空表、纳音表、
二十四山顺序、分歧度公式、排序方向、建除位次、黄黑道星序。**当前 28/28 全部被抓住**。

> 两轮共发现 **8 个测试缺口**（between 边界、unknown 拉 tier、publishable 必需集短路、
> unknown 分类串味、same_group kind 被忽略、二十四山只抽查首尾、TIER_RANK 顺序、演示标记无断言），
> 均已补测。**变异存活 = 测试没真正验证行为，要补测试而不是改变异点。**

**未达标项如实登记**：`app-zeri/cli.py`（34%）、`case_runner.py`（44%）、
`report.py`（77%）是当前主要缺口；`core-eval/ranker.py`（84.5%）与
`disagreement.py`（87%）的剩余分支主要是异常/空集保护路径。
**不以降低门禁或删除断言的方式"达标"**，缺口见 `docs/QUESTIONS.md` Q-008。

**CI 门禁：** 测试全绿 + 金标准回归通过 + `status` 变更签名检查 + 覆盖率（整体 ≥80%）+
无网络依赖扫描 + 规则引用完整性（每条 `tests` 指向的用例存在）+ 性能预算。

---

## 11. 风险与红线

1. **伪精确**：任何"分数"不得被表述为吉凶概率。报告页脚固定免责声明。
2. **规则污染**：`待考证` 规则一旦进入正式判定即视为缺陷，CI 必须阻断
   （本实现：默认不参与，命中只登记 unknown）。
3. **范围蔓延**：命理、风水、形峦只在 `core-symbol` 预留命名空间，不在本项目实现；
   禁止在择日模块里夹带断语生成。
4. **合规**：不承诺准确率、不做化解收费、健康与事故类问题引导就医与依法维权。
   定位：民俗时间管理与规则复核工具。
5. **巴士系数**：所有规则、决策、争议都写进 docs；换模型也能接手。
6. **版权**：只用公版古籍原文；现代书籍与论坛内容仅内部参考，不入库分发。

---

## 12. 施工顺序与完成状态

| ID | 里程碑 | 关键产出 | 状态 |
|---|---|---|---|
| M0 | 工程地基 | workspace、CI、lint、覆盖率门禁、AGENTS.md | ✅ |
| M1 | 事实层 | core-time 全量（节气/真太阳时/干支/农历/配置项） | ✅ |
| M2 | 符号层 | 干支/纳音/二十四山/分金/神煞注册表 | ✅ |
| M3 | DSL 与生命周期 | 解析器、求值器、状态机、签名 CI、lint | ✅ |
| M4 | 公共否决层规则集 | 44 条 YAML + 88 测试向量（34 待考证 + 10 定义级） | ⚠️ 断言级仍待考证（缺原文，需人类）；定义级已可判定 |
| M5 | 复核器 | 单候选评估 + 三态 + 报告 + manifest | ✅ |
| M6 | 生成器 | 全量评估 + 分层排序 + 无解说明 | ✅（三级剪枝未实现，当前为全量评估） |
| M7 | 多派与路由 | 派别包、school_policy、分歧度 | ✅（4 派声明，3 派仅占位） |
| M8 | 敏感性与鲁棒 | 参数扰动、坐向扰动、翻转清单、稳健集/敏感集 | ✅ |
| M9 | 案例体系 | schema、分级、运行器、四份报告、打乱对照 | ✅（仅 1 条 A 级案例） |
| M10 | 服务化与整合 | FastAPI、PWA、案例库浏览、报告导出 | ❌ 未实现 |

**瓶颈提示：** M4 的考证工时远超编码，Agent 不得代劳；M4 未完成前，
M5/M6 用 `--allow-unverified` 做链路联调，但不得发布结论。

---

## 13. 附录 A：公共否决层候选规则清单（全部 `status: 待考证`）

| 组 | 已落地规则 |
|---|---|
| 年煞 | `PUB-TAISUI-001` 太岁占山、`PUB-SUIPO-001` 岁破占山、`PUB-SANSHA-001/002/003` 三煞占山（年/月）/占向、`PUB-WUHUANG-001` 五黄占山 |
| 月煞 | `PUB-YUEPO-001` 月破占山、`PUB-YUEJIAN-001` 月建占山 |
| 日时 | `PUB-CHONGSHAN-001/002` 日/时冲山、`PUB-CHONGMING-001/002` 日/时冲命、`PUB-SILI-001` 四离、`PUB-SIJUE-001` 四绝、`PUB-YANGGONG-001` 杨公忌（不提供） |
| 结构 | `PUB-ZIXING-001` 自刑、`PUB-CHONG-001` 日时相冲、`PUB-XING-001` 三刑、`PUB-HAI-001` 六害、`PUB-PO-001` 相破、`PUB-REPEAT-001` 地支三见、`PUB-XUNKONG-001` 旬空、`PUB-GANCHONG-001` 天干相冲 |
| 正向 | `PUB-SANHEFU-001` 三合扶山、`PUB-BANHE-001` 半合扶山 |
| 方位 | `PUB-YINFU-001` 阴府（不推断）、`PUB-DUTIAN-001` 都天煞、`PUB-FUBING-001` 伏兵大祸、`PUB-GUANGFU-001` 天地官符、`PUB-DAXIAOYUE-001` 大小月建 |
| 相主 | `PUB-CHONGMING-001/002`、`PUB-MING-SANSHA-001` 年命三煞、`PUB-XIANGSHOU-001` 相主 |
| 事项专属 | `PUB-SANG-001/002` 重丧/三丧、`PUB-JIAQU-001/002` 妨翁姑/妨父母、`PUB-XIUJIU-001` 修旧宅加严 |
| 正五行 | `ZWX-FUSHAN-001`、`ZWX-BULONG-001`、`ZWX-XIANGSHOU-001` |
| 斗首/玄空 | `DS-HUAQI-001`、`XK-GUAQI-001`（均默认 `participates_in_veto: false`） |

> 上表仅为**待考证索引**，不构成任何规则断言。每条落地时必须：定原文引文、定适用事项、
> 定与其他派冲突处理、定 target 与 severity。

## 附录 B：争议项登记表（已配置化 + 报告回显）

`use_true_solar_time`、`day_boundary(早子/晚子)`、`year_boundary(立春/正月初一)`、`闰月归属`、
`历本依据（协纪/象吉/鳌头）`、`五黄三煞推算口径`、`分金取用体系`、`斗首化气是否参与否决`、
`玄空卦气是否参与否决`。

## 附录 C：术语表

日课（年月日时四柱）、坐山/向首、分金、扶山补龙相主、否决层/排序层/参考层、三态、
分歧度、manifest（可复现清单）、金标准回归、`unknown`（输入不足或依据未核）、
`CONFLICT`（派别结论不一致，不裁定谁对）。

---

**给 Agent 的最后一句指令：** 一次只做一个任务，做完自审再停；
遇到任何需要"判断规则对不对"的时刻，立刻停下输出 `QUESTION`，不要猜。


---

## 14. v0.2 增补：口径注册表与稳健性（评审后新增）

### 14.1 口径注册表（`core-rule/config/calibers/`）

择日里"有争议"的东西，本质多是**口径**不同。v0.2 把口径变成命名注册表：

```yaml
# core-rule/config/calibers/sansha.yaml
caliber_set: sansha
default: direction_group
calibers:
  direction_group:
    status: 有争议        # 粗化版不得冒充精确
    description: 只判定到方位组（三山），不区分劫煞/灾煞/岁煞
  named_sansha:
    status: 待考证
    description: 判定到劫煞/灾煞/岁煞
    requires: [《协纪辨方书》义例·三煞条原文, 三山与劫/灾/岁对应表]
```

**规则**：

1. 每次评估必须显式选用口径（或取默认值），报告「口径回显」节强制展示；
2. 口径状态与规则状态**正交**：一条已考证规则若依赖未裁定口径，结论仍不可用；
3. 未裁定口径下相关规则一律 `unknown`，但报告给出**对比式提示**：
   列出每个可选口径、各自状态、各自缺什么（`requires`），而不是一句"未知"。

**已注册口径**：

| 口径组 | 可选值 | 默认 | 影响 |
|---|---|---|---|
| `sansha` | `direction_group`（有争议）、`named_sansha`（待考证） | `direction_group` | 三煞判到方位组还是判到具体煞名 |
| `nayin` | `undecided`（有争议）、`chuanshan`、`fenjin`、`zhengzhen` | `undecided` | 阴府能否判定 |

CLI：`--caliber nayin=chuanshan --caliber sansha=named_sansha`

### 14.2 稳健集 / 敏感集

生成器主输出分两层（`--robustness`）：

- **稳健集**：在 `真太阳时开关 / 日界口径 / 坐向 ±angle_uncertainty_deg` 全部扰动下 `state` 不变；
- **敏感集**：任一扰动下翻转，单独列出并标注触发扰动与翻转前后状态。

`RobustnessReport.radius_deg` 给出"坐向误差在此范围内结论不变"的量化值。

理由：罗盘读数有 ±1~2° 误差，若 Top-K 里一半候选是"角度差一点就作废"的日子，
比不给结论更危险。

### 14.3 无解 / 无结论的 schema 区分

`GenResult.no_solution_reason` 三值：

| 值 | 含义 | 报告首行 |
|---|---|---|
| `all_rejected` | 全部候选被否决层排除 | "本窗口全部候选被否决层排除（真无解）" |
| `no_conclusion_pending_verification` | 有候选未被否决，但依赖未考证规则/未定口径 | "**本次无结论（非无解）**，不得当作「该窗口无可用日」" |
| `constraints_conflict` | 时间窗与每日时段/排除条件无交集 | "约束互斥，请检查输入" |

同时 `Evaluation.publishable` 与 `GenResult.is_publishable` 作为**布尔位**进 JSON，
避免"只写在文本里容易被复制粘贴丢掉"。

### 14.4 四柱的时间基准统一

v0.2 修复：真太阳时开启时，**年/月/日/时四柱统一基于"命理时间"**（`hour_ref`），
不再出现"年柱用民用时、时柱用真太阳时"的内部矛盾。
`tests/golden/test_solar_terms_regression.py::test_true_solar_time_shifts_year_boundary`
用立春 ±10 分钟 × 真太阳时交叉用例守住这一点。


---

## 15. v0.3 增补：定义级 severity 白名单、必需集发布、时间基准两轴

### 15.1 定义级只回答"是什么"（ADR-0009）

v0.2 的定义级只挡住了 `hard_veto` 与 `severity=禁用`，没挡住 `慎用` ——
`DEF-REPEAT-001` 携带 `severity=慎用` 并计入 `strong_avoid`，等于用"已确定"的外衣包装断言。

v0.3 新增 severity **`记录`**，为定义级唯一允许值：

| status | 允许的 severity | 是否影响 tier |
|---|---|---|
| `定义级` | 只能是 `记录` | **否** |
| `待考证`/`已考证`/`有争议` | `禁用`/`慎用`/`可用`/`推荐` | 是 |

加载期三条硬校验 + `rules lint` 兜底。8 条 `DEF-*` 的吉凶部分拆为 `ASSERT-*`（待考证）。

**一句话原则**：定义级只回答"是什么关系、几次、在哪个方位"，不回答"好不好"。

### 15.2 报告措辞三分

| 标签 | 触发 | 是否可作排除依据 |
|---|---|---|
| **确定** | 已考证/定义级规则命中 | 是 |
| **演示命中** | `--allow-unverified` 下待考证规则命中 | **否**（补原文后才行） |
| **未知** | 输入不足/口径未定/规则未考证 | — |

结论行示例：`不可用（确定）` / `演示性不可用 —— 仅由未考证规则命中，不作为排除依据`。

### 15.3 时间基准两轴（ADR-0011）

```
ym_time_ref:   auto | civil | true_solar   # 年/月柱（比交节用哪个时间）
hour_time_ref: auto | civil | true_solar   # 日/时柱（含换日边界）
```

- `auto` 跟随 `use_true_solar_time`（默认 False → 全民用时，惯例口径）；
- 混合口径（年月柱民用时 + 时柱真太阳时）是**可选项**，不是 bug；
- 日柱换日边界**必须**跟随 `hour_ref`（同一量同一基准）；
- `fact_hash` 纳入完整约定，避免"同 fact 不同口径"误判一致。


### 15.4 必需集准入与 publishable 语义边界（ADR-0012）

**准入四条**（`rules lint` 逐条校验，违反报 `required_set_unresolvable`）：

1. `hard_veto: true`
2. `target ∈ {mountain, facing, day, person}`（排除 `hour`：换时辰可规避）
3. 不属于参考层派别（`doushou`/`xuankong`）
4. **可判定闭合**：依赖字段可提供；依赖命主的规则只能进 `person_dependent`

**publishable 语义（安全底线，非完备性）**：

> `publishable = true` 表示"该事项的必需规则集已全部可判定，系统不会漏判这些规则覆盖的风险"。
> 它**不表示**规则集完备、也不表示该日期可用。

**阻塞的两种来源**：

1. 必需规则**未考证** —— 即使求值为 `False`，"不犯"的结论也不可信；
2. 必需规则**输入不足**（求值 `unknown`）。

**结构**：`default.core`（无输入依赖）+ `default.person_dependent`（未提供命主时不进集）
+ `overrides[task_kind]`（`add`/`remove`）。

**验收信号**（合成规则已验证，不依赖真实考证）：
`test_satisfied_required_set_enables_publishable` 把 10 条必需规则全部替换为已考证版本，
断言 `publishable is True`。
