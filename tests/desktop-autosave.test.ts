// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from 'vitest'

/**
 * 自动保存契约（Phase 2.2）：
 * 1. 只更新输入与 inputHash，绝不写 lastEvaluation —— 否则 rules_only/unstable 归因会消失；
 * 2. 无当前档案时不自动创建；
 * 3. 输入未变时不写盘。
 */
const writes: unknown[][] = []
const archives = [
  {
    id: 'a1', title: '档案一', inputHash: 'old-hash',
    lastEvaluation: { inputHash: 'old-hash', evaluatedAt: 1, verdict: 'KEEP' },
    state: { sittingDeg: 100 },
  },
]

vi.mock('vue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue')>()
  return { ...actual, ref: (v: unknown) => ({ value: v }) }
})

const store = await import('@desktop/archive/store')
const { createState } = await import('@desktop/workbench')

describe('档案自动保存', () => {
  beforeEach(() => {
    writes.length = 0
    const s = store.useArchiveStore()
    s.archives.value = archives.map((a) => ({ ...a }))
    s.currentId.value = ''
    s.errorMessage.value = ''
  })

  it('无当前档案时不写盘（不自动创建档案）', async () => {
    // currentId 初始为空
    const s = store.useArchiveStore()
    s.currentId.value = ''
    const ok = await s.autosave({ sittingDeg: 200 } as never)
    expect(ok).toBe(false)
  })

  it('自动保存后 lastEvaluation 保持原样', async () => {
    const s = store.useArchiveStore()
    s.archives.value = archives.map((a) => ({ ...a }))
    s.currentId.value = 'a1'
    const before = (s.archives.value[0] as { lastEvaluation: unknown }).lastEvaluation
    await s.autosave({ sittingDeg: 123 } as never)
    const after = (s.archives.value[0] as { lastEvaluation: unknown }).lastEvaluation
    expect(after).toEqual(before)
    expect(after).not.toBeNull()
  })

  it('自动保存会更新 inputHash 与输入状态', async () => {
    const s = store.useArchiveStore()
    s.archives.value = archives.map((a) => ({ ...a }))
    s.currentId.value = 'a1'
    const next = createState()
    next.sittingDeg = 123
    await s.autosave(next)
    const item = s.archives.value[0] as { inputHash: string; state: { sittingDeg: number } }
    expect(item.inputHash).not.toBe('old-hash')
    expect(item.state.sittingDeg).toBe(123)
  })
})
