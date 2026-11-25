/**
 * 档案迁移链：`1 → 2 → … → ARCHIVE_SCHEMA_VERSION`。
 *
 * 三条硬约束（评审 2026-11-02 指定）：
 *
 * 1. **只向前**。版本高于当前程序的档案直接抛错，不尝试降级读取——
 *    用旧程序打开新档案，缺字段会被当成「没有」，从而给出错误结论。
 * 2. **每步必须推进版本**。迁移函数返回的 `schemaVersion` 必须等于 `from + 1`，
 *    否则视为迁移写错，抛错而不是继续循环（避免死循环）。
 * 3. **缺失 `schemaVersion` 视为 v1**，但**不得**用 `'schemaVersion' in obj` 判断存在性：
 *    `{schemaVersion: undefined}` 经 JSON 序列化后键会消失，落盘前后必须得到同一结果。
 *    因此这里只读值，不读键。
 */

import type { Archive } from '../types'
import { ymdUtcOf } from '../utils/date'
import { LEGACY_RULE_PACK_VERSION } from '../zeri/version'
import { ARCHIVE_SCHEMA_VERSION, LEGACY_ARCHIVE_SCHEMA_VERSION, inputHashOf } from './schema'

export class ArchiveMigrationError extends Error {
  constructor(
    message: string,
    readonly fromVersion?: number,
  ) {
    super(message)
    this.name = 'ArchiveMigrationError'
  }
}

type RawArchive = Record<string, unknown>
type Migration = (archive: RawArchive) => RawArchive

/**
 * 迁移表：键是**起始版本**，值把档案升到 `起始版本 + 1`。
 * 新增版本时在这里加一项，并在 tests/fixtures/ 放一份该版本的样本。
 */
export const MIGRATIONS: Record<number, Migration> = {
  /**
   * v1 → v2：补 `rulePackVersion` 与 `inputHash`。
   *
   * v1 没有记录规则包版本，用 `legacy-unrecorded` 显式标注，不冒充当前版本——
   * 冒充会让 diff 得出「规则没变」的错误归因。
   */
  1: (archive) => ({
    ...archive,
    rulePackVersion: archive.rulePackVersion ?? LEGACY_RULE_PACK_VERSION,
    inputHash: inputHashOf(archive as unknown as Archive),
    schemaVersion: 2,
  }),
  /**
   * v2 → v3：补 `asOfDate`（报告锚点）并重算 `inputHash`。
   *
   * 回填用 `createdAt` 的 **UTC** 日期，不用本地日期：迁移结果必须与机器时区无关，
   * 否则同一份旧档案在不同时区的机器上会得到不同的 inputHash。
   * 必须重算 hash：INPUT_FIELDS 新增了 `asOfDate`，旧 hash 对应的是旧的输入边界，
   * 保留它会让之后每一次对比都误报「输入变了」。
   */
  2: (archive) => {
    const existing = archive.asOfDate
    let asOfDate: string
    if (typeof existing === 'string' && existing) {
      asOfDate = existing
    } else {
      const createdAt = archive.createdAt
      if (typeof createdAt !== 'number' || !Number.isFinite(createdAt)) {
        throw new ArchiveMigrationError(
          'v2 → v3 需要 createdAt 才能回填 asOfDate',
          2,
        )
      }
      asOfDate = ymdUtcOf(createdAt)
    }
    const next = { ...archive, asOfDate }
    return {
      ...next,
      inputHash: inputHashOf(next as unknown as Archive),
      schemaVersion: 3,
    }
  },
}

function readVersion(raw: RawArchive): number {
  const value = raw.schemaVersion
  if (value === undefined || value === null) return LEGACY_ARCHIVE_SCHEMA_VERSION
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 1) {
    throw new ArchiveMigrationError(`schemaVersion 非法：${JSON.stringify(value)}`)
  }
  return value
}

/** 单条迁移。输入必须是对象；不做宽松修正，坏数据直接抛错。 */
export function migrateArchive(raw: unknown): Archive {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new ArchiveMigrationError('档案必须是对象')
  }

  let current = { ...(raw as RawArchive) }
  let version = readVersion(current)

  if (version > ARCHIVE_SCHEMA_VERSION) {
    throw new ArchiveMigrationError(
      `档案来自更高版本 schemaVersion=${version}（当前程序支持到 ${ARCHIVE_SCHEMA_VERSION}），` +
        '请升级程序后再打开，避免用旧规则解释新字段',
      version,
    )
  }

  while (version < ARCHIVE_SCHEMA_VERSION) {
    const step = MIGRATIONS[version]
    if (!step) {
      throw new ArchiveMigrationError(`缺少 ${version} → ${version + 1} 的迁移`, version)
    }
    const next = step(current)
    const nextVersion = readVersion(next)
    if (nextVersion !== version + 1) {
      throw new ArchiveMigrationError(
        `迁移 ${version} → ${version + 1} 未推进版本（得到 ${nextVersion}），拒绝继续`,
        version,
      )
    }
    current = next
    version = nextVersion
  }

  return current as unknown as Archive
}

export interface MigrateBatchResult {
  archives: Archive[]
  /** 迁移失败的条目：保留原始数据与原因，不静默丢弃，也不阻塞其他条目 */
  failed: Array<{ index: number; error: string }>
}

/**
 * 批量迁移。单条失败不影响其他条目——一份坏档案不该让用户所有档案都打不开。
 * 调用方必须把 `failed` 展示给用户（而不是只取 `archives`）。
 */
export function migrateArchives(raw: unknown): MigrateBatchResult {
  if (!Array.isArray(raw)) return { archives: [], failed: [] }

  const archives: Archive[] = []
  const failed: MigrateBatchResult['failed'] = []

  raw.forEach((item, index) => {
    try {
      archives.push(migrateArchive(item))
    } catch (error) {
      failed.push({ index, error: error instanceof Error ? error.message : String(error) })
    }
  })

  return { archives, failed }
}
