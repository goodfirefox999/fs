# ADR-0011：年月柱/日时柱时间基准拆分，与 fact_hash 的约定完整性

- 状态：已采纳
- 日期：2026-11-01
- 决策者：评审意见（2026-11-01 两轮，观点互补）
- 触发：
  - 第一轮：「真太阳时那个'缺陷'，可能不是缺陷 —— 年月柱由节气交接决定（比较用钟表时），
    时柱用真太阳时，是传统常见混合口径」
  - 第二轮：「`hour_ref` 是全局约定，四柱的换年/换月/换日/换时全部基于同一 `hour_ref`」

## 背景

v0.2 曾把"年月柱用民用时、时柱用真太阳时"判为内部矛盾并统一到 `hour_ref`。
但两位评审给出了互补的视角：

- **跨口径的混合是选择**（传统实践确实存在），应由配置表达，不应在实现层定死；
- **同一量在不同代码路径用不同基准**才是真 bug（如"时柱用真太阳时、日柱用民用时换日"）。

## 决策一：两个独立配置

```python
CalendarConfig(
    ym_time_ref="auto",    # auto | civil | true_solar —— 年/月柱（比交节用哪个时间）
    hour_time_ref="auto",  # auto | civil | true_solar —— 日/时柱（含换日边界）
)
```

- `auto` 跟随 `use_true_solar_time`（保持旧配置兼容，默认 `auto` + `False` = 全民用时）；
- 年/月柱用 `ym_ref`，日/时柱用 `hour_ref`；
- **日柱换日边界跟随 `hour_ref`** —— 这是"同一量同一基准"的要求，不是口径选择。

## 决策二：fact_hash 必须含完整约定

```python
fact_hash = hash(facts + {day_boundary, use_true_solar_time, ym_time_ref, hour_time_ref, calibers})
```

理由：若只哈希 facts，两套口径下算出的四柱可能**碰巧相同**，
"同 fact 不同口径"被误判为一致，分歧度指标就失去意义。

**但要注意**：不同约定下 hash 不同是**预期**的，不是错误。
若两派约定不同，应通过多次 `evaluate` 对比（并输出 `convention_divergence`），
而不是在同一 `evaluate` 内混合 —— 后者才是 bug，故引擎仍保留一致性断言。

## 测试守护

`tests/golden/test_boundary_and_convention.py`：

| 用例 | 断言 |
|---|---|
| 民用时 23:30 + 子正换日 | 日柱不换（辛卯） |
| 民用时 23:30 + 子初换日 | 日柱换（壬辰） |
| 东经 113° 真太阳时 23:30 | 回退到 22:58，**日柱不换** |
| 东经 125° 民用时 22:55 | 真太阳时 23:10，**日柱换** |
| 混合口径（ym=civil, hour=true_solar）立春 +10min | 年柱按民用时（丁未），时柱按真太阳时 |
| 全真太阳时立春 +10min | 年柱被拉回交节前（丙午） |
| 同约定两次 hash | 相同 |
| 不同 day_boundary / 不同 time_ref | hash 不同 |

## 后果

- ✅ 混合口径是配置项，报告「口径回显」列出 `ym_time_ref` / `hour_time_ref` 两者。
- ✅ 日柱换日不再出现"时柱真太阳时、日柱民用时"的内部矛盾。
- ⚠️ `ym_time_ref` / `hour_time_ref` 增加两个 CLI 参数位（`--param ym_time_ref=true_solar`），
  文档需同步（已更新 DEVELOPMENT 第 6 节）。
- ⚠️ 默认回到 `civil`（惯例口径），这与 v0.2 的"统一到 hour_ref"行为不同 ——
  **是行为变更，不是纯 bugfix**，已在 CHANGELOG 0.3.0 标注。
