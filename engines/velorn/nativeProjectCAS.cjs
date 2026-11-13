'use strict'
// SPDX-License-Identifier: GPL-3.0-only
// Linux source-native project saves: filesystem SHA compare under a kernel
// open-file-description lock, not an app-local mutex or stale wall-clock lease.
const fs = require('node:fs/promises')
const { constants } = require('node:fs')
const { spawn } = require('node:child_process')
const crypto = require('node:crypto')
const path = require('node:path')
const MAX_PROJECT_BYTES = 128 * 1024 * 1024
const SOURCE_FILE = 'project.comfystudio'
const SHA256 = /^[a-f0-9]{64}$/
const sourceSha256 = data => crypto.createHash('sha256').update(data).digest('hex')
const nativeError = (code, message) => Object.assign(new Error(message), { code })

const acquireKernelFlock = (fd) => new Promise((resolve, reject) => {
  const child = spawn('flock', ['--exclusive', '--nonblock', '3'], {
    stdio: ['ignore', 'ignore', 'pipe', fd],
  })
  let settled = false
  child.once('error', error => {
    if (settled) return
    settled = true
    reject(nativeError('ZX7_FLOCK_UNAVAILABLE', `Linux flock unavailable: ${error.code || 'spawn failure'}`))
  })
  child.once('close', (code, signal) => {
    if (settled) return
    settled = true
    if (code === 0 && !signal) resolve()
    else reject(nativeError('ZX7_PROJECT_BUSY', `Native project writer lock unavailable (${code ?? signal})`))
  })
})

async function withNativeProjectLock(filePath, operation) {
  if (process.platform !== 'linux') throw nativeError('ZX7_OS_UNSUPPORTED', 'Native cross-process save requires Linux flock')
  if (typeof filePath !== 'string' || !path.isAbsolute(filePath) ||
      path.basename(filePath) !== SOURCE_FILE || typeof operation !== 'function') {
    throw nativeError('ZX7_INVALID_TARGET', 'Expected an absolute native project.comfystudio')
  }
  const dir = path.dirname(filePath)
  if (await fs.realpath(dir) !== dir) throw nativeError('ZX7_INVALID_TARGET', 'Native project parent must be a real directory')
  const handle = await fs.open(path.join(dir, '.zx7-native-project.lock'),
    constants.O_CREAT | constants.O_RDWR | constants.O_NOFOLLOW, 0o600)
  try {
    const stat = await handle.stat()
    if (!stat.isFile() || stat.uid !== process.getuid()) {
      throw nativeError('ZX7_UNTRUSTED_LOCK', 'Native lock must be an owner-controlled regular file')
    }
    await acquireKernelFlock(handle.fd)
    // util-linux flock exits but the kernel lock survives on this same
    // open-file-description FD. Kernel releases it on close/process death.
    return await operation()
  } finally {
    await handle.close()
  }
}

async function readRegularNativeProject(filePath) {
  let handle
  try { handle = await fs.open(filePath, constants.O_RDONLY | constants.O_NOFOLLOW) }
  catch (error) { if (error.code === 'ENOENT') return null; throw error }
  try {
    const stat = await handle.stat()
    if (!stat.isFile() || stat.size > MAX_PROJECT_BYTES) {
      throw nativeError('ZX7_INVALID_SOURCE', 'Native source must be a bounded regular file')
    }
    return await handle.readFile()
  } finally { await handle.close() }
}

async function saveNativeProjectCAS(filePath, content, expectedSha256) {
  if ((expectedSha256 !== null &&
       (typeof expectedSha256 !== 'string' || !SHA256.test(expectedSha256))) ||
      typeof content !== 'string' || Buffer.byteLength(content, 'utf8') > MAX_PROJECT_BYTES) {
    throw nativeError('ZX7_INVALID_REVISION', 'Missing or invalid source revision/content')
  }
  let next
  try { next = JSON.parse(content) }
  catch { throw nativeError('ZX7_INVALID_DOCUMENT', 'Native project JSON is invalid') }
  if (!next || typeof next !== 'object' || Array.isArray(next) ||
      typeof next.created !== 'string' || !Array.isArray(next.timelines)) {
    throw nativeError('ZX7_INVALID_DOCUMENT', 'Native document lacks project identity/timelines')
  }
  const data = Buffer.from(content, 'utf8')
  return withNativeProjectLock(filePath, async () => {
    const previous = await readRegularNativeProject(filePath)
    if ((previous === null && expectedSha256 !== null) ||
        (previous !== null && expectedSha256 === null) ||
        (previous !== null && sourceSha256(previous) !== expectedSha256)) {
      throw nativeError('ZX7_STALE_PROJECT', 'Another editor saved this project; reopen or reconcile before saving')
    }
    if (previous !== null) {
      let original
      try { original = JSON.parse(previous.toString('utf8')) }
      catch { throw nativeError('ZX7_INVALID_SOURCE', 'Committed native source JSON is invalid') }
      if (original?.created !== next.created) {
        throw nativeError('ZX7_DIFFERENT_PROJECT', 'Native project identity changed; refusing replacement')
      }
    }
    const directory = path.dirname(filePath)
    const temporary = path.join(directory, `.zx7-${SOURCE_FILE}.${process.pid}.${crypto.randomBytes(12).toString('hex')}.tmp`)
    let renamed = false
    let fd
    try {
      fd = await fs.open(temporary,
        constants.O_CREAT | constants.O_EXCL | constants.O_WRONLY | constants.O_NOFOLLOW, 0o600)
      await fd.writeFile(data)
      await fd.sync()
      await fd.close()
      fd = undefined
      await fs.rename(temporary, filePath)
      renamed = true
      // A failure after rename but before the directory fsync is uncertain.
      // Return an error, never a success that might invite an unsafe retry.
      const dirFd = await fs.open(directory, constants.O_RDONLY | constants.O_DIRECTORY)
      try { await dirFd.sync() } finally { await dirFd.close() }
      return { sha256: sourceSha256(data), committed: true }
    } finally {
      if (fd) await fd.close()
      if (!renamed) {
        try { await fs.unlink(temporary) }
        catch (e) { if (e.code !== 'ENOENT') throw e }
      }
    }
  })
}
module.exports = { MAX_PROJECT_BYTES, sourceSha256, withNativeProjectLock, saveNativeProjectCAS }
