/**
 * 档案对比的归因：把「结论变了」拆成「输入变了 / 规则变了 / 都变了」。
 *
 * 没有归因的对比是有害的：用户看到「昨天说可用，今天说不可用」，
 * 若不知道是改了坐向还是规则包升级，只能怀疑工具不可靠。
 *
 * 归因依据只有两项：`inputHash` 与 `rulePackVersion`。
 * 二者任一变化都可能导致结论变化，但**不能反推**——hash 相同且版本相同
 * 却结论不同，说明评估不确定（例如依赖了未固定顺序的数据），
 * 这里显式返回 `unstable` 而不是谎称「无变化」。
 */

export type DiffKind = 'none' | 'input_only' | 'rules_only' | 'both' | 'unstable'

/** 一次评估的可比对快照。只放归因需要的字段，不放完整结果。 */
export interface EvaluationSnapshot {
  inputHash: string
  rulePackVersion: string
  /** 结论标签，如 favorable / rejected / insufficient */
  verdict: string
  /** 窗口内被排除的天数（可选，仅用于叙述） */
  excludedDays?: number
  /** 窗口总天数（可选） */
  totalDays?: number
}

export interface DiffAttribution {
  kind: DiffKind
  inputChanged: boolean
  rulesChanged: boolean
  verdictChanged: boolean
  /** 可直接展示的一句话归因，不含推测 */
  narrative: string
}

function describeVerdictChange(prev: EvaluationSnapshot, next: EvaluationSnapshot): string {
  if (prev.verdict === next.verdict) return '结论未变'
  return `结论 ${prev.verdict} → ${next.verdict}`
}

function describeDays(prev: EvaluationSnapshot, next: EvaluationSnapshot): string {
  if (typeof prev.excludedDays !== 'number' || typeof next.excludedDays !== 'number') return ''
  const delta = next.excludedDays - prev.excludedDays
  if (delta === 0) return '排除天数相同'
  const sign = delta > 0 ? '+' : ''
  return `排除 ${prev.excludedDays} 天 → ${next.excludedDays} 天（${sign}${delta} 天）`
}

export function attributeDiff(
  prev: EvaluationSnapshot,
  next: EvaluationSnapshot,
): DiffAttribution {
  const inputChanged = prev.inputHash !== next.inputHash
  const rulesChanged = prev.rulePackVersion !== next.rulePackVersion
  const verdictChanged = prev.verdict !== next.verdict

  let kind: DiffKind
  if (!inputChanged && !rulesChanged) {
    // 输入与规则都相同却结论不同：不是「无变化」，是评估不稳定，必须暴露
    kind = verdictChanged ? 'unstable' : 'none'
  } else if (inputChanged && rulesChanged) {
    kind = 'both'
  } else if (inputChanged) {
    kind = 'input_only'
  } else {
    kind = 'rules_only'
  }

  const parts: string[] = []
  const days = describeDays(prev, next)
  if (days) parts.push(days)
  parts.push(describeVerdictChange(prev, next))

  switch (kind) {
    case 'none':
      parts.push('输入与规则包均未变化')
      break
    case 'unstable':
      parts.push('输入与规则包均未变化，但结论不同——评估存在未固定因素，需人工复核')
      break
    case 'input_only':
      parts.push('归因：输入变化（inputHash 不同），规则包未变')
      break
    case 'rules_only':
      parts.push(
        `归因：rulePackVersion ${prev.rulePackVersion} → ${next.rulePackVersion}，输入未变`,
      )
      break
    case 'both':
      parts.push(
        `归因：输入变化，且 rulePackVersion ${prev.rulePackVersion} → ${next.rulePackVersion}`,
      )
      break
  }

  return {
    kind,
    inputChanged,
    rulesChanged,
    verdictChanged,
    narrative: parts.join('；'),
  }
}
