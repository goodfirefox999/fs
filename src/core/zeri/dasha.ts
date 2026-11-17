/**
 * Layer 3：全流派共享的大煞 / 冲命前置 reject 层。
 * 命中任一 reject 项即进入 rejected_dates，任何流派的吉星与评分都不得覆盖
 * （董公「煞贡、直星、人专能解诸凶，唯不能解金神七煞」即此义的古典表述）。
 */
import type { SanShaLevel, ZeRiCategory } from '../types'
import { ZHI_CLASH } from '../constants/nayin60'
import { branchOfMountain, getMountain, resolveMountain } from '../constants/shan24'
import { isInSanShaSector, sanShaGradeOf, sanShaOfZhi } from '../engines/feixing'
import { isSiLiSiJueDay, isYangGongJi } from '../utils/date'
import type { DashaFamily, DashaHit, DashaStance, ShaGrade } from './types'
import { createRegistry } from '../utils/registry'
import { ruleMeta } from './sources'
import { JIN_SHEN_DI, JIN_SHEN_TIAN } from './tables/donggong'

/** 十恶大败日（日柱口径）。 */
export const SHI_E_DA_BAI_DAYS = [
  '甲辰', '乙巳', '丙申', '丁亥', '戊戌', '己丑', '庚辰', '辛巳', '壬申', '癸亥',
]

/** 往亡传统所忌之事：只在相关用事类别上 reject。 */
const WANG_WANG_CATEGORIES: ZeRiCategory[] = ['YANG_RUZHAI']

/** 重丧所忌用事（安葬/嫁娶类）。 */
const CHONG_SANG_CATEGORIES: ZeRiCategory[] = ['YIN_ANZANG', 'YIN_XIUFEN']

/** 兴工类用事：阴宅、动土修造，以及勾选「入宅伴随动土」的入宅。 */
function constructionLike(input: Pick<DashaInput, 'category' | 'includesConstruction'>): boolean {
  if (
    input.category === 'YANG_DONGTU' ||
    input.category === 'YIN_ANZANG' ||
    input.category === 'YIN_XIUFEN'
  ) {
    return true
  }
  return input.category === 'YANG_RUZHAI' && input.includesConstruction
}

/** 四家三煞占山（空间维度）与日课内部相犯（时间维度）分列，不混为一谈。 */
export const SAN_SHA_MOUNTAIN_RULES = [
  'D3_YEAR_SAN_SHA_ON_MOUNTAIN',
  'D3_MONTH_SAN_SHA_ON_MOUNTAIN',
  'D3_DAY_SAN_SHA_ON_MOUNTAIN',
  'D3_HOUR_SAN_SHA_ON_MOUNTAIN',
]

export const SAN_SHA_COURSE_RULES = ['D3_DAY_ON_YEAR_SAN_SHA', 'D3_HOUR_ON_DAY_SAN_SHA']

/**
 * 大煞条目的结构归属登记表：占山类看坐山是否落煞方，相犯类看四柱自身是否犯煞
 * （后者不构成对坐山的排除），GENERAL 为其余前置排除项。
 * 每个规则 id 都必须登记；familyOf 对未登记 id 抛错，
 * 新增规则忘了归类会在测试里直接红，而不是静默落进通用类。
 */
export const DASHA_FAMILY: Record<string, DashaFamily> = {
  D3_YEAR_SAN_SHA_ON_MOUNTAIN: 'SAN_SHA_MOUNTAIN',
  D3_MONTH_SAN_SHA_ON_MOUNTAIN: 'SAN_SHA_MOUNTAIN',
  D3_DAY_SAN_SHA_ON_MOUNTAIN: 'SAN_SHA_MOUNTAIN',
  D3_HOUR_SAN_SHA_ON_MOUNTAIN: 'SAN_SHA_MOUNTAIN',
  D3_DAY_ON_YEAR_SAN_SHA: 'SAN_SHA_COURSE',
  D3_HOUR_ON_DAY_SAN_SHA: 'SAN_SHA_COURSE',
  D3_SUI_PO: 'GENERAL',
  D3_YUE_PO: 'GENERAL',
  D3_RI_PO: 'GENERAL',
  D3_SHI_PO: 'GENERAL',
  D3_CHONG_SHAN: 'GENERAL',
  D3_CHONG_ZHU_MING: 'GENERAL',
  D3_JIN_SHEN_QI_SHA: 'GENERAL',
  D3_SHOU_SI: 'GENERAL',
  D3_SI_FEI: 'GENERAL',
  D3_WANG_WANG: 'GENERAL',
  D3_SHI_E_DA_BAI: 'GENERAL',
  D3_DA_BAI_MONTHLY: 'GENERAL',
  D3_SI_LI_SI_JUE: 'GENERAL',
  D3_YANG_GONG_JI: 'GENERAL',
  D3_CHONG_SANG: 'GENERAL',
  D3_XIEJI_ALL_JI: 'GENERAL',
}

