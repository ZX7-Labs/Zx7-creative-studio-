"""Compare physically observed editing patterns without inventing aesthetic rank.

All values derive from actual decoded reference graph receipts. This module
is factual retrieval support for an independent creative model, not a
popularity predictor, music classifier, or prescriptive editing algorithm.
"""
from __future__ import annotations

import math


class ReferenceComparisonError(ValueError):
    pass


def editing_signature(observation):
    if (not isinstance(observation, dict) or
            observation.get("schema") != "ZX7_AUTHORIZED_REFERENCE_GRAPH_V1"):
        raise ReferenceComparisonError("Physically measured source graph required")
    duration = observation.get("duration_seconds")
    cuts = observation.get("cut_candidate_count")
    graph = observation.get("graph")
    if (type(duration) not in (int, float) or not math.isfinite(duration)
            or duration <= 0 or type(cuts) is not int or cuts < 0
            or not isinstance(graph, list) or not 8 <= len(graph) <= 256):
        raise ReferenceComparisonError("Malformed reference graph evidence")

    def average(name):
        readings = [item.get(name) for item in graph]
        chosen = [value for value in readings
                  if type(value) in (int, float) and math.isfinite(value)]
        if any(value is not None and
               (type(value) not in (int, float) or not math.isfinite(value))
               for value in readings):
            raise ReferenceComparisonError("Untrusted numeric graph entry")
        return round(sum(chosen)/len(chosen), 5) if chosen else None

    audio_values = [item.get("audio_rms_dbfs") for item in graph]
    if any(value is not None and
           (type(value) not in (int, float) or not math.isfinite(value))
           for value in audio_values):
        raise ReferenceComparisonError("Non-finite audio graph")
    # dBFS values represent logarithmic energy, NOT linearly averaged decibels.
    levels = [10**(value/10.) for value in audio_values if value is not None]
    audio_level = (round(10*math.log10(sum(levels)/len(levels)), 4)
                   if levels and sum(levels)>0 else None)
    has_audio = observation.get("has_audio")
    if type(has_audio) is not bool or (not has_audio and levels):
        raise ReferenceComparisonError("Audio identity and measured bins disagree")
    return {
        "duration_seconds": duration,
        "cut_candidates_per_minute": round(cuts*60/duration, 4),
        "mean_motion_energy": average("motion_energy_mean"),
        "mean_luminance": average("mean_luminance"),
        "mean_chroma": average("mean_chroma"),
        "mean_audio_energy_dbfs": audio_level,
        "audio_present": has_audio,
        "source_sha256": observation["source_sha256"],
        "cut_boundaries_are_candidates": True,
        "artistic_rank_or_creative_quality": None,
    }


def compare_observed_cases(first_id, first, second_id, second):
    if not isinstance(first_id, str) or not isinstance(second_id, str):
        raise ReferenceComparisonError("Case identities required")
    left, right = editing_signature(first), editing_signature(second)
    numeric_fields = ("cut_candidates_per_minute", "mean_motion_energy",
                      "mean_luminance", "mean_chroma",
                      "mean_audio_energy_dbfs")
    differences = {}
    for field in numeric_fields:
        a, b = left[field], right[field]
        differences[field] = (
            round(b-a, 5) if a is not None and b is not None else None)
    return {
        "schema": "ZX7_MEASURED_EDITING_CASE_COMPARISON_V1",
        "first_case_id": first_id,
        "second_case_id": second_id,
        "first_observed": left,
        "second_observed": right,
        "second_minus_first": differences,
        "comparison_is_not_aesthetic_quality_score": True,
        "audience_engagement_or_causality_not_established": True,
        "editable_decisions_remain_model_selected": True,
    }
