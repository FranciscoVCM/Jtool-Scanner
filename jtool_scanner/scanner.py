"""First-pass screenshot scanner.

This module starts with high-confidence, color-stable objects and includes an
experimental edge/shape pass for blocks and spikes. The geometry pass is useful
for diagnostics, but it is not yet expected to produce final maps by itself.
"""

from __future__ import annotations

from collections import defaultdict, deque
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
MINI_SPIKE_MIN_SCORE = 0.44
MINI_SPIKE_MIN_DIRECTION_MARGIN = 0.04
MINI_SPIKE_BLOCKLIKE_SCORE = 0.80
MINI_SPIKE_BLOCKLIKE_DIRECTION_MARGIN = 0.06
FULL_SPIKE_MIN_OUTLINE_DELTA = 0.18
FULL_SPIKE_MIN_DIRECTION_MARGIN = 0.05
FULL_SPIKE_LOW_MARGIN_SCORE_CEILING = 0.32
FULL_SPIKE_BLOCKLIKE_OUTLINE_DELTA = 0.26
FULL_SPIKE_BLOCKLIKE_SCORE_MARGIN = 0.04
FULL_SPIKE_AXIS_SNAP_STEP = 16
BLOCK_MIN_SCORE = 0.30
WEAK_BLOCK_ALIGNED_MIN_SCORE = 0.28
BLOCK_ALIGNMENT_STEP = 16
PREFERRED_BLOCK_ALIGNMENT_STEP = 32
BLOCKLIKE_SPIKE_MIN_BLOCK_SCORE = 0.14
BLOCKLIKE_SPIKE_MAX_SPIKE_SCORE = 0.28
BLOCKLIKE_SPIKE_MIN_BORDER_SCORE = 0.12
BLOCKLIKE_SPIKE_MAX_CENTER_SCORE = 0.02
BLOCKLIKE_SPIKE_BLOCK_SCORE = WEAK_BLOCK_ALIGNED_MIN_SCORE + 0.001
BLOCK_RUN_GAP_STEP = 32
BLOCK_RUN_GAP_MIN_BLOCK_SCORE = 0.12
BLOCK_RUN_GAP_MIN_EDGE_DENSITY = 0.11
BLOCK_RUN_GAP_HOLLOW_MIN_BLOCK_SCORE = 0.04
BLOCK_RUN_GAP_HOLLOW_MIN_EDGE_DENSITY = 0.06
BLOCK_RUN_GAP_HOLLOW_MIN_BORDER_SCORE = 0.035
BLOCK_RUN_GAP_HOLLOW_MAX_CENTER_SCORE = 0.02
BLOCK_RUN_GAP_SCORE = WEAK_BLOCK_ALIGNED_MIN_SCORE + 0.002
OUTLINE_BLOCK_GRID_STEP = 16
OUTLINE_BLOCK_CENTER_MAX = 0.02
OUTLINE_BLOCK_BORDER_MIN = 0.10
OUTLINE_BLOCK_EDGE_MIN = 0.055
OUTLINE_BLOCK_ROOM_MIN_CANDIDATES = 120
WALLJUMP_COMPONENT_MAX_WIDTH = 13
WALLJUMP_COMPONENT_MIN_HEIGHT = 18
WALLJUMP_COMPONENT_MIN_DENSITY = 0.12
WALLJUMP_COMPONENT_MAX_DENSITY = 0.50
WALLJUMP_COMPONENT_MIN_AVG_BLUE = 60
WALLJUMP_SPARSE_COMPONENT_LIMIT = 100
WALLJUMP_PATCH_MIN_COUNT = 6
WALLJUMP_PATCH_MAX_COUNT = 24
WALLJUMP_PATCH_MIN_DENSITY = 0.035
WALLJUMP_PATCH_MAX_DENSITY = 0.095
WALLJUMP_PATCH_MIN_SIDE_BIAS = 0.28
WALLJUMP_SPARSE_MIN_LIGHT_RATIO = 0.45
WALLJUMP_SPARSE_BROAD_LIGHT_RATIO = 0.85
WATER_MIN_BLUE_LIFT = 10.0
WATER_MAX_BLUE_LIFT = 55.0
WATER_PALE_MAX_BLUE_LIFT = 50.0
WATER_DENSE_MIN_DENSITY = 0.40
WATER_DENSE_MIN_QUADRANT = 0.08
WATER_MAX_EDGE_DENSITY = 0.38
WATER_PALE_MAX_EDGE_DENSITY = 0.42
WATER_DEDUPE_DISTANCE = 24.0
CATHARSIS_ROOM_MAX_BRIGHTNESS = 100.0
CATHARSIS_ROOM_MAX_SATURATION = 0.16
CATHARSIS_ROOM_MIN_BLUE_OVER_RED = 8.0
CATHARSIS_ROOM_MIN_GREEN_MINUS_RED = -4.0
CATHARSIS_MAX_SATURATION = 0.13
CATHARSIS_WEAK_MIN_BLUE_LIFT = 1.0
CATHARSIS_WEAK_MIN_BRIGHTNESS = 2.0
CATHARSIS_WEAK_MAX_BRIGHTNESS = 150.0
CATHARSIS_WEAK_MAX_EDGE_DENSITY = 0.24
CATHARSIS_WEAK_MIN_GREEN_MINUS_RED = -8.0
CATHARSIS_SEED_MIN_BLUE_LIFT = 3.5
CATHARSIS_SEED_MIN_BRIGHTNESS = 20.0
CATHARSIS_SEED_MAX_BRIGHTNESS = 150.0
CATHARSIS_SEED_MAX_EDGE_DENSITY = 0.14
CATHARSIS_SEED_MIN_GREEN_MINUS_RED = -3.0
CATHARSIS_ISOLATED_SEED_MIN_BRIGHTNESS = 45.0
CATHARSIS_TAIL_MIN_BRIGHTNESS = 45.0
CATHARSIS_TAIL_MIN_BLUE_LIFT = 2.5
CATHARSIS_DARK_TAIL_MAX_BRIGHTNESS = 45.0
CATHARSIS_DARK_TAIL_MIN_BLUE_LIFT = 8.0
CATHARSIS_DARK_TAIL_MAX_EDGE_DENSITY = 0.04


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
    allow_tinted_warp = _looks_cyan_tinted(image, room)
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
        has_dark_core = _has_dark_portal_core(image, box)
        if not has_dark_core and not (allow_tinted_warp and density >= 0.45):
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
        if not (
            3 <= box.width <= WALLJUMP_COMPONENT_MAX_WIDTH
            and WALLJUMP_COMPONENT_MIN_HEIGHT <= box.height <= 45
        ):
            continue
        density = len(pixels) / box.area
        if not (WALLJUMP_COMPONENT_MIN_DENSITY <= density <= WALLJUMP_COMPONENT_MAX_DENSITY):
            continue
        _, _, avg_b = _average_pixel_color(image, pixels)
        if avg_b < WALLJUMP_COMPONENT_MIN_AVG_BLUE:
            continue
        map_x, map_y = _image_box_to_jtool_origin(box, room, grid_step)
        if _near_anchor(map_x, map_y, anchors, max_distance=32):
            continue
        type_id = OBJ_WALLJUMP_LEFT if map_x % GRID_SIZE < GRID_SIZE / 2 else OBJ_WALLJUMP_RIGHT
        kind = "walljump_left" if type_id == OBJ_WALLJUMP_LEFT else "walljump_right"
        score = min(1.0, density * 1.6)
        detections.append(Detection(kind, type_id, map_x, map_y, score, box))
    light_ratio = _light_sample_ratio(image, room)
    if (
        len(components) < WALLJUMP_SPARSE_COMPONENT_LIMIT
        and light_ratio >= WALLJUMP_SPARSE_MIN_LIGHT_RATIO
    ):
        predicate = (
            _is_sparse_walljump_green
            if light_ratio >= WALLJUMP_SPARSE_BROAD_LIGHT_RATIO
            else _is_walljump_green
        )
        detections.extend(
            _detect_sparse_walljump_patches(image, room, grid_step, anchors, predicate)
        )
    return _dedupe_walljumps(detections, min_distance=32)


