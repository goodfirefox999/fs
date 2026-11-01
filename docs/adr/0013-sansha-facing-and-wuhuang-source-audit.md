# ADR-0013：必需集出处预检——三煞占向移出、太岁坐向同轮降级、五黄截止条件

- 状态：已采纳（决策与代码落地，2026-11-01 同日完成；C9/C10 为登记的后续项）
- 日期：2026-11-01
- 决策者：评审裁定（2026-11-01 第五轮，含两轮预检交叉）
- 触发：
  - P0 考证开始前的出处预判核查：「必需集里若混着一条永远查不到原文的规则，
    补完其余九条也看不到 publishable=true」
  - 预检发现 PUB-SANSHA-003 的建模方向与《协纪辨方书》原文**相反**
    （不是"疑似冲突"，是原文直接给出了相反的坐向规则）
  - 评审补充：太岁（Q-012）的证据链比三煞更强，必须同轮处置——
    「保留一条方向反了的硬否决，比暂时缺少一条硬否决更危险」

## 一、预检发现（引文按置信度分级，沿用"不编造引文"铁律）

**A 级（逐字核到；来源：识典古籍在线本，四库影印对照待复核）**
《协纪辨方书·利用一·制煞要法》引《选择宗镜》：

> 「坐三煞，向太歲，此不能制者也，不可犯也。」
> 「三煞在方在向，及陰府在山，此可制而不易制者也，不可輕也。」
> 「太歲可坐不可向，三煞可向不可坐，不易之論也。」

**B 级（评审检索提供，维基文库四库本；本轮未能直接抓取页面，
逐字复核通过前不得录入任何规则的 quote 字段）**

> 三煞条按语：「按三煞为太岁三合之冲，可向不可坐，故占山则造葬皆忌，占方则可制而修也。」
> 太岁条引《宗镜》：「太岁，君也，坐之吉，向之凶，冲破坐山故也。」
> 太岁条按语：「至可坐不可向，则不易之论。盖向太岁则坐于岁破矣，虽有吉星不能解也。」
> 太岁条：「可坐不可向，在山在方，叠吉星则大吉，叠凶星则大凶」
> 《论修方》：「方之不可修者曰：本年戊己方，岁破方，太岁到方而带戊己、打头火（大煞）、金神也。
>   月家则大月建（土煞）、小儿煞（小月建）也。此皆不可犯者。」
> 《论修方》：「修凶方，除戊己、岁破、太岁之带凶者不修外，其余可制而修也，修凶方发福快。」
> 《论修方兼山向及中宫》：「四围有屋则中间之屋皆名中宫，太岁在向及戊己煞、三煞占山占向，
>   则中宫终年不吉，不可修」

**C 级（二手证据，仅作检索线索，不得录为出处）**：图解本目录（义例含"三元九星"条）；
网络流传"五黄至尊、不论生克一律为祸""五黄会劫煞，可向不可坐"等均属后世/民间口径，
**非**《协纪辨方书》原文。

**对现有规则的影响判读**：

| 规则 | 建模 | 原文判读 | 结论 |
|---|---|---|---|
| PUB-SANSHA-001/002 三煞占山 | 坐三煞山 → 禁用 | 「坐三煞……不可犯」；按语「占山则造葬皆忌」 | ✅ 原文支撑。考证路径：义例三煞条（起例/对应表）+ 制煞要法（忌方向） |
| PUB-SANSHA-003 三煞占向 | 向三煞 → 禁用 | 「三煞在方在向……可制而不易制」；「可向不可坐」；《论修方》不可修清单不含三煞向 | ❌ CONFLICT（双证据），移出必需集 |
| PUB-TAISUI-001 太岁占山 | 坐太岁山 → 禁用 | 「坐之吉，向之凶」；「太岁可坐不可向」 | ❌ CONFLICT（比三煞更直接），同轮降级 |
| PUB-SUIPO-001 岁破占山 | 坐岁破山 → 禁用 | 「向太岁则坐于岁破矣，虽有吉星不能解也」——坐岁破即向太岁 | ✅ 同段引文反向确认，硬否决方向正确 |
| PUB-WUHUANG-001 五黄占山 | 年五黄到山 → 禁用 | 起例条目大概率存在（三元九星）；忌法无 A/B 级直接支撑；《论修方》不可修清单亦不含五黄 | ⚠️ 保留必需集 + 截止条件（D3） |

