const { app, BrowserWindow, Menu, dialog, ipcMain, screen } = require('electron')
const fs = require('node:fs')
const path = require('node:path')
const { pathToFileURL } = require('node:url')
const { safeExportName } = require('./paths.cjs')

const DEV_SERVER = process.env.DESKTOP_DEV_SERVER
const isMac = process.platform === 'darwin'

/**
 * IPC 输入面（三个 handler 全部在此，逐个标注渲染进程能影响到什么）：
 * - archive:load 无入参，只读 userData。
 * - archive:save 入参是数组，落盘路径由 app.getPath('userData') 决定，渲染进程无法指定路径。
 * - archive:export 入参只贡献「文件名」，目录一律来自系统保存对话框；文件名再经 safeExportName 剥目录成分。
 * 结论：没有任何 handler 接受渲染进程给的绝对路径或相对路径。
 */
const ARCHIVE_MAX_BYTES = 8 * 1024 * 1024

const DEFAULT_BOUNDS = { width: 1480, height: 940 }

function storeFile() {
  return path.join(app.getPath('userData'), 'archives.json')
}

/**
 * 档案解析失败时静默返回 [] 是数据事故：界面会显示「还没有档案」，
 * 用户随手保存一次就把唯一副本覆盖了。这里把原文件改名留档，并让渲染进程看到。
 * 改名失败（权限等）时返回 null，调用方转只读模式，绝不覆盖原文件。
 */
function quarantineStore(file) {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-')
  const backup = `${file}.corrupt-${stamp}.json`
  try {
    fs.renameSync(file, backup)
    return backup
  } catch {
    return null
  }
}

function windowStateFile() {
  return path.join(app.getPath('userData'), 'window-state.json')
}

/** 窗口尺寸/位置不值得为它崩溃：读不到就用默认值，坐标不在任何显示器内也丢弃。 */
function loadWindowState() {
  const next = { ...DEFAULT_BOUNDS, maximized: false }
  let saved
  try {
    saved = JSON.parse(fs.readFileSync(windowStateFile(), 'utf8'))
  } catch {
    return next
  }
  if (!saved || typeof saved !== 'object') return next
  if (Number.isFinite(saved.width) && Number.isFinite(saved.height)) {
    next.width = Math.max(1180, Math.round(saved.width))
    next.height = Math.max(720, Math.round(saved.height))
  }
  if (Number.isFinite(saved.x) && Number.isFinite(saved.y)) {
    const visible = screen.getAllDisplays().some((display) => {
      const area = display.workArea
      return (
        saved.x + next.width > area.x &&
        saved.x < area.x + area.width &&
        saved.y + next.height > area.y &&
        saved.y < area.y + area.height
      )
    })
    if (visible) {
      next.x = Math.round(saved.x)
      next.y = Math.round(saved.y)
    }
  }
  next.maximized = saved.maximized === true
  return next
}

function trackWindowState(win) {
  let timer
  const persist = () => {
    if (win.isDestroyed()) return
    if (timer) clearTimeout(timer)
    timer = undefined
    try {
      fs.writeFileSync(
        windowStateFile(),
        JSON.stringify({ ...win.getNormalBounds(), maximized: win.isMaximized() }),
        'utf8',
      )
    } catch {
      // 窗口状态只是便利功能，写失败不影响使用
    }
  }
  const schedule = () => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(persist, 400)
  }
  win.on('resize', schedule)
  win.on('move', schedule)
  win.on('maximize', schedule)
  win.on('unmaximize', schedule)
  win.on('close', persist)
  win.on('closed', () => {
    if (timer) clearTimeout(timer)
  })
}

