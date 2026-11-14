// SPDX-License-Identifier: GPL-3.0-only
// Pure source-native range/ripple planner. Neither native project state nor
// original footage is mutated. Reuses the reviewed loss-aware razor to avoid
// divergent source-window, curve and linked-audio slicing semantics.
import { planLossAwareNativeSplit } from './zx7-loss-aware-split.mjs'

const EPS = 1e-7
const finite = value => typeof value === 'number' && Number.isFinite(value)
const fail = reason => ({ ok: false, reason })
const nonempty = value => {
  if (value == null || value === false || value === '') return false
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.values(value).some(nonempty)
  return Boolean(value)
}

// Moving a clip changes global time but must not reinterpret unknown temporal
// fields, effects, caches or native output. Known relative keyframes and audio
// envelopes keep their phase when the whole clip moves.
const SAFE_MOVABLE_FIELDS = new Set([
  'id', 'trackId', 'assetId', 'name', 'type', 'startTime', 'duration',
  'sourceDuration', 'trimStart', 'trimEnd', 'sourceFps', 'timelineFps',
  'sourceTimeScale', 'speed', 'reverse', 'frameSampling', 'gainDb',
  'fadeIn', 'fadeOut', 'volumeEnvelope', 'audioEq', 'color',
  'enabled', 'compositeLowerLayers', 'url', 'thumbnail', 'metadata',
  'lockMode', 'syncLock', 'linkGroupId', 'locked', 'syncLocked',
  'transform', 'labelColor', 'keyframes', 'effects', 'adjustments',
  'shapeMask', 'trackMatte', 'speedRamp', 'timeRemap', 'animation',
  'animations', 'titleAnimation', 'overlayKind', 'captionScope',
  'captions', 'maskAssetId', 'maskFrames', 'text', 'textProperties',
  'shapeProperties', 'cacheStatus', 'cacheProgress', 'cacheUrl',
  'cachePath', 'cacheKind', 'cacheSignature', 'opticalFlowCache',
])
const PHASE_UNPROVEN = [
  'effects', 'speedRamp', 'timeRemap', 'animation', 'animations',
  'titleAnimation', 'shapeMask', 'maskAssetId', 'maskFrames',
  'overlayKind', 'captionScope', 'captions',
]
const META_SAFE = new Set([
  'addedByMcp', 'addedAt', 'sourceTool', 'linkedAudioClipId',
  'linkedVideoClipId', 'batchIndex', 'batchLayout',
  'embeddedAudioFromVideoAsset', 'solidColor',
])
function safeToMove(clip) {
  if (Object.keys(clip).some(key => !SAFE_MOVABLE_FIELDS.has(key)))
    return false
  if (PHASE_UNPROVEN.some(key => nonempty(clip[key]))
      || nonempty(clip.trackMatte) && clip.trackMatte !== 'none'
      || nonempty(clip.syncLock) || clip.locked || clip.syncLocked
      || clip.lockMode === 'sync') return false
  if (clip.metadata != null && (!clip.metadata
      || typeof clip.metadata !== 'object' || Array.isArray(clip.metadata)
      || Object.keys(clip.metadata).some(key => !META_SAFE.has(key)))) return false
  return true
}

/**
 * Delete [startSeconds, endSeconds) on explicitly selected native tracks.
 * A single source-native synchronous writer consumes the entire returned plan.
 * No intermediate native split, removeClip, or moveClip side effects occur.
 *
 * Picture and audio preserve their source windows and clip-relative animation
 * by reusing the independently tested loss-aware razor at both boundaries.
 * All new IDs/link groups and metadata links are internally generated.
 * No transition/effect/marker/time-remap semantics are assumed.
 */
