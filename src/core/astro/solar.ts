/**
 * 太阳视位置（Meeus《Astronomical Algorithms》第 25 章截断式）。
 * 精度门槛由 tests/astro-solar.test.ts 用 Swiss Ephemeris 逐日校验，
 * 达不到 0.01° 就不允许天星包声明 FULL。
 */

export interface SolarPosition {
  julianDay: number
  /**  geometrical 日心视黄经的反向：太阳地心视黄经（含章动与光行差），度 */
  apparentLongitude: number
  /** 太阳平黄经，度 */
  meanLongitude: number
  /** 太阳真近点角，度 */
  meanAnomaly: number
  /** 均时差，分钟 */
  equationOfTimeMinutes: number
  /** 黄赤交角，度 */
  obliquity: number
}

const RAD = Math.PI / 180

function norm360(value: number): number {
  const v = value % 360
  return v < 0 ? v + 360 : v
}

/** UTC 日期时间 → 儒略日（含小数）。 */
export function julianDayUTC(
  year: number,
  month: number,
  day: number,
  hours = 0,
  minutes = 0,
  seconds = 0
): number {
  let y = year
  let m = month
  if (m <= 2) {
    y -= 1
    m += 12
  }
  const a = Math.floor(y / 100)
  const b = 2 - a + Math.floor(a / 4)
  const dayFraction = (hours + minutes / 60 + seconds / 3600) / 24
  return (
    Math.floor(365.25 * (y + 4716)) +
    Math.floor(30.6001 * (m + 1)) +
    day +
    dayFraction +
    b -
    1524.5
  )
}

/** 视黄经计算：date 为 YYYY-MM-DD，utHours 为当日世界时小时。 */
export function solarLongitude(date: string, utHours = 4): SolarPosition {
  const [year, month, day] = date.split('-').map((item) => Number(item))
  if (!year || !month || !day) throw new Error(`无效日期: ${date}`)
  const jd = julianDayUTC(year, month, day, utHours)
  const T = (jd - 2451545) / 36525

  const meanLongitude = norm360(
    280.4664567 + 36000.76983 * T + 0.0003032 * T * T
  )
  const meanAnomaly = norm360(
    357.52911 + 35999.05029 * T - 0.0001537 * T * T
  )
  const omega = norm360(125.04 - 1934.136 * T)
  const eccentricity = 0.016708634 - 0.000042037 * T - 0.0000001267 * T * T

  // 日方中心（equation of center）取到 e 的三阶，误差量级约 1e-5 度
  const centerRadians =
    (2 * eccentricity - eccentricity ** 3 / 4) * Math.sin(meanAnomaly * RAD) +
    eccentricity ** 2 * Math.sin(2 * meanAnomaly * RAD) +
    (eccentricity ** 3 / 8) * Math.sin(3 * meanAnomaly * RAD)
  const centerDegrees = (centerRadians * 180) / Math.PI

  const trueLongitude = norm360(meanLongitude + centerDegrees)

  const apparentLongitude = norm360(
    trueLongitude - 0.00569 - 0.00477 * Math.sin(omega * RAD)
  )

  const obliquity =
    23.439291 -
    0.0130042 * T -
    1.64e-7 * T * T +
    3.01e-7 * T * T * T +
    0.00256 * Math.cos(omega * RAD)

  // 均时差（Meeus 第 28 章低精度式）
  const y = Math.tan((obliquity / 2) * RAD) ** 2
  const equationRadians =
    y * Math.sin(2 * meanLongitude * RAD) -
    2 * eccentricity * Math.sin(meanAnomaly * RAD) +
    4 * eccentricity * y * Math.sin(meanAnomaly * RAD) * Math.cos(2 * meanLongitude * RAD) -
    0.5 * y * y * Math.sin(4 * meanLongitude * RAD) -
    1.25 * eccentricity * eccentricity * Math.sin(2 * meanAnomaly * RAD)
  const equationOfTimeMinutes = ((equationRadians * 180) / Math.PI) * 4

  return {
    julianDay: jd,
    apparentLongitude,
    meanLongitude,
    meanAnomaly,
    equationOfTimeMinutes,
    obliquity,
  }
}

/**
 * 太阳黄经映射到二十八宿（宿度表按年份做岁差校正后传入）。
 * 返回宿名与该宿内的相对度数。
 */
export function longitudeToXiu(
  longitude: number,
  bounds: Array<{ name: string; start: number }>
): { name: string; offset: number; span: number } | null {
  if (!bounds.length) return null
  const value = norm360(longitude)
  for (let i = 0; i < bounds.length; i++) {
    const start = bounds[i].start
    const next = bounds[(i + 1) % bounds.length].start
    const span = norm360(next - start) || 360
    const offset = norm360(value - start)
    if (offset < span) {
      return { name: bounds[i].name, offset, span }
    }
  }
  return null
}