function registerIpc() {
  ipcMain.handle('archive:load', () => {
    const file = storeFile()
    let text
    try {
      text = fs.readFileSync(file, 'utf8')
    } catch (error) {
      if (error && error.code === 'ENOENT') return { archives: [] }
      throw new Error(`读取档案失败：${error instanceof Error ? error.message : String(error)}`)
    }
    try {
      const parsed = JSON.parse(text)
      if (!Array.isArray(parsed)) throw new Error('档案文件不是数组')
      return { archives: parsed }
    } catch (error) {
      const backup = quarantineStore(file)
      const detail = error instanceof Error ? error.message : String(error)
      if (backup) {
        return {
          archives: [],
          warning: `档案文件无法解析（${detail}），原文件已备份为 ${path.basename(backup)}；可从档案页导入备份恢复。`,
        }
      }
      return {
        archives: [],
        readOnly: true,
        warning: `档案文件无法解析（${detail}），且备份失败。为避免覆盖唯一副本，本次会话禁止写入档案。`,
      }
    }
  })

  ipcMain.handle('archive:save', (_event, archives) => {
    if (!Array.isArray(archives) || !archives.every((item) => item && typeof item === 'object')) {
      throw new Error('档案数据格式不正确')
    }
    const text = JSON.stringify(archives, null, 2)
    if (Buffer.byteLength(text, 'utf8') > ARCHIVE_MAX_BYTES) {
      throw new Error('档案体积超出上限，请先导出后清理')
    }
    const file = storeFile()
    fs.mkdirSync(path.dirname(file), { recursive: true })
    // 原子写只防「写到一半崩溃」，防不了「覆盖掉上一版」；留一份 .bak 兜底
    if (fs.existsSync(file)) {
      try {
        fs.copyFileSync(file, `${file}.bak`)
      } catch {
        // 备份是尽力而为，失败不阻断正常保存
      }
    }
    // 先写临时文件再改名，避免中途崩溃把唯一一份档案写坏
    const tmp = `${file}.tmp`
    fs.writeFileSync(tmp, text, 'utf8')
    fs.renameSync(tmp, file)
    return { ok: true, file }
  })

  ipcMain.handle('archive:export', async (_event, payload) => {
    if (!payload || typeof payload !== 'object' || payload.data === undefined) {
      throw new Error('导出数据格式不正确')
    }
    const target = await dialog.showSaveDialog({
      title: '导出档案',
      // 只取文件名部分：渲染进程不能决定落盘目录，避免 ../ 或绝对路径越界
      defaultPath: safeExportName(payload?.suggestedName),
      filters: [{ name: 'JSON', extensions: ['json'] }],
    })
    if (target.canceled || !target.filePath) return { ok: false }
    const dir = path.dirname(target.filePath)
    fs.mkdirSync(dir, { recursive: true })
    const tmp = `${target.filePath}.tmp`
    fs.writeFileSync(tmp, JSON.stringify(payload.data, null, 2), 'utf8')
    fs.renameSync(tmp, target.filePath)
    return { ok: true, file: target.filePath }
  })

  /**
   * 导入：路径完全由系统打开对话框决定，渲染进程只拿到解析后的数据，
   * 与 archive:export 同一条边界规则——不接受渲染进程给的任何路径。
   */
  ipcMain.handle('archive:import', async () => {
    const target = await dialog.showOpenDialog({
      title: '导入档案',
      filters: [{ name: 'JSON', extensions: ['json'] }],
      properties: ['openFile'],
    })
    if (target.canceled || target.filePaths.length === 0) return { ok: false }

    const file = target.filePaths[0]
    const stat = fs.statSync(file)
    if (stat.size > ARCHIVE_MAX_BYTES) {
      throw new Error('导入文件体积超出上限')
    }
    const text = fs.readFileSync(file, 'utf8')
    let data
    try {
      data = JSON.parse(text)
    } catch {
      throw new Error('导入文件不是合法 JSON')
    }
    return { ok: true, data, file }
  })

  /**
   * 报告导出：入参只有 HTML 文本与文件名，落盘目录来自系统保存对话框。
   * 报告是纯文本，写临时文件再改名，避免中途崩溃留下半截文件。
   */
  ipcMain.handle('report:export', async (_event, payload) => {
    if (!payload || typeof payload.html !== 'string' || payload.html.length === 0) {
      throw new Error('报告内容为空')
    }
    if (Buffer.byteLength(payload.html, 'utf8') > ARCHIVE_MAX_BYTES) {
      throw new Error('报告体积超出上限')
    }
    const target = await dialog.showSaveDialog({
      title: '导出报告',
      defaultPath: safeExportName(payload?.suggestedName, '择日复核报告.html', 'html'),
      filters: [{ name: 'HTML', extensions: ['html'] }],
    })
    if (target.canceled || !target.filePath) return { ok: false }
    const dir = path.dirname(target.filePath)
    fs.mkdirSync(dir, { recursive: true })
    const tmp = `${target.filePath}.tmp`
    fs.writeFileSync(tmp, payload.html, 'utf8')
    fs.renameSync(tmp, target.filePath)
    return { ok: true, file: target.filePath }
  })
}

function createWindow() {
  const bounds = loadWindowState()
  const indexFile = path.join(__dirname, '../dist-desktop/index.html')
  const win = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    x: bounds.x,
    y: bounds.y,
    minWidth: 1180,
    minHeight: 720,
    title: '居境罗盘',
    backgroundColor: '#FBF7EF',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  trackWindowState(win)
  win.once('ready-to-show', () => {
    if (bounds.maximized) win.maximize()
    win.show()
  })

  // 本地应用不需要浏览外部页面：新窗口一律拒绝，主窗口只允许停在自身入口
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  const allowedPrefix = DEV_SERVER ? DEV_SERVER : pathToFileURL(indexFile).href
  win.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(allowedPrefix)) event.preventDefault()
  })

  if (DEV_SERVER) {
    win.loadURL(DEV_SERVER)
    win.webContents.openDevTools({ mode: 'detach' })
  } else {
    win.loadFile(indexFile)
  }
  return win
}

async function main() {
  const gotLock = app.requestSingleInstanceLock()
  if (!gotLock) {
    app.quit()
    return
  }
  await app.whenReady()
  registerIpc()

  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      ...(isMac ? [{ role: 'appMenu' }] : []),
      { role: 'fileMenu' },
      { role: 'editMenu' },
      { role: 'viewMenu' },
      { role: 'windowMenu' },
    ]),
  )

  createWindow()
  app.on('second-instance', () => {
    const focused = BrowserWindow.getAllWindows()[0]
    if (!focused) return
    if (focused.isMinimized()) focused.restore()
    focused.show()
    focused.focus()
  })
  // macOS：关掉窗口后点 Dock 图标要能重新开窗，否则只能退出重进
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
  app.on('window-all-closed', () => {
    if (!isMac) app.quit()
  })
}

void main()
