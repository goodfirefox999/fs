import { describe, expect, it } from 'vitest'
import oracle from './fixtures/bazhai-oracle.json'
import { calcMingGua, palacesOfGua } from '@/core/engines/bazhai'
import { PALACES, PALACE_IDS } from '@/core/constants/luoshu'
import type { PalaceId } from '@/core/types'

const ID_OF_GUA = Object.fromEntries(
  PALACE_IDS.map((id) => [PALACES[id].trigram, id])
) as Record<string, PalaceId>

// 夹具使用单字方位（北/南/东/西），引擎使用「正北」等全称
const SHORT_DIRECTION: Record<string, string> = {
  正北: '北',
  正南: '南',
  正东: '东',
  正西: '西',
}

describe('八宅与独立实现交叉校验', () => {
  it('八宅游年八方九星一致', () => {
    for (const gua of Object.keys(oracle.houses)) {
      const id = ID_OF_GUA[gua]
      expect(id, `未知卦 ${gua}`).toBeTruthy()
      const expected = oracle.houses[gua as keyof typeof oracle.houses]
      for (const palace of palacesOfGua(id)) {
        const direction = SHORT_DIRECTION[palace.direction] ?? palace.direction
        const star = expected[direction as keyof typeof expected]
        expect(star, `${gua}宅 ${direction}`).toBeTruthy()
        expect(palace.star.name, `${gua}宅 ${direction}`).toBe(star)
      }
    }
  })

  it('1901–2099 年男女命卦一致', () => {
    for (const row of oracle.ming) {
      const result = calcMingGua({
        date: `${row.year}-06-01`,
        precision: 'YEAR',
        gender: row.gender === '男' ? 'M' : 'F',
      })
      expect(result, `${row.year} ${row.gender}`).not.toBeNull()
      expect(result?.gua, `${row.year} ${row.gender}`).toBe(row.luoshu)
      expect(result?.info.name, `${row.year} ${row.gender}`).toBe(row.gua)
    }
  })
})
