/**
 * 规范化 JSON：把「同一个输入」压成同一个字符串，供 inputHash 使用。
 *
 * 三条规则决定了 inputHash 是否可比：
 *
 * 1. **键序无关**：按码点排序，不用 `localeCompare`（不同 ICU 数据会给出不同顺序，
 *    导致同一份数据在两端算出不同 hash）。
 * 2. **undefined 等同于缺失**：对象里值为 undefined 的键直接剔除。
 *    这条同时解决了 IPC 序列化边界——`JSON.stringify({a:undefined})` 得到 `{}`，
 *    若这里把 undefined 当作「有值」，内存里的对象与落盘后再读回来的对象
 *    会算出两个不同的 hash，跨会话 diff 立刻失效。
 * 3. **数值只接受有限数**：NaN / Infinity 不是可比较的事实，直接抛错，
 *    不静默变成 null（那会让两次不同的坏输入得到相同 hash）。
 */

export class CanonicalizeError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'CanonicalizeError'
  }
}

function canonicalNumber(value: number, path: string): string {
  if (!Number.isFinite(value)) {
    throw new CanonicalizeError(`${path} 不是有限数：${String(value)}`)
  }
  // -0 与 0 在 JSON 里无法区分，统一成 0，避免 0 与 -0 得到不同 hash
  const normalized = Object.is(value, -0) ? 0 : value
  return JSON.stringify(normalized)
}

function canonicalValue(value: unknown, path: string): string {
  if (value === null) return 'null'

  switch (typeof value) {
    case 'boolean':
      return value ? 'true' : 'false'
    case 'number':
      return canonicalNumber(value, path)
    case 'string':
      return JSON.stringify(value)
    case 'object':
      break
    default:
      // function / symbol / bigint 不属于档案数据；抛错而不是静默丢弃，
      // 否则「多了个不可序列化字段」会悄悄改变 hash 的语义
      throw new CanonicalizeError(`${path} 的类型不可规范化：${typeof value}`)
  }

  if (Array.isArray(value)) {
    // 数组里的 undefined 按 JSON 语义落成 null，保持「位置有意义」
    return `[${value.map((item, i) => canonicalValue(item === undefined ? null : item, `${path}[${i}]`)).join(',')}]`
  }

  const entries = Object.entries(value as Record<string, unknown>)
    .filter(([, item]) => item !== undefined)
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))

  const body = entries
    .map(([key, item]) => `${JSON.stringify(key)}:${canonicalValue(item, `${path}.${key}`)}`)
    .join(',')
  return `{${body}}`
}

/** 返回键序无关、剔除 undefined 的规范化 JSON 字符串。 */
export function canonicalize(value: unknown): string {
  return canonicalValue(value, '$')
}
