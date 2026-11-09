// Exercise the EXACT pinned upstream Electron MCP entrypoint, not a fake
// renderer helper. This is a safe preview/protocol test, not neural creativity.
import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { execFileSync } from 'node:child_process'
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

test('Pinned Electron MCP asset placement default preview is read-only and returns explicit apply call', async () => {
  const { server, applied } = nativeSession()
  server.updateSnapshot({
    app: { name: 'Velorn' },
    project: { id: 'source-pinned-native-fixture' },
    currentTimeline: {
      id: 'actual-timeline',
      fps: 24,
      duration: 10,
      playheadPosition: 0,
      clips: [],
      tracks: [{ id: 'video-1', type: 'video', name: 'Video 1', locked: false }],
      markers: [],
    },
    assets: [
      { id: 'native-asset-1', name: 'owned-neutral.mp4', type: 'video',
        duration: 4, width: 640, height: 360, hasAudio: false },
    ],
    timelines: [],
  })
  const requests = [
    ['add_asset_to_timeline', { assetId: 'native-asset-1', startSeconds: 0 }],
    ['add_assets_to_timeline', { assetIds: ['native-asset-1'],
                                  layout: 'sequential', startSeconds: 0 }],
  ]
  for (const [tool, args] of requests) {
    const receipt = nativeText(await server.callTool(tool, args))
    assert.equal(receipt.previewOnly, true)
    assert.equal(receipt.action, tool)
    assert.equal(typeof receipt.message, 'string')
    assert.equal(receipt.plan?.action, tool)
    assert.equal(receipt.plan?.previewOnly, true)
    assert.equal(receipt.suggestedApplyCall?.tool, tool)
    assert.equal(receipt.suggestedApplyCall?.arguments?.previewOnly, false)
    assert.equal('success' in receipt, false)
    assert.equal('result' in receipt, false)
    assert.deepEqual(applied, [], tool + ': default preview MUST NOT call renderer')
  }
  // The test explicitly selects the editor's own suggestedApplyCall;
  // production creative choice belongs only to the real model.
  const preview = nativeText(await server.callTool(
    'add_asset_to_timeline', { assetId: 'native-asset-1', previewOnly: true }))
  const result = nativeText(await server.callTool(
    preview.suggestedApplyCall.tool, preview.suggestedApplyCall.arguments))
  assert.equal(result.success, true)
  assert.equal(result.action, 'add_asset_to_timeline')
  assert.equal(applied.length, 1)
  assert.equal(applied[0].action, 'add_asset_to_timeline')
})

test('Pinned Electron MCP returns genuine JPEG as editable timeline preview, not export', async () => {
  // Real byte-producing FFmpeg decoder/encoder fixture. The stubbed renderer
  // is NOT an autonomous edit or verified exported MP4.
  const jpeg = execFileSync('ffmpeg', [
    '-nostdin', '-v', 'error', '-f', 'lavfi',
    '-i', 'color=c=blue:s=32x24:r=1:d=1', '-frames:v', '1',
    '-c:v', 'mjpeg', '-f', 'image2pipe', '-'
  ], { maxBuffer: 1024 * 1024, timeout: 15000 })
  assert.equal(jpeg.subarray(0, 3).toString('hex'), 'ffd8ff')
  assert.equal(jpeg.subarray(-2).toString('hex'), 'ffd9')
  let rendererCalls = 0
  const server = createComfyStudioMcpServer({
    performAction: async ({ action, payload }) => {
      assert.equal(action, 'inspect_timeline_frame')
      assert.equal(payload.mimeType, 'image/jpeg')
      rendererCalls += 1
      return {
        renderer: 'live',
        image: { mimeType: 'image/jpeg', data: jpeg.toString('base64') },
      }
    },
  })
  server.updateSnapshot({
    app: { name: 'Velorn' },
    project: { id: 'real-jpeg-source-fixture',
               currentTimelineId: 'native-timeline-1' },
    currentTimeline: {
      id: 'native-timeline-1', name: 'Preview', fps: 24,
      duration: 4, playheadPosition: 0,
      clips: [], tracks: [], markers: [],
    },
    assets: [], timelines: [],
  })
  const response = await server.callTool('inspect_timeline_frame', {
    timeSeconds: 0, includeImage: true,
  })
  assert.equal(response.isError, undefined)
  assert.equal(response.content.length, 2)
  const metadata = JSON.parse(response.content[0].text)
  assert.equal(metadata.timeline.id, 'native-timeline-1')
  assert.equal(metadata.capture.imageIncluded, true)
  assert.equal(metadata.capture.renderer, 'live')
  assert.equal(metadata.frame.frame, 0)
  assert.equal(metadata.activeClipCount, 0)
  assert.equal(response.content[1].type, 'image')
  assert.equal(response.content[1].mimeType, 'image/jpeg')
  assert.deepEqual(Buffer.from(response.content[1].data, 'base64'), jpeg)
  assert.equal(rendererCalls, 1)
  assert.equal(Object.hasOwn(metadata, 'export_sha256'), false)
})

