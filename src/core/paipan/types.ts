/**
 * 排盘（阳宅/阴宅）的统一输出形状。
 *
 * 为什么需要它：八宅、玄空、流年飞星、仙命四个引擎各自返回自有结构
 * （`BaZhaiResult` / `XuanKongChart` / `AnnualInfo` / `YinMatchResult`），
 * 直接渲染会得到四张互不相干的卡片，用户无法横向比较，也无法看出「哪一派说了什么」。
 *
 * 这里复用择日侧 `SchoolResult` 的字段语义（school / status / tendency / subRules /
 * conflictFlags / needsHumanReview），让排盘与择日共享同一套呈现纪律。
 *
 * **一个刻意的限制**：四派回答的不是同一个问题——
 * 八宅问「命与宅配不配」，玄空问「元运山向旺不旺」，飞星问「今年哪方有星」，
 * 仙命问「亡命与山向分金合不合」。所以本层**不做跨派冲突判定**，
 * `conflictFlags` 只承载同一派内部的矛盾（例如多位命主同组比例不一）。
 * 把不同问题的答案判成「冲突」是伪造分歧。
 */

import type { SourceRef, Tendency } from '../zeri/types'

export type PaipanSchoolId = 'BA_ZHAI' | 'XUAN_KONG' | 'FEI_XING' | 'XIAN_MING'

export const PAIPAN_SCHOOL_IDS: PaipanSchoolId[] = [
  'BA_ZHAI',
  'XUAN_KONG',
  'FEI_XING',
  'XIAN_MING',
]

export const PAIPAN_SCHOOL_LABELS: Record<PaipanSchoolId, string> = {
  BA_ZHAI: '八宅',
  XUAN_KONG: '玄空飞星',
  FEI_XING: '流年紫白',
  XIAN_MING: '仙命',
}

/** 该派本次是否能给出完整判断。 */
export type PaipanStatus = 'FULL' | 'PARTIAL' | 'UNAVAILABLE'

export interface PaipanSubRule {
  ruleId: string
  name: string
  /** 事实判定，例如「命宅同组」「旺山旺向」「年星八白入中」；无法判定为 null */
  verdict: string | null
  reasons: string[]
  source: SourceRef
  /** 缺数据时的说明，例如「未填出生日期」 */
  dataGap?: string
  /** 该条是否需要人工复核（流派分歧大、或依赖未核对的出处） */
  needsHumanReview: boolean
}

export interface PaipanSchoolResult {
  school: PaipanSchoolId
  schoolLabel: string
  status: PaipanStatus
  /** 该派倾向，不是系统结论；`insufficient_data` 表示数据不足 */
  tendency: Tendency
  subRules: PaipanSubRule[]
  /** 同一派内部的矛盾说明，不跨派 */
  conflictFlags: string[]
  needsHumanReview: boolean
  partialReason?: string
  /** 结构化补充数据（格局代码、星数等），供界面渲染，不参与吉凶 */
  extras?: Record<string, string | number | boolean | null>
}

/** 排盘报告：四派并列 + 数据缺口汇总，不合并成单一结论。 */
export interface PaipanReport {
  schools: PaipanSchoolResult[]
  /** 全派通用的数据缺口（缺坐向、缺出生日期等），提示用户补什么 */
  dataGaps: string[]
  notes: string[]
  needsHumanReview: boolean
}

export interface PaipanPersonInput {
  label: string
  /** YYYY-MM-DD；空串表示未填 */
  date: string
  gender: 'M' | 'F'
}
