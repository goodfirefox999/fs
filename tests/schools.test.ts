import { describe, expect, it } from 'vitest'
import { evaluateDay } from '@/core/zeri/evaluate'
import { checkDasha, type DashaInput } from '@/core/zeri/dasha'
import { arbitrate } from '@/core/zeri/arbitrate'
import { JIAZI_60 } from '@/core/constants/nayin60'
import {
  THREE_LUCKY_STARS,
  dongGongStarOf,
  jiaZiIndex,
  monthGroupOf,
  nineStarTable,
} from '@/core/zeri/tables/donggong'
import { mountainGuiRenFang } from '@/core/zeri/tables/sanhe'
import { SHAN_NAMES } from '@/core/constants/shan24'
import { precessionDegForYear, xiuBoundsForYear } from '@/core/zeri/tables/xiu28'
import { KAI_XI_DU, GU_DU_TO_DEG } from '@/core/zeri/tables/xiu28'
import type { SchoolResult, DashaResult } from '@/core/zeri/types'

function baseDashaInput(patch: Partial<DashaInput> = {}): DashaInput {
  return {
    date: '2026-10-30',
    yearGanZhi: '丙午',
    yearStem: '丙',
    yearBranch: '午',
    monthBranch: '戌',
    dayBranch: '丑',
    dayGanZhi: '丁丑',
    hourBranch: null,
    mountShan: '乾',
    mountDeg: 315,
    subjectBranches: [],
    badGods: [],
    behavior: 'YI_AND_JI',
    category: 'YANG_DONGTU',
    xiu: '娄',
    lunarMonth: 9,
    lunarDay: 20,
    warnOnly: [],
    ...patch,
  }
}

describe('三合禄马贵人表', () => {
  it('二十四山贵人到方表全覆盖且非空', () => {
    for (const name of SHAN_NAMES) {
      const list = mountainGuiRenFang(name)
      expect(list, `${name}山缺贵人表`).not.toBeNull()
      expect(list?.length ?? 0).toBeGreaterThan(0)
      expect(list, `${name}山贵人不应含戊己所配`).not.toContain(undefined)
    }
  })
})

describe('董公九星值日', () => {
  const published: Record<string, Record<string, string[]>> = {
    MENG: {
      煞贡: ['丁卯', '丙子', '乙酉', '甲午', '癸卯', '壬子', '辛酉'],
      直星: ['戊辰', '丁丑', '丙戌', '乙未', '甲辰', '癸丑', '壬戌'],
      人专: ['辛未', '庚辰', '己丑', '戊戌', '丁未', '丙辰'],
    },
    ZHONG: {
      煞贡: ['丙寅', '乙亥', '甲申', '癸巳', '壬寅', '辛亥', '庚申'],
      直星: ['丁卯', '丙子', '乙酉', '甲午', '癸卯', '壬子', '辛酉'],
      人专: ['庚午', '己卯', '戊子', '丁酉', '丙午', '乙卯'],
    },
    JI: {
      煞贡: ['乙丑', '甲戌', '癸未', '壬辰', '辛丑', '庚戌', '己未'],
      直星: ['丙寅', '乙亥', '甲申', '癸巳', '壬寅', '辛亥', '庚申'],
      人专: ['己巳', '戊寅', '丁亥', '丙申', '乙巳', '甲寅', '癸亥'],
    },
  }

  it('六十甲子逐日展开与刊本三星归属完全一致', () => {
    for (const group of ['MENG', 'ZHONG', 'JI'] as const) {
      const table = nineStarTable(group)
      expect(table).toHaveLength(60)
      for (const star of THREE_LUCKY_STARS) {
        const actual = JIAZI_60.filter((_, index) => table[index] === star).sort()
        expect(actual, `${group} 组 ${star}`).toEqual(published[group][star].slice().sort())
      }
    }
  })

  it('同一干支日在不同月组属不同星（不存在脱离月份的固定表）', () => {
    expect(dongGongStarOf('寅', '丁卯')).toBe('煞贡')
    expect(dongGongStarOf('子', '丁卯')).toBe('直星')
    expect(dongGongStarOf('辰', '丁卯')).toBe('卜木')
    expect(monthGroupOf('寅')).toBe('MENG')
    expect(monthGroupOf('子')).toBe('ZHONG')
    expect(monthGroupOf('辰')).toBe('JI')
    expect(jiaZiIndex('丁卯')).toBe(3)
  })
})

