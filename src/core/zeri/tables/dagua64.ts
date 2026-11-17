/**
 * 玄空大卦数据：先天六十四卦圆图、卦运、抽爻换象判定。
 * 全部由规则生成，不手抄长表；tests/dagua.test.ts 用刊本卦序反查生成结果。
 */
import { normalizeDeg } from '../../constants/shan24'

/** 经卦：三爻，(下,中,上)，1 阳 0 阴。 */
export interface Trigram {
  name: string
  symbol: string
  lines: [number, number, number]
  /**
   * 玄空大卦卦数（洛书配先天卦：乾9兑4离3震8巽2坎7艮6坤1，五居中宫无卦）。
   * 注意：这不是伏羲先天卦序数（乾1兑2离3震4巽5坎6艮7坤8），两者不可混用；
   * 「无五运」的依据是本数的 5 属中宫无卦，而非伏羲序缺位。
   */
  guaShu: number
  /** 玄空大卦卦运（1–4、6–9） */
  yun: number
  /** 该运所管年数：父母卦三爻按阳爻 9 年、阴爻 6 年相加 */
  years: number
}

/**
 * 八卦属性。`guaShu` 为先天洛书数（乾9兑4离3震8巽2坎7艮6坤1）；
 * `yun` 在本实现中与 `guaShu` 取同一值，`years` 为阳爻 9 年 / 阴爻 6 年相加的运年期
 * （乾 27、坤 18、其余 21 或 24）。
 *
 * 注意：**「卦气」与「卦运」在流派上是两个概念**——卦气取外卦洛书数，
 * 卦运另有一套求法（父母卦、爻变定运等）。本表把两者取同值，
 * 是因为本仓库只核实到「洛书数」这一层，未能核实各派一致的卦运求法，
 * 故在 `guaYun()` 与规则包里显式标注为需人工复核，不冒充已定论。
 */
export const TRIGRAMS: Trigram[] = [
  { name: '乾', symbol: '☰', lines: [1, 1, 1], guaShu: 9, yun: 9, years: 27 },
  { name: '兑', symbol: '☱', lines: [1, 1, 0], guaShu: 4, yun: 4, years: 24 },
  { name: '离', symbol: '☲', lines: [1, 0, 1], guaShu: 3, yun: 3, years: 24 },
  { name: '震', symbol: '☳', lines: [1, 0, 0], guaShu: 8, yun: 8, years: 21 },
  { name: '巽', symbol: '☴', lines: [0, 1, 1], guaShu: 2, yun: 2, years: 24 },
  { name: '坎', symbol: '☵', lines: [0, 1, 0], guaShu: 7, yun: 7, years: 21 },
  { name: '艮', symbol: '☶', lines: [0, 0, 1], guaShu: 6, yun: 6, years: 21 },
  { name: '坤', symbol: '☷', lines: [0, 0, 0], guaShu: 1, yun: 1, years: 18 },
]

const BY_LINES = new Map(TRIGRAMS.map((item) => [item.lines.join(''), item]))

export function trigramByLines(lines: [number, number, number]): Trigram {
  const found = BY_LINES.get(lines.join(''))
  if (!found) throw new Error(`无法识别的三爻组合: ${lines.join('')}`)
  return found
}

/** 别卦（六爻卦）：下卦 + 上卦 + 周易卦名。 */
export interface Hexagram {
  index: number
  lower: Trigram
  upper: Trigram
  name: string
  /** 六爻（初爻→上爻） */
  lines: number[]
}

