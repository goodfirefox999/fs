import type { ThingBehavior, ZeRiCategory } from '../types'

// 数据源：《钦定协纪辨方书》起例，按 cnlunar（MIT, Copyright (c) 2025 OPN48）
// 的 godType='8char' 口径移植，并用其 2020–2035 年输出做过逐日校验。
// 月序一律用节气月支（子＝农历十一月建），季节按三合局：0 春 1 夏 2 秋 3 冬。

export type GodLuck = 'GOOD' | 'BAD'
export type MatchKind = 'BRANCH' | 'STEM' | 'GANZHI' | 'IN_GANZHI'
export type GodSource =
  | 'MONTH'
  | 'SEASON'
  | 'YEAR_STEM'
  | 'DAY_LIST'
  | 'BRANCH_SET'
  | 'SI_LI_WAIT'
  | 'MONTH_SELF'

export interface XieJiGod {
  name: string
  luck: GodLuck
  source: GodSource
  /** MONTH/YEAR_STEM 按 12/10 位取值，SEASON 按 4 位取值，DAY_LIST 为干支白名单 */
  table: string[]
  match: MatchKind
  yi: string[]
  ji: string[]
}

export const MONTH_BRANCHES = ['子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥']

export const XIEJI_GODS: XieJiGod[] = [
  // ── 凶煞（等第表所需）──
  { name: '月煞', luck: 'BAD', source: 'MONTH', table: ['未', '辰', '丑', '戌', '未', '辰', '丑', '戌', '未', '辰', '丑', '戌'], match: 'BRANCH', yi: [], ji: ['修造', '搬移', '安床', '破土', '安葬', '启攒'] },
  { name: '月刑', luck: 'BAD', source: 'MONTH', table: ['卯', '戌', '巳', '子', '辰', '申', '午', '丑', '寅', '酉', '未', '亥'], match: 'BRANCH', yi: [], ji: ['修造', '竖柱上梁', '搬移', '安床', '破土', '安葬', '启攒'] },
  { name: '月害', luck: 'BAD', source: 'MONTH', table: ['未', '午', '巳', '辰', '卯', '寅', '丑', '子', '亥', '戌', '酉', '申'], match: 'BRANCH', yi: [], ji: ['破土', '安葬', '启攒', '修置产室', '开市'] },
  { name: '月厌', luck: 'BAD', source: 'MONTH', table: ['子', '亥', '戌', '酉', '申', '未', '午', '巳', '辰', '卯', '寅', '丑'], match: 'BRANCH', yi: [], ji: ['修造', '营建', '搬移', '安床', '破土', '安葬', '启攒'] },
  { name: '灾煞', luck: 'BAD', source: 'MONTH', table: ['午', '卯', '子', '酉', '午', '卯', '子', '酉', '午', '卯', '子', '酉'], match: 'BRANCH', yi: [], ji: ['修造', '竖柱上梁', '搬移', '安床', '破土', '安葬', '启攒'] },
  { name: '劫煞', luck: 'BAD', source: 'MONTH', table: ['巳', '寅', '亥', '申', '巳', '寅', '亥', '申', '巳', '寅', '亥', '申'], match: 'BRANCH', yi: [], ji: ['修造', '竖柱上梁', '搬移', '安床', '安葬', '启攒'] },
  { name: '大时', luck: 'BAD', source: 'MONTH', table: ['酉', '午', '卯', '子', '酉', '午', '卯', '子', '酉', '午', '卯', '子'], match: 'BRANCH', yi: [], ji: ['修造', '营建', '竖柱上梁', '搬移', '安床', '筑堤防'] },
  { name: '天吏', luck: 'BAD', source: 'MONTH', table: ['卯', '子', '酉', '午', '卯', '子', '酉', '午', '卯', '子', '酉', '午'], match: 'BRANCH', yi: [], ji: ['修造', '营建', '竖柱上梁', '搬移', '安床', '筑堤防'] },
  // ── 凶煞（用事禁忌补充）──
  { name: '往亡', luck: 'BAD', source: 'MONTH', table: ['戌', '丑', '寅', '巳', '申', '亥', '卯', '午', '酉', '子', '辰', '未'], match: 'BRANCH', yi: [], ji: ['搬移', '求医'] },
  // 受死：《协纪辨方书》卷六《九神总论》明文删驳（「龙虎、罪至、受死三辰并仍旧历从删」），
  // 此条按民间通书与 cnlunar 沿用的旧历口径保留，仅作提示与前置排除，不宣称官修背书。
  { name: '受死', luck: 'BAD', source: 'MONTH', table: ['卯', '酉', '戌', '辰', '亥', '巳', '子', '午', '丑', '未', '寅', '申'], match: 'BRANCH', yi: [], ji: ['畋猎'] },
  // 大败为岁煞组（与大时、咸池同表），与「十恶大败」日柱口径是两条不同神煞。
  { name: '大败', luck: 'BAD', source: 'MONTH', table: ['酉', '午', '卯', '子', '酉', '午', '卯', '子', '酉', '午', '卯', '子'], match: 'BRANCH', yi: [], ji: [] },
  { name: '五墓', luck: 'BAD', source: 'MONTH', table: ['壬辰', '戊辰', '乙未', '乙未', '戊辰', '丙戌', '丙戌', '戊辰', '辛丑', '辛丑', '戊辰', '壬辰'], match: 'GANZHI', yi: [], ji: ['修造', '营建', '搬移', '安床', '破土', '安葬', '启攒'] },
  { name: '独火', luck: 'BAD', source: 'MONTH', table: ['未', '午', '巳', '辰', '卯', '寅', '丑', '子', '亥', '戌', '酉', '申'], match: 'BRANCH', yi: [], ji: ['修造'] },
  { name: '六不成', luck: 'BAD', source: 'MONTH', table: ['卯', '未', '寅', '午', '戌', '巳', '酉', '丑', '申', '子', '辰', '亥'], match: 'BRANCH', yi: [], ji: ['修造'] },
  { name: '土府', luck: 'BAD', source: 'MONTH_SELF', table: MONTH_BRANCHES.slice(), match: 'BRANCH', yi: [], ji: ['修造', '营建', '开渠', '穿井', '破土', '筑堤防'] },
  { name: '白虎', luck: 'BAD', source: 'MONTH', table: ['寅', '辰', '午', '申', '戌', '子', '寅', '辰', '午', '申', '戌', '子'], match: 'BRANCH', yi: [], ji: ['安葬'] },
  { name: '玄武', luck: 'BAD', source: 'MONTH', table: ['巳', '未', '酉', '亥', '丑', '卯', '巳', '未', '酉', '亥', '丑', '卯'], match: 'BRANCH', yi: [], ji: ['安葬'] },
  {
    name: '地囊',
    luck: 'BAD',
    source: 'MONTH',
    table: [
      '辛未 辛酉', '乙酉 乙未', '庚子 庚午', '癸未 癸丑', '甲子 甲寅', '己卯 己丑',
      '戊辰 戊午', '癸未 癸巳', '丙寅 丙申', '丁卯 丁巳', '戊辰 戊子', '庚戌 庚子',
    ],
    match: 'GANZHI',
    yi: [],
    ji: ['修造', '营建', '穿井', '开渠', '破土', '筑堤防'],
  },
  { name: '复日', luck: 'BAD', source: 'MONTH', table: ['癸', '巳', '甲', '乙', '戊', '丙', '丁', '巳', '庚', '辛', '戊', '壬'], match: 'IN_GANZHI', yi: [], ji: ['破土', '安葬', '启攒'] },
  { name: '重日', luck: 'BAD', source: 'BRANCH_SET', table: ['巳', '亥'], match: 'BRANCH', yi: [], ji: ['破土', '安葬', '启攒'] },
  { name: '四废', luck: 'BAD', source: 'SEASON', table: ['庚申 辛酉', '壬子 癸亥', '甲寅 乙卯', '丁巳 丙午'], match: 'GANZHI', yi: [], ji: ['修造', '营建', '搬移', '安床', '破土', '安葬', '启攒'] },
  { name: '天转', luck: 'BAD', source: 'SEASON', table: ['乙卯', '丙午', '辛酉', '壬子'], match: 'GANZHI', yi: [], ji: ['修造', '搬移'] },
  { name: '地转', luck: 'BAD', source: 'SEASON', table: ['辛卯', '戊午', '癸酉', '丙子'], match: 'GANZHI', yi: [], ji: ['修造', '搬移'] },
  { name: '月建转杀', luck: 'BAD', source: 'SEASON', table: ['卯', '午', '酉', '子'], match: 'BRANCH', yi: [], ji: ['修造'] },
  // 四立前十八日；cnlunar 取 range(0,18) 实为十七日，此处从《协纪辨方书》本文
  { name: '土王用事', luck: 'BAD', source: 'SI_LI_WAIT', table: ['18'], match: 'IN_GANZHI', yi: [], ji: ['修造', '营建', '开渠', '穿井', '破土', '筑堤防'] },
  // ── 吉神（等第表所需）──
  { name: '六合', luck: 'GOOD', source: 'MONTH', table: ['丑', '子', '亥', '戌', '酉', '申', '未', '午', '巳', '辰', '卯', '寅'], match: 'BRANCH', yi: ['安葬', '结婚姻', '纳财'], ji: [] },
  { name: '相日', luck: 'GOOD', source: 'SEASON', table: ['巳', '申', '亥', '寅'], match: 'BRANCH', yi: ['上官', '临政'], ji: [] },
  { name: '时德', luck: 'GOOD', source: 'SEASON', table: ['午', '辰', '子', '寅'], match: 'BRANCH', yi: ['修造', '竖柱上梁', '搬移', '求医'], ji: [] },
  { name: '王日', luck: 'GOOD', source: 'SEASON', table: ['寅', '巳', '申', '亥'], match: 'BRANCH', yi: ['上官', '出行'], ji: [] },
  { name: '官日', luck: 'GOOD', source: 'SEASON', table: ['卯', '午', '酉', '子'], match: 'BRANCH', yi: ['上官', '临政'], ji: [] },
  { name: '守日', luck: 'GOOD', source: 'SEASON', table: ['酉', '子', '卯', '午'], match: 'BRANCH', yi: ['安抚边境', '上官'], ji: [] },
  { name: '民日', luck: 'GOOD', source: 'SEASON', table: ['午', '酉', '子', '卯'], match: 'BRANCH', yi: ['搬移', '纳财', '开市'], ji: [] },
  { name: '月德', luck: 'GOOD', source: 'MONTH', table: ['壬', '庚', '丙', '甲', '壬', '庚', '丙', '甲', '壬', '庚', '丙', '甲'], match: 'IN_GANZHI', yi: ['修造', '营建', '搬移', '安葬', '求医'], ji: [] },
  { name: '月德合', luck: 'GOOD', source: 'MONTH', table: ['丁', '乙', '辛', '己', '丁', '乙', '辛', '己', '丁', '乙', '辛', '己'], match: 'IN_GANZHI', yi: ['修造', '营建', '搬移', '安葬'], ji: [] },
  { name: '天德合', luck: 'GOOD', source: 'MONTH', table: ['空', '乙', '壬', '空', '丁', '丙', '空', '己', '戊', '空', '辛', '庚'], match: 'IN_GANZHI', yi: ['修造', '营建', '搬移', '安葬'], ji: [] },
  { name: '岁德', luck: 'GOOD', source: 'YEAR_STEM', table: ['甲', '庚', '丙', '壬', '戊', '甲', '庚', '丙', '壬', '戊'], match: 'IN_GANZHI', yi: ['修造'], ji: [] },
  { name: '岁德合', luck: 'GOOD', source: 'YEAR_STEM', table: ['己', '乙', '辛', '丁', '癸', '己', '乙', '辛', '丁', '癸'], match: 'IN_GANZHI', yi: ['修造'], ji: [] },
  // ── 吉神（用事宜项补充）──
  { name: '鸣吠', luck: 'GOOD', source: 'DAY_LIST', table: ['庚午', '壬申', '癸酉', '壬午', '甲申', '乙酉', '己酉', '丙申', '丁酉', '壬寅', '丙午', '庚寅', '庚申', '辛酉'], match: 'GANZHI', yi: ['破土', '安葬'], ji: [] },
  { name: '鸣吠对', luck: 'GOOD', source: 'DAY_LIST', table: ['丙寅', '丁卯', '丙子', '辛卯', '甲午', '庚子', '癸卯', '壬子', '甲寅', '乙卯'], match: 'GANZHI', yi: ['破土', '启攒'], ji: [] },
  { name: '大葬', luck: 'GOOD', source: 'DAY_LIST', table: ['壬申', '癸酉', '壬午', '甲申', '乙酉', '丙申', '丁酉', '壬寅', '丙午', '己酉', '庚申', '辛酉'], match: 'GANZHI', yi: ['安葬'], ji: [] },
  { name: '小葬', luck: 'GOOD', source: 'DAY_LIST', table: ['庚午', '壬辰', '甲辰', '乙巳', '甲寅', '丙辰', '庚寅'], match: 'GANZHI', yi: ['安葬'], ji: [] },
]

