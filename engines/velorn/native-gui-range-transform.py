#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Pinned-source GUI native edit integration.

Only transforms the *exact* already source-verified Velorn range child. Every
anchor must match once; drift/refactor fails before a new editor is published.
No arbitrary project files, original media or owner paths are touched.
"""
from pathlib import Path
import sys

def replace_one(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise SystemExit("Unreviewed native GUI/source ABI: expected one exact anchor " + repr(old[:100]))
    return source.replace(old, new, 1)

root = Path(sys.argv[1]).resolve(strict=True)
store = root / "src/stores/timelineStore.js"
gui = root / "src/components/Timeline.jsx"
s = store.read_text(encoding="utf-8")
s = replace_one(
    s,
    "import { planCloseTimelineGap } from '../utils/closeTimelineGap.mjs'",
    "import { planCloseTimelineGap } from '../utils/closeTimelineGap.mjs'\n"
    "import { reviewNativeSourceRange, commitReviewedNativeSourceRange } "
    "from '../utils/zx7-native-range-review.mjs'")
s = replace_one(s, "  rippleDeleteClipIds: (clipIds = []) => {", """\
  // Human In/Out controls use the same source-native A/V range algebra as
  // the privileged MCP action. The GUI is an actual human writer, not a model
  // tool and never fabricates an MCP source-revision token.
  zx7PreviewNativeRange: () => reviewNativeSourceRange(get()),
  zx7CommitNativeRange: (review) => {
    const plan = commitReviewedNativeSourceRange(get(), review)
    if (!plan.ok) return plan
    // No intermediate split/delete/shift becomes visible to subscribers.
    get().saveToHistory()
    set({
      clips: plan.clips,
      clipCounter: plan.clipCounter,
      selectedClipIds: plan.selectedClipIds,
      selectedTransitionId: null,
      selectedGap: null,
    })
    return {
      ok: true, startSeconds: plan.startSeconds,
      endSeconds: plan.endSeconds, ripple: plan.ripple,
      removedClipIds: plan.removedClipIds,
      shiftedClipIds: plan.shiftedClipIds,
    }
  },

  rippleDeleteClipIds: (clipIds = []) => {""")
store.write_text(s, encoding="utf-8")

s = gui.read_text(encoding="utf-8")
s = replace_one(
    s, "  const [editorHotkeys, setEditorHotkeys] = useState(DEFAULT_EDITOR_HOTKEYS)",
    """\
  const [editorHotkeys, setEditorHotkeys] = useState(DEFAULT_EDITOR_HOTKEYS)
  // Review is scoped to the exact native timeline/source bytes and options.
  // A human pointer/keyframe edit between preview and confirmation invalidates it.
  const [zx7RangeReview, setZx7RangeReview] = useState(null)
  const [zx7RangeError, setZx7RangeError] = useState('')""")
s = replace_one(
    s,
    '          <div className={toolbarSectionClass} aria-label="Timeline options">',
    """\
          <div className={toolbarSectionClass} aria-label="Timeline options">
            <button
              type="button"
              data-testid="zx7-native-range-review"
              disabled={inPoint == null || outPoint == null || inPoint >= outPoint}
              onClick={() => {
                const result = useTimelineStore.getState().zx7PreviewNativeRange()
                if (!result?.ok) {
                  setZx7RangeReview(null)
                  setZx7RangeError(result?.reason || 'Native range review failed without a timeline edit.')
                } else {
                  setZx7RangeError('')
                  setZx7RangeReview(result)
                }
              }}
              className={toolbarButtonClass}
              title="Review a source-preserving In→Out extract on the actual native picture and sound tracks; confirm before changing source."
              aria-label="Review source-safe In to Out extract"
            >
              <Scissors className="w-3 h-3" />
              {showToolbarLabels && 'Extract'}
            </button>""")
s = replace_one(
    s,
    "        {/* Info & Zoom */}",
    """\
        {/* Actual human In→Out confirmation. No model, extra engine, or
            hidden state write is introduced. A stale preview cannot commit. */}
        {(zx7RangeReview || zx7RangeError) && (
          <div
            role="dialog"
            aria-label="Review source-safe native In to Out extraction"
            data-testid="zx7-native-range-review-dialog"
            className="fixed right-6 top-20 z-[100] w-80 max-w-[calc(100vw-3rem)] rounded-lg border border-sf-dark-600 bg-sf-dark-900 p-3 shadow-xl text-sf-text"
          >
            <div className="text-xs font-semibold mb-2">Source-safe In→Out extraction</div>
            {zx7RangeError && (
              <p role="alert" className="text-xs text-rose-300 mb-2">{zx7RangeError}</p>
            )}
            {zx7RangeReview && (
              <>
                <p className="text-xs mb-2">
                  {zx7RangeReview.startSeconds.toFixed(3)}s – {zx7RangeReview.endSeconds.toFixed(3)}s
                  · {zx7RangeReview.ripple ? 'Ripple' : 'Lift'}
                  · {zx7RangeReview.affectedTrackIds.length} native tracks
                  · {zx7RangeReview.removeCount} source pieces removed
                  · {zx7RangeReview.shiftCount} pieces shifted
                </p>
                <p className="text-[11px] text-sf-text-muted mb-3">
                  Originals are retained. This native source change is one Undo step.
                  If the timeline changes, confirmation will refuse.
                </p>
                <button
                  type="button"
                  data-testid="zx7-native-range-commit"
                  className="mr-2 rounded bg-sf-accent px-3 py-1 text-xs text-white"
                  onClick={() => {
                    const result = useTimelineStore.getState().zx7CommitNativeRange(zx7RangeReview)
                    if (!result?.ok) {
                      setZx7RangeReview(null)
                      setZx7RangeError(result?.reason || 'Native range commit was refused.')
                    } else {
                      setZx7RangeError('')
                      setZx7RangeReview(null)
                    }
                  }}
                >
                  Apply native edit
                </button>
              </>
            )}
            <button
              type="button"
              data-testid="zx7-native-range-dismiss"
              className="rounded border border-sf-dark-600 px-3 py-1 text-xs"
              onClick={() => {
                setZx7RangeReview(null)
                setZx7RangeError('')
              }}
            >
              Cancel / Close
            </button>
          </div>
        )}
        {/* Info & Zoom */}""")
gui.write_text(s, encoding="utf-8")
