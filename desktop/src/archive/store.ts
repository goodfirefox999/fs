/**
 * 桌面工作台的档案状态。
 *
 * 持久化走 Electron IPC（`desktop/main.cjs` 的 handler）；浏览器预览
 * （`npm run desktop:web`）没有 `window.desktop`，退回 localStorage，
 * 这样改界面时不必每次起 Electron。
 *
 * 四个原则：
 * 1. **写盘只有一个入口**（`writeRaw`），避免不同路径写出不同形状；
 * 2. **迁移失败不覆盖原文件**：读失败时只提示，不回写；主进程若已把损坏文件
 *    改名留档，则照常允许写新文件；若连备份都失败，进入只读保护；
 * 3. **保存失败要可见**：`errorMessage` 必须展示，不能静默；
 * 4. **写入串行化**：保存/删除/重命名/导入并发时，后写者必须看到先写者的结果，
 *    否则「快速删两条」会把第一条删掉的结果覆盖回去。
 */

import { ref } from 'vue'
import { attributeDiff, type EvaluationSnapshot } from '@core/archive'
import { RULE_PACK_VERSION } from '@core/zeri/version'
import type { WorkbenchState } from '../workbench'
import {
  WORKBENCH_SCHEMA_VERSION,
  cloneState,
  createArchive,
  defaultTitle,
  migrateWorkbenchArchives,
  workbenchInputHash,
  type WorkbenchArchive,
} from './model'

const BROWSER_STORAGE_KEY = 'jl_workbench_archives_v1'

interface RawLoad {
  archives: unknown
  warning?: string
  readOnly?: boolean
}

const archives = ref<WorkbenchArchive[]>([])
const currentId = ref('')
const failures = ref<Array<{ index: number; error: string }>>([])
const ready = ref(false)
const saving = ref(false)
const lastSavedAt = ref(0)
const errorMessage = ref('')
/** 主进程读取档案时发现的问题（损坏已备份 / 只读保护） */
const warning = ref('')
const readOnly = ref(false)

let writeQueue: Promise<unknown> = Promise.resolve()

function bridge() {
  return typeof window !== 'undefined' ? window.desktop : undefined
}

async function readRaw(): Promise<RawLoad> {
  const desktop = bridge()
  if (desktop) return desktop.loadArchives()
  try {
    return { archives: JSON.parse(localStorage.getItem(BROWSER_STORAGE_KEY) || '[]') }
  } catch {
    return { archives: [] }
  }
}

/** 串行执行所有写操作：进入临界区后再读当前列表，避免后写者覆盖先写者。 */
function serialize<T>(task: () => Promise<T>): Promise<T> {
  const run = writeQueue.then(task, task)
  writeQueue = run.then(
    () => undefined,
    () => undefined,
  )
  return run
}

async function writeRaw(list: WorkbenchArchive[]): Promise<void> {
  if (readOnly.value) {
    throw new Error('档案文件损坏且未能备份，已进入只读保护；请先处理原文件再写入')
  }
  const desktop = bridge()
  if (desktop) {
    await desktop.saveArchives(list)
    return
  }
  localStorage.setItem(BROWSER_STORAGE_KEY, JSON.stringify(list))
}

async function load(): Promise<void> {
  try {
    const loaded = await readRaw()
    const result = migrateWorkbenchArchives(loaded.archives)
    archives.value = result.archives
    failures.value = result.failed
    warning.value = loaded.warning ?? ''
    readOnly.value = loaded.readOnly === true
    // 迁移补全过（例如旧档案缺 hash）才回写；有失败项或只读时不回写，避免覆盖原始数据
    if (
      !readOnly.value &&
      result.failed.length === 0 &&
      JSON.stringify(result.archives) !== JSON.stringify(loaded.archives)
    ) {
      await writeRaw(result.archives)
    }
  } catch (error) {
    errorMessage.value = `读取档案失败：${error instanceof Error ? error.message : String(error)}`
  } finally {
    ready.value = true
  }
}

function current(): WorkbenchArchive | undefined {
  return archives.value.find((item) => item.id === currentId.value)
}

