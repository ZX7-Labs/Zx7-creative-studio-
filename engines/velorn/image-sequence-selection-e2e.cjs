// SPDX-License-Identifier: GPL-3.0-only
// Exercise real browser-selected Files in the isolated Velorn preload.
const assert = require('node:assert/strict')
const { execFileSync } = require('node:child_process')
const { createHash } = require('node:crypto')
const fs = require('node:fs')
const { createServer } = require('node:http')
const os = require('node:os')
const path = require('node:path')
const { app, BrowserWindow, ipcMain } = require('electron')

const [sourceArgument, expectation] = process.argv.slice(2)
assert.ok(['before', 'after'].includes(expectation))
const source = fs.realpathSync(sourceArgument)
const scratch = fs.mkdtempSync(path.join(os.tmpdir(), 'zx7-image-sequence-'))
const profile = path.join(scratch, 'profile')
fs.mkdirSync(profile)
app.setPath('userData', profile)

const modules = new Map([
  ['/src/services/imageSequenceImport.js', 'src/services/imageSequenceImport.js'],
  ['/src/services/fileSystem', 'src/services/fileSystem.js'],
  ['/src/utils/imageSequenceDetection', 'src/utils/imageSequenceDetection.js'],
])
const server = createServer((request, response) => {
  if (request.url === '/') {
    response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
    response.end('<!doctype html><input type="file" multiple>')
  } else if (modules.has(request.url)) {
    response.writeHead(200, { 'Content-Type': 'text/javascript; charset=utf-8' })
    response.end(fs.readFileSync(path.join(source, modules.get(request.url))))
  } else {
    response.writeHead(404).end()
  }
})
const digest = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex')

async function probe() {
  assert.equal(process.versions.electron, '45.2.3')
  execFileSync('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=64x48:rate=24',
    '-frames:v', '3', '-threads', '1', path.join(scratch, 'shot.%04d.png')])
  const frames = [1, 2, 3].map(frame => path.join(scratch, `shot.000${frame}.png`))
  const originalHashes = frames.map(digest)
  ipcMain.handle('path:dirname', (_event, file) => path.dirname(file))
  ipcMain.handle('fs:listDirectory', (_event, directory) => {
    assert.equal(directory, scratch)
    return { success: true, items: frames.map(file => ({
      name: path.basename(file), path: file, isFile: true,
    })) }
  })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', resolve)
  })
  const win = new BrowserWindow({ show: false, webPreferences: {
    preload: path.join(source, 'electron/preload.js'),
    nodeIntegration: false, contextIsolation: true, sandbox: true,
  } })
  try {
    await win.loadURL(`http://127.0.0.1:${server.address().port}/`)
    const debuggerSession = win.webContents.debugger
    debuggerSession.attach('1.3')
    const { root } = await debuggerSession.sendCommand('DOM.getDocument')
    const { nodeId } = await debuggerSession.sendCommand('DOM.querySelector', {
      nodeId: root.nodeId, selector: 'input',
    })
    const select = async files => {
      await debuggerSession.sendCommand('DOM.setFileInputFiles', { nodeId, files })
      return win.webContents.executeJavaScript(`(async () => {
        const { buildSequenceImportPlan } = await import('/src/services/imageSequenceImport.js')
        const files = [...document.querySelector('input').files]
        const plan = await buildSequenceImportPlan(files)
        const memoryPlan = await buildSequenceImportPlan(
          files.map(file => new File([], file.name))
        )
        return {
          fileCount: files.length,
          hasLegacyFilePath: files.some(file => typeof file.path === 'string'),
          mode: plan?.expandedFrom ?? null,
          framePaths: plan?.sequences[0].frames.map(frame => frame.path) ?? [],
          memoryFileHasPlan: memoryPlan !== null,
        }
      })()`)
    }
    const picked = await select([frames[2], frames[0], frames[1]])
    assert.equal(picked.fileCount, 3)
    assert.equal(picked.hasLegacyFilePath, false)
    assert.equal(picked.memoryFileHasPlan, false)
    if (expectation === 'before') {
      assert.equal(picked.mode, null)
      console.log('Reproduced: original Velorn cannot resolve selected image sequences on Electron 45')
      return
    }
    assert.equal(picked.mode, 'files')
    assert.deepEqual(picked.framePaths, frames)
    const single = await select([frames[1]])
    assert.equal(single.fileCount, 1)
    assert.equal(single.mode, 'sibling')
    assert.deepEqual(single.framePaths, frames)

    const { transcodeImageSequence } = require(path.join(source, 'electron/imageSequenceTranscode.js'))
    const result = await transcodeImageSequence({
      ffmpegPath: 'ffmpeg', ffprobePath: 'ffprobe',
      entries: picked.framePaths.map(file => ({ path: file, duration: 1 / 24 })),
      fps: 24, outputDir: scratch, baseName: 'sequence',
    })
    assert.ok(result.success, result.error)
    const decoded = execFileSync('ffmpeg', ['-v', 'error', '-xerror', '-i', result.outputPath,
      '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
    assert.equal(decoded.length, 3 * 64 * 48 * 3)
    assert.deepEqual(frames.map(digest), originalHashes)
    console.log('Electron 45 native file selection, sibling expansion, and decoded sequence passed')
  } finally {
    win.destroy()
  }
}

app.on('window-all-closed', () => {})
app.whenReady().then(probe).then(
  () => app.exit(0),
  error => { console.error(error); app.exit(1) },
)
app.on('quit', () => {
  server.close()
  fs.rmSync(scratch, { recursive: true, force: true })
})
