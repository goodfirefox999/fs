/// <reference types="@dcloudio/types" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}

interface ImportMetaEnv {
  readonly DEV: boolean
  readonly PROD: boolean
  readonly VITE_CLOUD_ENV?: string
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

interface WxCloudCallResult {
  result?: unknown
}

interface WxCloudApi {
  init(options: { env?: string; traceUser?: boolean }): void
  callFunction(options: {
    name: string
    data?: Record<string, unknown>
  }): Promise<WxCloudCallResult>
}

interface WxRequestVirtualPaymentOptions {
  signData: string
  paySig: string
  signature: string
  mode: string
  success?: () => void
  fail?: (error: unknown) => void
}

interface WxApi {
  cloud?: WxCloudApi
  requestVirtualPayment?: (options: WxRequestVirtualPaymentOptions) => void
}

declare const wx: WxApi
