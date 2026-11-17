/**
 * 斗首五行（参考层规则包）。
 *
 * 为什么是「参考层」而不是第六派：
 *   1. 规格 §5 的五派输出契约是逐字要求（报告分节、Agent prompt、权重表都按五派写死），
 *      擅自加第六派会同时改写这三处契约；
 *   2. 斗首的吉凶强度（贪狼/廉贞各本不一）尚未人工考证，
 *      让它直接参与仲裁加权等于把未考证口径塞进结论。
 * 因此本包**不进 SCHOOL_IDS / 不进仲裁权重**，由界面单列为「参考层」，
 * 与五派并列展示但明确标注不参与合议。
 *
 * 斗首五行 ≠ 正五行（新手最易错处）：甲山正五行属木，斗首属水；
 * 甲干正五行属木，化气属土。两张表必须分开建模，本文件只做斗首一张。
 */
import type { FiveElement } from '../../types'
import type { DayFacts, ZeriContext } from '../facts'
import { ELEMENT_KE, ELEMENT_SHENG } from '../../constants/nayin60'
import { ZHI } from '../../constants/nayin60'

/** 二十四山斗首五行：壬子巽巳辛戌土／艮寅丁未木／癸丑丙午乾亥火／坤申甲卯水／乙庚辰酉金 */
export const DOU_SHOU_ELEMENT: Record<string, FiveElement> = {
  壬: '土', 子: '土', 巽: '土', 巳: '土', 辛: '土', 戌: '土',
  艮: '木', 寅: '木', 丁: '木', 未: '木',
  癸: '火', 丑: '火', 丙: '火', 午: '火', 乾: '火', 亥: '火',
  坤: '水', 申: '水', 甲: '水', 卯: '水',
  乙: '金', 庚: '金', 辰: '金', 酉: '金',
}

/** 十干化气（五运）：甲己土、乙庚金、丙辛水、丁壬木、戊癸火 */
export const HUAQI_ELEMENT: Record<string, FiveElement> = {
  甲: '土', 己: '土', 乙: '金', 庚: '金', 丙: '水',
  辛: '水', 丁: '木', 壬: '木', 戊: '火', 癸: '火',
}

/** 星名 → 别称（口诀用别称：贪官/廉子/武财/破鬼） */
export const STAR_ALIAS = {
  元辰: '元辰',
  贪狼: '贪官',
  廉贞: '廉子',
  武曲: '武财',
  破军: '破鬼',
} as const

export type DouShouStar = keyof typeof STAR_ALIAS

/** 番化诀：元辰化元辰、武财化贪官、贪官化破鬼、破鬼化廉子、廉子化武财 */
export const FANHUA: Record<string, string> = {
  元辰: '元辰',
  武财: '贪官',
  贪官: '破鬼',
  破鬼: '廉子',
  廉子: '武财',
}

/** 五行寄生十二宫的长生支（土取「申」，土寄坤口径） */
const CHANGSHENG: Record<FiveElement, string> = {
  木: '亥', 火: '寅', 金: '巳', 水: '申', 土: '申',
}

const STAGES = ['长生', '沐浴', '冠带', '临官', '帝旺', '衰', '病', '死', '墓', '绝', '胎', '养'] as const
const DEWEI_STAGES = new Set(['长生', '冠带', '临官', '帝旺'])

export interface DouShouStemResult {
  position: '年' | '月' | '日' | '时'
  gan: string
  huaqi: FiveElement | null
  relation: '同我' | '生我' | '我生' | '我克' | '克我' | null
  star: DouShouStar | null
  alias: string | null
  fanhua: string | null
  stage: string | null
  dewei: boolean | null
}

export interface DouShouResult {
  shanElement: FiveElement | null
  shanStage: string | null
  shanDewei: boolean | null
  stems: DouShouStemResult[]
  counts: Record<DouShouStar, number>
  /** 三重元辰 */
  sanyuan: boolean
  /** 三重武财 */
  sanwu: boolean
  reviewNotes: string[]
}

