// SPDX-License-Identifier: GPL-3.0-only
import test from 'node:test'
import assert from 'node:assert/strict'
import { reviewNativeSourceRange, commitReviewedNativeSourceRange } from './zx7-native-range-review.mjs'

const clip = (id, trackId, assetId, type) => ({
  id, trackId, assetId, type,
  startTime: 0, duration: 2, sourceDuration: 3,
  trimStart: 0, trimEnd: 2, speed: 1, sourceTimeScale: 1,
})
const fixtures = () => ({
  clips: [clip('clip-1','video-1','original-v','video'), clip('clip-2','audio-1','original-a','audio')],
  tracks: [{ id: 'video-1', type: 'video', locked: false },
    { id: 'audio-1', type: 'audio', locked: false }],
  transitions: [], markers: [],
  timelineSessionId: 7, timelineId: 'original-native-timeline',
  clipCounter: 3, timelineFps: 24, inPoint: 0.5, outPoint: 0.75,
  rippleEditMode: true, compoundEditContext: null,
})

test('the UI only proposes the same exact supported source-native A/V edit', () => {
  const state=fixtures(), original=structuredClone(state)
  const review=reviewNativeSourceRange(state)
  assert.equal(review.ok, true, review.reason)
  assert.equal(review.removeCount,2)
  assert.equal(review.shiftCount,2)
  assert.equal(review.durationSeconds,.25)
  assert.equal(review.ripple,true)
  assert.deepEqual(review.affectedTrackIds,['video-1','audio-1'])
  assert.deepEqual(state, original, 'preview is read-only')
  const committed=commitReviewedNativeSourceRange(state, review)
  assert.equal(committed.ok,true,committed.reason)
  assert.equal(committed.clips.length,4)
  assert.deepEqual(committed.clips.filter(c=>c.type==='video').map(c=>c.startTime),[0,.5])
  assert.deepEqual(committed.clips.filter(c=>c.type==='audio').map(c=>c.startTime),[0,.5])
  assert.deepEqual(state, original, 'planner never mutates the old native document')
})
test('an in-place original source mutation cannot silently change the confirmed edit', () => {
  const state=fixtures(), review=reviewNativeSourceRange(state)
  state.clips[0].trimStart = 0.125
  const result=commitReviewedNativeSourceRange(state, review)
  assert.equal(result.ok,false)
  assert.match(result.reason,/changed after range preview/i)
  assert.equal(result.clips,undefined)
})
test('a concurrent human edit, different timeline or new marker invalidates preview', () => {
  const changes=[
    s=>{s.clips=[...s.clips]},
    s=>{s.timelineSessionId++},
    s=>{s.timelineId='other-timeline'},
    s=>{s.markers.push({id:'beat',time:1})},
    s=>{s.tracks[0].locked=true},
    s=>{s.rippleEditMode=false},
    s=>{s.inPoint=0.25},
    s=>{s.timelineFps=30},
    s=>{s.clipCounter++},
  ]
  for(const change of changes){
    const state=fixtures(), review=reviewNativeSourceRange(state)
    change(state)
    const response=commitReviewedNativeSourceRange(state, review)
    assert.equal(response.ok,false,change.toString())
    assert.equal(response.clips,undefined)
  }
})
test('invalid, nested and unsafe effect/transition ranges visibly refuse before mutation', () => {
  const cases=[
    s=>{s.inPoint=null},
    s=>{s.outPoint=null},
    s=>{s.outPoint=s.inPoint},
    s=>{s.compoundEditContext={id:'native-child'}},
    s=>{s.clips[0].effects=[{id:'fx', type:'temporal-blur'}]},
    s=>{s.transitions=[{id:'a',kind:'between',clipAId:'clip-1',clipBId:'clip-2'}]},
    s=>{s.markers=[{id:'beat',time:1}]},
    s=>{s.tracks[1].locked=true},
  ]
  for(const edit of cases){
    const state=fixtures(), before=structuredClone(state)
    edit(state)
    const unchanged=structuredClone(state)
    const result=reviewNativeSourceRange(state)
    assert.equal(result.ok,false,edit.toString())
    assert.deepEqual(state,unchanged)
    assert.notDeepEqual(before,state)
  }
})
test('audio-visual lift (no ripple) keeps real gap and human review state', () => {
  const state=fixtures();state.rippleEditMode=false
  const review=reviewNativeSourceRange(state)
  assert.equal(review.ok,true,review.reason)
  assert.equal(review.shiftCount,0)
  const committed=commitReviewedNativeSourceRange(state,review)
  assert.equal(committed.ok,true,committed.reason)
  assert.deepEqual(committed.clips.map(x=>x.startTime),[0,.75,0,.75])
})
test('unknown review, stale review and invalid source cannot produce mutable timeline', () => {
  const state=fixtures()
  for(const item of [null,{}, {ok:true}, {ok:false,sourceFingerprint:'x'}])
    assert.equal(commitReviewedNativeSourceRange(state,item).ok,false)
  assert.equal(reviewNativeSourceRange({}).ok,false)
  assert.equal(commitReviewedNativeSourceRange(state,{
    ...reviewNativeSourceRange(state), removeCount:0}).ok,false)
})
