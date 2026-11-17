import type {
  PalaceChart,
  PalaceId,
  PatternCode,
  XuanKongChart,
} from '../types'
import { PALACES, PALACE_IDS } from '../constants/luoshu'
import {
  JIAN_XIANG_LABELS,
  SHAN_24_LIST,
  analyzeJianXiang,
  getMountain,
  normalizeDeg,
  type MountainMeta,
} from '../constants/shan24'
import { flyNinePalaces } from './feixing'

export type WuHuangPolicy = 'BEN_SHAN' | 'JI_KUN'

export interface XuanKongOptions {
  period: number
  sittingDeg: number
  wuHuangPolicy?: WuHuangPolicy
}

export interface FlightResolution {
  centerStar: number
  direction: 1 | -1
  baseMountain: MountainMeta | null
  substituted: boolean
}

export function periodFromYear(year: number): number {
  const period = Math.floor((year - 1864) / 20) + 1
  return Math.min(9, Math.max(1, period))
}

export function findMountainByGongAndYuan(gong: PalaceId, yuan: MountainMeta['yuan']): MountainMeta {
  const found = SHAN_24_LIST.find((mountain) => mountain.gong === gong && mountain.yuan === yuan)
  if (!found) throw new Error(`宫位 ${gong} 无${yuan}元龙`)
  return found
}

export function resolveFlight(
  yunStar: number,
  target: MountainMeta,
  useTiGua: boolean,
  wuHuangPolicy: WuHuangPolicy = 'BEN_SHAN'
): FlightResolution {
  if (yunStar === 5) {
    const direction =
      wuHuangPolicy === 'JI_KUN' ? getMountain('坤').yinYang : target.yinYang
    return { centerStar: 5, direction, baseMountain: null, substituted: false }
  }
  const baseMountain = findMountainByGongAndYuan(yunStar as PalaceId, target.yuan)
  const centerStar = useTiGua ? baseMountain.tiGuaStar : yunStar
  return {
    centerStar,
    direction: baseMountain.yinYang,
    baseMountain,
    substituted: useTiGua,
  }
}

const PATTERN_LABELS: Record<PatternCode, string> = {
  WANG_SHAN_WANG_XIANG: '旺山旺向',
  SHANG_SHAN_XIA_SHUI: '上山下水',
  SHUANG_XING_DAO_XIANG: '双星到向',
  SHUANG_XING_DAO_SHAN: '双星到山',
  NORMAL: '一般格局',
}

const PATTERN_NOTES: Record<PatternCode, string> = {
  WANG_SHAN_WANG_XIANG:
    '当运山星到坐山、当运向星到向首，传统视为坐向与当运星配合较完整的格局；仍需结合实地采光、通风与动线判断。',
  SHANG_SHAN_XIA_SHUI:
    '当运山星到向首、当运向星到坐山，传统称上山下水；宜通过内部布局与实地形势调和，不宜只凭盘面下结论。',
  SHUANG_XING_DAO_XIANG:
    '当运山星与向星同聚向首，传统重外向纳气；坐山一侧宜稳重、安静，避免过度开敞。',
  SHUANG_XING_DAO_SHAN:
    '当运山星与向星同聚坐山，传统重内聚与靠山；向首宜保持通透，但不宜过度空旷。',
  NORMAL:
    '当运星未形成典型四局，按各宫山向组合逐宫分析，重点看主要出入口、卧室与常用活动区。',
}