const FAMILY_REGISTRY = createRegistry('大煞分类', DASHA_FAMILY, '新增规则必须登记，禁止静默归入通用类')

export function familyOf(ruleId: string): DashaFamily {
  return FAMILY_REGISTRY.require(ruleId)
}

/**
 * 官书立场与民间通书相左、恒作提示的条目（受死：《协纪辨方书》卷六「并仍旧历从删」）。
 * 写在规则层而不是默认开关里，任何调用方（含直接调 checkDasha 的桌面端与测试）都无法把它升级为硬排除，
 * 避免出现「引用从删却据以排除」的自我矛盾。
 */
export const ALWAYS_WARN_DASHA = ['D3_SHOU_SI']

/**
 * 依通书/民俗口径列出的条目：官书或未载、或与民俗并存两说。
 * 由「民俗神煞」或「重丧」开关决定排除还是提示，呈现上单列一区，不混进官书明文大煞。
 */
export const FOLK_DASHA_RULE_IDS = [
  'D3_SHOU_SI',
  'D3_SI_FEI',
  'D3_WANG_WANG',
  'D3_SHI_E_DA_BAI',
  'D3_DA_BAI_MONTHLY',
  'D3_YANG_GONG_JI',
  'D3_CHONG_SANG',
]

/**
 * 民俗区内部再按出处立场分档，避免「官书从删」与「官书明文但本包允许降级」被读成同权重。
 * 每个 FOLK_DASHA_RULE_IDS 成员都必须在这里有一档。
 */
export const DASHA_STANCE: Record<string, DashaStance> = {
  D3_SHOU_SI: 'OFFICIAL_DELETED',
  D3_YANG_GONG_JI: 'FOLK_ONLY',
  D3_CHONG_SANG: 'FOLK_DIVIDED',
  D3_DA_BAI_MONTHLY: 'FOLK_DIVIDED',
  D3_SI_FEI: 'OFFICIAL_RELAXABLE',
  D3_WANG_WANG: 'OFFICIAL_RELAXABLE',
  D3_SHI_E_DA_BAI: 'OFFICIAL_RELAXABLE',
}

/**
 * 必须声明在 `DASHA_STANCE` **之后**：`createRegistry` 在构造期就会读取该表做校验，
 * 提前声明会触发 TDZ（`Cannot access 'DASHA_STANCE' before initialization`），
 * 表现为整个 dasha 模块导入即崩、六个测试文件连带失败。
 */
const STANCE_REGISTRY = createRegistry('出处立场', DASHA_STANCE)


export function stanceOf(ruleId: string): DashaStance | undefined {
  return FOLK_DASHA_RULE_IDS.includes(ruleId) ? STANCE_REGISTRY.require(ruleId) : undefined
}

/**
 * 一条规则只归一个 stance；出处同时涉及官书明文与通书异说时取最保守档
 * （保守 = 更接近「只作提示」），避免同一规则在两处显示不同严重度。
 */
export const STANCE_PRIORITY: DashaStance[] = [
  'OFFICIAL_DELETED',
  'FOLK_ONLY',
  'FOLK_DIVIDED',
  'OFFICIAL_RELAXABLE',
]

export const STANCE_LABELS: Record<DashaStance, string> = {
  OFFICIAL_DELETED: '官书从删·恒提示',
  FOLK_ONLY: '原书未载·通书沿用',
  FOLK_DIVIDED: '两说并存',
  OFFICIAL_RELAXABLE: '官书明文·本包可降',
}