/** 周易六十四卦卦名（上卦 × 下卦），与《原本周易本义》伏羲六十四卦方位图一致。 */
const HEXAGRAM_NAMES: Record<string, string> = {
  乾坤: '否', 坤乾: '泰', 震乾: '大壮', 巽乾: '小畜', 坎乾: '需', 离乾: '大有', 艮乾: '大畜', 兑乾: '夬',
  乾震: '无妄', 坤震: '复', 震震: '震', 巽震: '益', 坎震: '屯', 离震: '噬嗑', 艮震: '颐', 兑震: '随',
  乾离: '同人', 坤离: '明夷', 震离: '丰', 巽离: '家人', 坎离: '既济', 离离: '离', 艮离: '贲', 兑离: '革',
  乾兑: '履', 坤兑: '临', 震兑: '归妹', 巽兑: '中孚', 坎兑: '节', 离兑: '睽', 艮兑: '损', 兑兑: '兑',
  乾巽: '姤', 坤巽: '升', 震巽: '恒', 巽巽: '巽', 坎巽: '井', 离巽: '鼎', 艮巽: '蛊', 兑巽: '大过',
  乾坎: '讼', 坤坎: '师', 震坎: '解', 巽坎: '涣', 坎坎: '坎', 离坎: '未济', 艮坎: '蒙', 兑坎: '困',
  乾艮: '遁', 坤艮: '谦', 震艮: '小过', 巽艮: '渐', 坎艮: '蹇', 离艮: '旅', 艮艮: '艮', 兑艮: '咸',
  坤坤: '坤', 乾乾: '乾', 震坤: '豫', 巽坤: '观', 坎坤: '比', 离坤: '晋', 艮坤: '剥', 兑坤: '萃',
}

function hexagramName(upper: string, lower: string): string {
  const key = `${upper}${lower}`
  const found = HEXAGRAM_NAMES[key]
  if (!found || found.endsWith('?')) {
    throw new Error(`卦名表缺少 上${upper}下${lower}，禁止臆造卦名`)
  }
  return found
}

/**
 * 先天六十四卦圆图：复卦起 0°（子山中线），顺时针，每卦 5.625°、每爻 0.9375°。
 * 左半（0°–180°）阳息：下卦依次 震离兑乾，上卦依次 坤艮坎巽震离兑乾；
 * 右半（180°–360°）阴消：下卦依次 巽坎艮坤，上卦依次 乾兑离震巽坎艮坤。
 */
const LEFT_LOWER = ['震', '离', '兑', '乾']
const LEFT_UPPER = ['坤', '艮', '坎', '巽', '震', '离', '兑', '乾']
const RIGHT_LOWER = ['巽', '坎', '艮', '坤']
const RIGHT_UPPER = ['乾', '兑', '离', '震', '巽', '坎', '艮', '坤']

export const DEGREES_PER_HEXAGRAM = 360 / 64
export const DEGREES_PER_LINE = 360 / 384

function buildSequence(): Hexagram[] {
  const list: Hexagram[] = []
  const push = (upperName: string, lowerName: string) => {
    const lower = TRIGRAMS.find((item) => item.name === lowerName) as Trigram
    const upper = TRIGRAMS.find((item) => item.name === upperName) as Trigram
    list.push({
      index: list.length,
      lower,
      upper,
      name: hexagramName(upper.name, lower.name),
      lines: [...lower.lines, ...upper.lines],
    })
  }
  for (const lower of LEFT_LOWER) {
    for (const upper of LEFT_UPPER) push(upper, lower)
  }
  for (const lower of RIGHT_LOWER) {
    for (const upper of RIGHT_UPPER) push(upper, lower)
  }
  return list
}

export const HEXAGRAMS: Hexagram[] = buildSequence()

/**
 * 爻位排列方向为流派分歧点：
 * ASC 自卦界顺行初爻→上爻；DESC 自卦界顺行上爻→初爻（部分刊例即按此读数）。
 * 默认 ASC，调用方必须把所用口径写进输出，不得静默切换。
 */
export type YaoOrder = 'ASC' | 'DESC'

const LINE_NAMES = ['初爻', '二爻', '三爻', '四爻', '五爻', '上爻']

export function hexagramAt(
  deg: number,
  yaoOrder: YaoOrder = 'ASC'
): { hexagram: Hexagram; lineIndex: number; lineName: string; yaoOrder: YaoOrder } {
  const value = normalizeDeg(deg)
  const index = Math.floor(value / DEGREES_PER_HEXAGRAM) % 64
  const inside = value - index * DEGREES_PER_HEXAGRAM
  const raw = Math.min(5, Math.floor(inside / DEGREES_PER_LINE))
  const lineIndex = yaoOrder === 'ASC' ? raw : 5 - raw
  return {
    hexagram: HEXAGRAMS[index],
    lineIndex,
    lineName: LINE_NAMES[lineIndex],
    yaoOrder,
  }
}

