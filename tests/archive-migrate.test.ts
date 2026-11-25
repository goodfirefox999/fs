import { createHash } from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import {
  ARCHIVE_SCHEMA_VERSION,
  ArchiveMigrationError,
  attributeDiff,
  canonicalize,
  inputHashOf,
  migrateArchive,
  migrateArchives,
  sha256Hex,
  type EvaluationSnapshot,
} from '@/core/archive'
import { LEGACY_RULE_PACK_VERSION, RULE_PACK_VERSION } from '@/core/zeri/version'

const FIXTURES = path.resolve(__dirname, 'fixtures')

function readFixture<T = unknown>(name: string): T {
  return JSON.parse(fs.readFileSync(path.join(FIXTURES, name), 'utf8')) as T
}

describe('SHA-256 实现（三端一致的前提）', () => {
  it('已知向量', () => {
    expect(sha256Hex('')).toBe(
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    )
    expect(sha256Hex('abc')).toBe(
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    )
  })

  it('与 node:crypto 逐条一致（含中文、代理对、长串）', () => {
    const samples = [
      '居境罗盘',
      '丙山壬向 · 2026',
      '𠀀𠀁𠀂', // 扩展 B 区，代理对
      'a'.repeat(1000),
      '节'.repeat(100),
    ]
    for (const sample of samples) {
      const expected = createHash('sha256').update(sample, 'utf8').digest('hex')
      expect(sha256Hex(sample), `样本 ${sample.slice(0, 8)}`).toBe(expected)
    }
  })
})

describe('规范化 JSON', () => {
  it('键序无关', () => {
    expect(canonicalize({ b: 1, a: 2 })).toBe(canonicalize({ a: 2, b: 1 }))
  })

  it('undefined 键被剔除，与缺失等价', () => {
    expect(canonicalize({ a: 1, b: undefined })).toBe(canonicalize({ a: 1 }))
  })

  it('数组里的 undefined 落成 null（位置有意义）', () => {
    expect(canonicalize([1, undefined, 3])).toBe('[1,null,3]')
  })

  it('-0 与 0 同值', () => {
    expect(canonicalize({ v: -0 })).toBe(canonicalize({ v: 0 }))
  })

  it('NaN / Infinity 抛错而不是静默变 null', () => {
    expect(() => canonicalize({ v: Number.NaN })).toThrow(/不是有限数/)
    expect(() => canonicalize({ v: Number.POSITIVE_INFINITY })).toThrow(/不是有限数/)
  })
})

describe('inputHash：只覆盖影响结论的字段', () => {
  const base = readFixture('archive-v1.json') as Record<string, unknown>

  it('同输入同 hash', () => {
    expect(inputHashOf(base as never)).toBe(inputHashOf({ ...base } as never))
  })

  it('改标题、id、时间戳不改变 hash', () => {
    const original = inputHashOf(base as never)
    expect(inputHashOf({ ...base, title: '换个名字' } as never)).toBe(original)
    expect(inputHashOf({ ...base, id: 'a_other' } as never)).toBe(original)
    expect(inputHashOf({ ...base, updatedAt: 1 } as never)).toBe(original)
  })

  it('改坐向、用事年份、仙命都改变 hash', () => {
    const original = inputHashOf(base as never)
    expect(
      inputHashOf({
        ...base,
        reading: { ...(base.reading as object), mountDeg: 166 },
      } as never),
    ).not.toBe(original)
    expect(inputHashOf({ ...base, eventYear: 2027 } as never)).not.toBe(original)
    // 报告锚点决定择日起点与月盘所属月，是输入的一部分
    expect(inputHashOf({ ...base, asOfDate: '2026-06-01' } as never)).not.toBe(original)

    const yin = base.yin as Record<string, unknown>
    expect(
      inputHashOf({
        ...base,
        yin: { ...yin, incomingDragon: '午' },
      } as never),
    ).not.toBe(original)
  })

  it('可选字段为 undefined 与字段缺失得到同一 hash（IPC 序列化边界）', () => {
    const withUndefined = { ...base, yang: undefined }
    const withoutKey = { ...base }
    delete (withoutKey as Record<string, unknown>).yang

    // 先确认 JSON 往返后两者确实同形
    expect(JSON.stringify(withUndefined)).toBe(JSON.stringify(withoutKey))
    expect(inputHashOf(withUndefined as never)).toBe(inputHashOf(withoutKey as never))
  })
})

