import type {
  AuspiciousPositions,
  ZeRiCategory,
  ZeRiItem,
  ZeRiQuery,
  ZeRiRejection,
  ZeRiResult,
} from '../types'
import { branchOfMountain, getMountain } from '../constants/shan24'
import { addDays, solarOf, weekdayLabel } from '../utils/date'
import { evaluateDay } from '../zeri/evaluate'
import { SCHOOL_LABELS } from '../zeri/types'
import { guidanceFor } from '../zeri/dasha'
import { THREE_LUCKY_STARS, dongGongStarOf } from '../zeri/tables/donggong'
import { ZERI_CATEGORY_LABELS } from '../constants/xieji'

const CATEGORY_TERMS: Record<ZeRiCategory, string[]> = {
  YANG_RUZHAI: ['入宅', '移徙', '安床'],
  YANG_DONGTU: ['动土', '修造', '起基', '拆卸'],
  YANG_JIAQU: ['嫁娶', '结婚姻', '纳采', '订盟'],
  YANG_KAISHI: ['开市', '交易', '立券', '纳财'],
  YIN_ANZANG: ['安葬', '启钻', '破土'],
  YIN_XIUFEN: ['修坟', '立碑', '谢土'],
}

// 五派只给「本派规则倾向」，不输出单一吉凶结论；
// 文案避免把倾向读成事实断言或单一裁决。
const TENDENCY_LABELS: Record<string, string> = {
  favorable: '偏扶',
  neutral: '平',
  unfavorable: '偏慎',
  insufficient_data: '据不足',
}

