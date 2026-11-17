# 居境罗盘（zhuju-luopan）

传统人居环境与方位信息的记录工具，支持阳宅环境建档与先人纪念地环境建档。uni-app 3 + Vue 3 + TypeScript，输出微信小程序与 H5。

本仓库只做「测量记录 + 传统规则整理 + 日程参考」，不提供医疗、投资、法律或施工安全结论。阴宅部分统一以「先人纪念地环境建档」表述，不做按审核状态切换功能的处理。

## 快速开始

```bash
npm install
npm run dev:h5       # 浏览器预览（含本地内容接口）
npm run dev:mp-weixin
npm test             # 全量单元测试（含 cnlunar / 独立实现交叉校验）
npm run test:perf    # 性能测试（独占进程，不与其它测试并发，否则会因邻居负载假失败）
npm run typecheck    # 核心引擎类型检查
npm run scan         # 合规词扫描
npm run build:h5
npm run build:mp-weixin
```

小程序构建产物在 `dist/build/mp-weixin`。用微信开发者工具导入**仓库根目录**，根目录 `project.config.json` 已设置 `miniprogramRoot` 指向构建产物、`cloudfunctionRoot` 指向 `cloudfunctions/`。

## 目录

```
src/core/          排盘、八宅、仙命、分金、择日与《协纪辨方书》神煞引擎与常量
src/core/zeri/     多流派择日引擎：历法事实层、大煞前置层、五派规则包、仲裁层
src/core/astro/    太阳视黄经与均时差（Meeus 截断式，精度已逐日校验）
src/components/    罗盘、九宫盘等展示组件
src/pages/         首页、建档、报告、罗盘、择日、分享图、档案、我的、说明
src/stores/        Pinia：档案、草稿、应用设置与权益缓存
src/services/      云开发调用、支付、本地存储
cloudfunctions/    云函数（登录、下单、支付回调、权益、内容、反馈、埋点）
scripts/           内容包生成、合规扫描
tests/             金标准与规则测试
```

## 桌面版（Electron，当前主攻方向）

择日工作台已迁到桌面端，直接复用 `src/core` 的确定性引擎与五派规则包，不经 uni-app 运行时：

```bash
npm run desktop:dev     # 起渲染进程 + Electron（开发）
npm run desktop:web     # 只起渲染进程，用浏览器看界面（localhost:5199）
npm run desktop:build   # 产出 dist-desktop/
npm run desktop:dist    # electron-builder 打 macOS dmg + zip（未签名，本机可装）
```

- 目录：`desktop/main.cjs`（主进程、档案 JSON 读写走 IPC + userData）、`desktop/preload.cjs`（contextBridge，`sandbox: true`、`nodeIntegration: false`）、`desktop/src/`（Vue 3 三栏工作台）。
- 模块：**择日**（五派并列 + 大煞前置 + 排除统计）、**排盘**（八宅 / 玄空飞星 / 流年紫白 / 仙命，四派并列）、
  **罗盘**（真北/磁北换算、二十四山与分金读数、采用为坐向）、**档案**（本地持久化 + 导入导出 + 结论快照对比）。
- 罗盘（`desktop/src/components/CompassSvg.vue` + `views/CompassView.vue`）：用 SVG 重写，不复用
  `src/components/CompassDial.vue`（后者依赖 `uni.createCanvasContext`，桌面端不可用且要等 80ms 重绘）。
  **磁偏角只在罗盘页参与换算，不写进工作台状态**——`state.sittingDeg` 永远存真北度数，
  择日/排盘/档案只有一个口径，不必为「磁北还是真北」再加一个会进 `inputHash` 的字段。
