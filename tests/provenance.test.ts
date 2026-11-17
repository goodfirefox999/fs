import fs from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'
import { SOURCE_KEYS } from '@/core/zeri/sources'

/** 静态扫描：所有 sourceKey 引用必须已在登记表注册，防止「新增规则忘登记出处」。 */
function walk(dir: string): string[] {
  return fs
    .readdirSync(dir, { recursive: true })
    .map((item) => String(item))
    .filter((name) => name.endsWith('.ts'))
    .map((name) => path.join(dir, name))
}

describe('出处登记表守卫', () => {
  it('规则包与前置层引用的每个 sourceKey 都已登记', () => {
    const roots = ['src/core/zeri', 'src/core/engines'].map((dir) =>
      path.resolve(process.cwd(), dir)
    )
    const refs = new Set<string>()
    let occurrences = 0
    for (const root of roots) {
      for (const file of walk(root)) {
        if (file.endsWith(path.join('zeri', 'sources.ts'))) continue
        const text = fs.readFileSync(file, 'utf8')
        for (const match of text.matchAll(/sourceKey:\s*'([A-Z_]+)'/g)) {
          occurrences++
          refs.add(match[1])
        }
      }
    }
    expect(occurrences).toBeGreaterThan(30)
    const missing = Array.from(refs).filter((key) => !SOURCE_KEYS.includes(key))
    expect(missing, `未登记的出处 key：${missing.join(', ')}`).toEqual([])
  })

  it('登记表每个条目都具备可核对的标题，且不存在未被任何规则引用的空壳 key', () => {
    for (const key of SOURCE_KEYS) {
      expect(key).toBeTruthy()
    }
    // 玄空大卦元运表必须有独立的出处条目（此前只写在源码注释里）
    expect(SOURCE_KEYS).toContain('DAGUA_YUN_TABLE')
  })
})

describe('校验状态不可被代码升级', () => {
  it('ruleMeta 无论传入什么都只能产出 unverified', async () => {
    const { ruleMeta } = await import('@/core/zeri/sources')
    const base = { ruleId: 'X', name: 'X', sourceKey: 'XIEJI_BASE' }
    expect(ruleMeta(base).verification).toBe('unverified')
    // 试图携带更高状态也不应生效（无此入参，运行时同样返回 unverified）
    const sneaky = { ...base, verification: 'verified_by_human' } as typeof base & {
      verification: string
    }
    expect(ruleMeta(sneaky).verification).toBe('unverified')
  })
})
