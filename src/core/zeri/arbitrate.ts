/**
 * Layer 5：仲裁层。只做透明加权与冲突标记，不消灭分歧、不裁决谁对谁错。
 */
import type { ZeRiCategory } from '../types'
import type {
  ArbitrationResult,
  DashaResult,
  SchoolConflict,
  SchoolId,
  SchoolResult,
} from './types'
import { SCHOOL_LABELS } from './types'
import { weightsFor } from './registry'

function drivingRules(result: SchoolResult): string[] {
  return result.subRules
    .filter((rule) => Math.abs(rule.scoreDelta) >= 1)
    .map((rule) => rule.ruleId)
}

export function arbitrate(
  schools: SchoolResult[],
  dasha: DashaResult,
  category: ZeRiCategory
): ArbitrationResult {
  const weights = weightsFor(category).map((item) => ({
    ...item,
    tendency: schools.find((school) => school.school === item.school)?.tendency ?? ('insufficient_data' as const),
  }))

  const conflicts: SchoolConflict[] = []
  for (let i = 0; i < schools.length; i++) {
    for (let j = i + 1; j < schools.length; j++) {
      const a = schools[i]
      const b = schools[j]
      const opposite =
        (a.tendency === 'favorable' && b.tendency === 'unfavorable') ||
        (a.tendency === 'unfavorable' && b.tendency === 'favorable')
      if (!opposite) continue
      conflicts.push({
        schools: [a.school, b.school] as SchoolId[],
        issue: `${SCHOOL_LABELS[a.school]}判${a.tendency === 'favorable' ? '为宜' : '为忌'}（${a.scoreDelta >= 0 ? '+' : ''}${a.scoreDelta}），${SCHOOL_LABELS[b.school]}判${b.tendency === 'favorable' ? '为宜' : '为忌'}（${b.scoreDelta >= 0 ? '+' : ''}${b.scoreDelta}）；两派依据不同，仲裁层不判定孰是孰非`,
        ruleIds: [...drivingRules(a), ...drivingRules(b)],
      })
    }
  }

  const favorable = schools.filter((item) => item.tendency === 'favorable').length
  const unfavorable = schools.filter((item) => item.tendency === 'unfavorable').length
  const scored = schools.filter((item) => item.tendency !== 'insufficient_data').length

  let consensus: ArbitrationResult['consensus'] = 'mixed'
  if (dasha.rejected) consensus = 'rejected'
  else if (scored === 0) consensus = 'insufficient'
  else if (favorable > unfavorable) consensus = 'favorable'
  else if (unfavorable > favorable) consensus = 'unfavorable'

  return {
    rejected: dasha.rejected,
    schoolResults: schools,
    consensus,
    conflicts,
    weights,
    consensusFavorable: !dasha.rejected && favorable >= 3,
  }
}
