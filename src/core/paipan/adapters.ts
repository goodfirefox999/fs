/**
 * 四个排盘引擎 → 统一 `PaipanSchoolResult`。
 *
 * 每个 adapter 只做三件事：把事实翻成 `subRules`、按该派口径给 `tendency`、
 * 把「数据不足」与「需要人工复核」显式标出来。**不做跨派合并**。
 */

import type {
  AnnualInfo,
  BaZhaiResult,
  PatternCode,
  XuanKongChart,
  YinMatchResult,
} from '../types'
import type { Tendency } from '../zeri/types'
import { palaceLabel } from '../engines/feixing'
import { paipanSourceOf } from './sources'
import type { PaipanSchoolResult, PaipanSubRule } from './types'
import { PAIPAN_SCHOOL_LABELS } from './types'

/** 星名只用于显示，不参与判定。 */
const STAR_NAMES: Record<number, string> = {
  1: '一白',
  2: '二黑',
  3: '三碧',
  4: '四绿',
  5: '五黄',
  6: '六白',
  7: '七赤',
  8: '八白',
  9: '九紫',
}

export function starName(star: number): string {
  return STAR_NAMES[star] ?? `${star}`
}

/**
 * 八宅：命卦与宅卦是否同组。
 *
 * 倾向口径来自该派「同组为顺」的主张，不是历法事实，已在出处里声明。
 * 多成员分属东西四宅时不给单一倾向，标 neutral 并写明矛盾。
 */
export function adaptBaZhai(result: BaZhaiResult): PaipanSchoolResult {
  const source = paipanSourceOf('BA_ZHAI')
  const subRules: PaipanSubRule[] = result.members.map((member) => ({
    ruleId: `BZ_MING_GUA_${member.relation}`,
    name: `${member.relation}：命卦与宅卦`,
    verdict: member.matchLabel,
    reasons: [
      `命卦 ${member.mingGua.name}（${member.mingGua.groupLabel}）`,
      `宅卦 ${result.house.name}（${result.house.groupLabel}）`,
    ],
    source,
    needsHumanReview: false,
  }))

  const total = result.members.length
  const matched = result.members.filter((member) => member.match === 'MATCH').length
  const tendency: Tendency =
    total === 0
      ? 'insufficient_data'
      : matched === total
        ? 'favorable'
        : matched === 0
          ? 'unfavorable'
          : 'neutral'

  const conflictFlags: string[] = []
  if (matched > 0 && matched < total) {
    conflictFlags.push(
      `成员分属东西四宅（${matched}/${total} 同组），同一宅难以同时满足全部命卦`,
    )
  }

  const status = total === 0 ? 'PARTIAL' : 'FULL'
  return {
    school: 'BA_ZHAI',
    schoolLabel: PAIPAN_SCHOOL_LABELS.BA_ZHAI,
    status,
    tendency,
    subRules,
    conflictFlags,
    needsHumanReview: false,
    partialReason: total === 0 ? '未填任何成员的出生日期与性别，命卦未生成' : undefined,
    extras: {
      houseGua: result.house.gua,
      houseGroup: result.house.group,
      matchedMembers: matched,
      totalMembers: total,
    },
  }
}

const PATTERN_TENDENCY: Record<PatternCode, Tendency> = {
  WANG_SHAN_WANG_XIANG: 'favorable',
  SHUANG_XING_DAO_XIANG: 'favorable',
  SHUANG_XING_DAO_SHAN: 'neutral',
  SHANG_SHAN_XIA_SHUI: 'unfavorable',
  NORMAL: 'neutral',
}

/** 玄空飞星：元运山向格局。格局判词属该派主张，`warnings` 非空时要求人工复核。 */
export function adaptXuanKong(chart: XuanKongChart): PaipanSchoolResult {
  const source = paipanSourceOf('XUAN_KONG')
  const subRules: PaipanSubRule[] = [
    {
      ruleId: 'XK_PERIOD',
      name: '元运',
      verdict: `${chart.period} 运`,
      reasons: [`坐山 ${chart.sitting.shan} ${chart.sitting.deg}°，向首 ${chart.facing.shan}`],
      source,
      needsHumanReview: false,
    },
    {
      ruleId: 'XK_PATTERN',
      name: '山向格局',
      verdict: chart.patternLabel,
      reasons: chart.patternTraditional ? [chart.patternTraditional] : [],
      source,
      needsHumanReview: true,
    },
    {
      ruleId: 'XK_JIAN_XIANG',
      name: '兼向与替卦',
      verdict: chart.isJianXiang ? (chart.tiGuaUsed ? '兼向·已用替卦' : '兼向·同宫同阴阳不替') : '正针不兼',
      reasons: [`兼向类型 ${chart.jianKind}`],
      source,
      needsHumanReview: chart.isJianXiang,
    },
  ]

  for (const [index, warning] of chart.warnings.entries()) {
    subRules.push({
      ruleId: `XK_WARNING_${index + 1}`,
      name: '需人工复核',
      verdict: warning,
      reasons: [],
      source,
      needsHumanReview: true,
    })
  }

  return {
    school: 'XUAN_KONG',
    schoolLabel: PAIPAN_SCHOOL_LABELS.XUAN_KONG,
    status: 'FULL',
    tendency: PATTERN_TENDENCY[chart.pattern] ?? 'neutral',
    subRules,
    conflictFlags: [],
    needsHumanReview: chart.warnings.length > 0 || chart.isJianXiang,
    extras: {
      period: chart.period,
      pattern: chart.pattern,
      isJianXiang: chart.isJianXiang,
      tiGuaUsed: chart.tiGuaUsed,
    },
  }
}

