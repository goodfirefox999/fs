import { describe, expect, it } from 'vitest'
import type { ZeRiResult } from '@core/types'
import { buildZeRi } from '@core/engines/zeri'
import { buildPaipanReport } from '@core/paipan'
import { RULE_PACK_VERSION } from '@core/zeri/version'
import { renderWindowReportHtml, type WindowReportMeta } from '@desktop/report/window'

const META: WindowReportMeta = {
  generatedAt: '2026-11-02 12:00',
  taskLabel: '动土修造',
  mountShan: '午',
  sittingDeg: 180,
  startDate: '2026-11-01',
  daysCount: 30,
  inputHash: 'abcdef0123456789'.padEnd(64, '0'),
}

function scan(): ZeRiResult {
  return buildZeRi({
    startDate: META.startDate,
    daysCount: META.daysCount,
    category: 'YANG_DONGTU',
    mountShan: META.mountShan,
    eventYear: 2026,
    maxResults: 20,
  })
}

describe('窗口报告', () => {
  const result = scan()
  const html = renderWindowReportHtml(result, META)

  it('是自包含 HTML，且带四个主要分节', () => {
    expect(html.startsWith('<!doctype html>')).toBe(true)
    expect(html).not.toMatch(/<script\s+src=/i)
    expect(html).not.toMatch(/<link[^>]+stylesheet/i)
    for (const section of ['一、概览', '二、候选日', '三、前置层排除统计', '四、筛选说明']) {
      expect(html, `缺少分节「${section}」`).toContain(section)
    }
  })

  it('概览给出扫描/排除/不符/候选四个数字', () => {
    expect(html).toContain(String(result.scanned))
    expect(html).toContain('前置层排除')
    expect(html).toContain('宜忌不符')
    expect(html).toContain('候选')
  })

  it('候选日表带五派倾向计数，而不是合并结论', () => {
    if (result.items.length) {
      expect(html).toContain('五派倾向')
      expect(html).toMatch(/宜 \d+ · 平 \d+ · 忌 \d+/)
      expect(html).toContain('不代表合并结论')
    }
  })

  it('排除统计带「三吉星仍被排除」的证据列', () => {
    if (result.rejections.length) {
      expect(html).toContain('三吉星仍被排除')
      expect(html).toContain('吉星不解大煞')
    }
  })

  it('带规则包版本、输入哈希与免责声明', () => {
    expect(html).toContain(RULE_PACK_VERSION)
    expect(html).toContain('abcdef01')
    expect(html).toContain('不构成工程安全')
    expect(html).toContain('不承诺准确率')
  })

  it('打印友好：页码规则、防跨页断裂、打印提示', () => {
    expect(html).toContain('@bottom-center')
    expect(html).toContain('counter(page)')
    expect(html).toContain('counter(pages)')
    expect(html).toContain('break-after: avoid')
    expect(html).toContain('break-inside: avoid')
    expect(html).toContain('print-hint')
    expect(html).toContain('页眉和页脚')
    expect(html).toMatch(/@media print[\s\S]*?\.print-hint\s*\{\s*display:\s*none/)
  })

  it('转义用户可控文本', () => {
    const injected = renderWindowReportHtml(result, {
      ...META,
      taskLabel: '<img src=x onerror=alert(1)>',
    })
    expect(injected).not.toContain('onerror=alert(1)>')
    expect(injected).toContain('&lt;img')
  })
})

describe('窗口报告内嵌排盘', () => {
  const result = scan()
  const paipan = buildPaipanReport({
    mountShan: '午',
    sittingDeg: 180,
    year: 2026,
    members: [{ relation: '主命1', birth: { date: '1975-06-01', gender: 'M' } }],
  })

  it('有排盘时出第五节，四派并列', () => {
    const html = renderWindowReportHtml(result, { ...META, paipan })
    expect(html).toContain('排盘（同一坐向）')
    for (const label of ['八宅', '玄空飞星', '流年紫白', '仙命']) {
      expect(html, `排盘节缺少「${label}」`).toContain(label)
    }
    expect(html).toContain('六、说明与边界')
  })

  it('无排盘时不出该节，章节编号顺延', () => {
    const html = renderWindowReportHtml(result, META)
    expect(html).not.toContain('排盘（同一坐向）')
    expect(html).toContain('五、说明与边界')
  })
})

describe('无候选窗口', () => {
  it('明确说「没有候选日」，而不是留空表', () => {
    const empty: ZeRiResult = {
      items: [],
      scanned: 10,
      rejected: 10,
      unmatched: 0,
      eligible: 0,
      truncated: false,
      excludedByAlmanac: 0,
      excludedByHuangDao: 0,
      excludedByXiu: 0,
      rejections: [
        {
          name: '岁破',
          count: 10,
          review: false,
          source: '《协纪辨方书》',
          luckyStarDays: 2,
          luckyStarSamples: ['2026-11-03 值煞贡'],
          guidance: '本年岁破在午，坐午山兴工不可用',
        },
      ],
      notes: ['示例说明'],
    }
    const html = renderWindowReportHtml(empty, META)
    expect(html).toContain('没有候选日')
    expect(html).toContain('岁破')
    expect(html).toContain('值煞贡')
  })
})
