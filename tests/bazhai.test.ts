import { describe, expect, it } from 'vitest'
import {
  analyzeBaZhai,
  calcMingGua,
  houseGuaOf,
  palacesOfGua,
} from '@/core/engines/bazhai'
import { MING_GUA_INFO } from '@/core/constants/luoshu'

describe('八宅命卦', () => {
  it('命卦公式样本', () => {
    expect(calcMingGua({ date: '1990-06-15', gender: 'M' })?.gua).toBe(1)
    expect(calcMingGua({ date: '1990-06-15', gender: 'F' })?.gua).toBe(8)
    expect(calcMingGua({ date: '2000-06-15', gender: 'M' })?.gua).toBe(9)
    expect(calcMingGua({ date: '2000-06-15', gender: 'F' })?.gua).toBe(6)
    expect(calcMingGua({ date: '1984-06-15', gender: 'M' })?.gua).toBe(7)
    expect(calcMingGua({ date: '1984-06-15', gender: 'F' })?.gua).toBe(8)
    expect(calcMingGua({ date: '1995-06-15', gender: 'M' })?.gua).toBe(2)
    expect(calcMingGua({ date: '1995-06-15', gender: 'F' })?.gua).toBe(1)
  })

  it('五黄寄宫', () => {
    expect(calcMingGua({ date: '1995-06-15', gender: 'M' })?.gua).toBe(2)
    expect(calcMingGua({ date: '1995-06-15', gender: 'F' })?.gua).toBe(1)
  })

  it('立春界', () => {
    expect(calcMingGua({ date: '1990-01-20', gender: 'M' })?.effectiveYear).toBe(1989)
    expect(calcMingGua({ date: '1990-02-10', gender: 'M' })?.effectiveYear).toBe(1990)
    expect(calcMingGua({ date: '1990-02-04', gender: 'M' })?.effectiveYear).toBe(1990)
    expect(
      calcMingGua({ date: '1990-06-15', precision: 'YEAR', beforeLiChun: true, gender: 'M' })
        ?.effectiveYear
    ).toBe(1989)
  })

  it('缺少年份或性别时返回空', () => {
    expect(calcMingGua({ date: '', gender: 'M' })).toBeNull()
    expect(calcMingGua({ date: '1990-01-01' })).toBeNull()
  })

  it('坎命八方星', () => {
    const palaces = palacesOfGua(1)
    const byPalace = Object.fromEntries(palaces.map((item) => [item.palace, item.star.name]))
    expect(byPalace[1]).toBe('伏位')
    expect(byPalace[8]).toBe('五鬼')
    expect(byPalace[2]).toBe('绝命')
    expect(byPalace[3]).toBe('天医')
    expect(byPalace[4]).toBe('生气')
    expect(byPalace[6]).toBe('六煞')
    expect(byPalace[7]).toBe('祸害')
    expect(byPalace[9]).toBe('延年')
  })

  it('64 组合完整且四吉星各一', () => {
    const guas = Object.keys(MING_GUA_INFO).map(Number)
    let count = 0
    for (const gua of guas) {
      const palaces = palacesOfGua(gua)
      expect(palaces).toHaveLength(8)
      const good = palaces.filter((item) => item.star.level === 'GOOD')
      expect(good).toHaveLength(4)
      expect(new Set(good.map((item) => item.star.code)).size).toBe(4)
      count += palaces.length
    }
    expect(count).toBe(64)
  })

  it('宅卦与命宅分组', () => {
    expect(houseGuaOf('子').name).toBe('坎')
    expect(houseGuaOf('子').group).toBe('EAST')
    expect(houseGuaOf('乾').name).toBe('乾')
    expect(houseGuaOf('乾').group).toBe('WEST')
    const result = analyzeBaZhai(
      [
        { relation: '本人', birth: { date: '1990-06-15', gender: 'M' } },
        { relation: '家人', birth: { date: '', gender: 'F' } },
      ],
      '子'
    )
    expect(result.house.gua).toBe(1)
    expect(result.members).toHaveLength(1)
    expect(result.members[0].match).toBe('MATCH')
    expect(result.notes.length).toBeGreaterThan(0)
  })
})
