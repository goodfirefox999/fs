/// <reference types="vite/client" />

/**
 * 不在这里声明 `declare module '*.vue'`。
 *
 * 那个 shim 会把所有 .vue 组件变成 `any`，`vue-tsc` 就查不出「模板引用了未定义的变量」
 * 这类错误——桌面端曾因此带着一个 `degMountain is not defined` 的崩溃级 bug 通过了构建。
 * .vue 的类型由 vue-tsc 直接解析 SFC 得到，不需要 shim。
 */

interface DesktopLoadResult {
  archives: unknown[]
  /** 主进程在读取时发现的问题（如原文件损坏并已备份），必须展示给用户 */
  warning?: string
  /** 原文件损坏且备份失败：本次会话禁止写入，避免覆盖仅有的一份副本 */
  readOnly?: boolean
}

interface DesktopBridge {
  platform: string
  loadArchives: () => Promise<DesktopLoadResult>
  saveArchives: (archives: unknown[]) => Promise<{ ok: boolean; file: string }>
  exportArchives: (payload: {
    data: unknown
    suggestedName?: string
  }) => Promise<{ ok: boolean; file?: string }>
  /** 路径由主进程的系统打开对话框决定，渲染进程不参与 */
  importArchives?: () => Promise<{ ok: boolean; data?: unknown; file?: string }>
  /** 报告导出：入参只有 HTML 文本与建议文件名，目录由系统保存对话框决定 */
  exportReport?: (payload: {
    html: string
    suggestedName?: string
  }) => Promise<{ ok: boolean; file?: string }>
}

declare global {
  interface Window {
    desktop?: DesktopBridge
  }
}

export {}
