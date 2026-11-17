import { describe, expect, it } from 'vitest'
import {
  SHAN_24_LIST,
  isJianXiang,
  normalizeDeg,
  oppositeMountain,
  resolveMountain,
} from '@/core/constants/shan24'

describe('二十四山', () => {
  it('按 15° 均分且名称完整', () => {
    expect(SHAN_24_LIST).toHaveLength(24)
    expect(SHAN_24_LIST.map((item) => item.name).join('')).toBe(
      '子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥壬'
    )
  })

  it('边界取山', () => {
    expect(resolveMountain(0).name).toBe('子')
    expect(resolveMountain(7.4).name).toBe('子')
    expect(resolveMountain(7.6).name).toBe('癸')
    expect(resolveMountain(352.5).name).toBe('子')
    expect(resolveMountain(352.4).name).toBe('壬')
  })

  it('对宫正确', () => {
    expect(oppositeMountain('子').name).toBe('午')
    expect(oppositeMountain('艮').name).toBe('坤')
    expect(oppositeMountain('乾').name).toBe('巽')
  })

  it('兼向阈值为 4.5°', () => {
    expect(isJianXiang(0)).toBe(false)
    expect(isJianXiang(4.5)).toBe(false)
    expect(isJianXiang(4.6)).toBe(true)
    expect(normalizeDeg(-1)).toBe(359)
  })
})
