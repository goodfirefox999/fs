/**
 * Layer 1–2：预处理与历法事实层。
 * 只产出可核验的「事实」，不产出吉凶结论；五派规则包只能读这里的字段。
 */
import type { FiveElement, ZeRiCategory } from '../types'
import {
  ELEMENT_KE,
  ELEMENT_SHENG,
  GAN,
  GAN_ELEMENT,
  ZHI,
  ZHI_CLASH,
  ZHI_ELEMENT,
  nayinOfGanZhi,
} from '../constants/nayin60'
import { branchOfMountain, getMountain, oppositeMountain } from '../constants/shan24'
import type { MountainMeta } from '../constants/shan24'
import { analyzeDay, type DayShensha } from '../engines/shensha'
import { monthIndexFromZhi, solarOf, weekdayLabel } from '../utils/date'
import { solarLongitude } from '../astro/solar'

export interface Pillar {
  ganZhi: string
  stem: string
  branch: string
  stemElement: FiveElement
  branchElement: FiveElement
  nayin: string
  nayinElement: FiveElement
}

export interface DayFacts {
  date: string
  weekDay: string
  lunarText: string
  lunarMonth: number
  lunarDay: number
  isLunarLeapMonth: boolean
  pillars: {
    year: Pillar
    month: Pillar
    day: Pillar
    hour: Pillar | null
  }
  /** 节气月序：寅=1 … 丑=12 */
  monthIndex: number
  monthBranch: string
  season: number
  solarTerm: string | null
  zhiXing: string
  tianShen: string
  tianShenType: string
  tianShenLuck: string
  xiu: string
  xiuLuck: string
  pengZu: string[]
  jiShen: string[]
  xiongSha: string[]
  almanacYi: string[]
  almanacJi: string[]
  chongDesc: string
  chongShengXiao: string
  sha: string
  positions: {
    xi: string
    cai: string
    fu: string
    yangGui: string
    yinGui: string
    tai: string
  }
  /** 当日黄道吉时（时辰名） */
  luckyHours: string[]
  shensha: DayShensha
}

export interface SubjectInfo {
  label: string
  yearGanZhi: string
  branch: string
  stem: string
  nayinElement: FiveElement
}

export interface ZeriContext {
  category: ZeRiCategory
  /** 坐山（二十四山名） */
  mountShan: string
  mountMeta: MountainMeta
  facingMeta: MountainMeta
  /** 入首龙（阴宅用事；未采集时为 null，补龙规则将标记数据缺口） */
  incomingDragon: MountainMeta | null
  /** 主命/仙命列表 */
  subjects: SubjectInfo[]
  /** 日课时支；未指定时时柱相关规则跳过 */
  hourBranch: string | null
  /** 入宅是否伴随动土、修造、安门；为真时按兴工类恢复三煞占山等硬排除 */
  includesConstruction: boolean
  /** 坐山实际线度（用于玄空大卦抽爻与三煞占山判定） */
  sittingDeg: number
  /** 用事年份（玄空大卦按阳爻 9 年 / 阴爻 6 年的元运表取运，不用每运 20 年简化） */
  eventYear: number
  /** 玄空大卦爻位排列口径，流派分歧必须显式声明 */
  yaoOrder: 'ASC' | 'DESC'
  /** 真太阳时校正所需的经度（缺省不校正） */
  longitudeDeg: number | null
}

const HOUR_NAMES: Record<string, string> = {
  子: '子时(23-01)',
  丑: '丑时(01-03)',
  寅: '寅时(03-05)',
  卯: '卯时(05-07)',
  辰: '辰时(07-09)',
  巳: '巳时(09-11)',
  午: '午时(11-13)',
  未: '未时(13-15)',
  申: '申时(15-17)',
  酉: '酉时(17-19)',
  戌: '戌时(19-21)',
  亥: '亥时(21-23)',
}

/** 五鼠遁日上起时：甲己还加甲，乙庚丙作初，丙辛从戊起，丁壬庚子居，戊癸壬子是真途。 */
export function hourPillarOf(dayStem: string, hourBranch: string): string {
  const dayIndex = GAN.indexOf(dayStem as (typeof GAN)[number])
  const branchIndex = ZHI.indexOf(hourBranch as (typeof ZHI)[number])
  if (dayIndex < 0 || branchIndex < 0) throw new Error(`无效日干/时支: ${dayStem} ${hourBranch}`)
  const startStem = (dayIndex % 5) * 2
  return `${GAN[(startStem + branchIndex) % 10]}${hourBranch}`
}

