import { describe, expect, it } from 'vitest'
import {
  DOU_SHOU_ELEMENT,
  FANHUA,
  HUAQI_ELEMENT,
  douShouSummary,
  evaluateDouShou,
} from '@/core/zeri/packs/doushou'
import { evaluateDay } from '@/core/zeri/evaluate'
import type { DayFacts, ZeriContext } from '@/core/zeri/facts'
import { SHAN_NAMES } from '@/core/constants/shan24'

/** 只造 evaluateDouShou 用到的字段，其余留空——避免用真实日课掩盖查表错误。 */
function stubFacts(stems: [string, string, string, string | null], monthBranch: string): DayFacts {
  const p = (stem: string) => ({ stem })
  return {
    monthBranch,
    pillars: {
      year: p(stems[0]),
      month: p(stems[1]),
      day: p(stems[2]),
      hour: stems[3] ? p(stems[3]) : null,
    },
  } as unknown as DayFacts
}

const ctx = { mountShan: '乾' } as unknown as ZeriContext

describe('斗首五行表', () => {
  it('覆盖二十四山，且分布为 土6/火6/木4/水4/金4', () => {
    expect(Object.keys(DOU_SHOU_ELEMENT).sort()).toEqual([...SHAN_NAMES].sort())
    const dist: Record<string, number> = {}
    for (const el of Object.values(DOU_SHOU_ELEMENT)) dist[el] = (dist[el] ?? 0) + 1
    expect(dist).toEqual({ 土: 6, 火: 6, 木: 4, 水: 4, 金: 4 })
  })

  it('斗首五行 ≠ 正五行（甲山属水、子山属土）', () => {
    expect(DOU_SHOU_ELEMENT['甲']).toBe('水')
    expect(DOU_SHOU_ELEMENT['子']).toBe('土')
    expect(DOU_SHOU_ELEMENT['壬']).toBe('土')
  })

  it('化气取五运，与五合无关', () => {
    expect(HUAQI_ELEMENT['甲']).toBe('土')
    expect(HUAQI_ELEMENT['己']).toBe('土')
    expect(HUAQI_ELEMENT['乙']).toBe('金')
    expect(HUAQI_ELEMENT['丙']).toBe('水')
    expect(HUAQI_ELEMENT['丁']).toBe('木')
    expect(HUAQI_ELEMENT['戊']).toBe('火')
  })

  it('番化诀五步闭环', () => {
    expect(FANHUA['元辰']).toBe('元辰')
    expect(FANHUA['武财']).toBe('贪官')
    expect(FANHUA['贪官']).toBe('破鬼')
    expect(FANHUA['破鬼']).toBe('廉子')
    expect(FANHUA['廉子']).toBe('武财')
  })
})

describe('斗首五星定位', () => {
  it('乾山属火：丁化木生我→贪狼、辛化水克我→破军、乙化金我克→武曲', () => {
    const r = evaluateDouShou(stubFacts(['丁', '丁', '辛', '乙'], '未'), ctx)
    expect(r.shanElement).toBe('火')
    expect(r.stems.map((s) => s.star)).toEqual(['贪狼', '贪狼', '破军', '武曲'])
    expect(r.stems.map((s) => s.alias)).toEqual(['贪官', '贪官', '破鬼', '武财'])
    expect(r.counts).toEqual({ 元辰: 0, 贪狼: 2, 廉贞: 0, 武曲: 1, 破军: 1 })
    expect(r.sanyuan).toBe(false)
    expect(r.sanwu).toBe(false)
  })

  it('同我者为元辰，三见即三元格', () => {
    const r = evaluateDouShou(stubFacts(['戊', '癸', '戊', '癸'], '午'), ctx)
    expect(r.stems.map((s) => s.star)).toEqual(['元辰', '元辰', '元辰', '元辰'])
    expect(r.counts.元辰).toBe(4)
    expect(r.sanyuan).toBe(true)
  })

  it('我克者为武财，三见即三武格', () => {
    const r = evaluateDouShou(stubFacts(['乙', '庚', '乙', '戊'], '午'), ctx)
    expect(r.counts.武曲).toBe(3)
    expect(r.sanwu).toBe(true)
  })

  it('我生者为廉贞', () => {
    const r = evaluateDouShou(stubFacts(['甲', '己', '甲', '己'], '午'), ctx)
    expect(r.stems.map((s) => s.star)).toEqual(['廉贞', '廉贞', '廉贞', '廉贞'])
  })

  it('未给时柱时不臆造第四干', () => {
    const r = evaluateDouShou(stubFacts(['丁', '丁', '辛', null], '未'), ctx)
    expect(r.stems).toHaveLength(4)
    expect(r.stems[3].star).toBeNull()
    expect(r.stems[3].gan).toBe('')
  })

  it('坐山不在表内时整层降级，不静默通过', () => {
    const r = evaluateDouShou(stubFacts(['甲', '乙', '丙', '丁'], '子'), {
      mountShan: '?',
    } as unknown as ZeriContext)
    expect(r.shanElement).toBeNull()
    expect(r.stems.every((s) => s.star === null)).toBe(true)
    expect(douShouSummary(r)).toContain('不在斗首五行表内')
  })
})

describe('斗首得位', () => {
  it('木长生在亥：寅月临官得位、辰月衰不得位', () => {
    const dewei = evaluateDouShou(stubFacts(['丁', '甲', '乙', '丙'], '寅'), ctx)
    expect(dewei.stems[0].huaqi).toBe('木')
    expect(dewei.stems[0].stage).toBe('临官')
    expect(dewei.stems[0].dewei).toBe(true)

    const notDewei = evaluateDouShou(stubFacts(['丁', '甲', '乙', '丙'], '辰'), ctx)
    expect(notDewei.stems[0].stage).toBe('衰')
    expect(notDewei.stems[0].dewei).toBe(false)
  })

  it('口径声明里写明土长生两说', () => {
    const r = evaluateDouShou(stubFacts(['甲', '甲', '甲', '甲'], '申'), ctx)
    expect(r.reviewNotes.join(' ')).toContain('土寄坤')
  })
})

describe('接入日评估', () => {
  it('五派输出不变，斗首单列且不参与仲裁权重', () => {
    const evaluation = evaluateDay({
      date: '2026-12-02',
      category: 'YIN_ANZANG',
      mountShan: '乾',
      eventYear: 2026,
      subjects: [{ date: '1970-06-01', gender: 'M' }],
    })
    expect(evaluation.arbitration.weights).toHaveLength(5)
    expect(evaluation.schools.map((s) => s.school)).not.toContain('DOU_SHOU')
    expect(evaluation.doushou.shanElement).toBe('火')
    expect(evaluation.doushou.stems).toHaveLength(4)
  })
})
