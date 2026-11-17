import type { AnnualInfo, FlyingChart, MonthlyInfo, PalaceId } from '../types'
import { LUOSHU_ORDER, PALACES } from '../constants/luoshu'
import { GAN, ZHI, ZHI_CLASH } from '../constants/nayin60'
import { SHAN_24_LIST, normalizeDeg } from '../constants/shan24'
import {
  ganZhiOfYear,
  monthBranchForDate,
  monthIndexFromZhi,
  parseYmd,
  yearGanZhiForDate,
  zhiOfYear,
} from '../utils/date'

export function flyNinePalaces(centerStar: number, direction: 1 | -1): FlyingChart {
  const byPalace = {} as Record<PalaceId, number>
  const palaces: Array<{ palace: PalaceId; star: number }> = []
  LUOSHU_ORDER.forEach((palace, step) => {
    const raw = centerStar + direction * step
    const star = (((raw - 1) % 9) + 9) % 9 + 1
    byPalace[palace] = star
    palaces.push({ palace, star })
  })
  return { centerStar, palaces, byPalace }
}

export function starAt(chart: FlyingChart, palace: PalaceId): number {
  return chart.byPalace[palace]
}

export function annualCenter(year: number): number {
  let star = 11 - (year % 9)
  if (star <= 0) star += 9
  if (star > 9) star -= 9
  return star
}

const SAN_SHA_GROUPS: Record<string, { branches: string[]; direction: string }> = {
  申: { branches: ['巳', '午', '未'], direction: '南（巳午未）' },
  子: { branches: ['巳', '午', '未'], direction: '南（巳午未）' },
  辰: { branches: ['巳', '午', '未'], direction: '南（巳午未）' },
  寅: { branches: ['亥', '子', '丑'], direction: '北（亥子丑）' },
  午: { branches: ['亥', '子', '丑'], direction: '北（亥子丑）' },
  戌: { branches: ['亥', '子', '丑'], direction: '北（亥子丑）' },
  巳: { branches: ['寅', '卯', '辰'], direction: '东（寅卯辰）' },
  酉: { branches: ['寅', '卯', '辰'], direction: '东（寅卯辰）' },
  丑: { branches: ['寅', '卯', '辰'], direction: '东（寅卯辰）' },
  亥: { branches: ['申', '酉', '戌'], direction: '西（申酉戌）' },
  卯: { branches: ['申', '酉', '戌'], direction: '西（申酉戌）' },
  未: { branches: ['申', '酉', '戌'], direction: '西（申酉戌）' },
}

/**
 * 三合局支 → 三煞方。年支、月支、日支同用此表（年家三煞最重，月家、日层次之），
 * 故参数不叫「年支」。
 */
export function sanShaOfZhi(zhi: string): { branches: string[]; direction: string } {
  const group = SAN_SHA_GROUPS[zhi]
  if (!group) throw new Error(`无效地支: ${zhi}`)
  return group
}

export function sanShaSectorOf(yearZhi: string): {
  start: number
  end: number
  direction: string
} | null {
  const group = sanShaOfZhi(yearZhi)
  const first = SHAN_24_LIST.find((mountain) => mountain.name === group.branches[0])
  const last = SHAN_24_LIST.find((mountain) => mountain.name === group.branches[2])
  if (!first || !last) return null
  return {
    start: normalizeDeg(first.centerDeg - 7.5),
    end: normalizeDeg(last.centerDeg + 7.5),
    direction: group.direction,
  }
}

export function isInAngularSector(deg: number, start: number, end: number): boolean {
  const value = normalizeDeg(deg)
  if (start < end) return value >= start && value < end
  return value >= start || value < end
}

export function isInSanShaSector(deg: number, yearZhi: string): boolean {
  const sector = sanShaSectorOf(yearZhi)
  return sector ? isInAngularSector(deg, sector.start, sector.end) : false
}

