// SPDX-License-Identifier: GPL-3.0-only
// Contract-first: exact native source effects, audio and revision tests also run in Electron.
import test from 'node:test'
import assert from 'node:assert/strict'
import { planLossAwareNativeExtract } from './zx7-loss-aware-extract.mjs'
const tracks = [
  { id: 'video-1', type: 'video' }, { id: 'audio-1', type: 'audio' },
]
const source = (change = {}) => ({
  id: 'clip-1', trackId: 'video-1', assetId: 'original-v',
  type: 'video', startTime: 0, duration: 8, sourceDuration: 12,
  trimStart: 1, trimEnd: 9, speed: 1, sourceTimeScale: 1,
  enabled: true, transform: { positionX: 5, opacity: 100 }, ...change,
})
const audio = (change = {}) => source({
  id: 'clip-2', trackId: 'audio-1', assetId: 'original-a',
  type: 'audio', trimStart: 0, trimEnd: 8, ...change,
})
const extract = (clips, opts = {}) => planLossAwareNativeExtract({
  clips, tracks, transitions: [], markers: [], fps: 24,
  clipCounter: 10, startSeconds: 2, endSeconds: 4, ripple: true, ...opts,
})
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-8,
  String(a) + ' != ' + String(b))
test('one atomic ripple keeps both original source windows but not deleted media', () => {
  const original = source(), initial = structuredClone(original)
  const result = extract([original])
  assert.equal(result.ok, true, result.reason)
  assert.deepEqual(original, initial)
  assert.equal(result.clips.length, 2)
  const [left, right] = result.clips
  assert.equal(left.id, 'clip-1')
  near(left.startTime, 0); near(left.duration, 2)
  near(left.trimStart, 1); near(left.trimEnd, 3)
  near(right.startTime, 2); near(right.duration, 4)
  near(right.trimStart, 5); near(right.trimEnd, 9)
  assert.equal(right.assetId, original.assetId)
  assert.notEqual(right.transform, original.transform)
  assert.equal(result.deltaSeconds, 2)
  assert.equal(result.removedClipIds.length, 1)
})
test('non-ripple creates a real gap and does not move later sources', () => {
  const later = source({ id: 'clip-5', startTime: 10, duration: 1,
    trimStart: 0, trimEnd: 1, sourceDuration: 2 })
  const result = extract([source(), later], { ripple: false })
  assert.equal(result.ok, true, result.reason)
  assert.deepEqual(result.clips.map(x => x.startTime), [0, 4, 10])
})
test('ripple preserves source-relative keyframes on future clips', () => {
  const later = source({ id: 'clip-5', startTime: 10, duration: 2,
    trimStart: 0, trimEnd: 2, sourceDuration: 2,
    keyframes: { opacity: [
      { time: 0, value: 30, easing: 'easeInOut' },
      { time: 2, value: 80, easing: 'hold' },
    ] } })
  const result = extract([source(), later])
  assert.equal(result.ok, true, result.reason)
  const moved = result.clips.find(x => x.id === later.id)
  near(moved.startTime, 8)
  assert.deepEqual(moved.keyframes, later.keyframes)
  assert.notEqual(moved.keyframes, later.keyframes)
})
test('clip-local picture curves and sound automation keep their original phase', () => {
  const pic = source({ keyframes: { opacity: [
    { time: 0, value: 0, easing: 'cubic-bezier(0.1,0.2,0.8,1)' },
    { time: 8, value: 100, easing: 'linear' },
  ] } })
  const snd = audio({ gainDb: -3, fadeIn: 1, fadeOut: 1,
    audioEq: { enabled: true, bands: [] },
    volumeEnvelope: { version: 1, offsetSeconds: 0.25,
      points: [{ id: 'g1', time: 0, db: -2 }, { id: 'g2', time: 7, db: 3 }] },
  })
  const result = extract([pic, snd])
  assert.equal(result.ok, true, result.reason)
  const picRight = result.clips.find(x => x.type === 'video' && x.startTime === 2)
  const sndRight = result.clips.find(x => x.type === 'audio' && x.startTime === 2)
  assert.deepEqual(picRight.keyframes.opacity.map(x => x.time), [-4, 4])
  near(sndRight.volumeEnvelope.offsetSeconds, 4.25)
  assert.deepEqual(sndRight.volumeEnvelope.points, snd.volumeEnvelope.points)
  assert.equal(sndRight.fadeIn, 0); assert.equal(sndRight.fadeOut, 1)
})
test('linked original video/audio survive with correctly rekeyed new right group', () => {
  const pic = source({ metadata: { linkedAudioClipId: 'clip-2' },
    linkGroupId: 'original-link' })
  const snd = audio({ metadata: { linkedVideoClipId: 'clip-1' },
    linkGroupId: 'original-link' })
  const result = extract([pic, snd])
  assert.equal(result.ok, true, result.reason)
  assert.equal(result.clips.length, 4)
  const byId = new Map(result.clips.map(c => [c.id, c]))
  assert.equal(byId.get('clip-1').metadata.linkedAudioClipId, 'clip-2')
  assert.equal(byId.get('clip-2').metadata.linkedVideoClipId, 'clip-1')
  const rightPic = result.clips.find(c => c.type === 'video' && c.startTime === 2)
  const rightAudio = result.clips.find(c => c.type === 'audio' && c.startTime === 2)
  assert.equal(rightPic.linkGroupId, rightAudio.linkGroupId)
  assert.notEqual(rightPic.linkGroupId, 'original-link')
  assert.equal(rightPic.metadata.linkedAudioClipId, rightAudio.id)
  assert.equal(rightAudio.metadata.linkedVideoClipId, rightPic.id)
})
test('explicit track-local non-ripple cannot modify an unrelated picture', () => {
  const original = source({ keyframes: { positionX: [
    { time: 0, value: 1 }, { time: 8, value: 20 },
  ] } })
  const result = extract([original, audio()],
    { trackIds: ['audio-1'], ripple: false })
  assert.equal(result.ok, true, result.reason)
  assert.deepEqual(result.clips.find(c => c.id === original.id), original)
  assert.equal(result.clips.filter(c => c.type === 'audio').length, 2)
  assert.deepEqual(result.affectedTrackIds, ['audio-1'])
})
test('reverse retime preserves the playback-ordered original source positions', () => {
  const result = extract([source({ reverse: true, speed: 2,
    sourceTimeScale: 0.5, trimStart: 2, trimEnd: 10 })])
  assert.equal(result.ok, true, result.reason)
  near(result.clips[0].trimStart, 8)
  near(result.clips[0].trimEnd, 10)
  near(result.clips[1].trimStart, 2)
  near(result.clips[1].trimEnd, 6)
})
test('native fps snaps interval once at the boundary', () => {
  const result = extract([source()], { startSeconds: 2.004, endSeconds: 3.996 })
  assert.equal(result.ok, true, result.reason)
  near(result.startSeconds, 2); near(result.endSeconds, 4)
  near(result.clips[0].duration, 2)
  near(result.clips[1].startTime, 2)
})
test('creative state that cannot be preserved fails without any replacement clips', () => {
  const linked = source({ linkGroupId: 'a', metadata: { linkedAudioClipId: 'clip-2' } })
  const cases = [
    [[source({ effects: [{ id: 'fx', name: 'temporal' }] })], {}],
    [[source({ keyframes: { speed: [{ time: 0, value: 1 }] } })], {}],
    [[source({ unknownMovieEffectPhase: 55 })], {}],
    [[audio({ fadeIn: 3 })], {}],
    [[source()], { tracks: [{ ...tracks[0], locked: true }, tracks[1] } }],
    [[source()], { transitions: [{ id: 't', clipAId: 'clip-1' }] }],
    [[source()], { markers: [{ id: 'beat', time: 7 }] }],
    [[linked, audio({ metadata: { linkedVideoClipId: 'clip-1' }, linkGroupId: 'a' })],
      { trackIds: ['video-1'] }],
    [[source()], { startSeconds: 4, endSeconds: 2 }],
    [[source()], { startSeconds: 3, endSeconds: 3 }],
  ]
  for (const [clips, args] of cases) {
    const initial = structuredClone(clips)
    const result = extract(clips, args)
    assert.equal(result.ok, false, JSON.stringify(args))
    assert.equal(result.clips, undefined)
    assert.deepEqual(clips, initial)
  }
})
test('input validation rejects missing, duplicate and unrepresentable targets', () => {
  for (const override of [
    { trackIds: ['not-a-track'] }, { trackIds: ['audio-1', 'audio-1'] },
    { trackIds: [] }, { fps: 0 }, { fps: 1000 },
    { clipCounter: -1 }, { ripple: 'true' }, { startSeconds: NaN },
  ]) assert.equal(extract([source()], override).ok, false)
  assert.equal(extract([source()],
    { startSeconds: 9, endSeconds: 10, ripple: false }).ok, false)
})