/**
 * 前置层分区统一口径：卡片渲染与摘要计数都走这里，
 * 新增 family 或 stance 时不会出现「摘要说 3 条、卡片只有 2 条」。
 */
export function partitionDasha(dasha: {
  hits: DashaHit[]
  warned: DashaHit[]
}): { blocks: DashaHit[]; diverge: DashaHit[]; folk: DashaHit[] } {
  const byStance = (a: DashaHit, b: DashaHit) =>
    (a.stance ? STANCE_PRIORITY.indexOf(a.stance) : STANCE_PRIORITY.length) -
    (b.stance ? STANCE_PRIORITY.indexOf(b.stance) : STANCE_PRIORITY.length)
  return {
    blocks: dasha.hits,
    diverge: dasha.warned.filter((hit) => !FOLK_DASHA_RULE_IDS.includes(hit.ruleId)),
    folk: dasha.warned.filter((hit) => FOLK_DASHA_RULE_IDS.includes(hit.ruleId)).sort(byStance),
  }
}

/**
 * 三煞默认的严格度分层（按用事是否兴工，不靠用户开关心慈）。
 * 兴工口径（阴宅用事、动土修造，或入宅伴随动工）：年家、月家占山按通书硬忌排除，
 * 日家、时家占山与日课相犯两条降为提示。
 * 纯入宅：占山四条在规则层就不参与判定（不兴工），此处不得虚列为「已降级」；只保留日课相犯两条。
 * level 只负责把默认降级的层级升回排除，不能把不可放宽项降下去。
 */
export function defaultSanShaLax(
  category: ZeRiCategory,
  includesConstruction = false,
  level: SanShaLevel = 'year_month',
): string[] {
  if (level === 'all') return []
  if (!constructionLike({ category, includesConstruction })) return [...SAN_SHA_COURSE_RULES]
  const lax = ['D3_DAY_SAN_SHA_ON_MOUNTAIN', 'D3_HOUR_SAN_SHA_ON_MOUNTAIN', ...SAN_SHA_COURSE_RULES]
  if (level === 'year') lax.push('D3_MONTH_SAN_SHA_ON_MOUNTAIN')
  return lax
}

interface DashaRule {
  ruleId: string
  name: string
  sourceKey: string
  machineCheck?: string
  needsHumanReview?: boolean
  test: (input: DashaInput) => { hit: boolean; reason: string; shaGrade?: ShaGrade }
}

export interface DashaInput {
  date: string
  yearGanZhi: string
  yearStem: string
  yearBranch: string
  monthBranch: string
  dayBranch: string
  dayGanZhi: string
  hourBranch: string | null
  mountShan: string
  mountDeg: number
  subjectBranches: Array<{ label: string; branch: string }>
  badGods: string[]
  behavior: string
  category: ZeRiCategory
  /** 入宅是否伴随动土、修造或安门：为真时按兴工类恢复三煞占山等硬排除 */
  includesConstruction: boolean
  /** 当日值宿（二十八宿名首字） */
  xiu: string
  lunarMonth: number
  lunarDay: number
  /**
   * 被产品端降级为「提示」的大煞规则 id。
   * 默认全部为空：岁破/月破/日破/时破/年家三煞占山/冲山/冲命/四离四绝/诸事皆忌任何情况下都不得降级；
   * 受死一类官书从删的条目由 ALWAYS_WARN_DASHA 恒列为提示，不依赖这里。
   */
  warnOnly: string[]
}

/**
 * 永不允许降级的硬排除项。判据只放两类：
 * 历法事实（四柱相冲、四离四绝随节气时刻走）与官书明文忌日；
 * 依通书沿用的民俗条目（杨公忌、受死、四废一类）一律不在此列，交给「民俗神煞」开关或恒为提示。
 */
export const NON_NEGOTIABLE_DASHA = [
  'D3_SUI_PO',
  'D3_YUE_PO',
  'D3_RI_PO',
  'D3_SHI_PO',
  'D3_YEAR_SAN_SHA_ON_MOUNTAIN',
  'D3_CHONG_SHAN',
  'D3_CHONG_ZHU_MING',
  'D3_SI_LI_SI_JUE',
  'D3_XIEJI_ALL_JI',
]

