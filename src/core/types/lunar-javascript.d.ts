declare module 'lunar-javascript' {
  export class Solar {
    static fromYmd(year: number, month: number, day: number): Solar
    static fromYmdHms(
      year: number,
      month: number,
      day: number,
      hour: number,
      minute: number,
      second: number
    ): Solar
    static fromDate(date: Date): Solar
    getYear(): number
    getMonth(): number
    getDay(): number
    getWeek(): number
    getWeekInChinese(): string
    getLunar(): Lunar
    toYmd(): string
    toYmdHms(): string
    next(days: number): Solar
    getJulianDay(): number
  }

  export class Lunar {
    static fromDate(date: Date): Lunar
    static fromYmd(year: number, month: number, day: number): Lunar
    static fromYmdHms(
      year: number,
      month: number,
      day: number,
      hour: number,
      minute: number,
      second: number
    ): Lunar
    getYear(): number
    getMonth(): number
    getDay(): number
    getYearInGanZhi(): string
    getYearInGanZhiExact(): string
    getYearInGanZhiByLiChun(): string
    getYearShengXiaoExact(): string
    getMonthInGanZhiExact(): string
    getMonthZhiExact(): string
    getDayInGanZhi(): string
    getDayGan(): string
    getDayZhi(): string
    getDayChong(): string
    getDayChongShengXiao(): string
    getDayChongDesc(): string
    getDaySha(): string
    getZhiXing(): string
    getDayYi(): string[]
    getDayJi(): string[]
    getJieQiTable(): Record<string, Solar>
    getYearNaYin(): string
    getDayNaYin(): string
    getDayTianShen(): string
    getDayTianShenType(): string
    getDayTianShenLuck(): string
    getDayJiShen(): string[]
    getDayXiongSha(): string[]
    getDayPositionXi(): string
    getDayPositionCai(): string
    getDayPositionFu(): string
    getDayPositionYangGui(): string
    getDayPositionYinGui(): string
    getDayPositionTai(): string
    getJieQi(): string
    getPengZuGan(): string
    getPengZuZhi(): string
    getDayXunKong(): string
    getTimes(): LunarTime[]
    getXiu(): string
    getXiuLuck(): string
    getXiuSong(): string
    getFestivals(): string[]
    getOtherFestivals(): string[]
    toString(): string
    getSolar(): Solar
  }

  export class LunarTime {
    getGanZhi(): string
    getZhi(): string
    getTianShen(): string
    getTianShenType(): string
    getTianShenLuck(): string
    getYi(): string[]
    getJi(): string[]
    getChongDesc(): string
  }

  export const LunarUtil: Record<string, unknown>
}
