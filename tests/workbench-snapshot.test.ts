// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ZeRiResult } from '@core/types'
import { createState } from '@desktop/workbench'
import { cloneState } from '@desktop/archive/model'
import { sameSnapshot, snapshotOf, verdictOf } from '@desktop/archive/snapshot'

function fakeResult(over: Partial<ZeRiResult>): ZeRiResult {
  return {
    scanned: 90,
    rejected: 30,
    unmatched: 5,
    items: [],
    rejections: [],
    notes: [],
    ...over,
  } as unknown as ZeRiResult
}

describe('结论标签', () => {
  it('有候选优先', () => {
    expect(verdictOf(fakeResult({ items: [{}] as never, rejected: 89 }))).toBe('有候选')
  })

  it('全数被排除与「未排除但不合宜忌」分开', () => {
    expect(verdictOf(fakeResult({ items: [], rejected: 90 }))).toBe('全部排除')
    expect(verdictOf(fakeResult({ items: [], rejected: 30 }))).toBe('无匹配')
  })
})

describe('扫描快照', () => {
  it('哈希取自输入，排除天数取自结果', () => {
    const state = createState()
    const snapshot = snapshotOf(fakeResult({ scanned: 90, rejected: 42 }), state)
    expect(snapshot.inputHash).toMatch(/^[0-9a-f]{64}$/)
    expect(snapshot.rulePackVersion).toMatch(/^\d+\.\d+\.\d+$/)
    expect(snapshot.excludedDays).toBe(42)
    expect(snapshot.totalDays).toBe(90)
    expect(snapshot.verdict).toBe('无匹配')
  })

  it('sameSnapshot 忽略时间戳，只比五个字段', () => {
    const state = createState()
    const a = snapshotOf(fakeResult({}), state)
    const b = { ...a }
    expect(sameSnapshot(a, b)).toBe(true)
    expect(sameSnapshot(a, { ...b, excludedDays: 1 })).toBe(false)
    expect(sameSnapshot(a, { ...b, rulePackVersion: '9.9.9' })).toBe(false)
  })
})

describe('保存时写入评估快照', () => {
  beforeEach(() => {
    vi.resetModules()
    ;(window as unknown as { desktop: unknown }).desktop = {
      platform: 'darwin',
      loadArchives: async () => ({ archives: [] }),
      saveArchives: async () => ({ ok: true, file: '/tmp/a.json' }),
      exportArchives: async () => ({ ok: true, file: '/tmp/o.json' }),
      importArchives: async () => ({ ok: false }),
    }
  })

  it('保存后 lastEvaluation 落库，同输入再比对为 none', async () => {
    const { useArchiveStore } = await import('@desktop/archive/store')
    const store = useArchiveStore()
    const state = createState()
    const snapshot = snapshotOf(fakeResult({ items: [{}] as never }), state)

    const saved = await store.save(state, '测试档案', snapshot)
    expect(saved?.lastEvaluation?.verdict).toBe('有候选')
    expect(saved?.lastEvaluation?.excludedDays).toBe(30)

    const diff = store.diffAgainstCurrent(snapshot)
    expect(diff?.kind).toBe('none')
    expect(diff?.narrative).toContain('均未变化')
  })

  it('改了输入再比对归因为 input_only', async () => {
    const { useArchiveStore } = await import('@desktop/archive/store')
    const store = useArchiveStore()
    const state = createState()
    await store.save(state, '测试档案', snapshotOf(fakeResult({}), state))

    const changed = cloneState(state)
    changed.sittingDeg = 15
    const diff = store.diffAgainstCurrent(snapshotOf(fakeResult({}), changed))
    expect(diff?.kind).toBe('input_only')
    expect(diff?.inputChanged).toBe(true)
    expect(diff?.rulesChanged).toBe(false)
  })

  it('快照与输入不一致时不写入（防止旧结果贴到新输入上）', async () => {
    const { useArchiveStore } = await import('@desktop/archive/store')
    const store = useArchiveStore()
    const state = createState()

    const otherState = cloneState(state)
    otherState.mountShan = '午'
    const staleSnapshot = snapshotOf(fakeResult({}), otherState)

    const saved = await store.save(state, '测试档案', staleSnapshot)
    expect(saved?.lastEvaluation).toBeUndefined()
  })

  it('扫描不会覆盖已保存的结论基准（否则 diff 只能看到瞬时变化）', async () => {
    const { useArchiveStore } = await import('@desktop/archive/store')
    const store = useArchiveStore()
    const state = createState()
    const saved = snapshotOf(fakeResult({ items: [{}] as never }), state)
    await store.save(state, '基准档案', saved)

    const later = { ...saved, verdict: '无匹配' as const, excludedDays: 77 }
    await store.recordEvaluation(later)

    expect(store.current()?.lastEvaluation?.verdict).toBe('有候选')
    expect(store.current()?.lastEvaluation?.excludedDays).toBe(30)
    expect(store.diffAgainstCurrent(later)?.kind).toBe('unstable')
  })

  it('没有基准的档案，扫描补一次基准', async () => {
    const { useArchiveStore } = await import('@desktop/archive/store')
    const store = useArchiveStore()
    const state = createState()
    await store.save(state, '无结论档案')

    await store.recordEvaluation(snapshotOf(fakeResult({}), state))
    expect(store.current()?.lastEvaluation?.verdict).toBe('无匹配')
  })

  it('没有快照时只存输入，不编造结论', async () => {
    const { useArchiveStore } = await import('@desktop/archive/store')
    const store = useArchiveStore()
    const saved = await store.save(createState(), '无结论档案')
    expect(saved).toBeTruthy()
    expect(saved?.lastEvaluation).toBeUndefined()
    expect(store.diffAgainstCurrent(snapshotOf(fakeResult({}), createState()))).toBeNull()
  })
})