/**
 * 占山判定：命中时一并给出正煞／傍煞。
 * 煞区跨三支共五山，正煞取「中间一支及其两侧的天干山」共三山（北方壬·子·癸、南方丙·午·丁），
 * 傍煞取两端的地支山（亥、丑／巳、未）。此处「三山」是二十四山的分组，
 * 不是玄空飞星里的三元龙（地元／天元／人元）分组，勿混。
 * 两端支各自一山（亥丑、巳未）为傍煞。分级只作严重度标注，reject／warn 判定不变。
 */
function mountainSanShaHit(
  input: DashaInput,
  refBranch: string,
  prefix: string,
  tail: string,
): { hit: boolean; reason: string; shaGrade?: ShaGrade } {
  if (!constructionLike(input) || !isInSanShaSector(input.mountDeg, refBranch)) {
    return { hit: false, reason: '' }
  }
  const sanSha = sanShaOfZhi(refBranch)
  const grade = sanShaGradeOf(input.mountDeg, refBranch)
  // 线度与所选山名不符时（手输兼向度数）按线度落山说，避免界面里「坐亥山」却是壬山的正煞结论
  const at = resolveMountain(input.mountDeg)
  const mismatch = at.name === input.mountShan ? '' : `，线度${input.mountDeg}°实落${at.name}山`
  return {
    hit: true,
    shaGrade: grade ?? undefined,
    reason: `${prefix}三合局煞在${sanSha.direction}，坐山${input.mountShan}落煞方（${grade ?? '正傍未分'}${mismatch}）；${tail}`,
  }
}

