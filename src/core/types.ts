import type { SchoolConflict, SchoolResult } from './zeri/types'

export type SceneMode = 'YANG' | 'YIN'
export type Gender = 'M' | 'F'
export type NorthType = 'MAGNETIC' | 'TRUE'
export type InputMethod = 'SENSOR' | 'MANUAL_DEG' | 'MANUAL_SHAN' | 'MAP_LINE'
export type YuanLong = 'TIAN' | 'DI' | 'REN'
export type PalaceId = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9
export type Period = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9
export type StarNumber = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9
export type FiveElement = '金' | '木' | '水' | '火' | '土'
export type BirthPrecision = 'DAY' | 'YEAR'
export type JianXiangKind = 'ZHENG' | 'TONG_GONG' | 'YIN_YANG_JIAN' | 'CHU_GUA'
export type ThingBehavior = 'FROM_YI' | 'YI_AND_JI' | 'FROM_JI' | 'ALL_JI'

export interface BirthInfo {
  date: string
  precision?: BirthPrecision
  beforeLiChun?: boolean
  gender?: Gender
}

export interface CompassReading {
  facingDeg: number
  mountDeg: number
  northType: NorthType
  declination: number
  stability: number
  inputMethod: InputMethod
  uncertainty: number
}

export interface YangMember {
  relation: string
  birth: BirthInfo
}

export interface YangData {
  propertyType: 'RESIDENTIAL' | 'OFFICE' | 'SHOP'
  members: YangMember[]
}

export interface YinPerson {
  label: string
  birth: BirthInfo
}

export interface YinTerrain {
  backSupport: 'STRONG' | 'FLAT' | 'HOLLOW'
  frontView: 'OPEN' | 'BLOCKED' | 'TILTED'
  leftRight: 'BALANCED' | 'LEFT_MISS' | 'RIGHT_MISS'
  waterFlow?: string
  notes?: string
}

export interface YinData {
  monumentType: 'SINGLE' | 'COUPLE' | 'ANCESTRAL'
  deceased: YinPerson[]
  descendants: YinPerson[]
  terrain: YinTerrain
  /** 入首龙（二十四山），用于正五行补龙 */
  incomingDragon?: string
}

export interface BaseArchive {
  id: string
  mode: SceneMode
  title: string
  eventYear: number
  period: Period
  reading: CompassReading
  createdAt: number
  updatedAt: number
  schemaVersion: number
  /**
   * 影响结论的输入的 SHA-256（算法见 `core/archive/schema.ts`）。
   *
   * 可选的原因：v1 档案没有这个字段，读取时必须先过 `migrateArchives()`。
   * 新建与更新时一律写入，不依赖它「可能不存在」。
   */
  inputHash?: string
  /** 生成该档案结论时的规则包版本；v1 迁移后为 `legacy-unrecorded` */
  rulePackVersion?: string
  /**
   * 报告锚点（YYYY-MM-DD）：择日预览的起点与月盘所属的月份都以它为准，
   * 而不是「打开报告的那一天」。否则同一份档案隔天打开结论会变，
   * 而 inputHash 没变，归因层只能判「不稳定」。
   *
   * 新建时写入当天；v3 之前的档案迁移时用 `createdAt` 的 UTC 日期回填（UTC 是为了
   * 迁移结果与机器时区无关——同一份档案在任何端读出来必须是同一个值）。
   * 它影响结论，所以参与 inputHash。
   */
  asOfDate?: string
}

export type Archive = BaseArchive & {
  yang?: YangData
  yin?: YinData
}

export interface PalaceChart {
  palace: PalaceId
  trigram: string
  direction: string
  element: FiveElement
  yun: number
  shan: number
  xiang: number
  annual?: number
  monthly?: number
}

export type PatternCode =
  | 'WANG_SHAN_WANG_XIANG'
  | 'SHANG_SHAN_XIA_SHUI'
  | 'SHUANG_XING_DAO_XIANG'
  | 'SHUANG_XING_DAO_SHAN'
  | 'NORMAL'

export interface XuanKongChart {
  period: number
  sitting: { shan: string; deg: number; palace: PalaceId }
  facing: { shan: string; deg: number; palace: PalaceId }
  palaces: PalaceChart[]
  pattern: PatternCode
  patternLabel: string
  patternTraditional: string
  flags: PatternCode[]
  isJianXiang: boolean
  tiGuaUsed: boolean
  jianKind: JianXiangKind
  warnings: string[]
}

export interface MingGuaInfo {
  gua: number
  name: string
  element: FiveElement
  group: 'EAST' | 'WEST'
  groupLabel: string
}

