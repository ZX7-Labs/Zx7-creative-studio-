// SPDX-License-Identifier: GPL-3.0-only
// Contract-first regression tests for opt-in native loss-aware editorial edits.
import test from 'node:test'
import assert from 'node:assert/strict'
import { planLossAwareNativeSplit } from './zx7-loss-aware-split.mjs'

const base = (overrides = {}) => ({
  id: 'clip-1', trackId: 'video-1', assetId: 'asset-1', type: 'video',
  name: 'Source', startTime: 0, duration: 8, sourceDuration: 12,
  trimStart: 1, trimEnd: 9, speed: 1, sourceTimeScale: 1,
  transform: { positionX: 0, opacity: 100 }, enabled: true,
  ...overrides,
})
const tracks = [{ id: 'video-1', type: 'video' }, { id: 'audio-1', type: 'audio' }]
const call = (clips, opts = {}) => planLossAwareNativeSplit({
  clips, tracks, transitions: [], timeSeconds: 3, fps: 24, clipCounter: 2, ...opts,
})
const near = (a, b) => assert.ok(Math.abs(a - b) < 1e-9, `${a} !== ${b}`)

test('frame-aligned razor retains original source interval and timeline on both sides', () => {
  const original = base()
  const plan = call([original])
  assert.equal(plan.ok, true, plan.reason)
  assert.deepEqual(original, base(), 'input timeline must never be mutated')
  assert.deepEqual(plan.splits.map(s => [s.leftClipId, s.rightClipId]), [['clip-1', 'clip-2']])
  const [left, right] = plan.clips
  assert.equal(left.id, 'clip-1')
  assert.equal(right.id, 'clip-2')
  assert.equal(left.duration, 3)
  assert.equal(right.startTime, 3)
  assert.equal(right.duration, 5)
  near(left.trimStart, 1); near(left.trimEnd, 4)
  near(right.trimStart, 4); near(right.trimEnd, 9)
  assert.deepEqual(right.transform, original.transform)
  assert.notEqual(right.transform, original.transform)
  assert.deepEqual(plan.selectedClipIds, ['clip-2'])
  assert.equal(plan.clipCounter, 3)
})

test('right-side keyframes retain full original interpolation including eased curve crossing cut', () => {
  const authored = base({ keyframes: {
    positionX: [{ time: 0, value: 0, easing: 'easeInOut' }, { time: 8, value: 100, easing: 'hold' }],
    opacity: [{ time: 2, value: 40, easing: 'linear' }, { time: 6, value: 90, easing: 'linear' }],
  } })
  const plan = call([authored])
  assert.equal(plan.ok, true, plan.reason)
  const [left, right] = plan.clips
  assert.deepEqual(left.keyframes, authored.keyframes)
  assert.deepEqual(right.keyframes.positionX.map(k => k.time), [-3, 5])
  assert.deepEqual(right.keyframes.opacity.map(k => k.time), [-1, 3])
  assert.equal(right.keyframes.opacity[0].easing, 'linear')
  right.keyframes.opacity[0].value = 999
  assert.equal(authored.keyframes.opacity[0].value, 40, 'no shared editable curve state')
})