// 天德：四仲月（子午卯酉）查日支，其余月查日干；表值可含两个字（如「巳辰」）
export const TIAN_DEH_BY_MONTH = ['巳辰', '庚', '丁', '申未', '壬', '辛', '亥戌', '甲', '癸', '寅丑', '丙', '乙']
export const ZHONG_MONTHS = ['子', '午', '卯', '酉']

/** 宜忌等第表：键为凶煞或建除值，规则为 [月支范围, 同日所需并见之神, 等级] */
export const BAD_GOD_LEVEL_TABLE: Record<string, Array<[string, string[], number]>> = {
  平日: [['亥', ['相日', '时德', '六合'], 0], ['巳', ['相日', '六合', '月刑'], 1], ['申', ['相日', '月害'], 2], ['寅', ['相日', '月害', '月刑'], 3], ['卯午酉', ['天吏'], 3], ['辰戌丑未', ['月煞'], 4], ['子', ['天吏', '月刑'], 4]],
  收日: [['寅申', ['长生', '六合', '劫煞'], 0], ['巳亥', ['长生', '劫煞'], 2], ['辰未', ['月害'], 2], ['子午酉', ['大时'], 3], ['丑戌', ['月刑'], 3], ['卯', ['大时'], 4]],
  闭日: [['子午卯酉', ['王日'], 3], ['辰戌丑未', ['官日', '天吏'], 3], ['寅申巳亥', ['月煞'], 4]],
  劫煞: [['寅申', ['长生', '六合'], 0], ['辰戌丑未', ['除日', '相日'], 1], ['巳亥', ['长生', '月害'], 2], ['子午卯酉', ['执日'], 3]],
  灾煞: [['寅申巳亥', ['开日'], 1], ['辰戌丑未', ['满日', '民日'], 2], ['子午', ['月破'], 4], ['卯酉', ['月破', '月厌'], 5]],
  月煞: [['卯酉', ['六合', '危日'], 1], ['子午', ['月害', '危日'], 3]],
  月刑: [['巳', ['平日', '六合', '相日'], 1], ['寅', ['相日', '月害', '平日'], 3], ['辰酉亥', ['建日'], 3], ['子', ['平日', '天吏'], 4], ['卯', ['收日', '大时', '天破'], 4], ['未申', ['月破'], 4], ['午', ['月建', '月厌', '德大会'], 4]],
  月害: [['卯酉', ['守日', '除日'], 2], ['丑未', ['执日', '大时'], 2], ['巳亥', ['长生', '劫煞'], 2], ['申', ['相日', '平日'], 2], ['子午', ['月煞'], 3], ['辰戌', ['官日', '闭日', '天吏'], 3], ['寅', ['相日', '平日', '月刑'], 3]],
  月厌: [['寅申', ['成日'], 2], ['丑未', ['开日'], 2], ['辰戌', ['定日'], 3], ['巳亥', ['满日'], 3], ['子', ['月建', '德大会'], 4], ['午', ['月建', '月刑', '德大会'], 4], ['卯酉', ['月破', '灾煞'], 5]],
  大时: [['寅申巳亥', ['除日', '官日'], 0], ['辰戌', ['执日', '六合'], 0], ['丑未', ['执日', '月害'], 2], ['子午酉', ['收日'], 3], ['卯', ['收日', '月刑'], 4]],
  天吏: [['寅申巳亥', ['危日'], 2], ['辰戌丑未', ['闭日'], 3], ['卯午酉', ['平日'], 3], ['子', ['平日', '月刑'], 4]],
}