export interface BaZhaiStarInfo {
  code: string
  name: string
  element: FiveElement
  level: 'GOOD' | 'CAUTION'
  modernLabel: string
  suggestion: string
}

export interface BaZhaiPalace {
  palace: PalaceId
  direction: string
  star: BaZhaiStarInfo
}

export interface BaZhaiMemberResult {
  relation: string
  birth: BirthInfo
  effectiveYear: number
  mingGua: MingGuaInfo
  match: 'MATCH' | 'MISMATCH' | 'UNKNOWN'
  matchLabel: string
  palaces: BaZhaiPalace[]
}

export interface BaZhaiHouse {
  sittingShan: string
  gua: number
  name: string
  element: FiveElement
  group: 'EAST' | 'WEST'
  groupLabel: string
  palaces: BaZhaiPalace[]
}

export interface BaZhaiResult {
  house: BaZhaiHouse
  members: BaZhaiMemberResult[]
  notes: string[]
}

/**
 * 一百二十分金的分格：**只承载几何与历法事实**（度数、天干、六十甲子纳音）。
 *
 * 这里刻意没有「旺相／孤虚／空亡」之类的吉凶字段：该口径未经三源核验
 * （施工依据 v1.0 §6.8.1 与附录 E），不得进入数据结构——留在类型里，
 * 迟早会有人再把它接到界面上。要恢复必须先完成附录 E 的核验协议并以 fixture 固化。
 */
export interface FenJinSlot {
  index: number
  mount: string
  subIndex: 0 | 1 | 2 | 3 | 4
  ganZhi: string
  stem: string
  branch: string
  startDeg: number
  endDeg: number
  centerDeg: number
  /** 分格说明：天干 + 几何分格，中性描述 */
  slotNote: string
  nayin: string
  element: FiveElement
}

export interface FenJinResolution {
  slot: FenJinSlot
  offset: number
  isJianXiang: boolean
  warning: string | null
}

export type XianMingRelation =
  | 'SHAN_SHENG_MING'
  | 'BI_HE'
  | 'MING_KE_SHAN'
  | 'MING_SHENG_SHAN'
  | 'SHAN_KE_MING'

export type TabooSeverity = 'AVOID' | 'CAUTION'

export interface TabooHit {
  code: string
  name: string
  severity: TabooSeverity
  detail: string
}

export interface XianMingAnalysis {
  label: string
  birth: BirthInfo
  effectiveYear: number
  ganZhi: string
  nayin: string
  element: FiveElement
  mountElement: FiveElement
  mountRelation: XianMingRelation
  fenJinRelation: XianMingRelation
  tabooHits: TabooHit[]
  verdict: 'SUITABLE' | 'ADJUST' | 'AVOID' | 'UNKNOWN'
  summary: string
  notes: string[]
}

export interface YinMatchResult {
  fenJin: FenJinResolution
  deceased: XianMingAnalysis[]
  verdict: 'SUITABLE' | 'ADJUST' | 'AVOID' | 'UNKNOWN'
  summary: string
  suggestedSlots: FenJinSlot[]
  notes: string[]
}

export interface FlyingChart {
  centerStar: number
  palaces: Array<{ palace: PalaceId; star: number }>
  byPalace: Record<PalaceId, number>
}

export interface AnnualInfo {
  year: number
  yearGanZhi: string
  centerStar: number
  chart: FlyingChart
  taiSui: string
  suiPo: string
  sanShaMountains: string[]
  sanShaDirection: string
}

export interface MonthlyInfo {
  year: number
  monthIndex: number
  monthGanZhi: string
  centerStar: number
  chart: FlyingChart
}

export type ZeRiCategory =
  | 'YANG_RUZHAI'
  | 'YANG_DONGTU'
  | 'YANG_JIAQU'
  | 'YANG_KAISHI'
  | 'YIN_ANZANG'
  | 'YIN_XIUFEN'

/**
 * 三煞硬排除的层级（六条规则：年/月/日/时占山 + 日课相犯两条）。
 * - 'year'：只硬排年家占山，其余降为提示；
 * - 'year_month'（默认）：兴工与阴宅用事中硬排年家、月家占山，日/时占山与相犯两条作提示；
 * - 'all'：四家占山与两条相犯全部硬排。
 * 纯入宅不兴工，占山各条本就不参与判定，层级只影响相犯两条。
 */
export type SanShaLevel = 'year' | 'year_month' | 'all'

