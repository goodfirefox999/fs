/**
 * 董公择日所需数据表。
 * 重点更正：煞贡/直星/人专并非「脱离月份的固定六十甲子表」，
 * 而是《九天上圣秘传金符经》九星轮值——九星顺序固定，甲子日的起点随月组变化。
 */
import { GAN, ZHI } from '../../constants/nayin60'

/** 九星顺序（金符经轮值次序）。 */
export const NINE_STARS = [
  '妖星', '惑星', '禾刀', '煞贡', '直星', '卜木', '角己', '人专', '立早',
] as const

export type DongGongStar = (typeof NINE_STARS)[number]

/**
 * 三吉星：煞贡、直星、人专。
 *
 * 金符经总诀：「煞贡一星为大吉，直星行事可人心，卜木角己为凶恶，人专诸事并清宁。
 * 立早妖星惑星共，禾刀四曜有灾刑。」——立早与妖星、惑星、禾刀同列凶星，不属吉星。
 * （旧注释写成「四吉星含立早」，与实现和诀文都不符，已更正。）
 */
export const THREE_LUCKY_STARS: DongGongStar[] = ['煞贡', '直星', '人专']

/** 其余六星；本包对它们是否降分未核实到可靠出处，不虚构分值。 */
export const SIX_CAUTION_STARS: DongGongStar[] = [
  '妖星', '惑星', '禾刀', '卜木', '角己', '立早',
]

/** 月组：四孟（寅申巳亥）、四仲（子午卯酉）、四季（辰戌丑未）。 */
export type MonthGroup = 'MENG' | 'ZHONG' | 'JI'

export const MONTH_GROUP_LABELS: Record<MonthGroup, string> = {
  MENG: '四孟月（寅申巳亥）',
  ZHONG: '四仲月（子午卯酉）',
  JI: '四季月（辰戌丑未）',
}

const MENG_BRANCHES = ['寅', '申', '巳', '亥']
const ZHONG_BRANCHES = ['子', '午', '卯', '酉']

export function monthGroupOf(monthBranch: string): MonthGroup {
  if (MENG_BRANCHES.includes(monthBranch)) return 'MENG'
  if (ZHONG_BRANCHES.includes(monthBranch)) return 'ZHONG'
  return 'JI'
}

/** 甲子日所值之星：孟起妖星、仲起惑星、季起禾刀。 */
const START_INDEX: Record<MonthGroup, number> = { MENG: 0, ZHONG: 1, JI: 2 }

export function jiaZiIndex(ganZhi: string): number {
  const g = GAN.indexOf(ganZhi[0] as (typeof GAN)[number])
  const z = ZHI.indexOf(ganZhi[1] as (typeof ZHI)[number])
  if (g < 0 || z < 0) return -1
  // 求满足 n≡g (mod 10) 且 n≡z (mod 12) 的 0..59
  for (let n = 0; n < 60; n++) {
    if (n % 10 === g && n % 12 === z) return n
  }
  return -1
}

/** 六十甲子逐日展开：数组下标即六十甲子序（0=甲子），值为该月组下所值之星。 */
export function nineStarTable(group: MonthGroup): DongGongStar[] {
  const offset = START_INDEX[group]
  return Array.from({ length: 60 }, (_, index) => NINE_STARS[(offset + index) % 9])
}

/** O(1) 查星：不进表、不构造数组，供逐日扫描复用。 */
export function dongGongStarOf(monthBranch: string, dayGanZhi: string): DongGongStar {
  const group = monthGroupOf(monthBranch)
  const index = jiaZiIndex(dayGanZhi)
  if (index < 0) throw new Error(`无效干支: ${dayGanZhi}`)
  return NINE_STARS[(START_INDEX[group] + index) % 9]
}

/**
 * 规格给的表为「正月亥、二月丑、三月卯、四月巳、五月未、六月酉、七月亥、八月丑、九月卯、十月巳、十一月未、十二月酉」，
 * 即正月起亥、逐月加二。按节气月支索引（寅月＝正月）重排为十二位。
 */
export const GOU_CHEN_BY_MONTH_BRANCH: Record<string, string> = {
  寅: '亥', 卯: '丑', 辰: '卯', 巳: '巳', 午: '未', 未: '酉',
  申: '亥', 酉: '丑', 戌: '卯', 亥: '巳', 子: '未', 丑: '酉',
}

export function isGouChenHeiDao(monthBranch: string, dayBranch: string): boolean {
  return GOU_CHEN_BY_MONTH_BRANCH[monthBranch] === dayBranch
}

/** 安床忌宿（董公口径：心昴箕娄奎尾参危 + 四离四绝）。 */
export const AN_CHUANG_AVOID_XIU = ['心', '昴', '箕', '娄', '奎', '尾', '参', '危']

/**
 * 金神七煞（《协纪辨方书》卷三引《堪舆经》，曹震圭以年干五虎遁定）。
 * 天金神＝五虎遁逢庚辛之日；地金神＝旬内纳音属金之日。官书按语本身存疑。
 */
export const JIN_SHEN_TIAN: Record<string, string[]> = {
  甲: ['午', '未'], 己: ['午', '未'],
  乙: ['辰', '巳'], 庚: ['辰', '巳'],
  丙: ['子', '丑', '寅', '卯'], 辛: ['子', '丑', '寅', '卯'],
  丁: ['戌', '亥'], 壬: ['戌', '亥'],
  戊: ['申', '酉'], 癸: ['申', '酉'],
}

/** 地金神（纳音金日）补足的部分，与天金神合起来即「午未申酉」全式。 */
export const JIN_SHEN_DI: Record<string, string[]> = {
  甲: ['申', '酉'], 己: ['申', '酉'],
  乙: [], 庚: [],
  丙: ['午', '未'], 辛: ['午', '未'],
  丁: ['寅', '卯'], 壬: ['寅', '卯'],
  戊: ['子', '丑'], 癸: ['子', '丑'],
}

/** 《董公选要览》另一系统：二十八宿金神七煞（重名不同系统，不与年干式混用）。 */
export const JIN_SHEN_XIU = ['角', '亢', '奎', '娄', '牛', '鬼', '星']
