/**
 * 登记表工具：把「id → 元数据」的查找统一成会抛错的形态。
 * 背景：`Record<string, T>` 取值时键写错不会报错，只会拿到 undefined，
 * 于是界面说明、出处、分类会「静默变空」——本项目已两次踩过这类坑。
 */

export interface Registry<T> {
  /** 取不到就抛错：新条目忘了登记必须让测试红，而不是落到默认值 */
  require(id: string): T
  /** 允许缺失的场合（如只有部分条目有立场分档） */
  optional(id: string): T | undefined
  has(id: string): boolean
  keys(): string[]
  /** 反向校验：登记表里是否存在规则集之外的 id */
  extraKeys(validIds: string[]): string[]
}

export function createRegistry<T>(
  name: string,
  entries: Record<string, T>,
  missingHint = '',
): Registry<T> {
  return {
    require(id: string): T {
      if (!(id in entries)) {
        throw new Error(`${name} 缺少「${id}」的登记${missingHint ? `：${missingHint}` : ''}`)
      }
      return entries[id]
    },
    optional(id: string): T | undefined {
      return entries[id]
    },
    has(id: string): boolean {
      return id in entries
    },
    keys(): string[] {
      return Object.keys(entries)
    },
    extraKeys(validIds: string[]): string[] {
      const valid = new Set(validIds)
      return Object.keys(entries).filter((key) => !valid.has(key))
    },
  }
}
