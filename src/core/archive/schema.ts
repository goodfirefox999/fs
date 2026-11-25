/**
 * 档案持久化 schema：版本常量、输入哈希、以及「哪些字段影响结论」的边界。
 *
 * 版本史（README「本地档案库」一节必须同步）：
 * - **v1**：裸档案。有 `schemaVersion: 1`，但没有 inputHash，也没有 rulePackVersion，
 *   无法做跨版本 diff 归因。
 * - **v2**：新增 `inputHash` 与 `rulePackVersion`，使「同一输入、不同规则包」
 *   的差异可以被机器归因，而不是靠人回忆。
 * - **v3**（当前）：新增 `asOfDate`（报告锚点）并把它纳入 inputHash。此前择日预览的起点
 *   与月盘所属月都读系统时间，同一份档案隔天打开结论会变而 hash 不变，归因恒判
 *   「不稳定」。迁移时用 `createdAt` 的 UTC 日期回填（与机器时区无关）。
 *
 * 为什么升到 2 而不是假装仍是 1：v1 的档案已经在桌面端落盘过。偷偷给 v1 加字段
 * 会让「旧档案缺 inputHash」变成运行期 undefined，而不是一次显式迁移——
 * 那正是 undefined 序列化边界要防的东西。
 */

import type { Archive } from '../types'
import { canonicalize } from './canonical'
import { sha256Hex } from './sha256'

/** 当前档案 schema 版本。新建档案一律写这个值。 */
export const ARCHIVE_SCHEMA_VERSION = 3

/** v1 是历史版本，仅用于迁移起点与 fixture。 */
export const LEGACY_ARCHIVE_SCHEMA_VERSION = 1

/**
 * 参与 inputHash 的字段：只有它们变化才可能改变择日结论。
 *
 * 刻意排除：
 * - `id` / `createdAt` / `updatedAt`：同一地点改个备注不该让 hash 变；
 * - `title`：显示名称，不进入任何规则；
 * - `schemaVersion` / `inputHash` / `rulePackVersion`：元数据，不是输入。
 *
 * 包含 `asOfDate`：它决定择日预览的起点与月盘所属月，是会改变结论的输入。
 */
const INPUT_FIELDS = ['mode', 'eventYear', 'reading', 'yang', 'yin', 'asOfDate'] as const

/** 影响结论的输入子集（深拷贝前先做一次结构投影，避免把元数据带进 hash）。 */
export function inputPayload(archive: Pick<Archive, (typeof INPUT_FIELDS)[number]>): unknown {
  const out: Record<string, unknown> = {}
  for (const key of INPUT_FIELDS) {
    const value = (archive as Record<string, unknown>)[key]
    if (value !== undefined) out[key] = value
  }
  return out
}

/**
 * 输入哈希：对规范化后的输入子集做 SHA-256。
 *
 * 算法固定为 `sha256(canonicalize(inputPayload(archive)))`，写进 README。
 * 换算法等于换 hash 语义，必须同时升 `ARCHIVE_SCHEMA_VERSION` 并在迁移里重算，
 * 否则跨版本 diff 会把「算法变了」误报成「输入变了」。
 */
export function inputHashOf(archive: Pick<Archive, (typeof INPUT_FIELDS)[number]>): string {
  return sha256Hex(canonicalize(inputPayload(archive)))
}
