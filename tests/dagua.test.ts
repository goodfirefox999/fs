import { describe, expect, it } from 'vitest'
import {
  HEXAGRAMS,
  YUN_CYCLE_YEARS,
  changedHexagram,
  guaYun,
  hexagramAt,
  trigramByLines,
  yunOfYear,
  yunSpans,
  yaoRole,
} from '@/core/zeri/tables/dagua64'

/** 罗盘刊本所载伏羲六十四卦圆图卦序（自子中 0° 顺行）。 */
const PUBLISHED_ORDER = [
  '复', '颐', '屯', '益', '震', '噬嗑', '随', '无妄',
  '明夷', '贲', '既济', '家人', '丰', '离', '革', '同人',
  '临', '损', '节', '中孚', '归妹', '睽', '兑', '履',
  '泰', '大畜', '需', '小畜', '大壮', '大有', '夬', '乾',
  '姤', '大过', '鼎', '恒', '巽', '井', '蛊', '升',
  '讼', '困', '未济', '解', '涣', '坎', '蒙', '师',
  '遁', '咸', '旅', '小过', '渐', '蹇', '艮', '谦',
  '否', '萃', '晋', '豫', '观', '比', '剥', '坤',
]

describe('玄空大卦圆图与卦运', () => {
  it('生成的 64 卦序与刊本逐字一致', () => {
    expect(HEXAGRAMS).toHaveLength(64)
    expect(HEXAGRAMS.map((item) => item.name)).toEqual(PUBLISHED_ORDER)
  })

  it('每卦 5.625°、每爻 0.9375°，复起子中、乾尽午中、坤尽子中', () => {
    expect(hexagramAt(0).hexagram.name).toBe('复')
    expect(hexagramAt(174.5).hexagram.name).toBe('乾')
    expect(hexagramAt(180).hexagram.name).toBe('姤')
    expect(hexagramAt(359).hexagram.name).toBe('坤')
    expect(hexagramAt(177.5, 'DESC').lineName).toBe('三爻')
    expect(hexagramAt(177.5, 'ASC').lineName).toBe('四爻')
    expect(HEXAGRAMS[0].lines).toEqual([1, 0, 0, 0, 0, 0])
  })

  it('卦运：父母卦坤 18 年管一运、乾 27 年管九运，别卦按上下卦对应爻异或定运，无五运', () => {
    // 八纯卦上下相同，异或必得坤（000），故刊本将八纯归一运
    expect(guaYun(HEXAGRAMS[63]).yun).toBe(1)
    expect(guaYun(HEXAGRAMS[31]).yun).toBe(1)
    const tai = HEXAGRAMS.find((item) => item.name === '泰') as (typeof HEXAGRAMS)[number]
    expect(guaYun(tai).yun).toBe(9)
    expect(trigramByLines([0, 0, 0]).years).toBe(18)
    expect(trigramByLines([0, 0, 0]).yun).toBe(1)
    expect(trigramByLines([1, 1, 1]).years).toBe(27)
    expect(trigramByLines([1, 1, 1]).yun).toBe(9)
    const yuns = HEXAGRAMS.map((item) => guaYun(item).yun)
    expect(new Set(yuns).size).toBe(8)
    expect(yuns).not.toContain(5)
    for (const yun of [1, 2, 3, 4, 6, 7, 8, 9]) {
      expect(yuns.filter((item) => item === yun)).toHaveLength(8)
    }
  })

  it('元运年表与刊本逐字一致，且总周期 180 年', () => {
    expect(YUN_CYCLE_YEARS).toBe(180)
    expect(yunSpans(1864).map((span) => [span.yun, span.startYear, span.endYear])).toEqual([
      [1, 1864, 1881],
      [2, 1882, 1905],
      [3, 1906, 1929],
      [4, 1930, 1953],
      [6, 1954, 1974],
      [7, 1975, 1995],
      [8, 1996, 2016],
      [9, 2017, 2043],
    ])
    expect(yunOfYear(2026).yun).toBe(9)
    expect(yunOfYear(1996).yun).toBe(8)
    expect(yunOfYear(1954).yun).toBe(6)
  })

  it('抽爻换象：乾三爻变履为四九生成数（丁爻），节二爻变屯合十五（财爻）', () => {
    const qian = HEXAGRAMS[31]
    const third = changedHexagram(qian, 2)
    expect(third.name).toBe('履')
    expect(yaoRole(third).ding).toBe(true)
    expect(yaoRole(third).kinds).toContain('生成数')
    const jie = HEXAGRAMS.find((item) => item.name === '节') as (typeof HEXAGRAMS)[number]
    const second = changedHexagram(jie, 1)
    expect(second.name).toBe('屯')
    expect(yaoRole(second).kinds).toContain('合十五')
  })

  it('丁爻判定使用河图生成数', () => {
    const fu = HEXAGRAMS[0]
    const first = changedHexagram(fu, 0)
    const role = yaoRole(first)
    const upper = first.upper.guaShu
    const lower = first.lower.guaShu
    expect(role.ding).toBe(
      [[1, 6], [2, 7], [3, 8], [4, 9]].some(
        ([a, b]) => (a === upper && b === lower) || (a === lower && b === upper)
      )
    )
  })
})
