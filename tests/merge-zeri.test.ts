/**
 * mergeZeRiResults 单元测试：择日页分片计算的合并语义锁。
 *
 * 小程序择日页把长窗口切成 15 天一片分帧计算（低端机不再整段冻结主线程），
 * 本测试锁定合并语义：计数器求和、items 日期序拼接并按展示上限截断、
 * rejections 按名称聚合、notes 重建汇总行且固定说明不重复不丢失。
 */
import { describe, expect, it } from 'vitest'
import { mergeZeRiResults } from '@core/engines/zeri'
import type { ZeRiItem, ZeRiRejection, ZeRiResult } from '@core/types'

function item(solar: string): ZeRiItem {
  // merge 只按 solarDate 排序，其余字段构造最小占位
  return { solarDate: solar } as unknown as ZeRiItem
}

function rejection(name: string, count: number, lucky = 0): ZeRiRejection {
  return {
    name,
    count,
    review: false,
    source: '《协纪辨方书》',
    luckyStarDays: lucky,
    luckyStarSamples: Array.from({ length: count }, (_, i) => `样本${name}${i}`),
    guidance: `${name} 的解释文案`,
  }
}

function part(opts: {
  scanned: number
  rejected: number
  unmatched: number
  eligible: number
  items: ZeRiItem[]
  rejections: ZeRiRejection[]
  almanac?: number
  huangdao?: number
  xiu?: number
}): ZeRiResult {
  return {
    items: opts.items,
    scanned: opts.scanned,
    rejected: opts.rejected,
    unmatched: opts.unmatched,
    eligible: opts.eligible,
    truncated: opts.eligible > opts.items.length,
    excludedByAlmanac: opts.almanac ?? 0,
    excludedByHuangDao: opts.huangdao ?? 0,
    excludedByXiu: opts.xiu ?? 0,
    rejections: opts.rejections,
    notes: [
      `筛选范围：占位 起 ${opts.scanned} 天，用途为占位。`,
      '固定说明甲（各片一致）。',
      `本次完整扫描 ${opts.scanned} 天：占位 ${opts.rejected} 天。`,
      '固定说明乙（各片一致）。',
    ],
  }
}

const OPTS = {
  displayLimit: 5,
  startDate: '2027-01-01',
  daysCount: 30,
  category: '修造' as ZeRiCategory,
}

describe('mergeZeRiResults：分片合并语义', () => {
  it('计数器求和；items 跨片日期序拼接并按展示上限截断', () => {
    const p1 = part({
      scanned: 15, rejected: 5, unmatched: 4, eligible: 6, almanac: 2, huangdao: 1, xiu: 1,
      items: [item('2027-01-01'), item('2027-01-03'), item('2027-01-08')],
      rejections: [rejection('岁破', 5, 2)],
    })
    const p2 = part({
      scanned: 15, rejected: 3, unmatched: 6, eligible: 6, almanac: 1, huangdao: 2, xiu: 3,
      items: [item('2027-01-16'), item('2027-01-20')],
      rejections: [rejection('岁破', 3, 1), rejection('往亡', 3)],
    })
    const merged = mergeZeRiResults([p1, p2], OPTS)

    expect(merged.scanned).toBe(30)
    expect(merged.rejected).toBe(8)
    expect(merged.unmatched).toBe(10)
    expect(merged.eligible).toBe(12)
    expect(merged.excludedByAlmanac).toBe(3)
    expect(merged.excludedByHuangDao).toBe(3)
    expect(merged.excludedByXiu).toBe(4)
    expect(merged.items.map((i) => i.solarDate)).toEqual([
      '2027-01-01', '2027-01-03', '2027-01-08', '2027-01-16', '2027-01-20',
    ])
    expect(merged.truncated).toBe(true)
    // rejections 按名称聚合、按 count 降序
    expect(merged.rejections[0].name).toBe('岁破')
    expect(merged.rejections[0].count).toBe(8)
    expect(merged.rejections[0].luckyStarDays).toBe(3)
    expect(merged.rejections[1].name).toBe('往亡')
  })

  it('notes：范围行/汇总行用合并数字重建，固定说明保留且不重复', () => {
    const p1 = part({
      scanned: 15, rejected: 5, unmatched: 4, eligible: 6,
      items: [item('2027-01-01')], rejections: [rejection('岁破', 5)],
    })
    const p2 = part({
      scanned: 15, rejected: 3, unmatched: 6, eligible: 6,
      items: [item('2027-01-16')], rejections: [rejection('岁破', 3)],
    })
    const merged = mergeZeRiResults([p1, p2], OPTS)

    const scope = merged.notes.filter((n) => n.startsWith('筛选范围：'))
    const summary = merged.notes.filter((n) => n.startsWith('本次完整扫描 '))
    const empty = merged.notes.filter((n) => n.startsWith('当前条件下无候选日'))
    expect(scope).toEqual(['筛选范围：2027-01-01 起 30 天，用途为修造。'])
    expect(summary).toHaveLength(1)
    expect(summary[0]).toContain('30 天')
    expect(summary[0]).toContain('8 天')
    expect(summary[0]).toContain('12 天')
    expect(empty).toHaveLength(0)
    const fixed = merged.notes.filter((n) => n.includes('固定说明'))
    expect(fixed).toHaveLength(2)
  })

  it('全部被排除时置顶主因说明（数字用合并值）', () => {
    const p = part({
      scanned: 15, rejected: 15, unmatched: 0, eligible: 0,
      items: [], rejections: [rejection('岁破', 15)],
    })
    const merged = mergeZeRiResults([p], OPTS)
    expect(merged.notes[0].startsWith('当前条件下无候选日')).toBe(true)
    expect(merged.notes[0]).toContain('15/15')
    expect(merged.items).toHaveLength(0)
  })

  it('单片输入语义不变（分片退化为单片的兼容路径）', () => {
    const p = part({
      scanned: 10, rejected: 2, unmatched: 3, eligible: 2,
      items: [item('2027-01-02'), item('2027-01-05')],
      rejections: [rejection('岁破', 2)],
    })
    const merged = mergeZeRiResults([p], OPTS)
    expect(merged.scanned).toBe(10)
    expect(merged.eligible).toBe(2)
    expect(merged.truncated).toBe(false)
    expect(merged.rejections).toHaveLength(1)
  })
})