export function buildZeRi(query: ZeRiQuery): ZeRiResult {
  const terms = CATEGORY_TERMS[query.category]
  if (!terms) throw new Error(`未知择日类别: ${query.category}`)
  const daysCount = Math.max(1, Math.min(180, Math.round(query.daysCount)))
  const maxResults = Math.max(1, Math.min(60, query.maxResults ?? 12))
  const startSolar = solarOf(query.startDate)
  const mountMeta = getMountain(query.mountShan)
  const mountBranch = branchOfMountain(query.mountShan)
  const eventYear = query.eventYear ?? Number(query.startDate.slice(0, 4))

  const rejectionMap = new Map<string, ZeRiRejection>()
  const rejectionDays = new Map<string, Set<string>>()
  const candidates: ZeRiItem[] = []
  let scanned = 0
  let rejected = 0
  let unmatched = 0
  let excludedByAlmanac = 0
  let excludedByHuangDao = 0
  let excludedByXiu = 0

  // 完整扫描时间窗，不用展示条数提前截断扫描：
  // 否则「扫描 90 天、排除 30 天」会变成只扫描前 12 天的假统计。
  for (let offset = 0; offset < daysCount; offset++) {
    const date = startSolar.next(offset).toYmd()
    scanned++

    const evaluation = evaluateDay({
      date,
      category: query.category,
      mountShan: query.mountShan,
      sittingDeg: query.sittingDeg ?? mountMeta.centerDeg,
      eventYear,
      incomingDragon: query.incomingDragon ?? null,
      subjects: query.familyBirths,
      deceased: query.deceasedBirths ?? [],
      hourBranch: query.hourBranch ?? null,
      sanShaPolicy: query.sanShaMode ?? 'year_month',
      chongSangPolicy: query.chongSangMode ?? 'reject',
      jinShenPolicy: query.jinShenMode ?? 'reject',
      folkPolicy: query.folkMode ?? 'reject',
      includesConstruction: query.includesConstruction ?? false,
      yaoOrder: query.yaoOrder ?? 'ASC',
      longitudeDeg: query.longitudeDeg ?? null,
    })

    if (evaluation.dasha.rejected) {
      rejected++
      const star = dongGongStarOf(evaluation.facts.monthBranch, evaluation.facts.pillars.day.ganZhi)
      const lucky = THREE_LUCKY_STARS.includes(star)
      for (const hit of evaluation.dasha.hits) {
        let days = rejectionDays.get(hit.ruleId)
        if (!days) {
          days = new Set<string>()
          rejectionDays.set(hit.ruleId, days)
        }
        const firstHitToday = !days.has(date)
        days.add(date)
        let found = rejectionMap.get(hit.ruleId)
        if (!found) {
          found = {
            name: hit.name,
            count: 0,
            // 以规则自身声明的「是否允许降级」为准。此前用不可放宽清单反推，
            // 会把纯入宅本不适用的三煞占山误标成「可复核后放宽」。
            review: hit.negotiable,
            source: hit.source.title,
            luckyStarDays: 0,
            luckyStarSamples: [],
            guidance: guidanceFor(hit.ruleId, evaluation.context),
          }
          rejectionMap.set(hit.ruleId, found)
        }
        if (firstHitToday) {
          found.count += 1
          if (lucky) {
            found.luckyStarDays += 1
            if (found.luckyStarSamples.length < 3) found.luckyStarSamples.push(`${date} 值${star}`)
          }
        }
      }
      continue
    }

    const facts = evaluation.facts
    const dayYi = facts.almanacYi
    const dayJi = facts.almanacJi
    const { matchedYi, termInJi } = evaluateCategoryTerms(query.category, dayYi, dayJi)
    if (!matchedYi.length || termInJi.length) {
      unmatched++
      excludedByAlmanac++
      continue
    }
    if (query.onlyHuangDao && facts.tianShenLuck !== '吉') {
      unmatched++
      excludedByHuangDao++
      continue
    }
    if (query.avoidXiuXiong && facts.xiuLuck !== '吉') {
      unmatched++
      excludedByXiu++
      continue
    }

    const shensha = facts.shensha
    const huangDao = facts.tianShenLuck === '吉'
    const applyYi = shensha.behavior !== 'FROM_JI'
    const applyJi = shensha.behavior !== 'FROM_YI'
    const yiMatched = applyYi && shensha.yiCategories.includes(query.category)
    const jiMatched = applyJi && shensha.jiCategories.includes(query.category)

    const warnings: string[] = []
    const reasons: string[] = [`宜项含${matchedYi.join('、')}`]
    if (huangDao) reasons.push(`黄道日（${facts.tianShen}）`)
    if (mountBranch) reasons.push(`不冲坐山${mountMeta.name}`)
    if (yiMatched) {
      reasons.push(`协纪吉神并见：${shensha.yiGods.map((god) => god.name).join('、')}`)
    }
    if (jiMatched) {
      warnings.push(
        `《协纪辨方书》起例中${shensha.jiGods.map((god) => god.name).join('、')}忌本类用事，建议避开或请专业人士复核。`
      )
    }
    if (shensha.level >= 0) {
      reasons.push(`宜忌等第${shensha.levelName}（${shensha.behaviorLabel}）`)
    }
    for (const warn of evaluation.dasha.warned) {
      warnings.push(`按当前设置降级为提示：${warn.name}（${warn.reason}）`)
    }
    const tianxing = evaluation.schools.find((school) => school.school === 'TIAN_XING')
    if (tianxing?.partialReason) {
      warnings.push(`天星流派为部分计算：${tianxing.partialReason}`)
    }
    if (evaluation.arbitration.conflicts.length) {
      warnings.push(
        `流派之间存在分歧：${evaluation.arbitration.conflicts
          .map((conflict) => conflict.schools.map((id) => SCHOOL_LABELS[id]).join(' 与 '))
          .join('；')}，本工具不裁决孰是孰非。`
      )
    }
    const reviewCount = evaluation.schools
      .flatMap((school) => school.subRules)
      .filter((rule) => rule.needsHumanReview).length
    if (reviewCount) {
      reasons.push(`${reviewCount} 条规则标注为待人工复核`)
    }

    const positions: AuspiciousPositions = {
      xi: facts.positions.xi,
      cai: facts.positions.cai,
      fu: facts.positions.fu,
      yangGui: facts.positions.yangGui,
      yinGui: facts.positions.yinGui,
    }

    let score = 0
    if (yiMatched) score += 2
    if (jiMatched) score -= 2
    if (shensha.behavior === 'FROM_YI') score += 1
    if (shensha.behavior === 'FROM_JI') score -= 1
    if (huangDao) score += 1
    if (facts.xiuLuck === '吉') score += 1
    if (matchedYi.length > 1) score += 1

    candidates.push({
      solarDate: date,
      weekDay: facts.weekDay,
      lunarDate: facts.lunarText,
      ganZhi: facts.pillars.day.ganZhi,
      zhiXing: facts.zhiXing,
      huangDao,
      dayYi,
      dayJi,
      chong: facts.chongDesc,
      chongShengXiao: facts.chongShengXiao,
      sha: facts.sha,
      matchedYi,
      warnings,
      reasons,
      jiShen: facts.jiShen,
      xiongSha: facts.xiongSha,
      xiejiYi: yiMatched ? shensha.yiGods.map((god) => god.name) : [],
      xiejiJi: jiMatched ? shensha.jiGods.map((god) => god.name) : [],
      level: shensha.level,
      levelName: shensha.levelName,
      behavior: shensha.behavior,
      xiu: facts.xiu,
      xiuLuck: facts.xiuLuck,
      tianShen: facts.tianShen,
      pengZu: facts.pengZu,
      positions,
      luckyHours: facts.luckyHours,
      score,
      schools: evaluation.schools,
      conflicts: evaluation.arbitration.conflicts,
      consensus: evaluation.arbitration.consensus,
      consensusFavorable: evaluation.arbitration.consensusFavorable,
      dashaWarnings: evaluation.dasha.warned.map((hit) => hit.name),
    })
  }

  const items = candidates.slice(0, maxResults)
  const eligible = candidates.length
  const truncated = eligible > items.length
  const rejections = Array.from(rejectionMap.values()).sort((a, b) => b.count - a.count)
  const notes = [
    `筛选范围：${query.startDate} 起 ${daysCount} 天，用途为${categoryLabel(query.category)}。`,
    '前置层规则：不可放宽项只收历法事实与官书明文——岁破、月破、日破、时破、冲坐山、冲主命与仙命、四离四绝、协纪等第「诸事皆忌」，加上兴工口径下的年家三煞占山；' +
      '三煞按「占山四条」（年/月/日/时，看坐山是否落煞方，煞方由该柱自身地支的三合局起）与「日课相犯两条」（日支犯年煞、时支犯日煞，看四柱自身，不构成对坐山的排除）分层，' +
      '默认在兴工与阴宅用事中硬排年家、月家占山，日家、时家与相犯两条列为提示；' +
      '金神七煞限修造与入宅；受死按《协纪辨方书》卷六「龙虎、罪至、受死三辰并仍旧历从删」恒列为提示，不随开关升级为排除。' +
      '四废、往亡、十恶大败、大败、杨公忌按「民俗神煞」开关处理（杨公忌官书未列明文，默认按通书排除属显式声明的偏离），重丧另有开关，降级后仍原样列出。',
    '月支与太岁按交节当日、立春当日切换；玄空大卦元运按用事年份的立春归属。',
    query.category === 'YANG_RUZHAI'
      ? (query.includesConstruction
          ? '本次入宅勾选了「伴随动土、修造或安门」，已按兴工类恢复年家与月家三煞占山硬排除。'
          : '本次按纯入宅（不兴工）计算，年家与月家三煞占山不适用；若实际包含动土、修造或安门，请改用「动土修造」或勾选伴随修造，勿以本结果用于兴工。')
      : '',
    `本次完整扫描 ${scanned} 天：前置层排除 ${rejected} 天，附加条件跳过 ${unmatched} 天` +
      `（通书宜忌 ${excludedByAlmanac}、黄道 ${excludedByHuangDao}、宿吉 ${excludedByXiu}），` +
      `符合全部条件 ${eligible} 天，当前按日期升序展示 ${items.length} 天。`,
    '正五行、三合、董公、玄空大卦、天星五派并列输出，仲裁层只做透明加权与冲突标记，不合并任何一派的原始结论。',
    '天星派仅计算太阳（误差界已标注），太阴与五星四余未计算；玄空大卦的日课配卦映射存在流派分歧，均标注待人工复核。',
    '规则出处全部标注 verification_status=unverified，需人工核对后方可视为确认。',
    '择日结果为民俗日程参考，不替代施工、气象、地质、消防与安全评估。',
  ]
  if (!mountBranch && query.mountShan) {
    notes.push(`${query.mountShan}山不属于十二地支山，日支冲山规则未直接套用，建议用实体罗盘复核兼向。`)
  }
  if (query.incomingDragon) {
    notes.push(`入首龙按${query.incomingDragon}山参与补龙判定；未采集时补龙规则显式标记数据缺口。`)
  }
  if (!query.hourBranch) {
    notes.push('未指定日课时支，调候与日破、时破规则不参与判定。')
  }

  if (!items.length && rejections.length) {
    const top = [...rejections].sort((a, b) => b.count - a.count)[0]
    notes.unshift(`当前条件下无候选日：主因「${top.name}」排除 ${top.count}/${scanned} 天。${top.guidance}`)
  }

  return {
    items,
    scanned,
    rejected,
    unmatched,
    eligible,
    truncated,
    excludedByAlmanac,
    excludedByHuangDao,
    excludedByXiu,
    rejections,
    notes,
  }
}

/** 通书宜项与用事类别的匹配结果；桌面端日历复用，避免两处口径不同。 */
export function evaluateCategoryTerms(
  category: ZeRiCategory,
  dayYi: string[],
  dayJi: string[],
): { matchedYi: string[]; termInJi: string[] } {
  const terms = CATEGORY_TERMS[category] ?? []
  return {
    matchedYi: terms.filter((term) => dayYi.includes(term)),
    termInJi: terms.filter((term) => dayJi.includes(term)),
  }
}

export function schoolTendencyLabel(tendency: string): string {
  return TENDENCY_LABELS[tendency] ?? tendency
}

export function categoryLabel(category: ZeRiCategory): string {
  return ZERI_CATEGORY_LABELS[category] ?? category
}

export function defaultZeRiRange(today: string): { startDate: string; endDate: string } {
  return { startDate: today, endDate: addDays(today, 89) }
}