## 二、版次与卷次差异（验证"记 pian 优先于 juan"）

| 条目 | 篇次（准） | 卷次（双记） |
|---|---|---|
| 制煞要法 | 利用一 | 四库本卷三十四 / 通行转载本卷三十三 |
| 三元九星（五黄起例） | 义例（年神类） | 检索见卷八；图解本目录归义例一（卷三）——归类有差，核查以检索词定位，不依赖卷次 |
| 三煞 / 太岁条及按语 | 义例 | 待复核 |

## 三、决策

**D1｜PUB-SANSHA-003 移出必需集，降慎用、标有争议。**
`hard_veto→false`，`severity 禁用→慎用`（「不可輕」映射），`status 待考证→有争议`，
citation 录 A 级制煞要法引文（`quote_kind=原文`，`pian=利用一·制煞要法`），
notes 记 interpretation：「『可制』表示存在制化通道，本系统暂不建模制化；
『不可轻』映射为慎用，终局处置随制化建模再议」。
规则保留在库、继续评估（演示命中/慎用登记），不删除。

**D2｜PUB-TAISUI-001 同轮处置（最低限度拆除）。**
`hard_veto→false`，`status 待考证→有争议`，`severity 禁用→慎用`（**过渡登记**——
注意：原文「坐之吉」意味着慎用可能仍是方向性误标；终局是"条件性提示（叠吉星则吉）"
还是完全移出评估层，待 Q-012 人类裁定），移出必需集，
notes 登记「太岁占向 → 硬否决规则待建」。
理由：方向被原文否定却仍充当发布门槛 = 主动误判；且这一条硬否决同时压着两个错误——
把「坐之吉」误判为不可用，漏掉「向之凶」的真忌。

**退出条件（评审第五轮补钉）**：本过渡登记在 Q-012 裁定完成（按 H1/H2 假设检验收敛）
或当前考证周期结束（定义见 D3）时，必须替换为终局处置，以先到者为准——
过渡状态不得跨越一个考证周期。

**D3｜PUB-WUHUANG-001 保留必需集，设截止条件。**
核查以「义例·三元九星条是否含占山忌法」为终点。核查位置：
① 义例三元九星起例（入中基准、顺逆飞布）；
② 利用篇五黄论述逐字复核——注意：评审打开卷34页面未逐字见到
「五黃或入中宮則不可犯」句，该句从预检线索降级为待核；
③ 立成卷年家九星表（若有可直接当数据源）。
判据 A（有占山忌条）→ 走已考证升级；判据 B（只有起例 + 可制论述）→ 人类裁定二选一：
保留 hard_veto 并签名「本系统不建模制化，保守选择」，或降慎用移出必需集；
判据 C（义例查无）→ 转核鳌头/象吉原文，仍无则移出。
**不允许"保留 hard_veto 但既不签名也不设处置路径"的状态超过一个考证周期。**

**「一个考证周期」的定义（评审第五轮补钉；计量单位第九轮改述）**：自本 ADR 落档起，
至当前 P0 批次（修造必需集 8 条全部完成出处核查并设处置路径）完成止；
硬上限 **5 个提交区间**（自 tag `baseline-pre-adr0014` = `eac493d` 起计——仓库无 PR 流程，
commit 区间是可客观计数的单位），以先到者为准。
此定义同样约束 D2 的太岁过渡登记与其余必需集规则的悬置上限——
**任何必需集规则都不允许无限期悬置在否决层。**

**默认 fallback（评审第六轮补钉）**：截止时点若五黄仍未按判据 A/B/C 裁定，
默认按「降慎用 + 移出必需集」处置，并在 QUESTIONS 登记「五黄降级待复核」；
人类后续推翻此默认须显式签名。方向理由：未核查完成的规则不充当发布门槛——
降级后 publishable=true 的覆盖边界更窄但更可信。
生效时点：按上方「考证周期」定义自动计时（本 ADR 采纳日起算），到期自动触发，不依赖人工记忆。

