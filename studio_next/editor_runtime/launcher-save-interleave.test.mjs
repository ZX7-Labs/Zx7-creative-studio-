// SPDX-License-Identifier: GPL-3.0-only
// The source hash is not enough to admit a synthetic fault-injection child.
import test from 'node:test'
import assert from 'node:assert/strict'
import { isIsolatedNativeSaveInterleaveSource } from './launcher.mjs'
import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'

test('test-only native source admission requires isolated exact-Xvfb workspace', () => {
  const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'zx7-editor-mcp-gate-'))
  try {
    const root = path.join(fixture, 'projects')
    const gate = path.join(fixture, 'native-save-interleave-gate')
    fs.mkdirSync(root)
    fs.mkdirSync(gate)
    const sourceLock = JSON.parse(fs.readFileSync(new URL('./source-lock.json', import.meta.url)))
    const known = sourceLock.collab_save_interleave_revision
    assert.match(known, /^[0-9a-f]{40}$/)
    const props = {
      revision: known,
      projectsRoot: root,
      xvfbBinary: '/usr/bin/Xvfb',
      display: '127.0.0.1:97',
      environment: {
        CI: 'true',
        ZX7_CI_NATIVE_SAVE_PROJECTS_ROOT: root,
        ZX7_CI_NATIVE_SAVE_GATE_DIR: gate,
      },
    }
    assert.equal(isIsolatedNativeSaveInterleaveSource(props), true)
    assert.equal(isIsolatedNativeSaveInterleaveSource({...props, revision: sourceLock.collab_save_order_revision}), false)
    assert.equal(isIsolatedNativeSaveInterleaveSource({...props, environment: {...props.environment, CI: 'false'}}), false)
    assert.equal(isIsolatedNativeSaveInterleaveSource({...props, display: '127.0.0.1:98'}), false)
    assert.equal(isIsolatedNativeSaveInterleaveSource({...props, xvfbBinary: null}), false)
    assert.equal(isIsolatedNativeSaveInterleaveSource({...props, projectsRoot: '/tmp/private-project'}), false)
    assert.equal(isIsolatedNativeSaveInterleaveSource({...props, environment: {...props.environment, ZX7_CI_NATIVE_SAVE_GATE_DIR: '/tmp/foreign'}}), false)
    assert.equal(isIsolatedNativeSaveInterleaveSource({...props, environment: {...props.environment, ZX7_CI_NATIVE_SAVE_PROJECTS_ROOT: '/tmp/foreign'}}), false)
  } finally { fs.rmSync(fixture, {recursive: true, force: true}) }
})