function buildPillar(ganZhi: string): Pillar {
  const stem = ganZhi[0]
  const branch = ganZhi[1]
  const nayin = nayinOfGanZhi(ganZhi)
  return {
    ganZhi,
    stem,
    branch,
    stemElement: GAN_ELEMENT[stem],
    branchElement: ZHI_ELEMENT[branch],
    nayin: nayin.name,
    nayinElement: nayin.element,
  }
}

/** 由日期（可选时支）构造历法事实。 */
export function buildFacts(date: string, hourBranch: string | null = null): DayFacts {
  const solar = solarOf(date)
  const lunar = solar.getLunar()
  const shensha = analyzeDay(date)
  const dayGanZhi = lunar.getDayInGanZhi()
  const hourGanZhi = hourBranch ? hourPillarOf(dayGanZhi[0], hourBranch) : null
  const term = lunar.getJieQi()
  const monthPillarGanZhi = lunar.getMonthInGanZhiExact()

  return {
    date,
    weekDay: weekdayLabel(date),
    lunarText: lunar.toString(),
    lunarMonth: lunar.getMonth(),
    lunarDay: lunar.getDay(),
    isLunarLeapMonth: lunar.getMonth() < 0,
    pillars: {
      year: buildPillar(shensha.yearGanZhi),
      month: buildPillar(monthPillarGanZhi),
      day: buildPillar(dayGanZhi),
      hour: hourGanZhi ? buildPillar(hourGanZhi) : null,
    },
    monthIndex: monthIndexFromZhi(shensha.monthBranch),
    monthBranch: shensha.monthBranch,
    season: shensha.season,
    solarTerm: term || null,
    zhiXing: shensha.zhiXing,
    tianShen: lunar.getDayTianShen(),
    tianShenType: lunar.getDayTianShenType(),
    tianShenLuck: lunar.getDayTianShenLuck(),
    xiu: lunar.getXiu(),
    xiuLuck: lunar.getXiuLuck(),
    pengZu: [lunar.getPengZuGan(), lunar.getPengZuZhi()],
    jiShen: lunar.getDayJiShen(),
    xiongSha: lunar.getDayXiongSha(),
    almanacYi: lunar.getDayYi(),
    almanacJi: lunar.getDayJi(),
    chongDesc: lunar.getDayChongDesc(),
    chongShengXiao: lunar.getDayChongShengXiao(),
    sha: lunar.getDaySha(),
    positions: {
      xi: lunar.getDayPositionXi(),
      cai: lunar.getDayPositionCai(),
      fu: lunar.getDayPositionFu(),
      yangGui: lunar.getDayPositionYangGui(),
      yinGui: lunar.getDayPositionYinGui(),
      tai: lunar.getDayPositionTai(),
    },
    luckyHours: lunar
      .getTimes()
      .filter((time) => time.getTianShenLuck() === '吉')
      .slice(0, 6)
      .map((time) => `${time.getZhi()}时`),
    shensha,
  }
}

export function hourBranchName(branch: string): string {
  return HOUR_NAMES[branch] ?? `${branch}时`
}

/** 日课四柱中出现的地支集合（含时支）。 */
export function courseBranches(facts: DayFacts): string[] {
  const list = [
    facts.pillars.year.branch,
    facts.pillars.month.branch,
    facts.pillars.day.branch,
  ]
  if (facts.pillars.hour) list.push(facts.pillars.hour.branch)
  return list
}

export function courseStems(facts: DayFacts): string[] {
  const list = [
    facts.pillars.year.stem,
    facts.pillars.month.stem,
    facts.pillars.day.stem,
  ]
  if (facts.pillars.hour) list.push(facts.pillars.hour.stem)
  return list
}

