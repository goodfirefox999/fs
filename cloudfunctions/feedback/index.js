const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

exports.main = async (event) => {
  const { OPENID } = cloud.getWXContext()
  if (!OPENID) return { ok: false, message: '缺少微信身份信息' }
  const content = String(event.content || '').trim()
  if (content.length < 4) return { ok: false, message: '请填写至少 4 个字的反馈' }
  if (content.length > 500) return { ok: false, message: '反馈内容过长，请精简到 500 字以内' }
  const contact = String(event.contact || '').trim().slice(0, 80)
  const category = String(event.category || 'OTHER').slice(0, 20)

  const db = cloud.database()
  try {
    await db.collection('feedback').add({
      data: {
        openid: OPENID,
        category,
        content,
        contact,
        createdAt: Date.now(),
      },
    })
  } catch (error) {
    console.error('feedback failed', error)
    return { ok: false, message: '反馈提交失败，请稍后再试' }
  }
  return { ok: true, data: { received: true } }
}
