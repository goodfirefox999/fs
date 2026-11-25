/**
 * 桌面工作台的档案模型。
 *
 * 与小程序侧的 `Archive`（`src/core/types.ts`）是**两套数据**，不要混用：
 * - 小程序档案是「一处房产 / 一座纪念地」的建档数据（坐向、户型、命主）；
 * - 桌面档案是「一次择日工作台会话」的快照（用事、坐向、扫描窗口、严格度开关）。
 *
 * 两者共用的只有底层能力：规范化 JSON、SHA-256、diff 归因（都来自 `@core/archive`）。
 */

import { canonicalize, sha256Hex, type EvaluationSnapshot } from '@core/archive'
import { SHAN_NAMES } from '@core/constants/shan24'
import { ZHI } from '@core/constants/nayin60'
import { RULE_PACK_VERSION } from '@core/zeri/version'
import { createState, type PersonRow, type WorkbenchState } from '../workbench'

/** 当前工作台档案版本。字段增删一律升位并补迁移，不偷偷加可选字段。 */
export const WORKBENCH_SCHEMA_VERSION = 1

export interface WorkbenchArchive {
  id: string
  schemaVersion: number
  title: string
  createdAt: number
  updatedAt: number
  /** 影响结论的输入哈希（算法见 `workbenchInputHash`） */
  inputHash: string
  /** 生成该档案时使用的规则包版本 */
  rulePackVersion: string
  /** 完整工作台输入，用于恢复现场 */
  state: WorkbenchState
  /** 最近一次评估摘要，diff 归因的对比基准；未评估过则缺省 */
  lastEvaluation?: EvaluationSnapshot & { evaluatedAt: number }
}

/**
 * 参与 inputHash 的字段。
 *
 * 包含扫描窗口（`startDate` / `daysCount`）：hash 标识的是「这一次查询」，
 * 窗口不同就无法直接对比两次结果，所以必须进哈希。
 * 不包含 `id` / `title` / 时间戳：改个名字不该让 hash 变。
 */
export function workbenchInputPayload(state: WorkbenchState): Record<string, unknown> {
  return {
    category: state.category,
    mountShan: state.mountShan,
    sittingDeg: state.sittingDeg,
    startDate: state.startDate,
    daysCount: state.daysCount,
    hourBranch: state.hourBranch,
    incomingDragon: state.incomingDragon,
    subjects: state.subjects,
    deceased: state.deceased,
    sanShaMode: state.sanShaMode,
    chongSangMode: state.chongSangMode,
    jinShenMode: state.jinShenMode,
    folkMode: state.folkMode,
    includesConstruction: state.includesConstruction,
    onlyHuangDao: state.onlyHuangDao,
    avoidXiuXiong: state.avoidXiuXiong,
    yaoOrder: state.yaoOrder,
  }
}

/**
 * 工作台输入哈希。
 *
 * 与 `@core/archive` 的 `inputHashOf()` **共用算法但不共用语义**：两边都是
 * `sha256(canonicalize(payload))`，但 payload 不同——那边是房产档案的
 * `{ mode, eventYear, reading, yang, yin }`，这边是一次择日查询的完整工作台输入。
 * 两个哈希互不可校验、不可混用；未来做规则包升级 diff 时，只能用同一边自己的基准。
 */
export function workbenchInputHash(state: WorkbenchState): string {
  return sha256Hex(canonicalize(workbenchInputPayload(state)))
}

const CATEGORY_LABELS: Record<string, string> = {
  YANG_RUZHAI: '入宅安床',
  YANG_DONGTU: '动土修造',
  YANG_JIAQU: '嫁娶订盟',
  YANG_KAISHI: '开市交易',
  YIN_ANZANG: '安葬破土',
  YIN_XIUFEN: '修坟立碑',
}

export function defaultTitle(state: WorkbenchState): string {
  const category = CATEGORY_LABELS[state.category] ?? state.category
  return `${category} · ${state.mountShan}山 · ${state.startDate.slice(0, 7)}`
}

