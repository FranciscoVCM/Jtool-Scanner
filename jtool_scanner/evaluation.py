"""Fixture and scanner evaluation helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .constants import OBJ_SAVE, OBJ_WARP
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


def load_manifest(path: str | Path) -> tuple[Path, dict]:
    manifest_path = Path(path)
    return manifest_path.parent, json.loads(manifest_path.read_text(encoding="utf-8"))


def evaluate_manifest(
    manifest_path: str | Path,
    room_box: Box | None = None,
    tolerance: float = 64,
) -> list[PairEvaluation]:
    base, manifest = load_manifest(manifest_path)
    evaluations: list[PairEvaluation] = []
    for pair in manifest.get("pairs", []):
        truth = JMap.from_file(base / pair["jmap"])
        result = scan_png(base / pair["game_image"], room_box=room_box)
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
            )
        )
    return evaluations


def _count(detections: list[Detection], type_id: int) -> int:
    return sum(1 for detection in detections if detection.type_id == type_id)


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

