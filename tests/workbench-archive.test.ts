import { describe, expect, it } from 'vitest'
import { createState } from '@desktop/workbench'
import {
  WORKBENCH_SCHEMA_VERSION,
  WorkbenchArchiveError,
  cloneState,
  createArchive,
  migrateWorkbenchArchive,
  migrateWorkbenchArchives,
  workbenchInputHash,
} from '@desktop/archive/model'

describe('工作台输入哈希', () => {
  it('同输入同 hash', () => {
    const a = createState()
    const b = createState()
    expect(workbenchInputHash(a)).toBe(workbenchInputHash(b))
  })

  it('改坐山线度、用事、扫描窗口都改变 hash', () => {
    const base = createState()
    const original = workbenchInputHash(base)

    const moved = { ...cloneState(base), sittingDeg: 15 }
    expect(workbenchInputHash(moved)).not.toBe(original)

    const otherCategory = { ...cloneState(base), category: 'YIN_ANZANG' as const }
    expect(workbenchInputHash(otherCategory)).not.toBe(original)

    const wider = { ...cloneState(base), daysCount: 180 }
    expect(workbenchInputHash(wider)).not.toBe(original)
  })

  it('标题与时间戳不参与 hash', () => {
    const state = createState()
    const archive = createArchive(state, '甲档案')
    const renamed = { ...archive, title: '乙档案', updatedAt: archive.updatedAt + 1000 }
    expect(workbenchInputHash(renamed.state)).toBe(workbenchInputHash(archive.state))
  })

  it('命主生日参与 hash（冲命判定依赖它）', () => {
    const base = createState()
    const original = workbenchInputHash(base)
    const withBirth = cloneState(base)
    withBirth.subjects = [{ label: '主命1', date: '1975-06-01', gender: 'M' }]
    expect(workbenchInputHash(withBirth)).not.toBe(original)
  })
})

describe('档案创建', () => {
  it('新建即写当前版本、哈希与规则包版本', () => {
    const archive = createArchive(createState())
    expect(archive.schemaVersion).toBe(WORKBENCH_SCHEMA_VERSION)
    expect(archive.inputHash).toMatch(/^[0-9a-f]{64}$/)
    expect(archive.rulePackVersion).toMatch(/^\d+\.\d+\.\d+$/)
    expect(archive.title).toContain('山')
  })

  it('state 是深拷贝：改档案不影响工作台，改工作台不影响档案', () => {
    const state = createState()
    const archive = createArchive(state)

    archive.state.sittingDeg = 99
    expect(state.sittingDeg).not.toBe(99)

    state.mountShan = '午'
    expect(archive.state.mountShan).not.toBe('午')
  })
})

describe('档案迁移与校验', () => {
  it('v1 原样通过并补齐缺失元数据', () => {
    const state = cloneState(createState())
    const raw = {
      id: 'w_legacy',
      schemaVersion: 1,
      title: '旧档案',
      createdAt: 1,
      updatedAt: 2,
      state,
      // 故意不给 inputHash / rulePackVersion
    }
    const migrated = migrateWorkbenchArchive(raw)
    expect(migrated.schemaVersion).toBe(WORKBENCH_SCHEMA_VERSION)
    expect(migrated.inputHash).toBe(workbenchInputHash(state))
    expect(migrated.rulePackVersion).toBeTruthy()
  })

  it('缺少 schemaVersion 抛错（不猜版本）', () => {
    expect(() => migrateWorkbenchArchive({ state: createState() })).toThrow(WorkbenchArchiveError)
    expect(() => migrateWorkbenchArchive({ state: createState() })).toThrow(/schemaVersion/)
  })

  it('来自更高版本直接抛错，不降级读取', () => {
    const raw = { schemaVersion: 99, state: createState() }
    expect(() => migrateWorkbenchArchive(raw)).toThrow(/更高版本/)
  })

  it('缺少 state 抛错', () => {
    expect(() => migrateWorkbenchArchive({ schemaVersion: 1 })).toThrow(/缺少 state/)
  })

  it('批量迁移：一条坏档案不拖垮其余', () => {
    const good = createArchive(createState())
    const result = migrateWorkbenchArchives([good, { schemaVersion: 99 }, good])
    expect(result.archives).toHaveLength(2)
    expect(result.failed).toHaveLength(1)
    expect(result.failed[0].index).toBe(1)
  })

  it('非数组输入返回空结果', () => {
    expect(migrateWorkbenchArchives(null)).toEqual({ archives: [], failed: [] })
  })

  it('JSON 往返后迁移结果不变（IPC 序列化边界）', () => {
    const archive = createArchive(createState())
    const overIpc = migrateWorkbenchArchive(JSON.parse(JSON.stringify(archive)))
    expect(overIpc.inputHash).toBe(archive.inputHash)
    expect(overIpc.state).toEqual(archive.state)
  })
})

