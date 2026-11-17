import type { SceneMode } from '@/core/types'
import {
  angularDelta,
  mountainOffset,
  normalizeDeg,
  resolveMountain,
} from '@/core/constants/shan24'

export function formatTimestamp(value: number): string {
  const date = new Date(value)
  const month = date.getMonth() + 1
  const day = date.getDate()
  return `${date.getFullYear()}-${month < 10 ? `0${month}` : month}-${day < 10 ? `0${day}` : day}`
}

export function modeLabel(mode: SceneMode): string {
  return mode === 'YANG' ? '阳宅' : '纪念地'
}

export function modeFullLabel(mode: SceneMode): string {
  return mode === 'YANG' ? '阳宅环境' : '先人纪念地'
}

export function degreeText(deg: number): string {
  return `${normalizeDeg(deg).toFixed(1)}°`
}

export interface SittingFacingText {
  sitting: string
  facing: string
  text: string
  deg: string
  isJianXiang: boolean
  offset: number
}

export function sittingFacingText(facingDeg: number): SittingFacingText {
  const facing = resolveMountain(facingDeg)
  const sittingDeg = normalizeDeg(facingDeg + 180)
  const sitting = resolveMountain(sittingDeg)
  const offset = mountainOffset(sittingDeg, sitting)
  return {
    sitting: sitting.name,
    facing: facing.name,
    text: `坐${sitting.name}山 · 向${facing.name}`,
    deg: `${degreeText(sittingDeg)} / ${degreeText(facingDeg)}`,
    isJianXiang: Math.abs(offset) > 4.5,
    offset,
  }
}

export function offsetText(facingDeg: number): string {
  const facing = resolveMountain(facingDeg)
  const offset = angularDelta(facingDeg, facing.centerDeg)
  const sign = offset >= 0 ? '＋' : '－'
  return `偏离${facing.name}山中线 ${sign}${Math.abs(offset).toFixed(1)}°`
}

export function stabilityTone(stability: number): string {
  if (stability >= 92) return 'jade'
  if (stability >= 85) return 'gold'
  return 'accent'
}

export function verdictTone(verdict: string): string {
  if (verdict === 'SUITABLE') return 'info'
  if (verdict === 'ADJUST') return 'caution'
  if (verdict === 'AVOID') return 'danger'
  return ''
}

export function riskLabel(risk: string): string {
  if (risk === 'active') return '需重点安排'
  if (risk === 'attention') return '适度留意'
  return '平稳参考'
}

export function yearOfTimestamp(value: number): number {
  return new Date(value).getFullYear()
}
