/**
 * 排盘的出处登记表。
 *
 * 与择日侧 `core/zeri/sources.ts` 同一套纪律：每条都要写 `lineageNote`，
 * 说明该派主张与历法事实的边界、以及流派分歧在哪。
 *
 * **不写卷次**：八宅、玄空、紫白的通行本卷次划分本项目未逐条核对，
 * 宁可写「未逐条核对原书卷次」，也不编一个看起来精确的卷号。
 */

import type { SourceRef } from '../zeri/types'
import { createRegistry } from '../utils/registry'

const REGISTRY: Record<string, SourceRef> = {
  BA_ZHAI: {
    id: 'BA_ZHAI',
    title: '《八宅明镜》通行本（东西四宅、命卦九星）',
    locus: '明·箬冠道人撰；本项目未逐条核对原书卷次',
    modern: '命卦按 1901–2099 年逐年表计算，已与独立 MIT 实现逐宫比对',
    lineageNote:
      '东西四宅分组与「同组为顺」属该派主张，不是历法事实；本产品只把它作为八宅一派的倾向输出，不合并进统一吉凶。',
  },
  XUAN_KONG: {
    id: 'XUAN_KONG',
    title: '《沈氏玄空学》三元九运、山向飞星与替卦',
    locus: '清·沈竹礽，民国刊本；本项目未逐条核对原书卷次',
    modern: '九运 216 局（9 运 × 24 山）已与独立 MIT 实现逐宫比对',
    lineageNote:
      '旺山旺向、上山下水等格局判词属该派主张；五黄入中有「本山」与「寄坤」两说，本产品通过策略参数显式声明，不静默取一。',
  },
  FEI_XING: {
    id: 'FEI_XING',
    title: '流年紫白九星（年星入中、太岁岁破三煞方位）',
    locus: '通书通行算法；上元甲子起一白，年星逆布九宫',
    modern: '年星锚点、节气月切换、三煞方位已与通书口径对齐',
    lineageNote:
      '年星起法与换年口径耦合：本产品按立春换年，与通书一致；若按正月初一换年，交节前后的年星会差一位。',
  },
  XIAN_MING: {
    id: 'XIAN_MING',
    title: '仙命纳音与一百二十分金',
    locus: '六十甲子纳音为公版；一百二十分金每山五格，含空亡与旺相',
    modern: '纳音表与分金表为静态可审表，见 core/constants',
    lineageNote:
      '仙命与坐山/分金的关系有「纳音为主」与「正五行为主」两说；本产品分别输出 mountRelation 与 fenJinRelation，不合并为单一结论。',
  },
}

const REGISTRY_GUARD = createRegistry('排盘出处', REGISTRY)

export function paipanSourceOf(key: string): SourceRef {
  return REGISTRY_GUARD.require(key)
}
