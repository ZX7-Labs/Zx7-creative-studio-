// SPDX-License-Identifier: GPL-3.0-only
// Human-visible preview and explicit confirmation for the SAME source-native
// A/V range planner used by MCP. Never interprets foreign effects or media.
import { planLossAwareNativeExtract } from './zx7-loss-aware-extract.mjs'

const fail = (reason) => ({ ok: false, reason })

const sourceSnapshot = (state) => {
  if (!state || typeof state !== 'object') return null
  // The reviewed source is a JSON-owned native timeline. Fingerprint source
  // data and temporal switches, not volatile playhead, render or UI elements.
  // This protects against both immutable replaces and in-place mutation.
  const source = {
    clips: state.clips, tracks: state.tracks,
    transitions: state.transitions, markers: state.markers,
    timelineSessionId: state.timelineSessionId,
    timelineId: state.timelineId,
    clipCounter: state.clipCounter,
    timelineFps: state.timelineFps,
    inPoint: state.inPoint, outPoint: state.outPoint,
    rippleEditMode: state.rippleEditMode,
    compoundEditContext: state.compoundEditContext,
  }
  try {
    const frozen = JSON.stringify(source)
    if (!frozen || frozen.length > 1_000_000) return null
    return frozen
  } catch {
    return null
  }
}

function planFromState(state) {
  if (state?.compoundEditContext) return fail('Nested compound timeline range editing is not verified')
  if (state?.inPoint == null || state?.outPoint == null)
    return fail('Set real In and Out timeline points first (I / O)')
  return planLossAwareNativeExtract({
    clips: state.clips, tracks: state.tracks,
    transitions: state.transitions, markers: state.markers,
    startSeconds: state.inPoint, endSeconds: state.outPoint,
    ripple: state.rippleEditMode === true,
    fps: state.timelineFps, clipCounter: state.clipCounter,
  })
}

export function reviewNativeSourceRange(state) {
  const sourceFingerprint = sourceSnapshot(state)
  if (!sourceFingerprint) return fail('Native timeline snapshot is unavailable')
  const plan = planFromState(state)
  if (!plan.ok) return fail(plan.reason)
  return {
    ok: true,
    sourceFingerprint,
    startSeconds: plan.startSeconds,
    endSeconds: plan.endSeconds,
    durationSeconds: plan.deltaSeconds,
    ripple: plan.ripple,
    affectedTrackIds: [...plan.affectedTrackIds],
    removeCount: plan.removedClipIds.length,
    shiftCount: plan.shiftedClipIds.length,
    sourceAviProtected: true,
  }
}

export function commitReviewedNativeSourceRange(state, review) {
  if (review?.ok !== true || typeof review?.sourceFingerprint !== 'string')
    return fail('No approved human range review')
  const currentFingerprint = sourceSnapshot(state)
  if (!currentFingerprint || currentFingerprint !== review.sourceFingerprint)
    return fail('The timeline changed after range preview. Review again; no write performed')
  const planned = planFromState(state)
  if (!planned.ok) return fail(planned.reason)
  if (planned.startSeconds !== review.startSeconds ||
      planned.endSeconds !== review.endSeconds ||
      planned.ripple !== review.ripple ||
      planned.removedClipIds.length !== review.removeCount ||
      planned.shiftedClipIds.length !== review.shiftCount)
    return fail('The source-safe edit plan changed. Review again')
  return planned
}