- 报告导出（`desktop/src/report/`）：两种**自包含 HTML**（内联样式、无外部资源），可用浏览器「打印为 PDF」归档。
  - `html.ts` **单日复核**：输入 / 结论 / 前置层三区 / 五派并列 / 边界说明。
  - `window.ts` **窗口报告**：概览（扫描·排除·宜忌不符·候选）/ 候选清单 / 排除统计（含「三吉星仍被排除」证据）/
    筛选说明与本次口径 / 内嵌排盘四派。
  - 选 HTML 而非直接生成 PDF，是为了不引入字体嵌入与分页引擎；用户可控文本一律 HTML 转义，测试有注入用例。
  - 两份报告共用 `shared.ts` 的版式与转义，避免同一份材料出现两种字号。
  - 打印友好：A4 版心、`break-inside/after: avoid` 防表格行与标题跨页；
    页码用 CSS Paged Media 的 `@bottom-center`（WeasyPrint / Prince 等自动带「第 n 页 / 共 m 页」，
    Chrome 的打印对话框不实现 margin box，需勾选「页眉和页脚」——报告页首有提示，打印时自动隐藏）。
- IPC 输入面只有五个 handler：`archive:load` 无入参，`archive:save` 收数组并写死 userData 路径，`archive:export` 只接受文件名（`desktop/paths.cjs` 的 `safeExportName` 剥掉任何目录成分），`archive:import` 无入参、路径只来自系统打开对话框，`report:export` 只接受 HTML 正文与文件名。落盘目录一律来自系统对话框。`tests/desktop-paths.test.ts` 用穿越路径与静态扫描守住这条边界。
- 排盘（`src/core/paipan/`）：`engines/{bazhai,xuankong,feixing,xianming}` 各返回自有结构，
  由 adapter 翻成统一的 `PaipanSchoolResult`（复用择日 `SchoolResult` 的字段语义）。
  **四派回答的不是同一个问题**——八宅问命宅配合、玄空问元运山向、紫白只出流年方位、仙命问亡命与分金，
  所以**不做跨派冲突判定**，`conflictFlags` 只承载同一派内部的矛盾（如多成员分属东西四宅）。
  把不同问题的答案判成「冲突」是伪造分歧。
- 排盘的出处纪律与择日一致：每条子规则带 `source`，且必须写 `lineageNote` 说明该派主张与历法事实的边界；
  八宅/玄空/紫白的通行本卷次本项目未逐条核对，出处里直接写「未逐条核对原书卷次」，不编卷号。
  缺数据时仍出卡片、标 `PARTIAL` 并写 `partialReason`——少一张卡片会被读成「这一派没意见」。
- 档案（`desktop/src/archive/`）：`schemaVersion` 校验、`inputHash`（复用 `@core/archive` 的规范化 JSON + 纯 TS SHA-256）、
  单条损坏不拖垮其余、**有迁移失败项时不回写**（避免用可读子集覆盖用户原始档案）。
  浏览器预览（`desktop:web`）没有 `window.desktop`，退回 localStorage，方便只改界面时不必起 Electron。
- **结论快照与 diff 归因**：保存档案时把「结论标签 + 排除天数/总天数 + inputHash + rulePackVersion」
  一并写入 `lastEvaluation`。之后同一档案再扫描，择日页顶部显示归因：
  输入已改（未保存）/ 规则包已更新 / 两者都变 / 结论不稳定（输入与规则都没变却结论不同，提示人工复核）。
  快照的 `inputHash` 与本次保存的输入不一致时**丢弃快照**，避免把旧结果贴到新输入上。
- `npm run desktop:typecheck`：`vue-tsc` 查模板类型。**这条必须跑**——`vite build` 不执行模板，
  模板里引用未定义变量能一路通过构建，打开应用才白屏（曾有一个 `degMountain is not defined` 就是这么漏出去的）。
  `tests/desktop-smoke.test.ts` 用 jsdom 挂载整个工作台，跑「渲染 → 切模块 → 保存档案」。
- 控件改动经 200ms 防抖后整窗重扫（180 天实测独跑 478ms，逐字符重扫会钉死渲染线程）；单次扫描超过 1s 时改走 Web Worker，而不是继续加大防抖。
- 档案持久化在 `~/Library/Application Support/居境罗盘/archives.json`，写入采用「临时文件 + 改名」，避免中途崩溃把本机档案写坏。
- 首次装 Electron 需国内镜像：`ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/ npm i`。
- 当前只支持 macOS arm64 本地构建；对外分发需自行处理开发者证书与公证。

