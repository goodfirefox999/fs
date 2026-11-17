import type { SchoolId, SchoolResult, SubRuleResult, Tendency } from '../types'
import { SCHOOL_LABELS } from '../types'
import { ruleMeta } from '../sources'

export interface SubRuleOptions {
  action?: 'score' | 'reject'
  verdict: string | null
  scoreDelta?: number
  reasons?: string[]
  dataGap?: string
  needsHumanReview?: boolean
}

/** 规则计分阈值：三档以内为中性，避免把微小分差包装成吉凶结论。 */
export const FAVORABLE_THRESHOLD = 2
export const UNFAVORABLE_THRESHOLD = -2

export function subRule(
  meta: { ruleId: string; name: string; sourceKey: string; machineCheck?: string },
  options: SubRuleOptions
): SubRuleResult {
  const base = ruleMeta(meta)
  return {
    ...base,
    needsHumanReview: options.needsHumanReview ?? base.needsHumanReview,
    action: options.action ?? 'score',
    verdict: options.verdict,
    scoreDelta: options.action === 'reject' ? 0 : (options.scoreDelta ?? 0),
    reasons: options.reasons ?? [],
    dataGap: options.dataGap,
  }
}

export function tendencyOf(score: number, applicable: number): Tendency {
  if (applicable === 0) return 'insufficient_data'
  if (score >= FAVORABLE_THRESHOLD) return 'favorable'
  if (score <= UNFAVORABLE_THRESHOLD) return 'unfavorable'
  return 'neutral'
}

export function packResult(
  school: SchoolId,
  subRules: SubRuleResult[],
  options: {
    status?: SchoolResult['status']
    partialReason?: string
    extras?: SchoolResult['extras']
    conflictFlags?: string[]
  } = {}
): SchoolResult {
  const scoreDelta = subRules.reduce((sum, item) => sum + item.scoreDelta, 0)
  const applicable = subRules.filter((item) => item.verdict !== null).length
  const needsHumanReview = subRules.some((item) => item.needsHumanReview)
  return {
    school,
    schoolLabel: SCHOOL_LABELS[school],
    status: options.status ?? 'FULL',
    tendency: tendencyOf(scoreDelta, applicable),
    scoreDelta,
    subRules,
    conflictFlags: options.conflictFlags ?? [],
    needsHumanReview,
    partialReason: options.partialReason,
    extras: options.extras,
  }
}
