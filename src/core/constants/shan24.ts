import type { FiveElement, JianXiangKind, PalaceId, YuanLong } from '../types'
import { ZHI, ZHI_CLASH } from './nayin60'

export interface MountainMeta {
  index: number
  name: string
  centerDeg: number
  gong: PalaceId
  yuan: YuanLong
  yinYang: 1 | -1
  tiGuaStar: number
  zhengWuXing: FiveElement
}

const RAW: Array<[string, PalaceId, YuanLong, 1 | -1, number, FiveElement]> = [
  ['子', 1, 'TIAN', -1, 1, '水'],
  ['癸', 1, 'REN', -1, 1, '水'],
  ['丑', 8, 'DI', -1, 7, '土'],
  ['艮', 8, 'TIAN', 1, 7, '土'],
  ['寅', 8, 'REN', 1, 9, '木'],
  ['甲', 3, 'DI', 1, 1, '木'],
  ['卯', 3, 'TIAN', -1, 2, '木'],
  ['乙', 3, 'REN', -1, 2, '木'],
  ['辰', 4, 'DI', -1, 6, '土'],
  ['巽', 4, 'TIAN', 1, 6, '木'],
  ['巳', 4, 'REN', 1, 6, '火'],
  ['丙', 9, 'DI', 1, 7, '火'],
  ['午', 9, 'TIAN', -1, 9, '火'],
  ['丁', 9, 'REN', -1, 9, '火'],
  ['未', 2, 'DI', -1, 2, '土'],
  ['坤', 2, 'TIAN', 1, 2, '土'],
  ['申', 2, 'REN', 1, 1, '金'],
  ['庚', 7, 'DI', 1, 9, '金'],
  ['酉', 7, 'TIAN', -1, 7, '金'],
  ['辛', 7, 'REN', -1, 7, '金'],
  ['戌', 6, 'DI', -1, 6, '土'],
  ['乾', 6, 'TIAN', 1, 6, '金'],
  ['亥', 6, 'REN', 1, 6, '水'],
  ['壬', 1, 'DI', 1, 2, '水'],
]

export const SHAN_24_LIST: MountainMeta[] = RAW.map(
  ([name, gong, yuan, yinYang, tiGuaStar, zhengWuXing], index) => ({
    index,
    name,
    centerDeg: index * 15,
    gong,
    yuan,
    yinYang,
    tiGuaStar,
    zhengWuXing,
  })
)

export const SHAN_NAMES = SHAN_24_LIST.map((m) => m.name)

const BY_NAME = new Map(SHAN_24_LIST.map((m) => [m.name, m]))

export function getMountain(name: string): MountainMeta {
  const meta = BY_NAME.get(name)
  if (!meta) throw new Error(`未知坐山: ${name}`)
  return meta
}

export function normalizeDeg(deg: number): number {
  return ((deg % 360) + 360) % 360
}

export function angularDelta(a: number, b: number): number {
  const diff = normalizeDeg(a - b)
  return diff > 180 ? diff - 360 : diff
}

export function resolveMountain(deg: number): MountainMeta {
  const norm = normalizeDeg(deg)
  const index = Math.floor(normalizeDeg(norm + 7.5) / 15)
  return SHAN_24_LIST[index % 24]
}

export function mountainOffset(deg: number, meta: MountainMeta): number {
  return angularDelta(normalizeDeg(deg), meta.centerDeg)
}

export function oppositeMountain(name: string): MountainMeta {
  const meta = getMountain(name)
  return SHAN_24_LIST[(meta.index + 12) % 24]
}

export function mountainOfBranch(branch: string): MountainMeta | null {
  const index = ZHI.indexOf(branch as (typeof ZHI)[number])
  if (index < 0) return null
  return SHAN_24_LIST[index * 2]
}

export function branchOfMountain(name: string): string | null {
  const meta = getMountain(name)
  if (meta.index % 2 !== 0) return null
  return ZHI[meta.index / 2]
}

export function clashMountainOfBranch(branch: string): MountainMeta | null {
  const clash = ZHI_CLASH[branch]
  return clash ? mountainOfBranch(clash) : null
}

export function isJianXiang(deg: number): boolean {
  return Math.abs(mountainOffset(deg, resolveMountain(deg))) > 4.5
}

export interface JianXiangAnalysis {
  mountain: MountainMeta
  adjacent: MountainMeta | null
  offset: number
  isJianXiang: boolean
  kind: JianXiangKind
  useTiGua: boolean
}

// 中州派兼向起星：同宫同阴阳不替，阴阳互兼用替，出卦（跨卦宫）必替。
export function analyzeJianXiang(deg: number): JianXiangAnalysis {
  const norm = normalizeDeg(deg)
  const mountain = resolveMountain(norm)
  const offset = mountainOffset(norm, mountain)
  if (Math.abs(offset) <= 4.5) {
    return { mountain, adjacent: null, offset, isJianXiang: false, kind: 'ZHENG', useTiGua: false }
  }
  const adjacent = SHAN_24_LIST[(mountain.index + (offset > 0 ? 1 : 23)) % 24]
  if (adjacent.gong !== mountain.gong) {
    return { mountain, adjacent, offset, isJianXiang: true, kind: 'CHU_GUA', useTiGua: true }
  }
  if (adjacent.yinYang === mountain.yinYang) {
    return { mountain, adjacent, offset, isJianXiang: true, kind: 'TONG_GONG', useTiGua: false }
  }
  return { mountain, adjacent, offset, isJianXiang: true, kind: 'YIN_YANG_JIAN', useTiGua: true }
}

export const JIAN_XIANG_LABELS: Record<JianXiangKind, string> = {
  ZHENG: '正向',
  TONG_GONG: '同宫比和',
  YIN_YANG_JIAN: '阴阳互兼',
  CHU_GUA: '出卦',
}
