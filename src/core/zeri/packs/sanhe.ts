/**
 * 三合规则包：重三合六合、禄马贵人到山到向，与正五行包的「补龙」独立输出。
 */
import { branchOfMountain } from '../../constants/shan24'
import {
  LU_SHEN,
  TIAN_YI_GUI_REN,
  YI_MA,
  mountainGuiRenFang,
} from '../tables/sanhe'
import {
  SAN_HE_FRAMES,
  courseBranches,
  sixHarmonyPartner,
  type DayFacts,
  type ZeriContext,
} from '../facts'
import { packResult, subRule } from './common'
import type { SchoolResult } from '../types'

export function evaluateSanHe(facts: DayFacts, ctx: ZeriContext): SchoolResult {
  const branches = courseBranches(facts)
  const mountBranch = branchOfMountain(ctx.mountShan)
  const facingBranch = branchOfMountain(ctx.facingMeta.name)
  const dragonBranch = ctx.incomingDragon
    ? branchOfMountain(ctx.incomingDragon.name)
    : null
  const anchors = [mountBranch, facingBranch, dragonBranch].filter(Boolean) as string[]

  // 1. 三合局
  // 与正五行补龙同一条纪律：完整三合优先于半合。旧实现按表顺序遇半合即 break，
  // 若完整局恰在表后方，会出现「+1 盖住 +2」且结果依赖表序。
  const frameHits = SAN_HE_FRAMES.map((frame) => {
    const inCourse = frame.members.filter((item) => branches.includes(item))
    const anchored = frame.members.filter(
      (item) => branches.includes(item) || anchors.includes(item)
    )
    return { frame, inCourse, anchored }
  })
    .filter((item) => item.anchored.length >= 2)
    .sort(
      (a, b) =>
        b.anchored.length - a.anchored.length || b.inCourse.length - a.inCourse.length
    )

  const completeFrame = frameHits.find((item) => item.anchored.length === 3)
  const halfFrame = frameHits.find(
    (item) => item.anchored.length === 2 && item.inCourse.length >= 1
  )
  let juVerdict: string
  let juScore = 0
  const juReasons: string[] = []
  if (completeFrame) {
    juVerdict = '成局'
    juScore = 2
    juReasons.push(
      `日课与山家凑成${completeFrame.frame.members.join('')}三合${completeFrame.frame.element}局`
    )
  } else if (halfFrame) {
    juVerdict = '半合'
    juScore = 1
    juReasons.push(
      `日课与山家得${halfFrame.frame.members.join('')}三合${halfFrame.frame.element}局之两支，` +
        `缺${halfFrame.frame.members.filter((item) => !halfFrame.anchored.includes(item)).join('')}`
    )
  } else {
    juVerdict = '不成局'
    juReasons.push('日课地支与山家未构成三合局')
  }

  // 2. 六合
  const liuHeHits = anchors.filter((anchor) =>
    branches.includes(sixHarmonyPartner(anchor) ?? '')
  )
  const subjectHit = ctx.subjects.find((subject) =>
    branches.includes(sixHarmonyPartner(subject.branch) ?? '')
  )

  // 3. 禄马贵人到山到向到命
  const dao: string[] = []
  const luTargets = new Set(
    [facts.pillars.year, facts.pillars.month, facts.pillars.day, facts.pillars.hour]
      .filter((pillar) => pillar !== null)
      .map((pillar) => LU_SHEN[pillar!.stem])
      .filter(Boolean)
  )
  if (mountBranch && luTargets.has(mountBranch)) dao.push(`日课禄神到坐山${ctx.mountShan}`)
  if (facingBranch && luTargets.has(facingBranch)) dao.push(`日课禄神到向${ctx.facingMeta.name}`)
  for (const subject of ctx.subjects) {
    if (luTargets.has(subject.branch)) dao.push(`日课禄神到${subject.label}`)
  }
  const maSource = [facts.pillars.day.branch, facts.pillars.year.branch]
  const maTargets = new Set(
    maSource.map((branch) => YI_MA[branch]).filter(Boolean) as string[]
  )
  if (mountBranch && maTargets.has(mountBranch)) dao.push(`驿马到坐山${ctx.mountShan}`)
  if (facingBranch && maTargets.has(facingBranch)) dao.push(`驿马到向${ctx.facingMeta.name}`)
  const guiFang = mountainGuiRenFang(ctx.mountShan) ?? []
  if (guiFang.some((item) => branches.includes(item))) {
    dao.push(`山家贵人方${guiFang.join('')}有日课地支到`)
  }
  for (const subject of ctx.subjects) {
    const gui = TIAN_YI_GUI_REN[subject.stem] ?? []
    if (gui.some((item) => branches.includes(item))) {
      dao.push(`天乙贵人到${subject.label}`)
    }
  }

  return packResult(
    'SAN_HE',
    [
      subRule(
        { ruleId: 'SH_SAN_HE_JU', name: '三合局', sourceKey: 'ZONG_JING_SAN_HE' },
        { verdict: juVerdict, scoreDelta: juScore, reasons: juReasons }
      ),
      subRule(
        { ruleId: 'SH_LIU_HE', name: '六合', sourceKey: 'ZONG_JING_SAN_HE' },
        {
          verdict: liuHeHits.length || subjectHit ? '六合' : '无六合',
          scoreDelta: Math.min(2, liuHeHits.length + (subjectHit ? 1 : 0)),
          reasons: [
            ...liuHeHits.map((item) => `日课与${item}六合`),
            ...(subjectHit ? [`日课与${subjectHit.label}本命六合`] : []),
          ],
        }
      ),
      subRule(
        {
          ruleId: 'SH_LU_MA_GUI_REN_DAO_SHAN',
          name: '禄马贵人到山到向到命',
          sourceKey: 'ZONG_JING_SAN_HE',
        },
        {
          verdict: dao.length ? dao.length >= 2 ? '禄马贵人并到' : '禄马贵人到' : '无禄马贵人到',
          scoreDelta: Math.min(3, dao.length),
          reasons: dao.length ? dao : ['日课禄神、驿马、贵人未到山向与本命'],
          needsHumanReview: true,
        }
      ),
      subRule(
        { ruleId: 'SH_CHONG_SHAN_CHONG_MING', name: '冲山冲命（标记）', sourceKey: 'ZONG_JING_SAN_HE' },
        {
          verdict: '已由前置层处理',
          scoreDelta: 0,
          reasons: ['三合包不重复评分：冲坐山与冲主命由 Layer 3 大煞层直接排除'],
        }
      ),
    ],
    { extras: { mountBranch, dragonBranch } }
  )
}
