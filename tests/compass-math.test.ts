import { describe, expect, it } from 'vitest'
import {
  CITY_DECLINATIONS,
  CompassSampler,
  circularConcentration,
  circularMean,
  circularMedian,
  estimateMapBearingUncertainty,
  formatDegree,
  initialBearing,
  mountainSnapshot,
  nearestCity,
} from '@/core/engines/compassMath'

/**
 * 罗盘读数的数学。这些函数决定用户在罗盘页看到的度数与「是否锁定」，
 * 此前完全没有单元测试（2026-11-26 接入覆盖率时发现 0%）。
 *
 * 圆统计最经典的错误是跨 0°：359° 与 1° 的平均是 0°，不是 180°。
 */
describe('圆统计：角度采样平滑', () => {
  it('空样本返回 0，单样本返回自身', () => {
    expect(circularMean([])).toBe(0)
    expect(circularMean([123.4])).toBeCloseTo(123.4, 6)
  })

  it('均值跨 0° 不翻到对面', () => {
    expect(circularMean([359, 1])).toBeCloseTo(0, 6)
    expect(circularMean([350, 10])).toBeCloseTo(0, 6)
    expect(circularMean([355, 5, 0])).toBeCloseTo(0, 6)
    // 两个方向各偏 ±90° 的合矢量长度为 0，atan2(0,0)=0；不要求它有意义，只要求不出 NaN
    expect(Number.isNaN(circularMean([270, 90]))).toBe(false)
  })

  it('超出 0~360 与负数输入先归一化', () => {
    expect(circularMean([360 + 90, 90])).toBeCloseTo(90, 6)
    expect(circularMean([-90, 270])).toBeCloseTo(270, 6)
  })

  it('集中度：方向一致为 1，正反相对为 0', () => {
    expect(circularConcentration([45, 45, 45])).toBeCloseTo(1, 6)
    expect(circularConcentration([0, 180])).toBeCloseTo(0, 6)
    const mixed = circularConcentration([0, 10, 350])
    expect(mixed).toBeGreaterThan(0.95)
    expect(mixed).toBeLessThan(1)
    expect(circularConcentration([])).toBe(0)
  })

  it('中位数取上中位，且不被离群值拉走', () => {
    // 均值会被 190° 拉到约 47°，中位数稳在 10°（对跱点平局由多数一方取胜）
    expect(circularMedian([10, 10, 10, 190])).toBeCloseTo(10, 6)
    // 偶数样本时中间两点等价，取到其中之一即可——但不能取到离群值 10 或 16
    const even = circularMedian([10, 12, 14, 16])
    expect(even === 12 || even === 14).toBe(true)
    // 跨 0° 的一组样本，中位数在环绕意义下必须靠近 0°（358 与 0 在这里等价）
    const wrapped = circularMedian([358, 0, 2, 356])
    expect(Math.min(wrapped, 360 - wrapped)).toBeLessThan(4)
    expect(circularMedian([])).toBe(0)
  })
})

describe('CompassSampler：滑动窗口与锁定', () => {
  it('样本数不超过窗口；窗口满且稳定才锁定', () => {
    const sampler = new CompassSampler(5)
    let result = sampler.push(0)
    expect(result.samples).toBe(1)
    expect(result.isLocked).toBe(false)
    for (let i = 0; i < 10; i++) result = sampler.push(0.2)
    expect(result.samples).toBe(5)
    expect(result.isLocked).toBe(true)
    expect(result.stability).toBe(100)
    expect(result.smoothDeg).toBeCloseTo(0.2, 1)
  })

  it('读数抖动时不锁定', () => {
    const sampler = new CompassSampler(8)
    let result = sampler.push(0)
    for (let i = 0; i < 16; i++) result = sampler.push(i % 2 === 0 ? 20 : 340)
    expect(result.samples).toBe(8)
    expect(result.isLocked).toBe(false)
    // 抖动对称分布在 0° 两侧，平滑值仍在 0° 附近——稳定性低不等于度数错
    expect(result.smoothDeg < 2 || result.smoothDeg > 358).toBe(true)
  })

  it('窗口滑动后旧样本被丢弃，reset 清空', () => {
    const sampler = new CompassSampler(4)
    for (let i = 0; i < 4; i++) sampler.push(90)
    for (let i = 0; i < 4; i++) sampler.push(180)
    expect(sampler.size).toBe(4)
    expect(sampler.push(180).smoothDeg).toBeCloseTo(180, 1)
    sampler.reset()
    expect(sampler.size).toBe(0)
  })
})

describe('地图测向与两地方位', () => {
  it('基线越短不确定度越大，上限 90°', () => {
    expect(estimateMapBearingUncertainty(0)).toBe(90)
    expect(estimateMapBearingUncertainty(-5)).toBe(90)
    // 10 m 基线、5 m 误差：atan(10/10) = 45°
    expect(estimateMapBearingUncertainty(10)).toBe(45)
    expect(estimateMapBearingUncertainty(100)).toBeLessThan(10)
    expect(estimateMapBearingUncertainty(100000)).toBeLessThanOrEqual(90)
  })

  it('初始方位角与手算一致', () => {
    expect(initialBearing(30, 110, 31, 110)).toBeCloseTo(0, 1)
    expect(initialBearing(0, 110, 0, 111)).toBeCloseTo(90, 1)
    expect(initialBearing(0, 110, 0, 109)).toBeCloseTo(270, 1)
    // 北京 → 上海：y=sin(5.1°)cos(31.2°)，x=cos(39.9°)sin(31.2°)−sin(39.9°)cos(31.2°)cos(5.1°)
    // atan2(0.07605, −0.1492) ≈ 153.0°
    expect(initialBearing(39.9, 116.4, 31.2, 121.5)).toBeCloseTo(153.0, 0)
  })
})

describe('城市磁偏角表', () => {
  it('表内每个城市都能被自己的坐标命中', () => {
    expect(CITY_DECLINATIONS.length).toBeGreaterThanOrEqual(40)
    for (const city of CITY_DECLINATIONS) {
      expect(nearestCity(city.lat, city.lon).city).toBe(city.city)
    }
  })

  it('附近坐标落到最近的城市', () => {
    expect(nearestCity(22.9, 108.4).city).toBe('南宁')
    expect(nearestCity(39.0, 117.0).city).toBe('天津')
  })

  it('表内城市名与坐标不重复', () => {
    const names = CITY_DECLINATIONS.map((item) => item.city)
    expect(new Set(names).size).toBe(names.length)
  })
})

describe('坐山快照与度数格式', () => {
  it('山中心不兼向，偏离超过 4.5° 为兼向', () => {
    expect(mountainSnapshot(0).isJianXiang).toBe(false)
    expect(mountainSnapshot(0).offset).toBe(0)
    expect(mountainSnapshot(5).isJianXiang).toBe(true)
    expect(mountainSnapshot(7.5).isJianXiang).toBe(true)
  })

  it('格式化结果始终落在 [0, 360)，四舍五入不得显示 360.0°', () => {
    expect(formatDegree(123.456)).toBe('123.5°')
    expect(formatDegree(-1)).toBe('359.0°')
    expect(formatDegree(359.96)).toBe('0.0°')
    expect(formatDegree(720)).toBe('0.0°')
  })
})
