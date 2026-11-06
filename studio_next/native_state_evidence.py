"""Native snapshot facts and source-reviewed read-only preview intent.

No operation is selected or performed here. Both functions expose hard limits
that prevent the creative model from mistaking unimported footage, an empty
timeline or a preview receipt for a completed editable film.

The preview-only names below are source-reviewed against the pinned Velorn
b3c02adbd5c0779feb8abf34978299e9502cc0e7 electron/mcpServer.js
addAssetToTimeline/addAssetsToTimeline/addSolidColor, where a missing/true
previewOnly returns before performAction and invalid planning exits as error.
These are *safety contract bindings*, not creative templates or tool grants.
"""
from __future__ import annotations

import json

_SOURCE_REVIEWED_NONMUTATING_PREVIEWS = frozenset({
    "add_asset_to_timeline", "add_assets_to_timeline", "add_solid_color",
    "add_adjustment_clip",
    # Source-pinned direct preview handlers have an independent application
    # plan, not the asset plan's nested {action, previewOnly} shape.
    "add_transition", "update_transition", "remove_transitions",
    "move_clips", "trim_clips",
    # The same source-guaranteed preview-before-performAction contract
    # applies to these native sequence, track and keyframe operations.
    "update_track", "remove_track", "switch_timeline", "rename_timeline",
    "duplicate_timeline", "delete_timeline", "delete_clips",
    "create_timeline", "set_clip_keyframes",
})

_DIRECT_STRUCTURED_EDITOR_PLANS = frozenset({
    "add_transition", "update_transition", "remove_transitions",
    "move_clips", "trim_clips",
    # The same source-guaranteed preview-before-performAction contract
    # applies to these native sequence, track and keyframe operations.
    "update_track", "remove_track", "switch_timeline", "rename_timeline",
    "duplicate_timeline", "delete_timeline", "delete_clips",
    "create_timeline", "set_clip_keyframes",
})


# Exact no-write error emitted by the source-pinned Velorn 0.3.37
# src/services/mcpActions.js:handleImportAssetFromPath *before* importAsset.
# electron/mcpServer.js:runRendererActionTool prefixes the method name.
# This is protocol evidence, not a creative plan, test fixture or model hint.
_PINNED_NO_IMAGE_SEQUENCE_ERROR = (
    "import_asset_from_path failed: No image sequence found at this path. "
    "Point at a folder containing a numbered run, or at any one frame of it "
    "(3+ frames, e.g. shot.1001.png)."
)


def pinned_forced_image_sequence_absent_error(name, native_reply):
    """A source-attested pre-mutation failure, never an editor write ACK.

    No pathname or extension is guessed. The source adapter itself determines
    whether a forced image sequence exists; a directory ending in '.mp4' may
    legitimately contain frames and must remain supported. Reject any
    mismatched/malformed/extra MCP content; do not inspect private host paths.
    """
    if name != "import_asset_from_path":
        return False
    def field(value, key, default=None):
        return value.get(key, default) if isinstance(value, dict) else (
            getattr(value, key, default))
    if field(native_reply, "is_error", field(native_reply, "isError")) is not True:
        return False
    contents = field(native_reply, "content")
    if not isinstance(contents, (list, tuple)) or len(contents) != 1:
        return False
    part = contents[0]
    return (field(part, "type") == "text" and
            field(part, "text") == _PINNED_NO_IMAGE_SEQUENCE_ERROR)


# Pinned Velorn electron/mcpServer.js:addTransition resolves both clip IDs
# against its active timeline and returns this error BEFORE performAction.
# This exact rejection is not an attempted timeline mutation.
_PINNED_UNKNOWN_BETWEEN_TRANSITION_CLIPS = (
    "Both clipAId and clipBId must refer to clips on the active timeline."
)


def pinned_unknown_between_transition_clips(name, inputs, native_reply):
    """Only the exact pre-dispatch error for a model-chosen between transition.

    A missing target does not make the model's guessed clip IDs valid. Return
    only a bounded fact so the creative model must independently re-inspect
    the native timeline and decide its next action. No hidden write/retry.
    """
    if name != "add_transition" or not isinstance(inputs, dict):
        return False
    if any(not isinstance(inputs.get(k), str) or not inputs[k].strip()
           for k in ("clipAId", "clipBId")):
        return False
    def field(value, key, default=None):
        return value.get(key, default) if isinstance(value, dict) else (
            getattr(value, key, default))
    if field(native_reply, "is_error", field(native_reply, "isError")) is not True:
        return False
    content = field(native_reply, "content")
    if not isinstance(content, (list, tuple)) or len(content) != 1:
        return False
    return (field(content[0], "type") == "text" and
            field(content[0], "text") == _PINNED_UNKNOWN_BETWEEN_TRANSITION_CLIPS)



