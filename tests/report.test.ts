import fs from 'node:fs'
import path from 'node:path'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { migrateArchive } from '@/core/archive/migrate'
import { ymdUtcOf } from '@/core/utils/date'
import {
  buildArchiveZeRi,
  buildReport,
  sittingFacingOf,
  zeriCategoryOf,
} from '@/core/engines/report'
import { periodFromYear } from '@/core/engines/xuankong'
import type { Archive, ContentBundle } from '@/core/types'

const bundle = JSON.parse(
  fs.readFileSync(
    path.resolve(process.cwd(), 'cloudfunctions/getReportContent/content/shuangxing.json'),
    'utf8'
  )
) as ContentBundle

function yangArchive(eventYear = 2008): Archive {
  return {
    id: 'a_yang_1',
    mode: 'YANG',
    title: '测试住宅',
    eventYear,
    period: periodFromYear(eventYear) as Archive['period'],
    reading: {
      facingDeg: 180,
      mountDeg: 0,
      northType: 'MAGNETIC',
      declination: 5,
      stability: 95,
      inputMethod: 'MANUAL_DEG',
      uncertainty: 1,
    },
    createdAt: 1,
    updatedAt: 1,
    schemaVersion: 1,
    yang: {
      propertyType: 'RESIDENTIAL',
      members: [{ relation: '本人', birth: { date: '1990-06-15', gender: 'M' } }],
    },
  }
}

function yinArchive(): Archive {
  return {
    id: 'a_yin_1',
    mode: 'YIN',
    title: '测试纪念地',
    eventYear: 2026,
    period: 9,
    reading: {
      facingDeg: 180,
      mountDeg: 0,
      northType: 'MAGNETIC',
      declination: 5,
      stability: 92,
      inputMethod: 'MANUAL_DEG',
      uncertainty: 1,
    },
    createdAt: 1,
    updatedAt: 1,
    schemaVersion: 1,
    yin: {
      monumentType: 'SINGLE',
      deceased: [{ label: '先人', birth: { date: '1950-06-15' } }],
      descendants: [{ label: '家属', birth: { date: '1980-05-05', gender: 'M' } }],
      terrain: { backSupport: 'STRONG', frontView: 'OPEN', leftRight: 'BALANCED' },
    },
  }
}

describe('报告组装', () => {
  it('坐向与类别', () => {
    const archive = yangArchive()
    const sf = sittingFacingOf(archive)
    expect(sf.sitting.name).toBe('子')
    expect(sf.facing.name).toBe('午')
    expect(zeriCategoryOf(archive)).toBe('YANG_RUZHAI')
    expect(zeriCategoryOf(yinArchive())).toBe('YIN_ANZANG')
  })

  it('阳宅报告预览两宫，解锁后完整下发', () => {
    const archive = yangArchive()
    const preview = buildReport(archive)
    expect(preview.chart.pattern).toBe('SHUANG_XING_DAO_XIANG')
    expect(preview.previewPalaces).toEqual([5, 9])
    expect(preview.insights).toHaveLength(9)
    expect(preview.insights.filter((item) => !item.locked)).toHaveLength(2)
    expect(preview.bazhai?.members[0].mingGua.gua).toBe(1)
    expect(preview.zeri.length).toBeGreaterThan(0)
    expect(preview.contentVersion).toBe('preview-2026.10.1')

    const full = buildReport(archive, { contents: bundle, unlocked: true })
    expect(full.insights.every((item) => !item.locked)).toBe(true)
    const face = full.insights.find((item) => item.palace === 9)
    expect(face?.comboKey).toBe('88')
    expect(face?.title).toBe('山八白 · 向八白')
    expect(face?.analysis).toContain('山星八白')
    expect(full.contentVersion).toBe('2026.10.1')
  })

  it('阴宅报告含分金与仙命结论', () => {
    const report = buildReport(yinArchive(), { contents: bundle, unlocked: true })
    expect(report.fenjin?.slot.ganZhi).toBe('戊子')
    expect(report.fenjin?.slot.quality).toBe('KONG_WANG')
    expect(report.yinMatch?.verdict).toBe('AVOID')
    // 分金吉凶未经三源核验，报告不得产生 FENJIN 吉凶警告（附录 E 红线）。
    expect(report.warnings.some((item) => item.code === 'FENJIN')).toBe(false)
    expect(report.warnings.some((item) => item.code === 'YIN_VERDICT')).toBe(true)
    const face = report.insights.find((item) => item.palace === 9)
    expect(face?.analysis).toContain('纪念地')
  })

  it('解锁但内容缺失时给出提示', () => {
    const report = buildReport(yangArchive(), { unlocked: true, contents: null })
    expect(report.warnings.some((item) => item.code === 'CONTENT_UNAVAILABLE')).toBe(true)
    expect(report.insights.filter((item) => !item.locked)).toHaveLength(2)
  })

  it('独立择日入口与报告择日同源', () => {
    const archive = yangArchive()
    const zeri = buildArchiveZeRi(archive, '2026-03-01', 60, 5)
    expect(zeri.items.length).toBeGreaterThan(0)
    expect(zeri.items.length).toBeLessThanOrEqual(5)
    const report = buildReport(archive, { zeri: zeri.items })
    expect(report.zeri).toBe(zeri.items)
  })
})

