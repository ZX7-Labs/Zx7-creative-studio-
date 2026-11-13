// SPDX-License-Identifier: GPL-3.0-only
import fs from 'node:fs/promises'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import net from 'node:net'
import { spawn, execFileSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { VelornClient } from './client.mjs'
const sourceLock = JSON.parse(readFileSync(new URL('./source-lock.json', import.meta.url), 'utf8'))
export const UPSTREAM_COMMIT = sourceLock.upstream_revision
const trustedRevisions = new Set([UPSTREAM_COMMIT, sourceLock.desktop_revision, sourceLock.collab_revision, sourceLock.collab_scene_revision, sourceLock.collab_editorial_revision].filter(Boolean))
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
async function assertFree(port) {
  const server = net.createServer()
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(port, '127.0.0.1', resolve) })
  await new Promise(resolve => server.close(resolve))
}
export async function launchVelorn({ source, profileRoot, projectsRoot, stagingRoot, outputRoot,
  xvfbBinary, xvfbLibraryDir, display, noSandbox = false, softwareGpu = false,
  pointerTestPort = null, startupTimeoutMs = 90000, signal }) {
  signal?.throwIfAborted()
  for (const [key, value] of Object.entries({ source, profileRoot, projectsRoot, stagingRoot, outputRoot }))
    if (!value || !path.isAbsolute(value)) throw Error(`${key} must be an explicit absolute path.`)
  const [gitRoot, revision] = execFileSync('git', ['rev-parse', '--show-toplevel', 'HEAD'],
    { cwd: source, encoding: 'utf8' }).trimEnd().split(/\r?\n/)
  if (gitRoot !== await fs.realpath(source)) throw Error('Editor source must be the root of the approved checkout.')
  if (!trustedRevisions.has(revision)) throw Error(`Expected upstream ${UPSTREAM_COMMIT} or its approved desktop revision; found ${revision}`)
  execFileSync('git', ['diff', '--quiet', 'HEAD', '--'], { cwd: source })
  await fs.access(path.join(source, 'dist', 'index.html'))
  const require = createRequire(path.join(source, 'package.json'))
  const electron = require('electron')
  if (pointerTestPort !== null) {
    if (process.env.CI !== 'true' || !xvfbBinary ||
        !/^127\.0\.0\.1:\d+$/.test(display || '') ||
        pointerTestPort !== 19393) {
      throw Error('Native pointer inspector is permitted only in isolated synthetic Xvfb CI')
    }
  }
  await Promise.all([assertFree(5173), assertFree(19790),
    ...(pointerTestPort === null ? [] : [assertFree(pointerTestPort)])])
  await fs.mkdir(profileRoot, { recursive: true })
  const appProfile = path.join(profileRoot, 'velorn')
  await fs.mkdir(appProfile, { recursive: true })
  for (const root of [projectsRoot, stagingRoot, outputRoot]) await fs.mkdir(root, { recursive: true })
  await fs.writeFile(path.join(appProfile, 'settings.json'), JSON.stringify({
    defaultProjectsLocation: projectsRoot,
    comfyConnection: { host: '127.0.0.1', port: 19888, useHttps: false },
    comfyLauncher: { autoStart: false, stopOnQuit: false, disableAutoLaunch: true },
  }, null, 2), { flag: 'wx', mode: 0o600 })
  const children = [], logPath = path.join(profileRoot, 'launcher.log')
  const log = await fs.open(logPath, 'a', 0o600)
  const environment = { ...process.env, XDG_CONFIG_HOME: profileRoot }
  delete environment.ELECTRON_RUN_AS_NODE
  const start = (command, args, overrides = {}) => {
    signal?.throwIfAborted()
    const child = spawn(command, args, { cwd: source, env: { ...environment, ...overrides }, stdio: ['ignore', log.fd, log.fd] })
    child.on('error', error => { child.launchError = error }); children.push(child); return child
  }
  const checkChildren = () => {
    signal?.throwIfAborted()
    for (const child of children) {
      if (child.launchError) throw child.launchError
      if (child.exitCode !== null || child.signalCode !== null) throw Error(`Velorn child exited (${child.exitCode ?? child.signalCode}); inspect ${logPath}`)
    }
  }
  let closePromise
  const onAbort = () => { void close() }
  const close = () => {
    if (closePromise) return closePromise
    closePromise = (async () => {
      signal?.removeEventListener('abort', onAbort)
      for (const child of [...children].reverse()) child.kill('SIGTERM')
      for (let i = 0; i < 30 && children.some(child => child.exitCode === null && child.signalCode === null); i++) await pause(100)
      for (const child of children) if (child.exitCode === null && child.signalCode === null) child.kill('SIGKILL')
      await log.close()
    })()
    return closePromise
  }
  signal?.addEventListener('abort', onAbort, { once: true })
  try {
    signal?.throwIfAborted()
    if (xvfbBinary) {
      if (!display || !/^127\.0\.0\.1:\d+$/.test(display)) throw Error('Xvfb needs an explicit TCP display, for example 127.0.0.1:94.')
      const number = Number(display.split(':')[1]); await assertFree(6000 + number)
      start(xvfbBinary, [`:${number}`, '-screen', '0', '1280x720x24', '-ac', '-nolisten', 'local', '-nolisten', 'unix', '-listen', 'tcp'],
        xvfbLibraryDir ? { LD_LIBRARY_PATH: xvfbLibraryDir } : {})
      for (let i = 0; i < 100; i++) {
        checkChildren()
        const connected = await new Promise(resolve => {
          const socket = net.connect(6000 + number, '127.0.0.1')
          socket.once('connect', () => { socket.destroy(); resolve(true) })
          socket.once('error', () => resolve(false))
        })
        if (connected) break
        if (i === 99) throw Error('Xvfb did not become ready.')
        await pause(100)
      }
    }
    const vite = path.join(path.dirname(require.resolve('vite/package.json')), 'bin', 'vite.js')
    start(process.execPath, [vite, 'preview', '--host', '127.0.0.1', '--port', '5173', '--strictPort'])
    const deadline = Date.now() + startupTimeoutMs
    while (true) {
      checkChildren()
      try { if ((await fetch('http://127.0.0.1:5173/', { signal: AbortSignal.timeout(1000) })).ok) break } catch {}
      if (Date.now() > deadline) throw Error('Production renderer server did not become ready.')
      await pause(100)
    }
    const nativeElectron = start(electron, [...(noSandbox ? ['--no-sandbox'] : []),
      ...(softwareGpu ? ['--disable-gpu'] : []),
      ...(pointerTestPort === null ? [] : [
        '--remote-debugging-address=127.0.0.1',
        `--remote-debugging-port=${pointerTestPort}`,
      ]),
      source], display ? { DISPLAY: display } : {})
    // Isolated synthetic CI only: identify the exact launcher-owned main
    // Electron process for the crash/reopen proof. No test IPC endpoint,
    // model-callable kill tool, production path or arbitrary PID selection.
    if (process.env.CI === 'true' && xvfbBinary && display &&
        nativeElectron.pid && Number.isSafeInteger(nativeElectron.pid)) {
      await log.write(`ZX7_CI_NATIVE_ELECTRON_PID=${nativeElectron.pid}\\n`)
    }
    const client = new VelornClient({ projectsRoot, stagingRoot, outputRoot })
    while (true) {
      checkChildren()
      try {
        await client.discover()
        const project = (await client.call('get_project')).data
        if (project?.mcp?.lastSnapshotAt && project?.generatedAt) break
      } catch {}
      if (Date.now() > deadline) throw Error(`Velorn renderer/MCP not ready; inspect ${logPath}`)
      await pause(250)
    }
    let readinessError
    while (true) {
      checkChildren()
      try { await client.call('create_project', { name: `body-readiness-${process.pid}`, previewOnly: true }); break } catch (error) { readinessError = error }
      if (Date.now() > deadline) throw Error(`Native project bridge not ready: ${readinessError?.message}; inspect ${logPath}`)
      await pause(250)
    }
    return { client, close, source, revision, profileRoot, appProfile, projectsRoot, stagingRoot, outputRoot,
      rendererUrl: 'http://127.0.0.1:5173/', logPath, pid: children.at(-1).pid }
  } catch (error) { await close(); throw error }
}
