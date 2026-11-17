const crypto = require('crypto')
const https = require('https')
const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const PRODUCTS = {
  report_single_990: { price: 990, title: '单份完整分析' },
}

const ARCHIVE_ID_PATTERN = /^a_[a-z0-9_]{4,40}$/

function getEnv(name) {
  const value = process.env[name]
  if (!value) throw new Error(`缺少环境变量 ${name}`)
  return value
}

function httpsGetJson(url) {
  return new Promise((resolve, reject) => {
    const request = https.get(url, (response) => {
      let body = ''
      response.on('data', (chunk) => {
        body += chunk
      })
      response.on('end', () => {
        try {
          resolve(JSON.parse(body))
        } catch {
          reject(new Error('微信接口返回非 JSON'))
        }
      })
    })
    request.on('error', reject)
    request.setTimeout(8000, () => request.destroy(new Error('微信接口超时')))
  })
}

async function code2Session(code) {
  const appid = getEnv('WX_APPID')
  const secret = getEnv('WX_SECRET')
  const url =
    'https://api.weixin.qq.com/sns/jscode2session' +
    `?appid=${encodeURIComponent(appid)}` +
    `&secret=${encodeURIComponent(secret)}` +
    `&js_code=${encodeURIComponent(code)}` +
    '&grant_type=authorization_code'
  const result = await httpsGetJson(url)
  if (!result.openid || !result.session_key) {
    throw new Error(result.errmsg || '微信登录校验失败')
  }
  return result
}

function hmacHex(key, message) {
  return crypto.createHmac('sha256', key).update(message, 'utf8').digest('hex')
}

exports.main = async (event) => {
  try {
    const { OPENID } = cloud.getWXContext()
    if (!OPENID) return { ok: false, message: '缺少微信身份信息' }

    const code = String(event.code || '')
    const productId = String(event.productId || '')
    const archiveId = String(event.archiveId || '')
    if (!code) return { ok: false, message: '缺少登录凭证' }
    if (!ARCHIVE_ID_PATTERN.test(archiveId)) {
      return { ok: false, message: '档案编号无效' }
    }
    const product = PRODUCTS[productId]
    if (!product) return { ok: false, message: '商品不存在' }

    const session = await code2Session(code)
    if (session.openid !== OPENID) {
      return { ok: false, message: '登录身份与当前用户不一致' }
    }

    const db = cloud.database()
    const now = Date.now()

    // 防重（施工依据 §9.3.4：写库前查重）：同一用户+档案+商品若已有 PENDING 订单，
    // 直接复用原 outTradeNo 与签名参数。否则重复点击会生成多笔待支付单，
    // 用户可能为同一份报告付两次钱，且回调侧的幂等无法覆盖「两笔都支付成功」。
    const PENDING_WINDOW_MS = 30 * 60 * 1000
    const existing = await db.collection('orders').where({
      openid: OPENID,
      archiveId,
      productId,
      status: 'PENDING',
      createdAt: cloud.database().command.gte(now - PENDING_WINDOW_MS),
    }).orderBy('createdAt', 'desc').limit(1).get()

    let outTradeNo
    if (existing.data && existing.data.length) {
      outTradeNo = existing.data[0].outTradeNo
    } else {
      outTradeNo = `R${now.toString(36)}${crypto.randomBytes(5).toString('hex')}`
      const order = {
        outTradeNo,
        openid: OPENID,
        archiveId,
        productId,
        price: product.price,
        title: product.title,
        status: 'PENDING',
        createdAt: now,
      }
      await db.collection('orders').add({ data: order })
    }

    const signData = JSON.stringify({
      offerId: getEnv('XPAY_OFFER_ID'),
      buyQuantity: 1,
      env: Number(process.env.XPAY_ENV || 0),
      currencyType: 'CNY',
      platform: process.env.XPAY_PLATFORM || 'android',
      productId,
      goodsPrice: product.price,
      outTradeNo,
      attach: archiveId,
    })
    const signUri = process.env.XPAY_SIGN_URI || 'requestVirtualPayment'
    const paySig = hmacHex(getEnv('XPAY_APP_KEY'), `${signUri}&${signData}`)
    const signature = hmacHex(session.session_key, signData)

    return {
      ok: true,
      data: {
        outTradeNo,
        signData,
        paySig,
        signature,
        mode: 'short_series_goods',
      },
    }
  } catch (error) {
    console.error('createVirtualOrder failed', error)
    return { ok: false, message: error.message || '下单失败' }
  }
}
