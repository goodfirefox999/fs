/**
 * 排盘报告：把四个引擎各跑一次，翻译成统一形状后并列返回。
 *
 * **始终返回四张卡片**，缺数据的标 `PARTIAL` 并写 `partialReason`——
 * 少一张卡片会让用户以为「这一派没意见」，而事实是「这一派没数据」。
 */

import type { BirthInfo, YinData } from '../types'
import { resolveFenJin } from '../constants/fenjin120'
import { analyzeBaZhai } from '../engines/bazhai'
import { annualInfo } from '../engines/feixing'
import { analyzeYinMatch } from '../engines/xianming'
import { buildXuanKong, periodFromYear, type WuHuangPolicy } from '../engines/xuankong'
import { adaptBaZhai, adaptFeiXing, adaptXianMing, adaptXuanKong } from './adapters'
import type { PaipanReport, PaipanSchoolResult } from './types'

export interface PaipanInput {
  mountShan: string
  sittingDeg: number
  /** 用事年份，决定元运与年星 */
  year: number
  members?: Array<{ relation: string; birth: BirthInfo }>
  deceased?: Array<{ label: string; birth: BirthInfo }>
  wuHuangPolicy?: WuHuangPolicy
}

/**
 * 仙命判定只需要亡命与分金，不读地形。
 * 这里构造的 `terrain` 只为满足 `YinData` 形状，不参与任何判定；
 * 峦头数据由阴宅模块单独采集，不得用这里的占位值当结论。
 */
function yinDataOf(input: PaipanInput): YinData {
  return {
    monumentType: 'SINGLE',
    deceased: input.deceased ?? [],
    descendants: [],
    terrain: { backSupport: 'FLAT', frontView: 'OPEN', leftRight: 'BALANCED' },
  }
}

export function buildPaipanReport(input: PaipanInput): PaipanReport {
  const schools: PaipanSchoolResult[] = [
    adaptBaZhai(analyzeBaZhai(input.members ?? [], input.mountShan)),
    adaptXuanKong(
      buildXuanKong({
        period: periodFromYear(input.year),
        sittingDeg: input.sittingDeg,
        wuHuangPolicy: input.wuHuangPolicy,
      }),
    ),
    adaptFeiXing(annualInfo(input.year)),
    adaptXianMing(
      analyzeYinMatch(yinDataOf(input), input.mountShan, resolveFenJin(input.sittingDeg)),
    ),
  ]

  const dataGaps = schools
    .filter((school) => school.partialReason)
    .map((school) => `${school.schoolLabel}：${school.partialReason}`)

  return {
    schools,
    dataGaps,
    notes: [
      '四派回答的不是同一个问题：八宅问命宅配合、玄空问元运山向、紫白只出流年方位、仙命问亡命与分金。',
      '本页并列展示各派原始倾向，不做跨派合并，也不给统一吉凶结论。',
      '所有条目均为传统规则整理，需实地勘测与专业复核；不替代结构安全、消防与规划判断。',
    ],
    needsHumanReview: schools.some((school) => school.needsHumanReview),
  }
}