async function save(
  state: WorkbenchState,
  title?: string,
  snapshot?: EvaluationSnapshot,
): Promise<WorkbenchArchive | null> {
  saving.value = true
  errorMessage.value = ''
  try {
    return await serialize(async () => {
      const snapshotState = cloneState(state)
      const inputHash = workbenchInputHash(snapshotState)
      // 防御：快照必须来自同一份输入。不一致说明调用方把旧结果贴到了新输入上，
      // 这种档案的 diff 会永远归因错误，宁可丢掉快照也不写。
      const validSnapshot =
        snapshot && snapshot.inputHash === inputHash
          ? { ...snapshot, evaluatedAt: Date.now() }
          : undefined

      const existing = current()
      let next: WorkbenchArchive
      if (existing) {
        next = {
          ...existing,
          title: title?.trim() || existing.title,
          updatedAt: Date.now(),
          schemaVersion: WORKBENCH_SCHEMA_VERSION,
          inputHash,
          rulePackVersion: RULE_PACK_VERSION,
          state: snapshotState,
          lastEvaluation: validSnapshot ?? existing.lastEvaluation,
        }
      } else {
        next = createArchive(snapshotState, title)
        if (validSnapshot) next = { ...next, lastEvaluation: validSnapshot }
        currentId.value = next.id
      }
      const list = existing
        ? archives.value.map((item) => (item.id === next.id ? next : item))
        : [next, ...archives.value]
      await writeRaw(list)
      archives.value = list
      lastSavedAt.value = Date.now()
      return next
    })
  } catch (error) {
    errorMessage.value = `保存失败：${error instanceof Error ? error.message : String(error)}`
    return null
  } finally {
    saving.value = false
  }
}

/**
 * 自动保存：只把当前输入写回已有档案，**不动 lastEvaluation**。
 *
 * 与 save() 的区别是刻意不写快照，否则每次扫一下都会把「上次结论」刷新成当前，
 * rules_only / unstable 归因会永远消失（见 recordEvaluation 的注释）。
 * 只在已有当前档案时生效；无档案时不自动创建，避免用户随手改个字段就多出一条档案。
 * 写盘由主进程的 tmp+rename 保证原子性，本函数走同一条串行写队列。
 */
async function autosave(state: WorkbenchState): Promise<boolean> {
  const existing = current()
  if (!existing || readOnly.value) return false
  const snapshotState = cloneState(state)
  const inputHash = workbenchInputHash(snapshotState)
  if (inputHash === existing.inputHash) return false
  try {
    return await serialize(async () => {
      // 进队列后重新取一次：期间可能发生 open/remove/rename
      const target = current()
      if (!target || target.id !== existing.id) return false
      const next: WorkbenchArchive = {
        ...target,
        updatedAt: Date.now(),
        schemaVersion: WORKBENCH_SCHEMA_VERSION,
        inputHash,
        rulePackVersion: RULE_PACK_VERSION,
        state: snapshotState,
        // lastEvaluation 保持原值；输入变了但结论基准不动，diff 才能归因到 input_only
      }
      const list = archives.value.map((item) => (item.id === next.id ? next : item))
      await writeRaw(list)
      archives.value = list
      lastSavedAt.value = Date.now()
      return true
    })
  } catch (error) {
    errorMessage.value = `自动保存失败：${error instanceof Error ? error.message : String(error)}`
    return false
  }
}

/**
 * 给还没有结论基准的档案补一次扫描摘要（如外部导入的旧档案）。
 *
 * 已有基准时一律不写：`lastEvaluation` 是「上次保存时的结论」，
 * 扫描若能改写它，规则包升级导致的 rules_only / unstable 归因会在写盘瞬间消失。
 * 输入不一致时也不写——这次扫描不属于这份档案。
 * 与保存在同一条写队列里，且进入队列后重新核对。
 */
async function recordEvaluation(snapshot: EvaluationSnapshot): Promise<void> {
  try {
    await serialize(async () => {
      const existing = current()
      if (!existing) return
      if (existing.lastEvaluation) return
      if (snapshot.inputHash !== existing.inputHash) return
      const next: WorkbenchArchive = {
        ...existing,
        updatedAt: Date.now(),
        lastEvaluation: { ...snapshot, evaluatedAt: Date.now() },
      }
      const list = archives.value.map((item) => (item.id === next.id ? next : item))
      await writeRaw(list)
      archives.value = list
    })
  } catch (error) {
    errorMessage.value = `写入评估快照失败：${error instanceof Error ? error.message : String(error)}`
  }
}

