"""First-pass screenshot scanner.

This module intentionally starts with high-confidence, color-stable objects:
saves and warps. Blocks and spikes need a stronger tileset/model layer, but the
coordinate pipeline here is the same one they will use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .constants import GRID_SIZE, OBJ_SAVE, OBJ_WARP, ROOM_HEIGHT, ROOM_WIDTH
from .geometry import Box, distance, round_to_step
from .image import RGBImage, load_png
from .jmap import JMap, JMapObject
from .save_picker import move_start_to_save


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
) -> ScanResult:
    image = load_png(path)
    return scan_image(image, room_box=room_box, grid_step=grid_step)


def scan_image(
    image: RGBImage,
    room_box: Box | None = None,
    grid_step: int = GRID_SIZE,
) -> ScanResult:
    box = room_box or detect_room_box(image)
    detections: list[Detection] = []
    detections.extend(_detect_saves(image, box, grid_step))
    detections.extend(_detect_warps(image, box, grid_step))
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
