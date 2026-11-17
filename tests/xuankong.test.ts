import { describe, expect, it } from 'vitest'
import {
  buildXuanKong,
  findMountainByGongAndYuan,
  periodFromYear,
  resolveFlight,
} from '@/core/engines/xuankong'
import { getMountain } from '@/core/constants/shan24'

function palace(chart: ReturnType<typeof buildXuanKong>, id: number) {
  const found = chart.palaces.find((item) => item.palace === id)
  if (!found) throw new Error(`missing palace ${id}`)
  return found
}

describe('玄空飞星', () => {
  it('运由年份确定', () => {
    expect(periodFromYear(1864)).toBe(1)
    expect(periodFromYear(1984)).toBe(7)
    expect(periodFromYear(2004)).toBe(8)
    expect(periodFromYear(2024)).toBe(9)
    expect(periodFromYear(2026)).toBe(9)
  })

  it('八运子山午向为双星到向', () => {
    const chart = buildXuanKong({ period: 8, sittingDeg: 0 })
    expect(chart.sitting.shan).toBe('子')
    expect(chart.facing.shan).toBe('午')
    expect(chart.pattern).toBe('SHUANG_XING_DAO_XIANG')
    expect(chart.isJianXiang).toBe(false)
    expect(palace(chart, 9).shan).toBe(8)
    expect(palace(chart, 9).xiang).toBe(8)
    expect(palace(chart, 1).shan).toBe(9)
    expect(palace(chart, 1).xiang).toBe(7)
  })

  it('八运午山子向为双星到山', () => {
    const chart = buildXuanKong({ period: 8, sittingDeg: 180 })
    expect(chart.pattern).toBe('SHUANG_XING_DAO_SHAN')
    expect(palace(chart, 9).shan).toBe(8)
    expect(palace(chart, 9).xiang).toBe(8)
  })

  it('八运乾山巽向为旺山旺向', () => {
    const chart = buildXuanKong({ period: 8, sittingDeg: 315 })
    expect(chart.sitting.shan).toBe('乾')
    expect(chart.facing.shan).toBe('巽')
    expect(chart.pattern).toBe('WANG_SHAN_WANG_XIANG')
    expect(palace(chart, 6).shan).toBe(8)
    expect(palace(chart, 4).xiang).toBe(8)
  })

  it('同宫阴阳相同之兼仍用下卦（子兼癸）', () => {
    const chart = buildXuanKong({ period: 8, sittingDeg: 5 })
    expect(chart.isJianXiang).toBe(true)
    expect(chart.tiGuaUsed).toBe(false)
    expect(chart.jianKind).toBe('TONG_GONG')
    expect(chart.sitting.shan).toBe('子')
    expect(chart.facing.shan).toBe('午')
    expect(palace(chart, 1).shan).toBe(9)
    expect(palace(chart, 9).xiang).toBe(8)
  })

  it('阴阳互兼用替卦（壬兼子）', () => {
    const chart = buildXuanKong({ period: 8, sittingDeg: 351 })
    expect(chart.sitting.shan).toBe('壬')
    expect(chart.jianKind).toBe('YIN_YANG_JIAN')
    expect(chart.tiGuaUsed).toBe(true)
    expect(palace(chart, 5).shan).toBe(6)
  })

  // 中州派《地理辨正正释》系兼向起星例：八运壬山丙向兼亥巳，四之地元龙辰替六逆飞，三之地元龙甲替一顺飞
  it('出卦必替（八运壬山丙向兼亥巳）', () => {
    const chart = buildXuanKong({ period: 8, sittingDeg: 339 })
    expect(chart.sitting.shan).toBe('壬')
    expect(chart.facing.shan).toBe('丙')
    expect(chart.jianKind).toBe('CHU_GUA')
    expect(chart.tiGuaUsed).toBe(true)
    expect(palace(chart, 5)).toMatchObject({ yun: 8, shan: 6, xiang: 1 })
    expect(palace(chart, 1)).toMatchObject({ yun: 4, shan: 1, xiang: 6 })
    expect(palace(chart, 9)).toMatchObject({ yun: 3, shan: 2, xiang: 5 })
    expect(chart.warnings.join('')).toContain('出卦')
  })

  it('五黄入中不替，按本山阴阳定顺逆', () => {
    const chart = buildXuanKong({ period: 8, sittingDeg: 230.5 })
    expect(chart.sitting.shan).toBe('坤')
    expect(chart.isJianXiang).toBe(true)
    expect(palace(chart, 5).shan).toBe(5)
    expect(palace(chart, 2).shan).toBe(2)
  })

  it('同宫同元龙可反查', () => {
    expect(findMountainByGongAndYuan(4, 'TIAN').name).toBe('巽')
    expect(findMountainByGongAndYuan(3, 'TIAN').name).toBe('卯')
    expect(findMountainByGongAndYuan(9, 'TIAN').name).toBe('午')
  })

  it('五黄入中两种策略方向不同', () => {
    const ben = resolveFlight(5, getMountain('子'), false, 'BEN_SHAN')
    const kun = resolveFlight(5, getMountain('子'), false, 'JI_KUN')
    expect(ben.direction).toBe(-1)
    expect(kun.direction).toBe(1)
  })
})
