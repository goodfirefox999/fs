import { describe, expect, it } from 'vitest'
import { resolveFenJin, qualityLabel, describeFenJin } from '@/core/constants/fenjin120'
import { analyzeXianMing } from '@/core/engines/xianming'
import { resolveMountain } from '@/core/constants/shan24'

/**
 * 施工依据 v1.0 §0.3 与附录 E 第 6 条：
 * 120 分金的旺相/孤虚/空亡吉凶口径未经三源核验，首版只做几何事实，
 * 不得在 UI、报告、禁忌命中中出现吉凶结论。此测试锁死该红线。
 */
describe('分金合规红线：不输出未核验吉凶', () => {
  const BANNED = ['旺相', '孤虚', '空亡', '龟甲', '阳孤', '阴虚', '煞曜']

  it('resolveFenJin 的 120 格 warning 均不含吉凶词', () => {
    for (let deg = 0; deg < 360; deg += 0.5) {
      const r = resolveFenJin(deg)
      if (!r.warning) continue
      for (const word of BANNED) {
        expect(r.warning, `${deg}° warning 不得出现「${word}」`).not.toContain(word)
      }
    }
  })

  it('qualityLabel 对用户只返回未核验，不暴露吉凶分类', () => {
    expect(qualityLabel('WANG_XIANG')).toBe('未核验')
    expect(qualityLabel('GU_XU')).toBe('未核验')
    expect(qualityLabel('KONG_WANG')).toBe('未核验')
  })

  it('describeFenJin 只含几何事实与纳音', () => {
    for (let deg = 0; deg < 360; deg += 7) {
      const d = describeFenJin(resolveFenJin(deg).slot)
      for (const word of BANNED) {
        expect(d, `${deg}° 描述不得出现「${word}」`).not.toContain(word)
      }
    }
  })

  it('仙命分析不产生分金吉凶禁忌，verdict 不依赖未核验 quality', () => {
    const person = { label: '先父', birth: { date: '1950-03-15' } }
    for (const deg of [0, 3, 22.5, 97, 180, 275]) {
      const result = analyzeXianMing(person, resolveMountain(deg).name, resolveFenJin(deg))
      if (!result) continue
      const codes = result.tabooHits.map((h) => h.code)
      expect(codes, `${deg}° 不得有分金吉凶禁忌`).not.toContain('FENJIN_KONG_WANG')
      expect(codes, `${deg}° 不得有分金吉凶禁忌`).not.toContain('FENJIN_GU_XU')
      for (const hit of result.tabooHits) {
        for (const word of BANNED) {
          expect(hit.detail, `${deg}° 禁忌文案不得出现「${word}」`).not.toContain(word)
        }
      }
    }
  })
})
