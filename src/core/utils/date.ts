import { Solar } from 'lunar-javascript'
import type { BirthInfo } from '../types'

export interface Ymd {
  year: number
  month: number
  day: number
}

export function parseYmd(value: string): Ymd {
  const parts = value.split('-').map((item) => Number(item))
  if (parts.length !== 3 || parts.some((item) => !Number.isFinite(item))) {
    throw new Error(`无效日期: ${value}`)
  }
  return { year: parts[0], month: parts[1], day: parts[2] }
}

export function pad2(value: number): string {
  return value < 10 ? `0${value}` : String(value)
}

export function formatYmd(value: Ymd): string {
  return `${value.year}-${pad2(value.month)}-${pad2(value.day)}`
}

export function addDays(value: string, days: number): string {
  const { year, month, day } = parseYmd(value)
  const date = new Date(Date.UTC(year, month - 1, day + days))
  return `${date.getUTCFullYear()}-${pad2(date.getUTCMonth() + 1)}-${pad2(date.getUTCDate())}`
}

export function todayYmd(): string {
  return ymdOf(new Date())
}

/**
 * 毫秒时间戳 → 本地日期字符串（YYYY-MM-DD）。与 `todayYmd()` 同一时区口径，
 * 用于把时间戳换算成「用户当时看到的日期」。
 */