/** 抽爻换象：本卦某爻阴阳互变后的变卦。 */
export function changedHexagram(hexagram: Hexagram, lineIndex: number): Hexagram {
  const lines = hexagram.lines.slice()
  lines[lineIndex] ^= 1
  const lower = trigramByLines([lines[0], lines[1], lines[2]] as [number, number, number])
  const upper = trigramByLines([lines[3], lines[4], lines[5]] as [number, number, number])
  return {
    index: -1,
    lower,
    upper,
    name: hexagramName(upper.name, lower.name),
    lines,
  }
}

/** 卦运：上下卦对应爻异或所得经卦的洛书运数（无五运）。 */
/**
 * 卦运：本实现取「内卦与外卦逐爻相错（异或）」所得卦的洛书数。
 *
 * 这是**一种**口径，并非单一通行口径：
 * - 另有「父母卦」体系（九运卦上爻不变、二运卦初爻不变、三运卦二爻不变、四运卦三爻不变）；
 * - 也有直接取外卦洛书数为卦气、另以爻变定卦运者。
 *
 * 本仓库未核实到各派公认的同一求法，因此：
 * 1. 保留当前实现，但在规则包里把「卦运当旺」标为 `needsHumanReview`；
 * 2. 不把卦气与卦运合并成单一「吉凶分」；
 * 3. 若要改口径，必须同时改 `TRIGRAMS.yun` 的语义并补对拍用例，不能只改这一处。
 */
export function guaYun(hexagram: Hexagram): { trigram: Trigram; yun: number } {
  const lines = hexagram.lines
  const xored = [
    lines[0] ^ lines[3],
    lines[1] ^ lines[4],
    lines[2] ^ lines[5],
  ] as [number, number, number]
  const trigram = trigramByLines(xored)
  return { trigram, yun: trigram.yun }
}

/** 河图生成数对（丁爻）与合五/合十/合十五（财爻）。 */
const SHENG_CHENG_PAIRS: Array<[number, number]> = [
  [1, 6], [2, 7], [3, 8], [4, 9],
]

export function yaoRole(
  changed: Hexagram
): { ding: boolean; wealth: boolean; kinds: string[] } {
  const upper = changed.upper.guaShu
  const lower = changed.lower.guaShu
  const sum = upper + lower
  const ding = SHENG_CHENG_PAIRS.some(([a, b]) => (a === upper && b === lower) || (a === lower && b === upper))
  let kind = ''
  if (sum === 5) kind = '合五'
  else if (sum === 10) kind = '合十'
  else if (sum === 15) kind = '合十五'
  return {
    ding,
    wealth: sum === 5 || sum === 10 || sum === 15,
    kinds: [ding ? '生成数' : null, kind || null].filter(Boolean) as string[],
  }
}

/**
 * 元运年表：以 1864 年（上元甲子）起，按 坤18 / 巽离兑24 / 震艮坎21 / 乾27 顺行，循环 180 年。
 * 明确不采用「每运 20 年」的洛书九运简化模型。
 */
// 出处与流派分歧见 sources.ts 的 DAGUA_YUN_TABLE（verification_status: unverified）。
const YUN_ORDER: Array<{ yun: number; years: number }> = [
  { yun: 1, years: 18 },
  { yun: 2, years: 24 },
  { yun: 3, years: 24 },
  { yun: 4, years: 24 },
  { yun: 6, years: 21 },
  { yun: 7, years: 21 },
  { yun: 8, years: 21 },
  { yun: 9, years: 27 },
]

export interface YunSpan {
  yun: number
  startYear: number
  endYear: number
  years: number
}

export function yunSpans(cycleStart: number): YunSpan[] {
  let cursor = cycleStart
  return YUN_ORDER.map((item) => {
    const span: YunSpan = {
      yun: item.yun,
      startYear: cursor,
      endYear: cursor + item.years - 1,
      years: item.years,
    }
    cursor += item.years
    return span
  })
}

export const YUN_CYCLE_YEARS = YUN_ORDER.reduce((sum, item) => sum + item.years, 0)

export function yunOfYear(year: number): YunSpan & { cycleStart: number } {
  const offset = ((year - 1864) % YUN_CYCLE_YEARS + YUN_CYCLE_YEARS) % YUN_CYCLE_YEARS
  const cycleStart = year - offset
  const spans = yunSpans(cycleStart)
  const found = spans.find((span) => year >= span.startYear && year <= span.endYear) as YunSpan
  return { ...found, cycleStart }
}
