// SPDX-License-Identifier: GPL-3.0-only
// ZX7 opt-in, pure, fail-closed native timeline razor planner.
// Never mutate editor state, assets, or media. The pinned renderer commits
// one complete plan only after its existing synchronous source-revision fence.
const EPS = 1e-7
const finite = n => typeof n === 'number' && Number.isFinite(n)
const nonempty = value => {
  if (value == null || value === false || value === '') return false
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.values(value).some(nonempty)
  return Boolean(value)
}
const fail = reason => ({ ok: false, reason })
const clone = value => structuredClone(value)

// Pinned source-created media clip keys plus specifically reviewed authored
// keys. Unexpected new creative state is a hard refusal, never discarded.
const KNOWN_FIELDS = new Set([
  'id', 'trackId', 'assetId', 'name', 'startTime', 'duration',
  'sourceDuration', 'trimStart', 'trimEnd', 'sourceFps', 'timelineFps',
  'sourceTimeScale', 'speed', 'reverse', 'frameSampling', 'gainDb',
  'fadeIn', 'fadeOut', 'volumeEnvelope', 'audioEq', 'color', 'type',
  'enabled', 'compositeLowerLayers', 'url', 'thumbnail', 'metadata',
  'lockMode', 'syncLock', 'linkGroupId', 'locked', 'syncLocked',
  'transform', 'labelColor', 'keyframes', 'effects', 'adjustments',
  'shapeMask', 'trackMatte', 'speedRamp', 'timeRemap', 'animation',
  'animations', 'titleAnimation', 'overlayKind', 'captionScope',
  'captions', 'maskAssetId', 'maskFrames', 'text', 'textProperties',
  'shapeProperties', 'cacheStatus', 'cacheProgress', 'cacheUrl',
  'cachePath', 'cacheKind', 'cacheSignature', 'opticalFlowCache',
])

const DYNAMIC_FEATURES = [
  'effects', 'shapeMask', 'speedRamp', 'timeRemap', 'animation',
  'animations', 'titleAnimation', 'maskAssetId', 'maskFrames',
  'overlayKind', 'captionScope', 'captions', 'text', 'textProperties',
  'shapeProperties',
]

function validateCurve(keyframes, duration) {
  if (keyframes == null) return true
  if (!keyframes || typeof keyframes !== 'object' || Array.isArray(keyframes)) return false
  for (const [property, points] of Object.entries(keyframes)) {
    // Speed curves remap media time nonlinearly; their phase cannot currently
    // be proved by shifting visual keyframe coordinates alone.
    if (property === 'speed' || !Array.isArray(points) || points.length > 10000) return false
    let prev = -Infinity
    for (const point of points) {
      if (!point || typeof point !== 'object' || Array.isArray(point)
        || !finite(point.time) || !finite(point.value)
        || point.time <= prev
        || (point.easing != null && typeof point.easing !== 'string')
        || Object.keys(point).some(key => !['time', 'value', 'easing'].includes(key))) return false
      prev = point.time
    }
  }
  return true
}

function validateVolumeEnvelope(envelope) {
  if (envelope == null) return true
  if (!envelope || envelope.version !== 1 || !finite(envelope.offsetSeconds)
      || !Array.isArray(envelope.points) || envelope.points.length > 128) return false
  const ids = new Set(); const times = new Set()
  for (const point of envelope.points) {
    if (!point || typeof point.id !== 'string' || !point.id.trim()
        || !finite(point.time) || !finite(point.db)
        || point.db < -60 || point.db > 12 || ids.has(point.id) || times.has(point.time)) return false
    ids.add(point.id); times.add(point.time)
  }
  return true
}

function sourceRange(clip) {
  const sourceFps = Number(clip.sourceFps)
  const timelineFps = Number(clip.timelineFps)
  const explicitScale = Number(clip.sourceTimeScale)
  const baseScale = finite(explicitScale) && explicitScale > 0
    ? explicitScale : ((finite(sourceFps) && sourceFps > 0 && finite(timelineFps) && timelineFps > 0)
      ? timelineFps / sourceFps : 1)
  const speed = clip.speed == null ? 1 : clip.speed
  if (!finite(speed) || speed <= 0) return null
  const scale = baseScale * speed
  const start = clip.trimStart ?? 0
  const end = clip.trimEnd ?? clip.sourceDuration ?? (start + clip.duration * scale)
  if (!finite(scale) || scale <= 0 || !finite(start) || !finite(end)
      || start < 0 || end < start || end - start + EPS < clip.duration * scale
      || (finite(clip.sourceDuration) && end > clip.sourceDuration + EPS)) return null
  return { start, end, scale }
}