/** 与档案里上一次评估对比，返回归因；没有基准时返回 null。 */
function diffAgainstCurrent(snapshot: EvaluationSnapshot) {
  const previous = current()?.lastEvaluation
  if (!previous) return null
  return attributeDiff(previous, snapshot)
}

function open(id: string): WorkbenchState | null {
  const target = archives.value.find((item) => item.id === id)
  if (!target) return null
  currentId.value = id
  return cloneState(target.state)
}

function startNew(): void {
  currentId.value = ''
}

async function remove(id: string): Promise<void> {
  errorMessage.value = ''
  try {
    await serialize(async () => {
      const list = archives.value.filter((item) => item.id !== id)
      await writeRaw(list)
      if (currentId.value === id) currentId.value = ''
      archives.value = list
    })
  } catch (error) {
    errorMessage.value = `删除失败：${error instanceof Error ? error.message : String(error)}`
  }
}

async function rename(id: string, title: string): Promise<void> {
  const trimmed = title.trim()
  if (!trimmed) return
  errorMessage.value = ''
  try {
    await serialize(async () => {
      const list = archives.value.map((item) =>
        item.id === id ? { ...item, title: trimmed, updatedAt: Date.now() } : item,
      )
      await writeRaw(list)
      archives.value = list
    })
  } catch (error) {
    errorMessage.value = `重命名失败：${error instanceof Error ? error.message : String(error)}`
  }
}

async function exportOne(id: string): Promise<string | null> {
  const target = archives.value.find((item) => item.id === id)
  if (!target) return null
  const desktop = bridge()
  if (!desktop) {
    errorMessage.value = '浏览器预览模式不支持导出，请用桌面端'
    return null
  }
  errorMessage.value = ''
  try {
    const result = await desktop.exportArchives({
      data: target,
      suggestedName: `${target.title}.json`,
    })
    return result.ok ? (result.file ?? null) : null
  } catch (error) {
    errorMessage.value = `导出失败：${error instanceof Error ? error.message : String(error)}`
    return null
  }
}

/** 从系统对话框导入：文件路径由主进程决定，渲染进程不能指定。 */
async function importOne(): Promise<WorkbenchArchive | null> {
  const desktop = bridge()
  if (!desktop?.importArchives) {
    errorMessage.value = '当前环境不支持导入（浏览器预览模式）'
    return null
  }
  errorMessage.value = ''
  let result: { ok: boolean; data?: unknown; file?: string }
  try {
    result = await desktop.importArchives()
  } catch (error) {
    errorMessage.value = `导入失败：${error instanceof Error ? error.message : String(error)}`
    return null
  }
  if (!result.ok || result.data === undefined) return null

  // 导入的可能是单条，也可能是导出时打包的数组
  const rawList = Array.isArray(result.data) ? result.data : [result.data]
  const migrated = migrateWorkbenchArchives(rawList)
  if (!migrated.archives.length) {
    errorMessage.value = `导入失败：${migrated.failed[0]?.error ?? '文件不含可识别的档案'}`
    return null
  }

  // 导入不覆盖同 id 的旧档案：换新 id，避免用户以为「导入 = 还原」
  const imported = migrated.archives.map((item) => ({
    ...item,
    id: createArchive(item.state, item.title).id,
    updatedAt: Date.now(),
  }))
  try {
    return await serialize(async () => {
      const list = [...imported, ...archives.value]
      await writeRaw(list)
      archives.value = list
      currentId.value = imported[0].id
      return imported[0]
    })
  } catch (error) {
    errorMessage.value = `导入写入失败：${error instanceof Error ? error.message : String(error)}`
    return null
  }
}

function isDirty(state: WorkbenchState): boolean {
  const target = current()
  if (!target) return true
  return target.inputHash !== workbenchInputHash(state)
}

function dismissWarning(): void {
  warning.value = ''
}

export function useArchiveStore() {
  return {
    archives,
    currentId,
    failures,
    ready,
    saving,
    lastSavedAt,
    errorMessage,
    warning,
    readOnly,
    current,
    load,
    save,
    autosave,
    recordEvaluation,
    diffAgainstCurrent,
    open,
    startNew,
    remove,
    rename,
    exportOne,
    importOne,
    isDirty,
    defaultTitle,
    dismissWarning,
  }
}
