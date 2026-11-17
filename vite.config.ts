import fs from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import type { Plugin } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

const CONTENT_FILE = fileURLToPath(
  new URL('./cloudfunctions/getReportContent/content/shuangxing.json', import.meta.url)
)

function devContentApi(): Plugin {
  return {
    name: 'dev-content-api',
    configureServer(server) {
      server.middlewares.use('/api/content', (_req, res) => {
        try {
          const body = fs.readFileSync(CONTENT_FILE, 'utf8')
          res.statusCode = 200
          res.setHeader('Content-Type', 'application/json; charset=utf-8')
          res.setHeader('Cache-Control', 'no-store')
          res.end(body)
        } catch {
          res.statusCode = 500
          res.setHeader('Content-Type', 'application/json; charset=utf-8')
          res.end(JSON.stringify({ message: '内容文件未生成，请先运行 npm run content' }))
        }
      })
    },
  }
}

export default defineConfig({
  plugins: [uni(), devContentApi()],
})
