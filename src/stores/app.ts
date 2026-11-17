import { defineStore } from 'pinia'
import type { ContentBundle, NorthType } from '@/core/types'
import { fetchContent } from '@/services/cloud'
import {
  STORAGE_KEYS,
  readStorage,
  removeStorage,
  writeStorage,
} from '@/services/storage'

export interface AppSettings {
  city: string
  declination: number
  northType: NorthType
}

const defaultSettings: AppSettings = {
  city: '',
  declination: 0,
  northType: 'MAGNETIC',
}

export const useAppStore = defineStore('app', {
  state: () => ({
    content: null as ContentBundle | null,
    contentLoading: false,
    contentError: '',
    entitlements: readStorage<Record<string, boolean>>(STORAGE_KEYS.entitlements, {}),
    settings: readStorage<AppSettings>(STORAGE_KEYS.settings, defaultSettings),
  }),
  getters: {
    unlockedIds(state): string[] {
      return Object.keys(state.entitlements).filter(
        (key) => state.entitlements[key] && key !== '__dev_all__'
      )
    },
  },
  actions: {
    isUnlocked(archiveId: string): boolean {
      return Boolean(this.entitlements[archiveId] || this.entitlements.__dev_all__)
    },
    grantEntitlement(archiveId: string): void {
      this.entitlements = { ...this.entitlements, [archiveId]: true }
      writeStorage(STORAGE_KEYS.entitlements, this.entitlements)
    },
    resetEntitlements(): void {
      this.entitlements = {}
      removeStorage(STORAGE_KEYS.entitlements)
    },
    setSettings(patch: Partial<AppSettings>): void {
      this.settings = { ...this.settings, ...patch }
      writeStorage(STORAGE_KEYS.settings, this.settings)
    },
    async loadContent(archiveId: string, force = false): Promise<ContentBundle | null> {
      if (this.content && !force) return this.content
      if (this.contentLoading) return this.content
      if (!archiveId) {
        this.contentError = '请先解锁一份完整分析'
        return null
      }
      this.contentLoading = true
      this.contentError = ''
      try {
        this.content = await fetchContent(archiveId)
        return this.content
      } catch (error) {
        this.contentError =
          error instanceof Error ? error.message : '完整内容加载失败，请稍后重试'
        return null
      } finally {
        this.contentLoading = false
      }
    },
    clearLocal(): void {
      this.entitlements = {}
      this.content = null
      this.contentError = ''
      this.settings = { ...defaultSettings }
      removeStorage(STORAGE_KEYS.entitlements)
      removeStorage(STORAGE_KEYS.settings)
    },
  },
})
