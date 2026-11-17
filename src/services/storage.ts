export const STORAGE_KEYS = {
  archives: 'jl_archives_v1',
  current: 'jl_current_v1',
  entitlements: 'jl_entitlements_v1',
  settings: 'jl_settings_v1',
} as const

export function readStorage<T>(key: string, fallback: T): T {
  try {
    const value = uni.getStorageSync(key)
    if (value === '' || value === null || value === undefined) return fallback
    if (typeof value === 'string') {
      try {
        return JSON.parse(value) as T
      } catch {
        return value as unknown as T
      }
    }
    return value as T
  } catch {
    return fallback
  }
}

export function writeStorage(key: string, value: unknown): boolean {
  try {
    uni.setStorageSync(key, value)
    return true
  } catch (error) {
    // 静默失败会让用户以为档案已保存；必须显式提示，避免重启后发现数据丢失。
    console.error(`[storage] 写入失败: ${key}`, error)
    try {
      uni.showToast({ title: '本地存储写入失败，内容可能未保存', icon: 'none', duration: 3000 })
    } catch {
      // 非 UI 环境（测试/桌面）忽略提示失败。
    }
    return false
  }
}

export function removeStorage(key: string): void {
  try {
    uni.removeStorageSync(key)
  } catch {
    // ignore
  }
}