def _detect_sparse_walljump_patches(
    image: RGBImage,
    room: Box,
    grid_step: int,
    anchors: list[Detection],
    predicate,
) -> list[Detection]:
    detections: list[Detection] = []
    step = max(8, grid_step)
    for y in range(0, ROOM_HEIGHT - GRID_SIZE + 1, step):
        for x in range(0, ROOM_WIDTH - GRID_SIZE + 1, step):
            stats = _patch_color_stats(image, room, x, y, GRID_SIZE, predicate)
            side_bias = abs(stats.center_x_ratio - 0.5)
            if stats.count < WALLJUMP_PATCH_MIN_COUNT:
                continue
            if stats.count > WALLJUMP_PATCH_MAX_COUNT:
                continue
            if stats.density < WALLJUMP_PATCH_MIN_DENSITY:
                continue
            if stats.density > WALLJUMP_PATCH_MAX_DENSITY:
                continue
            if side_bias < WALLJUMP_PATCH_MIN_SIDE_BIAS:
                continue
            if _near_anchor(x, y, anchors, max_distance=40):
                continue
            type_id = OBJ_WALLJUMP_LEFT if stats.center_x_ratio > 0.5 else OBJ_WALLJUMP_RIGHT
            kind = "walljump_left" if type_id == OBJ_WALLJUMP_LEFT else "walljump_right"
            score = min(1.0, stats.density * 3 + side_bias)
            detections.append(
                _grid_detection(kind, type_id, x, y, score, image, room, GRID_SIZE)
            )
    return detections