describe('外部输入校验（导入文件 / 手改存档）', () => {
  function rawArchive(): Record<string, unknown> {
    return {
      id: 'w_ext',
      schemaVersion: WORKBENCH_SCHEMA_VERSION,
      title: '外部档案',
      createdAt: 1,
      updatedAt: 2,
      state: cloneState(createState()),
    }
  }

  it('inputHash 一律按归一化后的 state 重算，不沿用外部给的值', () => {
    const raw = { ...rawArchive(), inputHash: 'f'.repeat(64) }
    const migrated = migrateWorkbenchArchive(raw)
    expect(migrated.inputHash).toBe(workbenchInputHash(migrated.state))
  })

  it('lastEvaluation 与输入不符时丢弃，一致时保留', () => {
    const state = cloneState(createState())
    const hash = workbenchInputHash(state)
    const snapshot = {
      rulePackVersion: '1.0.0',
      verdict: '有候选',
      excludedDays: 1,
      totalDays: 90,
      evaluatedAt: 3,
    }

    const stale = migrateWorkbenchArchive({
      ...rawArchive(),
      state,
      lastEvaluation: { ...snapshot, inputHash: 'f'.repeat(64) },
    })
    expect(stale.lastEvaluation).toBeUndefined()

    const fresh = migrateWorkbenchArchive({
      ...rawArchive(),
      state,
      lastEvaluation: { ...snapshot, inputHash: hash },
    })
    expect(fresh.lastEvaluation?.verdict).toBe('有候选')
  })

  it('类型不合法的字段直接拒绝，不静默当默认值', () => {
    const badDeg = rawArchive()
    ;(badDeg.state as Record<string, unknown>).sittingDeg = '15'
    expect(() => migrateWorkbenchArchive(badDeg)).toThrow(/坐山线度/)

    const badDate = rawArchive()
    ;(badDate.state as Record<string, unknown>).startDate = '2026-02-30'
    expect(() => migrateWorkbenchArchive(badDate)).toThrow(/不是有效日期/)

    const badHour = rawArchive()
    ;(badHour.state as Record<string, unknown>).hourBranch = '午时'
    expect(() => migrateWorkbenchArchive(badHour)).toThrow(/日课时支/)

    const badBool = rawArchive()
    ;(badBool.state as Record<string, unknown>).onlyHuangDao = 'yes'
    expect(() => migrateWorkbenchArchive(badBool)).toThrow(/布尔/)
  })

  it('主命行的性别、生日非法都拒绝', () => {
    const badGender = rawArchive()
    ;(badGender.state as Record<string, unknown>).subjects = [
      { label: '主命1', date: '1975-06-01', gender: 'X' },
    ]
    expect(() => migrateWorkbenchArchive(badGender)).toThrow(/性别/)

    const badBirth = rawArchive()
    ;(badBirth.state as Record<string, unknown>).subjects = [
      { label: '主命1', date: '1975/06/01', gender: 'M' },
    ]
    expect(() => migrateWorkbenchArchive(badBirth)).toThrow(/YYYY-MM-DD/)
  })

  it('缺省字段按当前默认值补齐', () => {
    const migrated = migrateWorkbenchArchive({ schemaVersion: 1, state: { mountShan: '午' } })
    expect(migrated.state.mountShan).toBe('午')
    expect(migrated.state.sanShaMode).toBe('year_month')
    expect(migrated.state.subjects).toEqual([])
    expect(migrated.inputHash).toBe(workbenchInputHash(migrated.state))
  })
})
