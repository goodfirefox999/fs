import { mountainOffset, normalizeDeg, resolveMountain } from '../constants/shan24'

export interface SamplerResult {
  smoothDeg: number
  stability: number
  isLocked: boolean
  samples: number
}

export function circularMean(samples: number[]): number {
  if (!samples.length) return 0
  let sinSum = 0
  let cosSum = 0
  for (const deg of samples) {
    const rad = (normalizeDeg(deg) * Math.PI) / 180
    sinSum += Math.sin(rad)
    cosSum += Math.cos(rad)
  }
  const mean = Math.atan2(sinSum / samples.length, cosSum / samples.length)
  return normalizeDeg((mean * 180) / Math.PI)
}

export function circularConcentration(samples: number[]): number {
  if (!samples.length) return 0
  let sinSum = 0
  let cosSum = 0
  for (const deg of samples) {
    const rad = (normalizeDeg(deg) * Math.PI) / 180
    sinSum += Math.sin(rad)
    cosSum += Math.cos(rad)
  }
  return Math.sqrt((sinSum / samples.length) ** 2 + (cosSum / samples.length) ** 2)
}

/**
 * 圆中位数：使「到各样本的圆弧角距之和」最小的那个样本点。
 *
 * 不能按「离均值的距离」排序后取中间——那不是角度顺序：[10, 12, 14, 16] 会选出
 * 离均值最远的 10，中位数就成了离群值。用角距之和还能在对跱点平局时
 * 靠多数一方取胜（[10, 10, 10, 190] → 10）。
 */
export function circularMedian(samples: number[]): number {
  if (!samples.length) return 0
  let best = samples[0]
  let bestDeviation = Number.POSITIVE_INFINITY
  for (const candidate of samples) {
    let deviation = 0
    for (const other of samples) {
      deviation += Math.abs(((other - candidate + 540) % 360) - 180)
    }
    if (deviation < bestDeviation) {
      bestDeviation = deviation
      best = candidate
    }
  }
  return normalizeDeg(best)
}

export class CompassSampler {
  private buffer: number[] = []

  constructor(private readonly windowSize = 20) {}

  push(deg: number): SamplerResult {
    this.buffer.push(normalizeDeg(deg))
    if (this.buffer.length > this.windowSize) this.buffer.shift()
    const smoothDeg = circularMean(this.buffer)
    const concentration = circularConcentration(this.buffer)
    const stability = Math.round(Math.pow(Math.max(0, concentration), 8) * 100)
    return {
      smoothDeg: Number(smoothDeg.toFixed(1)),
      stability,
      isLocked: this.buffer.length >= this.windowSize && stability >= 92,
      samples: this.buffer.length,
    }
  }

  reset(): void {
    this.buffer = []
  }

  get size(): number {
    return this.buffer.length
  }
}

export function estimateMapBearingUncertainty(baselineMeters: number, gpsErrorMeters = 5): number {
  if (baselineMeters <= 0) return 90
  const angle = (Math.atan2(2 * gpsErrorMeters, baselineMeters) * 180) / Math.PI
  return Math.min(90, Number(angle.toFixed(1)))
}

export function initialBearing(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const toRad = (v: number) => (v * Math.PI) / 180
  const toDeg = (v: number) => (v * 180) / Math.PI
  const phi1 = toRad(lat1)
  const phi2 = toRad(lat2)
  const deltaLon = toRad(lon2 - lon1)
  const y = Math.sin(deltaLon) * Math.cos(phi2)
  const x =
    Math.cos(phi1) * Math.sin(phi2) -
    Math.sin(phi1) * Math.cos(phi2) * Math.cos(deltaLon)
  return normalizeDeg(toDeg(Math.atan2(y, x)))
}

export interface CityDeclination {
  city: string
  lat: number
  lon: number
  declination: number
}

