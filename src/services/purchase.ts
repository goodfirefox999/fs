import { callCloudFunction, checkEntitlement } from './cloud'

export interface OrderSign {
  outTradeNo: string
  signData: string
  paySig: string
  signature: string
  mode: string
}

export interface PurchaseResult {
  ok: boolean
  message: string
  outTradeNo?: string
}

function requestVirtualPayment(order: OrderSign): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof wx === 'undefined' || !wx.requestVirtualPayment) {
      reject(new Error('当前微信版本不支持虚拟支付'))
      return
    }
    wx.requestVirtualPayment({
      signData: order.signData,
      paySig: order.paySig,
      signature: order.signature,
      mode: order.mode || 'short_series_goods',
      success: () => resolve(),
      fail: (error) => reject(error),
    })
  })
}

export async function purchaseReport(
  archiveId: string,
  productId = 'report_single_990'
): Promise<PurchaseResult> {
  // #ifdef MP-WEIXIN
  try {
    const code = await new Promise<string>((resolve, reject) => {
      uni.login({
        provider: 'weixin',
        success: (result) => resolve(String(result.code ?? '')),
        fail: reject,
      })
    })
    if (!code) throw new Error('微信登录失败，请重试')
    const order = await callCloudFunction<OrderSign>('createVirtualOrder', {
      code,
      productId,
      archiveId,
    })
    await requestVirtualPayment(order)
    return {
      ok: true,
      message: '支付完成，正在确认解锁',
      outTradeNo: order.outTradeNo,
    }
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : '支付未完成',
    }
  }
  // #endif
  // #ifndef MP-WEIXIN
  void archiveId
  void productId
  return { ok: false, message: '请在微信小程序内完成支付' }
  // #endif
}

export async function waitForEntitlement(
  archiveId: string,
  attempts = 8
): Promise<boolean> {
  for (let index = 0; index < attempts; index++) {
    if (await checkEntitlement(archiveId)) return true
    await new Promise((resolve) => setTimeout(resolve, 900))
  }
  return false
}