## 小程序接入

1. 在 `src/manifest.json` 的 `mp-weixin.appid` 填入小程序 AppID；同时把根目录 `project.config.json` 的 `appid` 改为同一个值（`touristappid` 仅用于界面预览，云开发需要真实 AppID）。
2. 开通微信云开发，创建环境，把环境 ID 写入 `.env`：
   ```bash
   VITE_CLOUD_ENV=your-cloud-env-id
   ```
   未配置时 SDK 使用默认环境。
3. 在云开发控制台创建集合（权限均设为「所有用户不可读写」，只允许云函数访问）：

   | 集合 | 用途 |
   | --- | --- |
   | `orders` | 虚拟支付订单 |
   | `entitlements` | 单份报告权益（`openid + archiveId`） |
   | `users` | 登录用户记录 |
   | `feedback` | 意见反馈 |
   | `events` | 轻量埋点 |

   建议为 `orders.outTradeNo`、`entitlements.openid + archiveId` 建索引。
4. 在开发者工具中右键各云函数目录，选择「上传并部署：云端安装依赖」。云函数：

   | 云函数 | 说明 |
   | --- | --- |
   | `login` | 写入/更新用户记录，返回 openid |
   | `createVirtualOrder` | `code2Session` 校验身份、落单、生成支付签名 |
   | `virtualPayNotify` | 发货回调，幂等写入权益（HTTP 触发） |
   | `getEntitlement` | 查询某档案是否已解锁 |
   | `getReportContent` | 校验权益后返回完整内容包 |
   | `feedback` | 存储用户反馈 |
   | `track` | 存储白名单埋点 |

5. `virtualPayNotify` 需要「HTTP 访问服务」路径，把公网地址配置为微信虚拟支付后台的发货推送地址；地址带上随机 token 查询参数，并在云函数环境变量设置同名 `XPAY_NOTIFY_TOKEN`。

### 支付环境变量（仅云端）

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `WX_APPID` | 是 | 小程序 AppID |
| `WX_SECRET` | 是 | 小程序 AppSecret（不要写入前端） |
| `XPAY_OFFER_ID` | 是 | 虚拟支付 offerId |
| `XPAY_APP_KEY` | 是 | 虚拟支付 AppKey |
| `XPAY_ENV` | 否 | `0` 正式、`1` 沙箱，默认 `0` |
| `XPAY_PLATFORM` | 否 | 默认 `android` |
| `XPAY_SIGN_URI` | 否 | 支付签名 uri，默认 `requestVirtualPayment` |
| `XPAY_NOTIFY_TOKEN` | 是 | 回调地址共享 token；未配置时云函数 fail-closed（拒绝所有回调） |

**上线前必须核对：**

- `paySig` 的签名 uri 与微信官方最新文档一致（本仓库默认 `requestVirtualPayment`，可用 `XPAY_SIGN_URI` 覆盖）。
- 虚拟支付后台的商品 `productId`、价格与 `createVirtualOrder` 中的 `PRODUCTS` 一致；当前商品为 `report_single_990`（990 分）。
- 小程序类目与虚拟支付资质已通过审核；iOS 端虚拟支付能力以微信当期规则为准。
- 回调返回 `{"ErrCode":0,"ErrMsg":"success"}`；重复回调按幂等处理。
- 回调必须带正确 token，且 `MsgType`/`Event`/`Env` 与微信官方报文一致；`xpay_refund_notify` 会把订单置为 `REFUNDED` 并收回对应权益。
- AppSecret、AppKey 只存在于云函数环境变量，前端不得出现。

## 内容包

完整 81 组双星正文只存在于云端函数目录：

```bash
npm run content   # 重新生成 cloudfunctions/getReportContent/content/shuangxing.json
```

客户端只内置预览生成器；H5 开发环境通过 Vite 中间件 `/api/content` 读取同一份文件，生产小程序必须通过 `getReportContent` 且已解锁该档案。

## 数据与隐私

