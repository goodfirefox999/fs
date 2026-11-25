import { defineStore } from 'pinia'
import type { Archive, SceneMode } from '@/core/types'
import { ARCHIVE_SCHEMA_VERSION, inputHashOf, migrateArchives } from '@/core/archive'
import { RULE_PACK_VERSION } from '@/core/zeri/version'
import { periodFromYear } from '@/core/engines/xuankong'
import { todayYmd } from '@/core/utils/date'
import {
  STORAGE_KEYS,
  readStorage,
  removeStorage,
  writeStorage,
} from '@/services/storage'

export type ArchiveInput = Omit<
  Archive,
  | 'id'
  | 'createdAt'
  | 'updatedAt'
  | 'schemaVersion'
  | 'period'
  // 由 store 计算，调用方不得自行传入（否则 hash 与版本可能和实际不符）
  | 'inputHash'
  | 'rulePackVersion'
>

function makeId(): string {
  return `a_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
}

export const useArchiveStore = defineStore('archive', {
  state: () => {
    const raw = readStorage<unknown>(STORAGE_KEYS.archives, [])
    const loaded = migrateArchives(raw)
    // v1 档案（或更早、连 schemaVersion 都没有）读进来后需要回写一次，
    // 否则导出时仍会吐旧版本，下次启动又要再迁一遍。
    const hadLegacy =
      Array.isArray(raw) &&
      raw.some((item) => {
        const version = (item as Record<string, unknown> | null)?.schemaVersion
        if (version === undefined || version === null) return true
        return typeof version === 'number' && version < ARCHIVE_SCHEMA_VERSION
      })
    return {
      archives: loaded.archives,
      /** 迁移失败的条目：必须在界面上提示，不能静默丢弃 */
      migrationFailures: loaded.failed,
      pendingMigration: hadLegacy,
      currentId: readStorage<string>(STORAGE_KEYS.current, ''),
    }
  },
  getters: {
    sorted(state): Archive[] {
      return [...state.archives].sort((a, b) => b.updatedAt - a.updatedAt)
    },
    recent(state): Archive[] {
      return [...state.archives]
        .sort((a, b) => b.updatedAt - a.updatedAt)
        .slice(0, 3)
    },
    byMode: (state) => {
      return (mode: SceneMode) =>
        [...state.archives]
          .filter((item) => item.mode === mode)
          .sort((a, b) => b.updatedAt - a.updatedAt)
    },
  },
  actions: {
    getById(id: string): Archive | undefined {
      return this.archives.find((item) => item.id === id)
    },
    create(input: ArchiveInput): Archive {
      const now = Date.now()
      const base = {
        ...input,
        id: makeId(),
        period: periodFromYear(input.eventYear) as Archive['period'],
        createdAt: now,
        updatedAt: now,
        // 报告锚点在新建时定下，之后改输入也不动：它是「这份档案的结论从哪一天起算」，
        // 跟着创建日走，这样同一份档案在任何一天打开都是同一份结论。
        asOfDate: todayYmd(),
        schemaVersion: ARCHIVE_SCHEMA_VERSION,
        rulePackVersion: RULE_PACK_VERSION,
      }
      // inputHash 只覆盖影响结论的字段，改标题不该改变它
      const archive: Archive = { ...base, inputHash: inputHashOf(base) }
      this.archives.unshift(archive)
      this.currentId = archive.id
      this.persist()
      return archive
    },
    update(id: string, patch: Partial<Archive>): Archive | undefined {
      const index = this.archives.findIndex((item) => item.id === id)
      if (index < 0) return undefined
      const merged: Archive = {
        ...this.archives[index],
        ...patch,
        id,
        period: periodFromYear(patch.eventYear ?? this.archives[index].eventYear) as Archive['period'],
        updatedAt: Date.now(),
        schemaVersion: ARCHIVE_SCHEMA_VERSION,
        rulePackVersion: RULE_PACK_VERSION,
      }
      // 锚点只认原档案的值：patch 里即使带了 asOfDate 也不让它被覆盖，
      // 否则改一次输入就等于把择日起点挪到另一天，归因基准全部错位。
      const anchored: Archive = {
        ...merged,
        asOfDate: this.archives[index].asOfDate ?? todayYmd(),
      }
      // 放在最后算，外部即使传了 inputHash 也不会污染
      const next: Archive = { ...anchored, inputHash: inputHashOf(anchored) }
      this.archives.splice(index, 1, next)
      this.persist()
      return next
    },
    remove(id: string): void {
      this.archives = this.archives.filter((item) => item.id !== id)
      if (this.currentId === id) this.currentId = this.archives[0]?.id ?? ''
      this.persist()
    },
    setCurrent(id: string): void {
      this.currentId = id
      writeStorage(STORAGE_KEYS.current, id)
    },
    persist(): void {
      writeStorage(STORAGE_KEYS.archives, this.archives)
      writeStorage(STORAGE_KEYS.current, this.currentId)
    },
    /**
     * 启动时调用一次：把迁移后的档案回写，避免每次启动重复迁移。
     *
     * 有迁移失败项时**不回写**——那会把「读得出来但迁不动」的档案
     * 用内存里的可读子集覆盖掉，等于销毁用户数据。
     */
    hydrate(): void {
      if (!this.pendingMigration || this.migrationFailures.length > 0) return
      this.pendingMigration = false
      this.persist()
    },
    clear(): void {
      this.archives = []
      this.currentId = ''
      removeStorage(STORAGE_KEYS.archives)
      removeStorage(STORAGE_KEYS.current)
    },
  },
})
