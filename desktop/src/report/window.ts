/**
 * 窗口级报告：一次扫描的完整交付物。
 *
 * 与单日报告的区别：单日回答「这一天为什么能用/不能用」，
 * 窗口报告回答「这几个月里哪几天能用、其余为什么不能用」——
 * 后者才是拿去给主事人看的东西，所以它必须同时给出候选清单与排除统计。
 */

import type { ZeRiResult } from '@core/types'
import type { PaipanReport } from '@core/paipan'
import { RULE_PACK_VERSION } from '@core/zeri/version'
import { PRINT_HINT, REPORT_CSS, TENDENCY_LABEL, escapeHtml, tendencySummary } from './shared'

export interface WindowReportMeta {
  generatedAt: string
  taskLabel: string
  mountShan: string
  sittingDeg: number
  startDate: string
  daysCount: number
  inputHash?: string
  /** 同一坐向的排盘四派，附在报告末尾；缺省则不出这一节 */
  paipan?: PaipanReport
  /** 生成时使用的口径说明（如三煞层级、开关状态） */
  policyNotes?: string[]
}

function stat(label: string, value: number | string, hint?: string): string {
  return `<div class="stat"><b>${escapeHtml(value)}</b><span>${escapeHtml(label)}${
    hint ? ` · ${escapeHtml(hint)}` : ''
  }</span></div>`
}

