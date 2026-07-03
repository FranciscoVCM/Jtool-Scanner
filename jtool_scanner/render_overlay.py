"""SVG overlays for inspecting screenshot detections."""

from __future__ import annotations

from html import escape
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
from .geometry import Box
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
    "block": "#f97316",
    "spike": "#f43f5e",
    "mini_spike": "#ec4899",
    "other": "#ffffff",
}


def render_detection_overlay(
    result: ScanResult,
    image_path: str | Path,
    title: str = "JTool scanner detection overlay",
    show_labels: bool = False,
) -> str:
    """Render scanner detections over the source screenshot."""

    image_href = _image_href(image_path)
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
        "</style>",
        "</defs>",
        f'<image href="{escape(image_href)}" x="0" y="0" '
        f'width="{result.image_width}" height="{result.image_height}" '
        'preserveAspectRatio="none"/>',
        _rect(result.room_box, "room"),
        '<g class="detections">',
    ]

    for detection in result.detections:
        body.extend(_detection_elements(detection, show_labels, result.image_height))

    body.extend(["</g>", "</svg>"])
    return "\n".join(body) + "\n"


def _detection_elements(
    detection: Detection,
    show_label: bool,
    image_height: int,
) -> list[str]:
    group = _object_group(detection.type_id)
    stroke = STROKE_BY_GROUP[group]
    name = OBJECT_NAMES.get(detection.type_id, f"type_{detection.type_id}")
    box = detection.image_box
    title = (
        f"{detection.kind} {name} map=({detection.x}, {detection.y}) "
        f"score={detection.score:.2f} image=({box.x}, {box.y}, {box.width}, {box.height})"
    )
    elements = [
        f'<g data-kind="{escape(detection.kind)}" data-type="{escape(name)}" '
        f'data-score="{detection.score:.3f}">',
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
    if type_id == OBJ_BLOCK:
        return "block"
    if type_id in FULL_SPIKES:
        return "spike"
    if type_id in MINI_SPIKES:
        return "mini_spike"
    return "other"
