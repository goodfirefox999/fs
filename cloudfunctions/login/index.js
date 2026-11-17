const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

exports.main = async () => {
  const { OPENID, UNIONID, APPID } = cloud.getWXContext()
  if (!OPENID) {
    return { ok: false, message: '缺少微信身份信息' }
  }
  const db = cloud.database()
  const users = db.collection('users')
  const now = Date.now()
  try {
    const existing = await users.where({ openid: OPENID }).limit(1).get()
    if (existing.data.length === 0) {
      await users.add({
        data: {
          openid: OPENID,
          unionid: UNIONID || '',
          createdAt: now,
          lastSeenAt: now,
        },
      })
    } else {
      await users.doc(existing.data[0]._id).update({ data: { lastSeenAt: now } })
    }
  } catch (error) {
    return { ok: false, message: `用户记录写入失败: ${error.message}` }
  }
  return { ok: true, data: { openid: OPENID, appid: APPID } }
}
