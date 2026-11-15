"""Original-frame evidence for late cloud markers and fully explained solids."""

from collections import Counter
from dataclasses import replace
from functools import lru_cache
from math import ceil, floor
from pathlib import Path

from .constants import OBJ_BLOCK, OBJ_WARP, ROOM_HEIGHT, ROOM_WIDTH
from .geometry import Box


@lru_cache(maxsize=1)
def _atlas_extreme_roles():
    from PIL import Image

    path = Path(__file__).with_name("assets") / "jtool-pat-default" / "warp.png"
    with Image.open(path, formats=["PNG"]) as source:
        art = source.convert("RGBA")
    if art.size != (32, 32):
        return ()
    by_shade = {}
    for y in range(1, 31):
        for x in range(1, 31):
            p = art.getpixel((x, y))
            if p[3] == 255 and p[0] == p[1] == p[2] and all(
                art.getpixel((x + dx, y + dy)) == p for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ):
                by_shade.setdefault(p[0], []).append((x, y))
    if len(by_shade) != 4 or min(map(len, by_shade.values())) < 8:
        return ()
    return tuple(tuple(by_shade[k]) for k in (min(by_shade), max(by_shade)))


def _luma(rgb):
    return sum(rgb) / 3


def _quantile(values, fifth):
    return sorted(values)[len(values) * fifth // 5]


def _rgb_distance(a, b):
    return max(abs(u - v) for u, v in zip(a, b))


def _inside(inner, outer):
    return inner.area > 0 and outer.contains(inner.x, inner.y) and outer.contains(inner.right - 1, inner.bottom - 1)


def _native_square(x, y):
    return 0 <= x <= ROOM_WIDTH - 32 and 0 <= y <= ROOM_HEIGHT - 32


def _points(box):
    return ((x, y) for y in range(box.y, box.bottom) for x in range(box.x, box.right))


def _overlap(a, b):
    return max(a.x, b.x) < min(a.right, b.right) and max(a.y, b.y) < min(a.bottom, b.bottom)


def proves_separated_cloud(image, room, core_box, core_pixels, x, y, *, bright_pixel):
    """A darker rim separates the observed bright core from independent backdrop.

    Called only after legacy cloud morphology, at its own component pose.
    A rejected proof is not permission to relax the ordinary detector.
    """
    if not _native_square(x, y) or not _inside(room, Box(0, 0, image.width, image.height)):
        return False
    masks = _atlas_extreme_roles()
    if not masks:
        return False
    sx, sy = room.width / ROOM_WIDTH, room.height / ROOM_HEIGHT
    roles = []
    for mask in masks:
        taps = {(int(room.x + (x + u + .5) * sx), int(room.y + (y + v + .5) * sy)) for u, v in mask}
        if len(taps) != len(mask) or any(not room.contains(*p) for p in taps) or (roles and roles[0] & taps):
            return False
        roles.append(taps)
    inside = set(core_pixels)
    exterior = set()
    for axis, sign in ((0, -1), (0, 1), (1, -1), (1, 1)):
        start, end = (core_box.y, core_box.bottom - 1) if axis == 0 else (core_box.x, core_box.right - 1)
        rays = [round(start + (end - start) * (.25 + i * .10)) for i in range(6)]
        if len(set(rays)) != 6:
            return False
        count = 0
        reach = round(8 * (sx if axis == 0 else sy))
        for ray in rays:
            cross = [p[axis] for p in inside if p[1 - axis] == ray]
            if not cross:
                continue
            edge = (min if sign < 0 else max)(cross)
            pos = [(edge + sign * i, ray) if axis == 0 else (ray, edge + sign * i) for i in range(reach + 1)]
            if any(not room.contains(*p) for p in pos):
                return False
            colors = [image.pixel(*p) for p in pos]
            luminance = [_luma(c) for c in colors]
            for i in range(3, reach):
                far = pos[i:i + 2]
                a, b = colors[i:i + 2]
                if (any(p in inside or p in roles[0] or p in roles[1] for p in far)
                        or not (bright_pixel(*a) and bright_pixel(*b)) or _rgb_distance(a, b) > 8):
                    continue
                high = min(luminance[0], luminance[i], luminance[i + 1])
                if any(high - max(luminance[j:j + 2]) >= 28 for j in range(1, i - 1)):
                    exterior.update(far)
                    count += 1
                    break
        if count < 3:
            return False
    if len(exterior) < 16:
        return False
    outer = [_luma(image.pixel(*p)) for p in exterior]
    dark, bright = ([_luma(image.pixel(*p)) for p in role] for role in roles)
    low, high = _quantile(outer, 1), _quantile(outer, 4)
    return low - _quantile(dark, 4) >= 28 and _quantile(bright, 1) - high >= 10 and high - low <= 12


def _connected_from(points, seed):
    todo, known = [seed], {seed}
    while todo:
        x, y = todo.pop()
        for j in (-1, 0, 1):
            for i in (-1, 0, 1):
                p = x + i, y + j
                if p in points and p not in known:
                    known.add(p)
                    todo.append(p)
    return known


def _weak_strip(values, ink, backdrop, area, minimum):
    for width, height, transpose in ((area.width, area.height, False), (area.height, area.width, True)):
        for row in range(height):
            run, previous = 0, None
            for col in range(width):
                p = (area.x + row, area.y + col) if transpose else (area.x + col, area.y + row)
                rgb = values[p]
                if p in ink or _rgb_distance(rgb, backdrop) < 2:
                    run, previous = 0, None
                else:
                    run = run + 1 if previous is not None and _rgb_distance(rgb, previous) <= 1 else 1
                    previous = rgb
                    if run >= minimum:
                        return True
    return False


def _proves_false_solid(image, room, block, marker, bright_pixel):
    """Preserve mixed footprints and any unaccounted-for source structure."""
    if not (_native_square(block.x, block.y) and _native_square(marker.x, marker.y)
            and _inside(room, Box(0, 0, image.width, image.height))):
        return False
    sx, sy = room.width / ROOM_WIDTH, room.height / ROOM_HEIGHT
    body, core = block.image_box, marker.image_box
    expected = Box(round(room.x + block.x * sx), round(room.y + block.y * sy),
                   max(1, round(32 * sx)), max(1, round(32 * sy)))
    if body != expected or not _overlap(body, core):
        return False
    qx, qy = round(5 * sx), round(5 * sy)
    left, top = min(body.x, core.x - qx) - 1, min(body.y, core.y - qy)
    right, bottom = max(body.right, core.right + qx) + 1, max(body.bottom, core.bottom + qy)
    area = Box(left, top, right - left, bottom - top)
    span = max(2, round(2 * sx))
    witnesses = (Box(left - span, top, span, area.height), Box(right, top, span, area.height))
    if not all(_inside(b, room) for b in (area, *witnesses)):
        return False
    counts = [Counter(image.pixel(*p) for p in _points(b)) for b in witnesses]
    leading = [count.most_common(1)[0] for count in counts]
    backdrop = leading[0][0]
    if leading[1][0] != backdrop or any(n < .80 * b.area for (_, n), b in zip(leading, witnesses)):
        return False
    tolerance = max(2, max(_rgb_distance(c, backdrop) for count in counts for c in count))
    if tolerance > 6:
        return False
    values = {p: image.pixel(*p) for p in _points(area)}
    ink = {p for p, rgb in values.items() if _rgb_distance(rgb, backdrop) > tolerance}
    bright = {p for p in _points(core) if p in ink and bright_pixel(*values[p])}
    if not any(body.contains(*p) for p in bright) or _connected_from(ink, min(bright)) != ink:
        return False
    ox, oy = floor(room.x + marker.x * sx), floor(room.y + marker.y * sy)
    owner = Box(ox, oy, ceil(room.x + (marker.x + 32) * sx) - ox,
                ceil(room.y + (marker.y + 32) * sy) - oy)
    moat = Box(area.x + 1, area.y + 1, area.width - 2, area.height - 2)
    if any(not owner.contains(*p) or not moat.contains(*p) for p in ink):
        return False
    if _weak_strip(values, ink, backdrop, body, max(6, ceil(6 * min(sx, sy)))):
        return False
    run = 0
    for y in range(body.y, body.bottom):
        run = run + 1 if all((x, y) not in ink for x in range(body.x, body.right)) else 0
        if run >= ceil(16 * sy):
            return True
    return False


def apply_late_clouds(result, image, candidates, *, bright_pixel, warnings):
    """Consume verified original-source proposals after geometry has settled."""
    if not result.source_geometry or result.source_grid != (25, 19) or not candidates:
        return result
    markers = [d for d in result.detections if d.type_id == OBJ_WARP]
    added = []
    for d in candidates:
        if d.type_id != OBJ_WARP or any(
            _overlap(d.image_box, old.image_box) or (d.x - old.x) ** 2 + (d.y - old.y) ** 2 < 20**2
            for old in (*markers, *added)
        ):
            continue
        added.append(d)
    if not added:
        return result
    room = result.room_box
    kept = [d for d in result.detections if d.type_id != OBJ_BLOCK or not any(
        _overlap(d.image_box, m.image_box) and _proves_false_solid(image, room, d, m, bright_pixel)
        for m in added
    )]
    detections = sorted([*kept, *added], key=lambda d: (d.type_id, d.y, d.x))
    return replace(result, detections=detections, structural_warnings=warnings(detections))
