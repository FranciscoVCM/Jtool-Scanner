"""Original RGB longitudinal rail-end evidence; no scanner caller is bound."""
from __future__ import annotations

from math import sqrt
from statistics import median

from jtool_scanner.constants import ROOM_HEIGHT, ROOM_WIDTH
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_rail_bodies import _project


def _color_distance(left, right):
    return max(abs(a - b) for a, b in zip(left, right))


def _channel_median(colors):
    return tuple(map(median, zip(*colors)))


def _cosine(left, right):
    norm = sqrt(sum(a * a for a in left) * sum(b * b for b in right))
    return sum(a * b for a, b in zip(left, right)) / max(1e-8, norm)


def observe_rail_end(
    image: RGBImage, capture: Box, extent: Box, x: int, y: int
) -> dict:
    """Check an already phase-qualified horizontal body for one visible end.

    Continuation uses five original RGB columns at each 32px step. The
    transition offset and RGB sign come from one physical row fold; the other
    fold confirms them. Missing photographs cannot qualify an end. The
    result supports a rail proposal; it is not standalone body or hazard truth.
    """
    if (
        min(capture.width, capture.height, extent.width, extent.height) <= 0
        or capture.x < 0 or capture.y < 0
        or capture.right > image.width or capture.bottom > image.height
    ):
        raise ValueError("Invalid original capture or extent")
    rows = tuple(_project(y + j, ROOM_HEIGHT, extent.y, extent.height)
                 for j in range(5, 28))
    if len(set(rows)) != len(rows):
        return {"qualified": False, "unknown": "non-independent rows"}

    def strip(positions):
        cols = tuple(_project(i, ROOM_WIDTH, extent.x, extent.width) for i in positions)
        if len(set(cols)) != len(cols) or not all(
            capture.contains(xx, yy) for xx in cols for yy in rows
        ):
            return None
        return tuple(_channel_median([image.pixel(xx, yy) for xx in cols]) for yy in rows)

    def edge(boundary, sign, shift):
        loc = boundary + shift
        # Reject even cross-side duplicate pixels, not just within each strip.
        if strip([loc - 2*sign, loc - sign, loc + sign, loc + 2*sign]) is None:
            return None
        inside = strip([loc - 2*sign, loc - sign])
        outside = strip([loc + sign, loc + 2*sign])
        diffs = [tuple(a - b for a, b in zip(p, q)) for p, q in zip(inside, outside)]
        fit, held = diffs[::2], diffs[1::2]
        reference = _channel_median(fit)
        if max(map(abs, reference)) < 24:
            return [0, len(fit), 0, len(held)]

        def votes(fold):
            return sum(max(map(abs, d)) >= 24 and _cosine(d, reference) >= .70 for d in fold)

        return [votes(fit), len(fit), votes(held), len(held)]

    flanks = []
    for sign, start in ((-1, x), (1, x + 32)):
        witness = strip([start - sign*k for k in range(3, 8)])
        path = []
        if witness is not None:
            for step in range(5):
                boundary = start + sign*step*32
                outside = strip([boundary + sign*k for k in range(3, 8)])
                if outside is None:
                    path.append({"boundary": boundary, "unknown": "original exterior not visible"})
                    break
                agrees = sum(_color_distance(p, q) <= 12 for p, q in zip(witness, outside))
                if agrees / len(rows) >= .75:
                    path.append({"boundary": boundary, "continuation": agrees})
                    continue
                offsets = [(i, e) for i in range(-2, 3) if (e := edge(boundary, sign, i)) is not None]
                # Choose the offset before looking at held rows.
                pick = max(offsets, key=lambda r: (r[1][0] / r[1][1], -abs(r[0])), default=None)
                qualified = bool(pick and pick[1][0] / pick[1][1] >= .75
                                      and pick[1][2] / pick[1][3] >= .75)
                path.append({"boundary": boundary, "continuation": agrees,
                             "edge": pick, "qualified": qualified})
                break
        flanks.append(path)
    return {"qualified": any(p and p[-1].get("qualified", False) for p in flanks),
            "source_rows": len(rows), "flanks": flanks}