- 档案、设置、权益缓存保存在本机；档案不上传云端。
- 云端仅保存 openid、订单、权益、反馈与埋点。
- 删除本机档案后无法在应用内自动恢复，购买记录仍保留在云端但不会自动重建档案，请在删除前自行备份。
- 定位仅在用户主动点击「按当前位置推荐城市」时请求一次，用于匹配参考磁偏角。

## 本地档案库（schema / 迁移 / 对比归因）

数据层在 `src/core/archive/`，三端（小程序 / H5 / Electron）共用，不碰 UI 与 IPC。

**当前 `ARCHIVE_SCHEMA_VERSION = 2`。**

| 版本 | 变更 | 迁移 |
| --- | --- | --- |
| v1 | 裸档案，有 `schemaVersion: 1`，无输入哈希、无规则包版本 | — |
| v2 | 新增 `inputHash` 与 `rulePackVersion`，使跨版本对比可归因 | `1 → 2` 补算两项 |

- **`inputHash` 算法固定为** `sha256(canonicalize({ mode, eventYear, reading, yang, yin }))`，
  写死在 `core/archive/schema.ts`。换算法等于换哈希语义，必须同时升 `ARCHIVE_SCHEMA_VERSION`
  并在迁移里重算，否则跨版本 diff 会把「算法变了」误报成「输入变了」。
- 刻意排除 `id` / `title` / `createdAt` / `updatedAt`：改备注不该让哈希变。
- SHA-256 是**纯 TypeScript 实现**（`core/archive/sha256.ts`），不用 `node:crypto`（小程序没有）
  也不用 `crypto.subtle`（小程序与旧 WebView 不可用，且是异步 API）。三端必须算出同一个值，
  由 `tests/archive-migrate.test.ts` 与 `node:crypto` 逐条对拍（含中文与代理对）。
- **`undefined` 边界**：对象里值为 `undefined` 的键在规范化时剔除，等同于「字段缺失」。
  `JSON.stringify` 会把 `{ schemaVersion: undefined }` 变成 `{}`，因此迁移**只读值、不读键**——
  不得用 `'schemaVersion' in obj` 判断版本，否则内存态与落盘后读回态会得出两个结论。
- 迁移链只向前：版本高于当前程序直接抛错，不尝试降级读取（旧程序会把新字段当成「没有」）。
  每步必须推进版本，否则抛错而非死循环。
- 批量迁移时单条失败不拖垮其余，`migrateArchives()` 返回 `failed` 明细；
  `archiveStore.hydrate()` 在有失败项时**不回写**，避免用可读子集覆盖用户原始档案。
- 固定样本：`tests/fixtures/archive-v1.json`（历史）与 `archive-v2.json`（迁移后），
  测试断言迁移结果与样本逐字段相等。
- 对比归因 `attributeDiff()` 分五类：`none` / `input_only` / `rules_only` / `both` / `unstable`。
  输入与规则包都未变却结论不同时返回 `unstable` 并提示人工复核，**不谎称「无变化」**。

## 已实现与未实现

已实现：三元九运排盘、兼向出卦与替卦起星（同宫同阴阳不替、阴阳互兼用替、出卦必替）、五黄入中策略、旺山旺向/上山下水等格局、八宅命卦与八分区、120 分金、仙命纳音比对、择日硬条件筛选、《钦定协纪辨方书》宜忌等第与神煞起例、吉神宜趋／凶煞宜忌／二十八宿／值神／吉时／吉神方位、年度/月度紫白、罗盘采样与手动输入、九宫/分析/八宅/仙命/择日报告、分享图、本地档案、按份解锁。

月支与太岁按「交节当日、立春当日」切换，与传统通书一致（lunar-javascript 的 Exact 系列按交节时刻切换，日级择日会差一天）。

未实现/需人工复核：丧坑、丧窟、刺穴、地虎食骨等流派差异大的分金细则；天星派的太阴、五星与四余；日课干支到六十四卦的流派映射；小程序码分享；云端档案同步；真实支付联调（需 AppID、资质与真机）；规格中的 AI 解释层（需生成式 AI 备案与内容审核方案后再上线）。

