import type {
  Archive,
  ContentBundle,
  MonthlyInfo,
  PalaceId,
  Report,
  ReportWarning,
  SceneMode,
  ZeRiCategory,
  ZeRiItem,
  ZeRiQuery,
  ZeRiResult,
} from '../types'
import { branchOfMountain, normalizeDeg, resolveMountain } from '../constants/shan24'
import { resolveFenJin } from '../constants/fenjin120'
import { buildInsights } from '../content'
import { todayYmd } from '../utils/date'
import { analyzeBaZhai } from './bazhai'
import {
  annualInfo,
  isInSanShaSector,
  monthlyForDate,
} from './feixing'
import { analyzeYinMatch } from './xianming'
import { buildXuanKong, periodFromYear } from './xuankong'
import { buildZeRi } from './zeri'

export interface ReportOptions {
  contents?: ContentBundle | null
  unlocked?: boolean
  zeri?: ZeRiItem[]
  zeriStart?: string
  zeriDays?: number
  zeriMax?: number
}

export interface SittingFacing {
  sittingDeg: number
  facingDeg: number
  sitting: ReturnType<typeof resolveMountain>
  facing: ReturnType<typeof resolveMountain>
}

export function sittingFacingOf(archive: Archive): SittingFacing {
  const facingDeg = normalizeDeg(archive.reading.facingDeg)
  const sittingDeg = normalizeDeg(facingDeg + 180)
  return {
    sittingDeg,
    facingDeg,
    sitting: resolveMountain(sittingDeg),
    facing: resolveMountain(facingDeg),
  }
}

export function zeriCategoryOf(archive: Archive): ZeRiCategory {
  if (archive.mode === 'YIN') return 'YIN_ANZANG'
  return archive.yang?.propertyType === 'RESIDENTIAL' ? 'YANG_RUZHAI' : 'YANG_DONGTU'
}

export function zeriQueryForArchive(
  archive: Archive,
  startDate: string,
  daysCount: number,
  maxResults = 8
): ZeRiQuery {
  const { sitting, sittingDeg } = sittingFacingOf(archive)
  const familyBirths =
    archive.mode === 'YANG'
      ? archive.yang?.members.map((member) => member.birth) ?? []
      : archive.yin?.descendants.map((person) => person.birth) ?? []
  const deceasedBirths =
    archive.mode === 'YIN' ? archive.yin?.deceased.map((person) => person.birth) ?? [] : []
  return {
    startDate,
    daysCount,
    category: zeriCategoryOf(archive),
    mountShan: sitting.name,
    familyBirths,
    deceasedBirths,
    chongSangMode: 'warn',
    sanShaMode: 'year_month',
    maxResults,
    sittingDeg: sittingDeg,
    eventYear: archive.eventYear,
    incomingDragon: archive.mode === 'YIN' ? archive.yin?.incomingDragon ?? null : null,
  }
}

export function buildArchiveZeRi(
  archive: Archive,
  startDate = todayYmd(),
  daysCount = 90,
  maxResults = 8
): ZeRiResult {
  return buildZeRi(zeriQueryForArchive(archive, startDate, daysCount, maxResults))
}

function annualWarnings(archive: Archive, report: Report): ReportWarning[] {
  const { sittingDeg, sitting, facing } = sittingFacingOf(archive)
  const annual = report.annual
  const warnings: ReportWarning[] = []
  if (annual.chart.byPalace[sitting.gong] === 5) {
    warnings.push({
      code: 'ANNUAL_WU_HUANG_SIT',
      level: 'CAUTION',
      text: `${annual.year}年五黄到坐山（${facing.name}向·${sitting.name}山），该侧宜保持整洁安静，减少大拆大改。`,
    })
  }
  if (annual.chart.byPalace[facing.gong] === 5) {
    warnings.push({
      code: 'ANNUAL_WU_HUANG_FACE',
      level: 'CAUTION',
      text: `${annual.year}年五黄到向首，出入口区域宜保持通畅，避免堆放杂物与尖锐摆设。`,
    })
  }
  const sittingBranch = branchOfMountain(sitting.name)
  if (sittingBranch && annual.suiPo === sittingBranch) {
    warnings.push({
      code: 'SUI_PO',
      level: 'CAUTION',
      text: `${annual.year}年岁破在${annual.suiPo}，与坐山同支，传统上该侧宜静不宜动。`,
    })
  } else if (sittingBranch && annual.taiSui === sittingBranch) {
    warnings.push({
      code: 'TAI_SUI',
      level: 'INFO',
      text: `${annual.year}年太岁在${annual.taiSui}，与坐山同支；传统上宜减少正面对冲式施工。`,
    })
  }
  if (isInSanShaSector(sittingDeg, annual.taiSui)) {
    warnings.push({
      code: 'SAN_SHA',
      level: 'CAUTION',
      text: `${annual.year}年三煞在${annual.sanShaDirection}，坐山落在该范围，动土与外部改造宜请专业人士复核。`,
    })
  }
  return warnings
}

