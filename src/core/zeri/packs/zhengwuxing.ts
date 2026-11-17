/**
 * 正五行规则包（补龙、扶山、相主、调候、通关）。
 * 与三合包的「补龙」各自独立输出，仲裁层不合并。
 */
import type { FiveElement } from '../../types'
import { ELEMENT_KE, ELEMENT_SHENG, GAN_ELEMENT, ZHI_CLASH } from '../../constants/nayin60'
import {
  MOUNTAIN_HONG_FAN_WU_XING,
  MOUNTAIN_ZHENG_WU_XING,
  changShengOf,
  LU_SHEN,
  WANG_PHASES,
} from '../tables/sanhe'
import {
  courseBranches,
  courseStems,
  sanHeFrames,
  type DayFacts,
  type ZeriContext,
} from '../facts'
import { branchOfMountain } from '../../constants/shan24'
import { packResult, subRule } from './common'
import type { SchoolResult } from '../types'

const HE_TIAN_GAN: Record<string, string> = {
  甲: '己', 己: '甲', 乙: '庚', 庚: '乙', 丙: '辛', 辛: '丙',
  丁: '壬', 壬: '丁', 戊: '癸', 癸: '戊',
}

/** 调候：月令所属 → 宜取之时支组。 */
const TIAO_HOU_TARGET: Record<string, string[]> = {
  亥: ['巳', '午', '未'], 子: ['巳', '午', '未'], 丑: ['巳', '午', '未'],
  巳: ['亥', '子', '丑'], 午: ['亥', '子', '丑'], 未: ['亥', '子', '丑'],
  申: ['寅', '卯', '辰'], 酉: ['寅', '卯', '辰'], 戌: ['寅', '卯', '辰'],
  寅: ['申', '酉', '戌'], 卯: ['申', '酉', '戌'], 辰: ['申', '酉', '戌'],
}

const WAR_PAIRS: Array<{ a: FiveElement; b: FiveElement; via: FiveElement }> = [
  { a: '金', b: '木', via: '水' },
  { a: '水', b: '火', via: '木' },
  { a: '木', b: '土', via: '火' },
  { a: '土', b: '水', via: '金' },
  { a: '火', b: '金', via: '土' },
]

function pillarElements(facts: DayFacts): FiveElement[] {
  const list: FiveElement[] = []
  for (const pillar of [facts.pillars.year, facts.pillars.month, facts.pillars.day, facts.pillars.hour]) {
    if (!pillar) continue
    list.push(pillar.stemElement, pillar.branchElement)
  }
  return list
}

