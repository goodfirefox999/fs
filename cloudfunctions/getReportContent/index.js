const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

exports.main = async (event) => {
  const { OPENID } = cloud.getWXContext()
  if (!OPENID) return { ok: false, message: '缺少微信身份信息' }
  const archiveId = String(event.archiveId || '')
  if (!archiveId) return { ok: false, message: '缺少档案编号' }

  const db = cloud.database()
  const found = await db
    .collection('entitlements')
    .where({ openid: OPENID, archiveId })
    .limit(1)
    .get()
  if (found.data.length === 0) {
    return { ok: false, message: '该档案尚未解锁完整分析' }
  }

  const content = require('./content/shuangxing.json')
  return { ok: true, data: content }
}