const RULES: DashaRule[] = [
  {
    ruleId: 'D3_SUI_PO',
    name: '岁破',
    sourceKey: 'XIEJI_BASE',
    machineCheck: '与 cnlunar 2020–2035 逐日比对一致',
    test: (input) => ({
      hit: input.dayBranch === ZHI_CLASH[input.yearBranch],
      reason: `日支${input.dayBranch}正冲太岁${input.yearBranch}，为岁破日`,
    }),
  },
  {
    ruleId: 'D3_YUE_PO',
    name: '月破',
    sourceKey: 'XIEJI_BASE',
    test: (input) => ({
      hit: input.dayBranch === ZHI_CLASH[input.monthBranch],
      reason: `日支${input.dayBranch}正冲月建${input.monthBranch}，为月破（的）日`,
    }),
  },
  {
    ruleId: 'D3_RI_PO',
    name: '日破',
    sourceKey: 'XIEJI_BASE',
    test: (input) => ({
      hit: Boolean(input.hourBranch) && input.hourBranch === ZHI_CLASH[input.dayBranch],
      reason: `时支${input.hourBranch}冲日支${input.dayBranch}，日课时支相冲`,
    }),
  },
  {
    ruleId: 'D3_SHI_PO',
    name: '时破',
    sourceKey: 'XIEJI_BASE',
    test: (input) => ({
      hit: Boolean(input.hourBranch) && input.hourBranch === ZHI_CLASH[input.monthBranch],
      reason: `时支${input.hourBranch}冲月建${input.monthBranch}，为时破`,
    }),
  },
  {
    ruleId: 'D3_YEAR_SAN_SHA_ON_MOUNTAIN',
    name: '年家三煞占坐山',
    sourceKey: 'XIEJI_BASE',
    test: (input) =>
      // 三煞忌的是「该年在此方兴工动土、安葬破土」；纯搬入既有住宅不兴工，
      // 故占山四条只在用事含兴工（动土、修造、安门）或阴宅用事时参与判定。
      mountainSanShaHit(
        input,
        input.yearBranch,
        `${input.yearBranch}年`,
        '该年此方传统上不宜兴工、破土、安葬',
      ),
  },
  {
    ruleId: 'D3_MONTH_SAN_SHA_ON_MOUNTAIN',
    name: '月家三煞占坐山',
    sourceKey: 'XIEJI_BASE',
    test: (input) =>
      mountainSanShaHit(
        input,
        input.monthBranch,
        `${input.monthBranch}月`,
        '月家递轻于年家，通书多作硬忌',
      ),
  },
  {
    ruleId: 'D3_DAY_SAN_SHA_ON_MOUNTAIN',
    name: '日家三煞占坐山',
    sourceKey: 'XIEJI_BASE',
    test: (input) =>
      mountainSanShaHit(
        input,
        input.dayBranch,
        `日支${input.dayBranch}`,
        '日家三煞多派视作可解',
      ),
  },
  {
    ruleId: 'D3_HOUR_SAN_SHA_ON_MOUNTAIN',
    name: '时家三煞占坐山',
    sourceKey: 'XIEJI_BASE',
    test: (input) => {
      // 煞方一律由「该柱自身的地支三合局」起：年家用年支、月家用月支、日家用日支、时家用时支，
      // 通书与择日资料把四柱并列在同一口诀里（申子辰年／月／日／时皆煞南，寅午戌皆煞北）。
      // 另有主张「时三煞按日支起」的说法，本包不采用：按日支起煞会与 D3_DAY_SAN_SHA_ON_MOUNTAIN
      // 完全同解，逻辑上不成立；「日支定煞方、时支是否落煞」已由 D3_HOUR_ON_DAY_SAN_SHA
      // （时支犯日家三煞，属日课相犯、不看坐山）覆盖，两条不得合并。
      // 也不得把本条改成按日支起煞——tests/san-sha.test.ts 的「亥日申时坐午山」对照用例正是钉这一点的。
      if (!input.hourBranch) return { hit: false, reason: '' }
      return mountainSanShaHit(
        input,
        input.hourBranch,
        `时支${input.hourBranch}`,
        '时家三煞最轻，且需先指定日课时支',
      )
    },
  },
  {
    ruleId: 'D3_DAY_ON_YEAR_SAN_SHA',
    name: '日支犯年家三煞',
    sourceKey: 'XIEJI_BASE',
    test: (input) => {
      const sanSha = sanShaOfZhi(input.yearBranch)
      return {
        hit: sanSha.branches.includes(input.dayBranch),
        reason: `日支${input.dayBranch}落在${input.yearBranch}年三煞方（${sanSha.direction}）之内；此为日课犯年煞，与「日家三煞占山」不是一条`,
      }
    },
  },
  {
    ruleId: 'D3_HOUR_ON_DAY_SAN_SHA',
    name: '时支犯日家三煞',
    sourceKey: 'XIEJI_BASE',
    test: (input) => {
      if (!input.hourBranch) return { hit: false, reason: '' }
      const sanSha = sanShaOfZhi(input.dayBranch)
      return {
        hit: sanSha.branches.includes(input.hourBranch),
        reason: `时支${input.hourBranch}落在日支${input.dayBranch}三煞方（${sanSha.direction}）之内；属日课内部相犯，与山家无关`,
      }
    },
  },
  {
    ruleId: 'D3_CHONG_SHAN',
    name: '冲坐山',
    sourceKey: 'ZONG_JING_SAN_HE',
    test: (input) => {
      const mountBranch = branchOfMountain(input.mountShan)
      return {
        hit: Boolean(mountBranch) && ZHI_CLASH[input.dayBranch] === mountBranch,
        reason: `日支${input.dayBranch}冲坐山${input.mountShan}（${mountBranch}）`,
      }
    },
  },
  {
    ruleId: 'D3_CHONG_ZHU_MING',
    name: '冲主命',
    sourceKey: 'ZONG_JING_SAN_HE',
    test: (input) => {
      const hit = input.subjectBranches.find(
        (item) => ZHI_CLASH[input.dayBranch] === item.branch
      )
      return {
        hit: Boolean(hit),
        reason: hit
          ? `日支${input.dayBranch}冲${hit.label}（年支${hit.branch}）`
          : '日课不冲主命',
      }
    },
  },
  {
    ruleId: 'D3_JIN_SHEN_QI_SHA',
    name: '金神七煞',
    sourceKey: 'DONG_GONG',
    needsHumanReview: true,
    test: (input) => {
      const tian = JIN_SHEN_TIAN[input.yearStem] ?? []
      const di = JIN_SHEN_DI[input.yearStem] ?? []
      const kind = tian.includes(input.dayBranch)
        ? '天金神'
        : di.includes(input.dayBranch)
          ? '地金神'
          : null
      // 《协纪辨方书》卷三所忌为「筑城池、修官室、竖楼阁、兴工、上梁、移徙、嫁娶」，
      // 即修造与入宅类；安葬类按旧例只作提示，避免把年家方位煞误当通用日煞。
      const applies = input.category === 'YANG_DONGTU' || input.category === 'YANG_RUZHAI'
      return {
        hit: Boolean(kind) && applies,
        reason: kind
          ? `${input.yearStem}${input.yearBranch}之年，日支${input.dayBranch}为${kind}（《协纪辨方书》卷三引《堪舆经》；官书按语本身存疑）。` +
            '本表按「天金神＋地金神」合并，故甲己年含申酉，与部分通书只取午未的口径不同'
          : '',
      }
    },
  },
  {
    ruleId: 'D3_SHOU_SI',
    name: '受死',
    sourceKey: 'SHOU_SI',
    test: (input) => ({
      hit: input.badGods.includes('受死'),
      reason: `本月受死日为日支${input.dayBranch}（民间通书仍忌；《协纪辨方书》卷六已从此删）`,
    }),
  },
  {
    ruleId: 'D3_SI_FEI',
    name: '四废',
    sourceKey: 'XIEJI_BASE',
    test: (input) => ({
      hit: input.badGods.includes('四废'),
      reason: `日柱${input.dayGanZhi}为四废日，作为事皆废`,
    }),
  },
  {
    ruleId: 'D3_WANG_WANG',
    name: '往亡',
    sourceKey: 'XIEJI_BASE',
    test: (input) => ({
      hit: input.badGods.includes('往亡') && WANG_WANG_CATEGORIES.includes(input.category),
      reason: `往亡日忌${input.category === 'YANG_RUZHAI' ? '搬移入宅' : '往亡所忌之事'}`,
    }),
  },
  {
    ruleId: 'D3_SHI_E_DA_BAI',
    name: '十恶大败（日柱口径）',
    sourceKey: 'SHI_E_DA_BAI',
    test: (input) => ({
      hit: SHI_E_DA_BAI_DAYS.includes(input.dayGanZhi),
      reason: `日柱${input.dayGanZhi}属十恶大败十日`,
    }),
  },
  {
    ruleId: 'D3_DA_BAI_MONTHLY',
    name: '大败（月支口径）',
    sourceKey: 'SHI_E_DA_BAI',
    test: (input) => ({
      hit: input.badGods.includes('大败'),
      reason: '按「正月起卯逆行四仲」的月支口径犯大败；此煞与十恶大败日柱不同系统',
    }),
  },
  {
    ruleId: 'D3_SI_LI_SI_JUE',
    name: '四离四绝',
    sourceKey: 'SI_LI_SI_JUE',
    test: (input) => {
      const siLi = isSiLiSiJueDay(input.date)
      const name = siLi.name ?? ''
      const kind = ['春分', '秋分', '夏至', '冬至'].includes(name) ? '离' : '绝'
      return {
        hit: siLi.hit,
        reason: siLi.hit ? `${name}前一日，为四${kind}日` : '',
      }
    },
  },
  {
    ruleId: 'D3_YANG_GONG_JI',
    name: '杨公十三忌',
    sourceKey: 'YANG_GONG_JI',
    test: (input) => ({
      hit: isYangGongJi(input.lunarMonth, input.lunarDay),
      reason: `农历${Math.abs(input.lunarMonth)}月${input.lunarDay}日为杨公忌日`,
    }),
  },
  {
    ruleId: 'D3_CHONG_SANG',
    name: '重丧',
    sourceKey: 'CHONG_SANG',
    test: (input) => ({
      hit: input.badGods.includes('重丧') && CHONG_SANG_CATEGORIES.includes(input.category),
      reason: `安葬类用事逢重丧日（日干${input.dayGanZhi[0]}）`,
    }),
  },
  {
    ruleId: 'D3_XIEJI_ALL_JI',
    name: '协纪等第诸事皆忌',
    sourceKey: 'XIEJI_BASE',
    machineCheck: '等第表与 cnlunar 2026–2027 逐日一致',
    test: (input) => ({
      hit: input.behavior === 'ALL_JI',
      reason: '《协纪辨方书》宜忌等第判为「诸事皆忌」',
    }),
  },
]

