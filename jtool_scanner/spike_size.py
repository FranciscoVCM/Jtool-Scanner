"""Source contour ownership for competing native32/native16 hypotheses.

Existing detections locate small tests, not their answers. Independent mini
sides and a base locate two real smaller objects; exposed RGB slope absence
can reject an enclosing alias. Conversely, two strong full-size sides can
outvote a mini with a demonstrably missing side. Hidden, weak and color-only
contours abstain. No reference, palette or room identity enters detection.
"""

from math import hypot, sqrt
from statistics import median

from .geometry import Box
from .image import RGBImage
from .spike_shape import SpikeShapeField
from .spike_color_evidence import QuantizedColorSlopeField


def contour_size_changes(
    image: RGBImage, room: Box,
    spikes: list[tuple[int, int, int]],
    solids: list[tuple[int, int, int, int]],
) -> tuple[set[tuple[int, int, int]], set[tuple[int, int, int]]]:
    """Return source-supported additions and unsupported size hypotheses.

    Test at most two mini origins per ambiguous existing full; do not sweep
    every pixel or rerun the scanner. Newly added objects never supply evidence
    for another addition or deletion. All fields and patch metrics are lazy.
    """
    present = set(spikes)
    fulls = sorted(k for k in present if 3 <= k[0] <= 6)
    minis = sorted(k for k in present if 7 <= k[0] <= 10)
    fields: dict[int, SpikeShapeField] = {}
    rgb = None
    added: set[tuple[int, int, int]] = set()
    rejected: set[tuple[int, int, int]] = set()

    def field(size):
        if size not in fields:
            fields[size] = SpikeShapeField(image, room, native_size=size)
        return fields[size]

    def color():
        nonlocal rgb
        if rgb is None:
            rgb = QuantizedColorSlopeField(image, room)
        return rgb

    def clear(points):
        return all(0 <= x < 800 and 0 <= y < 608
                   and not any(bx <= x < bx + w and by <= y < by + h
                               for bx, by, w, h in solids)
                   for x, y in points)

    def base_score(x, y, d):
        f = field(16)
        _, first, second = f.vertices[d]
        tx, ty = second[0] - first[0], second[1] - first[1]
        length = hypot(tx, ty)
        nx, ny = -ty / length, tx / length
        scale, spread = f.patch_stats(x, y)
        hits = 0
        for i in range(12):
            # Corner joins belong to the diagonals. A short, independent
            # middle-base stroke can close an outlined diamond even when
            # equal fills on its two sides have no across-base color step.
            t = .3 + .4 * i / 11
            px, py = x + first[0] + t * tx, y + first[1] + t * ty
            for offset in (-2, -1, 0, 1, 2):
                gx, gy = f.gradient(round(px + offset * nx), round(py + offset * ny))
                magnitude = hypot(gx, gy)
                if (magnitude >= max(scale * .25, spread * .15)
                        and abs(gx * nx + gy * ny) >= magnitude * .95):
                    hits += 1
                    break
        return hits / 12

    def closed(k):
        t, x, y = k
        d = t - 4
        if not (4 <= x <= 780 and 4 <= y <= 588):
            return False
        if any(max(x, bx) < min(x + 16, bx + w)
               and max(y, by) < min(y + 16, by + h) for bx, by, w, h in solids):
            return False
        f = field(16)
        return (f.localized_score(x, y, d) >= 11 / 12
                and f.patch_stats(x, y)[1] >= 12
                and base_score(x, y, d) >= .5)

    def absent_side(x, y, d, size, side, *, leading=False):
        f = field(size)
        c = color()
        tip, *ends = f.vertices[d]
        end = ends[side]
        tx, ty = end[0] - tip[0], end[1] - tip[1]
        length = hypot(tx, ty)
        nx, ny = -ty / length, tx / length
        samples, possible = 0, 0
        # Negative evidence must not use a neighboring full's high gradient
        # percentile to hide a weaker real RGB-only mini boundary. A central
        # RGB difference's six channel components have total quantization
        # error squared <=6*(.5**2). Anything above that bound can protect a
        # possible direction, even when too weak to add a new object.
        minimum = 1.5
        strong_minimum = (c.patch_scale(x, y) * .25) ** 2
        ratio = sqrt(1 - .95 ** 2) / .95
        weak_vectors = []
        for i in range(12):
            t = .15 + (.25 if leading else .70) * i / 11
            px, py = x + tip[0] + t * tx, y + tip[1] + t * ty
            points = [(round(px + offset * nx), round(py + offset * ny))
                      for offset in range(-4, 5)]
            if not clear(points):
                continue
            samples += 1
            compatible = []
            strong = False
            for sx, sy in points[2:7]:
                gx, gy = c.gradient(sx, sy)
                magnitude_squared = sum(a*a + b*b for a, b in zip(gx, gy))
                if magnitude_squared <= minimum:
                    continue
                vector = tuple(a*nx + b*ny for a, b in zip(gx, gy))
                normal = sqrt(sum(a*a for a in vector))
                tangent = sqrt(sum((-a*ny + b*nx)**2 for a, b in zip(gx, gy)))
                # Non-border central differences: each endpoint is rounded
                # to8 bits. Possible RGB directions preserve that uncertainty.
                error = sqrt(3) * .5 * (abs(nx) + abs(ny))
                if max(0, tangent - error) <= (normal + error) * ratio:
                    compatible.append((normal, vector))
                    strong = strong or magnitude_squared >= strong_minimum
            possible += strong
            weak_vectors.append(max(compatible)[1] if compatible else (0., 0., 0.))
        if samples < 10 or possible / samples > .25:
            return False
        # Weak real RGB edges keep a consistent signed channel transition
        # along the slope. Random texture/quantization-compatible directions
        # must not be promoted to geometry, but a coherent weaker boundary
        # must also not be erased merely by the stronger surrounding full.
        center = tuple(median(v[k] for v in weak_vectors) for k in range(3))
        center_norm = sqrt(sum(a*a for a in center))
        coherent = sum(sum(a*b for a, b in zip(v, center))
                       >= .9 * center_norm * sqrt(sum(a*a for a in v))
                       for v in weak_vectors if any(v))
        return center_norm ** 2 <= minimum or coherent / samples < 2 / 3

    for d, x, y in fulls:
        if not (4 <= x <= 764 and 4 <= y <= 572):
            continue
        f = field(32)
        sides = f.side_scores(x, y, d)
        if max(sides) >= .75:
            continue
        positions = ({3: ((x, y + 16), (x + 16, y + 16)),
                      6: ((x, y), (x + 16, y)),
                      4: ((x, y), (x, y + 16)),
                      5: ((x + 16, y), (x + 16, y + 16))}[d])
        pair = [(d + 4, px, py) for px, py in positions]
        if not all(closed(k) for k in pair):
            continue
        added.update(k for k in pair if k not in present)
        # A real half-embedded full has a supported side or hidden leading
        # samples. A weak full score alone does not establish its absence.
        if (f.patch_stats(x, y)[1] >= 12
                and all(absent_side(x, y, d, 32, i, leading=True) for i in (0, 1))):
            rejected.add((d, x, y))

    for t, mx, my in minis:
        d = t - 4
        containing = [(fd, x, y) for fd, x, y in fulls if fd == d
                      and x <= mx and mx + 16 <= x + 32
                      and y <= my and my + 16 <= y + 32]
        if not containing or not (4 <= mx <= 780 and 4 <= my <= 588):
            continue
        if not any(field(32).score(x, y, d) >= 11 / 12
                   and field(32).patch_stats(x, y)[1] >= 12
                   and abs(field(32).contrast(x, y, d)) >= .5
                   for _, x, y in containing):
            continue
        possible = color().possible_side_scores(mx, my, field(16).vertices[d])
        if any(possible[i] <= .25 and absent_side(mx, my, d, 16, i) for i in (0, 1)):
            rejected.add((t, mx, my))
    return added, rejected
