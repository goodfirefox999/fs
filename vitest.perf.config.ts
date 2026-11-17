import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'

/**
 * 性能测试专用配置：只跑 `tests/bench`，独占进程。
 *
 * 与默认配置分开的原因：性能断言依赖「没有别的测试在抢 CPU」，
 * 混在全量里跑会因邻居负载产生假失败（实测探针 41ms → 97ms）。
 * 用法：`npm run test:perf`
 */
export default defineConfig({
  resolve: {
    alias: [
      { find: '@core', replacement: fileURLToPath(new URL('./src/core', import.meta.url)) },
      { find: '@', replacement: fileURLToPath(new URL('./src', import.meta.url)) },
    ],
  },
  test: {
    environment: 'node',
    include: ['tests/bench/**/*.test.ts'],
    fileParallelism: false,
    testTimeout: 60_000,
  },
})
