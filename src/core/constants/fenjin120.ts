import type { FenJinQuality, FenJinSlot } from '../types'
import {
  SHAN_24_LIST,
  angularDelta,
  getMountain,
  mountainOffset,
  normalizeDeg,
  resolveMountain,
} from './shan24'
import { ZHI, nayinOfGanZhi } from './nayin60'

const YANG_STEMS = ['甲', '丙', '戊', '庚', '壬']
const YIN_STEMS = ['乙', '丁', '己', '辛', '癸']

const WANG_XIANG = new Set(['丙', '丁', '庚', '辛'])
const GU_XU = new Set(['甲', '壬', '乙', '癸'])
const KONG_WANG = new Set(['戊', '己'])

function qualityOf(stem: string): FenJinQuality {
  if (WANG_XIANG.has(stem)) return 'WANG_XIANG'
  if (GU_XU.has(stem)) return 'GU_XU'
  if (KONG_WANG.has(stem)) return 'KONG_WANG'
  return 'GU_XU'
}

function qualityDetailOf(stem: string): string {
  if (stem === '丙' || stem === '庚') return '旺'
  if (stem === '丁' || stem === '辛') return '相'
  if (stem === '甲' || stem === '壬') return '阳孤'
  if (stem === '乙' || stem === '癸') return '阴虚'
  return '龟甲空亡'
}

function buildSlots(): FenJinSlot[] {
  const slots: FenJinSlot[] = []
  for (const mountain of SHAN_24_LIST) {
    const sourceIndex = mountain.index % 2 === 0 ? mountain.index : mountain.index - 1
    const branch = ZHI[sourceIndex / 2]
    const isYang = sourceIndex % 4 === 0
    const stems = isYang ? YANG_STEMS : YIN_STEMS
    const firstStart = mountain.centerDeg - 7.5
    for (let i = 0; i < 5; i++) {
      const stem = stems[i]
      const ganZhi = stem + branch
      const nayin = nayinOfGanZhi(ganZhi)
      const quality = qualityOf(stem)
      const startDeg = normalizeDeg(firstStart + i * 3)
      slots.push({
        index: mountain.index * 5 + i,
        mount: mountain.name,
        subIndex: i as 0 | 1 | 2 | 3 | 4,
        ganZhi,
        stem,
        branch,
        startDeg,
        endDeg: normalizeDeg(startDeg + 3),
        centerDeg: normalizeDeg(startDeg + 1.5),
        quality,
        qualityDetail: qualityDetailOf(stem),
        nayin: nayin.name,
        element: nayin.element,
        usableForYin: quality === 'WANG_XIANG',
      })
    }
  }
  return slots
}

export const FENJIN_SLOTS: FenJinSlot[] = buildSlots()

const BY_GANZHI = new Map(FENJIN_SLOTS.map((slot) => [`${slot.mount}:${slot.ganZhi}`, slot]))

export function resolveFenJin(deg: number): {
  slot: FenJinSlot
  offset: number
  isJianXiang: boolean
  warning: string | null
} {
  const norm = normalizeDeg(deg)
  const index = Math.floor(normalizeDeg(norm + 7.5) / 3) % 120
  const slot = FENJIN_SLOTS[index]
  const mountain = getMountain(slot.mount)
  const offset = mountainOffset(norm, mountain)
  const jianXiang = Math.abs(offset) > 4.5

  let warning: string | null = null
  if (jianXiang) {
    warning = `当前线度已进入兼向区（偏离${slot.mount}山中心 ${Math.abs(offset).toFixed(1)}°），传统立向需专业罗盘复核。`
  } else if (slot.quality === 'KONG_WANG') {
    warning = `当前线度落在${slot.ganZhi}（${slot.qualityDetail}），传统分金不建议作为立向主线，可微调至同山旺相分金。`
  } else if (slot.quality === 'GU_XU') {
    warning = `当前线度落在${slot.ganZhi}（${slot.qualityDetail}），传统分金视为孤虚格，建议调整至旺相分金。`
  }

  return { slot, offset, isJianXiang: jianXiang, warning }
}

export function fenJinOfMountain(mountName: string): FenJinSlot[] {
  return FENJIN_SLOTS.filter((slot) => slot.mount === mountName)
}

export function findFenJin(mountName: string, ganZhi: string): FenJinSlot | null {
  return BY_GANZHI.get(`${mountName}:${ganZhi}`) ?? null
}

export function suggestFenJinSlots(mountName: string): FenJinSlot[] {
  return fenJinOfMountain(mountName).filter((slot) => slot.usableForYin)
}

export function checkKongWangLine(deg: number, threshold = 1): string | null {
  const norm = normalizeDeg(deg)
  for (let i = 0; i < 8; i++) {
    const boundary = 22.5 + i * 45
    const diff = Math.min(Math.abs(norm - boundary), 360 - Math.abs(norm - boundary))
    if (diff <= threshold) {
      return `当前度数距八卦交界仅 ${diff.toFixed(1)}°，传统上属于空亡线临界区，建议用实体罗盘复测。`
    }
  }
  for (let i = 0; i < 24; i++) {
    const boundary = (7.5 + i * 15) % 360
    const diff = Math.min(Math.abs(norm - boundary), 360 - Math.abs(norm - boundary))
    if (diff <= threshold) {
      return `当前度数距两山交界仅 ${diff.toFixed(1)}°，下卦与替卦容易翻转，建议复测。`
    }
  }
  return null
}

export function describeFenJin(slot: FenJinSlot): string {
  return `${slot.ganZhi}·${slot.qualityDetail}·${slot.nayin}`
}

export function qualityLabel(quality: FenJinQuality): string {
  if (quality === 'WANG_XIANG') return '旺相'
  if (quality === 'KONG_WANG') return '空亡'
  return '孤虚'
}

export function nearestUsableSlot(deg: number): FenJinSlot {
  const mountain = resolveMountain(deg)
  const usable = suggestFenJinSlots(mountain.name)
  if (!usable.length) return resolveFenJin(deg).slot
  return usable.reduce((best, slot) =>
    Math.abs(angularDelta(deg, slot.centerDeg)) < Math.abs(angularDelta(deg, best.centerDeg))
      ? slot
      : best
  )
}
