/**
 * 玄空大卦规则包。
 * 硬性约束：元运按阳爻 9 年 / 阴爻 6 年（禁用每运 20 年简化）；
 * 抽爻换象的丁、财分开输出，不合并成单一分数。
 */
import {
  HEXAGRAMS,
  changedHexagram,
  guaYun,
  hexagramAt,
  yaoRole,
  yunOfYear,
  DEGREES_PER_HEXAGRAM,
} from '../tables/dagua64'
import { normalizeDeg } from '../../constants/shan24'
import { packResult, subRule } from './common'
import type { DayFacts, ZeriContext } from '../facts'
import type { SchoolResult } from '../types'

export function hexagramsCovering(deg: number): number[] {
  const value = normalizeDeg(deg)
  // 不能对 start/end 再做一次 normalizeDeg：
  // 坐山在 0° 附近时（如 2°），value-7.5 = -5.5 会被折成 354.5，
  // 得到 start=63、end=1，循环不执行、返回空数组，
  // 导致正北方位（子/癸/壬山一带）的「旺气到山」永远是「未到」。
  // 直接用可能为负的商取整，再由下面的取模回绕即可。
  const start = Math.floor((value - 7.5) / DEGREES_PER_HEXAGRAM)
  const end = Math.floor((value + 7.499) / DEGREES_PER_HEXAGRAM)
  const list: number[] = []
  for (let i = start; i <= end; i++) list.push(((i % 64) + 64) % 64)
  return Array.from(new Set(list))
}

export function evaluateXuanKongDaGua(_facts: DayFacts, ctx: ZeriContext): SchoolResult {
  const current = yunOfYear(ctx.eventYear)
  const sitting = hexagramAt(ctx.sittingDeg, ctx.yaoOrder)
  const sittingYun = guaYun(sitting.hexagram)
  const facing = hexagramAt(normalizeDeg(ctx.sittingDeg + 180), ctx.yaoOrder)
  const facingYun = guaYun(facing.hexagram)

  const changed = changedHexagram(sitting.hexagram, sitting.lineIndex)
  const role = yaoRole(changed)

  const wangYaoHexagrams = HEXAGRAMS.filter((item) => guaYun(item).yun === current.yun)
  const sittingArc = hexagramsCovering(ctx.sittingDeg)
  const facingArc = hexagramsCovering(normalizeDeg(ctx.sittingDeg + 180))
  const wangToSitting = wangYaoHexagrams.some((item) => sittingArc.includes(item.index))
  const wangToFacing = wangYaoHexagrams.some((item) => facingArc.includes(item.index))

  return packResult(
    'XUAN_KONG_DA_GUA',
    [
      subRule(
        {
          ruleId: 'XK_GUA_YUN_DANG_WANG',
          name: '卦运当旺',
          sourceKey: 'DAGUA_YUN_TABLE',
        },
        {
          verdict: sittingYun.yun === current.yun ? '当旺' : '失运',
          scoreDelta: sittingYun.yun === current.yun ? 2 : -1,
          reasons: [
            `坐山${ctx.mountShan}线度${ctx.sittingDeg.toFixed(2)}°落${sitting.hexagram.name}卦（${sitting.lineName}，${ctx.yaoOrder === 'ASC' ? '顺排' : '逆排'}口径），该卦卦运为${sittingYun.yun}运`,
            `${ctx.eventYear}年属${current.yun <= 4 ? '上元' : '下元'}第${current.yun}运（${current.startYear}–${current.endYear}年，${current.years}年）`,
            '元运按阳爻 9 年、阴爻 6 年推算，未采用每运 20 年的洛书简化模型',
            '无五运系因洛书配卦数的 5 居中宫无卦；另有五运单列或寄四运之说，元运起止年不同，不可与本表互换',
          ],
          needsHumanReview: true,
        }
      ),
      subRule(
        { ruleId: 'XK_CHOU_YAO_HUAN_XIANG', name: '抽爻换象（丁财分立）', sourceKey: 'XUAN_KONG_DA_GUA' },
        {
          verdict: `${sitting.hexagram.name}之${sitting.lineName}变${changed.name}`,
          // 规格要求丁、财不得合并为单一 score_delta，故本条自身不计分，只输出两个独立字段
          scoreDelta: 0,
          reasons: [
            `变卦${changed.name}上${changed.upper.name}（卦数${changed.upper.guaShu}）下${changed.lower.name}（卦数${changed.lower.guaShu}）`,
            role.kinds.length ? `合${role.kinds.join('、')}` : '未见生成数与合五、合十、合十五',
            '一说爻爻可抽不论生克合十，一说必合生成数与合五十/十五；本包按后者判定并保留分歧标注',
          ],
          needsHumanReview: true,
        }
      ),
      subRule(
        { ruleId: 'XK_GUA_QI_PEI_HE', name: '日课卦气相配', sourceKey: 'XUAN_KONG_DA_GUA' },
        {
          verdict: null,
          scoreDelta: 0,
          reasons: [],
          dataGap:
            '日课干支到六十四卦的映射存在纳甲派与分金派分歧（甲子配比／颐／坎三说并存），未核实到各派公认的同一口径，本版本不臆造映射',
          needsHumanReview: true,
        }
      ),
      subRule(
        { ruleId: 'XK_WANG_QI_DAO_SHAN_XIANG', name: '旺气到山到向', sourceKey: 'DAGUA_YUN_TABLE' },
        {
          verdict: wangToSitting || wangToFacing ? '旺气到' : '旺气未到',
          scoreDelta: (wangToSitting ? 1 : 0) + (wangToFacing ? 1 : 0),
          reasons: [
            `${current.yun}运当旺之卦共${wangYaoHexagrams.length}卦（${wangYaoHexagrams.map((item) => item.name).join('、')}）`,
            wangToSitting ? `坐山${ctx.mountShan}山范围内有当旺卦` : `坐山${ctx.mountShan}山范围内无当旺卦`,
            wangToFacing ? `向首${ctx.facingMeta.name}范围内有当旺卦` : `向首${ctx.facingMeta.name}范围内无当旺卦`,
          ],
        }
      ),
    ],
    {
      extras: {
        event_yun: current.yun,
        sitting_hexagram: sitting.hexagram.name,
        sitting_line: sitting.lineName,
        facing_hexagram: facing.hexagram.name,
        facing_yun: facingYun.yun,
        changed_hexagram: changed.name,
        ding_score: role.ding ? 1 : 0,
        cai_score: role.wealth ? 1 : 0,
        yao_order: ctx.yaoOrder,
      },
      conflictFlags: [
        '二十四山配六十四卦存在「64 卦等分圆周」与「分金/六十龙配卦」两套体系，步长差 0.375°/卦，本包采用等分圆周并强制人工复核',
        `向卦${facing.hexagram.name}卦运${facingYun.yun}与坐卦${sitting.hexagram.name}卦运${sittingYun.yun}分列，未合并为单一卦气吉凶`,
        '卦运求法存在「内外卦相错取洛书数」与「父母卦爻变定运」等口径，本包采用前者，未核实各派一致，需人工复核',
      ],
    }
  )
}
