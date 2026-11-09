# SPDX-License-Identifier: GPL-3.0-only
"""Assertions shared by the two physical editor proofs."""
from copy import deepcopy


BODY_OBSERVERS = frozenset({
    "zx7_inspect_native_content",
    "zx7_verify_native_export",
    "zx7_observe_verified_export_frame",
    "zx7_observe_verified_export_samples",
    "zx7_observe_verified_export_audio",
    "zx7_observe_verified_export_audio_timeline",
})


def assert_editor_catalog(discovered, granted, upstream):
    """Require exact grants and verify only the intentional host schema changes."""
    names = [tool.name for tool in discovered]
    assert len(names) == len(set(names)), "Duplicate editor tool names"
    expected = set(granted) | BODY_OBSERVERS
    actual = set(names)
    assert actual == expected, {"missing": sorted(expected - actual),
                                "unexpected": sorted(actual - expected)}
    for tool in discovered:
        if tool.name in BODY_OBSERVERS:
            continue
        original = upstream[tool.name]["inputSchema"]
        exposed = deepcopy(tool.input_schema)
        if tool.name in ("add_text_clip", "update_text_clip"):
            props = exposed["properties"]
            original_props = original["properties"]
            opacity = props["transform"]["properties"]["opacity"]
            original_opacity = original_props["transform"]["properties"]["opacity"]
            assert "steady-state" in opacity["description"], tool.name
            assert "base" in props["animationPreset"]["description"], tool.name
            for changed, raw in ((opacity, original_opacity),
                                 (props["animationPreset"], original_props["animationPreset"])):
                if "description" in raw:
                    changed["description"] = raw["description"]
                else:
                    changed.pop("description")
        elif tool.name in ("export_timeline", "export_fcpxml"):
            assert set(exposed["required"]) == set(original.get("required", [])) | {"outputPath"}, tool.name
            destination = exposed["properties"]["outputPath"]
            assert destination["minLength"] == 1 and "new absolute" in destination["description"], tool.name
            raw_destination = original["properties"]["outputPath"]
            for field in ("minLength", "description"):
                if field in raw_destination:
                    destination[field] = raw_destination[field]
                else:
                    destination.pop(field)
            if "required" in original:
                exposed["required"] = original["required"]
            else:
                exposed.pop("required")
        assert exposed == original, tool.name