export function evaluateZhengWuXing(facts: DayFacts, ctx: ZeriContext): SchoolResult {
  const branches = courseBranches(facts)
  const stems = courseStems(facts)
  const elements = pillarElements(facts)
  const dayStem = facts.pillars.day.stem

  // 1. 补龙
  const dragon = ctx.incomingDragon
  // 只认完整三合局（三支齐现）；半合按规格「缺一为待」不计旺相克。
  const frames = sanHeFrames(branches)
  const completeFrame = frames.find((item) => item.complete) ?? null
  const partialFrame = frames.find((item) => !item.complete) ?? null
  const dragonElement = dragon ? MOUNTAIN_ZHENG_WU_XING[dragon.name] : null
  const dragonHongFan = dragon ? MOUNTAIN_HONG_FAN_WU_XING[dragon.name] : null
  let longVerdict: string | null = null
  let longScore = 0
  const longReasons: string[] = []
  if (dragon && dragonElement && completeFrame) {
    if (completeFrame.element === dragonElement) {
      longVerdict = '旺局'
      longScore = 2
      longReasons.push(
        `日课三合${completeFrame.members.join('')}${completeFrame.element}局成局，与${dragon.name}龙正五行同气`,
      )
    } else if (ELEMENT_SHENG[completeFrame.element] === dragonElement) {
      longVerdict = '相局'
      longScore = 1
      longReasons.push(
        `日课三合局${completeFrame.element}生${dragon.name}龙正五行${dragonElement}，为生入`,
      )
    } else if (ELEMENT_KE[completeFrame.element] === dragonElement) {
      longVerdict = '克局'
      longScore = -2
      longReasons.push(
        `日课三合局${completeFrame.element}克${dragon.name}龙正五行${dragonElement}，为克入`,
      )
    } else {
      longVerdict = '泄耗局'
      longScore = 0
      longReasons.push(
        `日课三合局${completeFrame.element}与${dragon.name}龙${dragonElement}既不同气、不生不克，传统不作旺论`,
      )
    }
    if (dragonHongFan && dragonHongFan !== dragonElement) {
      longReasons.push(
        `洪范（斗首）派视${dragon.name}龙属${dragonHongFan}，与正五行${dragonElement}结论可能不同，未合并处理`,
      )
    }
  } else if (dragon && dragonElement && partialFrame) {
    longVerdict = '半合待成'
    longScore = 0
    longReasons.push(
      `日课仅得${partialFrame.members.join('')}${partialFrame.element}局之 ${partialFrame.hitCount} 支` +
        `（缺${partialFrame.missing.join('')}），三合未成，按「缺一为待」不计旺相克`,
    )
  } else if (dragon && dragonElement) {
    longVerdict = '不成局'
    longScore = 0
    longReasons.push('日课地支与三合四局均不足两支，补龙无从论旺相克')
  }

  // 2. 扶山
  const shanElement = MOUNTAIN_ZHENG_WU_XING[ctx.mountShan]
  const shanBranch = branchOfMountain(ctx.mountShan)
  const keStems = stems.filter((stem) => ELEMENT_KE[GAN_ELEMENT[stem]] === shanElement)
  const shengStems = stems.filter((stem) => ELEMENT_SHENG[GAN_ELEMENT[stem]] === shanElement)
  let shanVerdict: string | null = null
  let shanScore = 0
  const shanReasons: string[] = []
  const tianKeDiChong = [
    facts.pillars.year,
    facts.pillars.month,
    facts.pillars.day,
    facts.pillars.hour,
  ].some(
    (pillar) =>
      pillar !== null &&
      ELEMENT_KE[GAN_ELEMENT[pillar.stem]] === shanElement &&
      ZHI_CLASH[pillar.branch] === shanBranch
  )
  if (tianKeDiChong) {
    shanVerdict = '天克地冲坐山'
    shanScore = -2
    shanReasons.push(`日课存在天干克${shanElement}且地支冲${ctx.mountShan}山的柱`)
  } else if (keStems.length > 0 && shengStems.length === 0) {
    shanVerdict = '克山'
    shanScore = -1
    shanReasons.push(`日课${keStems.join('')}干克坐山${ctx.mountShan}（${shanElement}），传统宜避或改用生扶之干`)
  } else if (shengStems.length > 0) {
    shanVerdict = '生扶坐山'
    shanScore = 1
    shanReasons.push(`日课${shengStems.join('')}干生坐山${ctx.mountShan}（${shanElement}）`)
  } else {
    const biheStems = stems.filter((stem) => GAN_ELEMENT[stem] === shanElement)
    if (biheStems.length > 0) {
      shanVerdict = '山课比和'
      shanScore = 1
      shanReasons.push(`日课${biheStems.join('')}干与坐山${ctx.mountShan}（${shanElement}）比和`)
    } else {
      // 「无克无生」不等于「比和」：必须有天干确与坐山同五行才可记比和，
      // 否则会把毫无关系的日课加一分，属于伪造有利项。
      shanVerdict = '山课无生扶'
      shanScore = 0
      shanReasons.push(`日课天干既未生扶坐山${ctx.mountShan}（${shanElement}），也未与山家比和`)
    }
  }

  shanReasons.push(
    '本条扶山只按日课四柱天干与坐山五行的生克判，未计地支藏干与纳音，属简化口径，需人工复核',
  )

  // 3. 相主
  const subject = ctx.subjects[0]
  let zhuVerdict: string | null = null
  let zhuScore = 0
  const zhuReasons: string[] = []
  if (subject) {
    const hits: string[] = []
    if (dayStem === subject.stem) hits.push('日干与主命年干比肩')
    if (HE_TIAN_GAN[dayStem] === subject.stem) hits.push('日干与主命年干五合')
    const lu = LU_SHEN[subject.stem]
    if (lu && branches.includes(lu)) hits.push(`主命禄神${lu}到日课地支`)
    const changSheng = changShengOf(subject.stem, facts.pillars.day.branch)
    if (WANG_PHASES.includes(changSheng)) hits.push(`主命${subject.stem}日支${facts.pillars.day.branch}处${changSheng}`)
    if (hits.length) {
      zhuVerdict = hits.length >= 2 ? '相主得力' : '相主'
      zhuScore = Math.min(2, hits.length)
      zhuReasons.push(...hits)
    } else {
      zhuVerdict = '相主平常'
      zhuScore = 0
      zhuReasons.push('日课与主命无明显比合、禄马或生旺关系')
    }
  }

  // 4. 调候
  const target = TIAO_HOU_TARGET[facts.monthBranch] ?? null
  let tiaoHouVerdict: string | null = null
  let tiaoHouScore = 0
  const tiaoHouReasons: string[] = []
  if (!facts.pillars.hour) {
    tiaoHouVerdict = null
  } else if (target && target.includes(facts.pillars.hour.branch)) {
    tiaoHouVerdict = '真调候'
    tiaoHouScore = 1
    tiaoHouReasons.push(`${facts.monthBranch}月寒气/暑气宜取${target.join('')}之时，日课得${facts.pillars.hour.branch}时`)
  } else if (target) {
    tiaoHouVerdict = '假调候'
    tiaoHouScore = 0
    tiaoHouReasons.push(`${facts.monthBranch}月宜取${target.join('')}之时，日课${facts.pillars.hour.branch}时未合`)
  }
  if (facts.pillars.hour && target) {
    tiaoHouReasons.push(
      '本条只判寒暖燥湿（调候）；规格要求「调候与扶抑冲突时以扶抑为主」，本包未实现扶抑用神，故需人工复核',
    )
  }

  // 5. 通关
  // 「相战」按两五行各见两次以上（成势）计：四柱八字里偶然出现一个字不算相战，
  // 否则几乎任何日课都会命中「相战无通关」而误扣分。
  const countOf = (element: FiveElement) => elements.filter((item) => item === element).length
  const wars = WAR_PAIRS.filter((pair) => countOf(pair.a) >= 2 && countOf(pair.b) >= 2)
  let guanVerdict: string | null = null
  let guanScore = 0
  const guanReasons: string[] = []
  if (wars.length) {
    const resolved = wars.filter((pair) => elements.includes(pair.via))
    if (resolved.length === wars.length) {
      guanVerdict = '通关'
      guanScore = 1
      guanReasons.push(...wars.map((pair) => `${pair.a}${pair.b}相战，取${pair.via}通关`))
    } else {
      guanVerdict = '相战无通关'
      guanScore = -1
      guanReasons.push(
        ...wars.map((pair) =>
          elements.includes(pair.via)
            ? `${pair.a}${pair.b}相战已有${pair.via}通关`
            : `${pair.a}${pair.b}相战且缺${pair.via}通关`,
        ),
      )
    }
    guanReasons.push('相战按两五行各见两次以上计，单字偶见不计')
  } else {
    guanVerdict = '四柱不相战'
    guanScore = 0
    guanReasons.push('四柱五行未见两神成势相战（各见两次以上）')
  }

  return packResult(
    'ZHENG_WU_XING',
    [
      subRule(
        { ruleId: 'ZWX_BU_LONG', name: '补龙', sourceKey: 'ZHENG_WU_XING' },
        {
          verdict: dragon ? longVerdict : null,
          scoreDelta: longScore,
          reasons: dragon ? longReasons : [],
          dataGap: dragon ? undefined : '未采集入首龙，补龙规则不参与判定',
          needsHumanReview: true,
        }
      ),
      subRule(
        { ruleId: 'ZWX_FU_SHAN', name: '扶山', sourceKey: 'ZHENG_WU_XING' },
        { verdict: shanVerdict, scoreDelta: shanScore, reasons: shanReasons, needsHumanReview: true }
      ),
      subRule(
        { ruleId: 'ZWX_XIANG_ZHU', name: '相主', sourceKey: 'ZHENG_WU_XING' },
        {
          verdict: subject ? zhuVerdict : null,
          scoreDelta: subject ? zhuScore : 0,
          reasons: subject ? zhuReasons : [],
          dataGap: subject
            ? ctx.subjects.length > 1
              ? `相主评分取首位主命；其余 ${ctx.subjects.length - 1} 位仅参与冲命排除，未逐位计分`
              : undefined
            : '未采集主命出生年干支',
        }
      ),
      subRule(
        { ruleId: 'ZWX_TIAO_HOU', name: '调候', sourceKey: 'TIAO_HOU' },
        {
          verdict: tiaoHouVerdict,
          scoreDelta: tiaoHouScore,
          reasons: tiaoHouReasons,
          dataGap: facts.pillars.hour ? undefined : '未指定日课时支，调候规则不参与判定',
          needsHumanReview: true,
        }
      ),
      subRule(
        { ruleId: 'ZWX_TONG_GUAN', name: '通关', sourceKey: 'ZHENG_WU_XING' },
        { verdict: guanVerdict, scoreDelta: guanScore, reasons: guanReasons }
      ),
    ],
    {
      extras: dragon
        ? {
            dragonMountain: dragon.name,
            dragonZhengWuXing: dragonElement,
            dragonHongFanWuXing: dragonHongFan,
            courseElement: completeFrame?.element ?? partialFrame?.element ?? null,
            courseFrameComplete: Boolean(completeFrame),
          }
        : {
            courseElement: completeFrame?.element ?? partialFrame?.element ?? null,
            courseFrameComplete: Boolean(completeFrame),
          },
      conflictFlags:
        dragon && dragonHongFan && dragonHongFan !== dragonElement
          ? ['正五行与洪范（斗首）五行对入首龙归属不一致，两派结论并列，未做合并']
          : [],
    }
  )
}
