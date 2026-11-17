/** 五派规则包与仲裁层的类型定义：任何一派的原始输出都不得被合并或丢弃。 */

export type SchoolId =
  | 'ZHENG_WU_XING'
  | 'SAN_HE'
  | 'DONG_GONG'
  | 'XUAN_KONG_DA_GUA'
  | 'TIAN_XING'

export const SCHOOL_IDS: SchoolId[] = [
  'ZHENG_WU_XING',
  'SAN_HE',
  'DONG_GONG',
  'XUAN_KONG_DA_GUA',
  'TIAN_XING',
]

export const SCHOOL_LABELS: Record<SchoolId, string> = {
  ZHENG_WU_XING: '正五行',
  SAN_HE: '三合',
  DONG_GONG: '董公',
  XUAN_KONG_DA_GUA: '玄空大卦',
  TIAN_XING: '天星',
}

/** 只能由人工从 unverified 改为 verified_by_human，代码与 AI 一律不得升级。 */
export type VerificationStatus = 'unverified' | 'verified_by_human'

export type Tendency = 'favorable' | 'neutral' | 'unfavorable' | 'insufficient_data'

export type PackStatus = 'FULL' | 'PARTIAL' | 'UNAVAILABLE'

export type RuleAction = 'score' | 'reject'

export interface SourceRef {
  /** 稳定 id，便于 UI 与测试引用 */
  id: string
  /** 古籍或数据出处名称 */
  title: string
  /** 卷次/篇目等定位 */
  locus?: string
  /** 现代整理来源（含许可证） */
  modern?: string
  url?: string
  /** 流派分歧说明；存在分歧时必须写在这里而不是静默选一种 */
  lineageNote?: string
}

export interface SubRuleResult {
  ruleId: string
  name: string
  action: RuleAction
  /** 规则事实判定，例如「旺局」「真调候」「值煞贡」；无法判定为 null */
  verdict: string | null
  scoreDelta: number
  reasons: string[]
  source: SourceRef
  verification: VerificationStatus
  needsHumanReview: boolean
  /** 缺数据时的说明，例如「未提供入首龙」 */
  dataGap?: string
}

export interface SchoolResult {
  school: SchoolId
  schoolLabel: string
  status: PackStatus
  tendency: Tendency
  scoreDelta: number
  subRules: SubRuleResult[]
  /** 本包内部或与前置层之间的冲突说明，不裁决对错 */
  conflictFlags: string[]
  needsHumanReview: boolean
  partialReason?: string
  /** 玄空大卦要求丁/财分开，天星要求七政/四余分开，用附加字段承载 */
  extras?: Record<string, number | string | boolean | null>
}

/** 大煞条目的结构归属，见 DashaHit.family */
export type DashaFamily = 'SAN_SHA_MOUNTAIN' | 'SAN_SHA_COURSE' | 'GENERAL'

/** 三煞占山的严重度：煞区正中三山为正煞，两端一支为傍煞 */
export type ShaGrade = '正煞' | '傍煞'

/**
 * 出处的立场分档，只用于「民俗口径提示」区分级展示，不影响命中判定：
 * - OFFICIAL_DELETED：官书明文删驳（《协纪辨方书》卷六「并仍旧历从删」）；
 * - FOLK_ONLY：官书未列明文、通书沿用；
 * - FOLK_DIVIDED：官书与民俗并存两说，或口诀本身有两系；
 * - OFFICIAL_RELAXABLE：官书明文列出，但本包允许按「民俗神煞」开关降为提示。
 */
export type DashaStance =
  | 'OFFICIAL_DELETED'
  | 'FOLK_ONLY'
  | 'FOLK_DIVIDED'
  | 'OFFICIAL_RELAXABLE'

export interface DashaHit {
  ruleId: string
  name: string
  reason: string
  /** 该条在严格度设置上是否允许降为提示（与出处的核对状态是两件事） */
  negotiable: boolean
  /** 事件相关的大煞（如往亡只忌出行搬移）按类别命中才 reject */
  appliesToCategory: boolean
  /**
   * 结构归属：占山类回答「坐山是否落在煞方」，日课相犯类回答「四柱自身是否犯煞」。
   * 两者不是一个问题的两个等级，界面据此分区，不让相犯条冒充山家排除。
   */
  family: DashaFamily
  /** 三煞占山条目的正煞／傍煞标注；不改变 reject 或 warn 的判定 */
  shaGrade?: ShaGrade
  /** 民俗口径条目的出处立场分档，界面据此排序与标注 */
  stance?: DashaStance
  source: SourceRef
  verification: VerificationStatus
  needsHumanReview: boolean
}

export interface DashaResult {
  rejected: boolean
  hits: DashaHit[]
  /** 因用户设置降级为提示的条目，仍原样保留 */
  warned: DashaHit[]
}

export interface SchoolConflict {
  schools: SchoolId[]
  issue: string
  ruleIds: string[]
}

export interface SchoolWeight {
  school: SchoolId
  weight: number
  tendency: Tendency
}

export interface ArbitrationResult {
  rejected: boolean
  /** 五派并列，缺失的派也要占位并说明原因 */
  schoolResults: SchoolResult[]
  consensus: 'favorable' | 'mixed' | 'unfavorable' | 'rejected' | 'insufficient'
  conflicts: SchoolConflict[]
  weights: SchoolWeight[]
  /** 三派及以上 favorable 且无 reject */
  consensusFavorable: boolean
}
