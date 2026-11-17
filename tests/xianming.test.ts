import { describe, expect, it } from 'vitest'
import {
  analyzeXianMing,
  analyzeYinMatch,
  relationText,
} from '@/core/engines/xianming'
import { resolveFenJin } from '@/core/constants/fenjin120'
import type { YinData } from '@/core/types'

const person = { label: '先人', birth: { date: '1950-06-15' } }

describe('仙命分析', () => {
  it('立春界', () => {
    const before = analyzeXianMing(
      { label: '先人', birth: { date: '1950-01-20' } },
      '午',
      resolveFenJin(183)
    )
    const after = analyzeXianMing(
      { label: '先人', birth: { date: '1950-02-10' } },
      '午',
      resolveFenJin(183)
    )
    expect(before?.effectiveYear).toBe(1949)
    expect(before?.ganZhi).toBe('己丑')
    expect(after?.effectiveYear).toBe(1950)
    expect(after?.ganZhi).toBe('庚寅')
  })

  it('纳音与坐山关系', () => {
    const analysis = analyzeXianMing(person, '午', resolveFenJin(183))
    expect(analysis?.nayin).toBe('松柏木')
    expect(analysis?.element).toBe('木')
    expect(analysis?.mountElement).toBe('火')
    expect(analysis?.mountRelation).toBe('MING_SHENG_SHAN')
    expect(analysis?.verdict).toBe('SUITABLE')
    expect(relationText('MING_SHENG_SHAN')).toContain('仙命纳音生坐山')
  })

  it('三煞山命中时建议回避', () => {
    const analysis = analyzeXianMing(person, '子', resolveFenJin(3))
    expect(analysis?.verdict).toBe('AVOID')
    expect(analysis?.tabooHits.some((hit) => hit.code === 'SAN_SHA_SHAN')).toBe(true)
    expect(analysis?.summary).toContain('回避')
  })

  it('分金吉凶不参与结论（合规红线）', () => {
    const analysis = analyzeXianMing(person, '午', resolveFenJin(180))
    // 180° 的戊午格旧口径判「空亡」，但未经三源核验，不得产生禁忌与调整建议。
    expect(analysis?.verdict).toBe('SUITABLE')
    expect(analysis?.tabooHits.some((hit) => hit.code === 'FENJIN_KONG_WANG')).toBe(false)
    expect(analysis?.tabooHits.some((hit) => hit.code === 'FENJIN_GU_XU')).toBe(false)
  })

  it('多仙命汇总与建议分金', () => {
    const yin: YinData = {
      monumentType: 'SINGLE',
      deceased: [person],
      descendants: [{ label: '家属', birth: { date: '1980-05-05', gender: 'M' } }],
      terrain: { backSupport: 'STRONG', frontView: 'OPEN', leftRight: 'BALANCED' },
    }
    const match = analyzeYinMatch(yin, '子', resolveFenJin(3))
    expect(match.verdict).toBe('AVOID')
    expect(match.deceased).toHaveLength(1)
    expect(match.suggestedSlots.length).toBeGreaterThan(0)
    expect(match.suggestedSlots.every((slot) => slot.usableForYin)).toBe(true)
    expect(match.notes.length).toBeGreaterThan(0)
  })
})