test('Real pinned Electron native clip move/trim/delete defaults are no-write plans', async () => {
  const { server, applied } = nativeSession()
  server.updateSnapshot({
    app: { name: 'Velorn' },
    project: { id: 'source-pinned-native-fixture',
               currentTimelineId: 'native-active-timeline' },
    currentTimeline: {
      id: 'native-active-timeline', fps: 24, duration: 5,
      playheadPosition: 0, markers: [],
      tracks: [{ id: 'video-1', name: 'Real Video', type: 'video',
                 locked: false, visible: true }],
      clips: [{ id: 'native-clip-1', trackId: 'video-1', assetId: 'original-1',
                type: 'video', startTime: 0, duration: 4, enabled: true }],
    },
    assets: [{ id: 'original-1', name: 'Owned original.mp4',
               type: 'video', duration: 4 }],
    timelines: [],
  })
  const requests = [
    ['move_clips', { clipId: 'native-clip-1', startSeconds: 1.25 }],
    ['trim_clips', { clipId: 'native-clip-1', durationSeconds: 2.5 }],
    ['delete_clips', { clipId: 'native-clip-1' }],
  ]
  const messages = {
    move_clips: 'Clip move plan only. No timeline change was made.',
    trim_clips: 'Clip trim plan only. No timeline change was made.',
    delete_clips: 'Clip delete plan only. No timeline change was made.',
  }
  for (const [tool, args] of requests) {
    const receipt = nativeText(await server.callTool(tool, args))
    assert.equal(receipt.previewOnly, true)
    assert.equal(receipt.action, tool)
    assert.equal(receipt.message, messages[tool])
    assert.equal(Object.hasOwn(receipt, 'success'), false)
    assert.equal(Object.hasOwn(receipt, 'result'), false)
    assert.equal(receipt.suggestedApplyCall.tool, tool)
    assert.equal(receipt.suggestedApplyCall.arguments.previewOnly, false)
    assert.equal(typeof receipt.plan, 'object')
    assert.deepEqual(applied, [], tool + ': default plan must not call renderer')
  }
  // Explicit application is a different, independently chosen operation.
  const preview = nativeText(await server.callTool('move_clips', requests[0][1]))
  const appliedResponse = nativeText(await server.callTool(
    preview.suggestedApplyCall.tool, preview.suggestedApplyCall.arguments))
  assert.equal(appliedResponse.success, true)
  assert.equal(appliedResponse.action, 'move_clips')
  assert.equal(applied.length, 1)
  assert.equal(applied[0].action, 'move_clips')
})


test('Pinned native default preview failures dispatch zero renderer edits', async () => {
  const { server, applied } = nativeSession()
  for (const [tool, args] of [
    ['add_asset_to_timeline', { assetName: 'not-imported.mp4' }],
    ['add_assets_to_timeline', { assetNames: ['not-imported.mp4'] }],
    ['move_clips', { clipId: 'nonexistent-clip', startSeconds: 1 }],
    ['trim_clips', { clipId: 'nonexistent-clip', durationSeconds: 1 }],
  ]) {
    for (const input of [args, { ...args, previewOnly: true }]) {
      const receipt = await server.callTool(tool, input)
      assert.equal(receipt.isError, true, tool + ': native error expected')
      assert.equal(receipt.content.length, 1)
      assert.equal(receipt.content[0].type, 'text')
      assert.deepEqual(applied, [], tool + ': failed preview MUST NOT dispatch a renderer edit')
    }
  }
})
