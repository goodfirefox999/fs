const path = require('node:path')

const FALLBACK_NAME = '居境罗盘档案.json'

/**
 * 渲染进程只能决定导出文件的「名字」，不能决定落盘目录。
 * 按两种目录分隔符切段取最后一段（POSIX 与 Windows 路径都吃得下），
 * 剥控制字符、去前导点（防 .hidden 与 ..）、限长 80 字符，最后强制后缀。
 *
 * `ext` 默认 json；报告导出传 'html'。后缀只允许字母数字，避免被塞进路径片段。
 */
function safeExportName(raw, fallback = FALLBACK_NAME, ext = 'json') {
  const safeExt = /^[a-z0-9]+$/i.test(String(ext)) ? String(ext) : 'json'
  const cleaned = String(raw ?? '').replace(/[\u0000-\u001f\u007f]/g, '')
  const segments = cleaned.split(/[/\\]+/).filter(Boolean)
  const last = segments.length ? path.basename(segments[segments.length - 1]) : ''
  const base = last.replace(/^\.+/, '').trim().slice(0, 80).trim()
  if (!base) return fallback
  const suffix = new RegExp(`\\.${safeExt}$`, 'i')
  return suffix.test(base) ? base : `${base}.${safeExt}`
}

module.exports = { safeExportName, FALLBACK_NAME }
