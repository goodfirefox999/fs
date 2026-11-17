import type { ContentBundle } from '@/core/types'

let initialized = false

export function initCloud(): void {
  // #ifdef MP-WEIXIN
  if (initialized) return
  try {
    if (typeof wx !== 'undefined' && wx.cloud) {
      wx.cloud.init({
        env: import.meta.env.VITE_CLOUD_ENV || undefined,
        traceUser: true,
      })
      initialized = true
    }
  } catch {
    initialized = false
  }
  // #endif
}

export async function callCloudFunction<T>(
  name: string,
  data: Record<string, unknown> = {}
): Promise<T> {
  // #ifdef MP-WEIXIN
  initCloud()
  if (typeof wx === 'undefined' || !wx.cloud) {
    throw new Error('云开发未初始化，请检查小程序云环境配置')
  }
  const response = await wx.cloud.callFunction({ name, data })
  const payload = response.result as
    | { ok?: boolean; data?: T; message?: string }
    | T
    | undefined
  if (payload && typeof payload === 'object' && 'ok' in payload) {
    const envelope = payload as { ok?: boolean; data?: T; message?: string }
    if (envelope.ok === false) {
      throw new Error(envelope.message || '云端返回失败')
    }
    return (envelope.data ?? (payload as T)) as T
  }
  return payload as T
  // #endif
  // #ifndef MP-WEIXIN
  void name
  void data
  throw new Error('云端功能请在微信小程序中使用')
  // #endif
}

export async function fetchContent(archiveId: string): Promise<ContentBundle> {
  // #ifdef H5
  if (import.meta.env.DEV) {
    void archiveId
    const response = await fetch('/api/content')
    if (!response.ok) throw new Error(`内容接口返回 ${response.status}`)
    return (await response.json()) as ContentBundle
  }
  // #endif
  return callCloudFunction<ContentBundle>('getReportContent', { archiveId })
}

export async function checkEntitlement(archiveId: string): Promise<boolean> {
  // #ifdef MP-WEIXIN
  try {
    const result = await callCloudFunction<{ unlocked: boolean }>('getEntitlement', {
      archiveId,
    })
    return Boolean(result.unlocked)
  } catch {
    return false
  }
  // #endif
  // #ifndef MP-WEIXIN
  void archiveId
  return false
  // #endif
}

export function trackEvent(event: string, props: Record<string, unknown> = {}): void {
  // #ifdef MP-WEIXIN
  void callCloudFunction('track', { event, props }).catch(() => {
    // 统计失败不影响主流程
  })
  // #endif
  // #ifndef MP-WEIXIN
  void event
  void props
  // #endif
}
