/**
 * 数据表的结构性自检。
 *
 * 这些测试不判断「哪一派更对」，只判断「表有没有错位」——
 * 三合局漏一支、宿度总和不等于周天、卦覆盖出现空洞、九星起点错位，
 * 都是靠人眼看不出来、但会让整套判定静默失准的错误。
 */

import { describe, expect, it } from 'vitest'
import { SAN_HE_FRAMES } from '@core/zeri/facts'
import { KAI_XI_DU, GU_DU_TO_DEG, precessionDegForYear } from '@core/zeri/tables/xiu28'
import { NINE_STARS, nineStarTable } from '@core/zeri/tables/donggong'
import { hexagramsCovering } from '@core/zeri/packs/xuankongDagua'
import { YUN_CYCLE_YEARS, yunOfYear, yunSpans } from '@core/zeri/tables/dagua64'

describe('三合四局', () => {
  it('覆盖十二地支，不重不漏', () => {
    const all = SAN_HE_FRAMES.flatMap((frame) => frame.members)
    expect(all).toHaveLength(12)
    expect(new Set(all).size).toBe(12)
  })

  it('四局五行互不相同，且每局三支', () => {
    expect(SAN_HE_FRAMES.map((frame) => frame.element).sort()).toEqual(['水', '火', '金', '木'].sort())
    for (const frame of SAN_HE_FRAMES) {
      expect(frame.members).toHaveLength(3)
    }
  })
})

describe('二十八宿宿度', () => {
  it('二十八宿，古度合计 365.25（周天）', () => {
    expect(KAI_XI_DU).toHaveLength(28)
    const total = KAI_XI_DU.reduce((sum, item) => sum + item.du, 0)
    expect(total).toBeCloseTo(365.25, 6)
  })

  it('古度转今度后合计 360°', () => {
    const total = KAI_XI_DU.reduce((sum, item) => sum + item.du * GU_DU_TO_DEG, 0)
    expect(total).toBeCloseTo(360, 6)
  })

  it('岁差随年份单调增，且 1204 年为零点', () => {
    expect(precessionDegForYear(1204)).toBeCloseTo(0, 6)
    expect(precessionDegForYear(2026)).toBeGreaterThan(precessionDegForYear(1900))
    // 2026 距开禧 822 年，按 50.29″/年约 11.48°
    expect(precessionDegForYear(2026)).toBeCloseTo(11.48, 1)
  })

  it('传统「72 年 1 度」口径与现代口径差约 1%', () => {
    const modern = precessionDegForYear(2026, 'MODERN')
    const traditional = precessionDegForYear(2026, 'TRADITIONAL')
    const ratio = Math.abs(modern - traditional) / modern
    expect(ratio).toBeLessThan(0.02)
  })
})

describe('六十四卦圆周覆盖', () => {
  it('任意角度都能覆盖到至少一个卦，无空洞', () => {
    for (let deg = 0; deg < 360; deg += 0.5) {
      expect(hexagramsCovering(deg).length, `${deg}° 覆盖为空`).toBeGreaterThan(0)
    }
  })

  it('逐度扫描后六十四卦全部出现', () => {
    const seen = new Set<number>()
    for (let deg = 0; deg < 360; deg += 0.25) {
      for (const index of hexagramsCovering(deg)) seen.add(index)
    }
    expect(seen.size).toBe(64)
  })
})

describe('玄空大卦元运', () => {
  it('一运 18 年、九运 27 年（阳爻 9 / 阴爻 6 相加）', () => {
    const spans = yunSpans(1864)
    expect(spans[0]).toMatchObject({ yun: 1, startYear: 1864, years: 18 })
    expect(spans[spans.length - 1]).toMatchObject({ yun: 9, years: 27 })
  })

  it('八运合计 180 年，无五运槽位', () => {
    expect(YUN_CYCLE_YEARS).toBe(180)
    const spans = yunSpans(1864)
    expect(spans.map((span) => span.yun)).toEqual([1, 2, 3, 4, 6, 7, 8, 9])
    expect(spans.reduce((sum, span) => sum + span.years, 0)).toBe(180)
  })

  it('2026 年属九运，且区间首尾相接无空隙', () => {
    const current = yunOfYear(2026)
    expect(current.yun).toBe(9)
    expect(current.startYear).toBeLessThanOrEqual(2026)
    expect(current.endYear).toBeGreaterThanOrEqual(2026)

    const spans = yunSpans(current.cycleStart)
    for (let i = 1; i < spans.length; i++) {
      expect(spans[i].startYear).toBe(spans[i - 1].endYear + 1)
    }
  })
})

describe('董公九星轮值', () => {
  it('九星顺序固定，甲子日按三组月起不同星', () => {
    expect(NINE_STARS).toHaveLength(9)
    const meng = nineStarTable('MENG')
    const zhong = nineStarTable('ZHONG')
    const ji = nineStarTable('JI')
    expect(meng[0]).toBe('妖星')
    expect(zhong[0]).toBe('惑星')
    expect(ji[0]).toBe('禾刀')
  })

  it('每组表长 60，且严格按九星循环', () => {
    for (const group of ['MENG', 'ZHONG', 'JI'] as const) {
      const table = nineStarTable(group)
      expect(table).toHaveLength(60)
      for (let i = 1; i < table.length; i++) {
        const prev = NINE_STARS.indexOf(table[i - 1])
        const current = NINE_STARS.indexOf(table[i])
        expect(current).toBe((prev + 1) % 9)
      }
    }
  })
})
