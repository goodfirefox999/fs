import type {
  BaZhaiHouse,
  BaZhaiMemberResult,
  BaZhaiPalace,
  BaZhaiResult,
  BirthInfo,
  MingGuaInfo,
  PalaceId,
} from '../types'
import {
  BAZHAI_STARS,
  MING_GUA_BITS,
  MING_GUA_INFO,
  PALACES,
  PALACE_IDS,
} from '../constants/luoshu'
import { getMountain } from '../constants/shan24'
import { effectiveYearOfBirth } from '../utils/date'

export interface MingGuaResolution {
  gua: number
  info: MingGuaInfo
  effectiveYear: number
}

export function calcMingGua(birth: BirthInfo): MingGuaResolution | null {
  if (!birth.date || !birth.gender) return null
  let effectiveYear: number
  try {
    effectiveYear = effectiveYearOfBirth(birth)
  } catch {
    return null
  }
  const n = (((effectiveYear % 100) % 9) + 9) % 9
  let gua: number
  if (birth.gender === 'M') {
    gua = effectiveYear < 2000 ? 10 - n : 9 - n
  } else {
    gua = effectiveYear < 2000 ? n + 5 : n + 6
  }
  gua = (((gua - 1) % 9) + 9) % 9 + 1
  if (gua === 5) gua = birth.gender === 'M' ? 2 : 8
  const info = MING_GUA_INFO[gua]
  return {
    gua,
    effectiveYear,
    info: {
      gua,
      name: info.name,
      element: info.element,
      group: info.group,
      groupLabel: info.group === 'EAST' ? '东四命' : '西四命',
    },
  }
}

export function palacesOfGua(gua: number): BaZhaiPalace[] {
  const bits = MING_GUA_BITS[gua]
  if (bits === undefined) throw new Error(`无效命卦: ${gua}`)
  return PALACE_IDS.filter((palace) => palace !== 5).map((palace) => {
    const meta = PALACES[palace]
    const xor = bits ^ (meta.bits as number)
    return {
      palace,
      direction: meta.direction,
      star: BAZHAI_STARS[xor],
    }
  })
}

export function houseGuaOf(sittingShan: string): BaZhaiHouse {
  const gong = getMountain(sittingShan).gong
  const info = MING_GUA_INFO[gong]
  return {
    sittingShan,
    gua: gong,
    name: info.name,
    element: info.element,
    group: info.group,
    groupLabel: info.group === 'EAST' ? '东四宅' : '西四宅',
    palaces: palacesOfGua(gong),
  }
}

export function analyzeBaZhai(members: Array<{ relation: string; birth: BirthInfo }>, sittingShan: string): BaZhaiResult {
  const house = houseGuaOf(sittingShan)
  const notes: string[] = []
  const results: BaZhaiMemberResult[] = []

  for (const member of members) {
    const ming = calcMingGua(member.birth)
    if (!ming) {
      notes.push(`${member.relation}的出生日期或性别不完整，命卦暂未生成。`)
      continue
    }
    const match = ming.info.group === house.group ? 'MATCH' : 'MISMATCH'
    results.push({
      relation: member.relation,
      birth: member.birth,
      effectiveYear: ming.effectiveYear,
      mingGua: ming.info,
      match,
      matchLabel:
        match === 'MATCH'
          ? `命宅同组（${ming.info.groupLabel}配${house.groupLabel}）`
          : `命宅分组不同（${ming.info.groupLabel}配${house.groupLabel}）`,
      palaces: palacesOfGua(ming.gua),
    })
  }

  notes.push('八宅分区为传统空间经验，仅作房间功能与动线安排的参考，不替代结构安全、消防与采光通风的专业判断。')
  return { house, members: results, notes }
}

export function favorablePalaces(member: BaZhaiMemberResult): PalaceId[] {
  return member.palaces
    .filter((item) => item.star.level === 'GOOD')
    .map((item) => item.palace)
}

export function bestPalaceFor(member: BaZhaiMemberResult, use: 'SLEEP' | 'WORK' | 'LIVING'): BaZhaiPalace | null {
  const priority =
    use === 'SLEEP'
      ? ['TIAN_YI', 'YAN_NIAN', 'FU_WEI', 'SHENG_QI']
      : use === 'WORK'
        ? ['SHENG_QI', 'TIAN_YI', 'FU_WEI', 'YAN_NIAN']
        : ['SHENG_QI', 'YAN_NIAN', 'TIAN_YI', 'FU_WEI']
  for (const code of priority) {
    const found = member.palaces.find((item) => item.star.code === code)
    if (found) return found
  }
  return member.palaces[0] ?? null
}
