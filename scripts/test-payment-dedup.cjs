/**
 * 支付下单防重回归（施工依据 §9.3.4：写库前查重）。
 * 用 mock 的 wx-server-sdk 与 https 模块，验证同一用户+档案+商品
 * 在 30 分钟窗口内重复下单只产生一条 PENDING 订单，且复用原 outTradeNo。
 */
const assert = require('node:assert')
const Module = require('node:module')

const orders = []
let existingResult = { data: [] }
const command = { gte: (v) => ({ $gte: v }) }
const mockDb = {
  command,
  collection: (name) => {
    assert.strictEqual(name, 'orders')
    return {
      where: (cond) => ({
        orderBy: () => ({ limit: () => ({ get: async () => existingResult }) }),
      }),
      add: async ({ data }) => orders.push(data),
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
  if (request === 'https') {
    return {
      get: (_url, cb) => {
        const ev = new (require('node:events').EventEmitter)()
        ev.setTimeout = () => {}
        process.nextTick(() => cb({
          on: (e, fn) => { if (e === 'data') fn('{"openid":"openid_test","session_key":"sk"}'); if (e === 'end') fn() },
        }))
        return ev
      },
    }
  }
  return originalLoad(request, parent, isMain)
}

process.env.WX_APPID = 'wx_mock'
process.env.WX_SECRET = 'secret'
process.env.XPAY_OFFER_ID = 'offer'
process.env.XPAY_APP_KEY = 'key'

const fn = require('../cloudfunctions/createVirtualOrder/index.js')

async function main() {
  const event = { code: 'code', productId: 'report_single_990', archiveId: 'a_test001' }

  const r1 = await fn.main(event)
  assert.strictEqual(r1.ok, true, `首次下单应成功: ${r1.message}`)
  assert.strictEqual(orders.length, 1)
  const firstNo = r1.data.outTradeNo

  // 模拟库中已有刚才那笔 PENDING 单
  existingResult = { data: [{ outTradeNo: firstNo }] }
  const r2 = await fn.main(event)
  assert.strictEqual(r2.ok, true, `重复下单应成功复用: ${r2.message}`)
  assert.strictEqual(orders.length, 1, '重复下单不得新增订单')
  assert.strictEqual(r2.data.outTradeNo, firstNo, '重复下单应复用原 outTradeNo')

  console.log('支付防重测试通过：2 次调用只产生 1 笔订单，且复用 outTradeNo')
}

main().catch((e) => { console.error(e); process.exit(1) })
