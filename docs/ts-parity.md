# 双引擎术语与口径映射（ts-parity）

> 建立日期：2026-11-18
> 目的：为「Python zeri（规则考证权威源）」与「TypeScript `src/core`（产品引擎，桌面主线）」建立可审计的对照口径。
> 定位：**zeri 是规则考证与复核的权威源 + 案例库宿主；fengshui-mp/src/core 是产品引擎。**
> 不合并两仓（语言、部署、演进节奏不同），但任何规则口径变更必须同轮提交并双向登记。

---

## 1. 为什么需要这份文档

两引擎是「同一业务的两种严谨度实现」：

- Python 侧：出处登记表、影印逐字引文、裁决单、负向检索、`verification_status` 硬门槛，工程质量更严格；
- TS 侧：产品化完整（UI/报告/档案/合规扫描），直接面向用户。

已出现过必须双端同步的先例：斗首五行是 Python `core_symbol/doushou.py` 与 TS `packs/doushou.ts` 同轮实现同轮对拍的。若没有映射表，对拍无法自动化，口径漂移只能靠人肉发现。

---

## 2. 规则 id 映射（当前状态）

### 2.1 大煞前置层

| 语义 | TS `src/core/zeri/dasha.ts` | Python `core-rule/rules/public/` | 可直接对拍？ |
|---|---|---|---|
| 年三煞占山 | `D3_YEAR_SAN_SHA_ON_MOUNTAIN` | `PUB-SANSHA-001` | ⚠️ 否：Python 为「待考证」，命中登记 unknown；TS 为硬排除 |
| 月三煞占山 | `D3_MONTH_SAN_SHA_ON_MOUNTAIN` | `PUB-SANSHA-002` | ⚠️ 同上 |
| 日三煞占山 | `D3_DAY_SAN_SHA_ON_MOUNTAIN` | `PUB-MING-SANSHA-001` | ⚠️ 同上 |
| 时三煞占山 | `D3_HOUR_SAN_SHA_ON_MOUNTAIN` | （待建） | ❌ 无对应 |
| 日课犯年三煞 | `D3_DAY_ON_YEAR_SAN_SHA` | `PUB-SANXING-001`（donggong） | ❌ 语义不同 |
| 岁破 | `D3_SUI_PO` | `PUB-SUIPO-001` | ⚠️ 状态不同 |
| 月破 | `D3_YUE_PO` | `PUB-YUEPO-001` | ⚠️ 状态不同 |
| 冲山 | `D3_CHONG_SHAN` | `PUB-CHONGSHAN-001` | ⚠️ 状态不同 |
| 冲主命 | `D3_CHONG_ZHU_MING` | `PUB-CHONGMING-001` | ⚠️ 状态不同 |
| 金神七煞 | `D3_JIN_SHEN_QI_SHA` | （三版本存疑，未编码） | ❌ 无对应 |
| 四离四绝 | `D3_SI_LI_SI_JUE` | `PUB-SILI-001` / `PUB-SIJUE-001` | ⚠️ Q-027 待裁定 |

**关键结论**：当前**没有一条大煞规则可以对拍**。根因是 Python 侧 74 条「待考证」规则按 ADR-0005 默认不产生可用结论，而 TS 侧产品必须给出有效判定。这是设计差异，不是缺陷——对拍只能在「双方均已考证」的规则上进行。

### 2.2 派别规则包

| 派别 | TS | Python `school` | 可对拍？ |
|---|---|---|---|
| 正五行 | `packs/common.ts` + `packs/zhengwuxing` | `zhengwuxing`（5 条） | ⚠️ 部分 |
| 三合 | `packs/sanhe.ts` | `sanhe`（4 条） | ⚠️ 部分 |
| 董公 | `packs/donggong.ts` | `donggong`（5 条） | ⚠️ 部分 |
| 玄空大卦 | `packs/xuankongDagua.ts` | `xuankong_dagua`（4 条） | ⚠️ 部分 |
| 天星 | `packs/tianxing.ts` | `tianxing`（4 条） | ⚠️ 部分 |
| 斗首（参考层） | `packs/doushou.ts` | `doushou`（6 条，`layer: reference`） | ✅ 已双端同步 |

### 2.3 术语映射

| 概念 | TS | Python |
|---|---|---|
| 大煞强度档 | `DashaStance`（四档，见 `dasha.ts` 注册表） | `verdict_type` + `layer`（gate / reference / unspecified） |
| 正煞/傍煞 | `sanShaGradeOf` 返回 `'正煞' \| '傍煞'`（半开区间 `[中线-7.5, 中线+7.5)`） | `severity: 禁用` + `target: mountain` |
| 不确定 | `NEEDS_REVIEW` | `tier=NEEDS_REVIEW` / `unknown` 三分类 |
| 发布资格 | 无对应（产品侧不设 publishable） | `publishable` 布尔位（必需集全考证才可 true） |

**注意**：TS 的「正煞/傍煞」是空间几何档位，Python 的 `verdict_type` 是规则结论类型，两者**不是同一维度**，不得直接互转。

---

## 3. 可对拍的内容（当前可行）

虽然规则判定暂时无法对拍，但以下**确定性底座**可以对拍，且更有价值：

| 对象 | TS 位置 | Python 位置 | 对拍方式 |
|---|---|---|---|
| 二十四山归一 | `core/constants/shan24.ts` | `core-symbol/shan24` | 0~359.9 每 0.1° 对 `resolveMountain` / `degree_to_shan` |
| 节气时刻 | `core/astro/solar.ts` | `core-time/jieqi.py` | 2000-2100 每年 24 气，误差 <1s |
| 四柱干支 | `core/zeri/facts.ts` | `core-eval` | 金标准 `GS-2027-0711` + 12 个边界日 |
| 真太阳时 | `core/astro/solar.ts` | `core-time/`（均时差） | Meeus 截断 vs Skyfield 对拍基准 |
| 玄空盘 | `engines/xuankong.ts` | `core-symbol/` | 216 局 oracle（替卦 216 局待补） |
| 八宅盘 | `engines/bazhai.ts` | （Python 侧无对应） | 仅 TS 单侧 |

---

## 4. 同步纪律（必须执行）

1. **规则口径变更**（新增 / 改判 / 撤销）必须在两仓同轮提交，并在两仓 CHANGELOG 各记一条；
2. **新规则先落后建**：Python 侧先有 `rule_id` + 出处，TS 侧再登记映射；禁止 TS 侧先上线未考证规则；
3. **对拍前置**：只有当某规则在 Python 侧 `citation.verified_by` 非空时，才允许纳入 `parity` 对拍集；
4. **禁止自动升级考证状态**：任何代码不得把 `待考证` 改为 `已考证`，只能由人类在裁决单签署；
5. **id 映射变更必须更新本文件**，并在 PR 描述中列出受影响的对拍用例。

---

## 5. 当前缺口（诚实登记）

- 大煞层 0 条可对拍（见 §2.1）；
- `D3_*` 与 `PUB-*` 的完整映射尚未逐条建立，§2.1 只覆盖 11 条；
- Python 侧无 `ts-parity` CI job；
- 432 局替卦在 TS 侧未全量固化（oracle 仅 216 局下卦）。

本文件是映射基线，不是完成证明。后续每补一条映射，在此登记并附对拍证据。
