'use strict'
// SPDX-License-Identifier: GPL-3.0-only
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const os = require('node:os')
const path = require('node:path')
const { spawn } = require('node:child_process')
const { saveNativeProjectCAS, sourceSha256, withNativeProjectLock } = require('./nativeProjectCAS.cjs')

const document = (name, modified = '2026-11-13T00:00:00.000Z') => JSON.stringify({
  created: '2026-11-12T01:00:00.000Z', modified,
  name, timelines: [{ id: 'timeline-1', clips: [] }], assets: [],
})
const fixture = async () => {
  const scratch = await fs.mkdtemp(path.join(os.tmpdir(), 'zx7-native-cas-'))
  return { scratch, file: path.join(scratch, 'project.comfystudio'),
    cleanup: () => fs.rm(scratch, { recursive: true, force: true }) }
}
const runNode = (script, ...args) => new Promise((resolve, reject) => {
  const child = spawn(process.execPath, ['-e', script, ...args], {
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  let out = '', err = ''
  child.stdout.on('data', d => { out += d })
  child.stderr.on('data', d => { err += d })
  child.once('error', reject)
  child.once('close', (code, signal) => resolve({ code, signal, out, err }))
})

test('new project creates committed SHA; duplicate creator must not overwrite', async t => {
  const f = await fixture(); t.after(f.cleanup)
  const original = document('first')
  const result = await saveNativeProjectCAS(f.file, original, null)
  assert.equal(result.sha256, sourceSha256(Buffer.from(original)))
  await assert.rejects(saveNativeProjectCAS(f.file, document('lost'), null), {
    code: 'ZX7_STALE_PROJECT',
  })
  assert.equal(await fs.readFile(f.file, 'utf8'), original)
})

test('stale editor is refused after independent human commit', async t => {
  const f = await fixture(); t.after(f.cleanup)
  const original = (await saveNativeProjectCAS(f.file, document('source'), null)).sha256
  const updated = document('human edit', '2026-11-13T00:01:00.000Z')
  const newHead = await saveNativeProjectCAS(f.file, updated, original)
  assert.notEqual(newHead.sha256, original)
  await assert.rejects(saveNativeProjectCAS(f.file, document('stale AI'), original), {
    code: 'ZX7_STALE_PROJECT',
  })
  assert.equal(await fs.readFile(f.file, 'utf8'), updated)
})

test('two real independent OS writers never both commit from one source SHA', async t => {
  const f = await fixture(); t.after(f.cleanup)
  const baseline = (await saveNativeProjectCAS(f.file, document('source'), null)).sha256
  const modulePath = path.join(__dirname, 'nativeProjectCAS.cjs')
  const childScript = `const m=require(process.argv[1]);m.saveNativeProjectCAS(process.argv[2],process.argv[3],process.argv[4]).then(()=>process.exit(0),e=>{console.error(e.code);process.exit(1)})`
  const results = await Promise.all(['A', 'B'].map(label =>
    runNode(childScript, modulePath, f.file, document(label), baseline)))
  assert.deepEqual(results.map(x => x.code).sort(), [0, 1], JSON.stringify(results))
  const saved = JSON.parse(await fs.readFile(f.file, 'utf8'))
  assert.ok(['A', 'B'].includes(saved.name))
})

test('cross-process lock survives child flock exit and is released by exact process SIGKILL', async t => {
  const f = await fixture(); t.after(f.cleanup)
  const baseline = (await saveNativeProjectCAS(f.file, document('first'), null)).sha256
  const modulePath = path.join(__dirname, 'nativeProjectCAS.cjs')
  const script = `const m=require(process.argv[1]);m.withNativeProjectLock(process.argv[2],()=>{console.log('HELD');return new Promise(()=>setInterval(()=>{},1000))})`
  const child = spawn(process.execPath, ['-e', script, modulePath, f.file], {
    stdio: ['ignore', 'pipe', 'pipe'],
  })
  t.after(() => { if (!child.killed) child.kill('SIGKILL') })
  await new Promise((resolve, reject) => {
    let out = ''
    child.stdout.on('data', d => { out += d; if (out.includes('HELD')) resolve() })
    child.once('error', reject)
  })
  await assert.rejects(saveNativeProjectCAS(f.file, document('conflict'), baseline), {
    code: 'ZX7_PROJECT_BUSY',
  })
  child.kill('SIGKILL')
  await new Promise(resolve => child.once('close', resolve))
  assert.equal((await saveNativeProjectCAS(f.file, document('after death'), baseline)).committed, true)
  assert.equal(JSON.parse(await fs.readFile(f.file, 'utf8')).name, 'after death')
})

test('native writer rejects symlink targets without touching private source', async t => {
  const f = await fixture(); t.after(f.cleanup)
  const original = path.join(f.scratch, 'original.txt')
  await fs.writeFile(original, 'PRIVATE')
  await fs.symlink(original, f.file)
  await assert.rejects(saveNativeProjectCAS(f.file, document('evil'),
    sourceSha256(Buffer.from('PRIVATE'))))
  assert.equal(await fs.readFile(original, 'utf8'), 'PRIVATE')
})
