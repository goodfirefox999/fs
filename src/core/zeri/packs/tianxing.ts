/**
 * 天星规则包（七政部分）。
 * 精度闸门：本仓库太阳视黄经与 Swiss Ephemeris 逐日实测最大误差 0.014°，
 * 未达规格要求的 0.01°，因此：
 *   1) 包状态固定为 PARTIAL，并公布误差界；
 *   2) 太阴、五星、四余不参与判定（短级数误差 0.24°–0.33°，不得冒充精确星历）；
 *   3) 太阳落在宿界/山界 0.03° 临界区内时强制 needs_human_review。
 */
import { solarLongitude } from '../../astro/solar'
import { XIU_TO_MOUNTAIN, precessionDegForYear, xiuOfLongitude } from '../tables/xiu28'
import { normalizeDeg } from '../../constants/shan24'
import { packResult, subRule } from './common'
import type { DayFacts, ZeriContext } from '../facts'
import type { SchoolResult } from '../types'

/** 已实测的误差界（度）。 */
export const PUBLISHED_SOLAR_ERROR_DEG = 0.02
/** 临界判定半径（度）。 */
export const BOUNDARY_MARGIN_DEG = 0.03

/** 太阳到山/到向的计算结果，供规则与测试复用。 */
export function sunMountainHit(date: string, ctx: ZeriContext) {
  const utHours = 12 - (ctx.longitudeDeg ?? 120) / 15
  const sun = solarLongitude(date, utHours).apparentLongitude
  const xiu = xiuOfLongitude(sun, ctx.eventYear)
  if (!xiu) return null
  const mountain = XIU_TO_MOUNTAIN[xiu.name] ?? null
  return {
    sunLongitude: sun,
    xiu: xiu.name,
    mountain,
    margin: xiu.margin,
    nearBoundary: xiu.margin < BOUNDARY_MARGIN_DEG,
  }
}

export function evaluateTianXing(facts: DayFacts, ctx: ZeriContext): SchoolResult {
  const hit = sunMountainHit(facts.date, ctx)
  const toSitting = Boolean(hit && hit.mountain === ctx.mountShan)
  const toFacing = Boolean(hit && hit.mountain === ctx.facingMeta.name)
  const precession = precessionDegForYear(ctx.eventYear)

  return packResult(
    'TIAN_XING',
    [
      subRule(
        { ruleId: 'TX_SUN_DAO_SHAN', name: '太阳到山（升殿）', sourceKey: 'TIAN_XING' },
        {
          verdict: hit ? (toSitting ? '太阳到山' : '太阳未到山') : null,
          scoreDelta: toSitting ? 2 : 0,
          reasons: hit
            ? [
                `${facts.date}太阳视黄经${hit.sunLongitude.toFixed(3)}°，躔${hit.xiu}宿（开禧宿度按${ctx.eventYear}年岁差平移${precession.toFixed(2)}°），配${hit.mountain ?? '未知'}山`,
                hit.nearBoundary
                  ? `距宿界仅${hit.margin.toFixed(3)}°，在本算法误差界（${PUBLISHED_SOLAR_ERROR_DEG}°）之内，须人工复核`
                  : `距宿界${hit.margin.toFixed(2)}°，大于本算法误差界（${PUBLISHED_SOLAR_ERROR_DEG}°）`,
              ]
            : [],
          needsHumanReview: hit ? hit.nearBoundary : true,
        }
      ),
      subRule(
        { ruleId: 'TX_SUN_DAO_XIANG', name: '太阳到向', sourceKey: 'TIAN_XING' },
        {
          verdict: hit ? (toFacing ? '太阳到向' : '太阳未到向') : null,
          scoreDelta: toFacing ? 1 : 0,
          reasons: hit && toFacing ? [`太阳躔${hit.xiu}宿，配${ctx.facingMeta.name}山（向首）`] : [],
        }
      ),
      subRule(
        { ruleId: 'TX_MOON_SAN_HE_GONG_ZHAO', name: '太阴三合拱照山向', sourceKey: 'TIAN_XING' },
        {
          verdict: null,
          scoreDelta: 0,
          reasons: [],
          dataGap: '太阴黄经未计算：短级数摄动式最大偏差 0.24°–0.33°，未达精度要求，不以近似值冒充精确天星',
          needsHumanReview: true,
        }
      ),
      subRule(
        { ruleId: 'TX_FIVE_PLANETS', name: '五星四余到山到向', sourceKey: 'TIAN_XING' },
        {
          verdict: null,
          scoreDelta: 0,
          reasons: [],
          dataGap: '金木水火土五星与罗睺计都紫气月孛四余未计算',
          needsHumanReview: true,
        }
      ),
    ],
    {
      status: 'PARTIAL',
      partialReason:
        '仅七政中的太阳按已验证算法计算（误差界 0.02°，未达规格 0.01° 闸门）；太阴、五星、四余未计算',
      extras: {
        sun_longitude: hit ? Number(hit.sunLongitude.toFixed(4)) : null,
        sun_xiu: hit ? hit.xiu : null,
        sun_mountain: hit ? hit.mountain : null,
        published_error_deg: PUBLISHED_SOLAR_ERROR_DEG,
        precession_deg: Number(precession.toFixed(3)),
        facing_deg: Number(normalizeDeg(ctx.sittingDeg + 180).toFixed(2)),
      },
      conflictFlags: [
        '宿—山映射采用「巽起角宿等分式」，与依开禧宿度不等宽推定的结果不同，两法在数学上不可同时成立',
      ],
    }
  )
}