export const CITY_DECLINATIONS: CityDeclination[] = [
  { city: '北京', lat: 39.9, lon: 116.4, declination: -7.3 },
  { city: '天津', lat: 39.1, lon: 117.2, declination: -7.0 },
  { city: '上海', lat: 31.2, lon: 121.5, declination: -5.5 },
  { city: '重庆', lat: 29.6, lon: 106.5, declination: -1.7 },
  { city: '广州', lat: 23.1, lon: 113.3, declination: -2.7 },
  { city: '深圳', lat: 22.5, lon: 114.1, declination: -2.8 },
  { city: '杭州', lat: 30.3, lon: 120.2, declination: -5.2 },
  { city: '南京', lat: 32.1, lon: 118.8, declination: -5.7 },
  { city: '武汉', lat: 30.6, lon: 114.3, declination: -4.6 },
  { city: '成都', lat: 30.7, lon: 104.1, declination: -1.5 },
  { city: '西安', lat: 34.3, lon: 108.9, declination: -3.6 },
  { city: '沈阳', lat: 41.8, lon: 123.4, declination: -8.5 },
  { city: '哈尔滨', lat: 45.8, lon: 126.5, declination: -9.8 },
  { city: '长春', lat: 43.8, lon: 125.3, declination: -9.0 },
  { city: '济南', lat: 36.7, lon: 117.0, declination: -6.4 },
  { city: '青岛', lat: 36.1, lon: 120.4, declination: -6.3 },
  { city: '郑州', lat: 34.8, lon: 113.7, declination: -5.5 },
  { city: '长沙', lat: 28.2, lon: 113.0, declination: -3.9 },
  { city: '南昌', lat: 28.7, lon: 115.9, declination: -4.6 },
  { city: '福州', lat: 26.1, lon: 119.3, declination: -4.2 },
  { city: '厦门', lat: 24.5, lon: 118.1, declination: -3.8 },
  { city: '昆明', lat: 25.0, lon: 102.7, declination: -1.2 },
  { city: '贵阳', lat: 26.6, lon: 106.7, declination: -1.9 },
  { city: '南宁', lat: 22.8, lon: 108.3, declination: -2.2 },
  { city: '海口', lat: 20.0, lon: 110.3, declination: -1.8 },
  { city: '兰州', lat: 36.1, lon: 103.8, declination: -2.8 },
  { city: '西宁', lat: 36.6, lon: 101.8, declination: -1.7 },
  { city: '银川', lat: 38.5, lon: 106.2, declination: -3.4 },
  { city: '乌鲁木齐', lat: 43.8, lon: 87.6, declination: 3.4 },
  { city: '拉萨', lat: 29.7, lon: 91.1, declination: 0.4 },
  { city: '呼和浩特', lat: 40.8, lon: 111.7, declination: -6.3 },
  { city: '太原', lat: 37.9, lon: 112.5, declination: -5.5 },
  { city: '石家庄', lat: 38.0, lon: 114.5, declination: -6.1 },
  { city: '合肥', lat: 31.8, lon: 117.2, declination: -5.3 },
  { city: '苏州', lat: 31.3, lon: 120.6, declination: -5.4 },
  { city: '宁波', lat: 29.9, lon: 121.5, declination: -5.1 },
  { city: '温州', lat: 28.0, lon: 120.7, declination: -4.6 },
  { city: '珠海', lat: 22.3, lon: 113.6, declination: -2.9 },
  { city: '三亚', lat: 18.3, lon: 109.5, declination: -1.5 },
  { city: '香港', lat: 22.3, lon: 114.2, declination: -2.6 },
  { city: '澳门', lat: 22.2, lon: 113.5, declination: -2.7 },
  { city: '台北', lat: 25.0, lon: 121.5, declination: -3.5 },
]

export function nearestCity(lat: number, lon: number): CityDeclination {
  let best = CITY_DECLINATIONS[0]
  let bestScore = Number.POSITIVE_INFINITY
  for (const city of CITY_DECLINATIONS) {
    const score = (city.lat - lat) ** 2 + (city.lon - lon) ** 2
    if (score < bestScore) {
      best = city
      bestScore = score
    }
  }
  return best
}

export function mountainSnapshot(deg: number) {
  const mountain = resolveMountain(deg)
  const offset = mountainOffset(deg, mountain)
  return {
    mountain,
    offset,
    isJianXiang: Math.abs(offset) > 4.5,
    nearBoundary: Math.abs(Math.abs(offset) - 7.5) <= 1,
  }
}

/**
 * 先四舍五入到 0.1° 再取模：359.96° 必须显示 0.0°，
 * 不能先格式化再让它四舍五入成「360.0°」。
 */
export function formatDegree(deg: number): string {
  const tenths = Math.round(normalizeDeg(deg) * 10) % 3600
  return `${(tenths / 10).toFixed(1)}°`
}
