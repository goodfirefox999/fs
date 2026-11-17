import type {
  BirthInfo,
  FenJinResolution,
  FenJinSlot,
  FiveElement,
  TabooHit,
  XianMingAnalysis,
  XianMingRelation,
  YinData,
  YinMatchResult,
} from '../types'
import {
  ZHI_CLASH,
  nayinOfGanZhi,
  relationOf,
} from '../constants/nayin60'
import {
  SHAN_24_LIST,
  branchOfMountain,
  getMountain,
} from '../constants/shan24'
import { suggestFenJinSlots } from '../constants/fenjin120'
import { effectiveYearOfBirth, ganZhiOfYear } from '../utils/date'
import { isInAngularSector, sanShaSectorOf } from './feixing'

const RELATION_TEXT: Record<XianMingRelation, string> = {
  SHAN_SHENG_MING: '坐山五行生仙命纳音',
  BI_HE: '坐山与仙命纳音比和',
  MING_KE_SHAN: '仙命纳音克坐山五行',
  MING_SHENG_SHAN: '仙命纳音生坐山五行',
  SHAN_KE_MING: '坐山五行克仙命纳音',
}

export function relationText(relation: XianMingRelation): string {
  return RELATION_TEXT[relation]
}

function toXianMingRelation(relation: ReturnType<typeof relationOf>): XianMingRelation {
  if (relation === 'SHENG') return 'SHAN_SHENG_MING'
  if (relation === 'BI_HE') return 'BI_HE'
  if (relation === 'KE') return 'SHAN_KE_MING'
  if (relation === 'BEI_SHENG') return 'MING_SHENG_SHAN'
  return 'MING_KE_SHAN'
}

function adjacentMountain(mountName: string, offset: number): string | null {
  if (!offset) return null
  const mountain = getMountain(mountName)
  const next = SHAN_24_LIST[(mountain.index + (offset > 0 ? 1 : -1) + 24) % 24]
  return next.name
}

export function analyzeXianMing(
  person: { label: string; birth: BirthInfo },
  mountName: string,
  fenJin: FenJinResolution
): XianMingAnalysis | null {
  if (!person.birth.date) return null
  let effectiveYear: number
  try {
    effectiveYear = effectiveYearOfBirth(person.birth)
  } catch {
    return null
  }

  const ganZhi = ganZhiOfYear(effectiveYear)
  const yearBranch = ganZhi.slice(1)
  const nayin = nayinOfGanZhi(ganZhi)
  const mount = getMountain(mountName)
  const mountElement = mount.zhengWuXing
  const mountRelation = toXianMingRelation(relationOf(mountElement, nayin.element))
  const fenJinRelation = toXianMingRelation(relationOf(fenJin.slot.element, nayin.element))

  const tabooHits: TabooHit[] = []

  const mountBranch = branchOfMountain(mountName)
  if (mountBranch && ZHI_CLASH[yearBranch] === mountBranch) {
    tabooHits.push({
      code: 'CHONG_SHAN',
      name: '仙命冲山',
      severity: 'AVOID',
      detail: `仙命年支${yearBranch}与坐山${mountName}相冲，传统上建议更换坐山。`,
    })
  }

  const sector = sanShaSectorOf(yearBranch)
  if (sector && isInAngularSector(mount.centerDeg, sector.start, sector.end)) {
    tabooHits.push({
      code: 'SAN_SHA_SHAN',
      name: '三煞山',
      severity: 'AVOID',
      detail: `仙命年支${yearBranch}对应三煞在${sector.direction}，坐山${mountName}落在该范围，传统上建议回避。`,
    })
  }

  if (mountRelation === 'SHAN_KE_MING') {
    tabooHits.push({
      code: 'MOUNT_KE_MING',
      name: '坐山克仙命',
      severity: 'AVOID',
      detail: `坐山${mountName}属${mountElement}，克仙命纳音${nayin.name}（${nayin.element}），传统上视为不利组合。`,
    })
  }
  if (fenJinRelation === 'SHAN_KE_MING') {
    tabooHits.push({
      code: 'FENJIN_KE_MING',
      name: '分金克仙命',
      severity: 'CAUTION',
      detail: `分金${fenJin.slot.ganZhi}纳音属${fenJin.slot.element}，克仙命纳音，可考虑同山其他旺相分金。`,
    })
  }
  if (fenJin.slot.quality === 'KONG_WANG') {
    tabooHits.push({
      code: 'FENJIN_KONG_WANG',
      name: '分金空亡',
      severity: 'CAUTION',
      detail: `${fenJin.slot.ganZhi}属龟甲空亡线，传统上不作为立向主线。`,
    })
  } else if (fenJin.slot.quality === 'GU_XU') {
    tabooHits.push({
      code: 'FENJIN_GU_XU',
      name: '分金孤虚',
      severity: 'CAUTION',
      detail: `${fenJin.slot.ganZhi}属${fenJin.slot.qualityDetail}，传统上建议调整至旺相分金。`,
    })
  }

  if (fenJin.isJianXiang) {
    const adjacent = adjacentMountain(mountName, fenJin.offset)
    const adjacentBranch = adjacent ? branchOfMountain(adjacent) : null
    if (adjacentBranch && ZHI_CLASH[yearBranch] === adjacentBranch) {
      tabooHits.push({
        code: 'CHONG_JIAN',
        name: '仙命冲兼',
        severity: 'CAUTION',
        detail: `兼向靠近${adjacent}山，仙命年支${yearBranch}与其相冲，兼向线度需专业复核。`,
      })
    }
  }

  let verdict: XianMingAnalysis['verdict']
  if (tabooHits.some((hit) => hit.severity === 'AVOID')) {
    verdict = 'AVOID'
  } else if (tabooHits.length > 0 || fenJin.slot.quality !== 'WANG_XIANG') {
    verdict = 'ADJUST'
  } else {
    verdict = 'SUITABLE'
  }

  const summary =
    verdict === 'SUITABLE'
      ? '按年干支纳音与坐山、分金五行的对应关系，未发现需要回避的组合；仍建议实地复核地形与排水。'
      : verdict === 'ADJUST'
        ? '存在需要调整或复核的项目，可优先考虑同山旺相分金，并请专业人士现场确认。'
        : '存在传统上建议回避的组合，建议更换坐山或分金线度后再评估。'

  const notes = [
    `仙命按${effectiveYear}年${ganZhi}（${nayin.name}）计算；出生日期在立春前时按上一年计。`,
    '本分析只覆盖年干支纳音、坐山正五行、分金纳音与三煞、冲山等可核验规则。',
    '丧坑、丧窟、刺穴、地虎食骨等分金细则流派差异较大，本工具不自动下结论，需专业罗盘师复核。',
  ]

  return {
    label: person.label,
    birth: person.birth,
    effectiveYear,
    ganZhi,
    nayin: nayin.name,
    element: nayin.element,
    mountElement,
    mountRelation,
    fenJinRelation,
    tabooHits,
    verdict,
    summary,
    notes,
  }
}

