import { describe, expect, it } from 'vitest'
import fixture from './fixtures/swisseph-solar-2026.json'
import { solarLongitude } from '@/core/astro/solar'

const rows = fixture.rows as Array<[string, number, number]>

describe('太阳视黄经与均时差精度闸门', () => {
  /**
   * 规格要求天星包达到 0.01°，Meeus 截断式实测最大误差 0.014°，未达闸门。
   * 因此本仓库不把天星包声明为 FULL：这里断言的是「已实测精度上界」，
   * 天星包据此输出 status=PARTIAL、publishedErrorDeg=0.02，并在临界 0.03° 内要求人工复核。
   */
  it('2026 全年逐日与 Swiss Ephemeris 比对：黄经误差 < 0.02°（未达 0.01° 闸门）', () => {
    expect(rows).toHaveLength(365)
    let maxError = 0
    let worst = ''
    for (const [date, reference] of rows) {
      const ours = solarLongitude(date, 4).apparentLongitude
      let diff = Math.abs(ours - reference)
      if (diff > 180) diff = 360 - diff
      if (diff > maxError) {
        maxError = diff
        worst = `${date} ours=${ours.toFixed(4)} swe=${reference.toFixed(4)}`
      }
    }
    expect(maxError).toBeGreaterThan(0.005)
    expect(maxError, `最大误差出现在 ${worst}`).toBeLessThan(0.02)
  })

  it('均时差误差 < 0.5 分钟', () => {
    let maxError = 0
    let worst = ''
    for (const [date, , reference] of rows) {
      const ours = solarLongitude(date, 4).equationOfTimeMinutes
      const diff = Math.abs(ours - reference)
      if (diff > maxError) {
        maxError = diff
        worst = `${date} ours=${ours.toFixed(3)} swe=${reference.toFixed(3)}`
      }
    }
    expect(maxError, `最大误差出现在 ${worst}`).toBeLessThan(0.5)
  })
})