export const LEVEL_NAMES: Record<number, string> = {
  0: '上：吉足胜凶',
  1: '上次：吉足抵凶',
  2: '中：吉不抵凶',
  3: '中次：凶胜于吉',
  4: '下：凶又逢凶',
  5: '下下：凶叠大凶',
  [-1]: '等第未注',
}

export const BEHAVIOR_LABELS: Record<ThingBehavior, string> = {
  FROM_YI: '从宜不从忌',
  YI_AND_JI: '从宜亦从忌',
  FROM_JI: '从忌不从宜',
  ALL_JI: '诸事皆忌',
}

/** 「德」能降一档：岁德、岁德合、月德、月德合、天德、天德合 */
export const DE_GODS = ['岁德', '岁德合', '月德', '月德合', '天德', '天德合']

/** 用事类别的统一产品文案；避免页面、仲裁层与桌面端各写一套后漂移。 */
export const ZERI_CATEGORY_LABELS: Record<ZeRiCategory, string> = {
  YANG_RUZHAI: '入宅安床',
  YANG_DONGTU: '动土修造',
  YANG_JIAQU: '嫁娶订盟',
  YANG_KAISHI: '开市交易',
  YIN_ANZANG: '安葬破土',
  YIN_XIUFEN: '修坟立碑',
}