**D4｜lint 新增 `required_set_controversial`。**
在 `_check_required_set` 的 `_check_group` 循环内：`rule.status == "有争议"`
且出现在 core / person_dependent / overrides.add → 报错。
与既有准入四条（`required_set_unresolvable`，已实现于 cli.py:285）叠加：
D1/D2 的两条规则即使被误加回，先撞准入条件 1（hard_veto=false），再撞本检查。

**D5｜修造必需集 10 → 8。**
`default.core` 移出 PUB-SANSHA-003、PUB-TAISUI-001；各事项 `overrides.remove`
同步清理死条目；报告「必需集覆盖边界」清单分类更新：
三煞占向、太岁占山归入"已建模但移出（口径与原典冲突/存疑）"，
与"未建模"（大煞、月五黄、阴府、命主 2 条）**分列**——两类对用户的含义不同。

**D6｜`status=有争议` 退出 strict 档升级（评审第五轮裁定，选项 A）。**
`engine.py` 的 strict 档把 severity=慎用 升级为否决——若无处置，D1/D2 的「移出必需集」
只在非 strict 档成立，strict 档下命中仍产出否决，等于用档位设置抵消出处核查结论。
处置：strict 升级条件追加 `rule.status != "有争议"`——
**出处核查未通过的规则，不得在任何档位获得比其当前证据更强的否决力**，
其在 strict 档下保持慎用登记。
注意 `RuleSet.select()` 本就把有争议与待考证同等对待（默认不进判定），
本条实际影响 `--allow-unverified` 的演示路径。

**【superseded by ADR-0014】** 本决策由 ADR-0014 决策 1 的不变式
（"strict 只强化已确定的判断"：升级条件要求 `status == "已考证"`）吸收并取代，
实现以 ADR-0014 为准。

## 四、语义辨析（记录，不裁断，归 Q-012）

1. **「向太岁」两解**：修造**朝向**太岁方（向首指向太岁）vs「太岁**到向**」（太岁飞临向首）。
   两种语义对建模影响不同，Q-012 核查问题 1。
2. **中宫场景口径**：《论修方兼山向及中宫》将「三煞占山占向」并列为中宫不可修条件，
   与制煞要法一般原则（三煞可向）表面冲突。可能解释：中宫特殊、要求更严。
   这验证了口径注册表（`calibers/`）设计的必要性——不同场景不同口径，不得一刀切。
3. **「可制」= 制化通道未建模**：向三煞的可制性（三合局制、禄马贵人）与
   《论修方》「修凶方发福快」的体系，登记为**已知未覆盖能力**，不是已覆盖规则。
4. **engine strict 档与 D6**（评审第五轮裁定）：`engine.py` 的 strict 档会把
   severity=慎用 **升级为否决**——若无处置，D1/D2 的「移出必需集」只在非 strict 档成立，
   用户会看到"publishable=true（normal 档）"与"同一日期 strict 档下 REJECTED"并存的
   语义裂缝。按 D6：`status=有争议` 退出 strict 升级，**两档下均为慎用登记**；
   T5 断言两档行为一致。

## 五、工程事实核查（本轮已用代码验证，评审三问的裁定依据）

1. **manifest 是硬校验**：`cli.py:241-252`，`expected_by_status` 不一致 → problems →
   lint 返回 1。规则 status 变更必然强制 manifest 同步，无静默放过路径。
   D1/D2 落地时同步更新 `rules_manifest.yaml`（C5）。
2. **合成负向用例确实绕过 YAML 加载**：`tests/golden/test_required_and_negative.py:66`
   `_synthetic_rule()` 直接构造 `Rule`，经 `dc_replace` 注入 ruleset，全程不经 loader。
   **修复承诺（与本 PR 同步完成，不得延后）**：新增
   `test_public_sansha003_yaml_loads_as_controversial`，从
   `core-rule/rules/public/PUB-SANSHA-003.yaml` 经标准 `load_rule()` 加载，
   断言 `status == "有争议"`、`hard_veto is False`、`citation.pian` 非空、
   `citation.quote_kind == "原文"`——C1 的 YAML 改动以此测试为验收：
   **合成注入测试只证明引擎行为，证明不了文件改动本身**
   （YAML 字段拼错、`hard_veto: false` 写成字符串、citation 缺 pian，都只有它能抓到）。
   既有失败 `test_verified_with_full_citation_ok` 与此同源
   （loader 第四轮加严后测试未跟上，基线即失败），一并修正。
