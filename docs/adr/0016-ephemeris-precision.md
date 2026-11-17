# ADR-0016：节气与真太阳时的星历精度底座

- 状态：已采纳
- 日期：2026-11-04
- 触发：
  - 「节气计算放弃简化公式，改用 Skyfield + DE431/DE440，太阳黄经求根精度 < 0.1 秒」
  - 「任取一个节气交接时刻，与 NASA JPL Horizons 或 Swiss Ephemeris 官方输出比对，
    差值必须 < 1 秒；否则不得进入生产路径」
  - 「真太阳时必须同时包含经度校正 + 均时差；均时差用 VSOP87 或 Skyfield，不用 Spencer 近似」

## 一、背景：原 VSOP87 后备的真实误差

原实现是截断 VSOP87D（L0 64 项、L1 34 项……）+ Meeus 低精度章动 + 解析 ΔT 插值，
不是张培瑜简化公式，均时差也已经是 Meeus 28.3 而非 Spencer。但与 JPL DE440s
逐节气对拍后，2026 年 24 个节气的 TT 最大差 **6.97 秒**、UTC 最大差 **6.90 秒**
（ΔT 锚点修正前 UTC 最大 9.06 秒）。这不能满足「< 1 秒」的生产判据。

另一个被这次对拍暴露的问题是求根器的**跨 0°/360° 假导数**：春分附近有限差分
直接相减会得到约 −3600°/日的导数，旧代码靠 `d_lon <= 0 → 0.9856` 兜底才没有发散，
但会在残差未收敛时提前退出。现已改为对差分做 360° 解缠（`ephemeris.py` 与
`skyfield_ephemeris.py` 两处），参考表生成器也使用同一规则。

## 二、决策

| 层 | 决策 |
|---|---|
| 默认后端 | `auto`：能导入 skyfield 且星历文件存在时用 **Skyfield + DE440s**；否则回退 VSOP87 |
| 强制后端 | `ZERI_EPHEMERIS_BACKEND=skyfield` 在不可用时直接抛错，不静默降级 |
| 星历文件 | 默认 `~/.cache/zeri/skyfield/de440s.bsp`，`ZERI_EPHEMERIS_PATH` 可覆盖；**运行时不自动下载** |
| 可解释性 | 报告 `manifest.ephemeris` 全字段回显 `backend / precision / ephemeris_file / valid_range / delta_t_s / fallback_reason`；`precision` 只有 `high`（skyfield）与 `degraded`（vsop87） |
| 降级边界门 | 降级后端下候选距「节」< 15 秒 → `second_precision_required=true`；引擎把所有非定义级命中降为「证据不足」（`block_kind=evidence_insufficient`），已签规则也不得投票 |
| DE440s 范围 | 1849-12-26..2150-01-22（UTC）；越界显式 `ValueError`，不静默外推 |
| 生产路径 | 生产/验收结论必须 `precision=high`；`degraded` 只用于离线开发与降级演练，不得作为签名或对外结论的依据 |
| 依赖 | `pyproject.toml` 的 `high-precision = ["skyfield>=1.49"]`；不把星历文件打进包 |

## 三、验证证据

### 3.1 节气：Skyfield/DE440s vs Swiss Ephemeris 官方数据

参考表：`tests/golden/data/solar_terms_swisseph.json`
（Swiss Ephemeris 2.10.03 + 官方 `sepl_18.se1`，文件 SHA-256
`ca1393ceab3a44fbc895887cf789c68819ae6a1cbc9b22225872dbe4ccd99a66`）。

| 范围 | 指标 | 实测最大差 | 判据 |
|---|---|---|---|
| 2000-2100，24×9 个节气 | TT | **0.060 s** | < 0.1 s |
| 2000-2030，24×7 个节气 | UTC | **0.060 s** | **< 1 s** |
| 2050 / 2100 | UTC | 5.7 s / 24.4 s | 不判定——差异来自 ΔT **预测**分歧，不是星历误差 |
| 2050 / 2100 | TT | 0.044 s / 0.037 s | < 0.1 s |

测试：`tests/golden/test_ephemeris_precision.py`（Skyfield 不可用时 skip，并打印原因）。
参考表由独立实现/独立星历生成，不是拿本引擎给自己对答案。

### 3.2 均时差：vs Swiss `swe.time_equ`

2026 与 2050 各 12 个采样点（每月 15 日 12:00 UTC），本引擎与 Swiss 最大差
**0.43 秒**。经度校正仍是独立的 `(站点经度 − 时区中央经线) × 4 min/°`，
两项相加得到真太阳时。