/** 三合局：局名 → 所需三支（申子辰水、亥卯未木、寅午戌火、巳酉丑金）。 */
export const SAN_HE_FRAMES: Array<{ element: FiveElement; members: string[] }> = [
  { element: '水', members: ['申', '子', '辰'] },
  { element: '木', members: ['亥', '卯', '未'] },
  { element: '火', members: ['寅', '午', '戌'] },
  { element: '金', members: ['巳', '酉', '丑'] },
]

export interface SanHeFrameHit {
  element: FiveElement
  members: string[]
  /** 日课地支命中该局的支数（0–3） */
  hitCount: number
  missing: string[]
  /** 三支齐现才算成局；两支为半合 */
  complete: boolean
}

/**
 * 列出日课地支命中的全部三合局（含半合），按「完整局优先」排序。
 *
 * 旧实现只返回**第一个** `hitCount >= 2` 的局，带来两个问题：
 * 1. 半合被当成完整局：调用方按 `element` 给旺/相/克满额评分，
 *    而规格明确「缺一为待」；
 * 2. 结果依赖 `SAN_HE_FRAMES` 的表顺序：四柱若同时有两个半合，
 *    返回哪个局是任意的。
 *
 * 现在把「命中几支、是否成局」显式交给调用方，由调用方决定怎么用。
 */
export function sanHeFrames(branches: string[]): SanHeFrameHit[] {
  return SAN_HE_FRAMES.map((frame) => {
    const hit = frame.members.filter((item) => branches.includes(item))
    return {
      element: frame.element,
      members: frame.members,
      hitCount: hit.length,
      missing: frame.members.filter((item) => !branches.includes(item)),
      complete: hit.length === 3,
    }
  })
    .filter((frame) => frame.hitCount >= 2)
    .sort((a, b) => Number(b.complete) - Number(a.complete) || b.hitCount - a.hitCount)
}

export function sixHarmonyPartner(branch: string): string | null {
  const pairs: Record<string, string> = {
    子: '丑', 丑: '子', 寅: '亥', 亥: '寅', 卯: '戌', 戌: '卯',
    辰: '酉', 酉: '辰', 巳: '申', 申: '巳', 午: '未', 未: '午',
  }
  return pairs[branch] ?? null
}

export function elementRelation(from: FiveElement, to: FiveElement): string {
  if (from === to) return '比和'
  if (ELEMENT_SHENG[from] === to) return '生'
  if (ELEMENT_SHENG[to] === from) return '被生'
  if (ELEMENT_KE[from] === to) return '克'
  if (ELEMENT_KE[to] === from) return '被克'
  return '无关'
}

export function clashOf(branch: string): string {
  return ZHI_CLASH[branch]
}

/** 真太阳时：地方平时按经度修正，再叠加均时差；均时差来自太阳视黄经算法。 */
export function trueSolarMinutes(
  clockMinutes: number,
  longitudeDeg: number,
  date: string
): { offset: number; value: number } {
  const localMean = (longitudeDeg - 120) * 4
  const { equationOfTimeMinutes } = solarLongitude(date)
  const offset = localMean + equationOfTimeMinutes
  return { offset, value: clockMinutes + offset }
}

export function facingOf(mountName: string): MountainMeta {
  return oppositeMountain(mountName)
}

export function mountBranchOf(mountName: string): string | null {
  return branchOfMountain(mountName)
}

export function contextFor(options: {
  category: ZeRiCategory
  mountShan: string
  incomingDragon?: string | null
  subjects?: SubjectInfo[]
  hourBranch?: string | null
  includesConstruction?: boolean
  sittingDeg?: number
  eventYear: number
  yaoOrder?: 'ASC' | 'DESC'
  longitudeDeg?: number | null
}): ZeriContext {
  const mountMeta = getMountain(options.mountShan)
  return {
    category: options.category,
    mountShan: options.mountShan,
    mountMeta,
    facingMeta: oppositeMountain(options.mountShan),
    incomingDragon: options.incomingDragon ? getMountain(options.incomingDragon) : null,
    subjects: options.subjects ?? [],
    hourBranch: options.hourBranch ?? null,
    includesConstruction: options.includesConstruction ?? false,
    sittingDeg: options.sittingDeg ?? mountMeta.centerDeg,
    eventYear: options.eventYear,
    yaoOrder: options.yaoOrder ?? 'ASC',
    longitudeDeg: options.longitudeDeg ?? null,
  }
}
