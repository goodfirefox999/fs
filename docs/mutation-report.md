# 变异测试报告

- 运行时间：2026-11-03T11:02:59+08:00
- 级别：`full`（core = PR 门禁子集，full = nightly 全量）
- 变异点数：28　存活：0
- 结论：✅ 全部被抓住

| 变异点 | 结果 | 目的 |
|---|---|---|
| `dsl-in` | ✅ 抓住 | in 与 nin 互换 —— 若测试未覆盖集合归属，会静默通过 |
| `dsl-gte` | ✅ 抓住 | gte 边界改成严格大于 —— 若测试只测了远离边界的值，会漏 |
| `dsl-between` | ✅ 抓住 | between 边界开闭 —— 边界值是择日判定最常见 off-by-one |
| `zixing-set` | ✅ 抓住 | 把未塞进自刑表 —— 这是本项目明确纠正过的错误，必须有测试守住 |
| `sansha-direction` | ✅ 抓住 | 三煞方位错位（亥卯未煞西→煞东）—— 方位错则整条否决层错 |
| `three-state` | ✅ 抓住 | 禁用命中不再判不可用 —— 三态定义被破坏 |
| `day-pillar` | ✅ 抓住 | 日柱基准偏移一天 —— 金标准四柱会全错 |
| `tier-unknown` | ✅ 抓住 | unknown 不再拉低 tier —— 会把"未知"当"可用"放行 |
| `def-severity-whitelist` | ✅ 抓住 | 定义级 severity 白名单失效 —— 断言可伪装成定义（ADR-0009 核心防线） |
| `publishable-required` | ✅ 抓住 | 必需集阻塞失效 —— 待考证规则也能发布（ADR-0010 核心防线） |
| `caution-not-unsure` | ✅ 抓住 | 强忌不再判存疑 —— 三态定义被破坏 |
| `tier-hardfail` | ✅ 抓住 | 硬伤不判 REJECTED —— 否决层被架空 |
| `rule-conflict` | ✅ 抓住 | 同派内规则冲突不检测 —— 天德/勾陈类互相抵消会被漏掉 |
| `unknown-reason` | ✅ 抓住 | unknown 三分类串味 —— 用户拿不到正确的解除条件 |
| `same-group-kind` | ✅ 抓住 | same_group 的 kind 被忽略 —— 六冲/六合/三刑退化为三合判断 |
| `count-gte` | ✅ 抓住 | count_gte 边界改成严格大于 —— '至少一条'判定失准 |
| `lichun-longitude` | ✅ 抓住 | 立春黄经偏 1° —— 交节时刻错约 1 天，年柱全错 |
| `leap-month` | ✅ 抓住 | 置闰取反（有中气月当闰月）—— 闰月全错 |
| `hour-gan` | ✅ 抓住 | 五鼠遁偏移一位 —— 时柱全错 |
| `month-gan` | ✅ 抓住 | 五虎遁偏移一位 —— 月柱全错 |
| `xunkong-table` | ✅ 抓住 | 旬空表错位 —— 空亡判定全错 |
| `nayin-table` | ✅ 抓住 | 纳音五行错 —— 阴府等以纳音为据的判定全错 |
| `mountain-order` | ✅ 抓住 | 二十四山顺序错（丙巳互换）—— 坐向判定错位 |
| `disagreement-formula` | ✅ 抓住 | 分歧度公式取反 —— 0 表示一致变成 0 表示最分歧 |
| `tier-rank-order` | ✅ 抓住 | 排序方向反了 —— PREFERRED 排到最后 |
| `demo-participation` | ✅ 抓住 | 演示命中被当成确定判定 —— 未考证规则会被表述为「确定排除」 |
| `jianchu-offset` | ✅ 抓住 | 建除位次整体错一位 —— 建日不再是月建日，破日不再等于月破；恒等式必红 |
| `huangdao-star-swap` | ✅ 抓住 | 青龙与明堂对调 —— 月建日不再值青龙，勾陈 12/12 交叉对照必红 |

> 存活 = 测试没真正验证行为。处置方式是**补测试**，不是改变异点或降低阈值。