### 3.3 Horizons 交叉核对与一个必须说清的口径差

- 2026 立春前后，Horizons 的**天测 RA/Dec** 与 Skyfield 一致到毫角秒级；
- Horizons `QUANTITIES=31` 的 `ObsEcLon` 与 Skyfield/Swiss 的视黄经有约
  **0.045″** 的常数差，对应约 **1.1 秒**。这是「历元/春分点实现」差异，不是星历误差：
  Swiss 官方与 Skyfield 两套独立实现彼此只差 0.002″。
- 中国节气定义用的是**真春分点视黄经**，因此本引擎以 Skyfield/Swiss 口径为准；
  Horizons 的 ObsEcLon 不作为节气时刻的最终仲裁，只用于天测位置交叉核对。

### 3.4 VSOP87 后备仍必须显式降级

2026 年 24 个节气中，VSOP87 与 DE440s 的 UTC 最大差仍约 **7 秒**（不同节气不同，
立春恰好较小，测试取全年最大）。因此后备路径：

- `SolarTerm.backend = "vsop87"`；
- `manifest.ephemeris.precision = "degraded"`；
- 不删除该路径（离线环境仍要能跑），但不得冒充 `high`。

### 3.5 时间尺度与闰秒

| 路径 | UTC / TT / UT1 | 闰秒 |
|---|---|---|
| Skyfield/DE440s | `skyfield.timescale` 内部换算；`SolarTerm` 同时保存 `jd_ut`（UTC）、`jd_tt`（TT）、`delta_t_s`（TT−UT1） | 使用 Skyfield 内置闰秒表 |
| VSOP87 后备 | ΔT 锚点插值；把 UT1 与 UTC 视为同一尺度（差异 < 0.9 s） | 不单独处理，只保证 <1 s 的降级精度 |

生产路径要求 Skyfield；VSOP87 的 UT1/UTC 简化只服务离线降级，不用于秒级仲裁。

## 四、复现

```bash
# 1) 安装可选依赖
uv pip install -e '.[high-precision]'      # 或 pip install -e '.[high-precision]'

# 2) 放置星历（不会自动下载）
mkdir -p ~/.cache/zeri/skyfield
# 从 JPL 获取 de440s.bsp 后放到上述路径，或设置 ZERI_EPHEMERIS_PATH

# 3) 强制高精度并跑对拍
ZERI_EPHEMERIS_BACKEND=skyfield \
  PYTHONPATH=core-rule/src:core-symbol/src:core-time/src:core-eval/src:app-zeri/src \
  .venv/bin/python -m pytest tests/golden/test_ephemeris_precision.py -q

# 4) 关闭 Skyfield 验证降级标注
ZERI_EPHEMERIS_BACKEND=vsop87 \
  PYTHONPATH=... .venv/bin/python -m pytest tests/golden/test_solar_terms_regression.py -q
```

参考表的重新生成需要 `pyswisseph` 与官方 `sepl_18.se1`；该数据文件**不进入仓库**，
只在开发缓存中使用。`tests/golden/data/solar_terms_swisseph.json` 存的是派生时刻
（事实数据），不是 Swiss 数据文件本身。

## 五、后果与未决

1. **2026 立春旧锚点作废**：旧值 `04:01:51` 比 Swiss/Horizons 早约 17 秒，
   已从回归测试移除；不再保留秒级「公开历书」锚点，避免把低精度转述当成真值。
2. **`publishable` 不等于精度合格**：`publishable` 仍只表示「必需规则集闭合」，
   精度门禁看 `manifest.ephemeris.precision`。两者不可互相替代；报告若为
   `precision=degraded`，即使 `publishable=true` 也不得作为签名或对外结论依据。
3. **2050 以后的 UTC 不承诺 < 1 秒**：这是 ΔT 预测的物理限制，不是本引擎能修的；
   TT 对拍仍 < 0.1 秒。若将来要发布远期 UTC，必须单独标注 ΔT 模型与不确定度。
4. **生产门禁未接入 CI**：按当前「停止过度工程」的约束，`precision=degraded`
   只做显式标注与测试断言，不新增 CI 门禁；发布前人工检查 manifest。
5. **月球/行星未纳入**：本次只升级太阳（节气、四柱、真太阳时）。天星派若需要
   月球/行星高精度，需另立 ADR，不能默认沿用本条。
