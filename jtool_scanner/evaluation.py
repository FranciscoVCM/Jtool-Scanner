"""Fixture and scanner evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .constants import (
    OBJ_APPLE,
    OBJ_BLOCK,
    OBJ_MINI_SPIKE_DOWN,
    OBJ_MINI_SPIKE_LEFT,
    OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_UP,
    OBJ_SAVE,
    OBJ_SPIKE_DOWN,
    OBJ_SPIKE_LEFT,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_UP,
    OBJ_WALLJUMP_LEFT,
    OBJ_WALLJUMP_RIGHT,
    OBJ_WATER,
    OBJ_WATER_2,
    OBJ_WATER_3,
    OBJ_WARP,
    OBJECT_NAMES,
)
from .geometry import Box, distance
from .jmap import JMap
from .scanner import Detection, scan_png


@dataclass(frozen=True, slots=True)
class PairEvaluation:
    pair_id: str
    detected_saves: int
    truth_saves: int
    matched_saves: int
    detected_warps: int
    truth_warps: int
    matched_warps: int
    detected_apples: int
    truth_apples: int
    matched_apples: int
    detected_water: int
    truth_water: int
    matched_water: int
    detected_walljumps: int
    truth_walljumps: int
    matched_walljumps: int
    detected_blocks: int
    truth_blocks: int
    matched_blocks: int
    detected_full_spikes: int
    truth_full_spikes: int
    matched_full_spikes: int
    detected_mini_spikes: int
    truth_mini_spikes: int
    matched_mini_spikes: int


EVALUATION_TOTAL_FIELDS = (
    "detected_saves",
    "truth_saves",
    "matched_saves",
    "detected_warps",
    "truth_warps",
    "matched_warps",
    "detected_apples",
    "truth_apples",
    "matched_apples",
    "detected_water",
    "truth_water",
    "matched_water",
    "detected_walljumps",
    "truth_walljumps",
    "matched_walljumps",
    "detected_blocks",
    "truth_blocks",
    "matched_blocks",
    "detected_full_spikes",
    "truth_full_spikes",
    "matched_full_spikes",
    "detected_mini_spikes",
    "truth_mini_spikes",
    "matched_mini_spikes",
)


def aggregate_evaluations(evaluations: list[PairEvaluation]) -> dict[str, int]:
    totals = {"pairs": len(evaluations)}
    for field_name in EVALUATION_TOTAL_FIELDS:
        totals[field_name] = sum(
            getattr(evaluation, field_name)
            for evaluation in evaluations
        )
    return totals


def load_manifest(path: str | Path) -> tuple[Path, dict]:
    manifest_path = Path(path)
    return manifest_path.parent, json.loads(manifest_path.read_text(encoding="utf-8"))


def evaluate_manifest(
    manifest_path: str | Path,
    room_box: Box | None = None,
    grid_step: int = 16,
    tolerance: float = 64,
    include_color_objects: bool = False,
    include_geometry: bool = False,
) -> list[PairEvaluation]:
    base, manifest = load_manifest(manifest_path)
    evaluations: list[PairEvaluation] = []
    for pair in manifest.get("pairs", []):
        truth = JMap.from_file(base / pair["jmap"])
        result = scan_png(
            base / pair["game_image"],
            room_box=room_box,
            grid_step=grid_step,
            include_color_objects=include_color_objects,
            include_geometry=include_geometry,
        )
        evaluations.append(
            evaluate_scan(pair["id"], result.detections, truth, tolerance)
        )
    return evaluations


def evaluate_scan(
    pair_id: str,
    detections: list[Detection],
    truth: JMap,
    tolerance: float,
) -> PairEvaluation:
    return PairEvaluation(
        pair_id=pair_id,
        detected_saves=_count(detections, OBJ_SAVE),
        truth_saves=len(truth.objects_of_type(OBJ_SAVE)),
        matched_saves=_match_count(
            detections,
            [(obj.x, obj.y) for obj in truth.objects_of_type(OBJ_SAVE)],
            OBJ_SAVE,
            tolerance,
        ),
        detected_warps=_count(detections, OBJ_WARP),
        truth_warps=len(truth.objects_of_type(OBJ_WARP)),
        matched_warps=_match_count(
            detections,
            [(obj.x, obj.y) for obj in truth.objects_of_type(OBJ_WARP)],
            OBJ_WARP,
            tolerance,
        ),
        detected_apples=_count(detections, OBJ_APPLE),
        truth_apples=len(truth.objects_of_type(OBJ_APPLE)),
        matched_apples=_match_count(
            detections,
            [(obj.x, obj.y) for obj in truth.objects_of_type(OBJ_APPLE)],
            OBJ_APPLE,
            tolerance,
        ),
        detected_water=_count_any(detections, WATER_TYPES),
        truth_water=_count_truth_any(truth, WATER_TYPES),
        matched_water=_match_group(
            detections,
            truth,
            WATER_TYPES,
            tolerance,
        ),
        detected_walljumps=_count_any(detections, WALLJUMP_TYPES),
        truth_walljumps=_count_truth_any(truth, WALLJUMP_TYPES),
        matched_walljumps=_match_group(
            detections,
            truth,
            WALLJUMP_TYPES,
            tolerance,
        ),
        detected_blocks=_count(detections, OBJ_BLOCK),
        truth_blocks=len(truth.objects_of_type(OBJ_BLOCK)),
        matched_blocks=_match_count(
            detections,
            [(obj.x, obj.y) for obj in truth.objects_of_type(OBJ_BLOCK)],
            OBJ_BLOCK,
            tolerance,
        ),
        detected_full_spikes=_count_any(detections, FULL_SPIKE_TYPES),
        truth_full_spikes=_count_truth_any(truth, FULL_SPIKE_TYPES),
        matched_full_spikes=_match_type_set(
            detections,
            truth,
            FULL_SPIKE_TYPES,
            tolerance,
        ),
        detected_mini_spikes=_count_any(detections, MINI_SPIKE_TYPES),
        truth_mini_spikes=_count_truth_any(truth, MINI_SPIKE_TYPES),
        matched_mini_spikes=_match_type_set(
            detections,
            truth,
            MINI_SPIKE_TYPES,
            tolerance,
        ),
    )


def build_match_details(
    detections: list[Detection],
    truth: JMap,
    tolerance: float,
) -> dict[str, dict]:
    return {
        label: _match_detail_group(detections, truth, type_ids, tolerance, strict_type)
        for label, type_ids, strict_type in MATCH_DETAIL_GROUPS
    }


FULL_SPIKE_TYPES = frozenset(
    {
        OBJ_SPIKE_UP,
        OBJ_SPIKE_RIGHT,
        OBJ_SPIKE_LEFT,
        OBJ_SPIKE_DOWN,
    }
)
MINI_SPIKE_TYPES = frozenset(
    {OBJ_MINI_SPIKE_UP, OBJ_MINI_SPIKE_RIGHT, OBJ_MINI_SPIKE_LEFT, OBJ_MINI_SPIKE_DOWN}
)
WATER_TYPES = frozenset({OBJ_WATER, OBJ_WATER_2, OBJ_WATER_3})
WALLJUMP_TYPES = frozenset({OBJ_WALLJUMP_LEFT, OBJ_WALLJUMP_RIGHT})
MATCH_DETAIL_GROUPS = (
    ("saves", frozenset({OBJ_SAVE}), True),
    ("warps", frozenset({OBJ_WARP}), True),
    ("apples", frozenset({OBJ_APPLE}), True),
    ("water", WATER_TYPES, False),
    ("walljumps", WALLJUMP_TYPES, False),
    ("blocks", frozenset({OBJ_BLOCK}), True),
    ("full_spikes", FULL_SPIKE_TYPES, True),
    ("mini_spikes", MINI_SPIKE_TYPES, True),
)


def _count(detections: list[Detection], type_id: int) -> int:
    return sum(1 for detection in detections if detection.type_id == type_id)


def _count_any(detections: list[Detection], type_ids: frozenset[int]) -> int:
    return sum(1 for detection in detections if detection.type_id in type_ids)


def _count_truth_any(jmap: JMap, type_ids: frozenset[int]) -> int:
    return sum(len(jmap.objects_of_type(type_id)) for type_id in type_ids)


def _match_type_set(
    detections: list[Detection],
    truth: JMap,
    type_ids: frozenset[int],
    tolerance: float,
) -> int:
    return sum(
        _match_count(
            detections,
            [(obj.x, obj.y) for obj in truth.objects_of_type(type_id)],
            type_id,
            tolerance,
        )
        for type_id in type_ids
    )


def _match_group(
    detections: list[Detection],
    truth: JMap,
    type_ids: frozenset[int],
    tolerance: float,
) -> int:
    remaining = [
        (obj.x, obj.y)
        for type_id in type_ids
        for obj in truth.objects_of_type(type_id)
    ]
    matched = 0
    for detection in [det for det in detections if det.type_id in type_ids]:
        if not remaining:
            break
        best_index = min(
            range(len(remaining)),
            key=lambda index: distance((detection.x, detection.y), remaining[index]),
        )
        if distance((detection.x, detection.y), remaining[best_index]) <= tolerance:
            matched += 1
            remaining.pop(best_index)
    return matched


def _match_count(
    detections: list[Detection],
    truth: list[tuple[int, int]],
    type_id: int,
    tolerance: float,
) -> int:
    remaining = truth[:]
    matched = 0
    for detection in [det for det in detections if det.type_id == type_id]:
        if not remaining:
            break
        best_index = min(
            range(len(remaining)),
            key=lambda index: distance((detection.x, detection.y), remaining[index]),
        )
        if distance((detection.x, detection.y), remaining[best_index]) <= tolerance:
            matched += 1
            remaining.pop(best_index)
    return matched


def _match_detail_group(
    detections: list[Detection],
    truth: JMap,
    type_ids: frozenset[int],
    tolerance: float,
    strict_type: bool,
) -> dict:
    tolerance_sq = tolerance * tolerance
    group_truth = [
        obj
        for type_id in type_ids
        for obj in truth.objects_of_type(type_id)
    ]
    group_detections = [det for det in detections if det.type_id in type_ids]
    remaining = group_truth[:]
    unmatched_detections: list[Detection] = []

    for detection in group_detections:
        candidate_indexes = [
            index
            for index, obj in enumerate(remaining)
            if not strict_type or obj.type_id == detection.type_id
        ]
        if not candidate_indexes:
            unmatched_detections.append(detection)
            continue
        best_index = min(
            candidate_indexes,
            key=lambda index: _distance_sq(
                detection.x,
                detection.y,
                remaining[index].x,
                remaining[index].y,
            ),
        )
        if (
            _distance_sq(
                detection.x,
                detection.y,
                remaining[best_index].x,
                remaining[best_index].y,
            )
            <= tolerance_sq
        ):
            remaining.pop(best_index)
        else:
            unmatched_detections.append(detection)

    return {
        "unmatched_detection_count": len(unmatched_detections),
        "missed_truth_count": len(remaining),
        "unmatched_detections": [
            _detection_detail(detection, group_truth, strict_type)
            for detection in unmatched_detections
        ],
        "missed_truth": [
            _truth_detail(obj, group_detections, strict_type)
            for obj in remaining
        ],
    }


def _detection_detail(
    detection: Detection,
    truth: list,
    strict_type: bool,
) -> dict:
    candidates = [
        obj for obj in truth if not strict_type or obj.type_id == detection.type_id
    ]
    nearest = _nearest_truth(detection, candidates)
    return {
        "kind": detection.kind,
        "type_id": detection.type_id,
        "type_name": OBJECT_NAMES.get(detection.type_id, f"unknown_{detection.type_id}"),
        "x": detection.x,
        "y": detection.y,
        "score": round(detection.score, 4),
        "nearest_truth": nearest,
    }


def _truth_detail(
    obj,
    detections: list[Detection],
    strict_type: bool,
) -> dict:
    candidates = [
        detection
        for detection in detections
        if not strict_type or detection.type_id == obj.type_id
    ]
    nearest = _nearest_detection(obj, candidates)
    return {
        "type_id": obj.type_id,
        "type_name": OBJECT_NAMES.get(obj.type_id, f"unknown_{obj.type_id}"),
        "x": obj.x,
        "y": obj.y,
        "nearest_detection": nearest,
    }


def _nearest_truth(detection: Detection, truth: list) -> dict | None:
    if not truth:
        return None
    nearest = min(
        truth,
        key=lambda obj: _distance_sq(detection.x, detection.y, obj.x, obj.y),
    )
    distance_sq = _distance_sq(detection.x, detection.y, nearest.x, nearest.y)
    return {
        "type_id": nearest.type_id,
        "type_name": OBJECT_NAMES.get(nearest.type_id, f"unknown_{nearest.type_id}"),
        "x": nearest.x,
        "y": nearest.y,
        "distance": round(distance_sq**0.5, 2),
    }


def _nearest_detection(obj, detections: list[Detection]) -> dict | None:
    if not detections:
        return None
    nearest = min(
        detections,
        key=lambda detection: _distance_sq(detection.x, detection.y, obj.x, obj.y),
    )
    distance_sq = _distance_sq(nearest.x, nearest.y, obj.x, obj.y)
    return {
        "kind": nearest.kind,
        "type_id": nearest.type_id,
        "type_name": OBJECT_NAMES.get(nearest.type_id, f"unknown_{nearest.type_id}"),
        "x": nearest.x,
        "y": nearest.y,
        "score": round(nearest.score, 4),
        "distance": round(distance_sq**0.5, 2),
    }


def _distance_sq(first_x: int, first_y: int, second_x: int, second_y: int) -> int:
    return (first_x - second_x) ** 2 + (first_y - second_y) ** 2
