/**
 * 报告公共部分：样式、转义、标签。
 *
 * 单日报告与窗口报告共用同一套版式——两份报告如果各写一套 CSS，
 * 迟早会出现「同一份材料两种字号」的尴尬。
 */

import type { Tendency } from '@core/zeri/types'

export const TENDENCY_LABEL: Record<Tendency, string> = {
  favorable: '偏合',
  neutral: '中性',
  unfavorable: '偏忌',
  insufficient_data: '数据不足',
}

export const CONSENSUS_LABEL: Record<string, string> = {
  favorable: '多数流派并宜',
  mixed: '流派分歧',
  unfavorable: '多数流派并忌',
  rejected: '已被前置层排除',
  insufficient: '可判依据不足',
}

export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function list(items: string[], emptyText = '—'): string {
  if (!items.length) return `<span class="muted">${escapeHtml(emptyText)}</span>`
  return items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')
}

/** 五派倾向的一句话摘要：宜 n · 平 n · 忌 n · 据不足 n */
export function tendencySummary(schools: Array<{ tendency: Tendency }>): string {
  if (!schools.length) return '—'
  const count = (value: Tendency) => schools.filter((item) => item.tendency === value).length
  const parts = [
    `宜 ${count('favorable')}`,
    `平 ${count('neutral')}`,
    `忌 ${count('unfavorable')}`,
  ]
  const unknown = count('insufficient_data')
  if (unknown) parts.push(`据不足 ${unknown}`)
  return parts.join(' · ')
}

export const REPORT_CSS = `
  @page {
    size: A4;
    margin: 18mm 16mm;
    /* CSS Paged Media 的页脚页码：WeasyPrint / Prince 等引擎支持；
       Chrome 的打印对话框不实现 margin box，需用户勾选「页眉和页脚」。 */
    @bottom-center {
      content: "第 " counter(page) " 页 / 共 " counter(pages) " 页";
      font-size: 9px;
      color: #8a7f70;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 24px;
    font-family: "Songti SC", "Source Han Serif SC", "Noto Serif CJK SC", serif;
    color: #2b2620; background: #fbf7ef; font-size: 13px; line-height: 1.7;
  }
  .sheet { max-width: 820px; margin: 0 auto; background: #fffdf8; padding: 32px 36px; border: 1px solid rgba(43,38,32,.12); }
  h1 { font-size: 22px; margin: 0 0 4px; letter-spacing: .06em; }
  h2 { font-size: 15px; margin: 26px 0 10px; padding-bottom: 6px; border-bottom: 1px solid rgba(43,38,32,.15); break-after: avoid; }
  h3 { font-size: 13px; margin: 16px 0 6px; break-after: avoid; }
  .meta { margin: 0; color: #8a7f70; font-size: 11px; }
  .muted { color: #8a7f70; }
  .serif { font-family: inherit; }
  .count { margin-left: 8px; color: #8a7f70; font-size: 11px; font-weight: normal; }
  table { width: 100%; border-collapse: collapse; margin: 6px 0 4px; }
  th, td { text-align: left; vertical-align: top; padding: 5px 8px 5px 0; font-size: 12px; }
  thead { break-inside: avoid; }
  tr { break-inside: avoid; }
  thead th { color: #8a7f70; font-weight: 500; border-bottom: 1px solid rgba(43,38,32,.18); }
  tbody tr { border-bottom: 1px dashed rgba(43,38,32,.12); }
  .grid th:first-child, .grid td:first-child { width: 22%; }
  .kv th { width: 96px; color: #8a7f70; font-weight: 500; }
  .note { margin: 6px 0; color: #8a7f70; font-size: 11px; }
  .note.warn { color: #b08a4f; }
  .verdict { margin: 8px 0; padding: 10px 14px; border-left: 3px solid #3f6b5a; background: rgba(63,107,90,.08); font-size: 14px; break-inside: avoid; }
  .verdict.bad { border-left-color: #a8442a; background: rgba(168,68,42,.08); }
  .tag { display: inline-block; margin-left: 6px; padding: 0 8px; border-radius: 999px; border: 1px solid rgba(43,38,32,.2); font-size: 10px; color: #5e5548; }
  .tag.warn { color: #b08a4f; border-color: #b08a4f; }
  .school { margin-bottom: 14px; break-inside: avoid; }
  .school-head { display: flex; align-items: center; gap: 4px; }
  ul { margin: 4px 0; padding-left: 18px; }
  li { font-size: 12px; }
  .stat-row { display: flex; gap: 10px; margin: 10px 0; break-inside: avoid; }
  .stat { flex: 1; padding: 10px 12px; border: 1px solid rgba(43,38,32,.12); border-radius: 8px; background: #fff; }
  .stat b { display: block; font-size: 20px; font-weight: normal; }
  .stat span { color: #8a7f70; font-size: 11px; }
  .print-hint { margin: 10px 0 0; padding: 8px 12px; border-radius: 6px; background: rgba(176,138,79,.12); color: #8a7f70; font-size: 11px; }
  footer { margin-top: 28px; padding-top: 10px; border-top: 1px solid rgba(43,38,32,.15); color: #8a7f70; font-size: 10px; line-height: 1.7; break-inside: avoid; }
  @media print {
    body { background: #fff; padding: 0; }
    .sheet { border: none; padding: 0; max-width: none; }
    .print-hint { display: none; }
  }
`

/** 打印提示：屏幕上显示，打印时隐藏。 */
export const PRINT_HINT =
  '打印提示：用 Chrome 打印时勾选「页眉和页脚」可显示页码；用支持 CSS Paged Media 的引擎（如 WeasyPrint）导出会自动带「第 n 页 / 共 m 页」。'

