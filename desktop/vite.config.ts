import { fileURLToPath, URL } from 'node:url'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// 桌面端渲染进程：复用 ../src/core 的确定性引擎，不引入 uni-app 运行时
export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  base: './',
  plugins: [vue()],
  resolve: {
    alias: {
      '@core': fileURLToPath(new URL('../src/core', import.meta.url)),
      '@desktop': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: { port: 5199, strictPort: true },
  build: {
    outDir: fileURLToPath(new URL('../dist-desktop', import.meta.url)),
    emptyOutDir: true,
    target: 'es2022',
    rollupOptions: {
      output: {
        // 引擎与 UI 拆包：避免单个 chunk >500KB 触发构建警告，
        // 也让规则引擎的变更不使整个 UI 缓存失效。
        manualChunks(id) {
          // 只按路径归类，不列具体入口文件（各子目录的 index.ts 并非都存在）
          if (id.includes('/src/core/')) return 'core-engine'
          if (id.includes('node_modules')) return 'vendor'
          return undefined
        },
      },
    },
  },
})
