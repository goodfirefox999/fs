import { describe, expect, it } from 'vitest'
import { analyzeDay } from '@/core/engines/shensha'
import { buildZeRi } from '@/core/engines/zeri'
import {
  daysToNextSiLi,
  monthBranchForDate,
  yearGanZhiForDate,
  zhiXingForDate,
} from '@/core/utils/date'

describe('节气与立春口径', () => {
  it('交节当日换月支', () => {
    expect(monthBranchForDate('2026-10-07')).toBe('酉')
    expect(monthBranchForDate('2026-10-08')).toBe('戌')
    expect(monthBranchForDate('2026-02-03')).toBe('丑')
    expect(monthBranchForDate('2026-02-04')).toBe('寅')
  })

  it('立春当日换年干支', () => {
    expect(yearGanZhiForDate('2026-02-03')).toBe('乙巳')
    expect(yearGanZhiForDate('2026-02-04')).toBe('丙午')
    expect(yearGanZhiForDate('2027-01-15')).toBe('丙午')
  })

  it('建除随月建顺行', () => {
    expect(zhiXingForDate('2026-10-30')).toBe('平')
    expect(zhiXingForDate('2026-02-06')).toBe('收')
  })
})

describe('协纪神煞起例', () => {
  it('土王用事为四立前十八日', () => {
    expect(daysToNextSiLi('2026-01-17')).toBe(18)
    expect(analyzeDay('2026-01-17').bad).toContain('土王用事')
    expect(analyzeDay('2026-01-16').bad).not.toContain('土王用事')
    expect(analyzeDay('2026-02-04').bad).not.toContain('土王用事')
  })

  it('天德在四仲月查日支、余月查日干', () => {
    expect(analyzeDay('2026-01-16').good).toContain('天德')
    expect(analyzeDay('2026-01-16').dayGanZhi).toBe('庚寅')
    expect(analyzeDay('2026-02-04').good).not.toContain('天德')
  })

  it('月建与月破随节气月支', () => {
    const jian = analyzeDay('2026-10-27')
    expect(jian.monthBranch).toBe('戌')
    expect(jian.dayGanZhi).toBe('甲戌')
    expect(jian.bad).toContain('月建')
    const po = analyzeDay('2026-10-21')
    expect(po.dayGanZhi).toBe('戊辰')
    expect(po.bad).toContain('月破')
    const beforeJie = analyzeDay('2026-09-26')
    expect(beforeJie.monthBranch).toBe('酉')
    expect(beforeJie.dayGanZhi).toBe('癸卯')
    expect(beforeJie.bad).toContain('月破')
  })

  it('等第判为诸事皆忌', () => {
    const result = analyzeDay('2026-10-30')
    expect(result.level).toBe(4)
    expect(result.isDe).toBe(false)
    expect(result.behavior).toBe('ALL_JI')
  })

  it('吉神抵凶判为从宜不从忌', () => {
    const result = analyzeDay('2026-01-16')
    expect(result.level).toBe(1)
    expect(result.isDe).toBe(true)
    expect(result.behavior).toBe('FROM_YI')
  })
})

describe('择日引擎接入等第与神煞', () => {
  const query = {
    startDate: '2026-01-01',
    daysCount: 120,
    category: 'YANG_DONGTU' as const,
    mountShan: '子',
    familyBirths: [{ date: '1990-06-15', gender: 'M' as const }],
    chongSangMode: 'warn' as const,
    sanShaMode: 'year_month' as const,
    maxResults: 20,
  }
  const result = buildZeRi(query)

  it('返回候选日并带完整字段', () => {
    expect(result.items.length).toBeGreaterThan(0)
    for (const item of result.items) {
      expect(typeof item.level).toBe('number')
      expect(Array.isArray(item.jiShen)).toBe(true)
      expect(Array.isArray(item.luckyHours)).toBe(true)
      expect(Object.keys(item.positions)).toHaveLength(5)
      expect(item.score).toBeTypeOf('number')
    }
  })

  it('排除等第判为诸事皆忌的日子', () => {
    for (const item of result.items) {
      expect(analyzeDay(item.solarDate).behavior, item.solarDate).not.toBe('ALL_JI')
    }
  })

  it('从宜不从忌的日子不因凶煞给出回避提示', () => {
    const suide = result.items.find((item) => item.solarDate === '2026-01-16')
    expect(suide, '2026-01-16 宜起基动土，应进入候选').toBeDefined()
    expect(suide?.level).toBe(1)
    expect(suide?.behavior).toBe('FROM_YI')
    expect(suide?.xiejiJi).toEqual([])
    expect((suide?.xiejiYi.length ?? 0) > 0).toBe(true)
    expect(suide?.warnings.join('')).not.toContain('忌本类用事')
  })

  it('说明文案覆盖新增规则', () => {
    expect(result.notes.join('')).toContain('诸事皆忌')
    expect(result.notes.join('')).toContain('立春')
  })
})