export function analyzeYinMatch(
  yin: YinData,
  mountName: string,
  fenJin: FenJinResolution
): YinMatchResult {
  const deceased = yin.deceased
    .map((person) => analyzeXianMing(person, mountName, fenJin))
    .filter((item): item is XianMingAnalysis => item !== null)

  const notes: string[] = []
  if (deceased.length < yin.deceased.length) {
    notes.push('部分仙命出生信息不完整，未纳入计算。')
  }
  notes.push('本汇总按已录入仙命逐个比对，只覆盖可核验的年干支纳音、坐山与分金关系。')

  let verdict: YinMatchResult['verdict'] = 'SUITABLE'
  if (!deceased.length) {
    verdict = 'UNKNOWN'
  } else if (deceased.some((item) => item.verdict === 'AVOID')) {
    verdict = 'AVOID'
  } else if (deceased.some((item) => item.verdict === 'ADJUST')) {
    verdict = 'ADJUST'
  }

  const suggestedSlots = suggestFenJinSlots(mountName)
    .filter((slot) =>
      deceased.every((person) => relationOf(slot.element, person.element) !== 'KE')
    )
    .slice(0, 3)

  const summary =
    verdict === 'SUITABLE'
      ? '已录入仙命与当前坐向未发现需回避的组合，可继续核对地形、排水与现场安全。'
      : verdict === 'ADJUST'
        ? '当前坐向或分金存在需调整的项目，可参考旺相分金与专业意见。'
        : verdict === 'AVOID'
          ? '当前坐向与仙命存在传统上建议回避的组合，建议更换坐山或分金后再评估。'
          : '缺少可用的仙命出生信息，暂无法给出结论。'

  return {
    fenJin,
    deceased,
    verdict,
    summary,
    suggestedSlots,
    notes,
  }
}

export function slotRelationToElement(slot: FenJinSlot, element: FiveElement): XianMingRelation {
  return toXianMingRelation(relationOf(slot.element, element))
}

export function clashesMount(yearBranch: string, mountName: string): boolean {
  const mountBranch = branchOfMountain(mountName)
  return Boolean(mountBranch && ZHI_CLASH[yearBranch] === mountBranch)
}