def source_reviewed_preview_is_readonly(name, inputs, native_schema):
    """Only a pinned source-guaranteed preview, never a failed native WRITE."""
    if name not in _SOURCE_REVIEWED_NONMUTATING_PREVIEWS:
        return False
    if not isinstance(inputs, dict) or not isinstance(native_schema, dict):
        return False
    props = native_schema.get("properties")
    field = props.get("previewOnly") if isinstance(props, dict) else None
    if not isinstance(field, dict) or field.get("type") != "boolean":
        return False
    if "previewOnly" in inputs and type(inputs["previewOnly"]) is not bool:
        return False
    return inputs.get("previewOnly") is not False



def pinned_direct_native_plan_preview(name, inputs, native_schema, receipt):
    """Recognize only an actual pinned Velorn read-only direct plan receipt.

    electron/mcpServer.js:addAssetToTimeline/addAssetsToTimeline/addSolidColor/
    addAdjustmentClip plus fourteen source-reviewed transition, sequence,
    track and clip edit handlers return a *top-level*
    {previewOnly, action, plan, suggestedApplyCall} BEFORE performAction
    when previewOnly !== false. Native asset placement plans
    include an inner action/previewOnly; transition/move/trim plans instead
    contain semantic edit details and must not be forced into an unrelated
    asset schema. This only classifies source-proven, host-selected READ-only
    previews; it never executes the proposed apply action or grants a write.
    The complete receipt was parsed with duplicate-key rejection upstream.
    """
    if not source_reviewed_preview_is_readonly(name, inputs, native_schema):
        return False
    if not isinstance(receipt, dict):
        return False
    # A direct plan cannot simultaneously claim a completed write or carry a
    # generic/nested result. Both are ambiguous and must fail closed.
    if ("success" in receipt or "result" in receipt or
            receipt.get("previewOnly") is not True or
            receipt.get("action") != name or
            receipt.get("error") not in (None, "")):
        return False
    plan = receipt.get("plan")
    apply = receipt.get("suggestedApplyCall")
    if name in _DIRECT_STRUCTURED_EDITOR_PLANS:
        # Source plan is a typed description of the proposed transition or
        # clip move; unlike the asset plan it has no action/previewOnly keys.
        # A contradictory embedded action/previewOnly is rejected, not
        # interpreted as a harmless ordinary preview.
        plan_ok = (isinstance(plan, dict) and
                   # A dictionary containing only an action/preview flag is
                   # not the native editor's semantic preview plan and must
                   # not be accepted as source evidence of no mutation.
                   bool(set(plan) - {"action", "previewOnly"}) and
                   plan.get("action", name) == name and
                   plan.get("previewOnly", True) is True)
    else:
        plan_ok = (isinstance(plan, dict) and
                   plan.get("action") == name and
                   plan.get("previewOnly") is True)
    return (
        plan_ok and isinstance(apply, dict) and
        apply.get("tool") == name and
        isinstance(apply.get("arguments"), dict) and
        apply["arguments"].get("previewOnly") is False
    )


def pinned_snapshot_summary(snapshot):
    """No raw private paths; positive facts only from the real get_project ABI.

    No claim of serializable transaction/version isolation: the snapshot may
    lag the native application. The model must observe actual project state.
    """
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("mcp"), dict):
        return None
    mcp = snapshot["mcp"]
    exists = mcp.get("hasProject")
    if type(exists) is not bool:
        return None
    project = snapshot.get("project")
    timeline = snapshot.get("currentTimeline")
    if (exists and not isinstance(project, dict) or
            not exists and (project is not None or timeline is not None)):
        return None
    def count(value):
        return value if type(value) is int and 0 <= value <= 1_000_000 else None
    assets = count(snapshot.get("assetCount"))
    total = count(snapshot.get("timelineCount"))
    if assets is None or total is None:
        return None
    if timeline is not None:
        if not isinstance(timeline, dict):
            return None
        clips = count(timeline.get("clipCount"))
        tracks = count(timeline.get("trackCount"))
        transitions = count(timeline.get("transitionCount"))
        if clips is None or tracks is None or transitions is None:
            return None
    else:
        clips = tracks = transitions = None
    # Deliberately omit native project paths, asset names, timestamps,
    # content and any invented "has professional video" inference.
    return {
        "source": "host_authorized_native_get_project",
        "project_presence": "present" if exists else "absent",
        "native_project_asset_count": assets,
        "native_timeline_count": total,
        "current_timeline_clip_count": clips,
        "current_timeline_track_count": tracks,
        "current_timeline_transition_count": transitions,
        "snapshot_may_lag_app_state": True,
        "creative_content_or_export_quality_approved": False,
    }


def contradictory_nested_write_receipt(value):
    """A native MCP wrapper's success:true is insufficient if its result fails.

    Pinned Velorn's runRendererActionTool can derive a wrapper boolean from
    result.success !== false; ambiguous nonboolean child fields are not
    independent proof that the actual renderer changed the project.
    """
    return (isinstance(value, dict) and
            (("success" in value and value["success"] is not True) or
             value.get("error") not in (None, "", False)))
