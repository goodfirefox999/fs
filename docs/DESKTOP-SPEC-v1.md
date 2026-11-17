# 居境罗盘·桌面工作台规格 v1

> 建立日期：2026-11-18
> 定位：补齐「桌面转主线」后的施工依据空缺。
> 原《传统人居环境小程序-开发文档 v1.0》仍是**小程序线**的唯一施工依据；本文只约束桌面 Electron 线。
> 两线共用 `src/core` 纯 TS 引擎，但产品形态、发布链路、数据目录完全不同，不能逐条对表。

---

## 1. 产品定位与硬边界

桌面版是**离线优先的个人工作台**，不是对外服务：

- 五层架构沿用总纲：输入预处理 → 历法天文 → 共享前置层 → 五派规则包 → 仲裁与报告；
- 只输出「传统规则条件下的筛选结果」，不称准确率、不说必发必凶；
- 不实现审核开关、不在运行时调用生成式 AI（禁词扫描 `npm run scan` 硬阻断）；
- GIS/3D 若未来接入，只做客观形峦指标与可视化，不自动点穴、不断吉凶；
- 分金吉凶口径未经三源核验，**UI 与报告一律不显示**（附录 E 红线，已有 `tests/fenjin-compliance.test.ts` + 扫描守卫）。

## 2. 已实现模块（2026-11-18 实测）

| 模块 | 位置 | 状态 |
|---|---|---|
| 择日五派 + 大煞前置 + 仲裁 | `src/core/zeri/`、`src/core/engines/zeri.ts` | 完整，双 typecheck 通过 |
| 排盘四派（八宅/玄空/飞星/仙命） | `src/core/paipan/` | 四卡齐全，缺数据标 PARTIAL |
| 罗盘 | `desktop/src/components/CompassSvg.vue`、`views/CompassView.vue` | SVG 矢量；手动输入 + 真北/磁北换算；无传感器（平台限制） |
| 档案库 | `desktop/src/archive/` | schema v2、纯 TS SHA-256、链式迁移、attributeDiff 五类归因 |
| 自动保存 | `store.autosave` + `App.vue` watch | 2s 防抖；**不写 lastEvaluation**（保住 diff 基准） |
| 报告 | `desktop/src/report/` | 单日 + 窗口报告；含档案归因章节；打印分页优化 |
| IPC | `desktop/main.cjs` | 5 个 handler：load/save/export/import/report:export；路径穿越防护 |
| 落盘 | `archive:save` | tmp + rename 原子写 + `.bak` 兜底；体积上限校验 |

**质量基线**：`npm test` 282 passed / `test:perf` 1 passed / `typecheck` + `desktop:typecheck` 通过 / `scan` 0 违规 / `desktop:build` 三块共 502KB。

## 3. 数据目录与迁移

- 档案文件位置由 `desktop/paths.cjs` 的 `storeFile()` 决定，跨平台一致；
- 读取失败时：主进程先把损坏文件改名留档（`quarantineStore`），再返回空档案 + warning；
  备份也失败则进入 `readOnly`，**绝不回写覆盖唯一副本**；
- schema 迁移走 `migrateWorkbenchArchives()`，失败项进 `failures` 并在档案页上屏；
- 导出/导入为 JSON 文件，导入时重新算 `inputHash`，不一致的旧快照丢弃。

**自动保存纪律**（2026-11-18 新增）：

1. 只更新输入与 `inputHash`，`lastEvaluation` 保持原值；
2. 无当前档案时不自动创建；`readOnly` 时不写；
3. 卸载前把最后一次防抖中的改动落盘；
4. 载入档案时抑制一次 watch，避免把刚载入的基准当改动。

## 4. 发布链（待走通）

当前 `desktop/electron-builder.yml` 为 `identity: null`（仅自用、不分发）。对外分发前必须：

1. 申请 Apple Developer ID（$99/年）；
2. 配置 `identity: "Developer ID Application: ..."` 与 hardened runtime；
3. 公证（notarize）后 Gatekeeper 才不会拦截 dmg；
4. 发布门禁：`npm test && npm run test:perf && npm run typecheck && npm run desktop:typecheck && npm run scan && npm run desktop:build` 全绿；
5. 异机验收：另一台 Mac 安装后跑通「输入 → 择日 → 排盘 → 罗盘 → 保存 → 导出报告」；
6. 打 `v1.0.0` tag + CHANGELOG + 发布说明。

`npm run desktop:dist` 脚本已存在，但打包前置的签名/公证配置尚未完成。

## 5. 自动更新与平台边界

- **自动更新**：当前未实现。桌面是离线个人工具，建议 v1 不做；需要时再评估 electron-updater 与更新源托管，不提前引入。
- **Windows**：未规划。v1 只 macOS。
- **小程序线**：已按用户 11-02 决定暂停。恢复前需重核个人主体虚拟支付政策、备案时长，并跑云函数沙箱全链路；下单防重已修（`createVirtualOrder` 30 分钟窗口复用 PENDING 订单）。

## 6. 双引擎关系

Python `zeri/` 是规则考证权威源与案例库宿主；本仓 `src/core` 是产品引擎。不合并，但：

- 规则口径变更必须两仓同轮提交 + 双 CHANGELOG；
- 确定性底座对拍已落地（`tests/parity-mountain.test.ts` 读 Python 生成的 3600 点基准）；
- 12 个山界点归属分歧已登记为 `zeri/docs/QUESTIONS.md Q-031`，裁定前不得擅自改任一端；
- 规则判定层对拍需等 Python 侧 `citation.verified_by` 非空，当前大煞层 0 条可对拍（见 `zeri/docs/ts-parity.md`）。

## 7. 未做（诚实登记）

- 罗盘地图取角（涉及测绘合规，暂不做）；
- 报告目录书签（已有 `@page` 页码 + 屏幕打印提示）；
- 排盘结果入档案（刻意不做：它是即时计算，不是历史快照）；
- 生成式 AI 解释层（AIGC 备案前不上线）。
