// SPDX-License-Identifier: GPL-3.0-only
// One standard MCP connection owns the existing editor and its local bridge.
import fs from 'node:fs/promises'
import path from 'node:path'
import { execFile, spawn } from 'node:child_process'
import { promisify } from 'node:util'
import { launchVelorn } from './launcher.mjs'

// Python is installed in the supplied interpreter; no checkout cwd is needed.
const workingDirectory = process.cwd()
const inspect = promisify(execFile)

function options(argv) {
  const values = {}
  const booleans = new Set(['no-sandbox', 'software-gpu'])
  const strings = new Set(['source', 'config', 'state', 'python', 'xvfb-binary', 'xvfb-lib-dir', 'display'])
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i].slice(2)
    if (!argv[i].startsWith('--') || (!booleans.has(key) && !strings.has(key))) throw Error(`Unknown option ${argv[i]}`)
    if (booleans.has(key)) values[key] = true
    else {
      if (!argv[i + 1] || argv[i + 1].startsWith('--')) throw Error(`Missing value for --${key}`)
      values[key] = argv[++i]
    }
  }
  for (const key of ['source', 'config', 'state']) {
    if (!values[key] || !path.isAbsolute(values[key])) throw Error(`--${key} requires an absolute path`)
  }
  values.python ||= 'python3'
  return values
}

async function main() {
  const controller = new AbortController()
  let session, bridge, bridgeClosed
  const stop = () => { controller.abort(); bridge?.kill('SIGTERM') }
  process.once('SIGINT', stop)
  process.once('SIGTERM', stop)
  try {
    const values = options(process.argv.slice(2))
    // The same Python loader validates grants and roots for launcher and bridge.
    // Only MCP messages from the child may reach stdout.
    const { stdout } = await inspect(values.python, ['-m', 'studio_next.body_editor_mcp',
      '--config', values.config, '--print-launch-config'], {
      cwd: workingDirectory, maxBuffer: 256 * 1024, timeout: 15000, signal: controller.signal,
    })
    // A Chromium debugging socket exists ONLY for isolated synthetic X11
    // pointer integration proof. It is never a production MCP option and
    // never enabled by a model, project document or untrusted tool input.
    // An explicit CI environment variable alone is insufficient: require
    // a separate Xvfb display plus exact CI identity and the fixed port.
    const rawPointerPort = process.env.ZX7_POINTER_E2E_CDP_PORT
    let pointerTestPort = null
    if (rawPointerPort !== undefined) {
      if (process.env.CI !== 'true' || !values['xvfb-binary'] ||
          !values.display || rawPointerPort !== '19393') {
        throw Error('Native pointer inspection can only run in isolated Xvfb CI')
      }
      pointerTestPort = 19393
    }
    const config = JSON.parse(stdout)
    if (config.endpoint !== 'http://127.0.0.1:19790/mcp') throw Error('The pinned editor requires its local fixed MCP endpoint')
    await fs.mkdir(values.state, { recursive: true })
    const profileRoot = await fs.mkdtemp(path.join(values.state, 'session-'))
    session = await launchVelorn({ source: values.source, profileRoot,
      projectsRoot: config.projects_root, stagingRoot: config.staging_root, outputRoot: config.outputs_root,
      xvfbBinary: values['xvfb-binary'], xvfbLibraryDir: values['xvfb-lib-dir'], display: values.display,
      noSandbox: !!values['no-sandbox'], softwareGpu: !!values['software-gpu'],
      pointerTestPort, signal: controller.signal })
    controller.signal.throwIfAborted()
    bridge = spawn(values.python, ['-m', 'studio_next.body_editor_mcp', '--config', values.config,
      '--native-source', values.source],
      { cwd: workingDirectory, stdio: ['inherit', 'inherit', 'inherit'] })
    bridgeClosed = new Promise((resolve, reject) => {
      bridge.once('error', reject)
      bridge.once('close', (code, signal) => resolve({ code, signal }))
    })
    const outcome = await bridgeClosed
    if (!controller.signal.aborted && outcome.code !== 0) throw Error(`MCP bridge exited (${outcome.code ?? outcome.signal})`)
  } catch (error) {
    if (!controller.signal.aborted) throw error
  } finally {
    if (bridge && bridge.exitCode === null && bridge.signalCode === null) {
      bridge.kill('SIGTERM')
      const timer = setTimeout(() => bridge.kill('SIGKILL'), 3000)
      try { await bridgeClosed } finally { clearTimeout(timer) }
    }
    await session?.close()
    process.removeListener('SIGINT', stop)
    process.removeListener('SIGTERM', stop)
  }
}

main().catch(error => { console.error(error.stack); process.exitCode = 1 })
