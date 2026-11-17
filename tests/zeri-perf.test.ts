import { describe, expect, it } from 'vitest'
import { buildZeRi } from '@/core/engines/zeri'
import { evaluateDay } from '@/core/zeri/evaluate'

/**
 * 证据类测试：不测耗时，只测「报告里能不能看见该看见的东西」。
 *
 * 性能测试已拆到 `tests/bench/zeri-perf.test.ts`（独立配置、独占运行），
 * 原因见该文件顶部注释：全量并发会把耗时测量污染成假失败。
 */

const baseQuery = {
  startDate: '2026-12-01',
  category: 'YIN_ANZANG' as const,
  mountShan: '丙',
  familyBirths: [{ date: '1975-06-01', gender: 'M' as const }],
  maxResults: 20,
}

describe('吉星排除证据', () => {
  it('被大煞排除的三吉星之日在排除统计中留下可见证据', () => {
    const result = buildZeRi({ ...baseQuery, daysCount: 120 })
    const withLucky = result.rejections.filter((item) => item.luckyStarDays > 0)
    expect(withLucky.length, '至少一条大煞应排除过三吉星值日').toBeGreaterThan(0)
    const sample = withLucky[0]
    expect(sample.luckyStarSamples[0]).toMatch(/^\d{4}-\d{2}-\d{2} 值(煞贡|直星|人专)$/)
    expect(sample.luckyStarDays).toBeLessThanOrEqual(sample.count)
  })

  it('六凶星值日照实输出星名并标注不虚构分值', () => {
    let hit = false
    for (let d = 0; d < 60 && !hit; d++) {
      const date = new Date(Date.UTC(2026, 11, 1 + d)).toISOString().slice(0, 10)
      const e = evaluateDay({
        date,
        category: 'YANG_RUZHAI',
        mountShan: '乾',
        eventYear: 2026,
      })
      const rule = e.schools
        .find((school) => school.school === 'DONG_GONG')
        ?.subRules.find((item) => item.ruleId === 'DG_SHA_GONG_ZHI_XING_REN_ZHUAN')
      if (rule?.dataGap) {
        expect(rule.verdict).toBeTruthy()
        expect(rule.dataGap).toContain('不虚构分值')
        expect(rule.scoreDelta).toBe(0)
        expect(rule.needsHumanReview).toBe(true)
        hit = true
      }
    }
    expect(hit, '六十日内应至少遇到一次六凶星值日').toBe(true)
  })
})
