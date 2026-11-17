import { describe, expect, it } from 'vitest'
import oracle from './fixtures/xuankong-oracle.json'
import { buildXuanKong } from '@/core/engines/xuankong'
import type { PatternCode } from '@/core/types'

const PATTERN_MAP: Record<string, PatternCode> = {
  旺山旺向: 'WANG_SHAN_WANG_XIANG',
  上山下水: 'SHANG_SHAN_XIA_SHUI',
  双星到向: 'SHUANG_XING_DAO_XIANG',
  双星到坐: 'SHUANG_XING_DAO_SHAN',
  其他格局: 'NORMAL',
}

describe('玄空下卦与独立实现交叉校验', () => {
  it('9 运 × 24 山的运盘、山盘、向盘与格局一致', () => {
    expect(oracle.rows).toHaveLength(216)
    for (const row of oracle.rows) {
      const chart = buildXuanKong({ period: row.yun, sittingDeg: row.sitCenter })
      const oraclePattern = Object.keys(PATTERN_MAP).find((name) =>
        row.pattern.startsWith(name)
      )
      expect(oraclePattern, `无法识别格局 ${row.pattern}`).toBeTruthy()
      expect(chart.pattern, `${row.yun}运 ${row.sit}山格局`).toBe(
        PATTERN_MAP[oraclePattern as string]
      )
      for (const palace of chart.palaces) {
        const expected = row.grid[palace.trigram as keyof typeof row.grid]
        expect(expected, `${row.yun}运 ${row.sit}山 缺少${palace.trigram}宫`).toBeTruthy()
        expect(
          { yun: palace.yun, shan: palace.shan, xiang: palace.xiang },
          `${row.yun}运 ${row.sit}山 ${palace.trigram}宫`
        ).toEqual(expected)
      }
    }
  })
})
