"""Intrinsic gravity-arrow evidence in original RGB, independent of palette.

A component needs a complete tapered head, two shoulders and a straight shaft.
Different RGB components are competing evidence, not foreground/background
labels. Unavailable source pixels never establish empty space or a hidden sprite.
"""

from __future__ import annotations

from math import floor, sqrt
from statistics import median

from .constants import OBJ_GRAVITY_DOWN, OBJ_GRAVITY_UP
from .geometry import Box
from .image import RGBImage

ArrowPatch = tuple[int, int, bytes]


def head_share_supported(head_rows: int, total_rows: int) -> bool:
    """Count observed head rows, not the zero-based index of the last row."""
    return 0 < head_rows <= total_rows and .35 <= head_rows / total_rows <= .70


def _components(points: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    unseen = set(points)
    components = []
    while unseen:
        seed = unseen.pop()
        body = {seed}
        pending = [seed]
        while pending:
            x, y = pending.pop()
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if point in unseen:
                    unseen.remove(point)
                    body.add(point)
                    pending.append(point)
        components.append(body)
    return components


def _initial_arrow_proof(coloured, points_down: bool):
    points = {(x, 15 - y if points_down else y) for x, y in coloured}
    if not points or any(not (0 <= x < 16 and 0 <= y < 16) for x, y in points):
        return None
    body = max(_components(points), key=len)
    if len(body) < .8 * len(points):
        return None
    x0, x1 = min(x for x, y in body), max(x for x, y in body)
    y0, y1 = min(y for x, y in body), max(y for x, y in body)
    width, height = x1 - x0 + 1, y1 - y0 + 1
    if width < 8 or height < 11 or abs((x0 + x1) / 2 - 7.5) > 2:
        return None
    rows = []
    for y in range(y0, y1 + 1):
        xs = sorted(x for x, yy in body if yy == y)
        if not xs or xs[-1] - xs[0] + 1 - len(xs) > 1:
            return None
        rows.append((xs[0], xs[-1], len(xs)))
    maximum = max(row[2] for row in rows)
    for k in range(1, height - 4):
        if not head_share_supported(k + 1, height) or rows[k][2] < maximum - 2:
            continue
        stem = rows[k + 1:]
        shaft_width = median(row[2] for row in stem)
        if not 2 <= shaft_width <= 6:
            continue
        if max(row[2] for row in stem) - min(row[2] for row in stem) > 2:
            continue
        if maximum < 1.8 * shaft_width:
            continue
        left, right = median(row[0] for row in stem), median(row[1] for row in stem)
        if left - rows[k][0] < 2 or rows[k][1] - right < 2:
            continue
        if max(abs((row[0] + row[1]) / 2 - (left + right) / 2) for row in rows) > 1.5:
            continue
        if sum(row[2] for row in rows[:2]) / 2 > maximum * .45 + 1:
            continue
        expansion = [abs(row[2] - maximum * (i + .5) / (k + .5)) <= 2
                     for i, row in enumerate(rows[:k + 1])]
        if sum(expansion) < .8 * len(expansion):
            continue
        return dict(head_rows=k + 1, shaft_rows=len(stem), width=width,
                    height=height, shaft_width=shaft_width,
                    connected_share=len(body) / len(points),
                    direction='down' if points_down else 'up',
                    complete_head_shoulders_shaft=True, colour_is_not_world_empty=True)
    return None


def arrow_mask_proof(mask, points_down: bool = False):
    """Reject truncated, blunt, off-centre and non-arrow silhouettes."""
    proof = _initial_arrow_proof(mask, points_down)
    if proof is None:
        return None
    points = {(x, 15 - y if points_down else y) for x, y in mask}
    body = max(_components(points), key=len)
    x0, x1 = min(x for x, y in body), max(x for x, y in body)
    y0, y1 = min(y for x, y in body), max(y for x, y in body)
    if y1 - y0 + 1 < 13 or abs((x0 + x1) / 2 - 7.5) > 1:
        return None
    rows = []
    for y in range(y0, y1 + 1):
        xs = [x for x, yy in body if yy == y]
        rows.append((min(xs), max(xs), len(xs)))
    if rows[0][2] > 3:
        return None
    head = rows[:proof['head_rows']]
    if any(not (-2 <= b[0] - a[0] <= 1 and -1 <= b[1] - a[1] <= 2)
           for a, b in zip(head, head[1:])):
        return None
    stem = rows[proof['head_rows']:]
    center = median((a + b) / 2 for a, b, n in stem)
    if max(abs((a + b) / 2 - center) for a, b, n in head) > 1:
        return None
    return dict(proof, observed_topology_only=True,
                does_not_prove_hidden_sprite_semantics=True)


def patch_arrow_proofs(raw: bytes | None) -> dict[int, dict]:
    """Use local RGB adjacency, not fixed hues, bins or inferred empty colours."""
    if raw is None or len(raw) != 768:
        return {}
    pixels = [tuple(raw[i:i + 3]) for i in range(0, 768, 3)]
    ranges = [max(p[c] for p in pixels) - min(p[c] for p in pixels) for c in range(3)]
    if max(ranges) <= 6:
        return {}
    threshold = max(6, sqrt(sum(value * value for value in ranges)) / 12)
    squared = threshold * threshold
    unseen = set(range(256))
    components = []
    while unseen:
        seed = unseen.pop()
        component, pending = {seed}, [seed]
        while pending:
            i = pending.pop()
            x, y = i % 16, i // 16
            neighbours = (i - 1 if x else -1, i + 1 if x < 15 else -1,
                          i - 16 if y else -1, i + 16 if y < 15 else -1)
            for j in neighbours:
                if j in unseen and sum((a - b) ** 2 for a, b in zip(pixels[i], pixels[j])) <= squared:
                    unseen.remove(j)
                    component.add(j)
                    pending.append(j)
        components.append(component)
    answers = {}
    for component in components:
        if not 30 <= len(component) <= 170:
            continue
        mask = frozenset((i % 16, i // 16) for i in component)
        for down in (False, True):
            proof = arrow_mask_proof(mask, down)
            if proof is not None:
                answers[OBJ_GRAVITY_DOWN if down else OBJ_GRAVITY_UP] = dict(
                    proof, source_graph_threshold=threshold, source_rgb_graph=True)
    # Conflicting source interpretations are not two independently proved objects.
    return answers if len(answers) <= 1 else {}


def source_query_axes(image: RGBImage, physical: Box, extent: Box,
                      x: int, y: int, native_size: tuple[int, int],
                      native_offset: tuple[int, int]):
    """Require the whole footprint and sixteen distinct real samples per axis."""
    width, height = native_size
    xx, yy = x - native_offset[0], y - native_offset[1]
    if min(width, height, physical.width, physical.height, extent.width, extent.height) <= 0:
        return None
    if xx < 0 or yy < 0 or xx + 32 > width or yy + 32 > height:
        return None
    if (physical.x < 0 or physical.y < 0 or physical.right > image.width
            or physical.bottom > image.height):
        return None
    x0, x1 = extent.x + xx * extent.width / width, extent.x + (xx + 32) * extent.width / width
    y0, y1 = extent.y + yy * extent.height / height, extent.y + (yy + 32) * extent.height / height
    if x0 < physical.x or x1 > physical.right or y0 < physical.y or y1 > physical.bottom:
        return None
    xs = tuple(floor(extent.x + (xx + (i + .5) * 2) * extent.width / width) for i in range(16))
    ys = tuple(floor(extent.y + (yy + (i + .5) * 2) * extent.height / height) for i in range(16))
    if len(set(xs)) < 16 or len(set(ys)) < 16:
        return None
    if (min(xs) < physical.x or min(ys) < physical.y
            or max(xs) >= physical.right or max(ys) >= physical.bottom):
        return None
    return xs, ys


def original_rgb_patch(image: RGBImage, room: Box, x: int, y: int, *,
                       native_size=(800, 608), native_offset=(0, 0),
                       world_extent: Box | None = None) -> bytes | None:
    extent = room if world_extent is None else world_extent
    axes = source_query_axes(image, room, extent, x, y, native_size, native_offset)
    if axes is None:
        return None
    xs, ys = axes
    return bytes(value for py in ys for px in xs for value in image.pixel(px, py))
