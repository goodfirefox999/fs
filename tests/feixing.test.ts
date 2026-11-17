import { describe, expect, it } from 'vitest'
import {
  annualCenter,
  annualInfo,
  flyNinePalaces,
  monthGanZhiOf,
  monthlyCenter,
  monthlyForDate,
  sanShaOfZhi,
} from '@/core/engines/feixing'

describe('流年飞星', () => {
  it('年星锚点', () => {
    expect(annualCenter(2020)).toBe(7)
    expect(annualCenter(2022)).toBe(5)
    expect(annualCenter(2024)).toBe(3)
    expect(annualCenter(2025)).toBe(2)
    expect(annualCenter(2026)).toBe(1)
    expect(annualCenter(2027)).toBe(9)
  })

  it('2026 年盘与太岁岁破三煞', () => {
    const info = annualInfo(2026)
    expect(info.yearGanZhi).toBe('丙午')
    expect(info.centerStar).toBe(1)
    expect(info.chart.byPalace[9]).toBe(5)
    expect(info.chart.byPalace[6]).toBe(2)
    expect(info.taiSui).toBe('午')
    expect(info.suiPo).toBe('子')
    expect(info.sanShaMountains).toEqual(['亥', '子', '丑'])
    expect(sanShaOfZhi('申').branches).toEqual(['巳', '午', '未'])
  })

  it('元旦盘', () => {
    const chart = flyNinePalaces(5, 1)
    expect(chart.byPalace[5]).toBe(5)
    expect(chart.byPalace[6]).toBe(6)
    expect(chart.byPalace[1]).toBe(1)
    expect(chart.byPalace[4]).toBe(4)
  })

  it('月星三组表', () => {
    expect(monthlyCenter('午', 1)).toBe(8)
    expect(monthlyCenter('辰', 1)).toBe(5)
    expect(monthlyCenter('寅', 1)).toBe(2)
    expect(monthlyCenter('午', 12)).toBe(6)
  })

  it('五虎遁月干支', () => {
    expect(monthGanZhiOf('丙', 1)).toBe('庚寅')
    expect(monthGanZhiOf('乙', 1)).toBe('戊寅')
    expect(monthGanZhiOf('甲', 1)).toBe('丙寅')
  })

  it('按日期取节气月', () => {
    const feb = monthlyForDate('2026-02-05')
    expect(feb.monthIndex).toBe(1)
    expect(feb.centerStar).toBe(8)
    expect(feb.monthGanZhi).toBe('庚寅')
    const jan = monthlyForDate('2026-01-20')
    expect(jan.monthIndex).toBe(12)
    expect(jan.centerStar).toBe(9)
  })
})