describe('金神七煞与吉星不可覆盖前置层', () => {
  it('丙辛年庚辛日为天金神，命中即 reject', () => {
    const result = checkDasha(baseDashaInput({ dayBranch: '子', dayGanZhi: '庚子' }))
    expect(result.rejected).toBe(true)
    expect(result.hits.map((hit) => hit.ruleId)).toContain('D3_JIN_SHEN_QI_SHA')
  })

  it('丁壬年壬寅癸卯为地金神，同样进入排除', () => {
    const result = checkDasha(baseDashaInput({ yearStem: '丁', dayBranch: '寅', dayGanZhi: '壬寅' }))
    expect(result.hits.map((hit) => hit.ruleId)).toContain('D3_JIN_SHEN_QI_SHA')
  })

  it('甲己年午未申酉全式与坊间只取午未的差别保留在出处说明中', () => {
    const wu = checkDasha(baseDashaInput({ yearStem: '甲', yearBranch: '子', dayBranch: '午', dayGanZhi: '庚午' }))
    const shen = checkDasha(baseDashaInput({ yearStem: '甲', yearBranch: '子', dayBranch: '申', dayGanZhi: '壬申' }))
    expect(wu.hits.some((hit) => hit.ruleId === 'D3_JIN_SHEN_QI_SHA')).toBe(true)
    expect(shen.hits.some((hit) => hit.ruleId === 'D3_JIN_SHEN_QI_SHA')).toBe(true)
    const note = shen.hits.find((hit) => hit.ruleId === 'D3_JIN_SHEN_QI_SHA')
    expect(note?.source.title).toContain('董公')
  })

  it('煞贡值日也不能推翻大煞 reject', () => {
    const dasha: DashaResult = {
      rejected: true,
      hits: [
        {
          ruleId: 'D3_JIN_SHEN_QI_SHA',
          name: '金神七煞',
          reason: '天金神',
          appliesToCategory: true,
          source: { id: 'x', title: '《钦定协纪辨方书》卷三引《堪舆经》' },
          verification: 'unverified',
          needsHumanReview: true,
        },
      ],
      warned: [],
    }
    const schools: SchoolResult[] = [
      {
        school: 'DONG_GONG',
        schoolLabel: '董公',
        status: 'FULL',
        tendency: 'favorable',
        scoreDelta: 2,
        subRules: [],
        conflictFlags: [],
        needsHumanReview: true,
      },
    ]
    const result = arbitrate(schools, dasha, 'YIN_ANZANG')
    expect(result.consensus).toBe('rejected')
    expect(result.rejected).toBe(true)
    expect(result.consensusFavorable).toBe(false)
  })
})

describe('仲裁层冲突显式化', () => {
  it('两派倾向相反时保留双方原始输出并标记冲突', () => {
    const make = (school: SchoolResult['school'], label: string, tendency: SchoolResult['tendency'], ruleId: string): SchoolResult => ({
      school,
      schoolLabel: label,
      status: 'FULL',
      tendency,
      scoreDelta: tendency === 'favorable' ? 3 : -3,
      subRules: [
        {
          ruleId,
          name: ruleId,
          action: 'score',
          verdict: 'x',
          scoreDelta: tendency === 'favorable' ? 3 : -3,
          reasons: [],
          source: { id: ruleId, title: '测试' },
          verification: 'unverified',
          needsHumanReview: true,
        },
      ],
      conflictFlags: [],
      needsHumanReview: true,
    })
    const schools = [
      make('ZHENG_WU_XING', '正五行', 'favorable', 'ZWX_FU_SHAN'),
      make('XUAN_KONG_DA_GUA', '玄空大卦', 'unfavorable', 'XK_GUA_YUN_DANG_WANG'),
      make('SAN_HE', '三合', 'neutral', 'SH_SAN_HE_JU'),
    ]
    const result = arbitrate(schools, { rejected: false, hits: [], warned: [] }, 'YIN_ANZANG')
    expect(result.schoolResults).toHaveLength(3)
    expect(result.conflicts).toHaveLength(1)
    expect(result.conflicts[0].schools).toEqual(['ZHENG_WU_XING', 'XUAN_KONG_DA_GUA'])
    expect(result.conflicts[0].ruleIds).toContain('ZWX_FU_SHAN')
    expect(result.consensus).toBe('mixed')
    expect(result.weights[0].school).toBe('ZHENG_WU_XING')
    expect(result.weights[0].weight).toBe(5)
  })
})

