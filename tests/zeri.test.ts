import { describe, expect, it } from 'vitest'
import { Solar } from 'lunar-javascript'
import { buildZeRi, categoryLabel } from '@/core/engines/zeri'
import { ZHI_CLASH } from '@/core/constants/nayin60'
import { isSiLiSiJueDay, isYangGongJi, parseYmd } from '@/core/utils/date'

const TERMS = ['安葬', '启钻', '破土']

describe('择日筛选', () => {
  it('阴宅安葬候选日满足硬条件', () => {
    const result = buildZeRi({
      startDate: '2026-01-01',
      daysCount: 150,
      category: 'YIN_ANZANG',
      mountShan: '子',
      familyBirths: [{ date: '1990-06-15', gender: 'M' }],
      deceasedBirths: [{ date: '1950-06-15' }],
      chongSangMode: 'warn',
      sanShaMode: 'year_month',
      maxResults: 20,
    })
    expect(result.items.length).toBeGreaterThan(0)
    expect(result.items.length).toBeLessThanOrEqual(20)
    expect(result.scanned).toBeGreaterThan(0)

    for (const item of result.items) {
      expect(item.matchedYi.some((term) => TERMS.includes(term))).toBe(true)
      expect(item.dayJi.some((term) => TERMS.includes(term))).toBe(false)
      expect(isSiLiSiJueDay(item.solarDate).hit).toBe(false)

      const { year, month, day } = parseYmd(item.solarDate)
      const lunar = Solar.fromYmd(year, month, day).getLunar()
      const dayZhi = lunar.getDayZhi()
      expect(item.ganZhi).toBe(lunar.getDayInGanZhi())
      expect(isYangGongJi(lunar.getMonth(), lunar.getDay())).toBe(false)
      expect(dayZhi).not.toBe('子')
      expect(dayZhi).not.toBe('午')
      expect(dayZhi).not.toBe(ZHI_CLASH[lunar.getYearInGanZhiExact().slice(1)])
      expect(dayZhi).not.toBe(ZHI_CLASH[lunar.getMonthZhiExact()])
    }

    const dates = result.items.map((item) => item.solarDate)
    expect([...dates].sort()).toEqual(dates)
  })

  it('四离四绝与杨公忌判定', () => {
    expect(isSiLiSiJueDay('2026-02-03').hit).toBe(true)
    expect(isSiLiSiJueDay('2026-02-04').hit).toBe(false)
    expect(isYangGongJi(1, 13)).toBe(true)
    expect(isYangGongJi(1, 12)).toBe(false)
    expect(isYangGongJi(-7, 1)).toBe(true)
  })

  it('阳宅入宅候选日使用入宅类词条', () => {
    const result = buildZeRi({
      startDate: '2026-03-01',
      daysCount: 60,
      category: 'YANG_RUZHAI',
      mountShan: '午',
      familyBirths: [],
      maxResults: 8,
    })
    for (const item of result.items) {
      expect(item.matchedYi.some((term) => ['入宅', '移徙', '安床'].includes(term))).toBe(true)
    }
  })

  it('展示条数只截取候选，不截断扫描与统计', () => {
    const result = buildZeRi({
      startDate: '2026-03-01',
      daysCount: 120,
      category: 'YANG_RUZHAI',
      mountShan: '午',
      familyBirths: [],
      maxResults: 1,
    })
    expect(result.scanned).toBe(120)
    expect(result.eligible).toBeGreaterThan(1)
    expect(result.items).toHaveLength(1)
    expect(result.truncated).toBe(true)
    expect(result.rejected + result.unmatched + result.eligible).toBe(result.scanned)
  })

  it('新增嫁娶与开市类别有独立文案，且不是修坟立碑的兜底', () => {
    expect(categoryLabel('YANG_JIAQU')).toBe('嫁娶订盟')
    expect(categoryLabel('YANG_KAISHI')).toBe('开市交易')
  })

  it.each([
    ['YANG_JIAQU', ['嫁娶', '结婚姻', '纳采', '订盟']],
    ['YANG_KAISHI', ['开市', '交易', '立券', '纳财']],
  ] as const)('%s 能完整扫描并只产出本类词条的候选', (category, terms) => {
    const result = buildZeRi({
      startDate: '2026-03-01',
      daysCount: 60,
      category,
      mountShan: '午',
      familyBirths: [],
      maxResults: 5,
    })
    expect(result.scanned).toBe(60)
    for (const item of result.items) {
      expect(item.matchedYi.some((term) => terms.some((known) => known === term))).toBe(true)
    }
  })
})