function editableClip(clip, track, offset, rightDuration) {
  if (!clip || !['video', 'audio'].includes(clip.type)
      || !track || !['video', 'audio'].includes(track.type)
      || (track.type === 'video' && clip.type !== 'video')
      || track.locked || track.syncLocked || track.lockMode === 'sync'
      || clip.locked || clip.syncLocked || clip.lockMode === 'sync'
      || nonempty(clip.syncLock)) return fail('A source or track is locked or has unsupported semantics')
  const extra = Object.keys(clip).filter(key => !KNOWN_FIELDS.has(key))
  if (extra.length) return fail('Unreviewed native clip state: ' + extra.slice(0, 5).join(', '))
  const authored = DYNAMIC_FEATURES.filter(key => nonempty(clip[key]))
  if (authored.length) return fail('This cut needs source-native handling of ' + authored.join(', '))
  if (clip.trackMatte != null && clip.trackMatte !== 'none') return fail('Track matte relationship is not slice-safe')
  if (clip.compositeLowerLayers != null && clip.compositeLowerLayers !== 'auto') {
    return fail('Non-default compositing is not slice-safe')
  }
  if (clip.frameSampling === 'opticalFlow' || nonempty(clip.opticalFlowCache)) {
    return fail('Optical-flow retime must be reverified before razor')
  }
  if (!validateCurve(clip.keyframes, clip.duration)) return fail('Unrepresentable animated keyframes')
  if (!validateVolumeEnvelope(clip.volumeEnvelope)) return fail('Invalid audio automation')
  if (clip.metadata != null && (
    !clip.metadata || typeof clip.metadata !== 'object' || Array.isArray(clip.metadata)
    || Object.keys(clip.metadata).some(key => ![
      'addedByMcp', 'addedAt', 'sourceTool', 'linkedAudioClipId', 'linkedVideoClipId',
    ].includes(key)))) return fail('Unreviewed linked source metadata')
  if (clip.adjustments != null && typeof clip.adjustments !== 'object') return fail('Invalid static color adjustments')
  const bounds = sourceRange(clip)
  if (!bounds) return fail('Media source bounds or retime cannot be represented')
  const fadeIn = clip.fadeIn ?? 0
  const fadeOut = clip.fadeOut ?? 0
  if (!finite(fadeIn) || !finite(fadeOut) || fadeIn < 0 || fadeOut < 0
      || fadeIn > offset + EPS || fadeOut > rightDuration + EPS) {
    return fail('Cut crosses an audio edge fade that cannot be preserved')
  }
  return { ok: true, bounds }
}

function clearTransientCache(clip) {
  return {
    ...clip, cacheStatus: 'none', cacheProgress: 0,
    cacheUrl: null, cachePath: null, cacheKind: null,
    cacheSignature: null, opticalFlowCache: undefined,
  }
}

function shiftedKeyframes(keyframes, shift) {
  if (keyframes == null) return keyframes
  return Object.fromEntries(Object.entries(keyframes).map(([key, points]) => [
    key, points.map(point => ({ ...point, time: point.time - shift })),
  ]))
}

/**
 * Plan one native, editable multi-track cut. No replacement clips are
 * returned on failure. Both halves reference the SAME original asset.
 * Full curve points, including those shifted before t=0, are retained:
 * the renderer's interpolation therefore samples the same eased segment at
 * every global timeline time on either half.
 *
 * Supported: video/audio, linear speed/reverse, transform/keyframe curves,
 * static adjustments, EQ, gain, envelope, non-crossed edge fades, linked A/V.
 * Refused: timed effects, speed ramps, masks, transitions, locks, unreviewed
 * fields. This does not pretend all artistic edits are supported.
 */
