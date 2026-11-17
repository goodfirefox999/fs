/**
 * 单日复核报告（自包含 HTML）。
 *
 * 为什么导出 HTML 而不是直接生成 PDF：
 * - 不引入字体嵌入、分页引擎与 PDF 库；
 * - 浏览器/Electron 自带「打印为 PDF」，用户随时可以自己转；
 * - 报告里的样式与文字能被人直接阅读、复制、存档。
 */

import type { DayEvaluation } from '@core/zeri/evaluate'
import { STANCE_LABELS, partitionDasha } from '@core/zeri/dasha'
import { RULE_PACK_VERSION } from '@core/zeri/version'
import { CONSENSUS_LABEL, PRINT_HINT, REPORT_CSS, TENDENCY_LABEL, escapeHtml } from './shared'

export interface ReportMeta {
  generatedAt: string
  taskLabel: string
  mountShan: string
  sittingDeg: number
  /** 输入哈希前 8 位，便于两次运行对比 */
  inputHash?: string
  /** 扫描窗口说明，例如「2026-11-01 起 90 天」 */
  windowNote?: string
}

export function renderReportHtml(evaluation: DayEvaluation, meta: ReportMeta): string {
  const { facts, dasha, schools, arbitration, context } = evaluation
  const groups = partitionDasha(dasha)
  const pillars = [
    ['年', facts.pillars.year],
    ['月', facts.pillars.month],
    ['日', facts.pillars.day],
    ['时', facts.pillars.hour],
  ] as const

  const pillarRows = pillars
    .map(([label, pillar]) =>
      pillar
        ? `<tr><th>${label}柱</th><td class="serif">${escapeHtml(pillar.ganZhi)}</td><td>${escapeHtml(pillar.nayin)}</td></tr>`
        : `<tr><th>${label}柱</th><td class="muted">未定时支</td><td>—</td></tr>`,
    )
    .join('')

  const dashaSection = (title: string, rows: typeof groups.blocks, note: string) => {
    if (!rows.length) return ''
    const body = rows
      .map(
        (hit) => `
        <tr>
          <td class="serif">${escapeHtml(hit.name)}</td>
          <td>${escapeHtml(hit.reason)}</td>
          <td>${hit.stance ? escapeHtml(STANCE_LABELS[hit.stance]) : '—'}</td>
          <td class="muted">${escapeHtml(hit.source.title)}</td>
        </tr>`,
      )
      .join('')
    return `
    <h3>${escapeHtml(title)}<span class="count">${rows.length} 条</span></h3>
    ${note ? `<p class="note">${escapeHtml(note)}</p>` : ''}
    <table class="grid">
      <thead><tr><th>名称</th><th>说明</th><th>出处立场</th><th>出处</th></tr></thead>
      <tbody>${body}</tbody>
    </table>`
  }

  const schoolSection = schools.length
    ? schools
        .map(
          (school) => `
      <div class="school">
        <div class="school-head">
          <b class="serif">${escapeHtml(school.schoolLabel)}</b>
          <span class="tag">${escapeHtml(TENDENCY_LABEL[school.tendency] ?? school.tendency)}</span>
          ${school.status !== 'FULL' ? `<span class="tag warn">${school.status === 'PARTIAL' ? '数据不足' : '不可用'}</span>` : ''}
        </div>
        ${school.partialReason ? `<p class="note">${escapeHtml(school.partialReason)}</p>` : ''}
        <table class="grid">
          <thead><tr><th>规则</th><th>判定</th><th>分值</th><th>依据</th></tr></thead>
          <tbody>
            ${school.subRules
              .map(
                (rule) => `
              <tr>
                <td>${escapeHtml(rule.name)}</td>
                <td class="serif">${escapeHtml(rule.verdict ?? '—')}</td>
                <td>${rule.scoreDelta > 0 ? '+' : ''}${rule.scoreDelta}</td>
                <td class="muted">${escapeHtml(rule.reasons.join('；') || rule.dataGap || '—')}</td>
              </tr>`,
              )
              .join('')}
          </tbody>
        </table>
        ${school.conflictFlags.map((flag) => `<p class="note warn">${escapeHtml(flag)}</p>`).join('')}
      </div>`,
        )
        .join('')
    : `<p class="note">本日已由前置层排除，按规则不进入五派评分环节。</p>`

  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>择日复核报告 · ${escapeHtml(evaluation.date)}</title>
<style>${REPORT_CSS}</style>
</head>
<body>
<div class="sheet">
  <h1>择日复核报告</h1>
  <p class="meta">
    ${escapeHtml(evaluation.date)} · ${escapeHtml(meta.taskLabel)} ·
    生成于 ${escapeHtml(meta.generatedAt)} ·
    规则包 ${escapeHtml(RULE_PACK_VERSION)}
    ${meta.inputHash ? ` · 输入哈希 ${escapeHtml(meta.inputHash.slice(0, 8))}` : ''}
  </p>
  <p class="print-hint">${PRINT_HINT}</p>

  <h2>一、输入</h2>
  <table class="kv">
    <tbody>
      <tr><th>用事</th><td>${escapeHtml(meta.taskLabel)}</td></tr>
      <tr><th>坐向</th><td>${escapeHtml(meta.mountShan)}山 · 线度 ${escapeHtml(meta.sittingDeg)}°（真北）</td></tr>
      <tr><th>日期</th><td>${escapeHtml(evaluation.date)}（${escapeHtml(facts.weekDay)} · ${escapeHtml(facts.lunarText)}）</td></tr>
      ${pillarRows}
      <tr><th>建除 / 值神</th><td>${escapeHtml(facts.zhiXing)}日 · ${escapeHtml(facts.tianShen)}（${escapeHtml(facts.tianShenType)}${escapeHtml(facts.tianShenLuck)}）</td></tr>
      <tr><th>二十八宿</th><td>${escapeHtml(facts.xiu)}（${escapeHtml(facts.xiuLuck)}）</td></tr>
      <tr><th>冲煞</th><td>冲${escapeHtml(facts.chongShengXiao)} · 煞${escapeHtml(facts.sha)}</td></tr>
      ${meta.windowNote ? `<tr><th>扫描窗口</th><td>${escapeHtml(meta.windowNote)}</td></tr>` : ''}
    </tbody>
  </table>

  <h2>二、结论</h2>
  <p class="verdict ${dasha.rejected ? 'bad' : ''}">
    ${escapeHtml(CONSENSUS_LABEL[arbitration.consensus] ?? arbitration.consensus)}
    ${dasha.rejected ? '——命中前置层大煞，不进入评分' : ''}
  </p>
  ${
    arbitration.conflicts.length
      ? `<h3>流派分歧<span class="count">${arbitration.conflicts.length} 处</span></h3>
         <ul>${arbitration.conflicts.map((item) => `<li>${escapeHtml(item.issue)}</li>`).join('')}</ul>`
      : ''
  }

  <h2>三、前置层（大煞）</h2>
  ${
    groups.blocks.length || groups.diverge.length || groups.folk.length
      ? [
          dashaSection('前置排除', groups.blocks, '命中即判不可用，吉星不覆盖。'),
          dashaSection('口径分歧提示', groups.diverge, '同一神煞在不同通书口径下结论不同，按提示处理。'),
          dashaSection('民俗口径提示', groups.folk, '按出处立场分档，严重度并不等同。'),
        ].join('')
      : '<p class="note">本日未命中前置层大煞。</p>'
  }

  <h2>四、五派并列</h2>
  ${schoolSection}

  <h2>五、说明与边界</h2>
  <ul>
    <li>本报告为传统规则整理与复核工具输出，<strong>不构成工程安全、结构鉴定、医疗、法律或规划意见</strong>。</li>
    <li>不承诺准确率，不提供「化解」建议；涉及施工、地质、消防与纪念地事项，须由专业人士现场复核。</li>
    <li>各派结论并列呈现，不做跨派合并；流派分歧与需人工复核项均已原样保留。</li>
    <li>所有规则当前均为待人工核对状态（verification_status = unverified），出处以报告所列为准。</li>
  </ul>

  <footer>
    居境罗盘 · 桌面工作台 · 规则包 ${escapeHtml(RULE_PACK_VERSION)} ·
    本文件为自包含 HTML，可用浏览器「打印为 PDF」归档。
  </footer>
</div>
</body>
</html>`
}
