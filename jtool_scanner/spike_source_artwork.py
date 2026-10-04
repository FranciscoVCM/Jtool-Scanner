"""Independent crossed-art extent for NEW triangle ambiguity only.

Local column background removes broad illumination, not object color. Joint
RGB deviation preserves useful colored ink; original RGB boundaries protect
real overlaid triangles. No semantic label, palette, answer or room identity
enters ownership. Existing detections are never deleted by this observer.
"""

from math import hypot, sqrt
from statistics import median

from .spike_shape import VERTICES, _percentile
from .spike_source_growth import _distance


class _ColumnBackground:
    """Tiny source-owned view sharing the scan's already normalized RGB."""

    def __init__(self, rgb, parent):
        self.rgb, self.parent = rgb, parent
        self.columns, self.values = {}, {}

    def pixel(self, x, y):
        key = x, y
        if key not in self.values:
            if x not in self.columns:
                _, top = self.parent
                values = [self.rgb.pixel(x, py) for py in range(top, top + 32)]
                self.columns[x] = tuple(median(v[c] for v in values) for c in range(3))
            self.values[key] = 128 - sqrt(sum(
                (a - b) ** 2 for a, b in zip(self.rgb.pixel(x, y), self.columns[x])))
        return self.values[key]

    def gradient(self, x, y):
        return ((self.pixel(x + 1, y) - self.pixel(x - 1, y)) / 2,
                (self.pixel(x, y + 1) - self.pixel(x, y - 1)) / 2)


def independent_child_boundary(rgb, mini, parent):
    """Protect weak coherent own RGB edges, without borrowing X pixels.

    This is protective evidence, not an emission or absence certificate.
    Several materials can coexist: a componentwise median between them must
    not erase a real weaker color mode. Count distinct source sample positions.
    """
    t, x, y = mini
    ox, oy = parent
    tip, *ends = tuple((vx / 2, vy / 2) for vx, vy in VERTICES[t - 4])
    for end in ends:
        tx, ty = end[0] - tip[0], end[1] - tip[1]
        length = hypot(tx, ty)
        nx, ny = -ty / length, tx / length
        profiles = []
        for i in range(12):
            q = .15 + .7 * i / 11
            px, py = x + tip[0] + q * tx, y + tip[1] + q * ty
            candidates = []
            for j in range(-2, 3):
                sx, sy = round(px + j * nx), round(py + j * ny)
                distance = min(abs((sx - ox) - (sy - oy)),
                               abs((sx - ox) + (sy - oy) - 32)) / sqrt(2)
                if distance <= 3:
                    continue
                gx, gy = rgb.gradient(sx, sy)
                magnitude = sqrt(sum(a * a + b * b for a, b in zip(gx, gy)))
                vector = tuple(a * nx + b * ny for a, b in zip(gx, gy))
                norm = sqrt(sum(v * v for v in vector))
                if magnitude >= 4 and norm >= magnitude * .97:
                    candidates.append((vector, norm))
            profiles.append(candidates)
        coherent = False
        for candidates in profiles:
            for seed, norm in candidates:
                if sum(any(abs(sum(a * b for a, b in zip(seed, other)))
                           >= .9 * norm * other_norm for other, other_norm in p)
                       for p in profiles) >= 4:
                    coherent = True
                    break
            if coherent:
                break
        if not coherent:
            return False
    return True


class CrossArtworkOwner:
    """Abstain only on new contained art with independently continued arms."""

    def __init__(self, color):
        self.color = color
        self.frames, self.results = {}, {}

    def _frame(self, parent):
        if parent in self.frames:
            return self.frames[parent]
        x, y = parent
        field = _ColumnBackground(self.color(), parent)
        arms, signs = [], []
        for endpoint in ((0, 0), (32, 0), (0, 32), (32, 32)):
            tx, ty = 16 - endpoint[0], 16 - endpoint[1]
            length = hypot(tx, ty)
            nx, ny = -ty / length, tx / length
            profiles = []
            for i in range(12):
                # Keep the entire4px normal band clear of the outer frame
                # and the crossed center: neither may set this arm's scale.
                q = .30 + .40 * i / 11
                px, py = x + endpoint[0] + q * tx, y + endpoint[1] + q * ty
                values = [field.pixel(round(px + j * nx), round(py + j * ny))
                          for j in range(-4, 5)]
                gradients = [field.gradient(round(px + j * nx), round(py + j * ny))
                             for j in range(-2, 3)]
                profiles.append((px, py, values, gradients))
            spread = median(max(v) - min(v) for _, _, v, _ in profiles)
            if spread < 12:
                self.frames[parent] = None
                return None
            scale = max(1., _percentile([hypot(*g) for _, _, _, gs in profiles for g in gs], .9))
            strength = max(scale * .25, spread * .15)
            dark = median(min(v[0], v[-1]) - min(v[2:7]) for _, _, v, _ in profiles)
            light = median(max(v[2:7]) - max(v[0], v[-1]) for _, _, v, _ in profiles)
            sign = (1 if dark >= max(4., spread * .2) else
                    -1 if light >= max(4., spread * .2) else 0)
            if not sign:
                self.frames[parent] = None
                return None
            signs.append(sign)
            arm, hits, run, longest = [], 0, 0, 0
            for px, py, values, gradients in profiles:
                ink = (min(values[0], values[-1]) - min(values[2:7]) if sign == 1 else
                       max(values[2:7]) - max(values[0], values[-1]))
                found = ink >= max(4., spread * .2) and any(
                    hypot(gx, gy) >= strength
                    and abs(gx * nx + gy * ny) >= hypot(gx, gy) * .95 for gx, gy in gradients)
                arm.append((px, py, found))
                hits += found
                run = run + 1 if found else 0
                longest = max(longest, run)
            if hits < 11 or longest < 8:
                self.frames[parent] = None
                return None
            arms.append(arm)
        self.frames[parent] = arms if len(set(signs)) == 1 else None
        return self.frames[parent]

    def owns_at(self, mini, parent):
        t, mx, my = mini
        x, y = parent
        if not (7 <= t <= 10 and 4 <= x <= 764 and 4 <= y <= 572
                and x <= mx and mx + 16 <= x + 32 and y <= my and my + 16 <= y + 32):
            return False
        arms = self._frame(parent)
        if arms is None:
            return False
        child = tuple((mx + vx / 2, my + vy / 2) for vx, vy in VERTICES[t - 4])
        total = 0
        for arm in arms:
            independent = [hit for px, py, hit in arm if _distance(px, py, child) > 4]
            if len(independent) < 3 or sum(independent) < len(independent) - 1:
                return False
            total += len(independent)
        return total >= 18 and not independent_child_boundary(self.color(), mini, parent)

    def owns(self, mini):
        if mini not in self.results:
            _, x, y = mini
            self.results[mini] = any(self.owns_at(mini, (x + dx, y + dy))
                                     for dx in (-16, -8, 0) for dy in (-16, -8, 0))
        return self.results[mini]