/** 用事类别在《协纪辨方书》铺注术语中的对应项 */
export const CATEGORY_XIEJI_TERMS: Record<ZeRiCategory, string[]> = {
  YANG_RUZHAI: ['搬移', '安床', '入宅'],
  YANG_DONGTU: ['修造', '营建', '修宫室', '竖柱上梁', '筑堤防'],
  // 嫁娶、开市是产品端补充的日常事项，术语取通书铺注的常用同名项。
  YANG_JIAQU: ['嫁娶', '结婚姻', '纳采', '订盟'],
  YANG_KAISHI: ['开市', '交易', '立券', '纳财'],
  YIN_ANZANG: ['安葬', '破土', '启攒'],
  // 修坟立碑在原书中无独立条目，参照破土、启攒与修造类神煞处理
  YIN_XIUFEN: ['破土', '启攒', '修造', '营建'],
}

export function behaviorOf(level: number, isDe: boolean): ThingBehavior {
  if (level === 5) return 'ALL_JI'
  if (level === 4) return isDe ? 'FROM_JI' : 'ALL_JI'
  if (level === 3) return isDe ? 'YI_AND_JI' : 'FROM_JI'
  if (level === 2) return isDe ? 'FROM_YI' : 'FROM_JI'
  if (level === 1) return isDe ? 'FROM_YI' : 'YI_AND_JI'
  if (level === 0) return 'FROM_YI'
  return 'YI_AND_JI'
}
