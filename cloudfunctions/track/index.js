const cloud = require('wx-server-sdk')

cloud.init({ env: cloud.DYNAMIC_CURRENT_ENV })

const EVENTS = new Set([
  'app_launch',
  'archive_create',
  'report_view',
  'report_unlock',
  'compass_save',
  'zeri_query',
  'poster_save',
])

exports.main = async (event) => {
  const { OPENID } = cloud.getWXContext()
  if (!OPENID) return { ok: false, message: '缺少微信身份信息' }
  const name = String(event.event || '')
  if (!EVENTS.has(name)) return { ok: false, message: '未知事件' }
  const props = event.props && typeof event.props === 'object' ? event.props : {}

  const db = cloud.database()
  try {
    await db.collection('events').add({
      data: {
        openid: OPENID,
        event: name,
        props: JSON.stringify(props).slice(0, 2000),
        createdAt: Date.now(),
      },
    })
  } catch (error) {
    console.error('track failed', error)
    return { ok: false, message: '记录失败' }
  }
  return { ok: true, data: { recorded: true } }
}
