/**
 * 退款回调守卫回归（2026-11-26）：refund 只允许从 PAID 状态进入。
 *
 * 伪造的 refund 通知打在 PENDING 订单上时：不得删除权益、不得改订单状态，
 * 但应答仍为 success（不给攻击者探测信号，也避免微信重试）。
 * mock 风格与 test-payment-dedup.cjs 一致（替换 wx-server-sdk）。
 */
const assert = require('node:assert')
const Module = require('node:module')

process.env.XPAY_NOTIFY_TOKEN = 'token_test'
process.env.XPAY_ENV = '0'

let orderDoc = null
const removedEntitlements = []
const updates = []

const mockDb = {
  collection: (name) => {
    if (name === 'orders') {
      return {
        where: (cond) => ({
          limit: () => ({
            get: async () => ({ data: orderDoc && orderDoc.outTradeNo === cond.outTradeNo ? [orderDoc] : [] }),
          }),
        }),
        doc: (id) => ({
          update: async ({ data }) => {
            assert.strictEqual(id, orderDoc._id)
            updates.push(data)
            Object.assign(orderDoc, data)
          },
        }),
      }
    }
    assert.strictEqual(name, 'entitlements')
    return {
      doc: (id) => ({
        remove: async () => removedEntitlements.push(id),
      }),
    }
  },
}

const originalLoad = Module._load
Module._load = function (request, parent, isMain) {
  if (request === 'wx-server-sdk') {
    return {
      DYNAMIC_CURRENT_ENV: 'mock',
      init: () => {},
      getWXContext: () => ({ OPENID: 'openid_test' }),
      database: () => mockDb,
    }
  }
  return originalLoad.apply(this, arguments)
}

const notify = require('../cloudfunctions/virtualPayNotify/index.js')
Module._load = originalLoad

function refundEvent(outTradeNo, openid) {
  return {
    queryStringParameters: { token: 'token_test' },
    body: JSON.stringify({
      MsgType: 'event',
      Env: 0,
      Event: 'xpay_refund_notify',
      OutTradeNo: outTradeNo,
      OpenId: openid,
      BillNo: 'BILL_1',
    }),
  }
}

async function main() {
  // 场景 1：PENDING 订单收到伪造 refund → 权益不动、订单不动、幂等成功
  orderDoc = {
    _id: 'o1', outTradeNo: 'R1', openid: 'openid_test', archiveId: 'a1',
    status: 'PENDING', productId: 'report_single_990',
  }
  let res = await notify.main(refundEvent('R1', 'openid_test'))
  assert.deepStrictEqual(res, { ErrCode: 0, ErrMsg: 'success' })
  assert.strictEqual(orderDoc.status, 'PENDING', 'PENDING 订单不得被改成 REFUNDED')
  assert.strictEqual(removedEntitlements.length, 0, 'PENDING 订单不得删除权益')
  assert.strictEqual(updates.length, 0)

  // 场景 2：PAID 订单收到 refund → 正常退款收权
  orderDoc = {
    _id: 'o2', outTradeNo: 'R2', openid: 'openid_test', archiveId: 'a2',
    status: 'PAID', productId: 'report_single_990',
  }
  res = await notify.main(refundEvent('R2', 'openid_test'))
  assert.deepStrictEqual(res, { ErrCode: 0, ErrMsg: 'success' })
  assert.strictEqual(orderDoc.status, 'REFUNDED')
  assert.deepStrictEqual(removedEntitlements, ['openid_test_a2'])

  // 场景 3：已 REFUNDED 订单重复通知 → 幂等成功，可重复收权（防御残留）
  removedEntitlements.length = 0
  res = await notify.main(refundEvent('R2', 'openid_test'))
  assert.deepStrictEqual(res, { ErrCode: 0, ErrMsg: 'success' })
  assert.strictEqual(orderDoc.status, 'REFUNDED')
  assert.deepStrictEqual(removedEntitlements, ['openid_test_a2'])

  console.log('✅ refund 守卫回归通过：PAID 才可退款收权，PENDING/未知状态幂等拒绝')
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
