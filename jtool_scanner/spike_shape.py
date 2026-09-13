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
        self.localized_scores: dict[tuple[int, int, int], float] = {}

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
        coverages = self._side_coverages(x, y, direction, scale * .25)
        self.scores[key] = min(coverages)
        self.sides[key] = coverages
        return self.scores[key]

    def localized_score(self, x: int, y: int, direction: int) -> float:
        """Strong edge localization for new objects, not an absence criterion.

        Flat patches can have a near-zero gradient percentile. Gaussian fringe
        gradients then support several origins of the same filled triangle.
        Requiring gradient strength relative to local luminance spread removes
        that fringe without changing the established conservative refit/veto
        scores. A weak/isoluminant patch is not evidence for adding an object.
        """
        if not (0 <= x <= 768 and 0 <= y <= 576):
            return -1.0
        key = x, y, direction
        if key not in self.localized_scores:
            scale, spread = self.patch_stats(x, y)
            self.localized_scores[key] = min(self._side_coverages(
                x, y, direction, max(scale * .25, spread * .15),
            ))
        return self.localized_scores[key]

    def _side_coverages(self, x: int, y: int, direction: int,
                        minimum_strength: float) -> tuple[float, float]:
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
                    if magnitude >= minimum_strength and abs(gx * nx + gy * ny) >= magnitude * 0.95:
                        hits += 1
                        break
            coverages.append(hits / 12)
        return coverages[0], coverages[1]

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


def _block_union_area(x: int, y: int, blocks: list[tuple[int, int]]) -> int:
    """Area inside the candidate box, counting duplicate/overlapping tiles once."""
    area = 0
    for py in range(y, y + 32):
        cursor = x
        for left, right in sorted((max(x, bx), min(x + 32, bx + 32))
                                  for bx, by in blocks if by <= py < by + 32):
            if right > max(cursor, left):
                area += right - max(cursor, left)
            cursor = max(cursor, right)
    return area


def _unsupported_exposed_slopes(
    field: SpikeShapeField, rgb: RGBImage, x: int, y: int, direction: int,
    blocks: list[tuple[int, int]],
) -> bool:
    """Require an absent necessary slope with observable samples across it.

    Terrain hypotheses mask samples, never supply negative image evidence.
    One observed absent slope suffices even if terrain hides the other slope.
    Any positive evidence on either observable part vetoes rejection, including
    a shorter part that cannot itself supply enough negative samples.
    A color-separation guard preserves visible isoluminant objects even when
    the luminance edge field cannot see them.
    """
    scale, spread = field.patch_stats(x, y)
    channels = [[rgb.pixel(px, py)[channel]
                 for py in range(y, y + 32) for px in range(x, x + 32)]
                for channel in range(3)]
    color_spread = max(1.0, sum(_percentile(values, .95) - _percentile(values, .05)
                                for values in channels))
    tip, *ends = VERTICES[direction]
    observed_absent = 0
    for end in ends:
        tx, ty = end[0] - tip[0], end[1] - tip[1]
        length = hypot(tx, ty)
        nx, ny = -ty / length, tx / length
        hits, contrasts, color_contrasts = [], [], []
        for index in range(12):
            t = .15 + .70 * index / 11
            px, py = x + tip[0] + t * tx, y + tip[1] + t * ty
            samples = [(round(px + offset * nx), round(py + offset * ny))
                       for offset in range(-4, 5)]
            if any(not (0 <= sx < 800 and 0 <= sy < 608)
                   or any(bx <= sx < bx + 32 and by <= sy < by + 32 for bx, by in blocks)
                   for sx, sy in samples):
                continue
            supported = False
            for sx, sy in samples[2:7]:
                gx, gy = field.gradient(sx, sy)
                magnitude = hypot(gx, gy)
                if magnitude >= scale * .25 and abs(gx * nx + gy * ny) >= magnitude * .95:
                    supported = True
                    break
            hits.append(supported)
            inside, outside = samples[0], samples[-1]
            contrasts.append(abs(field.pixel(*outside) - field.pixel(*inside)) / spread)
            first, last = rgb.pixel(*inside), rgb.pixel(*outside)
            color_contrasts.append(sum(abs(a - b) for a, b in zip(first, last)) / color_spread)
        if hits and (sum(hits) / len(hits) > .25
                or median(contrasts) >= .15 or median(color_contrasts) >= .15):
            return False
        if len(hits) >= 4:
            observed_absent += 1
    return observed_absent >= 1


def _could_have_strong_slopes(field: SpikeShapeField, x: int, y: int, direction: int) -> bool:
    """Cheap upper bound for score >= .9, avoiding most patch-statistic work.

    A calibrated hit requires magnitude >= .25 because patch scale is at
    least one. Two misses among twelve samples rule out .9 coverage. This
    uses the same sampling/angle conditions as score; it cannot admit a
    rejection that the full nearby-triangle safeguard would have prevented.
    """
    if not (0 <= x <= 768 and 0 <= y <= 576):
        return False
    tip, *ends = VERTICES[direction]
    for end in ends:
        tx, ty = end[0] - tip[0], end[1] - tip[1]
        length = hypot(tx, ty)
        nx, ny = -ty / length, tx / length
        misses = 0
        for index in range(12):
            t = .15 + .70 * index / 11
            px, py = x + tip[0] + t * tx, y + tip[1] + t * ty
            for offset in (-2, -1, 0, 1, 2):
                gx, gy = field.gradient(round(px + offset * nx), round(py + offset * ny))
                magnitude = hypot(gx, gy)
                if magnitude >= .25 and abs(gx * nx + gy * ny) >= magnitude * .95:
                    break
            else:
                misses += 1
                if misses >= 2:
                    return False
    return True


