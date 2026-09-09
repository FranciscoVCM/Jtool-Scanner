"""Directed triangle evidence with scan-local calibration and caches.

No fixed foreground color or global bright/dark assumption is used. Nearby
well-supported spikes corroborate local contrast polarity; uncertain geometry
and competing position peaks are left unchanged.
"""

from math import hypot
from statistics import median

from PIL import Image, ImageFilter

from .geometry import Box
from .image import RGBImage


VERTICES = {
    3: ((16, 0), (0, 32), (32, 32)),
    4: ((32, 16), (0, 0), (0, 32)),
    5: ((0, 16), (32, 0), (32, 32)),
    6: ((16, 32), (0, 0), (32, 0)),
}


def _percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


class SpikeShapeField:
    def __init__(self, image: RGBImage, room: Box):
        crop = image.crop(room)
        gray = Image.frombytes("RGB", (crop.width, crop.height), crop.data)
        gray = gray.convert("L").resize((800, 608), Image.Resampling.BILINEAR)
        self.pixels = gray.filter(ImageFilter.GaussianBlur(0.7)).tobytes()
        self.stats: dict[tuple[int, int], tuple[float, float]] = {}
        self.scores: dict[tuple[int, int, int], float] = {}
        self.sides: dict[tuple[int, int, int], tuple[float, float]] = {}
        self.contrasts: dict[tuple[int, int, int], float] = {}

    def pixel(self, x: int, y: int) -> int:
        return self.pixels[min(607, max(0, y)) * 800 + min(799, max(0, x))]

    def gradient(self, x: int, y: int) -> tuple[float, float]:
        gx = (self.pixel(x + 1, y) - self.pixel(x - 1, y)) / (1 if x in (0, 799) else 2)
        gy = (self.pixel(x, y + 1) - self.pixel(x, y - 1)) / (1 if y in (0, 607) else 2)
        return gx, gy

    def patch_stats(self, x: int, y: int) -> tuple[float, float]:
        key = x, y
        if key not in self.stats:
            values = [self.pixel(px, py) for py in range(y, y + 32) for px in range(x, x + 32)]
            magnitudes = [hypot(*self.gradient(px, py)) for py in range(y, y + 32) for px in range(x, x + 32)]
            self.stats[key] = (
                max(1.0, _percentile(magnitudes, 0.90)),
                max(1.0, _percentile(values, 0.95) - _percentile(values, 0.05)),
            )
        return self.stats[key]

    def score(self, x: int, y: int, direction: int) -> float:
        if not (0 <= x <= 768 and 0 <= y <= 576):
            return -1.0
        key = x, y, direction
        if key in self.scores:
            return self.scores[key]
        scale, _ = self.patch_stats(x, y)
        tip, *ends = VERTICES[direction]
        coverages = []
        for end in ends:
            tx, ty = end[0] - tip[0], end[1] - tip[1]
            length = hypot(tx, ty)
            nx, ny = -ty / length, tx / length
            hits = 0
            for index in range(12):
                t = 0.15 + 0.70 * index / 11
                px, py = x + tip[0] + t * tx, y + tip[1] + t * ty
                for offset in (-2, -1, 0, 1, 2):
                    gx, gy = self.gradient(round(px + offset * nx), round(py + offset * ny))
                    magnitude = hypot(gx, gy)
                    if magnitude >= scale * 0.25 and abs(gx * nx + gy * ny) >= magnitude * 0.95:
                        hits += 1
                        break
            coverages.append(hits / 12)
        self.scores[key] = min(coverages)
        self.sides[key] = tuple(coverages)
        return self.scores[key]

    def side_scores(self, x: int, y: int, direction: int) -> tuple[float, float]:
        self.score(x, y, direction)
        return self.sides.get((x, y, direction), (-1.0, -1.0))

    def contrast(self, x: int, y: int, direction: int) -> float:
        key = x, y, direction
        if key in self.contrasts:
            return self.contrasts[key]
        tip, *ends = VERTICES[direction]
        cx = sum(p[0] for p in VERTICES[direction]) / 3
        cy = sum(p[1] for p in VERTICES[direction]) / 3
        values = []
        for end in ends:
            tx, ty = end[0] - tip[0], end[1] - tip[1]
            nx, ny = -ty, tx
            if nx * (cx - (tip[0] + end[0]) / 2) + ny * (cy - (tip[1] + end[1]) / 2) > 0:
                nx, ny = -nx, -ny
            length = hypot(nx, ny)
            nx, ny = nx / length, ny / length
            for index in range(10):
                t = 0.2 + 0.6 * index / 9
                px, py = x + tip[0] + t * tx, y + tip[1] + t * ty
                values.append(self.pixel(round(px + 4 * nx), round(py + 4 * ny)) - self.pixel(round(px - 4 * nx), round(py - 4 * ny)))
        self.contrasts[key] = median(values) / self.patch_stats(x, y)[1]
        return self.contrasts[key]

    def alternatives(self, x: int, y: int, direction: int, radius: int):
        return sorted(
            (self.score(x + dx, y + dy, other), x + dx, y + dy, other)
            for dx in range(-radius, radius + 1, 8)
            for dy in range(-radius, radius + 1, 8)
            for other in VERTICES if other != direction
        )[::-1]


