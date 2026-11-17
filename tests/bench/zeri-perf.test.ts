import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { buildZeRi } from '@/core/engines/zeri'
import { buildFacts } from '@/core/zeri/facts'

/**
 * 性能测试单独成一个配置（`vitest.perf.config.ts`），不参与默认全量运行。
 *
 * 原因：全量跑时多个测试文件并发，CPU 探针从 41ms 涨到 97ms、暖态成本从 3ms/天
 * 涨到 12ms/天，性能断言会被邻居的负载打成失败——这不是代码退化，
 * 是测量环境不干净。要测性能就必须独占。
 *
 * 运行：`npm run test:perf`
 */

const baseQuery = {
  startDate: '2026-12-01',
  category: 'YIN_ANZANG' as const,
  mountShan: '丙',
  familyBirths: [{ date: '1975-06-01', gender: 'M' as const }],
  maxResults: 20,
}

/** 历史基线：随仓库提交，防止「当次自适配阈值」把真实退化一起吸收掉。 */
const BASELINE_FILE = path.resolve(__dirname, 'perf-baseline.json')
const HARD_CEILING_MS = 3000
const RATCHET_RATIO = 1.4

interface PerfBaseline {
  recordedAt: string
  machine: string
  /** CPU 纯计算探针耗时（1e7 次乘加），用于折算机器快慢 */
  probeMs: number
  /** 暖态下每天 buildFacts 的耗时 */
  msPerDay: number
  note: string
}

function readBaseline(): PerfBaseline {
  if (!fs.existsSync(BASELINE_FILE)) {
    throw new Error(`缺少性能基线文件 ${BASELINE_FILE}；棘轮不能靠当次测量自证`)
  }
  const parsed = JSON.parse(fs.readFileSync(BASELINE_FILE, 'utf8')) as PerfBaseline
  for (const key of ['probeMs', 'msPerDay'] as const) {
    if (typeof parsed[key] !== 'number' || !(parsed[key] > 0)) {
      throw new Error(`性能基线字段 ${key} 非法：${JSON.stringify(parsed)}`)
    }
  }
  return parsed
}

function probeDates(count: number): string[] {
  return Array.from({ length: count }, (_, i) =>
    new Date(Date.UTC(2026, 11, 1 + i)).toISOString().slice(0, 10),
  )
}

/** 固定工作量的 CPU 探针：用来判断「这台机器本来就慢」还是「代码变慢了」。 */
function cpuProbeMs(): number {
  let acc = 0
  const started = performance.now()
  for (let i = 0; i < 10_000_000; i++) acc = (acc + i * 1.000001) % 1e9
  if (acc <= 0) throw new Error('探针被优化掉了')
  return performance.now() - started
}

/** 取多次采样的最小值：并发环境只有下限是可信的。 */
function minFactsMsPerDay(dates: string[], repeats: number): number {
  let best = Number.POSITIVE_INFINITY
  for (let r = 0; r < repeats; r++) {
    const started = performance.now()
    dates.forEach((date) => buildFacts(date, null))
    best = Math.min(best, (performance.now() - started) / dates.length)
  }
  return best
}

describe('择日扫描成本', () => {
  it('180 天扫描在可接受耗时内（含九星标记）', () => {
    const started = Date.now()
    // maxResults 放宽到 60，确保是整窗扫描而不是提前命中就退出
    const result = buildZeRi({ ...baseQuery, daysCount: 180, maxResults: 60 })
    const elapsed = Date.now() - started
    expect(result.scanned).toBe(180)

    const baseline = readBaseline()
    const warmDates = probeDates(30)
    const warmStarted = performance.now()
    warmDates.forEach((date) => buildFacts(date, null))
    const warmupMs = Math.round(performance.now() - warmStarted)

    const probeMs = Math.min(cpuProbeMs(), cpuProbeMs(), cpuProbeMs())
    const sampleDates = probeDates(60)
    minFactsMsPerDay(sampleDates, 1) // 预热缓存后再采样
    const msPerDay = minFactsMsPerDay(sampleDates, 3)

    // 机器折算：探针慢多少，就允许每天成本高多少；下限 1（更快的机器不放宽阈值）
    const machineFactor = Math.max(1, probeMs / baseline.probeMs)
    const allowedMsPerDay = baseline.msPerDay * RATCHET_RATIO * machineFactor

    /**
     * 两层阈值：
     * 1) 退化棘轮（会红的就是它）：每天事实层成本不得超出历史基线 ×1.4×机器折算。
     *    基线记在 tests/bench/perf-baseline.json，随代码提交；
     *    真要放宽只能人工改文件并在 PR 说明原因，不能由当次运行自己算出来。
     * 2) 墙钟预算（吸收噪声）：max(1500, ms/天 × 180 × 3)，并被 HARD_CEILING_MS 封顶，
     *    避免「机器越慢预算越大」变成无上限。
     */
    const allowOverride = process.env.NODE_ENV === 'test' || process.env.CI === 'true'
    const override = allowOverride ? Number(process.env.ZERI_PERF_BUDGET_MS ?? '') : Number.NaN
    const adaptive = Math.max(1500, Math.round(msPerDay * 180 * 3))
    const budget =
      Number.isFinite(override) && override > 0 ? override : Math.min(HARD_CEILING_MS, adaptive)

    console.log(
      `180 天扫描 ${elapsed}ms（预热 ${warmupMs}ms，探针 ${probeMs.toFixed(1)}ms → 机器折算 ${machineFactor.toFixed(2)}，` +
        `暖态 ${msPerDay.toFixed(2)}ms/天 ≤ 基线 ${(baseline.msPerDay * RATCHET_RATIO).toFixed(2)}×折算，` +
        `预算 ${budget}ms），命中 ${result.items.length}，排除 ${result.rejected}`,
    )

    expect(
      msPerDay,
      `成本超出基线 ${(baseline.msPerDay * RATCHET_RATIO).toFixed(2)}ms/天，需人工确认后更新基线文件`,
    ).toBeLessThanOrEqual(allowedMsPerDay)
    expect(elapsed).toBeLessThan(budget)
  })
})
