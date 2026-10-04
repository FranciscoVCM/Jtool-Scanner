"""Source-calibrated miniature search and independent larger-size ownership.

Original source-qualified hypotheses calibrate an 8px native lattice; new
objects never become witnesses. Equal-material joined bases need all four
independently visible external slopes. Inner artwork remains ambiguous when
the source supports a containing full-size outline or matching original full.
No room identity, reference geometry, fixed palette or learned answer enters
these scan-local observations.
"""

from math import hypot, sqrt
from statistics import median

from .spike_shape import VERTICES, _percentile
from .spike_source_ownership import triangle_contains, source_size_owns
from .spike_source_stroke import templates


def native_source_seeds(field, witnesses):
    """Necessary slope bound only; never guess a phase without a witness."""
    phases = sorted({(x % 8, y % 8) for x, y, _ in witnesses})
    return {(x, y) for px, py in phases
            for y in range(py if py >= 4 else py + 8, 589, 8)
            for x in range(px if px >= 4 else px + 8, 781, 8)
            if any(field.could_have_strong_slopes(x, y, d) for d in VERTICES)}


def _base(field, x, y, direction):
    _, first, second = field.vertices[direction]
    tx, ty = second[0] - first[0], second[1] - first[1]
    length = hypot(tx, ty)
    nx, ny = -ty / length, tx / length
    scale, spread = field.patch_stats(x, y)
    minimum = max(scale * .25, spread * .15)
    hits = run = longest = 0
    for i in range(12):
        q = .3 + .4 * i / 11
        px, py = x + first[0] + q * tx, y + first[1] + q * ty
        found = False
        for offset in (-2, -1, 0, 1, 2):
            gx, gy = field.gradient(round(px + offset * nx), round(py + offset * ny))
            magnitude = hypot(gx, gy)
            if magnitude >= minimum and abs(gx * nx + gy * ny) >= magnitude * .95:
                found = True
                break
        hits += found
        run = run + 1 if found else 0
        longest = max(longest, run)
    return hits / 12, longest / 12


def _distance(px, py, vertices):
    if triangle_contains(vertices, ((px, py),)):
        return 0.0
    answer = float('inf')
    for (ax, ay), (bx, by) in zip(vertices, vertices[1:] + vertices[:1]):
        tx, ty = bx - ax, by - ay
        q = max(0., min(1., ((px - ax) * tx + (py - ay) * ty) / (tx * tx + ty * ty)))
        answer = min(answer, hypot(px - (ax + q * tx), py - (ay + q * ty)))
    return answer


def _independent_leading_ink(field, x, y, direction, child, sign):
    """Only larger leading samples outside the child's entire 4px band."""
    positions = tuple(.05 + .2 * i / 11 for i in range(12))
    compiled = templates(field, direction, positions)
    tip, *ends = field.vertices[direction]
    origin = y * 800 + x
    for end, side in zip(ends, compiled):
        tx, ty = end[0] - tip[0], end[1] - tip[1]
        count = hits = 0
        for q, (pixels, _, _, _) in zip(positions, side):
            px, py = x + tip[0] + q * tx, y + tip[1] + q * ty
            if _distance(px, py, child) <= 4.:
                continue
            count += 1
            values = [sum(field.pixels[origin + j] * w for j, w in entries)
                      for entries in pixels]
            cutoff = max(4., (max(values) - min(values)) * .15)
            dark = min(values[0], values[-1]) - min(values[2:7])
            light = max(values[2:7]) - max(values[0], values[-1])
            ink_sign = 1 if dark >= cutoff else -1 if light >= cutoff else 0
            hits += ink_sign == sign
        if count < 6 or hits < count - 1:
            return False
    return True


def _glyph(rgb, x, y, direction, margin):
    """Centered joint-RGB source appearance; not a stored sprite template."""
    pixels = []
    vertices = VERTICES[direction]
    for j in range(8):
        for i in range(8):
            u, v = 32 * (i + .5) / 8, 32 * (j + .5) / 8
            signs = []
            for (ax, ay), (bx, by) in zip(vertices, vertices[1:] + vertices[:1]):
                cross = (bx - ax) * (v - ay) - (by - ay) * (u - ax)
                signs.append(cross)
                if margin and abs(cross) / hypot(bx - ax, by - ay) < margin:
                    break
            else:
                if not min(signs) < 0 < max(signs):
                    pixels.append(rgb.pixel(round(x + u), round(y + v)))
    means = [sum(p[c] for p in pixels) / len(pixels) for c in range(3)]
    values = [p[c] - means[c] for p in pixels for c in range(3)]
    energy = sqrt(sum(v * v for v in values))
    return tuple(v / energy for v in values) if energy else (0.,) * len(values)