describe('迁移链', () => {
  const v1 = readFixture('archive-v1.json')

  it('v1 → v3 补出 rulePackVersion、inputHash 与 asOfDate', () => {
    const migrated = migrateArchive(v1)
    expect(migrated.schemaVersion).toBe(ARCHIVE_SCHEMA_VERSION)
    expect(migrated.rulePackVersion).toBe(LEGACY_RULE_PACK_VERSION)
    expect(migrated.inputHash).toMatch(/^[0-9a-f]{64}$/)
    expect(migrated.inputHash).toBe(inputHashOf(migrated))
    // createdAt=1767225600000 是 2026-01-01T00:00:00Z；回填取 UTC 日期，与机器时区无关
    expect(migrated.asOfDate).toBe('2026-01-01')
  })

  it('v2 样本 → v3：已有字段原样保留，只多锚点并重算 hash', () => {
    const v2 = readFixture('archive-v2.json')
    const v3 = migrateArchive(v2)
    const { asOfDate, schemaVersion, inputHash, ...rest } = v3
    const { schemaVersion: _v, inputHash: _h, ...v2Rest } = v2 as typeof v3
    expect(schemaVersion).toBe(ARCHIVE_SCHEMA_VERSION)
    expect(asOfDate).toBe('2026-01-01')
    // INPUT_FIELDS 多了 asOfDate，旧 hash 必须被替换，否则之后每次对比都误报「输入变了」
    expect(inputHash).not.toBe((v2 as { inputHash: string }).inputHash)
    expect(rest).toEqual(v2Rest)
  })

  it('迁移幂等：v2 再迁一次不变', () => {
    const once = migrateArchive(v1)
    const twice = migrateArchive(once)
    expect(twice).toEqual(once)
  })

  it('缺失 schemaVersion 视为 v1', () => {
    const { schemaVersion: _drop, ...noVersion } = v1 as Record<string, unknown>
    const migrated = migrateArchive(noVersion)
    expect(migrated.schemaVersion).toBe(ARCHIVE_SCHEMA_VERSION)
  })

  it('schemaVersion 为 undefined（JSON 往返后键消失）同样视为 v1', () => {
    const raw = { ...(v1 as Record<string, unknown>), schemaVersion: undefined }
    const roundTripped = JSON.parse(JSON.stringify(raw))
    expect('schemaVersion' in roundTripped).toBe(false)
    expect(migrateArchive(roundTripped).schemaVersion).toBe(ARCHIVE_SCHEMA_VERSION)
  })

  it('来自更高版本的档案直接抛错，不尝试降级读取', () => {
    const future = { ...(v1 as Record<string, unknown>), schemaVersion: 99 }
    expect(() => migrateArchive(future)).toThrow(ArchiveMigrationError)
    expect(() => migrateArchive(future)).toThrow(/更高版本/)
  })

  it('非法 schemaVersion 抛错', () => {
    expect(() => migrateArchive({ ...(v1 as object), schemaVersion: '2' })).toThrow(/非法/)
    expect(() => migrateArchive({ ...(v1 as object), schemaVersion: 0 })).toThrow(/非法/)
  })

  it('批量迁移：一条坏档案不拖垮其余', () => {
    const result = migrateArchives([v1, { schemaVersion: 99 }, v1])
    expect(result.archives).toHaveLength(2)
    expect(result.failed).toHaveLength(1)
    expect(result.failed[0].index).toBe(1)
  })

  it('非数组输入返回空结果而不是抛错', () => {
    expect(migrateArchives(null)).toEqual({ archives: [], failed: [] })
  })

  it('与固定样本 archive-v3.json 完全一致（v1 直迁与经 v2 再迁是同一结果）', () => {
    const expected = readFixture('archive-v3.json')
    expect(migrateArchive(v1)).toEqual(expected)
    // v2 是曾落盘过的历史版本，必须能从它单独升上来
    expect(migrateArchive(readFixture('archive-v2.json'))).toEqual(expected)
  })

  it('v2 → v3 缺 createdAt 时拒绝迁移，不编造锚点', () => {
    const { createdAt: _drop, ...noCreatedAt } = readFixture('archive-v2.json') as Record<string, unknown>
    expect(() => migrateArchive(noCreatedAt)).toThrow(/createdAt/)
  })

  it('IPC 往返（JSON 序列化）后迁移结果不变', () => {
    // 桌面端 archive:save 用 JSON.stringify 落盘，archive:load 再 parse 回来。
    // 含 undefined 的字段会在这一步丢键——迁移若依赖「键是否存在」就会跨会话失效。
    const inMemory = migrateArchive(v1)
    const overIpc = migrateArchive(JSON.parse(JSON.stringify(inMemory)))
    expect(overIpc).toEqual(inMemory)
    expect(overIpc.inputHash).toBe(inMemory.inputHash)
  })

  it('含 undefined 字段的档案经 IPC 往返后 hash 不变', () => {
    const withUndefined = { ...(v1 as Record<string, unknown>), yang: undefined }
    const overIpc = migrateArchive(JSON.parse(JSON.stringify(withUndefined)))
    expect(overIpc.inputHash).toBe(migrateArchive(v1).inputHash)
  })
})

describe('差异归因', () => {
  const base: EvaluationSnapshot = {
    inputHash: 'a'.repeat(64),
    rulePackVersion: '1.0.3',
    verdict: 'favorable',
    excludedDays: 90,
    totalDays: 180,
  }

  it('全同 → none', () => {
    const result = attributeDiff(base, { ...base })
    expect(result.kind).toBe('none')
    expect(result.narrative).toContain('均未变化')
  })

  it('仅输入变 → input_only', () => {
    const result = attributeDiff(base, { ...base, inputHash: 'b'.repeat(64) })
    expect(result.kind).toBe('input_only')
    expect(result.inputChanged).toBe(true)
    expect(result.rulesChanged).toBe(false)
  })

  it('仅规则变 → rules_only，叙述里带版本号', () => {
    const result = attributeDiff(base, {
      ...base,
      rulePackVersion: '1.0.4',
      excludedDays: 87,
    })
    expect(result.kind).toBe('rules_only')
    expect(result.narrative).toContain('1.0.3 → 1.0.4')
    expect(result.narrative).toContain('90 天 → 87 天')
  })

  it('两者都变 → both', () => {
    const result = attributeDiff(base, {
      ...base,
      inputHash: 'b'.repeat(64),
      rulePackVersion: '1.0.4',
    })
    expect(result.kind).toBe('both')
  })

  it('输入与规则都未变但结论不同 → unstable（不谎称无变化）', () => {
    const result = attributeDiff(base, { ...base, verdict: 'rejected' })
    expect(result.kind).toBe('unstable')
    expect(result.narrative).toContain('需人工复核')
  })
})

describe('当前规则包版本', () => {
  it('是语义化版本，且不等于历史占位值', () => {
    expect(RULE_PACK_VERSION).toMatch(/^\d+\.\d+\.\d+$/)
    expect(RULE_PACK_VERSION).not.toBe(LEGACY_RULE_PACK_VERSION)
  })
})