function starOf(wo: FiveElement, ta: FiveElement): { relation: DouShouStemResult['relation']; star: DouShouStar } {
  if (wo === ta) return { relation: '同我', star: '元辰' }
  if (ELEMENT_SHENG[ta] === wo) return { relation: '生我', star: '贪狼' }
  if (ELEMENT_SHENG[wo] === ta) return { relation: '我生', star: '廉贞' }
  if (ELEMENT_KE[wo] === ta) return { relation: '我克', star: '武曲' }
  return { relation: '克我', star: '破军' }
}

function stageOf(element: FiveElement, monthBranch: string): string | null {
  const start = CHANGSHENG[element]
  const si = ZHI.indexOf(start as (typeof ZHI)[number])
  const mi = ZHI.indexOf(monthBranch as (typeof ZHI)[number])
  if (si < 0 || mi < 0) return null
  return STAGES[(mi - si + 12) % 12]
}

/**
 * 计算斗首结果。纯查表 + 生克，无天文依赖。
 * @param monthBranch 节气月支（斗首以月令论得位）
 */
export function evaluateDouShou(facts: DayFacts, ctx: ZeriContext): DouShouResult {
  const shanElement = DOU_SHOU_ELEMENT[ctx.mountShan] ?? null
  const monthBranch = facts.monthBranch
  const reviewNotes: string[] = [
    '贪狼（贪官）与廉贞（廉子）的吉凶各本不一，本包只给星名与生克关系，不断言吉凶',
    '番化链仅作参考，不参与任何评分',
    '土的长生位取「申」（土寄坤），另有「寅」（土寄艮）一说，见 lineageNote',
  ]

  const pillars = facts.pillars
  const entries: Array<['年' | '月' | '日' | '时', string | null]> = [
    ['年', pillars.year.stem],
    ['月', pillars.month.stem],
    ['日', pillars.day.stem],
    ['时', pillars.hour?.stem ?? null],
  ]

  const counts: Record<DouShouStar, number> = { 元辰: 0, 贪狼: 0, 廉贞: 0, 武曲: 0, 破军: 0 }
  const stems: DouShouStemResult[] = entries.map(([position, gan]) => {
    if (!gan || !shanElement) {
      return { position, gan: gan ?? '', huaqi: null, relation: null, star: null, alias: null, fanhua: null, stage: null, dewei: null }
    }
    const huaqi = HUAQI_ELEMENT[gan] ?? null
    if (!huaqi) {
      return { position, gan, huaqi: null, relation: null, star: null, alias: null, fanhua: null, stage: null, dewei: null }
    }
    const { relation, star } = starOf(shanElement, huaqi)
    const alias = STAR_ALIAS[star]
    const stage = stageOf(huaqi, monthBranch)
    counts[star] += 1
    return {
      position,
      gan,
      huaqi,
      relation,
      star,
      alias,
      fanhua: FANHUA[alias] ?? null,
      stage,
      dewei: stage ? DEWEI_STAGES.has(stage) : null,
    }
  })

  const shanStage = shanElement ? stageOf(shanElement, monthBranch) : null

  return {
    shanElement,
    shanStage,
    shanDewei: shanStage ? DEWEI_STAGES.has(shanStage) : null,
    stems,
    counts,
    sanyuan: counts.元辰 >= 3,
    sanwu: counts.武曲 >= 3,
    reviewNotes,
  }
}

/** 一句话摘要，供卡片与报告复用（同源，避免两处各写一套说法）。 */
export function douShouSummary(result: DouShouResult): string {
  if (!result.shanElement) return '坐山不在斗首五行表内，本层不判'
  const parts = [`山家斗首${result.shanElement}`]
  if (result.sanyuan) parts.push('三元格')
  if (result.sanwu) parts.push('三武格')
  const stars = (Object.keys(result.counts) as DouShouStar[])
    .filter((star) => result.counts[star] > 0)
    .map((star) => `${STAR_ALIAS[star]}${result.counts[star]}`)
  if (stars.length) parts.push(stars.join('·'))
  return parts.join('｜')
}
