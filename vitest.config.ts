import { defineConfig } from 'vitest/config'
import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // 桌面端的冒烟测试要挂载 .vue，必须挂 vue 插件；
  // 纯 TS 测试不受影响。
  plugins: [vue()],
  resolve: {
    // 顺序有意义：'@core' / '@desktop' 必须排在 '@' 前面，
    // 否则 '@core/x' 会先被 '@' 前缀替换成 '/srccore/x'。
    alias: [
      { find: '@core', replacement: fileURLToPath(new URL('./src/core', import.meta.url)) },
      { find: '@desktop', replacement: fileURLToPath(new URL('./desktop/src', import.meta.url)) },
      { find: '@', replacement: fileURLToPath(new URL('./src', import.meta.url)) },
    ],
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    // 性能测试单独跑（`npm run test:perf`）：它测的是独占环境下的耗时，
    // 与其它文件并发时会因邻居负载产生假失败（探针 41ms → 97ms）。
    exclude: ['tests/bench/**', 'node_modules/**'],
    coverage: {
      provider: 'v8',
      // 施工依据 v1.0 §10.1 的门槛是「引擎单测行覆盖 ≥ 90%」，对象是 src/core。
      // 界面层（pages/components/desktop）不在门槛内：它们靠冒烟测试与人工验收。
      include: ['src/core/**'],
      reporter: ['text-summary', 'json-summary', 'lcov'],
      reportsDirectory: 'coverage',
      // 棘轮起点（2026-11-26 基线：行 96.37% / 分支 89.95% / 函数 85.08%）。
      // 施工依据 §10.1 要求行覆盖 ≥ 90%，这里卡得更紧。只能往上调；
      // 要下调必须在 PR 里说明是哪段代码不再值得测，不能因为「红了」就放。
      thresholds: { lines: 95, branches: 85, functions: 80 },
    },
  },
})