export function ymdOf(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

/**
 * 毫秒时间戳 → UTC 日期字符串（YYYY-MM-DD）。
 *
 * 只用于**迁移回填**这类必须与机器时区无关的场合：同一份旧档案在任何时区的
 * 机器上迁移，都必须得到同一个回填值，否则 inputHash 会随机器变。
 * 不要拿它代替 `todayYmd()` 表示「今天」。
 */
export function ymdUtcOf(epochMs: number): string {
  const date = new Date(epochMs)
  return `${date.getUTCFullYear()}-${pad2(date.getUTCMonth() + 1)}-${pad2(date.getUTCDate())}`
}

export function compareYmd(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0
}

export function solarOf(value: string): Solar {
  const { year, month, day } = parseYmd(value)
  return Solar.fromYmd(year, month, day)
}

export function weekdayLabel(value: string): string {
  return `星期${solarOf(value).getWeekInChinese()}`
}

export function liChunOfYear(year: number): string {
  const table = Solar.fromYmd(year, 6, 1).getLunar().getJieQiTable()
  const liChun = table['立春']
  return liChun ? liChun.toYmd() : `${year}-02-04`
}

export function effectiveYearOfBirth(birth: BirthInfo): number {
  const { year } = parseYmd(birth.date)
  if (birth.precision === 'YEAR') {
    return birth.beforeLiChun ? year - 1 : year
  }
  return compareYmd(birth.date, liChunOfYear(year)) < 0 ? year - 1 : year
}

export function ganZhiOfYear(year: number): string {
  return Solar.fromYmd(year, 6, 1).getLunar().getYearInGanZhiExact()
}

export function zhiOfYear(year: number): string {
  return ganZhiOfYear(year).slice(1)
}

const MONTH_ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

export function monthIndexFromZhi(zhi: string): number {
  const index = MONTH_ZHI.indexOf(zhi)
  if (index < 0) throw new Error(`无效月支: ${zhi}`)
  return index <= 1 ? index + 11 : index - 1
}

export function isSiLiSiJueDay(value: string): { hit: boolean; name?: string } {
  const solar = solarOf(value)
  const table = solar.getLunar().getJieQiTable()
  const tomorrow = solar.next(1).toYmd()
  const names = ['立春', '立夏', '立秋', '立冬', '春分', '秋分', '夏至', '冬至']
  for (const name of names) {
    const term = table[name]
    if (term && term.toYmd() === tomorrow) {
      return { hit: true, name }
    }
  }
  return { hit: false }
}

const YANG_GONG_JI: Array<[number, number]> = [
  [1, 13],
  [2, 11],
  [3, 9],
  [4, 7],
  [5, 5],
  [6, 3],
  [7, 1],
  [7, 29],
  [8, 27],
  [9, 25],
  [10, 23],
  [11, 21],
  [12, 19],
]

export function isYangGongJi(lunarMonth: number, lunarDay: number): boolean {
  const month = Math.abs(lunarMonth)
  return YANG_GONG_JI.some(([m, d]) => m === month && d === lunarDay)
}

// ── 日级节气口径 ───────────────────────────────────────────────
// 通书与《协纪辨方书》以「交节当日」换月、以「立春当日」换年；
// lunar-javascript 的 Exact 系列按交节时刻切换，用于日级择日会差一天。

const JIE_TO_MONTH_ZHI: Record<string, string> = {
  立春: '寅', 惊蛰: '卯', 清明: '辰', 立夏: '巳', 芒种: '午', 小暑: '未',
  立秋: '申', 白露: '酉', 寒露: '戌', 立冬: '亥', 大雪: '子', 小寒: '丑',
}

const ZHI_XING_ORDER = ['建', '除', '满', '平', '定', '执', '破', '危', '成', '收', '开', '闭']
const SI_LI = ['立春', '立夏', '立秋', '立冬']

const jieCache = new Map<number, Array<{ name: string; date: string; zhi: string }>>()

function jieList(year: number): Array<{ name: string; date: string; zhi: string }> {
  const cached = jieCache.get(year)
  if (cached) return cached
  const table = Solar.fromYmd(year, 6, 1).getLunar().getJieQiTable()
  const list: Array<{ name: string; date: string; zhi: string }> = []
  for (const [name, zhi] of Object.entries(JIE_TO_MONTH_ZHI)) {
    const jie = table[name]
    if (jie) list.push({ name, date: jie.toYmd(), zhi })
  }
  list.sort((a, b) => compareYmd(a.date, b.date))
  jieCache.set(year, list)
  return list
}

/** 交节当日即换月柱，返回当日所处月支（子＝农历十一月建） */
export function monthBranchForDate(value: string): string {
  const { year } = parseYmd(value)
  for (const candidate of [year, year - 1]) {
    let zhi: string | null = null
    for (const jie of jieList(candidate)) {
      if (compareYmd(jie.date, value) <= 0) zhi = jie.zhi
    }
    if (zhi) return zhi
  }
  throw new Error(`无法确定月支: ${value}`)
}

/** 月建之支（与 monthBranchForDate 同义，用于与日支比较求月破） */
export function monthZhiForDate(value: string): string {
  return monthBranchForDate(value)
}

/** 建除十二值：月建日为建，顺行一位为除 */
export function zhiXingForDate(value: string): string {
  const dayZhi = solarOf(value).getLunar().getDayZhi()
  const offset = MONTH_ZHI.indexOf(dayZhi) - MONTH_ZHI.indexOf(monthBranchForDate(value))
  return ZHI_XING_ORDER[((offset % 12) + 12) % 12]
}

/** 立春当日换年，返回该日所处年干支 */
export function yearGanZhiForDate(value: string): string {
  const { year } = parseYmd(value)
  const liChun = liChunOfYear(year)
  if (compareYmd(value, liChun) >= 0) return ganZhiOfYear(year)
  return ganZhiOfYear(year - 1)
}

/** 季节序：0 春 1 夏 2 秋 3 冬（按月支三合局） */
export function seasonIndexOf(monthBranch: string): number {
  const offset = (((MONTH_ZHI.indexOf(monthBranch) - 2) % 12) + 12) % 12
  return Math.floor(offset / 3)
}

/** 四仲月（子午卯酉）：天德等地支类神煞以日支相较 */
export function isZhongMonth(monthBranch: string): boolean {
  return ['子', '午', '卯', '酉'].includes(monthBranch)
}

export function dayDiff(from: string, to: string): number {
  const a = parseYmd(from)
  const b = parseYmd(to)
  return Math.round(
    (Date.UTC(b.year, b.month - 1, b.day) - Date.UTC(a.year, a.month - 1, a.day)) / 86400000
  )
}

/** 距下一个四立节气的天数，用于土王用事（四立前十八日） */
export function daysToNextSiLi(value: string): number {
  const { year } = parseYmd(value)
  let nearest = Number.MAX_SAFE_INTEGER
  for (const candidateYear of [year, year + 1]) {
    const table = Solar.fromYmd(candidateYear, 6, 1).getLunar().getJieQiTable()
    for (const name of SI_LI) {
      const jie = table[name]
      if (!jie) continue
      const diff = dayDiff(value, jie.toYmd())
      if (diff >= 0 && diff < nearest) nearest = diff
    }
  }
  return nearest
}