def _detect_water(
    image: RGBImage,
    room: Box,
    grid_step: int,
    anchors: list[Detection],
) -> list[Detection]:
    del anchors
    room_profile = _room_color_profile(image, room)
    step = max(8, grid_step)
    detections: list[Detection] = []
    for y in range(0, ROOM_HEIGHT - GRID_SIZE + 1, step):
        for x in range(0, ROOM_WIDTH - GRID_SIZE + 1, step):
            profile = _patch_color_profile(image, room, x, y, GRID_SIZE)
            if not _is_water_profile_candidate(profile, room_profile):
                continue
            stats = _patch_color_stats(image, room, x, y, GRID_SIZE, _is_water_blue)
            features = _patch_features(image, room, x, y, GRID_SIZE)
            if not _is_water_patch(stats, features, profile, room_profile):
                continue
            score = min(
                1.0,
                max(
                    stats.density * 1.2,
                    (profile.avg_b - profile.avg_r) / 120,
                    (room_profile.avg_r - profile.avg_r) / 120,
                ),
            )
            detections.append(
                _grid_detection(
                    "water_2",
                    OBJ_WATER_2,
                    x,
                    y,
                    score,
                    image,
                    room,
                    GRID_SIZE,
                )
            )
    detections.extend(_detect_catharsis_water(image, room, room_profile))
    return _dedupe_water(detections, min_distance=WATER_DEDUPE_DISTANCE)


def _detect_catharsis_water(
    image: RGBImage,
    room: Box,
    room_profile: _ColorProfile,
) -> list[Detection]:
    if not _is_catharsis_room(room_profile):
        return []

    weak_cells: set[tuple[int, int]] = set()
    seed_cells: set[tuple[int, int]] = set()
    cell_info: dict[
        tuple[int, int],
        tuple[_ColorProfile, _PatchFeatures, tuple[float, float, float]],
    ] = {}
    for y in range(0, ROOM_HEIGHT - GRID_SIZE + 1, GRID_SIZE):
        for x in range(0, ROOM_WIDTH - GRID_SIZE + 1, GRID_SIZE):
            cell = (x, y)
            profile = _patch_color_profile(image, room, x, y, GRID_SIZE)
            features = _patch_features(image, room, x, y, GRID_SIZE)
            metrics = _color_profile_metrics(profile)
            cell_info[cell] = (profile, features, metrics)
            if _is_catharsis_weak(profile, features, metrics):
                weak_cells.add(cell)
            if _is_catharsis_seed(profile, features, metrics):
                seed_cells.add(cell)

    output_cells: set[tuple[int, int]] = set()
    seed_component_sizes: dict[tuple[int, int], int] = {}
    column_seed_ranges: list[tuple[int, int, int]] = []

    # Catharsis water is close to dark background art, so only vertical strips are
    # recovered here. Broader horizontal expansion produced convincing false hits.
    for component in _connected_seed_components(seed_cells):
        for cell in component:
            seed_component_sizes[cell] = len(component)
        if len(component) < 2:
            continue

        columns: dict[int, list[int]] = defaultdict(list)
        for x, y in component:
            columns[x].append(y)

        for x, ys in columns.items():
            if len(ys) < 2:
                continue
            min_y = min(ys)
            max_y = max(ys)
            column_seed_ranges.append((x, min_y, max_y))
            for y in range(min_y, max_y + 1, GRID_SIZE):
                if (x, y) in weak_cells:
                    output_cells.add((x, y))
            for y in (min_y - GRID_SIZE, max_y + GRID_SIZE):
                if (x, y) in weak_cells:
                    output_cells.add((x, y))

    for x, min_y, max_y in column_seed_ranges:
        for direction, start_y in ((-1, min_y - GRID_SIZE), (1, max_y + GRID_SIZE)):
            y = start_y + direction * GRID_SIZE
            for _ in range(2):
                cell = (x, y)
                if cell not in weak_cells or not _is_catharsis_tail(
                    cell_info[cell],
                    allow_dark=False,
                ):
                    break
                output_cells.add(cell)
                y += direction * GRID_SIZE

    for x, y in seed_cells:
        if seed_component_sizes.get((x, y), 1) != 1:
            continue
        if cell_info[(x, y)][2][1] < CATHARSIS_ISOLATED_SEED_MIN_BRIGHTNESS:
            continue
        for direction in (-1, 1):
            first = (x, y + direction * GRID_SIZE)
            if first not in weak_cells or not _is_catharsis_tail(
                cell_info[first],
                allow_dark=False,
            ):
                continue
            output_cells.add((x, y))
            output_cells.add(first)
            tail_y = y + direction * GRID_SIZE * 2
            for _ in range(2):
                cell = (x, tail_y)
                if cell not in weak_cells or not _is_catharsis_tail(
                    cell_info[cell],
                    allow_dark=True,
                ):
                    break
                output_cells.add(cell)
                tail_y += direction * GRID_SIZE

    return [
        _grid_detection("water_2", OBJ_WATER_2, x, y, 0.55, image, room, GRID_SIZE)
        for x, y in sorted(output_cells)
    ]


