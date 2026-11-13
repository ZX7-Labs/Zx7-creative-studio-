// SPDX-License-Identifier: GPL-3.0-only
// Actual source fileSystem service + real kernel writer. Only the IPC transport
// is simulated: this test reproduces read-only inventory silently advancing a
// stale editor's save authority (which could overwrite another process).
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { saveNativeProjectCAS, sourceSha256 } = require('./nativeProjectCAS.cjs')
const sourcePath = fileURLToPath(new URL('../src/services/fileSystem.js', import.meta.url))

const makeProject = name => ({
  created: '2026-11-14T01:00:00.000Z',
  modified: '2026-11-14T01:00:00.000Z',
  name, timelines: [{ id: 'native-timeline', clips: [] }], assets: [],
})

test('read-only load never adopts another process head for stale GUI save', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'zx7-cas-hydration-'))
  const previousWindow = globalThis.window
  try {
    const writeFile = async (file, text, options = {}) => {
      try {
        const result = await saveNativeProjectCAS(file, text, options.zx7ExpectedSha256)
        return { success: true, sha256: result.sha256 }
      } catch (error) { return { success: false, error: error.message } }
    }
    globalThis.window = { electronAPI: {
      isElectron: true,
      pathJoin: async (...segments) => path.join(...segments),
      exists: async file => { try { await fs.access(file); return true } catch { return false } },
      readFile: async (file, { encoding } = {}) => {
        const data = await fs.readFile(file)
        return { success: true, data: data.toString(encoding || 'utf8'),
          encoding: encoding || 'utf8', sha256: sourceSha256(data) }
      },
      writeFile,
    } }
    // Node doesn't treat this vendor .js as ESM: load the unchanged, REAL
    // source bytes through an ESM data URL, never a mirrored test reimplementation.
    const code = await fs.readFile(sourcePath)
    const { saveProject, loadProject } =
      await import('data:text/javascript;base64,' + code.toString('base64'))
    const original = makeProject('owner-source')
    const timestamp = await saveProject(root, original)
    assert.match(timestamp, /^2026-/)
    const native = path.join(root, 'project.comfystudio')
    const previous = await fs.readFile(native)
    const head = sourceSha256(previous)

    const changed = JSON.parse(previous.toString('utf8'))
    changed.zx7ExternalEditorMarker = 'independent-process-updated-the-file'
    const externallyWritten = JSON.stringify(changed, null, 2)
    await saveNativeProjectCAS(native, externallyWritten, head)
    const externalHead = sourceSha256(Buffer.from(externallyWritten))
    assert.equal(sourceSha256(await fs.readFile(native)), externalHead)

    // Project listing, preview and duplicate-source reads are not hydration:
    // this MUST NOT silently rebase the still-open old document's save head.
    const observed = await loadProject(root)
    assert.equal(observed.zx7ExternalEditorMarker, changed.zx7ExternalEditorMarker)
    await assert.rejects(saveProject(root, original), /Another editor saved this project/)
    assert.equal(sourceSha256(await fs.readFile(native)), externalHead)

    // Only an intentional new source-open operation may adopt a fresh head.
    const reloaded = await loadProject(root, { bindSourceHead: true })
    await saveProject(root, { ...reloaded, name: 'after-explicit-reopen' })
    const current = JSON.parse(await fs.readFile(native, 'utf8'))
    assert.equal(current.name, 'after-explicit-reopen')
    assert.equal(current.zx7ExternalEditorMarker, changed.zx7ExternalEditorMarker)
  } finally {
    globalThis.window = previousWindow
    await fs.rm(root, { recursive: true, force: true })
  }
})