def terrain_covered_aliases(image: RGBImage, room: Box,
                            spikes: list[tuple[int, int, int]],
                            blocks: list[tuple[int, int]]) -> set[tuple[int, int, int]]:
    """Reject unsupported triangle hypotheses inside a union of full blocks.

    Partial coverage, strong individual slopes and nearby supported triangles
    are deliberately preserved. Block detections alone cannot reject a spike.
    Coordinates and image evidence are scan-local; no reference truth is used.
    """
    field = None
    rejected = set()
    for direction, x, y in spikes:
        if not (0 <= x <= 768 and 0 <= y <= 576):
            continue
        nearby = [(bx, by) for bx, by in blocks if abs(bx-x) < 32 and abs(by-y) < 32]
        if not nearby:
            continue
        covered = True
        for py in range(y, y+32):
            cursor = x
            for left, right in sorted((max(x,bx), min(x+32,bx+32))
                                      for bx,by in nearby if by <= py < by+32):
                if left > cursor:
                    break
                cursor = max(cursor, right)
            if cursor < x+32:
                covered = False
                break
        if not covered:
            continue
        if field is None:
            field = SpikeShapeField(image, room)
        sides = field.side_scores(x, y, direction)
        if min(sides) >= .5 or max(sides) >= .75 or abs(field.contrast(x,y,direction)) >= .5:
            continue
        if any(field.score(x+dx,y+dy,direction) >= .9
               and abs(field.contrast(x+dx,y+dy,direction)) >= .5
               for dx in range(-16,17,8) for dy in range(-16,17,8)):
            continue
        rejected.add((direction,x,y))
    return rejected


def corroborated_refits(image: RGBImage, room: Box, spikes: list[tuple[int, int, int]]) -> dict[tuple[int, int, int], tuple[int, int, int]]:
    """Map (type,x,y) to a corroborated replacement; never force an answer."""
    if len(spikes) < 3:
        return {}
    field = SpikeShapeField(image, room)
    # Multiple hypotheses at one origin are not independent witnesses.
    seed_positions: dict[tuple[int, int], bool | None] = {}
    for direction, x, y in spikes:
        if field.score(x, y, direction) >= 0.9 and abs(field.contrast(x, y, direction)) >= 0.5:
            sign = field.contrast(x, y, direction) > 0
            key = x, y
            if key in seed_positions and seed_positions[key] != sign:
                seed_positions[key] = None
            else:
                seed_positions[key] = sign
    seeds = [(x, y, sign) for (x, y), sign in seed_positions.items() if sign is not None]
    if len(seeds) < 3:
        return {}
    replacements = {}
    for direction, x, y in spikes:
        if not 0 <= field.score(x, y, direction) < 0.25:
            continue
        candidates = field.alternatives(x, y, direction, 8)
        best = candidates[0]
        if best[0] < 0.9 or best[0] - candidates[1][0] < 0.25:
            continue
        _, nx, ny, other = best
        contrast = field.contrast(nx, ny, other)
        if abs(contrast) < 0.5:
            continue
        nearby = sorted((hypot(nx - sx, ny - sy), sx, sy, sign) for sx, sy, sign in seeds if 40 <= hypot(nx - sx, ny - sy) <= 192)[:5]
        if len(nearby) < 3 or sum(seed[3] == (contrast > 0) for seed in nearby) / len(nearby) < 0.8:
            continue
        wider = field.alternatives(x, y, direction, 16)
        if wider[0] != best or best[0] - wider[1][0] < 0.25:
            continue
        replacements[direction, x, y] = other, nx, ny
    return replacements
