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
  },
})