export function planLossAwareNativeSplit({
  clips, tracks, transitions = [], timeSeconds, clipIds = null,
  fps = 24, clipCounter = 1,
} = {}) {
  if (!Array.isArray(clips) || !Array.isArray(tracks) || !Array.isArray(transitions)
      || !finite(timeSeconds) || timeSeconds < 0 || !finite(fps) || fps <= 0 || fps > 240
      || !Number.isSafeInteger(clipCounter) || clipCounter < 1) return fail('Invalid native timeline or cut time')
  const trackById = new Map(tracks.map(track => [track?.id, track]))
  if (trackById.size !== tracks.length || trackById.has(undefined)) return fail('Ambiguous tracks')
  const byId = new Map(clips.map(clip => [clip?.id, clip]))
  if (byId.size !== clips.length || byId.has(undefined) || byId.has('')
      || clips.some(clip => !finite(clip.startTime) || !finite(clip.duration)
        || clip.startTime < 0 || clip.duration <= 0 || !trackById.has(clip.trackId))) return fail('Incomplete or duplicated clip state')
  if (clipIds != null && (!Array.isArray(clipIds) || clipIds.length === 0
    || clipIds.some(id => typeof id !== 'string' || !id)
    || new Set(clipIds).size !== clipIds.length)) return fail('Explicit cut targets must be unique')
  const time = Math.round(timeSeconds * fps) / fps
  const halfFrame = 0.5 / fps
  const within = clip => time > clip.startTime + halfFrame && time < clip.startTime + clip.duration - halfFrame
  const targets = clipIds == null
    ? clips.filter(clip => within(clip) && !trackById.get(clip.trackId).locked)
    : clipIds.map(id => byId.get(id))
  if (!targets.length || targets.some(clip => !clip || !within(clip))) return fail('Cut is outside the selected source')
  const targetIds = new Set(targets.map(c => c.id))
  if (targetIds.size !== targets.length) return fail('Ambiguous source identity')
  for (const clip of clips) {
    const link = clip.linkGroupId
    if (typeof link !== 'string' || !link.trim()) continue
    const group = clips.filter(item => item.linkGroupId === link)
    if (group.some(item => targetIds.has(item.id))
      && group.some(item => !targetIds.has(item.id))) return fail('Linked audio/video must be cut together')
  }
  for (const transition of transitions) {
    if (!transition || typeof transition !== 'object') return fail('Invalid native transition')
    if ([transition.clipId, transition.clipAId, transition.clipBId]
      .some(id => id && targetIds.has(id))) return fail('A transition relationship crosses this source')
  }
  const plans = new Map()
  for (const clip of targets) {
    const offset = time - clip.startTime
    const rightDuration = clip.duration - offset
    const validation = editableClip(clip, trackById.get(clip.trackId), offset, rightDuration)
    if (!validation.ok) return fail('Clip ' + clip.id + ': ' + validation.reason)
    plans.set(clip.id, { offset, rightDuration, bounds: validation.bounds })
  }
  const ids = new Set(byId.keys())
  let nextId = clipCounter
  for (const id of ids) {
    const match = /^clip-(\d+)$/.exec(id)
    if (match) nextId = Math.max(nextId, Number(match[1]) + 1)
  }
  if (!Number.isSafeInteger(nextId)) return fail('Native clip ID range exhausted')
  const rightIds = new Map()
  for (const clip of targets) {
    while (ids.has('clip-' + nextId)) nextId++
    if (!Number.isSafeInteger(nextId)) return fail('Native clip ID range exhausted')
    const id = 'clip-' + nextId++
    ids.add(id)
    rightIds.set(clip.id, id)
  }
  const usedGroups = new Set(clips.map(c => c.linkGroupId).filter(Boolean))
  const replacementGroups = new Map()
  for (const clip of targets) {
    if (!clip.linkGroupId) continue
    if (!replacementGroups.has(clip.linkGroupId)) {
      let candidate = 'zx7-cut-' + rightIds.get(clip.id)
      while (usedGroups.has(candidate)) candidate += '-next'
      usedGroups.add(candidate)
      replacementGroups.set(clip.linkGroupId, candidate)
    }
  }
  const nextClips = []
  for (const clip of clips) {
    if (!targetIds.has(clip.id)) {
      nextClips.push(clip)
      continue
    }
    const { offset, rightDuration, bounds } = plans.get(clip.id)
    const splitSource = clip.reverse === true
      ? bounds.end - offset * bounds.scale
      : bounds.start + offset * bounds.scale
    const left = clearTransientCache({
      ...clone(clip), duration: offset,
      trimStart: clip.reverse ? splitSource : bounds.start,
      trimEnd: clip.reverse ? bounds.end : splitSource,
      ...(clip.fadeOut != null ? { fadeOut: 0 } : {}),
    })
    const right = clearTransientCache({
      ...clone(clip),
      id: rightIds.get(clip.id), startTime: time, duration: rightDuration,
      trimStart: clip.reverse ? bounds.start : splitSource,
      trimEnd: clip.reverse ? splitSource : bounds.end,
      keyframes: shiftedKeyframes(clip.keyframes, offset),
      ...(clip.fadeIn != null ? { fadeIn: 0 } : {}),
      ...(clip.volumeEnvelope != null ? { volumeEnvelope: {
        ...clone(clip.volumeEnvelope),
        offsetSeconds: clip.volumeEnvelope.offsetSeconds + offset,
      } } : {}),
      ...(clip.linkGroupId ? { linkGroupId: replacementGroups.get(clip.linkGroupId) } : {}),
    })
    for (const field of ['linkedVideoClipId', 'linkedAudioClipId']) {
      const paired = rightIds.get(right.metadata?.[field])
      if (paired) right.metadata[field] = paired
      else if (right.metadata?.[field] && byId.has(right.metadata[field])) {
        return fail('Embedded audio/video link must be cut together')
      }
    }
    nextClips.push(left, right)
  }
  return {
    ok: true, clips: nextClips, clipCounter: nextId,
    timeSeconds: time,
    selectedClipIds: targets.map(clip => rightIds.get(clip.id)),
    splits: targets.map(clip => ({
      leftClipId: clip.id, rightClipId: rightIds.get(clip.id),
      trackId: clip.trackId, name: clip.name || clip.id,
    })),
  }
}