/**
 * 流年紫白：只出事实（年星入中、太岁、岁破、三煞方位），**不判吉凶**。
 *
 * 这一派在本产品里是参考层：它回答「今年星怎么排」，不回答「能不能用」。
 * 五黄落宫单列为一条提示，因为它是通书里最常被引用的年家方位，但仍不给倾向。
 */
export function adaptFeiXing(info: AnnualInfo): PaipanSchoolResult {
  const source = paipanSourceOf('FEI_XING')
  const subRules: PaipanSubRule[] = [
    {
      ruleId: 'FX_CENTER',
      name: '年星入中',
      verdict: `${starName(info.centerStar)}入中`,
      reasons: [`${info.year} 年（${info.yearGanZhi}）`],
      source,
      needsHumanReview: false,
    },
    {
      ruleId: 'FX_TAISUI',
      name: '太岁方位',
      verdict: info.taiSui,
      reasons: [],
      source,
      needsHumanReview: false,
    },
    {
      ruleId: 'FX_SUIPO',
      name: '岁破方位',
      verdict: info.suiPo,
      reasons: [],
      source,
      needsHumanReview: false,
    },
    {
      ruleId: 'FX_SANSHA',
      name: '三煞方位',
      verdict: `${info.sanShaDirection}（${info.sanShaMountains.join('、')}）`,
      reasons: [],
      source,
      needsHumanReview: false,
    },
  ]

  const wuHuangPalaces = Object.entries(info.chart.byPalace)
    .filter(([, star]) => star === 5)
    .map(([palace]) => palaceLabel(Number(palace) as 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9))
  if (wuHuangPalaces.length) {
    subRules.push({
      ruleId: 'FX_WU_HUANG',
      name: '五黄落宫',
      verdict: wuHuangPalaces.join('、'),
      reasons: ['五黄为年家常用方位，此处只列方位，不作吉凶判定'],
      source,
      needsHumanReview: false,
    })
  }

  return {
    school: 'FEI_XING',
    schoolLabel: PAIPAN_SCHOOL_LABELS.FEI_XING,
    status: 'FULL',
    // 参考层：不因星数给出倾向
    tendency: 'neutral',
    subRules,
    conflictFlags: [],
    needsHumanReview: false,
    extras: {
      centerStar: info.centerStar,
      yearGanZhi: info.yearGanZhi,
    },
  }
}

const VERDICT_TENDENCY: Record<string, Tendency> = {
  SUITABLE: 'favorable',
  ADJUST: 'neutral',
  AVOID: 'unfavorable',
  UNKNOWN: 'insufficient_data',
}

const VERDICT_LABELS: Record<string, string> = {
  SUITABLE: '相合',
  ADJUST: '可调',
  AVOID: '相冲克',
  UNKNOWN: '数据不足',
}

/** 仙命：亡命纳音与坐山、分金的生克。多亡命判定不一致时列冲突，不取平均。 */
export function adaptXianMing(result: YinMatchResult): PaipanSchoolResult {
  const source = paipanSourceOf('XIAN_MING')
  const subRules: PaipanSubRule[] = result.deceased.map((item) => ({
    ruleId: `XM_${item.label}`,
    name: `${item.label}：仙命与山向分金`,
    verdict: item.summary,
    reasons: [
      `仙命 ${item.ganZhi}（${item.nayin}·${item.element}）`,
      `坐山五行 ${item.mountElement}`,
      `分金 ${result.fenJin.slot.ganZhi}（${result.fenJin.slot.nayin}·${result.fenJin.slot.element}）`,
      ...item.tabooHits.map((hit) => `${hit.name}：${hit.detail}`),
    ],
    source,
    needsHumanReview: item.tabooHits.length > 0,
  }))

  if (result.fenJin.isJianXiang) {
    subRules.push({
      ruleId: 'XM_FEN_JIN_JIAN',
      name: '分金兼向',
      verdict: result.fenJin.warning ?? '兼向',
      reasons: [],
      source,
      needsHumanReview: true,
    })
  }

  const verdicts = new Set(result.deceased.map((item) => item.verdict))
  const conflictFlags: string[] = []
  if (verdicts.size > 1) {
    conflictFlags.push(
      `多位亡命判定不一致（${Array.from(verdicts)
        .map((verdict) => VERDICT_LABELS[verdict] ?? verdict)
        .join('、')}），不取平均，需分别取舍`,
    )
  }

  return {
    school: 'XIAN_MING',
    schoolLabel: PAIPAN_SCHOOL_LABELS.XIAN_MING,
    status: result.deceased.length === 0 ? 'PARTIAL' : 'FULL',
    tendency: VERDICT_TENDENCY[result.verdict] ?? 'insufficient_data',
    subRules,
    conflictFlags,
    needsHumanReview: result.deceased.some((item) => item.tabooHits.length > 0),
    partialReason: result.deceased.length === 0 ? '未填任何仙命的出生日期' : undefined,
    extras: {
      verdict: result.verdict,
      suggestedSlots: result.suggestedSlots.length,
    },
  }
}
