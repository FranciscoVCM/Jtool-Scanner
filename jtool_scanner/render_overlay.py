"""SVG overlays for inspecting screenshot detections."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from .constants import (
    OBJ_APPLE,
    OBJ_BLOCK,
    OBJ_MINI_SPIKE_DOWN,
    OBJ_MINI_SPIKE_LEFT,
    OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_UP,
    OBJ_PLATFORM,
    OBJ_PLAYER_START,
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
    ROOM_HEIGHT,
    ROOM_WIDTH,
)
from .geometry import Box, distance
from .jmap import JMap
from .scanner import Detection, ScanResult


FULL_SPIKES = {
    OBJ_SPIKE_UP,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_LEFT,
    OBJ_SPIKE_DOWN,
}
MINI_SPIKES = {
    OBJ_MINI_SPIKE_UP,
    OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_LEFT,
    OBJ_MINI_SPIKE_DOWN,
}

STROKE_BY_GROUP = {
    "save": "#ffd400",
    "warp": "#8b5cf6",
    "apple": "#ef4444",
    "water": "#38bdf8",
    "walljump": "#22c55e",
    "platform": "#facc15",
    "block": "#f97316",
    "spike": "#f43f5e",
    "mini_spike": "#ec4899",
    "other": "#ffffff",
}
STATUS_STROKE = {
    "matched": "#22c55e",
    "unmatched": "#ef4444",
}
WATER_TYPES = {
    OBJ_WATER,
    OBJ_WATER_2,
    OBJ_WATER_3,
}


def render_detection_overlay(
    result: ScanResult,
    image_path: str | Path,
    title: str = "JTool scanner detection overlay",
    show_labels: bool = False,
    truth: JMap | None = None,
    tolerance: float = 24,
) -> str:
    """Render scanner detections over the source screenshot."""

    image_href = _image_href(image_path)
    matches = (
        _match_detections_to_truth(result.detections, truth, tolerance)
        if truth is not None
        else None
    )
    body: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{result.image_width}" '
        f'height="{result.image_height}" viewBox="0 0 {result.image_width} '
        f'{result.image_height}" role="img" aria-label="{escape(title)}">',
        f"<title>{escape(title)}</title>",
        "<defs>",
        "<style>",
        ".room{fill:none;stroke:#facc15;stroke-width:2;stroke-dasharray:8 5}",
        ".det{fill:#000;fill-opacity:.08;stroke-width:3}",
        ".center{fill:#fff;stroke:#111;stroke-width:1}",
        ".label{font:12px monospace;paint-order:stroke;stroke:#000;stroke-width:3;fill:#fff}",
        ".missed{fill:none;stroke:#facc15;stroke-width:3;stroke-dasharray:6 4}",
        "</style>",
        "</defs>",
        f'<image href="{escape(image_href)}" x="0" y="0" '
        f'width="{result.image_width}" height="{result.image_height}" '
        'preserveAspectRatio="none"/>',
        _rect(result.room_box, "room"),
        '<g class="detections">',
    ]

    for index, detection in enumerate(result.detections):
        status = None if matches is None else ("matched" if index in matches[0] else "unmatched")
        body.extend(_detection_elements(detection, show_labels, result.image_height, status))

    if matches is not None:
        body.append("</g>")
        body.append('<g class="missed-truth">')
        for truth_item in _truth_items(truth):
            if truth_item.index not in matches[1]:
                body.extend(_missed_truth_elements(result, truth_item, show_labels))

    body.extend(["</g>", "</svg>"])
    return "\n".join(body) + "\n"


def _detection_elements(
    detection: Detection,
    show_label: bool,
    image_height: int,
    status: str | None,
) -> list[str]:
    group = _object_group(detection.type_id)
    stroke = STATUS_STROKE[status] if status else STROKE_BY_GROUP[group]
    name = OBJECT_NAMES.get(detection.type_id, f"type_{detection.type_id}")
    box = detection.image_box
    title = (
        f"{detection.kind} {name} map=({detection.x}, {detection.y}) "
        f"score={detection.score:.2f} image=({box.x}, {box.y}, {box.width}, {box.height})"
    )
    elements = [
        f'<g data-kind="{escape(detection.kind)}" data-type="{escape(name)}" '
        f'data-group="{escape(group)}" data-score="{detection.score:.3f}"'
        f'{_status_attr(status)}>',
        f"<title>{escape(title)}</title>",
        _rect(box, "det", stroke=stroke),
        (
            f'<circle class="center" cx="{box.center_x:g}" cy="{box.center_y:g}" '
            'r="3"/>'
        ),
    ]
    if show_label:
        elements.append(
            _label(box, f"{detection.kind}:{name} {detection.score:.2f}", image_height)
        )
    elements.append("</g>")
    return elements


def _missed_truth_elements(
    result: ScanResult,
    truth_item: "_TruthItem",
    show_label: bool,
) -> list[str]:
    box = _truth_image_box(result, truth_item)
    name = OBJECT_NAMES.get(truth_item.type_id, f"type_{truth_item.type_id}")
    title = f"missed truth {name} map=({truth_item.x}, {truth_item.y})"
    elements = [
        f'<g data-status="missed" data-type="{escape(name)}">',
        f"<title>{escape(title)}</title>",
        _rect(box, "missed"),
    ]
    if show_label:
        elements.append(_label(box, f"missed:{name}", result.image_height))
    elements.append("</g>")
    return elements


def _label(box: Box, text: str, image_height: int) -> str:
    label_y = box.y - 4
    if label_y < 12:
        label_y = min(image_height - 4, box.bottom + 13)
    return f'<text class="label" x="{box.x}" y="{label_y}">{escape(text)}</text>'


def _rect(box: Box, class_name: str, stroke: str | None = None) -> str:
    stroke_attr = f' stroke="{stroke}"' if stroke else ""
    return (
        f'<rect class="{class_name}" x="{box.x}" y="{box.y}" '
        f'width="{box.width}" height="{box.height}"{stroke_attr}/>'
    )


def _image_href(image_path: str | Path) -> str:
    return Path(image_path).resolve().as_uri()


@dataclass(frozen=True, slots=True)
class _TruthItem:
    index: int
    type_id: int
    x: int
    y: int


def _match_detections_to_truth(
    detections: list[Detection],
    truth: JMap,
    tolerance: float,
) -> tuple[set[int], set[int]]:
    remaining = _truth_items(truth)
    matched_detections: set[int] = set()
    matched_truth: set[int] = set()
    for detection_index, detection in enumerate(detections):
        candidates = [
            truth_item
            for truth_item in remaining
            if truth_item.type_id in _match_type_ids(detection.type_id)
        ]
        if not candidates:
            continue
        best = min(
            candidates,
            key=lambda truth_item: distance(
                (detection.x, detection.y),
                (truth_item.x, truth_item.y),
            ),
        )
        if distance((detection.x, detection.y), (best.x, best.y)) <= tolerance:
            matched_detections.add(detection_index)
            matched_truth.add(best.index)
            remaining.remove(best)
    return matched_detections, matched_truth


def _truth_items(truth: JMap) -> list[_TruthItem]:
    return [
        _TruthItem(index, obj.type_id, obj.x, obj.y)
        for index, obj in enumerate(truth.objects)
        if obj.type_id != OBJ_PLAYER_START
    ]


def _match_type_ids(type_id: int) -> set[int]:
    if type_id in WATER_TYPES:
        return WATER_TYPES
    return {type_id}


def _truth_image_box(result: ScanResult, truth_item: _TruthItem) -> Box:
    width = 16 if truth_item.type_id in MINI_SPIKES else 32
    height = 16 if truth_item.type_id in MINI_SPIKES or truth_item.type_id == OBJ_PLATFORM else 32
    scale_x = result.room_box.width / ROOM_WIDTH
    scale_y = result.room_box.height / ROOM_HEIGHT
    return Box(
        int(round(result.room_box.x + truth_item.x * scale_x)),
        int(round(result.room_box.y + truth_item.y * scale_y)),
        max(1, int(round(width * scale_x))),
        max(1, int(round(height * scale_y))),
    )


def _status_attr(status: str | None) -> str:
    return f' data-status="{status}"' if status else ""


def _object_group(type_id: int) -> str:
    if type_id == OBJ_SAVE:
        return "save"
    if type_id == OBJ_WARP:
        return "warp"
    if type_id == OBJ_APPLE:
        return "apple"
    if type_id in (OBJ_WATER, OBJ_WATER_2, OBJ_WATER_3):
        return "water"
    if type_id in (OBJ_WALLJUMP_LEFT, OBJ_WALLJUMP_RIGHT):
        return "walljump"
    if type_id == OBJ_PLATFORM:
        return "platform"
    if type_id == OBJ_BLOCK:
        return "block"
    if type_id in FULL_SPIKES:
        return "spike"
    if type_id in MINI_SPIKES:
        return "mini_spike"
    return "other"
