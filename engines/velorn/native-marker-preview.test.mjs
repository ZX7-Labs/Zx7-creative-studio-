// Exercise the EXACT pinned upstream Electron MCP entrypoint, not a fake
// renderer helper. This is a safe preview/protocol test, not neural creativity.
import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { createComfyStudioMcpServer } = require('../../third_party/velorn/electron/mcpServer.js')

function nativeSession() {
  const applied = []
  const server = createComfyStudioMcpServer({
    performAction: async (operation) => {
      applied.push(operation)
      return { applied: true }
    },
  })
  server.updateSnapshot({
    app: { name: 'Velorn' },
    project: { id: 'source-pinned-native-fixture' },
    currentTimeline: {
      id: 'actual-timeline',
      fps: 24,
      duration: 10,
      playheadPosition: 0,
      clips: [],
      tracks: [],
      markers: [{ id: 'native-marker-1', time: 2,
                  label: 'Original', color: '#ff8800' }],
    },
    assets: [],
    timelines: [],
  })
  return { server, applied }
}

function nativeText(result) {
  assert.notEqual(result.isError, true, 'Native preview unexpectedly failed')
  assert.equal(result.content.length, 1)
  assert.equal(result.content[0].type, 'text')
  return JSON.parse(result.content[0].text)
}

test('Pinned Electron MCP add/remove/update marker preview is truly read-only', async () => {
  const { server, applied } = nativeSession()
  const requests = [
    ['add_timeline_markers', {
      markers: [{ timeSeconds: 2, label: 'New marker' }],
      previewOnly: true,
    }],
    ['remove_timeline_markers', {
      markerIds: ['native-marker-1'], previewOnly: true,
    }],
    ['set_timeline_marker_properties', {
      markerIds: ['native-marker-1'], label: 'Revised',
      previewOnly: true,
    }],
  ]
  for (const [name, args] of requests) {
    const receipt = nativeText(await server.callTool(name, args))
    assert.equal(receipt.previewOnly, true)
    assert.equal(receipt.markerCount, 1)
    assert.equal(receipt.markers.length, 1)
    assert.equal('success' in receipt, false)
    assert.equal('action' in receipt, false)
    assert.equal('result' in receipt, false)
    assert.deepEqual(applied, [], name + ': preview MUST NOT call renderer')
  }
})

test('Native marker commit crosses renderer boundary only when model selects application', async () => {
  const { server, applied } = nativeSession()
  const requested = { markers: [{ timeSeconds: 2, label: 'Apply' }],
                      previewOnly: false }
  const result = nativeText(await server.callTool('add_timeline_markers', requested))
  assert.equal(result.success, true)
  assert.equal(result.action, 'add_timeline_markers')
  assert.equal(applied.length, 1)
  assert.equal(applied[0].action, 'add_timeline_markers')
  assert.equal(applied[0].payload.markers.length, 1)
})