describe('报告锚点 asOfDate：同一份档案在任何一天打开都是同一份结论', () => {
  const FIXTURES = path.resolve(process.cwd(), 'tests/fixtures')
  const read = (name: string) =>
    JSON.parse(fs.readFileSync(path.join(FIXTURES, name), 'utf8')) as Archive

  /** generatedAt 是「何时生成」的元数据，不是结论；比较结论时要剔除。 */
  function conclusionOf(report: ReturnType<typeof buildReport>) {
    const { generatedAt: _meta, ...conclusion } = report
    return JSON.stringify(conclusion)
  }

  const setClock = (year: number, month: number, day: number) =>
    vi.setSystemTime(new Date(year, month - 1, day, 10, 0, 0))

  afterEach(() => {
    vi.useRealTimers()
  })

  it('有锚点的档案：系统日期不同，报告除 generatedAt 外完全相同', () => {
    // 样本的 asOfDate=2026-01-01、eventYear=2026：择日窗口与 2026 年 1 月的月盘都被冻结在锚点上
    const archive = migrateArchive(read('archive-v3.json'))
    const options = { contents: bundle, unlocked: true, zeriDays: 20 }
    vi.useFakeTimers({ toFake: ['Date'] })

    setClock(2026, 3, 10)
    const inMarch = buildReport(archive, options)
    setClock(2027, 8, 15)
    const nextYear = buildReport(archive, options)

    expect(conclusionOf(nextYear)).toBe(conclusionOf(inMarch))
    expect(inMarch.monthly).toBeDefined()
    for (const item of inMarch.zeri) {
      expect(item.solarDate >= '2026-01-01').toBe(true)
      expect(item.solarDate < '2026-01-21').toBe(true)
    }
  })

  it('对照组：没有锚点的旧档案仍会随系统日期漂移（证明上面的用例不是假阳性）', () => {
    // 未经迁移的 v1 样本没有 asOfDate，退回读系统时间——正是 v3 要消灭的行为
    const legacy = read('archive-v1.json')
    const options = { contents: bundle, unlocked: true, zeriDays: 20 }
    vi.useFakeTimers({ toFake: ['Date'] })

    setClock(2026, 1, 1)
    const onAnchorDay = buildReport(legacy, options)
    setClock(2026, 3, 10)
    const inMarch = buildReport(legacy, options)

    expect(conclusionOf(inMarch)).not.toBe(conclusionOf(onAnchorDay))
  })

  it('锚点回填用 UTC 日期：迁移结果与机器时区无关', () => {
    // 2026-01-01T00:00:00Z 在 UTC-8 的本地日期是 2025-12-31；取本地日期会让同一份档案随机器变 hash
    expect(ymdUtcOf(1767225600000)).toBe('2026-01-01')
    expect(ymdUtcOf(Date.UTC(2026, 11, 31, 23, 59, 59))).toBe('2026-12-31')
  })
})
