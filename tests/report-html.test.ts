import { describe, expect, it } from 'vitest'
import { evaluateDay, type DayEvaluation } from '@core/zeri/evaluate'
import { RULE_PACK_VERSION } from '@core/zeri/version'
import { renderReportHtml, type ReportMeta } from '@desktop/report/html'

const META: ReportMeta = {
  generatedAt: '2026-11-02 12:00',
  taskLabel: '动土修造',
  mountShan: '午',
  sittingDeg: 180,
  inputHash: 'abcdef0123456789'.padEnd(64, '0'),
  windowNote: '2026-11-01 起 90 天',
}

function evalOf(date: string, mountShan = '午'): DayEvaluation {
  return evaluateDay({ date, category: 'YANG_DONGTU', mountShan, eventYear: 2026 })
}

describe('复核报告 HTML', () => {
  const evaluation = evalOf('2026-11-18')
  const html = renderReportHtml(evaluation, META)

  it('是自包含 HTML：无外部脚本与样式表', () => {
    expect(html.startsWith('<!doctype html>')).toBe(true)
    expect(html).toContain('<style>')
    expect(html).not.toMatch(/<script\s+src=/i)
    expect(html).not.toMatch(/<link[^>]+stylesheet/i)
  })

  it('五个分节齐全', () => {
    for (const section of ['一、输入', '二、结论', '三、前置层', '四、五派并列', '五、说明与边界']) {
      expect(html, `缺少分节「${section}」`).toContain(section)
    }
  })

  it('带规则包版本与输入哈希前缀，便于两次运行对比', () => {
    expect(html).toContain(RULE_PACK_VERSION)
    expect(html).toContain('abcdef01')
  })

  it('带免责声明与不承诺准确率的措辞', () => {
    expect(html).toContain('不构成工程安全')
    expect(html).toContain('不承诺准确率')
    expect(html).toContain('需人工复核')
  })

  it('打印友好：页码规则、防跨页断裂、打印提示', () => {
    // CSS Paged Media 页脚页码（WeasyPrint 等支持）
    expect(html).toContain('@bottom-center')
    expect(html).toContain('counter(page)')
    expect(html).toContain('counter(pages)')
    // 标题不与正文分离、表格行不跨页
    expect(html).toContain('break-after: avoid')
    expect(html).toContain('break-inside: avoid')
    // 屏幕上给出 Chrome 的页码开关提示，打印时隐藏
    expect(html).toContain('print-hint')
    expect(html).toContain('页眉和页脚')
    expect(html).toMatch(/@media print[\s\S]*?\.print-hint\s*\{\s*display:\s*none/)
  })

  it('把用户可控文本转义，不执行注入', () => {
    const injected = renderReportHtml(evaluation, {
      ...META,
      taskLabel: '<script>alert(1)</script>',
      mountShan: '"><img src=x onerror=alert(1)>',
    })
    expect(injected).not.toContain('<script>alert(1)</script>')
    expect(injected).toContain('&lt;script&gt;')
    expect(injected).not.toContain('onerror=alert(1)>')
  })
})

describe('被前置层排除的日期', () => {
  it('报告说明「不进入五派评分」，而不是留空', () => {
    let rejected: DayEvaluation | null = null
    for (let offset = 0; offset < 60 && !rejected; offset++) {
      const date = new Date(Date.UTC(2026, 10, 1 + offset)).toISOString().slice(0, 10)
      const evaluation = evalOf(date)
      if (evaluation.dasha.rejected) rejected = evaluation
    }
    expect(rejected, '60 天内应至少有一天被前置层排除').toBeTruthy()

    const html = renderReportHtml(rejected!, META)
    expect(html).toContain('已被前置层排除')
    expect(html).toContain('不进入五派评分')
  })
})

describe('报告档案归因章节', () => {
  const evaluation = evalOf('2026-11-18')

  it('无归因时不渲染该节', () => {
    const html = renderReportHtml(evaluation, META)
    expect(html).not.toContain('与上次保存的结论对比')
  })

  it('有归因时渲染归因类型与叙述', () => {
    const html = renderReportHtml(evaluation, {
      ...META,
      attribution: { kind: 'rules_only', narrative: '归因：rulePackVersion 1.0.0 → 1.1.0，输入未变' },
    })
    expect(html).toContain('与上次保存的结论对比')
    expect(html).toContain('仅规则包变化')
    expect(html).toContain('rulePackVersion 1.0.0 → 1.1.0')
  })

  it('结论不稳定时以醒目样式呈现', () => {
    const html = renderReportHtml(evaluation, {
      ...META,
      attribution: { kind: 'unstable', narrative: '输入与规则包均未变化，但结论不同' },
    })
    expect(html).toContain('结论不稳定')
    expect(html).toContain('verdict bad')
  })
})
