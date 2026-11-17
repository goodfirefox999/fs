import { describe, expect, it } from 'vitest'
import oracle from './fixtures/xieji-oracle.json'
import { analyzeDay } from '@/core/engines/shensha'

const rows = oracle.days

describe('《钦定协纪辨方书》起例与 cnlunar 交叉校验', () => {
  it('岁德随年干与日干（丙午年丙日）', () => {
    const suide = analyzeDay('2026-05-02')
    expect(suide.yearGanZhi).toBe('丙午')
    expect(suide.dayGanZhi).toBe('丙子')
    expect(suide.good).toContain('岁德')
    expect(suide.good).not.toContain('岁德合')
    const suideHe = analyzeDay('2026-05-07')
    expect(suideHe.dayGanZhi).toBe('辛巳')
    expect(suideHe.good).toContain('岁德合')
    expect(suideHe.good).not.toContain('岁德')
  })

  it('夹具覆盖 730 天', () => {
    expect(rows).toHaveLength(730)
  })

  it('月支、日干支、建除十二值一致', () => {
    for (const row of rows) {
      const result = analyzeDay(row.date)
      expect(result.monthBranch, `${row.date} 月支`).toBe(row.mb)
      expect(result.dayGanZhi, `${row.date} 日干支`).toBe(row.dgz)
      expect(result.zhiXing, `${row.date} 建除`).toBe(row.zx)
    }
  })

  it('移植神煞命中集合一致', () => {
    const diffs: string[] = []
    for (const row of rows) {
      const result = analyzeDay(row.date)
      // 土王用事：本仓库从「四立前十八日」，cnlunar 少一日
      // 岁德/岁德合：cnlunar 的立春年柱校正在 11–1 月会早翻一年，年柱口径以本仓库为准
      const drop = (list: string[]) =>
        list.filter((name) => name !== '土王用事' && name !== '岁德' && name !== '岁德合')
      const mine = drop([...result.good, ...result.bad]).sort().join(',')
      const expected = drop(row.gods).sort().join(',')
      if (mine !== expected) diffs.push(`${row.date} 期望[${expected}] 实得[${mine}]`)
    }
    expect(diffs.slice(0, 8), `神煞差异 ${diffs.length} 天`).toEqual([])
  })

  it('宜忌等第等级一致', () => {
    const diffs: string[] = []
    for (const row of rows) {
      const result = analyzeDay(row.date)
      if (result.level !== row.lv) diffs.push(`${row.date} 期望${row.lv} 实得${result.level}`)
    }
    expect(diffs.slice(0, 8), `等第差异 ${diffs.length} 天`).toEqual([])
  })
})