## 多流派择日引擎（`src/core/zeri/`）

分层与规格一致，任何两派之间不做静默合并：

| 层 | 文件 | 职责 |
| --- | --- | --- |
| Layer 1–2 | `facts.ts` | 四柱（含五鼠遁时柱）、节气月、建除、值神、二十八宿、彭祖、吉神方位、真太阳时；只出事实不出结论 |
| Layer 3 | `dasha.ts` | 全流派共享的大煞排除，命中即不进入评分 |
| 规则包 | `packs/*.ts` | 正五行、三合、董公、玄空大卦、天星，各自输出 `verdict/score_delta/reasons/source_ref` |
| 数据 | `tables/*.ts`、`constants/xieji.ts` | 干支神煞起例、禄马贵人、洪范/正五行、九星轮值、六十四卦圆图、开禧宿度 |
| Layer 5 | `arbitrate.ts` | 按用事类型的透明加权、`consensus_favorable` 与 `conflict_flag`，保留五派原始输出 |
| 出处 | `sources.ts` | 规则 id → 古籍/现代来源登记表 |

- 用事入口覆盖入宅安床、动土修造、嫁娶订盟、开市交易、安葬破土、修坟立碑六类；原四类之外新增的嫁娶、开市在权重表中显式声明为「产品端扩展，需人工复核」，不冒充原规格排序。
- 一次计算完整遍历所选时间窗后再截取展示条数，`scanned / rejected / unmatched / eligible / truncated` 分开返回；界面不得把「展示 N 天」写成「只扫描 N 天」。排除项按规则与日期的去重组合计数，同一日命中多项时分别列出并注明。
- 三煞占山附带严重度标注 `shaGrade`：煞区跨三支共五山，正煞＝中间一支及其两侧的天干山（北方壬·子·癸、南方丙·午·丁），傍煞＝两端的地支山（亥丑、巳未）——「三山」指二十四山分组，不是玄空飞星的三元龙，勿混。区间归属与 `resolveMountain` 同一条半开规则（每山 [中线-7.5, 中线+7.5)），边界度数已在用例里逐个钉住；兼向只改变落在哪一山，不额外升降档。线度与所选山名不符时（手输兼度）说明里按线度落山说。分类与立场同样进数据结构：`DashaHit.family`（占山／相犯／通用）、`DashaHit.stance`（官书从删·原书未载·两说并存·官书明文但本包可降），`DASHA_FAMILY` 未登记的 id 由 `familyOf()` 直接抛错，与 `sourceOf()` 同标准，避免新规则忘了归类却静默落进通用类。受死的删驳原文按卷六「要安以下九神」按语逐字登记在 `sources.ts`（含 Wikisource 链接）；杨公忌「官书未列明文」这一判断本身标为待人工核对，不假装核到卷次。
- 大煞默认策略：不可放宽项只收历法事实与官书明文两类——岁破、月破、日破、时破、冲坐山、冲主命与仙命、四离四绝、等第「诸事皆忌」，加上兴工口径下的年家三煞占山。三煞拆成两组分开计数：`SAN_SHA_MOUNTAIN`（年/月/日/时占坐山，看山家方位）与 `SAN_SHA_COURSE`（日支犯年煞、时支犯日煞，属日课四柱自身相犯，不构成对坐山的排除），`DashaHit.family` 落进数据结构、界面分区展示；默认在兴工口径（阴宅用事、动土修造、入宅勾选伴随动工）硬排年家与月家占山，日家、时家占山与相犯两条列为提示，可选层级为「仅年家 / 年家＋月家 / 整层」。纯入宅不兴工，占山四条不参与判定。四条占山的煞方一律由「该柱自身地支的三合局」起（年家用年支、月家用月支、日家用日支、时家用时支，即申子辰年/月/日/时皆煞南、寅午戌皆煞北），这是通书与择日资料的通行起法；「以日支起煞、看时支是否落煞」是另一条规则（时支犯日煞，归 `SAN_SHA_COURSE`），两条不得合并，也不得把时家占山改成按日支起煞——那样会与日家占山同解。`tests/san-sha.test.ts` 用「日家不占山、时家占山」的对照数据钉住这条起法。金神七煞（限修造与入宅）与四废、往亡、十恶大败、大败、杨公忌、重丧按各自开关处理，降级后仍原样列出；受死按《协纪辨方书》卷六「龙虎、罪至、受死三辰并仍旧历从删」恒列为提示，任何开关都不会把它升成排除。杨公忌按通书口径默认硬排（官书未列明文，属显式声明的偏离），关掉「民俗神煞硬排除」即降为提示；降为提示的民俗条目在界面上进「民俗口径提示」区，与流派口径分歧分开，「大煞前置排除」区里只剩真硬排除。
- 玄空大卦的元运按阳爻 9 年 / 阴爻 6 年（一运 1864–1881……九运 2017–2043），不使用每运 20 年的简化；爻位顺逆为流派分歧，通过 `yaoOrder` 显式声明，默认 `ASC`。
- 天星包固定 `PARTIAL`：太阳视黄经实测与 Swiss Ephemeris 最大偏差 0.014°，未达自设 0.01° 门槛，故公布误差界、宿界 0.03° 内要求复核，太阴与五星四余不下结论。
- 所有规则 `verification_status` 恒为 `unverified`（类型层面禁止代码写入 `verified_by_human`），`tests/schools.test.ts` 有守卫用例。
- **验证强度分层**（详见 [`docs/ZERI-AUDIT-2026-11-02.md`](docs/ZERI-AUDIT-2026-11-02.md)）：
  大煞层与 cnlunar 逐日对拍 5844 天，八宅/飞星/玄空盘与独立 MIT 实现逐宫对拍，天星太阳与 Swiss Ephemeris 对拍（偏差 0.014°）——
  这三类有外部 oracle；**正五行、三合、玄空大卦目前只有自建用例，只能说明实现自洽，不能说明符合某派公认算法**。
  该差距需要各派权威算例才能补齐，不是靠多写测试能解决的。