export interface ZeRiQuery {
  startDate: string
  daysCount: number
  category: ZeRiCategory
  mountShan: string
  familyBirths: BirthInfo[]
  deceasedBirths?: BirthInfo[]
  chongSangMode?: 'reject' | 'warn'
  sanShaMode?: SanShaLevel
  jinShenMode?: 'reject' | 'warn'
  folkMode?: 'reject' | 'warn'
  maxResults?: number
  /** 坐山实际线度，用于玄空大卦抽爻与三煞占山 */
  sittingDeg?: number
  /** 用事年份（决定玄空大卦元运） */
  eventYear?: number
  /** 阴宅入首龙（二十四山） */
  incomingDragon?: string | null
  /** 入宅是否伴随动土、修造、安门 */
  includesConstruction?: boolean
  /** 日课时支 */
  hourBranch?: string | null
  /** 只保留黄道日 */
  onlyHuangDao?: boolean
  /** 排除二十八宿判凶之日 */
  avoidXiuXiong?: boolean
  /** 玄空大卦爻位排列口径 */
  yaoOrder?: 'ASC' | 'DESC'
  /** 当地经度，用于真太阳时校正 */
  longitudeDeg?: number | null
}

export interface ZeRiRejection {
  name: string
  count: number
  /** 该大煞是否可被人工复核后放宽 */
  review: boolean
  source: string
  /** 其中值煞贡/直星/人专仍被排除的天数（吉星不解大煞的可见证据） */
  luckyStarDays: number
  /** 样例：日期 · 值星 */
  luckyStarSamples: string[]
  /** 为什么会被大面积排除的解释文案（两端共用） */
  guidance: string
}

export interface ZeRiItem {
  solarDate: string
  weekDay: string
  lunarDate: string
  ganZhi: string
  zhiXing: string
  huangDao: boolean
  dayYi: string[]
  dayJi: string[]
  chong: string
  chongShengXiao: string
  sha: string
  matchedYi: string[]
  warnings: string[]
  reasons: string[]
  jiShen: string[]
  xiongSha: string[]
  xiejiYi: string[]
  xiejiJi: string[]
  level: number
  levelName: string
  behavior: ThingBehavior
  xiu: string
  xiuLuck: string
  tianShen: string
  pengZu: string[]
  positions: AuspiciousPositions
  luckyHours: string[]
  score: number
  /** 五派并列原始输出（仲裁层不合并） */
  schools: SchoolResult[]
  /** 流派之间的分歧，只标记不裁决 */
  conflicts: SchoolConflict[]
  consensus: 'favorable' | 'mixed' | 'unfavorable' | 'rejected' | 'insufficient'
  consensusFavorable: boolean
  /** 被产品端降级为提示的大煞 */
  dashaWarnings: string[]
}

export interface AuspiciousPositions {
  xi: string
  cai: string
  fu: string
  yangGui: string
  yinGui: string
}

export interface ZeRiResult {
  items: ZeRiItem[]
  /** 完整时间窗内实际扫描的天数，不受展示条数上限影响 */
  scanned: number
  rejected: number
  /** 通过前置层、但被通书宜忌或附加条件跳过的天数 */
  unmatched: number
  /** 通过全部筛选条件、可进入候选池的天数 */
  eligible: number
  /** 候选池是否大于本次展示条数 */
  truncated: boolean
  /** 以下三项把 unmatched 拆开，避免界面把不同原因混成一个数 */
  excludedByAlmanac: number
  excludedByHuangDao: number
  excludedByXiu: number
  rejections: ZeRiRejection[]
  notes: string[]
}

export interface ReportWarning {
  code: string
  level: 'INFO' | 'CAUTION' | 'DANGER'
  text: string
}

export interface ShuangXingContent {
  id: string
  combo: { shan: number; xiang: number }
  title: string
  classic: { source: string; paraphrase: string }
  analysis: string
  actions: string[]
  yin: { analysis: string; actions: string[] }
  riskLevel: 'balanced' | 'attention' | 'active'
  reviewStatus: string
  version: number
}

export interface PalaceInsight {
  palace: PalaceId
  comboKey: string
  title: string
  analysis: string
  actions: string[]
  riskLevel: string
  locked: boolean
}

export interface Report {
  archiveId: string
  mode: SceneMode
  chart: XuanKongChart
  annual: AnnualInfo
  monthly?: MonthlyInfo
  bazhai?: BaZhaiResult
  fenjin?: FenJinResolution
  yinMatch?: YinMatchResult
  zeri: ZeRiItem[]
  insights: PalaceInsight[]
  warnings: ReportWarning[]
  previewPalaces: PalaceId[]
  contentVersion: string
  generatedAt: number
}

export interface ContentBundle {
  version: string
  shuangxing: ShuangXingContent[]
}
