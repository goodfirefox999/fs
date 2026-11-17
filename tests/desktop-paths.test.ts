import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import { describe, expect, it } from 'vitest'

const require = createRequire(import.meta.url)
const { safeExportName, FALLBACK_NAME } = require('../desktop/paths.cjs') as {
  safeExportName: (raw: unknown, fallback?: string, ext?: string) => string
  FALLBACK_NAME: string
}

const mainSource = fs.readFileSync(path.resolve(process.cwd(), 'desktop/main.cjs'), 'utf8')

describe('导出文件名沙箱', () => {
  it('渲染进程只能贡献文件名，不能贡献目录', () => {
    expect(safeExportName('../../etc/passwd')).toBe('passwd.json')
    expect(safeExportName('/Users/panshi/.ssh/id_rsa')).toBe('id_rsa.json')
    expect(safeExportName('..\\..\\secrets\\a.json')).toBe('a.json')
    expect(safeExportName('/abs/path/中文档案.json')).toBe('中文档案.json')
  })

  it('退化输入回落默认名，且结果永不含路径分隔符', () => {
    for (const raw of ['', null, undefined, '.', '..', '...', '   ', '///', 'a\\..\\..']) {
      const name = safeExportName(raw)
      expect(name, String(raw)).toBe(FALLBACK_NAME)
    }
    for (const raw of ['a\\b\\c', '../x', 'x/../../y', 'name\u0000with.json', '  spaced  .json']) {
      const name = safeExportName(raw)
      expect(name, raw).not.toMatch(/[/\\]/)
      expect(name.endsWith('.json'), name).toBe(true)
    }
    expect(safeExportName('.hidden')).toBe('hidden.json')
  })

  it('限长并强制 .json 后缀', () => {
    const long = safeExportName('x'.repeat(300))
    expect(long.length).toBeLessThanOrEqual('x'.repeat(80).length + '.json'.length)
    expect(safeExportName('档案')).toBe('档案.json')
    expect(safeExportName('档案.JSON')).toBe('档案.JSON')
  })

  it('报告导出可指定 html 后缀，路径穿越同样被剥掉', () => {
    expect(safeExportName('择日复核-2026-11-18', '默认.html', 'html')).toBe(
      '择日复核-2026-11-18.html',
    )
    expect(safeExportName('报告.html', '默认.html', 'html')).toBe('报告.html')
    expect(safeExportName('../../etc/passwd', '默认.html', 'html')).toBe('passwd.html')
    expect(safeExportName('/abs/path/x', '默认.html', 'html')).toBe('x.html')
    expect(safeExportName('', '默认.html', 'html')).toBe('默认.html')
    // 非法后缀回落 json，不允许把路径片段塞进后缀
    expect(safeExportName('x', 'y.json', '../evil')).toBe('x.json')
    expect(safeExportName('x', 'y.json', 'html/../..')).toBe('x.json')
  })
})

describe('主进程 IPC 输入面', () => {
  it('只有五个 handler，且没有任何 handler 读取渲染进程给的路径字段', () => {
    const channels = [...mainSource.matchAll(/ipcMain\.handle\('([^']+)'/g)].map((m) => m[1])
    expect(channels.sort()).toEqual([
      'archive:export',
      'archive:import',
      'archive:load',
      'archive:save',
      'report:export',
    ])

    // 白名单：suggestedName 只贡献文件名，data 是档案内容，html 是报告正文。
    // 三者都不得参与路径拼接，下面逐条断言。
    const outside = [
      ...mainSource.matchAll(/payload\??\.(?!suggestedName|data|html)[A-Za-z_$]+/g),
    ].map((m) => m[0])
    expect(outside, `main.cjs 读取了计划外的渲染进程字段：${outside.join(', ')}`).toEqual([])
    expect(mainSource).toContain('safeExportName(payload?.suggestedName)')
    // 报告正文只写进文件内容，不参与路径
    expect(mainSource).toContain('fs.writeFileSync(tmp, payload.html')
    // 落盘目标只可能来自 userData 或系统保存对话框
    expect(mainSource).toContain('path.join(app.getPath(\'userData\'), \'archives.json\')')
    expect(mainSource).toMatch(/const tmp = `\$\{target\.filePath\}\.tmp`/)

    // 导入同样是「路径只来自系统对话框」：handler 不收任何渲染进程参数，
    // 文件路径由 showOpenDialog 的返回值决定，体积上限与 save 一致。
    const importAt = mainSource.indexOf("ipcMain.handle('archive:import'")
    expect(importAt, 'archive:import handler 必须存在').toBeGreaterThan(-1)
    const importBlock = mainSource.slice(importAt, importAt + 800)
    expect(importBlock).toContain('async () =>')
    expect(importBlock).toContain('dialog.showOpenDialog')
    expect(importBlock).toContain('target.filePaths[0]')
    expect(importBlock).toContain('ARCHIVE_MAX_BYTES')

    // 报告导出：同样只接受 HTML 文本与建议文件名，目录来自系统保存对话框
    const reportAt = mainSource.indexOf("ipcMain.handle('report:export'")
    expect(reportAt, 'report:export handler 必须存在').toBeGreaterThan(-1)
    const reportBlock = mainSource.slice(reportAt, reportAt + 900)
    expect(reportBlock).toContain('dialog.showSaveDialog')
    expect(reportBlock).toContain("safeExportName(payload?.suggestedName, '择日复核报告.html', 'html')")
    expect(reportBlock).toContain('ARCHIVE_MAX_BYTES')
  })

  it('窗口保持沙箱化：无 nodeIntegration、contextIsolation 开启、禁止外链与新窗口', () => {
    expect(mainSource).toContain('nodeIntegration: false')
    expect(mainSource).toContain('contextIsolation: true')
    expect(mainSource).toContain('sandbox: true')
    expect(mainSource).toContain("setWindowOpenHandler(() => ({ action: 'deny' }))")
    expect(mainSource).toContain('will-navigate')
  })
})
