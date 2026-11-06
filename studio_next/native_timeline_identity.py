"""Native timeline object-identity checks from genuine current editor state.

This is a source/typed-reference admission boundary, not an editing recipe.
Only explicit native clip/track IDs are checked. The creative model selects
every operation, while Velorn remains the final source of state and authority.
"""
from __future__ import annotations


_CLIP_KEYS = ("clipId", "clipIds")
_TRACK_KEYS = ("trackId", "trackIds")


def needs_native_timeline_identity(inputs: dict, native_schema: dict) -> bool:
    if not isinstance(inputs, dict) or not isinstance(native_schema, dict):
        return False
    declared = native_schema.get("properties")
    if not isinstance(declared, dict):
        return False
    return any(name in inputs and name in declared
               for name in (*_CLIP_KEYS, *_TRACK_KEYS))


def _requested_ids(inputs: dict, properties: dict,
                   singular: str, plural: str):
    ids = []
    if singular in properties:
        raw = inputs.get(singular)
        if isinstance(raw, str) and raw.strip():
            ids.append(raw.strip())
    if plural in properties:
        raw = inputs.get(plural)
        if isinstance(raw, list):
            ids.extend(x.strip() for x in raw
                       if isinstance(x, str) and x.strip())
    return ids


def assess_native_timeline_references(inputs: dict, native_schema: dict,
                                      timeline: dict) -> dict | None:
    """Return no-dispatch evidence for absent IDs without inventing source IDs.

    get_timeline(includeClips=true,limit=1000) is a bounded native READ.
    If the source reports a clipped clip inventory, absence is unknown.
    """
    if not needs_native_timeline_identity(inputs, native_schema):
        return None
    props = native_schema["properties"]
    if not isinstance(timeline, dict):
        return {"validation_keyword": "native_timeline_identity_unverified",
                "no_native_dispatch": True}
    clips, tracks = timeline.get("clips"), timeline.get("tracks")
    truncated = timeline.get("clipLimitApplied")
    if (not isinstance(clips, list) or not isinstance(tracks, list) or
            type(truncated) is not bool or
            len(clips) > 1000 or len(tracks) > 1000 or
            any(not isinstance(x, dict) or not isinstance(x.get("id"), str)
                or not x["id"] or len(x["id"]) > 512
                for x in (*clips, *tracks))):
        return {"validation_keyword": "native_timeline_identity_unverified",
                "no_native_dispatch": True}
    clip_ids = {x["id"] for x in clips}
    track_ids = {x["id"] for x in tracks}
    requested_clips = _requested_ids(inputs, props, *_CLIP_KEYS)
    requested_tracks = _requested_ids(inputs, props, *_TRACK_KEYS)
    unknown_clips = sorted(set(requested_clips) - clip_ids)
    unknown_tracks = sorted(set(requested_tracks) - track_ids)
    if not unknown_clips and not unknown_tracks:
        return None
    keyword = ("native_timeline_inventory_incomplete"
               if truncated and unknown_clips else
               "native_clip_id_absent" if unknown_clips else
               "native_track_id_absent")
    return {
        "validation_keyword": keyword,
        "native_clip_count_observed": len(clips),
        "native_track_count_observed": len(tracks),
        "native_clip_ids_sample": sorted(clip_ids)[:8],
        "native_track_ids_sample": sorted(track_ids)[:8],
        "native_ids_must_be_observed_not_invented": True,
        "no_native_dispatch": True,
    }
