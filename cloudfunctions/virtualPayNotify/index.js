const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const DELIVER_EVENT = 'xpay_goods_deliver_notify'
const REFUND_EVENT = 'xpay_refund_notify'
// 其余已知事件（代币支付、投诉、风控、订阅等）当前无需业务处理，只应答避免微信重试 15 次。
const ACK_ONLY_EVENTS = new Set([
  'xpay_coin_pay_notify',
  'xpay_complaint_notify',
  'xpay_wxpay_callback_notify',
  'xpay_subscribe_signing_result_notify',
  'xpay_subscribe_pay_fail_notify',
  'xpay_subscribe_ios_refund_query_notify',
])

function success() {
  return { ErrCode: 0, ErrMsg: 'success' }
}

function fail(message) {
  return { ErrCode: 1, ErrMsg: message }
}

function parseBody(event) {
  if (!event) return null
  // 仅接受「HTTP 访问服务」的请求体或「消息推送」的官方报文（平铺 event）。
  // 不再把客户端 callFunction 的任意 data 当作回调，避免伪造发货。
  if (typeof event.body === 'string') {
    const raw = event.isBase64Encoded
      ? Buffer.from(event.body, 'base64').toString('utf8')
      : event.body
    try {
      return JSON.parse(raw)
    } catch {
      return null
    }
  }
  if (typeof event.body === 'object' && event.body !== null) return event.body
  if (event.MsgType === 'event') return event
  return null
}

function readToken(event) {
  const query = event.queryStringParameters || event.queryString || {}
  if (query && query.token) return String(query.token)
  const headers = event.headers || {}
  return String(headers['x-xpay-token'] || headers['X-Xpay-Token'] || '')
}

function expectedEnv() {
  const raw = process.env.XPAY_ENV
  const value = raw === undefined || raw === '' ? 0 : Number(raw)
  if (!Number.isInteger(value) || (value !== 0 && value !== 1)) {
    throw new Error('XPAY_ENV 必须为 0（现网）或 1（沙箱）')
  }
  return value
}

async function deliver(orders, entitlements, order, payload) {
  // 已退款订单不再补发权益；重复回调直接应答。
  if (order.status === 'REFUNDED') return success()

  const openid = order.openid
  const outTradeNo = order.outTradeNo
  const goods = payload.GoodsInfo || {}
  const productId = String(goods.ProductId || '')
  const actualPrice = Number(goods.ActualPrice)
  if (order.productId !== productId) return fail('product mismatch')
  if (!Number.isFinite(actualPrice) || actualPrice !== order.price) {
    return fail('price mismatch')
  }

  const entitlementId = `${openid}_${order.archiveId}`
  if (order.status === 'PAID') {
    try {
      await entitlements.doc(entitlementId).get()
    } catch {
      await entitlements.doc(entitlementId).set({
        data: {
          openid,
          archiveId: order.archiveId,
          productId: order.productId,
          outTradeNo,
          createdAt: Date.now(),
        },
      })
    }
    return success()
  }

  const now = Date.now()
  await orders.doc(order._id).update({
    data: {
      status: 'PAID',
      paidAt: now,
      billNo: String(payload.BillNo || ''),
      payTime: Number(payload.PayTime || 0),
      notifyEnv: Number(payload.Env),
    },
  })

  try {
    await entitlements.doc(entitlementId).set({
      data: {
        openid,
        archiveId: order.archiveId,
        productId: order.productId,
        outTradeNo,
        createdAt: now,
      },
    })
  } catch (error) {
    console.error('entitlement write failed', error)
    return fail('entitlement write failed')
  }

  return success()
}

async function refund(orders, entitlements, order, payload) {
  const now = Date.now()
  // 只允许从已支付状态进入退款：PENDING/未知状态的伪造 refund 通知
  // 不得凭空删除权益（无权益可删也应幂等成功，不给攻击者探测信号）。
  if (order.status !== 'PAID' && order.status !== 'REFUNDED') {
    return success()
  }
  if (order.status !== 'REFUNDED') {
    await orders.doc(order._id).update({
      data: {
        status: 'REFUNDED',
        refundedAt: now,
        refundBillNo: String(payload.BillNo || ''),
        notifyEnv: Number(payload.Env),
      },
    })
  }
  // getEntitlement / getReportContent 以权益文档存在性判断解锁，退回时删除即可收回。
  try {
    await entitlements.doc(`${order.openid}_${order.archiveId}`).remove()
  } catch (error) {
    // 文档不存在或已删除时无需处理。
    console.warn('entitlement remove skipped', error && error.message)
  }
  return success()
}

exports.main = async (event) => {
  try {
    // 未配置 token 时 fail-closed：否则任何知道云函数地址的人都能伪造发货回调。
    const expectedToken = process.env.XPAY_NOTIFY_TOKEN
    if (!expectedToken) {
      console.error('XPAY_NOTIFY_TOKEN 未配置，拒绝回调')
      return fail('notify token not configured')
    }
    if (readToken(event) !== expectedToken) {
      return fail('unauthorized')
    }
    if (event.httpMethod && event.httpMethod !== 'POST') {
      return fail('method not allowed')
    }

    const payload = parseBody(event)
    if (!payload) return fail('invalid body')
    if (payload.MsgType !== 'event') return fail(`unexpected msg type ${payload.MsgType || ''}`)

    const expected = expectedEnv()
    const actualEnv = Number(payload.Env)
    if (!Number.isInteger(actualEnv) || actualEnv !== expected) {
      return fail('env mismatch')
    }

    const outTradeNo = String(payload.OutTradeNo || '')
    const openid = String(payload.OpenId || '')
    if (!outTradeNo || !openid) return fail('missing order identity')

    const eventType = String(payload.Event || '')
    if (ACK_ONLY_EVENTS.has(eventType)) {
      console.warn('ack without handling', eventType, outTradeNo)
      return success()
    }
    if (eventType !== DELIVER_EVENT && eventType !== REFUND_EVENT) {
      return fail(`unexpected event ${eventType}`)
    }

    const db = cloud.database()
    const orders = db.collection('orders')
    const entitlements = db.collection('entitlements')
    const found = await orders.where({ outTradeNo }).limit(1).get()
    const order = found.data[0]
    if (!order) {
      console.error('order not found', outTradeNo)
      return fail('order not found')
    }
    if (order.openid !== openid) return fail('openid mismatch')

    return eventType === REFUND_EVENT
      ? await refund(orders, entitlements, order, payload)
      : await deliver(orders, entitlements, order, payload)
  } catch (error) {
    console.error('virtualPayNotify failed', error)
    return fail(error.message || 'notify failed')
  }
}
