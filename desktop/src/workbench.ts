import { reactive } from 'vue'
import type { BirthInfo, Gender, SanShaLevel, ZeRiCategory, ZeRiQuery } from '@core/types'
import type { DayEvaluationInput } from '@core/zeri/evaluate'

export interface DayCell {
  date: string
  day: number
  lead: boolean
  status: 'candidate' | 'rejected' | 'unmatched' | 'outside'
  ganZhi: string
  zhiXing: string
  xiu: string
  luckyStar: boolean
  reasons: string[]
  consensus: string
}

export interface PersonRow {
  label: string
  date: string
  gender: Gender
}

export interface WorkbenchState {
  category: ZeRiCategory
  mountShan: string
  sittingDeg: number
  startDate: string
  daysCount: number
  hourBranch: string
  incomingDragon: string
  subjects: PersonRow[]
  deceased: PersonRow[]
  sanShaMode: SanShaLevel
  chongSangMode: 'reject' | 'warn'
  jinShenMode: 'reject' | 'warn'
  folkMode: 'reject' | 'warn'
  /** 入宅是否伴随动土、修造、安门 */
  includesConstruction: boolean
  onlyHuangDao: boolean
  avoidXiuXiong: boolean
  yaoOrder: 'ASC' | 'DESC'
}

function today(): string {
  const now = new Date()
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

export function createState(): WorkbenchState {
  return reactive({
    category: 'YANG_RUZHAI',
    mountShan: '子',
    sittingDeg: 0,
    startDate: today(),
    daysCount: 90,
    hourBranch: '',
    incomingDragon: '',
    subjects: [{ label: '主命1', date: '', gender: 'M' }],
    deceased: [],
    sanShaMode: 'year_month',
    chongSangMode: 'warn',
    jinShenMode: 'reject',
    folkMode: 'reject',
    includesConstruction: false,
    onlyHuangDao: false,
    avoidXiuXiong: false,
    yaoOrder: 'ASC',
  })
}

function births(rows: PersonRow[]): BirthInfo[] {
  return rows.filter((row) => row.date).map((row) => ({ date: row.date, gender: row.gender }))
}

/** 元运取扫描起始年的立春归属年；跨年扫描时以起始年为准。 */
function eventYearOf(state: WorkbenchState): number {
  return Number(state.startDate.slice(0, 4))
}

export function toQuery(state: WorkbenchState): ZeRiQuery {
  return {
    startDate: state.startDate,
    daysCount: state.daysCount,
    category: state.category,
    mountShan: state.mountShan,
    familyBirths: births(state.subjects),
    deceasedBirths: births(state.deceased),
    maxResults: 60,
    sittingDeg: state.sittingDeg,
    eventYear: eventYearOf(state),
    incomingDragon: state.incomingDragon || null,
    hourBranch: state.hourBranch || null,
    sanShaMode: state.sanShaMode,
    chongSangMode: state.chongSangMode,
    jinShenMode: state.jinShenMode,
    includesConstruction: state.includesConstruction,
    folkMode: state.folkMode,
    onlyHuangDao: state.onlyHuangDao,
    avoidXiuXiong: state.avoidXiuXiong,
    yaoOrder: state.yaoOrder,
  }
}

export function toEvaluationInput(
  state: WorkbenchState,
  date: string,
): Omit<DayEvaluationInput, 'date'> {
  return {
    category: state.category,
    mountShan: state.mountShan,
    sittingDeg: state.sittingDeg,
    eventYear: Number(date.slice(0, 4)) || eventYearOf(state),
    incomingDragon: state.incomingDragon || null,
    subjects: births(state.subjects),
    deceased: births(state.deceased),
    hourBranch: state.hourBranch || null,
    sanShaPolicy: state.sanShaMode,
    chongSangPolicy: state.chongSangMode,
    jinShenPolicy: state.jinShenMode,
    includesConstruction: state.includesConstruction,
    folkPolicy: state.folkMode,
    yaoOrder: state.yaoOrder,
  }
}
