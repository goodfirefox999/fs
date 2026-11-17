import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import type { ContentBundle } from '@/core/types'

const ABSOLUTE = [
  '算命', '占卜', '预测', '改运', '转运', '化煞', '破解', '开光', '加持', '消灾',
  '解难', '辟邪', '镇宅', '大师', '祖传', '秘法', '灵验', '最灵', '保证', '必然',
  '凶宅', '血光', '破财', '灾祸', '克夫', '克妻', '绝后', '损丁', '庇佑',
  '升官发财', '鬼怪', '寻龙点穴',
]

const bundle = JSON.parse(
  fs.readFileSync(
    path.resolve(process.cwd(), 'cloudfunctions/getReportContent/content/shuangxing.json'),
    'utf8'
  )
) as ContentBundle

describe('内容库合规', () => {
  it('81 组完整', () => {
    expect(bundle.shuangxing).toHaveLength(81)
    const keys = new Set(bundle.shuangxing.map((item) => `${item.combo.shan}${item.combo.xiang}`))
    expect(keys.size).toBe(81)
  })

  it('无绝对禁词', () => {
    for (const item of bundle.shuangxing) {
      const text = [
        item.title,
        item.classic.paraphrase,
        item.analysis,
        ...item.actions,
        item.yin.analysis,
        ...item.yin.actions,
      ].join('\n')
      for (const word of ABSOLUTE) {
        expect(text, `${item.id} 命中 ${word}`).not.toContain(word)
      }
    }
  })

  it('阳宅与阴宅文本均有独立内容', () => {
    for (const item of bundle.shuangxing) {
      expect(item.analysis.length).toBeGreaterThan(40)
      expect(item.actions.length).toBeGreaterThanOrEqual(2)
      expect(item.yin.analysis).toContain('纪念地')
      expect(item.yin.actions.length).toBeGreaterThanOrEqual(2)
    }
  })
})