export function makeArchiveId(): string {
  return `w_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`
}

/** JSON 深拷贝：`state` 是 Vue reactive 代理，structuredClone 会抛 DataCloneError。 */
export function cloneState(state: WorkbenchState): WorkbenchState {
  return JSON.parse(JSON.stringify(state)) as WorkbenchState
}

export function createArchive(state: WorkbenchState, title?: string): WorkbenchArchive {
  const now = Date.now()
  const snapshot = cloneState(state)
  return {
    id: makeArchiveId(),
    schemaVersion: WORKBENCH_SCHEMA_VERSION,
    title: title?.trim() || defaultTitle(snapshot),
    createdAt: now,
    updatedAt: now,
    inputHash: workbenchInputHash(snapshot),
    rulePackVersion: RULE_PACK_VERSION,
    state: snapshot,
  }
}

export class WorkbenchArchiveError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'WorkbenchArchiveError'
  }
}

const CATEGORIES: WorkbenchState['category'][] = [
  'YANG_RUZHAI',
  'YANG_DONGTU',
  'YANG_JIAQU',
  'YANG_KAISHI',
  'YIN_ANZANG',
  'YIN_XIUFEN',
]
const SAN_SHA_MODES: WorkbenchState['sanShaMode'][] = ['year', 'year_month', 'all']
const POLICY_MODES: Array<'reject' | 'warn'> = ['reject', 'warn']
const GENDERS: PersonRow['gender'][] = ['M', 'F']

function asRecord(raw: unknown, label: string): Record<string, unknown> {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new WorkbenchArchiveError(`${label}必须是对象`)
  }
  return raw as Record<string, unknown>
}

function pickEnum<T extends string>(
  value: unknown,
  allowed: readonly T[],
  fallback: T,
  label: string,
): T {
  if (value === undefined || value === null) return fallback
  if (typeof value === 'string' && (allowed as readonly string[]).includes(value)) return value as T
  throw new WorkbenchArchiveError(`${label}非法：${JSON.stringify(value)}`)
}

function pickBool(value: unknown, fallback: boolean, label: string): boolean {
  if (value === undefined || value === null) return fallback
  if (typeof value !== 'boolean') throw new WorkbenchArchiveError(`${label}必须是布尔值`)
  return value
}

function pickDate(value: unknown, fallback: string, label: string): string {
  if (value === undefined || value === null || value === '') return fallback
  if (typeof value !== 'string') throw new WorkbenchArchiveError(`${label}必须是字符串`)
  const text = value.trim()
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text)
  if (!match) throw new WorkbenchArchiveError(`${label}格式应为 YYYY-MM-DD：${text}`)
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const date = new Date(Date.UTC(year, month - 1, day))
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
    throw new WorkbenchArchiveError(`${label}不是有效日期：${text}`)
  }
  return text
}

function normalizePerson(raw: unknown, index: number, prefix: string): PersonRow {
  const record = asRecord(raw, `${prefix}第 ${index + 1} 行`)
  const label =
    typeof record.label === 'string' && record.label.trim()
      ? record.label.trim()
      : `${prefix}${index + 1}`
  return {
    label,
    date: pickDate(record.date, '', `${prefix}第 ${index + 1} 行生日`),
    gender: pickEnum(record.gender, GENDERS, 'M', `${prefix}第 ${index + 1} 行性别`),
  }
}

function normalizePeople(raw: unknown, prefix: string): PersonRow[] {
  if (raw === undefined || raw === null) return []
  if (!Array.isArray(raw)) throw new WorkbenchArchiveError(`${prefix}必须是数组`)
  return raw.map((item, index) => normalizePerson(item, index, prefix))
}

function normalizeDeg(value: number): number {
  const normalized = ((value % 360) + 360) % 360
  const rounded = Math.round(normalized * 10) / 10
  return rounded === 360 ? 0 : rounded
}

/**
 * 外部 JSON（导入文件、手工改过的存档）进入工作台前的最后一道闸门。
 * 缺省字段按当前默认值补齐；类型或取值不合法直接报错，不把畸形数据灌进界面。
 */
