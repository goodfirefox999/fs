/**
 * 三合禄马贵人所需的基础表。
 * 禄神、天乙贵人、驿马为通行口诀；二十四山贵人到方表按规格提供的纳甲口径实现，
 * 与正五行派存在分歧，已在 needsHumanReview 中强制标注。
 */
import type { FiveElement } from '../../types'

export const LU_SHEN: Record<string, string> = {
  甲: '寅', 乙: '卯', 丙: '巳', 丁: '午', 戊: '巳', 己: '午',
  庚: '申', 辛: '酉', 壬: '亥', 癸: '子',
}

/** 天乙贵人：甲戊庚牛羊，乙己鼠猴乡，丙丁猪鸡位，壬癸兔蛇藏，六辛逢虎马。 */
export const TIAN_YI_GUI_REN: Record<string, string[]> = {
  甲: ['丑', '未'], 戊: ['丑', '未'], 庚: ['丑', '未'],
  乙: ['子', '申'], 己: ['子', '申'],
  丙: ['亥', '酉'], 丁: ['亥', '酉'],
  壬: ['卯', '巳'], 癸: ['卯', '巳'],
  辛: ['寅', '午'],
}

export const YI_MA: Record<string, string> = {
  申: '寅', 子: '寅', 辰: '寅',
  寅: '申', 午: '申', 戌: '申',
  巳: '亥', 酉: '亥', 丑: '亥',
  亥: '巳', 卯: '巳', 未: '巳',
}

/** 规格附录：二十四山贵人到方速查表（纳甲口径）。戊己不用，故仅八字有值。 */
export const MOUNTAIN_GUI_REN_FANG: Record<string, string[]> = {
  甲: ['丑', '未'], 乙: ['子', '申'], 丙: ['亥', '酉'], 丁: ['酉', '亥'],
  庚: ['午', '丑'], 辛: ['寅', '午'], 壬: ['巳', '卯'], 癸: ['卯', '巳'],
}

/** 干支山 → 纳甲所属干：乾坤艮巽按纳甲归干，地支山取本支。 */
export const GONG_NA_JIA: Record<string, string[]> = {
  乾: ['甲', '壬'], 坤: ['乙', '癸'], 艮: ['丙'], 巽: ['辛'],
}

/** 地支藏干（子藏癸、丑藏癸辛己……），用于把贵人表扩展到十二地支山。 */
export const BRANCH_HIDDEN_STEMS: Record<string, string[]> = {
  子: ['癸'], 丑: ['癸', '辛', '己'], 寅: ['甲', '丙', '戊'], 卯: ['乙'],
  辰: ['乙', '戊', '癸'], 巳: ['丙', '庚', '戊'], 午: ['丁', '己'], 未: ['丁', '乙', '己'],
  申: ['庚', '壬', '戊'], 酉: ['辛'], 戌: ['辛', '丁', '戊'], 亥: ['壬', '甲'],
}

/**
 * 二十四山贵人到方：干山与乾坤艮巽用纳甲，地支山取本支藏干；
 * 规格明确「戊己不用」，故藏干中的戊己不参与取贵人。
 */
export function mountainGuiRenFang(mountain: string): string[] | null {
  const direct = MOUNTAIN_GUI_REN_FANG[mountain]
  if (direct) return direct
  const na = GONG_NA_JIA[mountain]
  const hidden = BRANCH_HIDDEN_STEMS[mountain]
  const stems = na ?? hidden
  if (!stems) return null
  const list = new Set<string>()
  for (const stem of stems) {
    if (stem === '戊' || stem === '己') continue
    for (const item of TIAN_YI_GUI_REN[stem] ?? []) list.add(item)
  }
  return list.size ? Array.from(list) : null
}

/** 二十四山正五行（《地理五诀》通行口径，与本项目 shan24 表同源）。 */
export const MOUNTAIN_ZHENG_WU_XING: Record<string, FiveElement> = {
  壬: '水', 子: '水', 癸: '水', 丑: '土', 艮: '土', 寅: '木',
  甲: '木', 卯: '木', 乙: '木', 辰: '土', 巽: '木', 巳: '火',
  丙: '火', 午: '火', 丁: '火', 未: '土', 坤: '土', 申: '金',
  庚: '金', 酉: '金', 辛: '金', 戌: '土', 乾: '金', 亥: '水',
}

/**
 * 洪范（斗首）五行：与正五行归属不同，两派不可混用。
 * 口诀「甲寅辰巽大江水，戌坎申辛水一同，艮震巳山原来木，丙午壬乙火炎中，
 * 酉丁乾亥为金位，丑癸坤庚未土中」。
 */
export const MOUNTAIN_HONG_FAN_WU_XING: Record<string, FiveElement> = {
  甲: '水', 寅: '水', 辰: '水', 巽: '水', 戌: '水', 子: '水', 申: '水', 辛: '水',
  艮: '木', 卯: '木', 巳: '木',
  午: '火', 壬: '火', 丙: '火', 乙: '火',
  酉: '金', 丁: '金', 乾: '金', 亥: '金',
  丑: '土', 癸: '土', 坤: '土', 庚: '土', 未: '土',
}

/** 洪范五行按元素分组，便于人工核对总数。 */
export const HONG_FAN_GROUPS: Record<FiveElement, string[]> = {
  水: ['甲', '寅', '辰', '巽', '戌', '子', '申', '辛'],
  木: ['艮', '卯', '巳'],
  火: ['午', '壬', '丙', '乙'],
  金: ['酉', '丁', '乾', '亥'],
  土: ['丑', '癸', '坤', '庚', '未'],
}

/** 天干十二长生（生旺死绝表），仅用于补龙/扶山的旺衰判定。 */
const CHANG_SHENG_ORDER = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养']

/** 阳干顺行、阴干逆行，起于长生位。 */
const CHANG_SHENG_START: Record<string, string> = {
  甲: '亥', 丙: '寅', 戊: '寅', 庚: '巳', 壬: '申',
  乙: '午', 丁: '酉', 己: '酉', 辛: '子', 癸: '卯',
}

const BRANCHES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

export function changShengOf(stem: string, branch: string): string {
  const start = CHANG_SHENG_START[stem]
  if (!start) return '未知'
  const startIndex = BRANCHES.indexOf(start)
  const branchIndex = BRANCHES.indexOf(branch)
  if (startIndex < 0 || branchIndex < 0) return '未知'
  const yang = ['甲', '丙', '戊', '庚', '壬'].includes(stem)
  const steps = yang
    ? (branchIndex - startIndex + 12) % 12
    : (startIndex - branchIndex + 12) % 12
  return CHANG_SHENG_ORDER[steps]
}

export const WANG_PHASES = ['长生', '冠带', '临官', '帝旺', '养']
export const WEAK_PHASES = ['病', '死', '墓', '绝']