3. **生成器无规则级剪枝**：`generator.py` 仅有 weekday 排除与 veto 直方图，
   候选排序由 `hard_fail_count`（engine vetoes）驱动。规则退出 veto 通道后
   gen 自动放行，无需改 generator；PR 跑一次 gen 冒烟对比确认（S1）。

## 六、落地清单（✅ 待实施，下一 PR 一次完成）

| # | 项 | 文件 |
|---|---|---|
| C1 ✅ | 003 YAML：hard_veto/severity/status/citation/notes 按 D1 | `core-rule/rules/public/PUB-SANSHA-003.yaml` |
| C2 ✅ | TAISUI YAML：hard_veto/severity/status/notes 按 D2 | `core-rule/rules/public/PUB-TAISUI-001.yaml` |
| C3 ✅ | default.core 移两条 + overrides 清死条目 + 注释覆盖边界更新 | `core-rule/config/required_rules.yaml` |
| C4 ✅ | `required_set_controversial` 检查 + 两条非阻断提示（必需集含待考证规则→提示补原文解锁进度；quote 已填但 verified_by 为空→提示未经人类签名） | `app-zeri/src/app_zeri/cli.py` |
| C5 ✅ | expected_by_status 同步（有争议 +2，待考证 -2） | `core-rule/config/rules_manifest.yaml` |
| C6 ✅ | loader.py:203-222 重复校验块删除（quote_kind/pian 检查各写了两遍）+ 修既有失败 test_verified_with_full_citation_ok | `core-rule/src/core_rule/loader.py` |
| C7 ✅ | D6：strict 升级条件追加 `rule.status != "有争议"`（含注释引 ADR-0013） | `core-eval/src/core_eval/engine.py` |
| C8 ✅ | SUIPO-001 notes 登记同源线索（B 级"坐岁破即向太岁"待逐字复核，**不录 quote**） | `core-rule/rules/public/PUB-SUIPO-001.yaml` |
| T1 ✅ | `test_required_set_rejects_controversial_status`：有争议规则进 core → lint 报错 | tests/golden |
| T2 ✅ | `test_xiuzao_required_set_eight_rules`：修造必需集 8 条且不含 003/TAISUI | tests/golden |
| T3 ✅ | `test_sansha_taisui_not_in_any_required_set`：遍历全部 task_kind 断言两条均不在 | tests/golden |
| T4 ✅ | `test_public_sansha003_yaml_loads_as_controversial`：**走标准加载器**从磁盘加载 003 与 TAISUI-001，断言 status=有争议、hard_veto is False、citation.pian 非空、quote_kind=原文（覆盖合成用例绕过的链路，见第五节 2 修复承诺） | tests/golden |
| T5 ✅ | `test_sansha003_hit_registers_caution_not_veto`：**normal 与 strict 两档下均为慎用登记、均不进 vetoes**（D6 行为） | tests/golden |
| S1 ✅ | gen 冒烟对比：同一 window/修造，改动前后候选数与 veto_reasons 分布（基线快照 out/baseline-gen-2026-03.json） | 手工/脚本 |
| C9 📌后续 | 报告标注 strictness 档位；strict 档否决项注明"因 strict 模式，原慎用项升级为否决"（只影响非有争议规则） | `app-zeri/src/app_zeri/report.py` |
| C10 📌后续 | 规则来源可追溯 lint：ruleset 内 Rule 对象须能追溯到 YAML 路径（fixture 用标记豁免）；需 Rule 增加 source_path 字段 | `core-rule/src/core_rule/models.py` |

## 七、与 ADR-0012 的关系

ADR-0012 的准入四条与可判定闭合不变；本 ADR 是其**出处维度**的补充——
实际生效的准入口径为"四条 + 出处预检"：进必需集的规则，除满足四条外，
其建模方向不得与已核原文冲突（冲突即标有争议，被 D4 拦截）。
修造必需集 P0 终点更新为 **8 条**（若五黄按判据 B/C 处置则 7 条），
其中三煞占山 2 条的考证路径已明确（义例三煞条 + 制煞要法）。
