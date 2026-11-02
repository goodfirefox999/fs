# C 第二批迁移清单：`verdict_type` 批量标注（截至 2026-11-03）

> **性质**：这是 C 第二批的**工单列表**，不是裁定结果。每条规则的 gate/vote/reference
> 归类需按 `docs/research/verification-patterns.md` 的判据逐条过：
> 有恒等式/原典支撑 → `vote` 或 `gate`；只有转述 → `reference`。
>
> **进度锁定**：`core-rule/config/verdict_baseline.yaml`（当前未标注 75 条，
> 棘轮测试 `tests/unit/test_verdict_baseline.py` 保证只减不增）。
>
> **为什么这 75 条暂不归类**：不是"行为不明确"（路由行为仍按 severity/hard_veto，
> 与标注前完全一致），而是**证据强度未逐条裁定**——批量给它们安上 gate/vote
> 等于替考证者做主。

## 已完成（C 第一批，10 条 + 1 条影子规则）

| 规则 | verdict_type | 说明 |
|---|---|---|
| PUB-ZIBAI-MONTH-001 | gate | 五黄月盘到山（参评） |
| PUB-ZIBAI-DAY-001 | gate（ineligible） | day_yuan_undecided，参考层 |
| PUB-ZIBAI-HOUR-001 | gate（ineligible） | 同上 |
| PUB-ZIBAI-JI-001 | reference | 四吉到山无原典支撑 |
| PUB-XIU-XIONG-001 | reference | 值宿凶，粗标签 |
| PUB-XIU-JI-001 | reference | 值宿吉，粗标签 |
| PUB-TIANDE-001 | vote | 天德（卦位口径已回显） |
| PUB-YUEDE-001 | vote | 月德 |
| PUB-YUEDE-HE-001 | vote | 月德合 |
| PUB-TIANSHE-001 | vote | 天赦 |
| PUB-WUHUANG-PALACE-001 | gate（ineligible） | Q-018 五黄到宫影子规则（并行会话标注） |

## 待迁移（75 条，按派别分组）

### donggong（5 条）

- [ ] `DG-DASHA-001`
- [ ] `DG-GOUCHEN-001`
- [ ] `DG-JIANCHU-001`
- [ ] `DG-JINSHEN-001`
- [ ] `DG-SANXING-001`

### doushou（6 条）

- [ ] `DS-DEWEI-001`
- [ ] `DS-HUAQI-001`
- [ ] `DS-LIANZHEN-001`
- [ ] `DS-POJUN-001`
- [ ] `DS-SANWU-001`
- [ ] `DS-SANYUAN-001`

### public（47 条）

- [ ] `ASSERT-CHONG-001`
- [ ] `ASSERT-GANCHONG-001`
- [ ] `ASSERT-HAI-001`
- [ ] `ASSERT-PO-001`
- [ ] `ASSERT-REPEAT-001`
- [ ] `ASSERT-XING-001`
- [ ] `ASSERT-XUNKONG-001`
- [ ] `ASSERT-ZIXING-001`
- [ ] `DEF-CHONG-001`
- [ ] `DEF-GANCHONG-001`
- [ ] `DEF-HAI-001`
- [ ] `DEF-PO-001`
- [ ] `DEF-REPEAT-001`
- [ ] `DEF-SANHE-001`
- [ ] `DEF-SANHE-MOUNTAIN-001`
- [ ] `DEF-XING-001`
- [ ] `DEF-XUNKONG-001`
- [ ] `DEF-ZIXING-001`
- [ ] `PUB-BANHE-001`
- [ ] `PUB-CHONGMING-001`
- [ ] `PUB-CHONGMING-002`
- [ ] `PUB-CHONGSHAN-001`
- [ ] `PUB-CHONGSHAN-002`
- [ ] `PUB-DAXIAOYUE-001`
- [ ] `PUB-DUTIAN-001`
- [ ] `PUB-FUBING-001`
- [ ] `PUB-GUANGFU-001`
- [ ] `PUB-JIAQU-001`
- [ ] `PUB-JIAQU-002`
- [ ] `PUB-MING-SANSHA-001`
- [ ] `PUB-SANG-001`
- [ ] `PUB-SANG-002`
- [ ] `PUB-SANHEFU-001`
- [ ] `PUB-SANSHA-001`
- [ ] `PUB-SANSHA-002`
- [ ] `PUB-SANSHA-003`
- [ ] `PUB-SIJUE-001`
- [ ] `PUB-SILI-001`
- [ ] `PUB-SUIPO-001`
- [ ] `PUB-TAISUI-001`
- [ ] `PUB-WUHUANG-001`
- [ ] `PUB-XIANGSHOU-001`
- [ ] `PUB-XIUJIU-001`
- [ ] `PUB-YANGGONG-001`
- [ ] `PUB-YINFU-001`
- [ ] `PUB-YUEJIAN-001`
- [ ] `PUB-YUEPO-001`

### sanhe（4 条）

- [ ] `SH-CHONGSHAN-MARKER-001`
- [ ] `SH-LIUHE-001`
- [ ] `SH-LUMAGUIREN-001`
- [ ] `SH-SANHEJU-001`

### tianxing（4 条）

- [ ] `TX-JIAFU-001`
- [ ] `TX-MOONDAO-001`
- [ ] `TX-SANHEGONG-001`
- [ ] `TX-SUNDAO-001`

### xuankong_dagua（4 条）

- [ ] `XK-CHOUYAO-001`
- [ ] `XK-GUAQI-001`
- [ ] `XK-GUAYUN-001`
- [ ] `XK-WANGQI-001`

### zhengwuxing（5 条）

- [ ] `ZWX-BULONG-001`
- [ ] `ZWX-FUSHAN-001`
- [ ] `ZWX-TIAOHOU-001`
- [ ] `ZWX-TONGGUAN-001`
- [ ] `ZWX-XIANGSHOU-001`

