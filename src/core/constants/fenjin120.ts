import type { FenJinSlot } from '../types'
import {
  SHAN_24_LIST,
  getMountain,
  mountainOffset,
  normalizeDeg,
} from './shan24'
import { ZHI, nayinOfGanZhi } from './nayin60'

const YANG_STEMS = ['甲', '丙', '戊', '庚', '壬']
const YIN_STEMS = ['乙', '丁', '己', '辛', '癸']

/**
 * 分格说明只描述几何/历法事实（天干 + 几何分格）。
 *
 * 合规约束（施工依据 v1.0 §0.3 与附录 E 第 6 条）：外部方案按天干把分金分成
 * 「旺相／孤虚／空亡」的吉凶口径未经三源核验，不得进入数据结构与界面。
 * 这里连内部分类都不保留——留着就会有人再把它接到界面上。
 */
function slotNoteOf(stem: string): string {
  return `${stem}干·几何分格`
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
        slotNote: slotNoteOf(stem),
        nayin: nayin.name,
        element: nayin.element,
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
  }
  // 兼向等几何提醒保留；未核验的吉凶口径不在这里、也不在任何字段里。

  return { slot, offset, isJianXiang: jianXiang, warning }
}

export function fenJinOfMountain(mountName: string): FenJinSlot[] {
  return FENJIN_SLOTS.filter((slot) => slot.mount === mountName)
}

export function findFenJin(mountName: string, ganZhi: string): FenJinSlot | null {
  return BY_GANZHI.get(`${mountName}:${ganZhi}`) ?? null
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
  return `${slot.ganZhi}·${slot.slotNote}·${slot.nayin}`
}