## 第三方数据与授权

完整清单见 `THIRD_PARTY_NOTICES.md`（含随包依赖、仅开发期使用的校验基准、因许可原因未使用其代码的仓库）。要点：

- `lunar-javascript`（MIT）：历法、宜忌、吉神凶煞、二十八宿、时辰吉凶、吉神方位。
- 择日神煞与宜忌等第表按 [`OPN48/cnlunar`](https://github.com/OPN48/cnlunar)（MIT, Copyright (c) 2025 OPN48）的 `godType='8char'` 口径移植为 TypeScript，源数据出自《钦定协纪辨方书》；`tests/fixtures/xieji-oracle.json` 由该库 2026–2027 年输出逐日生成，用于交叉校验。
- 玄空与八宅盘面另有 `tests/fixtures/xuankong-oracle.json`、`bazhai-oracle.json` 两套独立实现结果做交叉校验。
- 两处已知偏离 cnlunar 的实现差异：土王用事从「四立前十八日」正文（cnlunar 取十七日）；岁德、岁德合按立春换年（cnlunar 以正月初一换年）。二者在 `tests/xieji-oracle.test.ts` 中单独断言。
- 神煞移植已独立复验：2020–2035 年共 5844 天逐日比对，42 项神煞与建除值全部一致，仅岁德/岁德合受年界口径影响。
- 玄空 216 局（9 运 × 24 山）与八宅八方、1901–2099 年命卦均与独立 MIT 实现逐宫一致。

## 合规说明

- 阴宅统一表述为「先人纪念地环境建档」，不做按审核状态切换功能的处理；择日严格度开关只影响同一套已公开规则的显示口径，不隐藏任何功能。
- 界面在每条规则上直接展示出处、流派分歧与「待人工复核」标记，避免把流派结论包装成统一吉凶断言。
- 文案避免夸大承诺、负面恐吓与医疗/投资建议；`npm run scan` 会拦截禁词与按审核状态切换的写法。
- 报告与分享图均附使用边界说明，涉及施工、地质、消防与纪念地事项时提示由专业人士现场复核。
