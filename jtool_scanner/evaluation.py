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
            PairEvaluation(
                pair_id=pair["id"],
                detected_saves=_count(result.detections, OBJ_SAVE),
                truth_saves=len(truth.objects_of_type(OBJ_SAVE)),
                matched_saves=_match_count(
                    result.detections,
                    [(obj.x, obj.y) for obj in truth.objects_of_type(OBJ_SAVE)],
                    OBJ_SAVE,
                    tolerance,
                ),
                detected_warps=_count(result.detections, OBJ_WARP),
                truth_warps=len(truth.objects_of_type(OBJ_WARP)),
                matched_warps=_match_count(
                    result.detections,
                    [(obj.x, obj.y) for obj in truth.objects_of_type(OBJ_WARP)],
                    OBJ_WARP,
                    tolerance,
                ),
                detected_apples=_count(result.detections, OBJ_APPLE),
                truth_apples=len(truth.objects_of_type(OBJ_APPLE)),
                matched_apples=_match_count(
                    result.detections,
                    [(obj.x, obj.y) for obj in truth.objects_of_type(OBJ_APPLE)],
                    OBJ_APPLE,
                    tolerance,
                ),
                detected_water=_count_any(result.detections, WATER_TYPES),
                truth_water=_count_truth_any(truth, WATER_TYPES),
                matched_water=_match_group(
                    result.detections,
                    truth,
                    WATER_TYPES,
                    tolerance,
                ),
                detected_walljumps=_count_any(result.detections, WALLJUMP_TYPES),
                truth_walljumps=_count_truth_any(truth, WALLJUMP_TYPES),
                matched_walljumps=_match_group(
                    result.detections,
                    truth,
                    WALLJUMP_TYPES,
                    tolerance,
                ),
                detected_blocks=_count(result.detections, OBJ_BLOCK),
                truth_blocks=len(truth.objects_of_type(OBJ_BLOCK)),
                matched_blocks=_match_count(
                    result.detections,
                    [(obj.x, obj.y) for obj in truth.objects_of_type(OBJ_BLOCK)],
                    OBJ_BLOCK,
                    tolerance,
                ),
                detected_full_spikes=_count_any(result.detections, FULL_SPIKE_TYPES),
                truth_full_spikes=_count_truth_any(truth, FULL_SPIKE_TYPES),
                matched_full_spikes=_match_type_set(
                    result.detections,
                    truth,
                    FULL_SPIKE_TYPES,
                    tolerance,
                ),
                detected_mini_spikes=_count_any(result.detections, MINI_SPIKE_TYPES),
                truth_mini_spikes=_count_truth_any(truth, MINI_SPIKE_TYPES),
                matched_mini_spikes=_match_type_set(
                    result.detections,
                    truth,
                    MINI_SPIKE_TYPES,
                    tolerance,
                ),
            )
        )
    return evaluations


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