export function buildReport(archive: Archive, options: ReportOptions = {}): Report {
  const { sittingDeg, sitting, facing } = sittingFacingOf(archive)
  const period = periodFromYear(archive.eventYear)
  const chart = buildXuanKong({ period, sittingDeg })
  const annual = annualInfo(archive.eventYear)
  // 月盘依赖「当前月」；档案只存 eventYear。跨年时把今年月盘叠到另一年的年盘上
  // 会得到两张互不匹配的盘，此时不提供月盘（页面显示为「—」）。
  const currentYear = Number(todayYmd().slice(0, 4))
  const monthly: MonthlyInfo | undefined =
    archive.eventYear === currentYear ? monthlyForDate(todayYmd()) : undefined

  chart.palaces.forEach((palace) => {
    palace.annual = annual.chart.byPalace[palace.palace]
    if (monthly) palace.monthly = monthly.chart.byPalace[palace.palace]
  })

  const warnings: ReportWarning[] = chart.warnings.map((text, index) => ({
    code: `CHART_${index + 1}`,
    level: 'CAUTION',
    text,
  }))

  if (archive.reading.inputMethod === 'SENSOR' && archive.reading.stability < 85) {
    warnings.push({
      code: 'COMPASS_STABILITY',
      level: 'CAUTION',
      text: `罗盘采样稳定性为 ${Math.round(archive.reading.stability)}%，低于建议值；建议到开阔处复测或改用手动度数输入。`,
    })
  }
  if (archive.reading.northType === 'MAGNETIC' && Math.abs(archive.reading.declination) >= 3) {
    warnings.push({
      code: 'MAGNETIC_NORTH',
      level: 'INFO',
      text: `当地磁偏角约 ${archive.reading.declination.toFixed(1)}°，本盘按磁北读数排布；如使用真北读数，请以校准后的度数为准。`,
    })
  }

  const bazhai =
    archive.mode === 'YANG' && archive.yang
      ? analyzeBaZhai(archive.yang.members, sitting.name)
      : undefined
  if (archive.mode === 'YANG' && (!archive.yang || archive.yang.members.length === 0)) {
    warnings.push({
      code: 'NO_MEMBERS',
      level: 'INFO',
      text: '尚未录入居住者出生信息，命卦与八宅分区暂未计算。',
    })
  }

  let fenjin
  let yinMatch
  if (archive.mode === 'YIN') {
    fenjin = resolveFenJin(sittingDeg)
    if (fenjin.warning) {
      warnings.push({ code: 'FENJIN', level: 'CAUTION', text: fenjin.warning })
    }
    if (archive.yin) {
      yinMatch = analyzeYinMatch(archive.yin, sitting.name, fenjin)
      if (yinMatch.verdict === 'AVOID') {
        warnings.push({
          code: 'YIN_VERDICT',
          level: 'DANGER',
          text: '当前坐向与已录入仙命存在传统上建议回避的组合，请先查看仙命分析或更换分金线度。',
        })
      } else if (yinMatch.verdict === 'ADJUST') {
        warnings.push({
          code: 'YIN_VERDICT',
          level: 'CAUTION',
          text: '当前分金或仙命关系存在需调整的项目，请由专业人士现场复核。',
        })
      }
    }
  }

  const previewPalaces: PalaceId[] = [5, facing.gong]
  const unlocked = options.unlocked ?? false
  if (unlocked && !options.contents) {
    warnings.push({
      code: 'CONTENT_UNAVAILABLE',
      level: 'CAUTION',
      text: '已解锁但完整内容加载失败，请检查网络后重试；当前仍显示预览内容。',
    })
  }

  const insights = buildInsights(
    chart,
    archive.mode,
    unlocked ? options.contents ?? null : null,
    previewPalaces,
    unlocked
  )

  const zeri =
    options.zeri ??
    buildArchiveZeRi(
      archive,
      options.zeriStart ?? todayYmd(),
      options.zeriDays ?? 90,
      options.zeriMax ?? 8
    ).items

  const report: Report = {
    archiveId: archive.id,
    mode: archive.mode,
    chart,
    annual,
    monthly,
    bazhai,
    fenjin,
    yinMatch,
    zeri,
    insights,
    warnings: [],
    previewPalaces,
    contentVersion: options.contents?.version ?? 'preview-2026.10.1',
    generatedAt: Date.now(),
  }

  report.warnings = [...warnings, ...annualWarnings(archive, report)]
  return report
}

export function reportModeLabel(mode: SceneMode): string {
  return mode === 'YANG' ? '阳宅环境建档' : '先人纪念地环境建档'
}

export function verdictLabel(verdict: string): string {
  if (verdict === 'SUITABLE') return '暂未发现需回避项'
  if (verdict === 'ADJUST') return '建议调整后复核'
  if (verdict === 'AVOID') return '建议回避当前组合'
  return '待补充信息'
}