describe('五派并列输出', () => {
  it('未犯大煞之日输出五派结果，每条规则均带出处与 unverified 状态', () => {
    const evaluation = evaluateDay({
      date: '2026-12-02',
      category: 'YIN_ANZANG',
      mountShan: '乾',
      eventYear: 2026,
      subjects: [{ date: '1970-06-01', gender: 'M' }],
    })
    expect(evaluation.dasha.rejected, evaluation.dasha.hits.map((h) => h.name).join('/')).toBe(false)
    expect(evaluation.schools.map((item) => item.school)).toEqual([
      'ZHENG_WU_XING',
      'SAN_HE',
      'DONG_GONG',
      'XUAN_KONG_DA_GUA',
      'TIAN_XING',
    ])
    for (const school of evaluation.schools) {
      for (const rule of school.subRules) {
        expect(rule.source.title, rule.ruleId).toBeTruthy()
        expect(rule.verification).toBe('unverified')
      }
    }
    expect(evaluation.schools.find((item) => item.school === 'TIAN_XING')?.status).toBe('PARTIAL')
    expect(evaluation.arbitration.weights).toHaveLength(5)
  })

  it('三煞占坐山直接排除，且不进入五派评分', () => {
    const evaluation = evaluateDay({
      date: '2026-12-03',
      category: 'YIN_ANZANG',
      mountShan: '子',
      eventYear: 2026,
    })
    expect(evaluation.schools).toHaveLength(0)
    expect(evaluation.arbitration.consensus).toBe('rejected')
    expect(evaluation.dasha.hits.map((hit) => hit.ruleId)).toContain('D3_YEAR_SAN_SHA_ON_MOUNTAIN')
  })

  it('未提供入首龙与时支时，相关规则显式标记数据缺口', () => {
    const evaluation = evaluateDay({
      date: '2026-12-02',
      category: 'YANG_RUZHAI',
      mountShan: '乾',
      eventYear: 2026,
    })
    const wuxing = evaluation.schools.find((item) => item.school === 'ZHENG_WU_XING')
    expect(wuxing?.subRules.find((rule) => rule.ruleId === 'ZWX_BU_LONG')?.dataGap).toContain('入首龙')
    expect(wuxing?.subRules.find((rule) => rule.ruleId === 'ZWX_TIAO_HOU')?.dataGap).toContain('时支')
    const dagua = evaluation.schools.find((item) => item.school === 'XUAN_KONG_DA_GUA')
    expect(dagua?.subRules.find((rule) => rule.ruleId === 'XK_GUA_QI_PEI_HE')?.dataGap).toContain('映射')
  })

  it('玄空大卦丁财分开输出', () => {
    const evaluation = evaluateDay({
      date: '2026-12-02',
      category: 'YANG_RUZHAI',
      mountShan: '乾',
      eventYear: 2026,
    })
    const dagua = evaluation.schools.find((item) => item.school === 'XUAN_KONG_DA_GUA')
    expect(dagua?.extras?.ding_score).toBeDefined()
    expect(dagua?.extras?.cai_score).toBeDefined()
    expect(dagua?.subRules.find((rule) => rule.ruleId === 'XK_CHOU_YAO_HUAN_XIANG')?.scoreDelta).toBe(0)
  })
})

describe('出处与校验状态约束', () => {
  const dates = ['2026-03-03', '2026-03-09', '2026-06-18', '2026-09-09', '2026-12-02', '2027-01-20']
  const categories = ['YANG_RUZHAI', 'YANG_DONGTU', 'YIN_ANZANG', 'YIN_XIUFEN'] as const

  it('所有规则与排除项都带出处，且校验状态一律为 unverified', () => {
    let seen = 0
    for (const date of dates) {
      for (const category of categories) {
        const e = evaluateDay({
          date,
          category,
          mountShan: '卯',
          eventYear: Number(date.slice(0, 4)),
          incomingDragon: '未',
          subjects: [{ date: '1988-05-05', gender: 'M' }],
          hourBranch: '午',
        })
        for (const hit of [...e.dasha.hits, ...e.dasha.warned]) {
          expect(hit.source.title, `${date} ${hit.ruleId}`).toBeTruthy()
          expect(hit.verification).toBe('unverified')
          seen++
        }
        for (const rule of e.schools.flatMap((school) => school.subRules)) {
          expect(rule.source.title, `${date} ${rule.ruleId}`).toBeTruthy()
          expect(rule.verification, rule.ruleId).toBe('unverified')
          seen++
        }
        // 被排除的日期不得留下任何流派评分
        if (e.dasha.rejected) expect(e.schools).toHaveLength(0)
      }
    }
    expect(seen).toBeGreaterThan(80)
  })

  it('源码中不存在把规则标为 verified_by_human 的写入路径', () => {
    const fs = require('node:fs')
    const path = require('node:path')
    const dir = path.resolve(process.cwd(), 'src/core/zeri')
    const files = fs.readdirSync(dir, { recursive: true }) as string[]
    const offenders = files
      .filter((name) => /\.(ts)$/.test(String(name)))
      .filter((name) => {
        const text = fs.readFileSync(path.join(dir, String(name)), 'utf8')
        return /verification:\s*'verified_by_human'/.test(text)
      })
    expect(offenders).toEqual([])
  })
})

describe('天星宿度与岁差', () => {
  it('开禧宿度合计 365.25 古度', () => {
    const total = KAI_XI_DU.reduce((sum, item) => sum + item.du, 0)
    expect(Number(total.toFixed(4))).toBe(365.25)
    expect(GU_DU_TO_DEG).toBeCloseTo(0.98563, 5)
  })

  it('按用事年做岁差平移，校正前后宿界不同', () => {
    const epoch = xiuBoundsForYear(1204)
    const now = xiuBoundsForYear(2026)
    expect(epoch[0].start).toBeCloseTo(0, 6)
    expect(precessionDegForYear(2026)).toBeGreaterThan(11.3)
    expect(precessionDegForYear(2026)).toBeLessThan(11.6)
    expect(Math.abs(now[0].start - epoch[0].start)).toBeGreaterThan(11)
    expect(now[7].name).toBe('斗')
  })
})