export function normalizeWorkbenchState(raw: unknown): WorkbenchState {
  const record = asRecord(raw, '档案 state')
  const defaults = createState()

  const sittingDegRaw = record.sittingDeg === undefined ? defaults.sittingDeg : record.sittingDeg
  if (typeof sittingDegRaw !== 'number' || !Number.isFinite(sittingDegRaw)) {
    throw new WorkbenchArchiveError('坐山线度必须是有限数字')
  }
  const daysCountRaw = record.daysCount === undefined ? defaults.daysCount : record.daysCount
  if (
    typeof daysCountRaw !== 'number' ||
    !Number.isInteger(daysCountRaw) ||
    daysCountRaw < 1 ||
    daysCountRaw > 366
  ) {
    throw new WorkbenchArchiveError(`扫描天数非法：${JSON.stringify(daysCountRaw)}`)
  }
  const hourBranch = record.hourBranch === undefined ? defaults.hourBranch : record.hourBranch
  if (
    typeof hourBranch !== 'string' ||
    (hourBranch !== '' && !(ZHI as readonly string[]).includes(hourBranch))
  ) {
    throw new WorkbenchArchiveError(`日课时支非法：${JSON.stringify(hourBranch)}`)
  }
  const incomingDragon =
    record.incomingDragon === undefined ? defaults.incomingDragon : record.incomingDragon
  if (
    typeof incomingDragon !== 'string' ||
    (incomingDragon !== '' && !SHAN_NAMES.includes(incomingDragon))
  ) {
    throw new WorkbenchArchiveError(`入首龙非法：${JSON.stringify(incomingDragon)}`)
  }

  return {
    category: pickEnum(record.category, CATEGORIES, defaults.category, '用事类型'),
    mountShan: pickEnum(record.mountShan, SHAN_NAMES, defaults.mountShan, '坐山'),
    sittingDeg: normalizeDeg(sittingDegRaw),
    startDate: pickDate(record.startDate, defaults.startDate, '起始日期'),
    daysCount: daysCountRaw,
    hourBranch,
    incomingDragon,
    subjects: normalizePeople(record.subjects, '主命'),
    deceased: normalizePeople(record.deceased, '仙命'),
    sanShaMode: pickEnum(record.sanShaMode, SAN_SHA_MODES, defaults.sanShaMode, '三煞口径'),
    chongSangMode: pickEnum(
      record.chongSangMode,
      POLICY_MODES,
      defaults.chongSangMode,
      '重丧口径',
    ),
    jinShenMode: pickEnum(record.jinShenMode, POLICY_MODES, defaults.jinShenMode, '金神口径'),
    folkMode: pickEnum(record.folkMode, POLICY_MODES, defaults.folkMode, '民俗口径'),
    includesConstruction: pickBool(
      record.includesConstruction,
      defaults.includesConstruction,
      '伴随动工',
    ),
    onlyHuangDao: pickBool(record.onlyHuangDao, defaults.onlyHuangDao, '只看黄道'),
    avoidXiuXiong: pickBool(record.avoidXiuXiong, defaults.avoidXiuXiong, '避开宿凶'),
    yaoOrder: pickEnum(record.yaoOrder, ['ASC', 'DESC'] as const, defaults.yaoOrder, '爻位顺序'),
  }
}

function normalizeSnapshot(
  raw: unknown,
): (EvaluationSnapshot & { evaluatedAt: number }) | undefined {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return undefined
  const record = raw as Record<string, unknown>
  if (typeof record.inputHash !== 'string' || !record.inputHash) return undefined
  if (typeof record.rulePackVersion !== 'string' || !record.rulePackVersion) return undefined
  if (typeof record.verdict !== 'string' || !record.verdict) return undefined
  return {
    inputHash: record.inputHash,
    rulePackVersion: record.rulePackVersion,
    verdict: record.verdict,
    excludedDays:
      typeof record.excludedDays === 'number' && Number.isFinite(record.excludedDays)
        ? record.excludedDays
        : undefined,
    totalDays:
      typeof record.totalDays === 'number' && Number.isFinite(record.totalDays)
        ? record.totalDays
        : undefined,
    evaluatedAt:
      typeof record.evaluatedAt === 'number' && Number.isFinite(record.evaluatedAt)
        ? record.evaluatedAt
        : Date.now(),
  }
}