/**
 * 煞区跨三支共五座山，正煞＝中间一支及其两侧的天干山（北方壬·子·癸、南方丙·午·丁），
 * 傍煞＝两端的地支山（亥、丑／巳、未）——通书「丙午丁为三煞方，巳未为傍煞」即此例。
 * 这里的「三山」是二十四山的分组，不是玄空飞星的三元龙（地元／天元／人元）分组。
 * 只用于严重度标注，不改变命中与否。
 *
 * 边界归属与 resolveMountain 用同一条半开区间，使山名与档位永远一致：
 * 每山占 [中线-7.5, 中线+7.5)，煞区起点 start＝首支中线-7.5、宽 75°；
 * 令 rel＝(deg-start) mod 360，则 rel<15 为首支（傍煞）、15≤rel<60 为中间三山（正煞）、
 * 60≤rel<75 为末支（傍煞）、rel≥75 已出煞区（ isInSanShaSector 上界取不含）。
 * 故 322.5° 属傍煞、337.5° 属正煞、22.5° 属傍煞、37.5° 不占山。
 * 兼向只改变落在哪一山，不额外升降档：壬山兼子（350°）仍落在壬山区间，按正煞标注。
 */
export function sanShaGradeOf(deg: number, refZhi: string): '正煞' | '傍煞' | null {
  const sector = sanShaSectorOf(refZhi)
  if (!sector || !isInSanShaSector(deg, refZhi)) return null
  const rel = normalizeDeg(normalizeDeg(deg) - sector.start)
  if (rel < 15 || rel >= 60) return '傍煞'
  return '正煞'
}

export function annualInfo(year: number): AnnualInfo {
  const yearGanZhi = ganZhiOfYear(year)
  const yearZhi = yearGanZhi.slice(1)
  const centerStar = annualCenter(year)
  const sanSha = sanShaOfZhi(yearZhi)
  return {
    year,
    yearGanZhi,
    centerStar,
    chart: flyNinePalaces(centerStar, 1),
    taiSui: yearZhi,
    suiPo: ZHI_CLASH[yearZhi],
    sanShaMountains: sanSha.branches,
    sanShaDirection: sanSha.direction,
  }
}

const MONTH_CENTER: Record<'ZHENG' | 'MU' | 'SHENG', number[]> = {
  ZHENG: [8, 7, 6, 5, 4, 3, 2, 1, 9, 8, 7, 6],
  MU: [5, 4, 3, 2, 1, 9, 8, 7, 6, 5, 4, 3],
  SHENG: [2, 1, 9, 8, 7, 6, 5, 4, 3, 2, 1, 9],
}

function yearGroupOfZhi(yearZhi: string): 'ZHENG' | 'MU' | 'SHENG' {
  if (['子', '午', '卯', '酉'].includes(yearZhi)) return 'ZHENG'
  if (['辰', '戌', '丑', '未'].includes(yearZhi)) return 'MU'
  return 'SHENG'
}

export function monthlyCenter(yearZhi: string, monthIndex: number): number {
  if (monthIndex < 1 || monthIndex > 12) throw new Error(`无效月序: ${monthIndex}`)
  return MONTH_CENTER[yearGroupOfZhi(yearZhi)][monthIndex - 1]
}

export function monthGanZhiOf(yearGan: string, monthIndex: number): string {
  const ganIndex = GAN.indexOf(yearGan as (typeof GAN)[number])
  if (ganIndex < 0) throw new Error(`无效年干: ${yearGan}`)
  if (monthIndex < 1 || monthIndex > 12) throw new Error(`无效月序: ${monthIndex}`)
  const firstStem = ((ganIndex % 5) * 2 + 2) % 10
  const stem = GAN[(firstStem + monthIndex - 1) % 10]
  const zhi = ZHI[(2 + monthIndex - 1) % 12]
  return `${stem}${zhi}`
}

export function monthlyInfo(year: number, monthIndex: number, yearZhi?: string): MonthlyInfo {
  const zhi = yearZhi ?? zhiOfYear(year)
  const yearGanZhi = ganZhiOfYear(year)
  const centerStar = monthlyCenter(zhi, monthIndex)
  return {
    year,
    monthIndex,
    monthGanZhi: monthGanZhiOf(yearGanZhi[0], monthIndex),
    centerStar,
    chart: flyNinePalaces(centerStar, 1),
  }
}

export function monthlyForDate(date: string): MonthlyInfo {
  const { year } = parseYmd(date)
  const yearGanZhi = yearGanZhiForDate(date)
  const monthIndex = monthIndexFromZhi(monthBranchForDate(date))
  const centerStar = monthlyCenter(yearGanZhi.slice(1), monthIndex)
  return {
    year,
    monthIndex,
    monthGanZhi: monthGanZhiOf(yearGanZhi[0], monthIndex),
    centerStar,
    chart: flyNinePalaces(centerStar, 1),
  }
}

export function palaceLabel(palace: PalaceId): string {
  return `${PALACES[palace].direction}·${PALACES[palace].trigram}宫`
}