export function buildXuanKong(options: XuanKongOptions): XuanKongChart {
  const period = Math.round(options.period)
  if (period < 1 || period > 9) throw new Error(`无效运: ${options.period}`)
  const sittingDeg = normalizeDeg(options.sittingDeg)
  const facingDeg = normalizeDeg(sittingDeg + 180)
  const sitJian = analyzeJianXiang(sittingDeg)
  const faceJian = analyzeJianXiang(facingDeg)
  const sitting = sitJian.mountain
  const facing = faceJian.mountain
  const jianXiang = sitJian.isJianXiang
  const tiGua = sitJian.useTiGua

  const yunChart = flyNinePalaces(period, 1)
  const shanYunStar = yunChart.byPalace[sitting.gong]
  const xiangYunStar = yunChart.byPalace[facing.gong]
  const shanFlight = resolveFlight(
    shanYunStar,
    sitting,
    sitJian.useTiGua,
    options.wuHuangPolicy
  )
  const xiangFlight = resolveFlight(
    xiangYunStar,
    facing,
    faceJian.useTiGua,
    options.wuHuangPolicy
  )
  const shanChart = flyNinePalaces(shanFlight.centerStar, shanFlight.direction)
  const xiangChart = flyNinePalaces(xiangFlight.centerStar, xiangFlight.direction)

  const palaces: PalaceChart[] = PALACE_IDS.map((palace) => {
    const meta = PALACES[palace]
    return {
      palace,
      trigram: meta.trigram,
      direction: meta.direction,
      element: meta.element,
      yun: yunChart.byPalace[palace],
      shan: shanChart.byPalace[palace],
      xiang: xiangChart.byPalace[palace],
    }
  })

  const sit = sitting.gong
  const face = facing.gong
  const shanAtSit = shanChart.byPalace[sit]
  const xiangAtSit = xiangChart.byPalace[sit]
  const shanAtFace = shanChart.byPalace[face]
  const xiangAtFace = xiangChart.byPalace[face]

  const flags: PatternCode[] = []
  if (shanAtSit === period && xiangAtFace === period) flags.push('WANG_SHAN_WANG_XIANG')
  if (shanAtFace === period && xiangAtSit === period) flags.push('SHANG_SHAN_XIA_SHUI')
  if (shanAtFace === period && xiangAtFace === period) flags.push('SHUANG_XING_DAO_XIANG')
  if (shanAtSit === period && xiangAtSit === period) flags.push('SHUANG_XING_DAO_SHAN')
  const pattern = flags[0] ?? 'NORMAL'

  const warnings: string[] = []
  if (jianXiang) {
    warnings.push(
      tiGua
        ? `坐向落在兼向区（${JIAN_XIANG_LABELS[sitJian.kind]}），已按替卦起星；兼向对罗盘精度要求较高，建议用实体罗盘复测。`
        : `坐向落在兼向区，${sitting.name}兼${sitJian.adjacent?.name}同卦宫且阴阳相同，按同宫比和仍用下卦起星。`
    )
  }
  if (sitJian.kind === 'CHU_GUA') {
    warnings.push(
      `坐山${sitting.name}兼${sitJian.adjacent?.name}已跨出${PALACES[sitting.gong].trigram}卦宫（传统称出卦），向首同理；此类线度传统上建议重新立极定向。`
    )
  }
  if (shanFlight.centerStar === period) {
    warnings.push('当运山星入中，传统称山星入囚，宜重点关注坐山一侧的通风、采光与安静程度。')
  }
  if (xiangFlight.centerStar === period) {
    warnings.push('当运向星入中，传统称向星入囚，宜重点关注出入口与前方视野的通透程度。')
  }
  if (shanChart.byPalace[sit] === 5 || xiangChart.byPalace[sit] === 5) {
    warnings.push('五黄星到坐山，传统视为宜静不宜动；该区域宜保持整洁、减少大拆大改。')
  }
  if (shanChart.byPalace[face] === 5 || xiangChart.byPalace[face] === 5) {
    warnings.push('五黄星到向首，传统视为宜稳不宜冲；出入口区域宜保持通畅、避免堆放杂物。')
  }

  return {
    period,
    sitting: { shan: sitting.name, deg: sittingDeg, palace: sitting.gong },
    facing: { shan: facing.name, deg: facingDeg, palace: facing.gong },
    palaces,
    pattern,
    patternLabel: PATTERN_LABELS[pattern],
    patternTraditional: PATTERN_NOTES[pattern],
    flags,
    isJianXiang: jianXiang,
    tiGuaUsed: tiGua,
    jianKind: sitJian.kind,
    warnings,
  }
}

export function chartPalace(
  chart: XuanKongChart,
  palace: PalaceId
): PalaceChart {
  const found = chart.palaces.find((item) => item.palace === palace)
  if (!found) throw new Error(`盘面缺少宫位 ${palace}`)
  return found
}

export function comboKeyOf(palace: PalaceChart): string {
  return `${palace.shan}${palace.xiang}`
}
