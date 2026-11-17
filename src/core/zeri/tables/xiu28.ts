/**
 * 天星择日数据：开禧宿度（不等宽）、宿—山对应、岁差校正。
 * 规格禁止用「每宿 360/28 度」的均分近似，这里一律用不等宽宿度并按年校正。
 */
import { normalizeDeg } from '../../constants/shan24'

/** 开禧宿度（古度，太=3/4、半=1/2、少=1/4），四象合计 365.25 古度。 */
export const KAI_XI_DU: Array<{ name: string; du: number }> = [
  { name: '角', du: 12.75 }, { name: '亢', du: 9.75 }, { name: '氐', du: 16.25 },
  { name: '房', du: 5.75 }, { name: '心', du: 6 }, { name: '尾', du: 18 }, { name: '箕', du: 9.5 },
  { name: '斗', du: 22.75 }, { name: '牛', du: 7 }, { name: '女', du: 11 },
  { name: '虚', du: 9.25 }, { name: '危', du: 16 }, { name: '室', du: 18.25 }, { name: '壁', du: 9.75 },
  { name: '奎', du: 18 }, { name: '娄', du: 12.75 }, { name: '胃', du: 15.25 }, { name: '昴', du: 11 },
  { name: '毕', du: 16.5 }, { name: '觜', du: 0.5 }, { name: '参', du: 9.5 },
  { name: '井', du: 30.25 }, { name: '鬼', du: 2.5 }, { name: '柳', du: 13.5 },
  { name: '星', du: 6.75 }, { name: '张', du: 17.75 }, { name: '翼', du: 20.25 }, { name: '轸', du: 18.75 },
]

/** 古度 → 今度：周天 365.25 古度对应 360°。 */
export const GU_DU_TO_DEG = 360 / 365.25

/** 开禧历元（1204 年）。 */
export const KAI_XI_EPOCH_YEAR = 1204

/** 总岁差：每年 50.29 角秒；传统择日多用「72 年 1 度」，两者差约 1%。 */
export const PRECESSION_ARCSEC_PER_YEAR = 50.29
export const TRADITIONAL_PRECESSION_YEARS_PER_DEG = 72

export function precessionDegForYear(
  year: number,
  model: 'MODERN' | 'TRADITIONAL' = 'MODERN'
): number {
  const driftYears = year - KAI_XI_EPOCH_YEAR
  return model === 'MODERN'
    ? (driftYears * PRECESSION_ARCSEC_PER_YEAR) / 3600
    : driftYears / TRADITIONAL_PRECESSION_YEARS_PER_DEG
}

export interface XiuBound {
  name: string
  /** 该宿起始黄经（今度，已按年份做岁差平移） */
  start: number
  /** 该宿跨度（今度） */
  span: number
}

/**
 * 按用事年给出二十八宿的黄经区间。
 * 说明：平移只补「宿位」，不补「宿宽」——各时代距度本身不同，严格做法需用距星坐标重算，
 * 因此本表输出必须伴随 needsHumanReview。
 */
export function xiuBoundsForYear(year: number): XiuBound[] {
  const shift = precessionDegForYear(year)
  let cursor = shift
  return KAI_XI_DU.map((item) => {
    const span = item.du * GU_DU_TO_DEG
    const bound: XiuBound = { name: item.name, start: normalizeDeg(cursor), span }
    cursor += span
    return bound
  })
}

/** 角宿起于春分点（黄经 0°）的传统设定，加岁差平移。 */
export function xiuOfLongitude(
  longitude: number,
  year: number
): { name: string; offset: number; span: number; margin: number } | null {
  const bounds = xiuBoundsForYear(year)
  const value = normalizeDeg(longitude)
  for (const bound of bounds) {
    const offset = normalizeDeg(value - bound.start)
    if (offset < bound.span) {
      return {
        name: bound.name,
        offset,
        span: bound.span,
        margin: Math.min(offset, bound.span - offset),
      }
    }
  }
  return null
}

/** 等分式「二十八宿配二十四山」（由巽山起，四山重宿），天星择日刊本通行表。 */
export const XIU_TO_MOUNTAIN: Record<string, string> = {
  角: '巽', 亢: '辰', 氐: '乙', 房: '卯', 心: '卯', 尾: '甲', 箕: '寅',
  斗: '艮', 牛: '丑', 女: '癸', 虚: '子', 危: '子', 室: '壬', 壁: '亥',
  奎: '乾', 娄: '戌', 胃: '辛', 昴: '酉', 毕: '酉', 觜: '庚', 参: '申',
  井: '坤', 鬼: '未', 柳: '丁', 星: '午', 张: '午', 翼: '丙', 轸: '巳',
}

export const XIU_NAMES = KAI_XI_DU.map((item) => item.name)