def _is_catharsis_room(profile: _ColorProfile) -> bool:
    brightness = _profile_brightness(profile)
    return (
        brightness <= CATHARSIS_ROOM_MAX_BRIGHTNESS
        and profile.saturation <= CATHARSIS_ROOM_MAX_SATURATION
        and profile.avg_b >= profile.avg_r + CATHARSIS_ROOM_MIN_BLUE_OVER_RED
        and profile.avg_g >= profile.avg_r + CATHARSIS_ROOM_MIN_GREEN_MINUS_RED
    )


def _color_profile_metrics(profile: _ColorProfile) -> tuple[float, float, float]:
    blue_lift = profile.avg_b - max(profile.avg_r, profile.avg_g)
    return blue_lift, _profile_brightness(profile), profile.avg_g - profile.avg_r


def _profile_brightness(profile: _ColorProfile) -> float:
    return (profile.avg_r + profile.avg_g + profile.avg_b) / 3


def _is_catharsis_weak(
    profile: _ColorProfile,
    features: _PatchFeatures,
    metrics: tuple[float, float, float],
) -> bool:
    blue_lift, brightness, green_minus_red = metrics
    return (
        profile.saturation <= CATHARSIS_MAX_SATURATION
        and blue_lift >= CATHARSIS_WEAK_MIN_BLUE_LIFT
        and CATHARSIS_WEAK_MIN_BRIGHTNESS <= brightness <= CATHARSIS_WEAK_MAX_BRIGHTNESS
        and features.edge_density <= CATHARSIS_WEAK_MAX_EDGE_DENSITY
        and green_minus_red >= CATHARSIS_WEAK_MIN_GREEN_MINUS_RED
    )


def _is_catharsis_seed(
    profile: _ColorProfile,
    features: _PatchFeatures,
    metrics: tuple[float, float, float],
) -> bool:
    blue_lift, brightness, green_minus_red = metrics
    return (
        profile.saturation <= CATHARSIS_MAX_SATURATION
        and blue_lift >= CATHARSIS_SEED_MIN_BLUE_LIFT
        and CATHARSIS_SEED_MIN_BRIGHTNESS <= brightness <= CATHARSIS_SEED_MAX_BRIGHTNESS
        and features.edge_density <= CATHARSIS_SEED_MAX_EDGE_DENSITY
        and green_minus_red >= CATHARSIS_SEED_MIN_GREEN_MINUS_RED
    )


def _is_catharsis_tail(
    cell_info: tuple[_ColorProfile, _PatchFeatures, tuple[float, float, float]],
    allow_dark: bool,
) -> bool:
    _, features, metrics = cell_info
    blue_lift, brightness, _ = metrics
    if (
        brightness >= CATHARSIS_TAIL_MIN_BRIGHTNESS
        and blue_lift >= CATHARSIS_TAIL_MIN_BLUE_LIFT
        and features.edge_density <= CATHARSIS_WEAK_MAX_EDGE_DENSITY
    ):
        return True
    return (
        allow_dark
        and brightness <= CATHARSIS_DARK_TAIL_MAX_BRIGHTNESS
        and blue_lift >= CATHARSIS_DARK_TAIL_MIN_BLUE_LIFT
        and features.edge_density <= CATHARSIS_DARK_TAIL_MAX_EDGE_DENSITY
    )


def _connected_seed_components(
    seed_cells: set[tuple[int, int]],
) -> list[list[tuple[int, int]]]:
    components: list[list[tuple[int, int]]] = []
    seen: set[tuple[int, int]] = set()
    for seed in sorted(seed_cells):
        if seed in seen:
            continue
        queue: deque[tuple[int, int]] = deque([seed])
        seen.add(seed)
        component: list[tuple[int, int]] = []
        while queue:
            x, y = queue.popleft()
            component.append((x, y))
            for neighbor in (
                (x + GRID_SIZE, y),
                (x - GRID_SIZE, y),
                (x, y + GRID_SIZE),
                (x, y - GRID_SIZE),
            ):
                if neighbor in seed_cells and neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(component)
    return components


