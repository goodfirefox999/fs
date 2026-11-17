import type { ThingBehavior, ZeRiCategory } from '../types'
import { GAN, ZHI, ZHI_CLASH } from '../constants/nayin60'
import {
  BAD_GOD_LEVEL_TABLE,
  MONTH_BRANCHES,
  BEHAVIOR_LABELS,
  CATEGORY_XIEJI_TERMS,
  DE_GODS,
  LEVEL_NAMES,
  TIAN_DEH_BY_MONTH,
  XIEJI_GODS,
  ZHONG_MONTHS,
  behaviorOf,
  type GodLuck,
  type XieJiGod,
} from '../constants/xieji'
import {
  daysToNextSiLi,
  monthBranchForDate,
  seasonIndexOf,
  solarOf,
  yearGanZhiForDate,
  zhiXingForDate,
} from '../utils/date'

export interface DayGodHit {
  name: string
  luck: GodLuck
  yi: string[]
  ji: string[]
}

export interface DayShensha {
  date: string
  yearGanZhi: string
  monthBranch: string
  dayGanZhi: string
  zhiXing: string
  season: number
  gods: DayGodHit[]
  good: string[]
  bad: string[]
  level: number
  levelName: string
  behavior: ThingBehavior
  behaviorLabel: string
  isDe: boolean
  jiGods: Array<{ name: string; terms: string[] }>
  yiGods: Array<{ name: string; terms: string[] }>
  jiCategories: ZeRiCategory[]
  yiCategories: ZeRiCategory[]
}

function intersects(list: string[], candidates: string[]): string[] {
  return candidates.filter((item) => list.includes(item))
}

function matchesGod(
  god: XieJiGod,
  ctx: { monthIndex: number; season: number; yearStemIndex: number; dayStem: string; dayBranch: string; dayGanZhi: string; siLiWait: number }
): boolean {
  if (god.source === 'SI_LI_WAIT') {
    const limit = Number(god.table[0])
    return ctx.siLiWait >= 1 && ctx.siLiWait <= limit
  }
  if (god.source === 'BRANCH_SET') return god.table.includes(ctx.dayBranch)
  if (god.source === 'MONTH_SELF') return ctx.dayBranch === MONTH_BRANCHES[ctx.monthIndex]
  if (god.source === 'DAY_LIST') return god.table.includes(ctx.dayGanZhi)

  const index = god.source === 'SEASON' ? ctx.season : god.source === 'YEAR_STEM' ? ctx.yearStemIndex : ctx.monthIndex
  const value = god.table[index]
  if (value === undefined || value === '空') return false
  if (god.match === 'GANZHI') return value.split(' ').includes(ctx.dayGanZhi)
  if (god.match === 'IN_GANZHI') return value.includes(ctx.dayStem) || value.includes(ctx.dayBranch)
  if (god.match === 'STEM') return value === ctx.dayStem
  return value === ctx.dayBranch
}

function matchesTianDeh(monthBranch: string, dayStem: string, dayBranch: string): boolean {
  const value = TIAN_DEH_BY_MONTH[MONTH_BRANCHES.indexOf(monthBranch)]
  if (!value) return false
  return ZHONG_MONTHS.includes(monthBranch)
    ? value.includes(dayBranch)
    : value.includes(dayStem)
}

export function analyzeDay(date: string): DayShensha {
  const solar = solarOf(date)
  const lunar = solar.getLunar()
  const monthBranch = monthBranchForDate(date)
  const monthIndex = MONTH_BRANCHES.indexOf(monthBranch)
  const season = seasonIndexOf(monthBranch)
  const dayGanZhi = lunar.getDayInGanZhi()
  const dayStem = dayGanZhi[0]
  const dayBranch = dayGanZhi[1]
  const yearGanZhi = yearGanZhiForDate(date)
  const zhiXing = zhiXingForDate(date)
  const siLiWait = daysToNextSiLi(date)

  const ctx = {
    monthIndex,
    season,
    yearStemIndex: GAN.indexOf(yearGanZhi[0] as (typeof GAN)[number]),
    dayStem,
    dayBranch,
    dayGanZhi,
    siLiWait,
  }

  const gods: DayGodHit[] = []
  if (matchesTianDeh(monthBranch, dayStem, dayBranch)) {
    gods.push({ name: '天德', luck: 'GOOD', yi: ['修造', '营建', '搬移', '安葬', '求医'], ji: [] })
  }
  for (const god of XIEJI_GODS) {
    if (matchesGod(god, ctx)) {
      gods.push({ name: god.name, luck: god.luck, yi: god.yi, ji: god.ji })
    }
  }
  if (dayBranch === monthBranch) gods.push({ name: '月建', luck: 'BAD', yi: [], ji: [] })
  if (dayBranch === ZHI_CLASH[monthBranch]) gods.push({ name: '月破', luck: 'BAD', yi: [], ji: [] })

  const good = gods.filter((item) => item.luck === 'GOOD').map((item) => item.name)
  const bad = gods.filter((item) => item.luck === 'BAD').map((item) => item.name)

  // 宜忌等第：凶煞或建除值 + 同日并见之神 + 月支范围
  const pool = [...good, ...bad, `${zhiXing}日`]
  let level = -1
  for (const name of pool) {
    const rules = BAD_GOD_LEVEL_TABLE[name]
    if (!rules) continue
    for (const [branches, coGods, value] of rules) {
      if (!branches.includes(monthBranch)) continue
      if (coGods.some((coGod) => pool.includes(coGod)) && value > level) level = value
    }
  }

  const isDe = good.some((name) => DE_GODS.includes(name))
  const behavior = behaviorOf(level, isDe)

  const jiGods: Array<{ name: string; terms: string[] }> = []
  const yiGods: Array<{ name: string; terms: string[] }> = []
  const jiCategories = new Set<ZeRiCategory>()
  const yiCategories = new Set<ZeRiCategory>()
  for (const [category, terms] of Object.entries(CATEGORY_XIEJI_TERMS) as Array<[ZeRiCategory, string[]]>) {
    for (const god of gods) {
      const matched = intersects(god.luck === 'BAD' ? god.ji : god.yi, terms)
      if (!matched.length) continue
      if (god.luck === 'BAD') {
        jiCategories.add(category)
        const known = jiGods.find((item) => item.name === god.name)
        if (known) known.terms = matched
        else jiGods.push({ name: god.name, terms: matched })
      } else {
        yiCategories.add(category)
        const known = yiGods.find((item) => item.name === god.name)
        if (known) known.terms = matched
        else yiGods.push({ name: god.name, terms: matched })
      }
    }
  }

  return {
    date,
    yearGanZhi,
    monthBranch,
    dayGanZhi,
    zhiXing,
    season,
    gods,
    good,
    bad,
    level,
    levelName: LEVEL_NAMES[level] ?? LEVEL_NAMES[-1],
    behavior,
    behaviorLabel: BEHAVIOR_LABELS[behavior],
    isDe,
    jiGods,
    yiGods,
    jiCategories: Array.from(jiCategories),
    yiCategories: Array.from(yiCategories),
  }
}

/** 用事类别在通书宜忌术语中的命中项 */
export function categoryTermMatch(category: ZeRiCategory, list: string[]): string[] {
  return intersects(CATEGORY_XIEJI_TERMS[category], list)
}
