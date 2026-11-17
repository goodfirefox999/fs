/**
 * 择日评估主流程：Layer 1–2 事实 → Layer 3 大煞排除 → 五派并列评分 → Layer 5 仲裁。
 * reject 命中后不再进入评分，但排除原因原样保留。
 */
import type { BirthInfo, SanShaLevel, ZeRiCategory } from '../types'
import { effectiveYearOfBirth, ganZhiOfYear } from '../utils/date'
import { nayinOfGanZhi } from '../constants/nayin60'
import { buildFacts, contextFor, type SubjectInfo, type ZeriContext } from './facts'
import {
  ALWAYS_WARN_DASHA,
  FOLK_DASHA_RULE_IDS,
  checkDasha,
  defaultSanShaLax,
  type DashaInput,
} from './dasha'
import { arbitrate } from './arbitrate'
import { SCHOOL_EVALUATORS } from './registry'
import { evaluateDouShou, type DouShouResult } from './packs/doushou'
import type { ArbitrationResult, DashaResult, SchoolResult } from './types'
import { SCHOOL_IDS } from './types'

export interface DayEvaluationInput {
  date: string
  category: ZeRiCategory
  mountShan: string
  sittingDeg?: number
  eventYear: number
  incomingDragon?: string | null
  /** 主命（在世主事者），用于相主与冲命 */
  subjects?: BirthInfo[]
  /** 仙命，仅参与冲命排除，不参与相主评分 */
  deceased?: BirthInfo[]
  hourBranch?: string | null
  sanShaPolicy?: SanShaLevel
  chongSangPolicy?: 'reject' | 'warn'
  includesConstruction?: boolean
  /** 金神七煞与民俗类神煞（受死/四废/往亡/大败/十恶大败）可降级为提示 */
  jinShenPolicy?: 'reject' | 'warn'
  folkPolicy?: 'reject' | 'warn'
  yaoOrder?: 'ASC' | 'DESC'
  longitudeDeg?: number | null
  /** 直接指定降级的规则 id，优先级高于上面的开关 */
  warnOnly?: string[]
}

export interface DayEvaluation {
  date: string
  facts: ReturnType<typeof buildFacts>
  context: ZeriContext
  dasha: DashaResult
  schools: SchoolResult[]
  arbitration: ArbitrationResult
  /**
   * 斗首参考层：与五派并列展示，但**不进仲裁权重、不改 consensus**。
   * 吉凶强度未考证（贪狼/廉贞各本不一），故只给星名与生克，不给合议结论。
   */
  doushou: DouShouResult
}

export function subjectInfoOf(label: string, birth: BirthInfo): SubjectInfo | null {
  try {
    const year = effectiveYearOfBirth(birth)
    const ganZhi = ganZhiOfYear(year)
    const nayin = nayinOfGanZhi(ganZhi)
    return {
      label,
      yearGanZhi: ganZhi,
      stem: ganZhi[0],
      branch: ganZhi[1],
      nayinElement: nayin.element,
    }
  } catch {
    return null
  }
}

/**
 * 「民俗神煞硬排除」开关覆盖的条目：民俗口径全集去掉
 * 受死（官书从删，恒为提示）与重丧（口诀两系并存，另有独立开关）。
 */
const FOLK_DASHA = FOLK_DASHA_RULE_IDS.filter(
  (id) => !ALWAYS_WARN_DASHA.includes(id) && id !== 'D3_CHONG_SANG',
)

function defaultWarnOnly(input: DayEvaluationInput): string[] {
  const list: string[] = []
  // 三煞分六条（年/月/日/时占山 + 日课相犯两条）：默认降级哪些层级由 defaultSanShaLax 按
  // 「是否兴工 + 所选层级」给出；层级为「整层」时返回空列表，即六条全部按排除处理。
  list.push(
    ...defaultSanShaLax(
      input.category,
      input.includesConstruction ?? false,
      input.sanShaPolicy ?? 'year_month',
    ),
  )
  if (input.chongSangPolicy === 'warn') list.push('D3_CHONG_SANG')
  if (input.jinShenPolicy === 'warn') list.push('D3_JIN_SHEN_QI_SHA')
  if (input.folkPolicy === 'warn') list.push(...FOLK_DASHA)
  return Array.from(new Set(list))
}

export function evaluateDay(input: DayEvaluationInput): DayEvaluation {
  const facts = buildFacts(input.date, input.hourBranch ?? null)
  const subjectInfos = (input.subjects ?? [])
    .map((birth, index) => subjectInfoOf(`主命${index + 1}`, birth))
    .filter(Boolean) as SubjectInfo[]
  const deceasedInfos = (input.deceased ?? [])
    .map((birth, index) => subjectInfoOf(`仙命${index + 1}`, birth))
    .filter(Boolean) as SubjectInfo[]

  const ctx = contextFor({
    category: input.category,
    mountShan: input.mountShan,
    incomingDragon: input.incomingDragon ?? null,
    subjects: subjectInfos,
    hourBranch: input.hourBranch ?? null,
    includesConstruction: input.includesConstruction ?? false,
    sittingDeg: input.sittingDeg,
    eventYear: input.eventYear,
    yaoOrder: input.yaoOrder ?? 'ASC',
    longitudeDeg: input.longitudeDeg ?? null,
  })

  const dashaInput: DashaInput = {
    date: input.date,
    yearGanZhi: facts.pillars.year.ganZhi,
    yearStem: facts.pillars.year.stem,
    yearBranch: facts.pillars.year.branch,
    monthBranch: facts.monthBranch,
    dayBranch: facts.pillars.day.branch,
    dayGanZhi: facts.pillars.day.ganZhi,
    hourBranch: facts.pillars.hour?.branch ?? null,
    mountShan: ctx.mountShan,
    mountDeg: ctx.sittingDeg,
    subjectBranches: [...subjectInfos, ...deceasedInfos].map((item) => ({
      label: item.label,
      branch: item.branch,
    })),
    badGods: facts.shensha.bad,
    behavior: facts.shensha.behavior,
    category: input.category,
    includesConstruction: input.includesConstruction ?? false,
    xiu: facts.xiu,
    lunarMonth: facts.lunarMonth,
    lunarDay: facts.lunarDay,
    warnOnly: input.warnOnly ?? defaultWarnOnly(input),
  }
  const dasha = checkDasha(dashaInput)

  // reject 优先级最高：命中大煞的日期不进入五派评分
  const schools: SchoolResult[] = dasha.rejected
    ? []
    : SCHOOL_IDS.map((id) => SCHOOL_EVALUATORS[id](facts, ctx))

  return {
    date: input.date,
    facts,
    context: ctx,
    dasha,
    schools,
    arbitration: arbitrate(schools, dasha, input.category),
    doushou: evaluateDouShou(facts, ctx),
  }
}