export function planLossAwareNativeExtract({
  clips, tracks, transitions = [], markers = [], startSeconds, endSeconds,
  trackIds = null, ripple = true, fps = 24, clipCounter = 1,
} = {}) {
  if (!Array.isArray(clips) || clips.length > 1000
      || !Array.isArray(tracks) || tracks.length < 1 || tracks.length > 256
      || !Array.isArray(transitions) || !Array.isArray(markers)
      || !finite(startSeconds) || !finite(endSeconds)
      || startSeconds < 0 || endSeconds <= startSeconds
      || !finite(fps) || fps <= 0 || fps > 240
      || typeof ripple !== 'boolean'
      || !Number.isSafeInteger(clipCounter) || clipCounter < 1)
    return fail('Invalid exact range, rate, source inventory or native counter')
  const start = Math.round(startSeconds * fps) / fps
  const end = Math.round(endSeconds * fps) / fps
  if (!finite(start) || !finite(end) || end - start < 1 / fps - EPS
      || end > 10000000) return fail('Range must cover at least one native video frame')
  const trackById = new Map(tracks.map(track => [track?.id, track]))
  if (trackById.size !== tracks.length || trackById.has(undefined)
      || trackById.has('') || tracks.some(track =>
        !track || !['video', 'audio'].includes(track.type)))
    return fail('Ambiguous or unsupported native track inventory')
  if (trackIds != null && (!Array.isArray(trackIds) || !trackIds.length
      || trackIds.some(id => typeof id !== 'string' || !trackById.has(id))
      || new Set(trackIds).size !== trackIds.length))
    return fail('Selected native track IDs are incomplete, absent or duplicated')
  const selected = trackIds == null
    ? new Set(trackById.keys()) : new Set(trackIds)
  const affectedTrackIds = tracks.filter(t => selected.has(t.id)).map(t => t.id)
  if (affectedTrackIds.some(id => {
    const t = trackById.get(id)
    return t.locked || t.syncLocked || t.lockMode === 'sync'
  })) return fail('Locked or synchronized native track cannot be range-edited')
  // Native transitions can own absolute/relative time and clip handles;
  // neither a stale reference nor a baked compromise is an acceptable edit.
  if (transitions.length) return fail('Authored transition timing needs a reviewed native range implementation')
  if (markers.length && ripple) return fail('Ripple cannot silently leave authored timeline markers unshifted')
  const ids = new Set()
  for (const c of clips) {
    if (!c || typeof c.id !== 'string' || !c.id || ids.has(c.id)
        || !trackById.has(c.trackId)
        || !finite(c.startTime) || !finite(c.duration)
        || c.startTime < 0 || c.duration <= 0
        || !finite(c.startTime + c.duration)) return fail('Incomplete native clip identities or timing')
    ids.add(c.id)
  }
  // Unknown source links may live on excluded tracks. Never let a selected
  // clip write orphan its nonselected A/V partner. The razor itself verifies
  // that an actual boundary cuts complete groups or refuses.
  const oldById = new Map(clips.map(c => [c.id, c]))
  const touched = c => selected.has(c.trackId) &&
    ((c.startTime < end - EPS && c.startTime + c.duration > start + EPS) ||
     (ripple && c.startTime >= end - EPS))
  // Before any native write, reject scoped edits that detach or desynchronize
  // an original linked sound/picture pair. No silent per-track permission expansion.
  const groups = new Map()
  for (const c of clips) {
    if (typeof c.linkGroupId === 'string' && c.linkGroupId.trim()) {
      if (!groups.has(c.linkGroupId)) groups.set(c.linkGroupId, [])
      groups.get(c.linkGroupId).push(c)
    }
    for (const field of ['linkedVideoClipId', 'linkedAudioClipId']) {
      const partnerId = c.metadata?.[field]
      if (partnerId != null) {
        const partner = oldById.get(partnerId)
        if (!partner || touched(partner) !== touched(c))
          return fail('Range would detach or desynchronize original linked audio/video')
      }
    }
  }
  for (const members of groups.values()) {
    if (members.some(touched) && members.some(c => !touched(c)))
      return fail('Range would edit only part of a linked native source group')
  }
  const crossings = (current, time) => current.filter(c =>
    selected.has(c.trackId) && c.startTime + EPS < time
    && c.startTime + c.duration > time + EPS).map(c => c.id)

  let stage = structuredClone(clips)
  let counter = clipCounter
  const selectedRightPieces = new Set()
  const splitAtStart = crossings(stage, start)
  if (splitAtStart.length) {
    const planned = planLossAwareNativeSplit({
      clips: stage, tracks, transitions, timeSeconds: start,
      clipIds: splitAtStart, fps, clipCounter: counter,
    })
    if (!planned.ok) return fail('Start boundary: ' + planned.reason)
    stage = planned.clips
    counter = planned.clipCounter
  }
  const splitAtEnd = crossings(stage, end)
  if (splitAtEnd.length) {
    const planned = planLossAwareNativeSplit({
      clips: stage, tracks, transitions, timeSeconds: end,
      clipIds: splitAtEnd, fps, clipCounter: counter,
    })
    if (!planned.ok) return fail('End boundary: ' + planned.reason)
    stage = planned.clips
    counter = planned.clipCounter
    for (const split of planned.splits) selectedRightPieces.add(split.rightClipId)
  }

  const kept = []
  const removedClipIds = []
  const shiftedClipIds = []
  const selectedClipIds = []
  for (const clip of stage) {
    if (!selected.has(clip.trackId)) {
      kept.push(clip)
      continue
    }
    const clipEnd = clip.startTime + clip.duration
    if (clipEnd <= start + EPS) {
      kept.push(clip)
    } else if (clip.startTime >= end - EPS) {
      if (ripple) {
        if (!safeToMove(clip)) return fail('Post-range clip contains unreviewed temporal semantics: ' + clip.id)
        kept.push({ ...clip, startTime: clip.startTime - (end - start) })
        shiftedClipIds.push(clip.id)
      } else {
        kept.push(clip)
      }
      if (selectedRightPieces.has(clip.id)) selectedClipIds.push(clip.id)
    } else if (clip.startTime >= start - EPS && clipEnd <= end + EPS) {
      removedClipIds.push(clip.id)
    } else {
      return fail('Source clips cannot be cut at exact selected frame boundaries')
    }
  }
  if (!removedClipIds.length && !shiftedClipIds.length) {
    return fail('Range has no native effect; refuse an empty history checkpoint')
  }
  if (kept.length > 1000) return fail('Native timeline clip budget exhausted')
  const liveById = new Map(kept.map(c => [c.id, c]))
  if (liveById.size !== kept.length) return fail('Extract would produce duplicate native IDs')
  for (const clip of kept) {
    for (const field of ['linkedAudioClipId', 'linkedVideoClipId']) {
      const target = clip.metadata?.[field]
      if (target != null && (!liveById.has(target)
          || liveById.get(target).metadata?.[
            field === 'linkedAudioClipId' ? 'linkedVideoClipId' : 'linkedAudioClipId'
          ] !== clip.id)) return fail('Extract would break editable original linked A/V')
    }
  }
  return {
    ok: true, clips: kept, clipCounter: counter,
    startSeconds: start, endSeconds: end, deltaSeconds: end - start,
    ripple, affectedTrackIds, splitAtStart, splitAtEnd,
    removedClipIds, shiftedClipIds, selectedClipIds,
    warnings: [],
  }
}
