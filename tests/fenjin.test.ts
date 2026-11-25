import { describe, expect, it } from 'vitest'
import {
  FENJIN_SLOTS,
  checkKongWangLine,
  fenJinOfMountain,
  resolveFenJin,
} from '@/core/constants/fenjin120'

/**
 * 一百二十分金只承载几何与历法事实。
 *
 * 施工依据 v1.0 §6.8.1 与附录 E：外部方案按天干分的「旺相／孤虚／空亡」吉凶口径
 * 未经三源核验，不得进入数据结构。2026-11-26 已把该分类从 FenJinSlot 里拆除，
 * 这些用例锁住「只剩事实」的状态——有人把吉凶字段加回来时，这里会先红。
 */
describe('一百二十分金：只有几何与纳音事实', () => {
  it('共 120 格，每山 5 格，每格 3°', () => {
    expect(FENJIN_SLOTS).toHaveLength(120)
    for (const slot of FENJIN_SLOTS) {
      expect(slot.endDeg).not.toBe(slot.startDeg)
      expect(slot.slotNote).toMatch(/^[甲乙丙丁戊己庚辛壬癸]干·几何分格$/)
      // 纳音是完整名（如「海中金」），不是单个五行字
      expect(slot.nayin.length).toBeGreaterThanOrEqual(3)
    }
    expect(fenJinOfMountain('子')).toHaveLength(5)
  })

  it('分格里没有吉凶字段', () => {
    for (const slot of FENJIN_SLOTS) {
      const keys = Object.keys(slot).sort()
      expect(keys).toEqual(
        ['branch', 'centerDeg', 'element', 'endDeg', 'ganZhi', 'index', 'mount', 'nayin', 'slotNote', 'startDeg', 'stem', 'subIndex'],
      )
    }
  })

  it('子山五格排布', () => {
    const slots = fenJinOfMountain('子')
    expect(slots.map((slot) => slot.ganZhi)).toEqual(['甲子', '丙子', '戊子', '庚子', '壬子'])
    expect(slots.map((slot) => slot.centerDeg)).toEqual([354, 357, 0, 3, 6])
    expect(slots.map((slot) => slot.nayin)).toEqual([
      '海中金',
      '涧下水',
      '霹雳火',
      '壁上土',
      '桑柘木',
    ])
  })

  it('0° 落在戊子，几何事实可查', () => {
    const result = resolveFenJin(0)
    expect(result.slot.ganZhi).toBe('戊子')
    expect(result.slot.nayin).toBe('霹雳火')
    expect(result.isJianXiang).toBe(false)
    expect(result.warning).toBeNull()
  })

  it('3° 落在庚子', () => {
    const result = resolveFenJin(3)
    expect(result.slot.ganZhi).toBe('庚子')
    expect(result.isJianXiang).toBe(false)
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
