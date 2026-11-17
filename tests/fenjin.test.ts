import { describe, expect, it } from 'vitest'
import {
  FENJIN_SLOTS,
  checkKongWangLine,
  fenJinOfMountain,
  nearestUsableSlot,
  resolveFenJin,
  suggestFenJinSlots,
} from '@/core/constants/fenjin120'
import { angularDelta } from '@/core/constants/shan24'

describe('一百二十分金', () => {
  it('共 120 格，每山 5 格', () => {
    expect(FENJIN_SLOTS).toHaveLength(120)
    for (const slot of FENJIN_SLOTS) {
      expect(slot.endDeg).not.toBe(slot.startDeg)
    }
    expect(fenJinOfMountain('子')).toHaveLength(5)
  })

  it('子山五格排布', () => {
    const slots = fenJinOfMountain('子')
    expect(slots.map((slot) => slot.ganZhi)).toEqual(['甲子', '丙子', '戊子', '庚子', '壬子'])
    expect(slots.map((slot) => slot.centerDeg)).toEqual([354, 357, 0, 3, 6])
    expect(slots.map((slot) => slot.quality)).toEqual([
      'GU_XU',
      'WANG_XIANG',
      'KONG_WANG',
      'WANG_XIANG',
      'GU_XU',
    ])
    expect(slots.map((slot) => slot.nayin)).toEqual([
      '海中金',
      '涧下水',
      '霹雳火',
      '壁上土',
      '桑柘木',
    ])
  })

  it('0° 落在戊子，几何事实可查但不输出吉凶', () => {
    const result = resolveFenJin(0)
    expect(result.slot.ganZhi).toBe('戊子')
    // 内部分类保留供后续考证使用，但用户可见文案不得含吉凶结论。
    expect(result.slot.quality).toBe('KONG_WANG')
    expect(result.warning).toBeNull()
  })

  it('3° 落在庚子旺相', () => {
    const result = resolveFenJin(3)
    expect(result.slot.ganZhi).toBe('庚子')
    expect(result.slot.quality).toBe('WANG_XIANG')
    expect(result.slot.usableForYin).toBe(true)
    expect(result.isJianXiang).toBe(false)
  })

  it('每山两个旺相分金', () => {
    const usable = FENJIN_SLOTS.filter((slot) => slot.usableForYin)
    expect(usable).toHaveLength(48)
    for (const slot of usable) {
      expect(['丙', '丁', '庚', '辛']).toContain(slot.stem)
    }
    for (const name of ['子', '午', '卯', '酉', '乾', '坤']) {
      expect(suggestFenJinSlots(name)).toHaveLength(2)
    }
  })

  it('最近旺相分金按角距选择', () => {
    const slot = nearestUsableSlot(1.2)
    expect(slot.ganZhi).toBe('庚子')
    expect(Math.abs(angularDelta(1.2, slot.centerDeg))).toBeLessThan(2)
    expect(nearestUsableSlot(0).quality).toBe('WANG_XIANG')
  })

  it('空亡线提示', () => {
    expect(checkKongWangLine(0)).toBeNull()
    expect(checkKongWangLine(22.5)).toContain('空亡线')
    expect(checkKongWangLine(7.5)).toContain('两山交界')
  })

  it('兼向提示', () => {
    const result = resolveFenJin(5)
    expect(result.isJianXiang).toBe(true)
    expect(result.warning).toContain('兼向')
  })
})
