/**
 * 从一次扫描结果里提取可比对的快照。
 *
 * 只放归因需要的字段，不放完整结果——档案要长期保存，完整结果会让文件无限膨胀，
 * 而 diff 只需要知道「输入是什么、规则是哪版、结论落在哪一档、排除了多少天」。
 */

import type { ZeRiResult } from '@core/types'
import { RULE_PACK_VERSION } from '@core/zeri/version'
import type { EvaluationSnapshot } from '@core/archive'
import type { WorkbenchState } from '../workbench'
import { workbenchInputHash } from './model'

/**
 * 结论标签。刻意用中文短标签而不是 `favorable/rejected`：
 * `attributeDiff` 的叙述会直接把它拼进「结论 A → B」，英文码在界面上不可读。
 */
export type ScanVerdict = '有候选' | '全部排除' | '无匹配'

export function verdictOf(result: ZeRiResult): ScanVerdict {
  if (result.items.length > 0) return '有候选'
  // 没有候选时，区分「被大煞全数排除」与「没被排除但不符合宜忌」
  return result.rejected >= result.scanned ? '全部排除' : '无匹配'
}

export function snapshotOf(result: ZeRiResult, state: WorkbenchState): EvaluationSnapshot {
  return {
    inputHash: workbenchInputHash(state),
    rulePackVersion: RULE_PACK_VERSION,
    verdict: verdictOf(result),
    excludedDays: result.rejected,
    totalDays: result.scanned,
  }
}

/** 两次快照是否等价（忽略时间戳），用于避免重复写盘。 */
export function sameSnapshot(
  a: EvaluationSnapshot,
  b: EvaluationSnapshot,
): boolean {
  return (
    a.inputHash === b.inputHash &&
    a.rulePackVersion === b.rulePackVersion &&
    a.verdict === b.verdict &&
    a.excludedDays === b.excludedDays &&
    a.totalDays === b.totalDays
  )
}
