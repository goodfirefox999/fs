import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
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
    expect(report.warnings.some((item) => item.code === 'FENJIN')).toBe(true)
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
