/**
 * 择日引擎审计回归。
 *
 * 每一条都对应一次真实审计发现：这些 bug 都不会让既有测试变红，
 * 因为既有测试断言的是「实现自洽」，而它们错在「口径与规格不符」。
 */

import { describe, expect, it } from 'vitest'
import type { ZeRiCategory } from '@core/types'
import { GAN_ELEMENT, ZHI_ELEMENT } from '@core/constants/nayin60'
import { contextFor, sanHeFrames, type DayFacts } from '@core/zeri/facts'
import { evaluateZhengWuXing } from '@core/zeri/packs/zhengwuxing'
import { evaluateSanHe } from '@core/zeri/packs/sanhe'
import { hexagramsCovering } from '@core/zeri/packs/xuankongDagua'
import { THREE_LUCKY_STARS } from '@core/zeri/tables/donggong'

function pillar(stem: string, branch: string) {
  return {
    ganZhi: `${stem}${branch}`,
    stem,
    branch,
    stemElement: GAN_ELEMENT[stem],
    branchElement: ZHI_ELEMENT[branch],
    nayin: '',
    nayinElement: '水' as const,
  }
}

type Pair = [stem: string, branch: string]

/** 显式构造日课：比「遍历日期找样本」可控，也不会因某年干支巧合而找不到。 */
function fakeFacts(p: { year: Pair; month: Pair; day: Pair; hour?: Pair }): DayFacts {
  const month = pillar(...p.month)
  return {
    date: '2026-01-01',
    monthBranch: month.branch,
    pillars: {
      year: pillar(...p.year),
      month,
      day: pillar(...p.day),
      hour: p.hour ? pillar(...p.hour) : null,
    },
  } as unknown as DayFacts
}

function ctxOf(category: ZeRiCategory, mountShan: string, dragon: string | null = null) {
  return contextFor({ category, mountShan, incomingDragon: dragon, eventYear: 2026 })
}

describe('三合局：完整局与半合必须分开', () => {
  it('三支齐现才算 complete', () => {
    const frames = sanHeFrames(['申', '子', '辰', '寅'])
    expect(frames[0].complete).toBe(true)
    expect(frames[0].element).toBe('水')
    expect(frames[0].hitCount).toBe(3)
  })

  it('两支为半合，missing 指出缺哪支', () => {
    const frames = sanHeFrames(['申', '子'])
    expect(frames[0].complete).toBe(false)
    expect(frames[0].hitCount).toBe(2)
    expect(frames[0].missing).toEqual(['辰'])
  })

  it('多组半合都在结果里，不因表顺序只留一个', () => {
    const frames = sanHeFrames(['申', '子', '寅', '午'])
    expect(frames.every((item) => !item.complete)).toBe(true)
    expect(frames.map((item) => item.element).sort()).toEqual(['水', '火'])
  })
})

describe('补龙：半合不得给满额分（规格「缺一为待」）', () => {
  it('半合时 scoreDelta 为 0 且 verdict 为「半合待成」', () => {
    // 申子寅：水局得申子（缺辰），火局只得寅（不足两支）
    const facts = fakeFacts({ year: ['丙', '申'], month: ['戊', '子'], day: ['甲', '寅'] })
    // 子龙正五行属水，与申子辰水局同气；旧逻辑会把半合判成「旺局 +2」
    const result = evaluateZhengWuXing(facts, ctxOf('YANG_DONGTU', '子', '子'))
    const buLong = result.subRules.find((rule) => rule.ruleId === 'ZWX_BU_LONG')!
    expect(buLong.verdict).toBe('半合待成')
    expect(buLong.scoreDelta).toBe(0)
    expect(buLong.reasons.join()).toContain('缺辰')
  })

  it('完整三合局仍给满额分', () => {
    const facts = fakeFacts({ year: ['丙', '申'], month: ['戊', '子'], day: ['庚', '辰'] })
    const result = evaluateZhengWuXing(facts, ctxOf('YANG_DONGTU', '子', '子'))
    const buLong = result.subRules.find((rule) => rule.ruleId === 'ZWX_BU_LONG')!
    expect(buLong.verdict).toBe('旺局')
    expect(buLong.scoreDelta).toBe(2)
  })

  it('与三合局无关时给「不成局」而不是静默留空', () => {
    // 子、午、卯分属三个不同的三合局，任何一局都只有一支
    const facts = fakeFacts({ year: ['甲', '子'], month: ['丙', '午'], day: ['乙', '卯'] })
    const result = evaluateZhengWuXing(facts, ctxOf('YANG_DONGTU', '子', '子'))
    const buLong = result.subRules.find((rule) => rule.ruleId === 'ZWX_BU_LONG')!
    expect(buLong.verdict).toBe('不成局')
    expect(buLong.scoreDelta).toBe(0)
  })
})