def _is_water_patch(
    stats: _ColorStats,
    features: _PatchFeatures,
    profile: _ColorProfile,
    room_profile: _ColorProfile,
) -> bool:
    if not _is_water_profile_candidate(profile, room_profile):
        return False

    red_drop = room_profile.avg_r - profile.avg_r
    room_blue_lift = profile.avg_b - room_profile.avg_b
    cyan_room = (
        room_profile.avg_b > room_profile.avg_g + 15
        and room_profile.avg_g > room_profile.avg_r + 55
    )
    dense_water = (
        stats.density >= WATER_DENSE_MIN_DENSITY
        and stats.min_quadrant_density >= WATER_DENSE_MIN_QUADRANT
        and features.edge_density <= WATER_MAX_EDGE_DENSITY
        and (room_blue_lift >= 12 or red_drop >= 28 or cyan_room)
        and (cyan_room or profile.saturation <= 0.62)
    )
    pale_water = (
        profile.avg_b >= 205
        and profile.avg_g >= 170
        and profile.avg_g > profile.avg_r + 8
        and red_drop >= 25
        and profile.avg_b - profile.avg_g <= WATER_PALE_MAX_BLUE_LIFT
        and features.edge_density <= WATER_PALE_MAX_EDGE_DENSITY
    )
    return dense_water or pale_water


def _is_water_profile_candidate(
    profile: _ColorProfile,
    room_profile: _ColorProfile,
) -> bool:
    blue_lift = profile.avg_b - profile.avg_g
    if blue_lift <= WATER_MIN_BLUE_LIFT or blue_lift > WATER_MAX_BLUE_LIFT:
        return False

    pale_room = room_profile.avg_b > 200 and room_profile.avg_r > 150
    if pale_room and profile.avg_g > room_profile.avg_g - 5:
        return False
    return True


def _dedupe_water(detections: list[Detection], min_distance: float) -> list[Detection]:
    result: list[Detection] = []
    for det in sorted(
        detections,
        key=lambda item: (
            -item.score,
            item.y % GRID_SIZE != 0,
            item.x % GRID_SIZE != 0,
            item.y,
            item.x,
        ),
    ):
        if any(
            distance((det.x, det.y), (existing.x, existing.y)) < min_distance
            for existing in result
        ):
            continue
        result.append(det)
    return sorted(result, key=lambda item: (item.y, item.x, -item.score))


def _dedupe_walljumps(detections: list[Detection], min_distance: float) -> list[Detection]:
    result: list[Detection] = []
    for det in sorted(detections, key=lambda item: item.score, reverse=True):
        if any(
            distance((det.x, det.y), (existing.x, existing.y)) < min_distance
            for existing in result
        ):
            continue
        result.append(det)
    return sorted(result, key=lambda item: (item.y, item.x, -item.score))


