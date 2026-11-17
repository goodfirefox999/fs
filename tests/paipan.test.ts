import { describe, expect, it } from 'vitest'
import { buildPaipanReport } from '@core/paipan'
import { paipanSourceOf } from '@core/paipan/sources'
import { periodFromYear } from '@core/engines/xuankong'

const BASE = {
  mountShan: '子',
  sittingDeg: 0,
  year: 2026,
  members: [{ relation: '主命1', birth: { date: '1975-06-01', gender: 'M' as const } }],
  deceased: [{ label: '先父', birth: { date: '1938-04-12', gender: 'M' as const } }],
}

describe('排盘四派并列', () => {
  it('始终返回四张卡片，顺序固定', () => {
    const report = buildPaipanReport(BASE)
    expect(report.schools.map((school) => school.school)).toEqual([
      'BA_ZHAI',
      'XUAN_KONG',
      'FEI_XING',
      'XIAN_MING',
    ])
  })

  it('缺数据时仍出卡片，但标 PARTIAL 并说明原因', () => {
    const report = buildPaipanReport({ mountShan: '子', sittingDeg: 0, year: 2026 })
    expect(report.schools).toHaveLength(4)

    const baZhai = report.schools.find((school) => school.school === 'BA_ZHAI')!
    expect(baZhai.status).toBe('PARTIAL')
    expect(baZhai.partialReason).toContain('出生日期')

    const xianMing = report.schools.find((school) => school.school === 'XIAN_MING')!
    expect(xianMing.status).toBe('PARTIAL')
    expect(xianMing.partialReason).toContain('仙命')

    expect(report.dataGaps.length).toBe(2)
    expect(report.dataGaps.join()).toContain('八宅')
    expect(report.dataGaps.join()).toContain('仙命')
  })

  it('紫白只出事实，不给倾向', () => {
    const report = buildPaipanReport(BASE)
    const feiXing = report.schools.find((school) => school.school === 'FEI_XING')!
    expect(feiXing.tendency).toBe('neutral')
    const ids = feiXing.subRules.map((rule) => rule.ruleId)
    expect(ids).toContain('FX_CENTER')
    expect(ids).toContain('FX_TAISUI')
    expect(ids).toContain('FX_SUIPO')
    expect(ids).toContain('FX_SANSHA')
  })

  it('玄空按用事年份取元运', () => {
    const report = buildPaipanReport(BASE)
    const xuanKong = report.schools.find((school) => school.school === 'XUAN_KONG')!
    expect(xuanKong.extras?.period).toBe(periodFromYear(2026))
    expect(xuanKong.subRules.map((rule) => rule.ruleId)).toContain('XK_PATTERN')
  })

  it('八宅给出成员数与同组数，多成员不同组时列冲突', () => {
    const report = buildPaipanReport({
      ...BASE,
      members: [
        { relation: '主命1', birth: { date: '1975-06-01', gender: 'M' as const } },
        { relation: '主命2', birth: { date: '1980-03-15', gender: 'F' as const } },
      ],
    })
    const baZhai = report.schools.find((school) => school.school === 'BA_ZHAI')!
    expect(baZhai.extras?.totalMembers).toBe(2)
    // 同组数应在 0..2 之间；若恰为 1，必须给出冲突说明
    const matched = Number(baZhai.extras?.matchedMembers)
    expect(matched).toBeGreaterThanOrEqual(0)
    expect(matched).toBeLessThanOrEqual(2)
    if (matched === 1) {
      expect(baZhai.conflictFlags.length).toBeGreaterThan(0)
    }
  })

  it('仙命无数据时倾向为 insufficient_data', () => {
    const report = buildPaipanReport({ ...BASE, deceased: [] })
    const xianMing = report.schools.find((school) => school.school === 'XIAN_MING')!
    expect(xianMing.tendency).toBe('insufficient_data')
  })
})

describe('排盘出处纪律', () => {
  it('每条子规则的出处都来自登记表，且写了流派分歧', () => {
    const report = buildPaipanReport(BASE)
    for (const school of report.schools) {
      for (const rule of school.subRules) {
        expect(rule.source.id, `${school.school}/${rule.ruleId} 缺 source.id`).toBeTruthy()
        expect(rule.source.title, `${school.school}/${rule.ruleId} 缺 source.title`).toBeTruthy()
        expect(
          rule.source.lineageNote,
          `${school.school}/${rule.ruleId} 未写 lineageNote（必须说明该派主张与事实的边界）`,
        ).toBeTruthy()
      }
    }
  })

  it('未登记的出处 key 直接抛错，不静默返回空', () => {
    expect(() => paipanSourceOf('NOT_REGISTERED')).toThrow(/排盘出处/)
  })

  it('四派出处各自独立，不共用一条', () => {
    const ids = ['BA_ZHAI', 'XUAN_KONG', 'FEI_XING', 'XIAN_MING'].map(
      (key) => paipanSourceOf(key).id,
    )
    expect(new Set(ids).size).toBe(4)
  })
})