/** 三煞按年、月、日分层，可放宽程度不同：兴工与阴宅用事中的年家三煞占山不可放宽。 */
export function isNegotiable(
  ruleId: string,
  input: Pick<DashaInput, 'category' | 'includesConstruction'>,
): boolean {
  const construction = constructionLike(input)
  if (ruleId === 'D3_YEAR_SAN_SHA_ON_MOUNTAIN') return !construction
  if (SAN_SHA_MOUNTAIN_RULES.includes(ruleId) || SAN_SHA_COURSE_RULES.includes(ruleId)) return true
  return !NON_NEGOTIABLE_DASHA.includes(ruleId)
}

export function checkDasha(input: DashaInput): {
  rejected: boolean
  hits: DashaHit[]
  warned: DashaHit[]
} {
  const hits: DashaHit[] = []
  const warned: DashaHit[] = []

  for (const rule of RULES) {
    const result = rule.test(input)
    if (!result.hit) continue
    const meta = ruleMeta({
      ruleId: rule.ruleId,
      name: rule.name,
      sourceKey: rule.sourceKey,
      machineCheck: rule.machineCheck,
      needsHumanReview: rule.needsHumanReview,
    })
    const hit: DashaHit = {
      ruleId: rule.ruleId,
      name: rule.name,
      reason: result.reason,
      negotiable: isNegotiable(rule.ruleId, input),
      appliesToCategory: true,
      family: familyOf(rule.ruleId),
      ...(result.shaGrade ? { shaGrade: result.shaGrade } : {}),
      stance: stanceOf(rule.ruleId),
      source: meta.source,
      verification: meta.verification,
      needsHumanReview: meta.needsHumanReview,
    }
    if (
      ALWAYS_WARN_DASHA.includes(rule.ruleId) ||
      (!NON_NEGOTIABLE_DASHA.includes(rule.ruleId) && input.warnOnly.includes(rule.ruleId))
    ) {
      warned.push(hit)
    } else {
      hits.push(hit)
    }
  }

  return { rejected: hits.length > 0, hits, warned }
}

