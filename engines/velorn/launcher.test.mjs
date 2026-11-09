// SPDX-License-Identifier: GPL-3.0-only
import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import os from 'node:os'
import net from 'node:net'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { UPSTREAM_COMMIT } from './launcher.mjs'
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
const cli = path.join(path.dirname(fileURLToPath(import.meta.url)), 'cli.mjs')
async function availablePort() {
  const server = net.createServer()
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve) })
  const port = server.address().port
  await new Promise(resolve => server.close(resolve)); return port
}
async function isListening(port) {
  return new Promise(resolve => {
    const socket = net.connect(port, '127.0.0.1')
    socket.once('connect', () => { socket.destroy(); resolve(true) })
    socket.once('error', () => resolve(false))
  })
}
async function waitFor(predicate, description, timeout = 5000) {
  const deadline = Date.now() + timeout
  do { if (await predicate()) return; await pause(25) } while (Date.now() < deadline)
  throw Error(`Timed out: ${description}`)
}

for (const mode of ['jsonl', 'mcp']) {
test(`${mode}: SIGTERM during startup stops owned processes and frees ports`, { timeout: 15000 }, async () => {
  const fixture = await fs.mkdtemp(path.join(os.tmpdir(), 'velorn-lifecycle-'))
  const source = path.join(fixture, 'source'), bins = path.join(fixture, 'bin')
  await fs.mkdir(path.join(source, 'dist'), { recursive: true })
  await fs.mkdir(path.join(source, 'node_modules', 'electron'), { recursive: true })
  await fs.mkdir(path.join(source, 'node_modules', 'vite', 'bin'), { recursive: true })
  await fs.mkdir(bins)
  await fs.writeFile(path.join(source, 'package.json'), '{}')
  await fs.writeFile(path.join(source, 'dist', 'index.html'), 'synthetic lifecycle fixture')
  // Only setup is simulated. Real child processes and real TCP ports prove cleanup.
  await fs.writeFile(path.join(bins, 'git'), `#!/bin/sh\nif [ "$1" = rev-parse ]; then pwd -P; echo ${UPSTREAM_COMMIT}; fi\n`, { mode: 0o755 })
  await fs.writeFile(path.join(source, 'node_modules', 'electron', 'index.js'), `module.exports = ${JSON.stringify(process.execPath)}\n`)
  await fs.writeFile(path.join(source, 'node_modules', 'vite', 'package.json'), '{"name":"vite"}')
  const pidFile = path.join(fixture, 'owned-pids')
  const record = `require('node:fs').appendFileSync(${JSON.stringify(pidFile)}, process.pid+'\\n');`
  await fs.writeFile(path.join(source, 'node_modules', 'vite', 'bin', 'vite.js'), `${record}\nrequire('node:http').createServer((req,res)=>{res.statusCode=503;res.end('booting')}).listen(5173,'127.0.0.1')\n`)
  const displayPort = await availablePort(), display = displayPort - 6000
  await fs.writeFile(path.join(bins, 'fixture-xvfb'), `#!${process.execPath}\n${record}\nrequire('node:net').createServer(socket=>socket.end()).listen(${displayPort},'127.0.0.1')\n`, { mode: 0o755 })
  const configPath = path.join(fixture, 'editor.json')
  await fs.writeFile(configPath, JSON.stringify({ endpoint: 'http://127.0.0.1:19790/mcp',
    projects_root: fixture + '/projects', staging_root: fixture + '/staging', outputs_root: fixture + '/outputs',
    allowed_tools: { get_project: 'read' } }))
  const entry = mode === 'mcp' ? path.join(path.dirname(cli), 'mcp.mjs') : cli
  const ownArgs = mode === 'mcp'
    ? ['--config', configPath, '--state', fixture + '/state']
    : ['--profile', fixture + '/profile', '--projects', fixture + '/projects', '--staging', fixture + '/staging', '--outputs', fixture + '/outputs']
  const child = spawn(process.execPath, [entry, '--source', source, ...ownArgs, '--xvfb-binary', bins + '/fixture-xvfb', '--display', `127.0.0.1:${display}`], {
    env: { ...process.env, PATH: bins + path.delimiter + process.env.PATH }, stdio: ['pipe', 'pipe', 'pipe'],
  })
  let stderr = ''
  child.stderr.on('data', chunk => { stderr += chunk })
  try {
    await waitFor(async () => await isListening(displayPort) && await isListening(5173), 'owned startup listeners')
    assert.equal(child.exitCode, null)
    child.kill('SIGTERM')
    await waitFor(() => child.exitCode !== null || child.signalCode !== null, 'CLI exit after startup SIGTERM')
    assert.equal(await isListening(displayPort), false, 'owned X display still listening')
    assert.equal(await isListening(5173), false, 'owned renderer still listening')
    assert.equal(child.exitCode, 0, stderr)
    for (const pid of (await fs.readFile(pidFile, 'utf8')).trim().split('\n').map(Number))
      assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' }, `owned PID ${pid} survived`)
  } finally {
    child.stdin.destroy(); child.kill('SIGKILL')
    for (const pid of (await fs.readFile(pidFile, 'utf8').catch(() => '')).trim().split('\n').filter(Boolean).map(Number))
      try { process.kill(pid, 'SIGKILL') } catch {}
    await fs.rm(fixture, { recursive: true, force: true })
  }
})
}
