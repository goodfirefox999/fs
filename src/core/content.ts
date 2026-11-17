import type {
  ContentBundle,
  PalaceId,
  PalaceInsight,
  SceneMode,
  ShuangXingContent,
  XuanKongChart,
} from './types'
import { STARS } from './constants/luoshu'
import { relationOf } from './constants/nayin60'

const STAR_ACTION: Record<number, string> = {
  1: '保持该区通风与光线柔和，可放置常用书籍或通讯设备。',
  2: '减少长期堆物，保持地面干燥，适合作为储物或短时休整区。',
  3: '避免频繁搬动与尖锐摆设，可用绿植或木质收纳柔化空间。',
  4: '适合学习、阅读或需要专注的工作位，保持桌面整洁。',
  5: '不宜作为长期停留的主位，保持通畅、整洁与适度照明。',
  6: '适合规则明确的工作区，金属物件收纳归位，避免尖锐外露。',
  7: '适合需要表达与沟通的区域，注意控制音量与光线刺激。',
  8: '适合稳定收纳与长期使用的家具，保持承重与动线安全。',
  9: '适合社交与展示，注意用电安全与光线过热。',
}

const RELATION_PREVIEW: Record<string, string> = {
  SHENG: '山星生向星，内在投入容易转化为外部结果，注意节奏与休息。',
  KE: '山星克向星，内部安排对外部目标形成约束，宜先稳后动。',
  BI_HE: '山向同气，节奏容易一致，宜设定清晰边界。',
  BEI_SHENG: '向星生山星，外部资源容易回流到内部，适合沉淀与修整。',
  BEI_KE: '向星克山星，外部事务容易牵动内部节奏，需预留缓冲。',
}

export interface PreviewInsight {
  title: string
  analysis: string
  actions: string[]
  riskLevel: string
}

export function comboIdOf(shan: number, xiang: number): string {
  return `S${shan}X${xiang}`
}

export function riskLevelOf(shan: number, xiang: number): string {
  if (shan === 5 || xiang === 5) return 'active'
  if ([2, 7].includes(shan) || [2, 7].includes(xiang)) return 'attention'
  return 'balanced'
}

export function previewInsight(shan: number, xiang: number): PreviewInsight {
  const shanStar = STARS[shan]
  const xiangStar = STARS[xiang]
  const relation = relationOf(shanStar.element, xiangStar.element)
  return {
    title: `山${shanStar.name} · 向${xiangStar.name}`,
    analysis: `山星${shanStar.name}主${shanStar.theme}，向星${xiangStar.name}主${xiangStar.theme}。${RELATION_PREVIEW[relation]}`,
    actions: [STAR_ACTION[shan], STAR_ACTION[xiang]],
    riskLevel: riskLevelOf(shan, xiang),
  }
}

export function findComboContent(
  bundle: ContentBundle | null | undefined,
  shan: number,
  xiang: number
): ShuangXingContent | undefined {
  if (!bundle) return undefined
  return bundle.shuangxing.find((item) => item.combo.shan === shan && item.combo.xiang === xiang)
}

export function buildInsights(
  chart: XuanKongChart,
  mode: SceneMode,
  bundle: ContentBundle | null,
  previewPalaces: PalaceId[],
  unlocked: boolean
): PalaceInsight[] {
  return chart.palaces.map((palace) => {
    const comboKey = `${palace.shan}${palace.xiang}`
    const preview = previewInsight(palace.shan, palace.xiang)
    const content = unlocked ? findComboContent(bundle, palace.shan, palace.xiang) : undefined
    if (content) {
      const analysis = mode === 'YIN' ? content.yin.analysis : content.analysis
      const actions = mode === 'YIN' ? content.yin.actions : content.actions
      return {
        palace: palace.palace,
        comboKey,
        title: content.title,
        analysis,
        actions,
        riskLevel: content.riskLevel,
        locked: false,
      }
    }
    if (previewPalaces.includes(palace.palace)) {
      return {
        palace: palace.palace,
        comboKey,
        title: preview.title,
        analysis: preview.analysis,
        actions: preview.actions,
        riskLevel: preview.riskLevel,
        locked: false,
      }
    }
    return {
      palace: palace.palace,
      comboKey,
      title: preview.title,
      analysis: '该宫位的完整分析需解锁后查看。',
      actions: [],
      riskLevel: preview.riskLevel,
      locked: true,
    }
  })
}