export const DASHA_RULE_IDS = RULES.map((rule) => rule.ruleId)

/** 兴工类用事下的年家三煞占山说明。 */
export const SAN_SHA_MOUNTAIN_NOTE =
  '该年三煞正在坐山一方，传统上此年此方不宜兴工、破土、安葬；整段日期被排除是规则本身给出的结论，不是计算故障。可更换坐山、另择年份，或确认本次用事确实不兴工。'

/** 入宅勾选「伴随动土、修造或安门」后的说明：口径已切到兴工类。 */
export const SAN_SHA_MOUNTAIN_RUZHAI_WORK_NOTE =
  '本次已勾选「入宅伴随动土、修造或安门」，故按兴工类恢复年家与月家三煞占山硬排除。若实际只是搬入既有住宅、不动工，请取消勾选；若确要动工，本结果提示该年此方传统上不宜兴工。'

const MONTH_SHA_MOUNTAIN_NOTE =
  '月家三煞递轻于年家，但通书在兴工、葬事中同样忌之，故默认与年家一并硬排除。你所据流派若只忌年家，把「三煞硬排除层级」调到「仅年家」即降为提示。'

/**
 * 空结果与大面积排除的人类可读解释。
 * 放在数据层是为了小程序与桌面端共用同一口径，避免两处各写一套说法。
 * 特例文案用常量直引，不走字符串键查表：键写错时 TS 会报错，不会在界面上静默变空。
 */
