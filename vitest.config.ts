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
  },
})
