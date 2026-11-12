// Test the actual pinned Electron MCP read ABI used by Python host identity
// admission. This tests source observations, not model creativity or real GUI.
import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { createComfyStudioMcpServer } =
  require('../../third_party/velorn/electron/mcpServer.js')

const snapshot = ({clipId='clip-A', assetId='asset-A', generation='fixture-1'}={}) => ({
  app: { name: 'Velorn' },
  project: { name: 'native-project-1', currentTimelineId: 'timeline-1' },
  currentTimeline: {
    id: 'timeline-1', name: 'Native', fps: 24, duration: 6,
    playheadPosition: 0, generatedAt: generation,
    tracks: [{ id: 'video-1', type: 'video', name: 'Video' }],
    clips: [{ id: clipId, trackId: 'video-1', assetId }],
    markers: [],
  },
  assets: [{ id: assetId, name: 'source-original.mp4', type: 'video' }],
  timelines: [],
  generatedAt: generation,
})

async function observed(server, tool, inputs) {
  const result = await server.callTool(tool, inputs)
  assert.notEqual(result.isError, true, tool + ' failed')
  assert.equal(result.content?.length, 1)
  assert.equal(result.content[0].type, 'text')
  return JSON.parse(result.content[0].text)
}

test('Real upstream get_project/get_timeline/get_assets supply source ID evidence', async () => {
  const actions = []
  const server = createComfyStudioMcpServer({
    performAction: async action => { actions.push(action); return {applied:true} },
  })
  server.updateSnapshot(snapshot())
  const before = await observed(server, 'get_project', {})
  const timeline = await observed(server, 'get_timeline', {includeClips:true,limit:1000})
  const assets = await observed(server, 'get_assets', {limit:1000})
  const after = await observed(server, 'get_project', {})
  assert.equal(Object.hasOwn(before.project, 'id'), false,
    'Real Velorn project snapshot does not expose project.id')
  assert.equal(before.project.name, 'native-project-1')
  assert.equal(before.project.currentTimelineId, 'timeline-1')
  assert.equal(before.mcp.hasProject, true)
  assert.equal(before.currentTimeline.id, 'timeline-1')
  assert.equal(before.currentTimeline.clipCount, 1)
  assert.equal(before.currentTimeline.trackCount, 1)
  assert.equal(before.assetCount, 1)
  assert.equal(typeof before.generatedAt, 'string')
  assert.equal(before.generatedAt, after.generatedAt)
  assert.equal(timeline.clipLimitApplied, false)
  assert.deepEqual(timeline.clips.map(c => c.id), ['clip-A'])
  assert.deepEqual(timeline.tracks.map(t => t.id), ['video-1'])
  assert.equal(assets.limitApplied, false)
  assert.equal(assets.count, 1)
  assert.deepEqual(assets.assets.map(a => a.id), ['asset-A'])
  assert.deepEqual(actions, [], 'Read-only inventory must never call performAction')
})

test('Real upstream reflects human project changes instead of preserving stale IDs', async () => {
  const server = createComfyStudioMcpServer({
    performAction: async () => { throw new Error('No writer expected') },
  })
  server.updateSnapshot(snapshot())
  const earlier = await observed(server, 'get_timeline', {includeClips:true,limit:1000})
  server.updateSnapshot(snapshot({clipId:'human-replacement',
                                  assetId:'asset-human',generation:'fixture-2'}))
  const updated = await observed(server, 'get_timeline', {includeClips:true,limit:1000})
  const assets = await observed(server, 'get_assets', {limit:1000})
  const project = await observed(server, 'get_project', {})
  assert.deepEqual(earlier.clips.map(x => x.id), ['clip-A'])
  assert.deepEqual(updated.clips.map(x => x.id), ['human-replacement'])
  assert.deepEqual(assets.assets.map(x => x.id), ['asset-human'])
  assert.notEqual(project.generatedAt, 'fixture-1')
})
