import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { resolveFenJin, describeFenJin, FENJIN_SLOTS } from '@/core/constants/fenjin120'
import { analyzeXianMing, analyzeYinMatch } from '@/core/engines/xianming'
import { resolveMountain } from '@/core/constants/shan24'
import type { YinData } from '@/core/types'

/**
 * 施工依据 v1.0 §0.3 与附录 E 第 6 条：
 * 120 分金的旺相/孤虚/空亡吉凶口径未经三源核验，首版只做几何事实，
 * 不得在 UI、报告、禁忌命中、建议分金里出现吉凶结论。此测试锁死该红线。
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

  it('describeFenJin 只含几何事实与纳音', () => {
    for (let deg = 0; deg < 360; deg += 7) {
      const d = describeFenJin(resolveFenJin(deg).slot)
      for (const word of BANNED) {
        expect(d, `${deg}° 描述不得出现「${word}」`).not.toContain(word)
      }
    }
  })

  it('仙命分析不产生分金吉凶禁忌，verdict 不依赖未核验分类', () => {
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

  it('建议分金不再按「旺相」预筛：同一坐山各线度给出的候选一致', () => {
    // 旧实现对子山只把「旺相」两格当候选；现在候选是本山全部 5 格再按纳音筛。
    // 所以换一条线度（仙命不变）不会改变候选集合——线度只决定「当前在哪格」，不该决定「哪格可用」。
    const yin: YinData = {
      monumentType: 'SINGLE',
      deceased: [{ label: '先人', birth: { date: '1950-03-15' } }],
      descendants: [],
      terrain: { backSupport: 'STRONG', frontView: 'OPEN', leftRight: 'BALANCED' },
    }
    const at = (deg: number) => analyzeYinMatch(yin, '子', resolveFenJin(deg)).suggestedSlots
    expect(at(0)).toEqual(at(3))
    expect(at(0)).toEqual(at(357))
  })
})

/**
 * 吉凶分类已从类型与引擎里拆除（2026-11-26）。这条回归直接扫源码：
 * 枚举名、吉凶布尔字段、按分金字段着色，任何一个回到界面或核心代码都算回退。
 * `npm run scan` 里有同样的规则；这里再锁一遍，让它在 `npm test` 里也必红。
 */
describe('分金吉凶枚举不得回到代码与界面', () => {
  const root = path.resolve(process.cwd())
  const walk = (dir: string): string[] => {
    const full = path.join(root, dir)
    if (!fs.existsSync(full)) return []
    return fs.readdirSync(full, { withFileTypes: true }).flatMap((entry) => {
      if (entry.name === 'node_modules' || entry.name === 'dist') return []
      const rel = path.join(dir, entry.name)
      return entry.isDirectory() ? walk(rel) : [rel]
    })
  }

  const ENUM = /\b(WANG_XIANG|KONG_WANG|GU_XU|FenJinQuality|usableForYin|suggestFenJinSlots|nearestUsableSlot|qualityLabel|qualityDetail)\b/
  const UI_BINDING = /:(class|fill|style)=\"[^\"]*\.quality\b/

  it('src 与 desktop/src 中没有分金吉凶标识符', () => {
    const files = [...walk('src'), ...walk('desktop/src')].filter((file) => /\.(ts|vue|js)$/.test(file))
    expect(files.length).toBeGreaterThan(50)
    const offenders: string[] = []
    for (const file of files) {
      const text = fs.readFileSync(path.join(root, file), 'utf8')
      if (ENUM.test(text) || UI_BINDING.test(text)) offenders.push(file)
    }
    expect(offenders).toEqual([])
  })

  it('FenJinSlot 的字段里没有吉凶分类', () => {
    for (const slot of FENJIN_SLOTS) {
      expect(Object.keys(slot)).not.toContain('quality')
      expect(Object.keys(slot)).not.toContain('usableForYin')
    }
  })
})