def terrain_exposed_aliases(
    image: RGBImage, room: Box, spikes: list[tuple[int, int, int]],
    blocks: list[tuple[int, int]],
) -> set[tuple[int, int, int]]:
    """Reject partial-terrain aliases only when their exposed slopes are absent.

    Whole-patch scores can be supplied by patterned terrain covering a spike's
    base. Inspect the unmasked source separately, retaining insufficiently
    exposed, strongly edged, color-separated or nearby-triangle cases. This
    complements complete-coverage arbitration; it does not weaken that rule.
    """
    field = None
    rgb = None
    rejected = set()
    for direction, x, y in spikes:
        if direction not in VERTICES or not (0 <= x <= 768 and 0 <= y <= 576):
            continue
        # Include terrain just outside the box: normal samples extend four px.
        nearby = [(bx, by) for bx, by in blocks if abs(bx - x) < 40 and abs(by - y) < 40]
        if not 512 <= _block_union_area(x, y, nearby) < 1024:
            continue
        if field is None:
            field = SpikeShapeField(image, room)
        sides = field.side_scores(x, y, direction)
        if min(sides) >= .5 or max(sides) >= .75 or abs(field.contrast(x, y, direction)) >= .5:
            continue
        if rgb is None:
            crop = image.crop(room)
            normalized = Image.frombytes('RGB', (crop.width, crop.height), crop.data)
            normalized = normalized.resize((800, 608), Image.Resampling.BILINEAR)
            rgb = RGBImage(800, 608, normalized.filter(ImageFilter.GaussianBlur(.7)).tobytes())
        if not _unsupported_exposed_slopes(field, rgb, x, y, direction, nearby):
            continue
        if any(_could_have_strong_slopes(field, x + dx, y + dy, direction)
               and field.score(x + dx, y + dy, direction) >= .9
               and abs(field.contrast(x + dx, y + dy, direction)) >= .5
               for dx in range(-16, 17, 8) for dy in range(-16, 17, 8)):
            continue
        rejected.add((direction, x, y))
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


def corroborated_proposals(
    image: RGBImage, room: Box, spikes: list[tuple[int, int, int]],
) -> list[tuple[int, int, int]]:
    """Recover unoccupied, unambiguous triangles with local source witnesses.

    The coarse edge-mask classifier can miss a real triangle or normalize it
    away before final pruning. This independent directed-slope check uses the
    original source, not that classifier's acceptance threshold. It runs once
    after capture consensus; new proposals never become their own witnesses.
    Sparse, competing, low-contrast and opposite-polarity evidence abstains.
    """
    if len(spikes) < 3:
        return []
    field = SpikeShapeField(image, room)
    seed_signs: dict[tuple[int, int], set[bool]] = {}
    for direction, x, y in spikes:
        if field.score(x, y, direction) >= .9:
            contrast = field.contrast(x, y, direction)
            if abs(contrast) >= .5:
                seed_signs.setdefault((x, y), set()).add(contrast > 0)
    # Duplicates and contradictory hypotheses at one origin are not separate
    # material witnesses. In particular, the last duplicate cannot break a tie.
    seeds = [(x, y, next(iter(signs))) for (x, y), signs in seed_signs.items()
             if len(signs) == 1]
    if len(seeds) < 3:
        return []
    proposals = []
    for y in range(0, 577, 8):
        for x in range(0, 769, 8):
            # Leave crowded/shifted/direction conflicts to reconciliation. This
            # stage adds missing objects, it does not replace existing ones.
            if any(hypot(x - sx, y - sy) < 24 for _, sx, sy in spikes):
                continue
            nearby = []
            for witness in sorted((hypot(x - sx, y - sy), sx, sy, sign)
                                  for sx, sy, sign in seeds
                                  if 40 <= hypot(x - sx, y - sy) <= 192):
                # Nearby shifted hypotheses can describe the same physical
                # triangle even when their exact origin tuples differ.
                if any(hypot(witness[1] - kept[1], witness[2] - kept[2]) < 24
                       for kept in nearby):
                    continue
                nearby.append(witness)
                if len(nearby) == 5:
                    break
            if len(nearby) < 3:
                continue
            for direction in VERTICES:
                # A necessary angular condition saves patch statistics at most
                # grid positions; it never substitutes for the full evidence.
                if not _could_have_strong_slopes(field, x, y, direction):
                    continue
                score = field.localized_score(x, y, direction)
                # New objects require every sample on BOTH slopes. A nearly
                # complete contour can be a displaced, partly occluded sprite;
                # keep that uncertainty rather than materializing a shifted tile.
                if score < 1.0:
                    continue
                contrast = field.contrast(x, y, direction)
                if (abs(contrast) < .5
                        or sum(seed[3] == (contrast > 0) for seed in nearby) / len(nearby) < .8):
                    continue
                runner_up = max(field.localized_score(x + dx, y + dy, other)
                                for dx in (-8, 0, 8) for dy in (-8, 0, 8)
                                for other in VERTICES
                                if (dx, dy, other) != (0, 0, direction))
                # Include the SAME direction at neighboring positions. A long
                # diagonal can support multiple origins without locating a tile.
                if score - runner_up >= .25:
                    proposals.append((direction, x, y))
    return proposals
