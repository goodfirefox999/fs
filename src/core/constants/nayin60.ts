import type { FiveElement } from '../types'

export const GAN = ['甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸'] as const
export const ZHI = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥'] as const

export type Gan = (typeof GAN)[number]
export type Zhi = (typeof ZHI)[number]

export const GAN_ELEMENT: Record<string, FiveElement> = {
  甲: '木', 乙: '木', 丙: '火', 丁: '火', 戊: '土',
  己: '土', 庚: '金', 辛: '金', 壬: '水', 癸: '水',
}

export const ZHI_ELEMENT: Record<string, FiveElement> = {
  子: '水', 丑: '土', 寅: '木', 卯: '木', 辰: '土', 巳: '火',
  午: '火', 未: '土', 申: '金', 酉: '金', 戌: '土', 亥: '水',
}

export const ZHI_CLASH: Record<string, string> = {
  子: '午', 丑: '未', 寅: '申', 卯: '酉', 辰: '戌', 巳: '亥',
  午: '子', 未: '丑', 申: '寅', 酉: '卯', 戌: '辰', 亥: '巳',
}

export const ZHI_NEXT: Record<string, string> = {
  子: '丑', 丑: '寅', 寅: '卯', 卯: '辰', 辰: '巳', 巳: '午',
  午: '未', 未: '申', 申: '酉', 酉: '戌', 戌: '亥', 亥: '子',
}

export const ZHI_PREV: Record<string, string> = {
  子: '亥', 丑: '子', 寅: '丑', 卯: '寅', 辰: '卯', 巳: '辰',
  午: '巳', 未: '午', 申: '未', 酉: '申', 戌: '酉', 亥: '戌',
}

export const SAN_HE: Record<string, string[]> = {
  申: ['申', '子', '辰'], 子: ['申', '子', '辰'], 辰: ['申', '子', '辰'],
  寅: ['寅', '午', '戌'], 午: ['寅', '午', '戌'], 戌: ['寅', '午', '戌'],
  巳: ['巳', '酉', '丑'], 酉: ['巳', '酉', '丑'], 丑: ['巳', '酉', '丑'],
  亥: ['亥', '卯', '未'], 卯: ['亥', '卯', '未'], 未: ['亥', '卯', '未'],
}

export const NAYIN_NAMES = [
  '海中金', '炉中火', '大林木', '路旁土', '剑锋金', '山头火',
  '涧下水', '城头土', '白蜡金', '杨柳木', '泉中水', '屋上土',
  '霹雳火', '松柏木', '长流水', '沙中金', '山下火', '平地木',
  '壁上土', '金箔金', '覆灯火', '天河水', '大驿土', '钗钏金',
  '桑柘木', '大溪水', '沙中土', '天上火', '石榴木', '大海水',
] as const

export const JIAZI_60: string[] = Array.from({ length: 60 }, (_, i) => GAN[i % 10] + ZHI[i % 12])

const JIAZI_INDEX: Record<string, number> = Object.fromEntries(
  JIAZI_60.map((gz, i) => [gz, i])
)

export function isYangGan(gan: string): boolean {
  return GAN.indexOf(gan as Gan) % 2 === 0
}

export function isYangZhi(zhi: string): boolean {
  return ZHI.indexOf(zhi as Zhi) % 2 === 0
}

export function ganZhiOfIndex(index: number): string {
  return JIAZI_60[((index % 60) + 60) % 60]
}

export function nayinOfGanZhi(ganZhi: string): { name: string; element: FiveElement } {
  const index = JIAZI_INDEX[ganZhi]
  if (index === undefined) throw new Error(`无效干支: ${ganZhi}`)
  const name = NAYIN_NAMES[Math.floor(index / 2)]
  return { name, element: name.slice(-1) as FiveElement }
}

export function nayinOfIndex(index: number): { name: string; element: FiveElement } {
  return nayinOfGanZhi(ganZhiOfIndex(index))
}

export const ELEMENT_SHENG: Record<FiveElement, FiveElement> = {
  木: '火', 火: '土', 土: '金', 金: '水', 水: '木',
}

export const ELEMENT_KE: Record<FiveElement, FiveElement> = {
  木: '土', 土: '水', 水: '火', 火: '金', 金: '木',
}

export function relationOf(a: FiveElement, b: FiveElement):
  | 'SHENG'
  | 'KE'
  | 'BI_HE'
  | 'BEI_SHENG'
  | 'BEI_KE' {
  if (a === b) return 'BI_HE'
  if (ELEMENT_SHENG[a] === b) return 'SHENG'
  if (ELEMENT_KE[a] === b) return 'KE'
  if (ELEMENT_SHENG[b] === a) return 'BEI_SHENG'
  return 'BEI_KE'
}