describe('扶山：无生无克不得伪装成比和', () => {
  it('四柱天干既非生扶、又非比和时记 0 分', () => {
    // 子山属水；甲乙木既非水之比和，也不生水。旧实现会落到 else 分支记 +1。
    const facts = fakeFacts({ year: ['甲', '寅'], month: ['乙', '卯'], day: ['甲', '辰'] })
    const result = evaluateZhengWuXing(facts, ctxOf('YANG_DONGTU', '子'))
    const fuShan = result.subRules.find((rule) => rule.ruleId === 'ZWX_FU_SHAN')!
    expect(fuShan.verdict).toBe('山课无生扶')
    expect(fuShan.scoreDelta).toBe(0)
  })

  it('确有同五行天干时才记比和', () => {
    const facts = fakeFacts({ year: ['壬', '寅'], month: ['癸', '卯'], day: ['甲', '辰'] })
    const result = evaluateZhengWuXing(facts, ctxOf('YANG_DONGTU', '子'))
    const fuShan = result.subRules.find((rule) => rule.ruleId === 'ZWX_FU_SHAN')!
    expect(fuShan.verdict).toBe('山课比和')
    expect(fuShan.scoreDelta).toBe(1)
  })
})

describe('三合包：完整局必须优先于表序更早的半合', () => {
  it('水局半合不得覆盖火局完整局', () => {
    // 日课地支申子寅戌；午山为火局锚点。水局先命中半合（申子），火局后成完整局（寅午戌）。
    const facts = fakeFacts({
      year: ['甲', '申'],
      month: ['丙', '子'],
      day: ['壬', '寅'],
      hour: ['庚', '戌'],
    })
    const result = evaluateSanHe(facts, ctxOf('YANG_DONGTU', '午'))
    const ju = result.subRules.find((rule) => rule.ruleId === 'SH_SAN_HE_JU')!
    expect(ju.verdict).toBe('成局')
    expect(ju.scoreDelta).toBe(2)
    expect(ju.reasons.join()).toContain('寅午戌')
  })
})

describe('玄空大卦：跨 0° 的卦覆盖区间不得为空', () => {
  it('0°/2°/358° 都能算出覆盖的卦', () => {
    for (const deg of [0, 2, 5, 355, 358, 359.9]) {
      expect(hexagramsCovering(deg).length, `${deg}° 覆盖为空`).toBeGreaterThan(0)
    }
  })

  it('子山 2° 的覆盖跨 0° 两侧', () => {
    const covered = hexagramsCovering(2)
    expect(covered).toContain(0)
    expect(covered).toContain(63)
  })

  it('不跨 0° 时仍是 3–4 卦（山宽 15°，每卦 5.625°）', () => {
    const covered = hexagramsCovering(180)
    expect(covered.length).toBeGreaterThanOrEqual(3)
    expect(covered.length).toBeLessThanOrEqual(4)
  })
})

describe('通关：单字偶见不算相战', () => {
  it('金木各一见时不判「金木相战」', () => {
    // 土4（戊辰、戊戌）、火2（丙午）、金1（庚）、木1（寅）
    const facts = fakeFacts({
      year: ['戊', '辰'],
      month: ['丙', '午'],
      day: ['庚', '寅'],
      hour: ['戊', '戌'],
    })
    const result = evaluateZhengWuXing(facts, ctxOf('YANG_DONGTU', '子'))
    const guan = result.subRules.find((rule) => rule.ruleId === 'ZWX_TONG_GUAN')!
    expect(guan.verdict).toBe('四柱不相战')
    expect(guan.scoreDelta).toBe(0)
    expect(guan.reasons.join()).not.toContain('金木相战')
  })

  it('两五行各见两次以上才算成势相战', () => {
    // 金2（庚、辛）、木2（寅、卯）
    const facts = fakeFacts({
      year: ['庚', '寅'],
      month: ['辛', '卯'],
      day: ['戊', '辰'],
      hour: ['戊', '戌'],
    })
    const result = evaluateZhengWuXing(facts, ctxOf('YANG_DONGTU', '子'))
    const guan = result.subRules.find((rule) => rule.ruleId === 'ZWX_TONG_GUAN')!
    expect(guan.reasons.join()).toContain('金木相战')
  })
})

describe('董公九星：三吉星不含立早', () => {
  it('三吉星恰为煞贡、直星、人专', () => {
    expect(THREE_LUCKY_STARS).toEqual(['煞贡', '直星', '人专'])
    expect(THREE_LUCKY_STARS).not.toContain('立早')
  })
})