def _detect_geometry(image: RGBImage, room: Box, grid_step: int) -> list[Detection]:
    step = max(8, grid_step)
    detections: list[Detection] = []
    patch_candidates: list[_GeometryPatchCandidate] = []
    outline_block_candidates = 0

    for y in range(0, ROOM_HEIGHT - GRID_SIZE + 1, step):
        for x in range(0, ROOM_WIDTH - GRID_SIZE + 1, step):
            patch = _patch_features(image, room, x, y, GRID_SIZE)
            if patch.edge_density < 0.035:
                continue
            spike = _classify_full_spike(patch)
            block = _classify_block(patch)
            candidate = _GeometryPatchCandidate(x, y, patch, spike, block)
            patch_candidates.append(candidate)
            if (
                not (spike and _accept_full_spike(spike, block))
                and not _accept_block(candidate)
                and _outline_block_score(candidate) is not None
            ):
                outline_block_candidates += 1

    allow_outline_blocks = (
        outline_block_candidates >= OUTLINE_BLOCK_ROOM_MIN_CANDIDATES
    )

    for candidate in patch_candidates:
        if candidate.spike and _accept_full_spike(candidate.spike, candidate.block):
            if _is_blocklike_spike_candidate(candidate):
                detections.append(
                    _geometry_detection(
                        "block",
                        OBJ_BLOCK,
                        candidate.x,
                        candidate.y,
                        max(BLOCKLIKE_SPIKE_BLOCK_SCORE, candidate.block.score),
                        image,
                        room,
                        GRID_SIZE,
                    )
                )
            else:
                detections.append(
                    _geometry_detection(
                        candidate.spike.kind,
                        candidate.spike.type_id,
                        candidate.x,
                        candidate.y,
                        candidate.spike.score,
                        image,
                        room,
                        GRID_SIZE,
                    )
                )
        elif _accept_block(candidate):
            detections.append(
                _geometry_detection(
                    "block",
                    OBJ_BLOCK,
                    candidate.x,
                    candidate.y,
                    candidate.block.score,
                    image,
                    room,
                    GRID_SIZE,
                )
            )
        elif allow_outline_blocks:
            outline_score = _outline_block_score(candidate)
            if outline_score is not None:
                detections.append(
                    _geometry_detection(
                        "block",
                        OBJ_BLOCK,
                        candidate.x,
                        candidate.y,
                        outline_score,
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
            block = _classify_block(patch)
            if mini and _accept_mini_spike(mini, block):
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

    detections = _dedupe_geometry(detections)
    detections = _recover_block_run_gaps(detections, image, room)
    return _normalize_full_spike_detections(_dedupe_geometry(detections))


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
    direction_margin: float = 1.0
    outline_delta: float = 1.0


@dataclass(frozen=True, slots=True)
class _GeometryPatchCandidate:
    x: int
    y: int
    patch: _PatchFeatures
    spike: _GeometryClass | None
    block: _GeometryClass


@dataclass(frozen=True, slots=True)
class _ColorStats:
    count: int
    density: float
    min_quadrant_density: float
    center_x_ratio: float
    center_y_ratio: float
    score: float


@dataclass(frozen=True, slots=True)
class _ColorProfile:
    avg_r: float
    avg_g: float
    avg_b: float
    saturation: float


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


def _patch_color_profile(
    image: RGBImage,
    room: Box,
    map_x: int,
    map_y: int,
    map_size: int,
) -> _ColorProfile:
    sample = 16
    scale_x = room.width / ROOM_WIDTH
    scale_y = room.height / ROOM_HEIGHT
    left = room.x + map_x * scale_x
    top = room.y + map_y * scale_y
    width = map_size * scale_x
    height = map_size * scale_y
    total_r = total_g = total_b = total_saturation = count = 0

    for sy in range(sample):
        py = int(min(image.height - 1, max(0, top + (sy + 0.5) * height / sample)))
        for sx in range(sample):
            px = int(min(image.width - 1, max(0, left + (sx + 0.5) * width / sample)))
            r, g, b = image.pixel(px, py)
            total_r += r
            total_g += g
            total_b += b
            total_saturation += max(r, g, b) - min(r, g, b)
            count += 1

    return _ColorProfile(
        avg_r=total_r / count,
        avg_g=total_g / count,
        avg_b=total_b / count,
        saturation=total_saturation / (count * 255),
    )


def _room_color_profile(image: RGBImage, room: Box) -> _ColorProfile:
    total_r = total_g = total_b = total_saturation = count = 0
    step = 16
    for y in range(max(0, room.y), min(image.height, room.bottom), step):
        row = image.row(y)
        for x in range(max(0, room.x), min(image.width, room.right), step):
            offset = x * 3
            r = row[offset]
            g = row[offset + 1]
            b = row[offset + 2]
            total_r += r
            total_g += g
            total_b += b
            total_saturation += max(r, g, b) - min(r, g, b)
            count += 1
    if count == 0:
        return _ColorProfile(0.0, 0.0, 0.0, 0.0)
    return _ColorProfile(
        avg_r=total_r / count,
        avg_g=total_g / count,
        avg_b=total_b / count,
        saturation=total_saturation / (count * 255),
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
    candidates: list[tuple[float, str, int, float]] = []
    for kind, type_id, direction in classes:
        outline, outside = _triangle_masks(direction)
        outline_hits = sum(1 for pos in outline if patch.edge_mask[pos]) / len(outline)
        outside_hits = sum(1 for pos in outside if patch.edge_mask[pos]) / max(1, len(outside))
        score = outline_hits * 0.78 + patch.edge_density * 0.38 - outside_hits * 0.18
        candidates.append((score, kind, type_id, outline_hits - outside_hits))
    candidates.sort(reverse=True)
    best_score, kind, type_id, outline_delta = candidates[0]
    second_score = candidates[1][0] if len(candidates) > 1 else 0.0
    return _GeometryClass(
        kind,
        type_id,
        best_score,
        best_score - second_score,
        outline_delta,
    )


def _accept_full_spike(spike: _GeometryClass, block: _GeometryClass) -> bool:
    if spike.score <= max(0.24, block.score + 0.03):
        return False
    if spike.outline_delta < FULL_SPIKE_MIN_OUTLINE_DELTA:
        return False
    if (
        spike.outline_delta < FULL_SPIKE_BLOCKLIKE_OUTLINE_DELTA
        and spike.score < block.score + FULL_SPIKE_BLOCKLIKE_SCORE_MARGIN
    ):
        return False
    if (
        spike.direction_margin < FULL_SPIKE_MIN_DIRECTION_MARGIN
        and spike.score < FULL_SPIKE_LOW_MARGIN_SCORE_CEILING
    ):
        return False
    return True


def _accept_mini_spike(mini: _GeometryClass, block: _GeometryClass) -> bool:
    if mini.score < MINI_SPIKE_MIN_SCORE:
        return False
    if mini.direction_margin < MINI_SPIKE_MIN_DIRECTION_MARGIN:
        return False
    if (
        block.score > MINI_SPIKE_BLOCKLIKE_SCORE
        and mini.direction_margin < MINI_SPIKE_BLOCKLIKE_DIRECTION_MARGIN
    ):
        return False
    return True


def _accept_block(candidate: _GeometryPatchCandidate) -> bool:
    if candidate.block.score >= BLOCK_MIN_SCORE:
        return True
    return (
        _is_block_aligned(candidate.x, candidate.y)
        and candidate.block.score >= WEAK_BLOCK_ALIGNED_MIN_SCORE
    )


def _is_blocklike_spike_candidate(candidate: _GeometryPatchCandidate) -> bool:
    if not candidate.spike:
        return False
    return (
        _is_block_aligned_to(candidate.x, candidate.y, PREFERRED_BLOCK_ALIGNMENT_STEP)
        and candidate.block.score >= BLOCKLIKE_SPIKE_MIN_BLOCK_SCORE
        and candidate.spike.score <= BLOCKLIKE_SPIKE_MAX_SPIKE_SCORE
        and candidate.patch.border_score >= BLOCKLIKE_SPIKE_MIN_BORDER_SCORE
        and candidate.patch.center_score <= BLOCKLIKE_SPIKE_MAX_CENTER_SCORE
    )


def _outline_block_score(candidate: _GeometryPatchCandidate) -> float | None:
    if candidate.x % OUTLINE_BLOCK_GRID_STEP or candidate.y % OUTLINE_BLOCK_GRID_STEP:
        return None
    if candidate.patch.center_score > OUTLINE_BLOCK_CENTER_MAX:
        return None
    if candidate.patch.border_score < OUTLINE_BLOCK_BORDER_MIN:
        return None
    if candidate.patch.edge_density < OUTLINE_BLOCK_EDGE_MIN:
        return None
    return max(
        0.301,
        candidate.patch.border_score * 0.90 + candidate.patch.edge_density * 0.35,
    )


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


def _recover_block_run_gaps(
    detections: list[Detection],
    image: RGBImage,
    room: Box,
) -> list[Detection]:
    block_detections = [det for det in detections if det.type_id == OBJ_BLOCK]
    block_positions = {(det.x, det.y) for det in block_detections}
    recovered = list(detections)
    for y in range(0, ROOM_HEIGHT - GRID_SIZE + 1, BLOCK_RUN_GAP_STEP):
        for x in range(0, ROOM_WIDTH - GRID_SIZE + 1, BLOCK_RUN_GAP_STEP):
            if (x, y) in block_positions:
                continue
            if any(distance((x, y), (det.x, det.y)) < 28 for det in block_detections):
                continue
            if not _is_block_run_gap(x, y, block_positions):
                continue
            patch = _patch_features(image, room, x, y, GRID_SIZE)
            block = _classify_block(patch)
            if not _accept_block_run_gap_patch(patch, block):
                continue
            recovered.append(
                _geometry_detection(
                    "block",
                    OBJ_BLOCK,
                    x,
                    y,
                    max(BLOCK_RUN_GAP_SCORE, block.score),
                    image,
                    room,
                    GRID_SIZE,
                )
            )
    return recovered


def _accept_block_run_gap_patch(
    patch: _PatchFeatures,
    block: _GeometryClass,
) -> bool:
    if (
        block.score >= BLOCK_RUN_GAP_MIN_BLOCK_SCORE
        and patch.edge_density >= BLOCK_RUN_GAP_MIN_EDGE_DENSITY
    ):
        return True
    return (
        block.score >= BLOCK_RUN_GAP_HOLLOW_MIN_BLOCK_SCORE
        and patch.edge_density >= BLOCK_RUN_GAP_HOLLOW_MIN_EDGE_DENSITY
        and patch.border_score >= BLOCK_RUN_GAP_HOLLOW_MIN_BORDER_SCORE
        and patch.center_score <= BLOCK_RUN_GAP_HOLLOW_MAX_CENTER_SCORE
    )


def _is_block_run_gap(x: int, y: int, block_positions: set[tuple[int, int]]) -> bool:
    return (
        ((x - BLOCK_RUN_GAP_STEP, y) in block_positions)
        and ((x + BLOCK_RUN_GAP_STEP, y) in block_positions)
    ) or (
        ((x, y - BLOCK_RUN_GAP_STEP) in block_positions)
        and ((x, y + BLOCK_RUN_GAP_STEP) in block_positions)
    )


def _normalize_full_spike_detections(detections: list[Detection]) -> list[Detection]:
    normalized: list[Detection] = []
    for detection in detections:
        if detection.type_id not in FULL_SPIKE_TYPES:
            normalized.append(detection)
            continue
        x, y = _normalize_full_spike_origin(detection.type_id, detection.x, detection.y)
        normalized.append(
            Detection(
                detection.kind,
                detection.type_id,
                x,
                y,
                detection.score,
                detection.image_box,
            )
        )
    return normalized


def _normalize_full_spike_origin(type_id: int, x: int, y: int) -> tuple[int, int]:
    if type_id in (OBJ_SPIKE_UP, OBJ_SPIKE_DOWN):
        return round_to_step(x, FULL_SPIKE_AXIS_SNAP_STEP), y
    if type_id in (OBJ_SPIKE_LEFT, OBJ_SPIKE_RIGHT):
        return x, round_to_step(y, FULL_SPIKE_AXIS_SNAP_STEP)
    return x, y


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
        key=_geometry_dedupe_key,
    ):
        if any(_geometry_conflicts(det, existing) for existing in result):
            continue
        result.append(det)
    return sorted(result, key=lambda item: (item.y, item.x, -item.score))


def _geometry_dedupe_key(detection: Detection) -> tuple[bool, int, float]:
    return (
        detection.type_id in MINI_SPIKE_TYPES,
        _block_alignment_rank(detection),
        -detection.score,
    )


def _block_alignment_rank(detection: Detection) -> int:
    if detection.type_id != OBJ_BLOCK:
        return 1
    if _is_block_aligned_to(detection.x, detection.y, PREFERRED_BLOCK_ALIGNMENT_STEP):
        return 0
    if _is_block_aligned(detection.x, detection.y):
        return 1
    return 2


def _is_block_aligned(x: int, y: int) -> bool:
    return _is_block_aligned_to(x, y, BLOCK_ALIGNMENT_STEP)


def _is_block_aligned_to(x: int, y: int, step: int) -> bool:
    return x % step == 0 and y % step == 0


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


def _average_pixel_color(
    image: RGBImage,
    pixels: list[tuple[int, int]],
) -> tuple[float, float, float]:
    total_r = total_g = total_b = 0
    for x, y in pixels:
        r, g, b = image.pixel(x, y)
        total_r += r
        total_g += g
        total_b += b
    count = max(1, len(pixels))
    return total_r / count, total_g / count, total_b / count


def _is_save_yellow(r: int, g: int, b: int) -> bool:
    return r > 170 and g > 130 and b < 90 and r > b * 2


def _is_save_red(r: int, g: int, b: int) -> bool:
    return r > 120 and g < 95 and b < 95 and r > g * 1.5


def _is_tinted_save_yellow(r: int, g: int, b: int) -> bool:
    return r > 95 and g > 145 and 80 < b < 215 and g > r + 25 and g > b + 20


def _is_apple_red(r: int, g: int, b: int) -> bool:
    return r > 150 and g < 95 and b < 95 and r > g * 1.8 and r > b * 1.8


def _is_walljump_green(r: int, g: int, b: int) -> bool:
    return g > 115 and r < 90 and b < 105 and g > r + 55 and g > b + 35


def _is_sparse_walljump_green(r: int, g: int, b: int) -> bool:
    return g > 105 and r < 115 and b < 135 and g > r * 1.35 and g > b * 1.20


def _is_water_blue(r: int, g: int, b: int) -> bool:
    return (
        b > 118
        and g > 92
        and r < 190
        and b > r + 18
        and g > r + 3
        and b <= g + 58
    )


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


def _light_sample_ratio(image: RGBImage, room: Box) -> float:
    light = count = 0
    step = 8
    for y in range(max(0, room.y), min(image.height, room.bottom), step):
        row = image.row(y)
        for x in range(max(0, room.x), min(image.width, room.right), step):
            offset = x * 3
            r = row[offset]
            g = row[offset + 1]
            b = row[offset + 2]
            count += 1
            if r > 145 and g > 145 and b > 145:
                light += 1
    return light / count if count else 0.0


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