def _strict_rgb_slopes(rgb, key):
    """Candidate-local RGB strength and direction; no diagnostic-only work."""
    direction, x, y = key
    tip, *ends = VERTICES[direction]
    coverages = []
    for end in ends:
        tx, ty = end[0] - tip[0], end[1] - tip[1]
        length = hypot(tx, ty)
        nx, ny = -ty / length, tx / length
        profiles, magnitudes = [], []
        for i in range(12):
            q = .15 + .70 * i / 11
            px, py = x + tip[0] + q * tx, y + tip[1] + q * ty
            points = [(round(px + j * nx), round(py + j * ny)) for j in range(-4, 5)]
            values = [rgb.pixel(*p) for p in points]
            gradients = []
            for p in points[2:7]:
                gx, gy = rgb.gradient(*p)
                magnitude = sqrt(sum(a * a + b * b for a, b in zip(gx, gy)))
                normal = sqrt(sum((a * nx + b * ny) ** 2 for a, b in zip(gx, gy)))
                gradients.append((magnitude, normal))
                magnitudes.append(magnitude)
            spread = max(sqrt(sum((a - b) ** 2 for a, b in zip(v, w)))
                         for v in values for w in values)
            profiles.append((spread, gradients))
        scale = max(1., _percentile(magnitudes, .90))
        spread = median(p[0] for p in profiles)
        cutoff = max(scale * .25, spread * .15)
        hits = sum(any(m >= cutoff and spread >= 12 and n >= m * .95 for m, n in gs)
                   for _, gs in profiles)
        coverages.append(hits / 12)
    return min(coverages)


class LargerSourceOwner:
    """Abstain only on newly proposed minis; never delete an existing object."""
    def __init__(self, spikes, field, stroke, color, ownership):
        self.spikes, self.field, self.stroke = spikes, field, stroke
        self.color, self.ownership = color, ownership
        self.anchors = None
        self.signatures, self.rgb_scores, self.results = {}, {}, {}

    def original_anchors(self):
        if self.anchors is None:
            anchors = []
            field = self.field(32)
            for x, y in sorted({(x, y) for t, x, y in self.spikes if 3 <= t <= 6}):
                if not (4 <= x <= 764 and 4 <= y <= 572):
                    continue
                scores = sorted((field.localized_score(x, y, d), d) for d in VERTICES)
                best, direction = scores[-1]
                if (best >= 11 / 12 and best - scores[-2][0] >= .25
                        and field.patch_stats(x, y)[1] >= 12
                        and min(_base(field, x, y, direction)) >= .5):
                    anchors.append((direction, x, y))
            self.anchors = anchors
        return self.anchors

    def glyph(self, key, margin):
        cache_key = key, margin
        if cache_key not in self.signatures:
            self.signatures[cache_key] = _glyph(self.color(), key[1], key[2], key[0], margin)
        return self.signatures[cache_key]

    def owns(self, mini):
        if mini in self.results:
            return self.results[mini]
        t, mx, my = mini
        direction = t - 4
        child = tuple((mx + vx / 2, my + vy / 2) for vx, vy in VERTICES[direction])
        # A snapped ORIGINAL full hypothesis locates a source frame, not its
        # filtered pixel-center phase. Check its bounded pixel neighborhood
        # with the SAME strict pure slope/material/base requirements. Only
        # containing frames qualify; never emit a parent, move the old object,
        # lower evidence thresholds or erase an existing miniature.
        offsets = sorted(((dx, dy) for dx in range(-2, 3) for dy in range(-2, 3)),
                         key=lambda p: (p[0] ** 2 + p[1] ** 2, p))
        for pt, px, py in self.spikes:
            if pt != direction or not (px - 2 <= mx <= px + 18 and py - 2 <= my <= py + 18):
                continue
            for dx, dy in offsets:
                if source_size_owns(self.ownership, mini, (direction, px + dx, py + dy)):
                    self.results[mini] = True
                    return True
        for dx in (-16, -8, 0):
            for dy in (-16, -8, 0):
                x, y = mx + dx, my + dy
                if not (4 <= x <= 764 and 4 <= y <= 572):
                    continue
                parent = direction, x, y
                if not triangle_contains(tuple((x + vx, y + vy) for vx, vy in VERTICES[direction]), child):
                    continue
                ink = self.stroke(32).stroke(x, y, direction)
                if (ink['score'] >= 11 / 12 and _independent_leading_ink(
                        self.stroke(32), x, y, direction, child,
                        1 if ink['contrast'] > 0 else -1)):
                    self.results[mini] = True
                    return True
                for anchor in self.original_anchors():
                    if anchor[0] != direction or anchor == parent:
                        continue
                    scores = [sum(a * b for a, b in zip(self.glyph(parent, m), self.glyph(anchor, m)))
                              for m in (0, 2)]
                    if min(scores) >= .95:
                        if parent not in self.rgb_scores:
                            self.rgb_scores[parent] = _strict_rgb_slopes(self.color(), parent)
                        if self.rgb_scores[parent] >= 2 / 3:
                            self.results[mini] = True
                            return True
        # The same strict pure-source owner, extended only to complete in-frame
        # full boxes at the viewport edge. Not a blanket border exclusion.
        for dx in (-16, -8, 0):
            for dy in (-16, -8, 0):
                x, y = mx + dx, my + dy
                if 4 <= x <= 764 and 4 <= y <= 572:
                    continue
                if 0 <= x <= 768 and 0 <= y <= 576 and source_size_owns(
                        self.ownership, mini, (direction, x, y), allow_viewport_edge=True):
                    self.results[mini] = True
                    return True
        self.results[mini] = False
        return False


