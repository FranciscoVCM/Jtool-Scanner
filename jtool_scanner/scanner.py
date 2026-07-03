"""First-pass screenshot scanner.

This module starts with high-confidence, color-stable objects and includes an
experimental edge/shape pass for blocks and spikes. The geometry pass is useful
for diagnostics, but it is not yet expected to produce final maps by itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .constants import (
    GRID_SIZE,
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
    OBJ_WATER_2,
    OBJ_WARP,
    ROOM_HEIGHT,
    ROOM_WIDTH,
)
from .geometry import Box, distance, round_to_step
from .image import RGBImage, load_png
from .jmap import JMap, JMapObject
from .save_picker import move_start_to_save


FULL_SPIKE_TYPES = frozenset(
    {
        OBJ_SPIKE_UP,
        OBJ_SPIKE_RIGHT,
        OBJ_SPIKE_LEFT,
        OBJ_SPIKE_DOWN,
    }
)
MINI_SPIKE_TYPES = frozenset(
    {
        OBJ_MINI_SPIKE_UP,
        OBJ_MINI_SPIKE_RIGHT,
        OBJ_MINI_SPIKE_LEFT,
        OBJ_MINI_SPIKE_DOWN,
    }
)
COLOR_OBJECT_TYPES = frozenset(
    {
        OBJ_APPLE,
        OBJ_WALLJUMP_LEFT,
        OBJ_WALLJUMP_RIGHT,
        OBJ_WATER_2,
    }
)
GEOMETRY_TYPES = frozenset({OBJ_BLOCK, *FULL_SPIKE_TYPES, *MINI_SPIKE_TYPES})
MINI_SPIKE_COEXIST_SCORE = 0.60


@dataclass(frozen=True, slots=True)
class Detection:
    kind: str
    type_id: int
    x: int
    y: int
    score: float
    image_box: Box


@dataclass(slots=True)
class ScanResult:
    image_width: int
    image_height: int
    room_box: Box
    detections: list[Detection] = field(default_factory=list)

    def to_jmap(self, start_policy: str = "auto") -> JMap:
        objects = [JMapObject(det.x, det.y, det.type_id) for det in self.detections]
        jmap = JMap(objects=objects)
        move_start_to_save(jmap, start_policy)
        return jmap


def scan_png(
    path: str | Path,
    room_box: Box | None = None,
    grid_step: int = GRID_SIZE,
    include_color_objects: bool = False,
    include_geometry: bool = False,
) -> ScanResult:
    image = load_png(path)
    return scan_image(
        image,
        room_box=room_box,
        grid_step=grid_step,
        include_color_objects=include_color_objects,
        include_geometry=include_geometry,
    )


def scan_image(
    image: RGBImage,
    room_box: Box | None = None,
    grid_step: int = GRID_SIZE,
    include_color_objects: bool = False,
    include_geometry: bool = False,
) -> ScanResult:
    box = room_box or detect_room_box(image)
    detections: list[Detection] = []
    detections.extend(_detect_saves(image, box, grid_step))
    detections.extend(_detect_warps(image, box, grid_step))
    if include_color_objects:
        detections.extend(_detect_color_objects(image, box, grid_step, detections))
    if include_geometry:
        detections.extend(_detect_geometry(image, box, grid_step))
        detections = _dedupe_overlapping_geometry(detections)
    detections.sort(key=lambda det: (det.type_id, det.y, det.x))
    return ScanResult(image.width, image.height, box, detections)


def detect_room_box(image: RGBImage) -> Box:
    top = _detect_title_bar_height(image)
    return Box(0, top, image.width, image.height - top)


def _detect_title_bar_height(image: RGBImage) -> int:
    blue_rows = 0
    for y in range(min(64, image.height)):
        row = image.row(y)
        blue_count = 0
        for x in range(image.width):
            r = row[x * 3]
            g = row[x * 3 + 1]
            b = row[x * 3 + 2]
            if r < 40 and 70 <= g <= 180 and b > 140:
                blue_count += 1
        if blue_count / image.width > 0.55:
            blue_rows += 1
        elif blue_rows >= 12:
            return y
        elif y > 8:
            blue_rows = 0
    return blue_rows if blue_rows >= 12 else 0


def _detect_saves(image: RGBImage, room: Box, grid_step: int) -> list[Detection]:
    allow_tinted = _looks_cyan_tinted(image, room)
    components = _connected_components(
        image,
        room,
        lambda r, g, b: _is_save_yellow(r, g, b)
        or _is_save_red(r, g, b)
        or (allow_tinted and _is_tinted_save_yellow(r, g, b)),
    )
    detections: list[Detection] = []
    for component in components:
        box, pixels = component
        if not (8 <= box.width <= 55 and 8 <= box.height <= 80):
            continue
        if box.area > 3200:
            continue
        red = yellow = 0
        for x, y in pixels:
            r, g, b = image.pixel(x, y)
            if _is_save_red(r, g, b):
                red += 1
            if _is_save_yellow(r, g, b) or (allow_tinted and _is_tinted_save_yellow(r, g, b)):
                yellow += 1
        if yellow < 18:
            continue
        if red < 12 and yellow < 35:
            continue
        density = (red + yellow) / box.area
        if density < 0.12:
            continue
        map_x, map_y = _image_box_to_jtool_origin(box, room, grid_step)
        score = min(1.0, density * 2.5 + min(red, yellow) / 150)
        detections.append(Detection("save", OBJ_SAVE, map_x, map_y, score, box))
    return _dedupe_detections(detections, min_distance=40)


def _detect_warps(image: RGBImage, room: Box, grid_step: int) -> list[Detection]:
    components = _connected_components(
        image,
        room,
        lambda r, g, b: _is_warp_blue(r, g, b) or _is_warp_purple(r, g, b),
    )
    detections: list[Detection] = []
    for box, pixels in components:
        if not (20 <= box.width <= 120 and 20 <= box.height <= 120):
            continue
        if box.area > 8000:
            continue
        colored = len(pixels)
        density = colored / box.area
        if density < 0.08:
            continue
        # Reject skinny walljump-like fragments and scattered UI text.
        ratio = box.width / max(1, box.height)
        if ratio < 0.65 or ratio > 1.45:
            continue
        if not _has_dark_portal_core(image, box):
            continue
        map_x, map_y = _image_box_to_jtool_origin(box, room, grid_step)
        score = min(1.0, density * 2.0 + colored / 500)
        if score < 0.55:
            continue
        detections.append(Detection("warp", OBJ_WARP, map_x, map_y, score, box))
    return _dedupe_detections(detections)


def _detect_color_objects(
    image: RGBImage,
    room: Box,
    grid_step: int,
    anchors: list[Detection],
) -> list[Detection]:
    detections: list[Detection] = []
    detections.extend(_detect_apples(image, room, grid_step, anchors))
    detections.extend(_detect_walljumps(image, room, grid_step, anchors + detections))
    detections.extend(_detect_water(image, room, grid_step, anchors + detections))
    return detections


def _detect_apples(
    image: RGBImage,
    room: Box,
    grid_step: int,
    anchors: list[Detection],
) -> list[Detection]:
    components = _connected_components(image, room, lambda r, g, b: _is_apple_red(r, g, b))
    detections: list[Detection] = []
    for box, pixels in components:
        if not (12 <= box.width <= 28 and 12 <= box.height <= 28):
            continue
        ratio = box.width / max(1, box.height)
        if ratio < 0.65 or ratio > 1.45:
            continue
        density = len(pixels) / box.area
        if density < 0.50:
            continue
        map_x, map_y = _image_box_to_jtool_origin(box, room, grid_step)
        if _near_anchor(map_x, map_y, anchors, max_distance=40):
            continue
        score = min(1.0, density * 1.35)
        detections.append(Detection("apple", OBJ_APPLE, map_x, map_y, score, box))
    return _dedupe_detections(detections, min_distance=40)


def _detect_walljumps(
    image: RGBImage,
    room: Box,
    grid_step: int,
    anchors: list[Detection],
) -> list[Detection]:
    components = _connected_components(
        image,
        room,
        lambda r, g, b: _is_walljump_green(r, g, b),
    )
    detections: list[Detection] = []
    for box, pixels in components:
        if not (5 <= box.width <= 10 and 18 <= box.height <= 45):
            continue
        density = len(pixels) / box.area
        if not (0.20 <= density <= 0.62):
            continue
        map_x, map_y = _image_box_to_jtool_origin(box, room, grid_step)
        if _near_anchor(map_x, map_y, anchors, max_distance=32):
            continue
        type_id = OBJ_WALLJUMP_LEFT if map_x % GRID_SIZE < GRID_SIZE / 2 else OBJ_WALLJUMP_RIGHT
        kind = "walljump_left" if type_id == OBJ_WALLJUMP_LEFT else "walljump_right"
        score = min(1.0, density * 1.6)
        detections.append(Detection(kind, type_id, map_x, map_y, score, box))
    return _dedupe_detections(detections, min_distance=24)


def _detect_water(
    image: RGBImage,
    room: Box,
    grid_step: int,
    anchors: list[Detection],
) -> list[Detection]:
    step = max(GRID_SIZE, grid_step)
    detections: list[Detection] = []
    for y in range(0, ROOM_HEIGHT - GRID_SIZE + 1, step):
        for x in range(0, ROOM_WIDTH - GRID_SIZE + 1, step):
            stats = _patch_color_stats(image, room, x, y, GRID_SIZE, _is_water_blue)
            if stats.density < 0.55 or stats.count < 140:
                continue
            if stats.min_quadrant_density < 0.20:
                continue
            features = _patch_features(image, room, x, y, GRID_SIZE)
            if features.edge_density > 0.12:
                continue
            if _near_anchor(x, y, anchors, max_distance=40):
                continue
            detections.append(
                _grid_detection(
                    "water_2",
                    OBJ_WATER_2,
                    x,
                    y,
                    stats.score,
                    image,
                    room,
                    GRID_SIZE,
                )
            )
    return _filter_adjacent_water(_dedupe_detections(detections, min_distance=16))


def _filter_adjacent_water(detections: list[Detection]) -> list[Detection]:
    return [
        det
        for det in detections
        if any(
            other is not det and distance((det.x, det.y), (other.x, other.y)) <= 40
            for other in detections
        )
    ]


def _detect_geometry(image: RGBImage, room: Box, grid_step: int) -> list[Detection]:
    step = max(8, grid_step)
    detections: list[Detection] = []
    for y in range(0, ROOM_HEIGHT - GRID_SIZE + 1, step):
        for x in range(0, ROOM_WIDTH - GRID_SIZE + 1, step):
            patch = _patch_features(image, room, x, y, GRID_SIZE)
            if patch.edge_density < 0.035:
                continue
            spike = _classify_full_spike(patch)
            block = _classify_block(patch)
            if spike and spike.score > max(0.24, block.score + 0.03):
                detections.append(
                    _geometry_detection(
                        spike.kind,
                        spike.type_id,
                        x,
                        y,
                        spike.score,
                        image,
                        room,
                        GRID_SIZE,
                    )
                )
            elif block.score >= 0.30:
                detections.append(
                    _geometry_detection(
                        "block",
                        OBJ_BLOCK,
                        x,
                        y,
                        block.score,
                        image,
                        room,
                        GRID_SIZE,
                    )
                )

    for y in range(0, ROOM_HEIGHT - 16 + 1, step):
        for x in range(0, ROOM_WIDTH - 16 + 1, step):
            patch = _patch_features(image, room, x, y, 16)
            if patch.edge_density < 0.045:
                continue
            mini = _classify_mini_spike(patch)
            if mini and mini.score >= 0.36:
                detections.append(
                    _geometry_detection(
                        mini.kind,
                        mini.type_id,
                        x,
                        y,
                        mini.score,
                        image,
                        room,
                        16,
                    )
                )

    return _dedupe_geometry(detections)


@dataclass(frozen=True, slots=True)
class _PatchFeatures:
    edge_mask: tuple[bool, ...]
    edge_density: float
    border_score: float
    center_score: float


@dataclass(frozen=True, slots=True)
class _GeometryClass:
    kind: str
    type_id: int
    score: float


@dataclass(frozen=True, slots=True)
class _ColorStats:
    count: int
    density: float
    min_quadrant_density: float
    center_x_ratio: float
    center_y_ratio: float
    score: float


def _patch_color_stats(
    image: RGBImage,
    room: Box,
    map_x: int,
    map_y: int,
    map_size: int,
    predicate,
) -> _ColorStats:
    sample = 16
    scale_x = room.width / ROOM_WIDTH
    scale_y = room.height / ROOM_HEIGHT
    left = room.x + map_x * scale_x
    top = room.y + map_y * scale_y
    width = map_size * scale_x
    height = map_size * scale_y
    count = 0
    quadrant_counts = [0, 0, 0, 0]
    quadrant_totals = [0, 0, 0, 0]
    total_x = 0
    total_y = 0

    for sy in range(sample):
        py = int(min(image.height - 1, max(0, top + (sy + 0.5) * height / sample)))
        for sx in range(sample):
            px = int(min(image.width - 1, max(0, left + (sx + 0.5) * width / sample)))
            quadrant = (1 if sx >= sample / 2 else 0) + (2 if sy >= sample / 2 else 0)
            quadrant_totals[quadrant] += 1
            r, g, b = image.pixel(px, py)
            if predicate(r, g, b):
                count += 1
                quadrant_counts[quadrant] += 1
                total_x += sx
                total_y += sy

    density = count / (sample * sample)
    min_quadrant_density = min(
        filled / total
        for filled, total in zip(quadrant_counts, quadrant_totals)
        if total
    )
    if count:
        center_x_ratio = total_x / count / (sample - 1)
        center_y_ratio = total_y / count / (sample - 1)
    else:
        center_x_ratio = 0.5
        center_y_ratio = 0.5
    return _ColorStats(
        count=count,
        density=density,
        min_quadrant_density=min_quadrant_density,
        center_x_ratio=center_x_ratio,
        center_y_ratio=center_y_ratio,
        score=min(1.0, density * 1.7),
    )


def _patch_features(
    image: RGBImage,
    room: Box,
    map_x: int,
    map_y: int,
    map_size: int,
) -> _PatchFeatures:
    sample = 16
    scale_x = room.width / ROOM_WIDTH
    scale_y = room.height / ROOM_HEIGHT
    left = room.x + map_x * scale_x
    top = room.y + map_y * scale_y
    width = map_size * scale_x
    height = map_size * scale_y
    gray: list[int] = []

    for sy in range(sample):
        py = int(min(image.height - 1, max(0, top + (sy + 0.5) * height / sample)))
        for sx in range(sample):
            px = int(min(image.width - 1, max(0, left + (sx + 0.5) * width / sample)))
            r, g, b = image.pixel(px, py)
            gray.append((r * 30 + g * 59 + b * 11) // 100)

    edges: list[bool] = []
    total_strength = 0
    for sy in range(sample):
        for sx in range(sample):
            current = gray[sy * sample + sx]
            right = gray[sy * sample + min(sample - 1, sx + 1)]
            down = gray[min(sample - 1, sy + 1) * sample + sx]
            strength = abs(current - right) + abs(current - down)
            total_strength += strength
            edges.append(strength >= 34)

    edge_density = sum(edges) / len(edges)
    border_positions = [
        sy * sample + sx
        for sy in range(sample)
        for sx in range(sample)
        if sx <= 1 or sx >= sample - 2 or sy <= 1 or sy >= sample - 2
    ]
    center_positions = [
        sy * sample + sx
        for sy in range(4, 12)
        for sx in range(4, 12)
    ]
    border_score = sum(1 for pos in border_positions if edges[pos]) / len(border_positions)
    center_score = sum(1 for pos in center_positions if edges[pos]) / len(center_positions)
    # Low-contrast screenshots can still be meaningful if the whole patch has
    # steady texture; add a small normalized gradient contribution.
    edge_density = max(edge_density, min(0.30, total_strength / (len(edges) * 260)))
    return _PatchFeatures(tuple(edges), edge_density, border_score, center_score)


def _classify_block(patch: _PatchFeatures) -> _GeometryClass:
    score = patch.border_score * 0.65 + patch.center_score * 0.20 + patch.edge_density * 0.35
    return _GeometryClass("block", OBJ_BLOCK, score)


def _classify_full_spike(patch: _PatchFeatures) -> _GeometryClass | None:
    return _best_triangle_class(
        patch,
        [
            ("spike_up", OBJ_SPIKE_UP, "up"),
            ("spike_right", OBJ_SPIKE_RIGHT, "right"),
            ("spike_left", OBJ_SPIKE_LEFT, "left"),
            ("spike_down", OBJ_SPIKE_DOWN, "down"),
        ],
    )


def _classify_mini_spike(patch: _PatchFeatures) -> _GeometryClass | None:
    return _best_triangle_class(
        patch,
        [
            ("mini_spike_up", OBJ_MINI_SPIKE_UP, "up"),
            ("mini_spike_right", OBJ_MINI_SPIKE_RIGHT, "right"),
            ("mini_spike_left", OBJ_MINI_SPIKE_LEFT, "left"),
            ("mini_spike_down", OBJ_MINI_SPIKE_DOWN, "down"),
        ],
    )


def _best_triangle_class(
    patch: _PatchFeatures,
    classes: list[tuple[str, int, str]],
) -> _GeometryClass | None:
    best: _GeometryClass | None = None
    for kind, type_id, direction in classes:
        outline, outside = _triangle_masks(direction)
        outline_hits = sum(1 for pos in outline if patch.edge_mask[pos]) / len(outline)
        outside_hits = sum(1 for pos in outside if patch.edge_mask[pos]) / max(1, len(outside))
        score = outline_hits * 0.78 + patch.edge_density * 0.38 - outside_hits * 0.18
        if best is None or score > best.score:
            best = _GeometryClass(kind, type_id, score)
    return best


def _triangle_masks(direction: str) -> tuple[list[int], list[int]]:
    sample = 16
    center = (sample - 1) / 2
    outline: list[int] = []
    outside: list[int] = []
    for sy in range(sample):
        for sx in range(sample):
            if direction == "up":
                side = abs(sx - center) * 2
                edge_dist = min(abs(sy - side), abs(sy - (sample - 1)))
                inside = sy >= side - 1
            elif direction == "down":
                side = (sample - 1) - abs(sx - center) * 2
                edge_dist = min(abs(sy - side), sy)
                inside = sy <= side + 1
            elif direction == "right":
                side = (sample - 1) - abs(sy - center) * 2
                edge_dist = min(abs(sx - side), sx)
                inside = sx <= side + 1
            else:
                side = abs(sy - center) * 2
                edge_dist = min(abs(sx - side), abs(sx - (sample - 1)))
                inside = sx >= side - 1
            pos = sy * sample + sx
            if edge_dist <= 1.15:
                outline.append(pos)
            elif not inside:
                outside.append(pos)
    return outline, outside


def _geometry_detection(
    kind: str,
    type_id: int,
    x: int,
    y: int,
    score: float,
    image: RGBImage,
    room: Box,
    size: int,
) -> Detection:
    scale_x = room.width / ROOM_WIDTH
    scale_y = room.height / ROOM_HEIGHT
    image_box = Box(
        int(round(room.x + x * scale_x)),
        int(round(room.y + y * scale_y)),
        max(1, int(round(size * scale_x))),
        max(1, int(round(size * scale_y))),
    )
    return Detection(kind, type_id, x, y, min(1.0, score), image_box)


def _grid_detection(
    kind: str,
    type_id: int,
    x: int,
    y: int,
    score: float,
    image: RGBImage,
    room: Box,
    size: int,
) -> Detection:
    return _geometry_detection(kind, type_id, x, y, score, image, room, size)


def _dedupe_geometry(detections: list[Detection]) -> list[Detection]:
    result: list[Detection] = []
    for det in sorted(
        detections,
        key=lambda item: (item.type_id in MINI_SPIKE_TYPES, -item.score),
    ):
        if any(_geometry_conflicts(det, existing) for existing in result):
            continue
        result.append(det)
    return sorted(result, key=lambda item: (item.y, item.x, -item.score))


def _geometry_conflicts(det: Detection, existing: Detection) -> bool:
    if det.type_id in MINI_SPIKE_TYPES and existing.type_id in MINI_SPIKE_TYPES:
        return distance((det.x, det.y), (existing.x, existing.y)) < 14
    if det.type_id in MINI_SPIKE_TYPES or existing.type_id in MINI_SPIKE_TYPES:
        mini = det if det.type_id in MINI_SPIKE_TYPES else existing
        return (
            mini.score < MINI_SPIKE_COEXIST_SCORE
            and distance((det.x, det.y), (existing.x, existing.y)) < 20
        )
    return (
        det.type_id == existing.type_id
        and distance((det.x, det.y), (existing.x, existing.y)) < 28
    )


def _dedupe_overlapping_geometry(detections: list[Detection]) -> list[Detection]:
    # Saves and warps are more reliable than the experimental geometry pass.
    anchors = [det for det in detections if det.type_id not in GEOMETRY_TYPES]
    result: list[Detection] = []
    for det in detections:
        if det.type_id not in GEOMETRY_TYPES:
            result.append(det)
            continue
        if any(distance((det.x, det.y), (anchor.x, anchor.y)) < 20 for anchor in anchors):
            continue
        result.append(det)
    return result


def _near_anchor(
    x: int,
    y: int,
    anchors: list[Detection],
    max_distance: float,
) -> bool:
    return any(distance((x, y), (anchor.x, anchor.y)) < max_distance for anchor in anchors)


def _connected_components(
    image: RGBImage,
    room: Box,
    predicate,
) -> list[tuple[Box, list[tuple[int, int]]]]:
    left = max(0, room.x)
    top = max(0, room.y)
    right = min(image.width, room.right)
    bottom = min(image.height, room.bottom)
    width = right - left
    height = bottom - top
    mask = bytearray(width * height)

    for y in range(top, bottom):
        row = image.row(y)
        base = (y - top) * width
        for x in range(left, right):
            pos = x * 3
            if predicate(row[pos], row[pos + 1], row[pos + 2]):
                mask[base + (x - left)] = 1

    components: list[tuple[Box, list[tuple[int, int]]]] = []
    for index, value in enumerate(mask):
        if value != 1:
            continue
        stack = [index]
        mask[index] = 2
        pixels: list[tuple[int, int]] = []
        min_x = max_x = left + (index % width)
        min_y = max_y = top + (index // width)
        while stack:
            current = stack.pop()
            cx = current % width
            cy = current // width
            px = left + cx
            py = top + cy
            pixels.append((px, py))
            if px < min_x:
                min_x = px
            elif px > max_x:
                max_x = px
            if py < min_y:
                min_y = py
            elif py > max_y:
                max_y = py

            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if nx < 0 or ny < 0 or nx >= width or ny >= height:
                    continue
                neighbor = ny * width + nx
                if mask[neighbor] == 1:
                    mask[neighbor] = 2
                    stack.append(neighbor)
        if len(pixels) >= 8:
            components.append((Box(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1), pixels))
    return components


def _image_box_to_jtool_origin(box: Box, room: Box, grid_step: int) -> tuple[int, int]:
    scale_x = room.width / ROOM_WIDTH
    scale_y = room.height / ROOM_HEIGHT
    raw_x = (box.center_x - room.x) / scale_x - GRID_SIZE / 2
    raw_y = (box.center_y - room.y) / scale_y - GRID_SIZE / 2
    return round_to_step(raw_x, grid_step), round_to_step(raw_y, grid_step)


def _dedupe_detections(detections: list[Detection], min_distance: float = 24) -> list[Detection]:
    result: list[Detection] = []
    for det in sorted(detections, key=lambda item: item.score, reverse=True):
        if any(
            det.type_id == existing.type_id
            and distance((det.x, det.y), (existing.x, existing.y)) < min_distance
            for existing in result
        ):
            continue
        result.append(det)
    return sorted(result, key=lambda item: (item.y, item.x, -item.score))


def _is_save_yellow(r: int, g: int, b: int) -> bool:
    return r > 170 and g > 130 and b < 90 and r > b * 2


def _is_save_red(r: int, g: int, b: int) -> bool:
    return r > 120 and g < 95 and b < 95 and r > g * 1.5


def _is_tinted_save_yellow(r: int, g: int, b: int) -> bool:
    return r > 95 and g > 145 and 80 < b < 215 and g > r + 25 and g > b + 20


def _is_apple_red(r: int, g: int, b: int) -> bool:
    return r > 150 and g < 95 and b < 95 and r > g * 1.8 and r > b * 1.8


def _is_walljump_green(r: int, g: int, b: int) -> bool:
    return g > 105 and r < 115 and b < 135 and g > r * 1.35 and g > b * 1.20


def _is_water_blue(r: int, g: int, b: int) -> bool:
    return b > 135 and g > 105 and r < 150 and b > r + 35 and g > r + 20


def _looks_cyan_tinted(image: RGBImage, room: Box) -> bool:
    total_r = total_g = total_b = count = 0
    step = 8
    for y in range(max(0, room.y), min(image.height, room.bottom), step):
        row = image.row(y)
        for x in range(max(0, room.x), min(image.width, room.right), step):
            offset = x * 3
            total_r += row[offset]
            total_g += row[offset + 1]
            total_b += row[offset + 2]
            count += 1
    if count == 0:
        return False
    avg_r = total_r / count
    avg_g = total_g / count
    avg_b = total_b / count
    return avg_b > avg_g + 15 and avg_g > avg_r + 55


def _is_warp_blue(r: int, g: int, b: int) -> bool:
    return b > 115 and r < 95 and g < 95 and b > r * 1.4


def _is_warp_purple(r: int, g: int, b: int) -> bool:
    return b > 120 and r > 55 and g < 80 and b > g * 1.7


def _has_dark_portal_core(image: RGBImage, box: Box) -> bool:
    center_x = int(round(box.center_x))
    center_y = int(round(box.center_y))
    total_r = total_g = total_b = count = 0
    for y in range(center_y - 2, center_y + 3):
        for x in range(center_x - 2, center_x + 3):
            if x < 0 or y < 0 or x >= image.width or y >= image.height:
                continue
            r, g, b = image.pixel(x, y)
            total_r += r
            total_g += g
            total_b += b
            count += 1
    if count == 0:
        return False
    avg_r = total_r / count
    avg_g = total_g / count
    avg_b = total_b / count
    return avg_b < 95 and avg_r < 95 and avg_g < 95
