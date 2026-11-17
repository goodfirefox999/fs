/**
 * 本地档案库：schema 版本、输入哈希、迁移链、差异归因。
 *
 * 这个目录只做「数据的形状与演进」，不碰 UI 与 IPC。
 * 三端（小程序 / H5 / Electron）共用同一套函数，使同一份档案
 * 在任何端读出来都是同一个 inputHash。
 */

export { ARCHIVE_SCHEMA_VERSION, LEGACY_ARCHIVE_SCHEMA_VERSION, inputHashOf, inputPayload } from './schema'
export { canonicalize, CanonicalizeError } from './canonical'
export { sha256Hex } from './sha256'
export {
  ArchiveMigrationError,
  MIGRATIONS,
  migrateArchive,
  migrateArchives,
  type MigrateBatchResult,
} from './migrate'
export { attributeDiff, type DiffAttribution, type DiffKind, type EvaluationSnapshot } from './diff'
