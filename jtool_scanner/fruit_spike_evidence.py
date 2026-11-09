"""Account for original-pixel edges borrowed from a detected fruit body.

This is a negative proof for the legacy off-grid support route, not a
classifier for apples or spikes. Call only on an original, unresampled frame.
"""

from dataclasses import dataclass
from math import floor, hypot, sqrt

from .geometry import Box
from .image import RGBImage
from .spike_shape import VERTICES


Point = tuple[int, int]
FruitBody = tuple[Box, set[Point]]
_SIDE_OFFSETS = (-1.5, -.75, 0., .75, 1.5)
_EDGE_THRESHOLD = 34
_NEIGHBORS = tuple(
    (16 * (i // 16) + min(i % 16 + 1, 15), 16 * min(i // 16 + 1, 15) + i % 16)
    for i in range(256)
)


@dataclass(frozen=True)
class FruitSupportBudget:
    warm_votes: int
    combined_votes: int
    remaining_score: float
    held_side_sites: tuple[int, int]

    def withholds(self, admission_floor: float) -> bool:
        return self.remaining_score < admission_floor and max(self.held_side_sites) <= 3


def _physical_taps(image: RGBImage, room: Box, x: int, y: int) -> tuple[Point, ...] | None:
    if not (0 <= x <= 768 and 0 <= y <= 576):
        return None
    if not (0 <= room.x < room.right <= image.width and 0 <= room.y < room.bottom <= image.height):
        return None
    sx, sy = room.width / 800, room.height / 608
    left, top = room.x + x * sx, room.y + y * sy
    taps = tuple((floor(left + (u + .5) * (32 * sx) / 16),
                  floor(top + (v + .5) * (32 * sy) / 16))
                 for v in range(16) for u in range(16))
    independent = tuple((floor(room.x + (x + (u + .5) * 2) * room.width / 800),
                         floor(room.y + (y + (v + .5) * 2) * room.height / 608))
                        for v in range(16) for u in range(16))
    if taps != independent or len(set(taps)) != 256 or any(not room.contains(*p) for p in taps):
        return None
    return taps


def _gradient(image: RGBImage, room: Box, x: int, y: int):
    points = ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
    if any(not room.contains(*p) for p in points):
        return None
    left, right, top, bottom = (image.pixel(*p) for p in points)
    return points, tuple(v - u for u, v in zip(left, right)), tuple(v - u for u, v in zip(top, bottom))


def _dot(a, b):
    return sum(u * v for u, v in zip(a, b))


def _magnitude(vector):
    return sqrt(_dot(vector, vector))


def _segment_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _incompatible(image, room, a, b, sides, ink):
    length = int(hypot(a[0] - b[0], a[1] - b[1]))
    if not length:
        return False
    centers = dict.fromkeys((round(a[0] + i * (b[0] - a[0]) / length),
                             round(a[1] + i * (b[1] - a[1]) / length)) for i in range(length + 1))
    opposed = 0
    for p in centers:
        source = _gradient(image, room, *p)
        if source is None:
            continue
        points, gx, gy = source
        if any(q in ink for q in (*points, p)):
            continue
        total = _dot(gx, gx) + _dot(gy, gy)
        if total < 12 ** 2:
            continue
        shares = [sum((nx * u + ny * v) ** 2 for u, v in zip(gx, gy)) / total
                  for first, last, nx, ny in sides if _segment_distance(p, first, last) <= 4.0]
        if shares:
            aligned = max(shares)
            if aligned >= .70:
                return False
            opposed += aligned <= .42
    return opposed >= 2


def _held_sides(image, room, x, y, type_id, ink):
    sx, sy = room.width / 800, room.height / 608
    vertices = [(room.x + (x + u * 32 / 32) * sx, room.y + (y + v * 32 / 32) * sy)
                for u, v in VERTICES[type_id]]
    cx, cy = (sum(p[k] for p in vertices) / 3 for k in range(2))
    tip, *ends = vertices
    held_sides = []
    for end in ends:
        dx, dy = end[0] - tip[0], end[1] - tip[1]
        length = hypot(dx, dy)
        nx, ny = -dy / length, dx / length
        if nx * (cx - tip[0]) + ny * (cy - tip[1]) < 0:
            nx, ny = -nx, -ny
        phases = []
        for offset in _SIDE_OFFSETS:
            samples = []
            for i in range(16):
                u = .18 + .64 * i / 15
                site = (floor(tip[0] + u * dx + offset * nx), floor(tip[1] + u * dy + offset * ny))
                source = _gradient(image, room, *site)
                if source is None:
                    return None  # unavailable side evidence cannot justify a veto
                points, h, v = source
                normal = tuple(nx * a + ny * b for a, b in zip(h, v))
                tangent = tuple(-ny * a + nx * b for a, b in zip(h, v))
                n, t = _magnitude(normal), _magnitude(tangent)
                valid = n >= 8 and n >= 2 * t and not any(p in ink for p in (*points, site))
                samples.append((site, normal, n, valid))
            phases.append(samples)
        held = []
        for fit in (0, 1):
            trial = []
            for offset, samples in zip(_SIDE_OFFSETS, phases):
                training = [(normal, n) for _, normal, n, valid in samples[fit::2] if valid]
                total = tuple(sum(normal[k] / n for normal, n in training) for k in range(3))
                length = _magnitude(total)
                unit = tuple(z / length for z in total) if length > 1e-9 else (0, 0, 0)
                coherence = sum(_dot(normal, unit) >= .85 * n for normal, n in training)
                trial.append((coherence, -abs(offset), unit, samples))
            _, _, unit, samples = max(trial, key=lambda row: row[:2])
            held.append(len({site for site, normal, n, valid in samples[1-fit::2]
                             if valid and _dot(normal, unit) >= .85 * n}))
        held_sides.append(min(held))
    return tuple(held_sides)


def original_fruit_support_budget(
    image: RGBImage, room: Box, x: int, y: int, type_id: int, ink: set[Point],
    *, outline: tuple[int, ...], edge_mask: tuple[bool, ...],
) -> FruitSupportBudget | None:
    """Withdraw proved fruit contributions while retaining unknown edge credit."""
    taps = _physical_taps(image, room, x, y)
    if taps is None or not ink or not outline or len(edge_mask) != len(taps):
        return None
    gray = [(30 * r + 59 * g + 11 * b) // 100 for r, g, b in (image.pixel(*p) for p in taps)]
    strengths = [tuple(abs(gray[i] - gray[j]) for j in pair) for i, pair in enumerate(_NEIGHBORS)]
    totals = tuple(sum(pair) for pair in strengths)
    if tuple(value >= _EDGE_THRESHOLD for value in totals) != edge_mask:
        return None
    dry = [tuple(s if taps[i] not in ink and taps[j] not in ink else 0 for j, s in zip(pair, strengths[i]))
           for i, pair in enumerate(_NEIGHBORS)]
    residual = [sum(pair) for pair in dry]
    hits = [i for i in outline if edge_mask[i]]
    warm_votes = sum(residual[i] < _EDGE_THRESHOLD for i in hits)
    if warm_votes < 6:
        return None
    vertices = [(room.x + (x + u) * room.width / 800, room.y + (y + v) * room.height / 608)
                for u, v in VERTICES[type_id]]
    sides = []
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = hypot(dx, dy)
        sides.append((a, b, -dy / length, dx / length))
    remaining_hits = 0
    for i in hits:
        if residual[i] < _EDGE_THRESHOLD:
            continue
        other = sum(s for j, s in zip(_NEIGHBORS[i], dry[i])
                    if s and _incompatible(image, room, taps[i], taps[j], sides, ink))
        remaining_hits += residual[i] - other >= _EDGE_THRESHOLD
    density = max(sum(s >= _EDGE_THRESHOLD for s in residual) / 256, min(.30, sum(residual) / (256 * 260)))
    upper = remaining_hits / len(outline) * .78 + .38 * density
    held = _held_sides(image, room, x, y, type_id, ink)
    if held is None:
        return None
    return FruitSupportBudget(warm_votes, len(hits) - remaining_hits, upper, held)