test('audio cut retains EQ, envelope time coordinates, gain and only surviving edge fades', () => {
  const audio = base({ id: 'clip-9', type: 'audio', trackId: 'audio-1',
    assetId: 'asset-a', trimStart: 0, trimEnd: 8, gainDb: -4,
    fadeIn: 1, fadeOut: 1, audioEq: { enabled: true, bands: [] },
    volumeEnvelope: { version: 1, offsetSeconds: 0.5,
      points: [{ id: 'a', time: 1, db: -8 }, { id: 'b', time: 6, db: 2 }] },
  })
  const plan = call([audio])
  assert.equal(plan.ok, true, plan.reason)
  const [left, right] = plan.clips
  assert.equal(left.fadeIn, 1)
  assert.equal(left.fadeOut, 0)
  assert.equal(right.fadeIn, 0)
  assert.equal(right.fadeOut, 1)
  assert.equal(right.volumeEnvelope.offsetSeconds, 3.5)
  assert.deepEqual(right.volumeEnvelope.points, audio.volumeEnvelope.points)
  assert.notEqual(right.audioEq, audio.audioEq)
  assert.equal(right.gainDb, -4)
})
test('cuts inside unrepresentable edge fades and unknown effects refuse atomically', () => {
  for (const clip of [
    base({ type: 'audio', trackId: 'audio-1', fadeIn: 4 }),
    base({ type: 'audio', trackId: 'audio-1', fadeOut: 6 }),
    base({ effects: [{ id: 'film', type: 'filmGrain', settings: {} }] }),
    base({ keyframes: { speed: [{ time: 0, value: 1 }, { time: 8, value: 2 }] } }),
    base({ speedRamp: [{ time: 0, speed: 1 }] }),
  ]) {
    const before = structuredClone(clip)
    const plan = call([clip])
    assert.equal(plan.ok, false, JSON.stringify(clip))
    assert.equal(plan.clips, undefined, 'refusal returns no replacement timeline')
    assert.deepEqual(clip, before)
  }
})
test('reverse retime divides source range in playback order without duplicating source', () => {
  const clip = base({ trimStart: 2, trimEnd: 10, sourceDuration: 12,
    speed: 2, sourceTimeScale: 0.5, reverse: true })
  const plan = call([clip])
  assert.equal(plan.ok, true, plan.reason)
  const [left, right] = plan.clips
  assert.equal(left.reverse, true)
  assert.equal(right.reverse, true)
  near(left.trimStart, 7); near(left.trimEnd, 10)
  near(right.trimStart, 2); near(right.trimEnd, 7)
})
test('linked video + audio split together, right-side group and metadata rewire', () => {
  const video = base({ metadata: { linkedAudioClipId: 'clip-3' }, linkGroupId: 'group-a' })
  const audio = base({ id: 'clip-3', trackId: 'audio-1', type: 'audio',
    metadata: { linkedVideoClipId: 'clip-1' }, linkGroupId: 'group-a' })
  const plan = call([video, audio], { clipIds: ['clip-1', 'clip-3'], clipCounter: 4 })
  assert.equal(plan.ok, true, plan.reason)
  const rightVideo = plan.clips.find(c => c.id === 'clip-4')
  const rightAudio = plan.clips.find(c => c.id === 'clip-5')
  assert.equal(rightVideo.linkGroupId, rightAudio.linkGroupId)
  assert.notEqual(rightVideo.linkGroupId, 'group-a')
  assert.equal(rightVideo.metadata.linkedAudioClipId, rightAudio.id)
  assert.equal(rightAudio.metadata.linkedVideoClipId, rightVideo.id)
  assert.equal(plan.clips.find(c => c.id === 'clip-1').metadata.linkedAudioClipId, 'clip-3')
})
test('linked incomplete set, transition, locked partner, duplicate id and subframe cut refuse', () => {
  const video = base({ linkGroupId: 'g' })
  const audio = base({ id: 'clip-3', type: 'audio', trackId: 'audio-1', linkGroupId: 'g' })
  for (const bad of [
    call([video, audio], { clipIds: ['clip-1'] }),
    call([video], { transitions: [{ id: 't', clipAId: 'clip-1' }] }),
    call([video, audio], { clipIds: ['clip-1', 'clip-3'],
      tracks: [{ id: 'video-1' }, { id: 'audio-1', locked: true }] }),
    call([base(), base()]),
    call([base()], { timeSeconds: 1 / 100 }),
    call([base()], { clipIds: ['missing'] }),
  ]) assert.equal(bad.ok, false)
})
test('preview and invalid request never allocate ids or mutate the store', () => {
  const clip = base()
  const a = call([clip], { timeSeconds: 3.01 })
  assert.equal(a.ok, true)
  assert.equal(a.timeSeconds, 3)
  const b = call([clip], { clipIds: [] })
  assert.equal(b.ok, false)
  assert.equal(clip.duration, 8)
})