/**
 * 单条迁移 / 校验。
 *
 * 当前只有 v1，没有迁移步骤；但版本检查必须现在就写：
 * 将来加 v2 时，旧程序打开新档案要能明确报错，而不是把新字段当不存在。
 */
export function migrateWorkbenchArchive(raw: unknown): WorkbenchArchive {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    throw new WorkbenchArchiveError('档案必须是对象')
  }
  const record = raw as Record<string, unknown>

  const version = record.schemaVersion
  if (version === undefined || version === null) {
    throw new WorkbenchArchiveError('档案缺少 schemaVersion，无法判断版本')
  }
  if (typeof version !== 'number' || !Number.isInteger(version) || version < 1) {
    throw new WorkbenchArchiveError(`schemaVersion 非法：${JSON.stringify(version)}`)
  }
  if (version > WORKBENCH_SCHEMA_VERSION) {
    throw new WorkbenchArchiveError(
      `档案来自更高版本 schemaVersion=${version}（当前支持 ${WORKBENCH_SCHEMA_VERSION}），请升级程序`,
    )
  }
  if (!record.state || typeof record.state !== 'object' || Array.isArray(record.state)) {
    throw new WorkbenchArchiveError('档案缺少 state')
  }

  // v1 无需变换；但外部导入的 JSON 必须过结构校验，缺省元数据按当前版本补齐
  const state = normalizeWorkbenchState(record.state)
  const id =
    typeof record.id === 'string' && /^[\w-]{1,64}$/.test(record.id) ? record.id : makeArchiveId()
  const title =
    typeof record.title === 'string' && record.title.trim()
      ? record.title.trim()
      : defaultTitle(state)
  const createdAt =
    typeof record.createdAt === 'number' && Number.isFinite(record.createdAt)
      ? record.createdAt
      : Date.now()
  const updatedAt =
    typeof record.updatedAt === 'number' && Number.isFinite(record.updatedAt)
      ? record.updatedAt
      : Date.now()
  // 哈希只描述 state：归一化可能补齐了缺省字段，旧哈希已不对应当前输入，
  // 保留它会让 isDirty 永远为真、diff 基准错位，所以一律重算。
  const inputHash = workbenchInputHash(state)
  const rulePackVersion =
    typeof record.rulePackVersion === 'string' && record.rulePackVersion
      ? record.rulePackVersion
      : RULE_PACK_VERSION

  const snapshot = normalizeSnapshot(record.lastEvaluation)
  return {
    id,
    schemaVersion: WORKBENCH_SCHEMA_VERSION,
    title,
    createdAt,
    updatedAt,
    inputHash,
    rulePackVersion,
    state,
    // 与 save() 同一原则：快照必须属于这份输入，否则 diff 会归因到错误的基准
    lastEvaluation: snapshot && snapshot.inputHash === inputHash ? snapshot : undefined,
  }
}

export interface MigrateWorkbenchResult {
  archives: WorkbenchArchive[]
  failed: Array<{ index: number; error: string }>
}

/** 批量迁移：单条坏档案不拖垮其余，失败项必须展示给用户。 */
export function migrateWorkbenchArchives(raw: unknown): MigrateWorkbenchResult {
  if (!Array.isArray(raw)) return { archives: [], failed: [] }
  const archives: WorkbenchArchive[] = []
  const failed: MigrateWorkbenchResult['failed'] = []
  raw.forEach((item, index) => {
    try {
      archives.push(migrateWorkbenchArchive(item))
    } catch (error) {
      failed.push({ index, error: error instanceof Error ? error.message : String(error) })
    }
  })
  return { archives, failed }
}
