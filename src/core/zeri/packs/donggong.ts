/**
 * 董公规则包：十二建星、九星轮值（煞贡/直星/人专）、勾陈黑道、安床忌宿。
 * 硬性约束：吉星只能参与本包评分，不能覆盖 Layer 3 的大煞排除。
 */
import type { ZeRiCategory } from '../../types'
import {
  AN_CHUANG_AVOID_XIU,
  SIX_CAUTION_STARS,
  THREE_LUCKY_STARS,
  dongGongStarOf,
  isGouChenHeiDao,
  monthGroupOf,
} from '../tables/donggong'
import { packResult, subRule } from './common'
import { NINE_STARS } from '../tables/donggong'
import { JIN_SHEN_XIU } from '../tables/donggong'
import type { DayFacts, ZeriContext } from '../facts'
import type { SchoolResult } from '../types'
import { ZERI_CATEGORY_LABELS } from '../../constants/xieji'

/** 十二建星 × 用事类别的传统取舍（规格口径：破、闭一般不利；成、开、定、满各有宜忌）。 */
const JIAN_CHU_SCORE: Record<string, Partial<Record<ZeRiCategory, number>>> = {
  建: { YANG_DONGTU: -1, YIN_ANZANG: -1 },
  除: { YANG_RUZHAI: 1 },
  满: { YANG_RUZHAI: -1 },
  平: { YANG_DONGTU: -1, YIN_ANZANG: -1 },
  定: { YANG_RUZHAI: 1, YIN_ANZANG: 1 },
  执: { YANG_DONGTU: -1 },
  破: { YANG_RUZHAI: -1, YANG_DONGTU: -1, YIN_ANZANG: -1, YIN_XIUFEN: -1 },
  危: { YANG_DONGTU: -1 },
  成: { YANG_RUZHAI: 1, YANG_DONGTU: 1, YIN_ANZANG: 1, YIN_XIUFEN: 1 },
  收: { YIN_ANZANG: -1 },
  开: { YANG_RUZHAI: 1, YANG_DONGTU: 1, YIN_ANZANG: 1 },
  闭: { YANG_RUZHAI: -1, YANG_DONGTU: -1, YIN_XIUFEN: -1 },
}

export function evaluateDongGong(facts: DayFacts, ctx: ZeriContext): SchoolResult {
  const star = dongGongStarOf(facts.monthBranch, facts.pillars.day.ganZhi)
  const group = monthGroupOf(facts.monthBranch)
  const lucky = THREE_LUCKY_STARS.includes(star)
  const caution = SIX_CAUTION_STARS.includes(star)
  const jianChuScore = JIAN_CHU_SCORE[facts.zhiXing]?.[ctx.category] ?? 0
  const gouChen = isGouChenHeiDao(facts.monthBranch, facts.pillars.day.branch)
  const anChuangXiu =
    ctx.category === 'YANG_RUZHAI' && AN_CHUANG_AVOID_XIU.includes(facts.xiu)
  const jinShenXiu = JIN_SHEN_XIU.includes(facts.xiu)

  return packResult(
    'DONG_GONG',
    [
      subRule(
        {
          ruleId: 'DG_SHA_GONG_ZHI_XING_REN_ZHUAN',
          name: '煞贡·直星·人专值日',
          sourceKey: 'JIN_FU_JING',
        },
        {
          verdict: star,
          scoreDelta: lucky ? 2 : 0,
          reasons: lucky
            ? [
                `${facts.monthBranch}月（${group === 'MENG' ? '四孟' : group === 'ZHONG' ? '四仲' : '四季'}）甲子起星，本日${facts.pillars.day.ganZhi}值${star}`,
                '本包加分仅抵中低层神煞，不解金神七煞，也不得推翻前置层排除',
              ]
            : [
                `本日${facts.pillars.day.ganZhi}值${star}，非煞贡/直星/人专`,
                `${facts.monthBranch}月组九星轮值序：${NINE_STARS.join('→')}`,
              ],
          dataGap: caution
            ? `${star}为金符经九星中除煞贡/直星/人专之外的六星之一，其降分口径未核实到可靠出处，本包不虚构分值（记 0 分）`
            : undefined,
          needsHumanReview: true,
        }
      ),
      subRule(
        { ruleId: 'DG_JIAN_CHU', name: '十二建星取舍', sourceKey: 'XIEJI_BASE' },
        {
          verdict: facts.zhiXing,
          scoreDelta: jianChuScore,
          reasons: [
            `${facts.zhiXing}日用于${ZERI_CATEGORY_LABELS[ctx.category]}，` +
              `传统取舍${jianChuScore > 0 ? '为宜' : jianChuScore < 0 ? '为忌' : '本包未列专门取舍'}`,
          ],
          dataGap:
            ctx.category === 'YANG_JIAQU' || ctx.category === 'YANG_KAISHI'
              ? '嫁娶、开市为产品端补充事项，十二建星专门取舍尚未逐条考证，本包不虚构分值'
              : undefined,
          needsHumanReview: true,
        }
      ),
      subRule(
        { ruleId: 'DG_GOU_CHEN_HEI_DAO', name: '勾陈黑道日', sourceKey: 'DONG_GONG' },
        {
          verdict: gouChen ? '勾陈黑道' : '非勾陈黑道',
          scoreDelta: gouChen ? -1 : 0,
          reasons: gouChen
            ? [`${facts.monthBranch}月勾陈黑道在${facts.pillars.day.branch}日`]
            : ['本日不犯本月勾陈黑道'],
        }
      ),
      subRule(
        {
          ruleId: 'DG_JIN_SHEN_XIU',
          name: '二十八宿金神七煞（提示）',
          sourceKey: 'DONG_GONG',
        },
        {
          verdict: jinShenXiu ? `值宿${facts.xiu}为忌` : `值宿${facts.xiu}非金神七煞宿`,
          scoreDelta: jinShenXiu ? -1 : 0,
          reasons: jinShenXiu
            ? [
                `《董公选要览》另以角亢奎娄牛鬼星为金神七煞，本日值${facts.xiu}；此为与年干式重名的另一系统，本包只在本派内扣分，不冒充前置层硬排除`,
              ]
            : ['本日值宿不在角亢奎娄牛鬼星之内'],
          needsHumanReview: true,
        }
      ),
      subRule(
        { ruleId: 'DG_AN_CHUANG_JIU_XIU', name: '安床忌宿', sourceKey: 'DONG_GONG' },
        {
          verdict:
            ctx.category === 'YANG_RUZHAI'
              ? anChuangXiu
                ? `值宿${facts.xiu}为忌`
                : `值宿${facts.xiu}不论`
              : null,
          scoreDelta: anChuangXiu ? -1 : 0,
          reasons: anChuangXiu
            ? [`安床忌心昴箕娄奎尾参危及金神七煞宿，本日值${facts.xiu}`]
            : ctx.category === 'YANG_RUZHAI'
              ? [`本日值${facts.xiu}宿，不在安床忌宿之列`]
              : [],
          dataGap: ctx.category === 'YANG_RUZHAI' ? undefined : '本条只适用于入宅安床',
        }
      ),
    ],
    {
      extras: {
        donggong_star: star,
        month_group: group,
        jie_sha_scope: '仅解中低神煞',
      },
      conflictFlags: [
        '九星轮值出自《金符经》系统，官修《协纪辨方书》义例未收，故不与协纪吉神合并计分',
      ],
    }
  )
}