class JoinedMiniClosure:
    def __init__(self, local_field, solids):
        self.field, self.solids, self.results = local_field(16), solids, {}

    def signed_sides(self, x, y, direction):
        field = self.field
        tip, *ends = field.vertices[direction]
        cx = sum(p[0] for p in field.vertices[direction]) / 3
        cy = sum(p[1] for p in field.vertices[direction]) / 3
        values = []
        for end in ends:
            tx, ty = end[0] - tip[0], end[1] - tip[1]
            nx, ny = -ty, tx
            if nx * (cx - (tip[0] + end[0]) / 2) + ny * (cy - (tip[1] + end[1]) / 2) > 0:
                nx, ny = -nx, -ny
            length = hypot(nx, ny)
            nx, ny = nx / length, ny / length
            side = []
            for i in range(10):
                q = .2 + .6 * i / 9
                px, py = x + tip[0] + q * tx, y + tip[1] + q * ty
                outer = sum(field.pixel(round(px + j * nx), round(py + j * ny)) for j in (2, 3, 4)) / 3
                inner = sum(field.pixel(round(px - j * nx), round(py - j * ny)) for j in (0, 1, 2)) / 3
                side.append(outer - inner)
            values.append(median(side) / field.patch_stats(x, y)[1])
        return values

    def closed(self, key):
        if key in self.results:
            return self.results[key]
        t, x, y = key
        if not 7 <= t <= 10:
            return False
        direction = t - 4
        partner = {3: (10, x, y + 16), 6: (7, x, y - 16),
                   4: (9, x - 16, y), 5: (8, x + 16, y)}[direction]
        sides = []
        for mt, mx, my in (key, partner):
            if (not (4 <= mx <= 780 and 4 <= my <= 588)
                    or any(max(mx, bx) < min(mx + 16, bx + w)
                           and max(my, by) < min(my + 16, by + h) for bx, by, w, h in self.solids)
                    or not self.field.could_have_strong_slopes(mx, my, mt - 4)
                    or self.field.localized_score(mx, my, mt - 4) != 1.0
                    or self.field.patch_stats(mx, my)[1] < 12):
                self.results[key] = False
                return False
            side = self.signed_sides(mx, my, mt - 4)
            sides.extend(side)
            if min(abs(s) for s in side) < .2 or side[0] * side[1] <= 0:
                self.results[key] = False
                return False
        self.results[key] = not min(sides) <= 0 <= max(sides)
        return self.results[key]
