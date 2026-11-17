import type { SchoolId } from './types'
import type { ZeRiCategory } from '../types'
import { SCHOOL_IDS } from './types'
import { evaluateZhengWuXing } from './packs/zhengwuxing'
import { evaluateSanHe } from './packs/sanhe'
import { evaluateDongGong } from './packs/donggong'
import { evaluateXuanKongDaGua } from './packs/xuankongDagua'
import { evaluateTianXing } from './packs/tianxing'
import type { DayFacts, ZeriContext } from './facts'
import type { SchoolResult } from './types'

export type SchoolEvaluator = (facts: DayFacts, ctx: ZeriContext) => SchoolResult

export const SCHOOL_EVALUATORS: Record<SchoolId, SchoolEvaluator> = {
  ZHENG_WU_XING: evaluateZhengWuXing,
  SAN_HE: evaluateSanHe,
  DONG_GONG: evaluateDongGong,
  XUAN_KONG_DA_GUA: evaluateXuanKongDaGua,
  TIAN_XING: evaluateTianXing,
}

/** 事件类型权重（规格第 4 节表）；名次 1–5 直接映射为权重 5–1，公开可查。 */
const RANKS: Record<ZeRiCategory, SchoolId[]> = {
  YIN_ANZANG: ['ZHENG_WU_XING', 'SAN_HE', 'TIAN_XING', 'DONG_GONG', 'XUAN_KONG_DA_GUA'],
  // 修坟立碑规格未列表，沿用安葬权重并标注为产品端扩展
  YIN_XIUFEN: ['ZHENG_WU_XING', 'SAN_HE', 'TIAN_XING', 'DONG_GONG', 'XUAN_KONG_DA_GUA'],
  YANG_RUZHAI: ['XUAN_KONG_DA_GUA', 'ZHENG_WU_XING', 'SAN_HE', 'DONG_GONG', 'TIAN_XING'],
  YANG_DONGTU: ['ZHENG_WU_XING', 'SAN_HE', 'DONG_GONG', 'XUAN_KONG_DA_GUA', 'TIAN_XING'],
  // 嫁娶、开市为产品端补充事项，规格未单列权重；沿用「正五行为底、多派复核」的总纲顺序。
  YANG_JIAQU: ['ZHENG_WU_XING', 'SAN_HE', 'DONG_GONG', 'XUAN_KONG_DA_GUA', 'TIAN_XING'],
  YANG_KAISHI: ['ZHENG_WU_XING', 'SAN_HE', 'DONG_GONG', 'XUAN_KONG_DA_GUA', 'TIAN_XING'],
}

export const RANK_NOTE: Record<ZeRiCategory, string> = {
  YIN_ANZANG: '阴宅安葬以补龙为主：正五行 > 三合 > 天星 > 董公 > 玄空大卦',
  YIN_XIUFEN: '修坟立碑沿用安葬权重（规格未单列，属产品端扩展，需人工复核）',
  YANG_RUZHAI: '阳宅入宅重元运内局：玄空大卦 > 正五行 > 三合 > 董公 > 天星',
  YANG_DONGTU: '动土修造以扶山为重：正五行 > 三合 > 董公 > 玄空大卦 > 天星',
  YANG_JIAQU: '嫁娶订盟为产品端扩展：正五行 > 三合 > 董公 > 玄空大卦 > 天星，权重需人工复核',
  YANG_KAISHI: '开市交易为产品端扩展：正五行 > 三合 > 董公 > 玄空大卦 > 天星，权重需人工复核',
}

export function weightsFor(category: ZeRiCategory): Array<{ school: SchoolId; weight: number }> {
  const ranks = RANKS[category] ?? SCHOOL_IDS
  return ranks.map((school, index) => ({ school, weight: ranks.length - index }))
}