export function renderWindowReportHtml(result: ZeRiResult, meta: WindowReportMeta): string {
  const endDate = (() => {
    const [year, month, day] = meta.startDate.split('-').map(Number)
    const end = new Date(Date.UTC(year, month - 1, day + meta.daysCount - 1))
    return end.toISOString().slice(0, 10)
  })()

  const items = [...result.items].sort((a, b) => a.solarDate.localeCompare(b.solarDate))
  const rejections = [...result.rejections].sort((a, b) => b.count - a.count)

  const candidateRows = items
    .map(
      (item) => `
      <tr>
        <td class="serif">${escapeHtml(item.solarDate)}</td>
        <td>${escapeHtml(item.weekDay)} · ${escapeHtml(item.lunarDate)}</td>
        <td class="serif">${escapeHtml(item.ganZhi)}</td>
        <td>${escapeHtml(item.zhiXing)} · ${escapeHtml(item.xiu)}（${escapeHtml(item.xiuLuck)}）</td>
        <td>${escapeHtml(tendencySummary(item.schools))}</td>
        <td>${escapeHtml(item.matchedYi.slice(0, 4).join('、') || '—')}</td>
        <td>${escapeHtml(item.levelName)}</td>
      </tr>`,
    )
    .join('')

  const rejectionRows = rejections
    .map(
      (item) => `
      <tr>
        <td class="serif">${escapeHtml(item.name)}</td>
        <td>${item.count}</td>
        <td>${escapeHtml(item.review ? '可人工复核后放宽' : '不可放宽')}</td>
        <td>${
          item.luckyStarDays
            ? `${item.luckyStarDays} 天 · ${escapeHtml(item.luckyStarSamples.join('，'))}`
            : '<span class="muted">—</span>'
        }</td>
        <td class="muted">${escapeHtml(item.source)}</td>
      </tr>`,
    )
    .join('')

  const paipanSection = meta.paipan
    ? `
  <h2>五、排盘（同一坐向）</h2>
  <p class="note">四派回答的不是同一个问题，并列展示，不做跨派合并。</p>
  ${meta.paipan.schools
    .map(
      (school) => `
    <div class="school">
      <div class="school-head">
        <b class="serif">${escapeHtml(school.schoolLabel)}</b>
        <span class="tag">${escapeHtml(TENDENCY_LABEL[school.tendency] ?? school.tendency)}</span>
        ${school.status !== 'FULL' ? '<span class="tag warn">数据不足</span>' : ''}
      </div>
      ${school.partialReason ? `<p class="note">${escapeHtml(school.partialReason)}</p>` : ''}
      <table class="grid">
        <thead><tr><th>规则</th><th>判定</th><th>依据</th></tr></thead>
        <tbody>
          ${school.subRules
            .map(
              (rule) => `
            <tr>
              <td>${escapeHtml(rule.name)}</td>
              <td class="serif">${escapeHtml(rule.verdict ?? '—')}</td>
              <td class="muted">${escapeHtml(rule.reasons.join('；') || rule.dataGap || '—')}</td>
            </tr>`,
            )
            .join('')}
        </tbody>
      </table>
      ${school.conflictFlags.map((flag) => `<p class="note warn">${escapeHtml(flag)}</p>`).join('')}
    </div>`,
    )
    .join('')}
  ${meta.paipan.dataGaps.length ? `<p class="note">数据缺口：${escapeHtml(meta.paipan.dataGaps.join('；'))}</p>` : ''}
  `
    : ''

  const policyList = (meta.policyNotes ?? [])
    .map((note) => `<li>${escapeHtml(note)}</li>`)
    .join('')

  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>择日窗口报告 · ${escapeHtml(meta.startDate)} 起 ${escapeHtml(meta.daysCount)} 天</title>
<style>${REPORT_CSS}</style>
</head>
<body>
<div class="sheet">
  <h1>择日窗口报告</h1>
  <p class="meta">
    ${escapeHtml(meta.taskLabel)} · ${escapeHtml(meta.mountShan)}山 ${escapeHtml(meta.sittingDeg)}°（真北）·
    ${escapeHtml(meta.startDate)} 至 ${escapeHtml(endDate)} ·
    生成于 ${escapeHtml(meta.generatedAt)} ·
    规则包 ${escapeHtml(RULE_PACK_VERSION)}
    ${meta.inputHash ? ` · 输入哈希 ${escapeHtml(meta.inputHash.slice(0, 8))}` : ''}
  </p>
  <p class="print-hint">${PRINT_HINT}</p>

  <h2>一、概览</h2>
  <div class="stat-row">
    ${stat('扫描天数', result.scanned)}
    ${stat('前置层排除', result.rejected, '命中大煞即不评分')}
    ${stat('宜忌不符', result.unmatched, '未被排除但不符合用事宜忌')}
    ${stat('候选', items.length)}
  </div>
  <p class="note">
    候选 = 通过前置层、且符合本次用事的通书宜忌。
    排除与不符的天数之和可能大于扫描天数，因为同一天可命中多条。
  </p>

  <h2>二、候选日<span class="count">${items.length} 天</span></h2>
  ${
    items.length
      ? `<table class="grid">
    <thead>
      <tr><th>日期</th><th>星期 / 农历</th><th>日干支</th><th>建除 · 宿</th><th>五派倾向</th><th>宜</th><th>等第</th></tr>
    </thead>
    <tbody>${candidateRows}</tbody>
  </table>
  <p class="note">五派倾向为各派原始输出的计数，不代表合并结论；单日依据请另出「单日复核报告」。</p>`
      : '<p class="verdict bad">本窗口内没有候选日。请查看下方排除统计，确认是条件过严还是窗口本身不宜。</p>'
  }

  <h2>三、前置层排除统计<span class="count">累计 ${rejections.reduce((sum, item) => sum + item.count, 0)} 次</span></h2>
  ${
    rejections.length
      ? `<table class="grid">
    <thead>
      <tr><th>大煞</th><th>天数</th><th>可否放宽</th><th>三吉星仍被排除</th><th>出处</th></tr>
    </thead>
    <tbody>${rejectionRows}</tbody>
  </table>
  <p class="note">同一日可犯多条，故累计次数大于排除天数。「三吉星仍被排除」是「吉星不解大煞」的可见证据。</p>`
      : '<p class="note">本窗口未命中前置层大煞。</p>'
  }

  <h2>四、筛选说明</h2>
  <ul>${result.notes.map((note) => `<li>${escapeHtml(note)}</li>`).join('')}</ul>
  ${policyList ? `<h3>本次口径</h3><ul>${policyList}</ul>` : ''}

  ${paipanSection}

  <h2>${meta.paipan ? '六' : '五'}、说明与边界</h2>
  <ul>
    <li>本报告为传统规则整理与筛选工具输出，<strong>不构成工程安全、结构鉴定、医疗、法律或规划意见</strong>。</li>
    <li>不承诺准确率；候选日仅表示「未触达本规则集所列禁忌」，不等于适宜施工或必吉。</li>
    <li>所有规则当前均为待人工核对状态（verification_status = unverified）；出处以报告所列为准。</li>
    <li>涉及施工、地质、消防与纪念地事项，须由专业人士现场复核后再决定。</li>
  </ul>

  <footer>
    居境罗盘 · 桌面工作台 · 规则包 ${escapeHtml(RULE_PACK_VERSION)} ·
    本文件为自包含 HTML，可用浏览器「打印为 PDF」归档。
  </footer>
</div>
</body>
</html>`
}