export const DASHA_GUIDANCE: Record<string, string> = {
  D3_YEAR_SAN_SHA_ON_MOUNTAIN: SAN_SHA_MOUNTAIN_NOTE,
  D3_MONTH_SAN_SHA_ON_MOUNTAIN: MONTH_SHA_MOUNTAIN_NOTE,
  D3_DAY_SAN_SHA_ON_MOUNTAIN:
    '日家三煞占山多派视为可解（一日之煞力远弱于年月），默认仅作提示；把「三煞硬排除层级」调到「整层」后升级为排除。',
  D3_HOUR_SAN_SHA_ON_MOUNTAIN:
    '时家三煞为四家之最轻，且只有指定日课时支后才可能命中；默认仅作提示。',
  D3_DAY_ON_YEAR_SAN_SHA:
    '日支落在本年三煞方之内（日课犯年煞），忌的是在该方兴工用事；这是四柱自身的问题，不构成对坐山的排除，与「日家三煞占山」是两条不同规则。各派轻重差异大，默认列为提示。',
  D3_HOUR_ON_DAY_SAN_SHA:
    '时支落在本日三煞方之内，属日课内部相犯（时辰不宜用事），与山家方位无关，不构成对坐山的排除；默认列为提示，且需先指定日课时支。',
  D3_SUI_PO:
    '该年岁破方与日支相冲的日子按月固定出现，传统上不用作大事；如需用事，请人工复核岁破口径（以立春还是以正月初一换年）。',
  D3_CHONG_SHAN:
    '日支正冲坐山的日子固定分布在本命盘的对宫方位，传统上不用作兴工与安葬；这是坐山与日课的硬性冲突。',
  D3_CHONG_ZHU_MING:
    '日支正冲主命或仙命年支，传统上避开；如为合葬或多位仙命，只要冲其中一位即排除，可核对出生年是否录错。',
  D3_JIN_SHEN_QI_SHA:
    '金神七煞按年干取值日地支，命中天数多寡取决于年干流派口径（是否并入纳音金地金神）。可将严格度改为「仅提示」或人工复核所选口径。',
  D3_XIEJI_ALL_JI:
    '《协纪辨方书》宜忌等第判为「诸事皆忌」的日子不列候选；该等第依赖同日吉神凶煞并见情况，可对照原书人工复核。',
  D3_SI_FEI:
    '四废按季节配日柱，一季只有两日；若命中密集，请核对季节（节气月）归属。',
  D3_WANG_WANG:
    '往亡只忌出行、搬移、上官一类用事，已按事件类型限定；安葬、修造不受此条排除。',
  D3_YANG_GONG_JI:
    '杨公十三忌按农历固定十三日出现，相传出自杨筠松但官书未列明文，通书普遍沿用。本包采用通书口径，默认随「民俗神煞硬排除」一并排除（与岁破同级效果），这是显式声明的偏离而不是官书结论；关闭该开关即降为民俗口径提示，原始判定仍完整保留。',
  D3_YUE_PO:
    '日支正冲当月月建即为月破（的）日，每月固定一支；《协纪辨方书》列为不可用事之日，不提供放宽。',
  D3_RI_PO:
    '时支正冲日支为日破，需先指定日课时支才会参与判定；已指定的日子按硬排除处理。',
  D3_SHI_PO:
    '时支正冲月建为时破，同样需指定日课时支后才判定；传统上与日破并列作凶时论。',
  D3_SHOU_SI:
    '受死按月支固定排布。《协纪辨方书》四库全书本卷六「要安以下九神」按语明文：「若夫龙虎罪至受死三辰并仍旧历从删」——官书已从此删，民间通书仍忌。本包因此恒作提示、不作硬排除；采用哪一系请人工核对所据版本。',
  D3_SHI_E_DA_BAI:
    '十恶大败按日柱十条固定出现（《协纪辨方书》称「无禄」）；另有以月支排布的同名岁煞，两条不同系统已分列，不合并计分。',
  D3_DA_BAI_MONTHLY:
    '此条是「正月起卯逆行四仲」的岁煞大败，与十恶大败日柱不同系统；官书并存两说，默认按所选严格度处理，建议人工核对所据通书版本。',
  D3_SI_LI_SI_JUE:
    '四离四绝为四立、二分、二至前一日的四时交界日，逐年随节气交接时刻变化；属历法事实，不提供放宽。',
  D3_CHONG_SANG:
    '重丧口诀有「正七庚起」与「正月起甲」两系，本产品采用其中一系并要求人工核对；可在严格度设置中降为提示。',
}

/** 用事口径切到兴工时（入宅勾选伴随动土），三煞占山的处置建议随之改变。 */
export function guidanceFor(
  ruleId: string,
  input?: Pick<DashaInput, 'category' | 'includesConstruction'>,
): string {
  if (
    SAN_SHA_MOUNTAIN_RULES.includes(ruleId) &&
    input?.category === 'YANG_RUZHAI' &&
    input.includesConstruction
  ) {
    return SAN_SHA_MOUNTAIN_RUZHAI_WORK_NOTE
  }
  return DASHA_GUIDANCE[ruleId] ?? '按所选严格度参与前置排除，原始判定与出处已完整保留，可人工复核后调整。'
}
