"""Offline original-pixel backdrop evidence for compact rooms.

This helper does not assign terrain or change scanner behavior. Uniform
surfaces can have other meanings; matching flat paint is not solid or empty
truth by itself.
"""
from collections import defaultdict
from collections.abc import Callable
from math import floor
from statistics import median

from jtool_scanner.geometry import Box


def compact_flat_background(
    pixel: Callable[[int, int], tuple[int, int, int]],
    image_size: tuple[int, int],
    frame: tuple[int, int, int, int],
    observed: Box,
) -> dict:
    """Observe two disjoint sets of smooth, fully captured 16px patches.

    The frame maps native room coordinates into physical source pixels; it
    can extend past the image. An unavailable or duplicated sample never
    provides background evidence. The caller must supply the observed
    compact extent, independent of any emitted detections.
    """
    ox, oy, w, h = frame
    groups = [defaultdict(list), defaultdict(list)]
    sampled = set()
    for j, y in enumerate(range(observed.y, observed.bottom, 16)):
        for i, x in enumerate(range(observed.x, observed.right, 16)):
            xs = [floor(ox + (x + d) * w / 800) for d in (2, 6, 10, 14)]
            ys = [floor(oy + (y + d) * h / 608) for d in (2, 6, 10, 14)]
            sites = {(a, b) for a in xs for b in ys}
            if (
                len(sites) != 16 or sites & sampled
                or not all(0 <= a < image_size[0] and 0 <= b < image_size[1] for a, b in sites)
            ):
                continue
            sampled.update(sites)
            channels = tuple(zip(*(pixel(a, b) for b in ys for a in xs)))
            if any(max(c) - min(c) > 10 for c in channels):
                continue
            key = tuple(int(median(c)) // 16 for c in channels)
            groups[(i + j) % 2][key].append((x, y))

    folds = []
    for sample in groups:
        ranks = sorted(sample.items(), key=lambda item: (-len(item[1]), item[0]))
        if not ranks:
            folds.append(dict(qualified=False, ranks=[]))
            continue
        winner, points = ranks[0]
        runner = len(ranks[1][1]) if len(ranks) > 1 else 0
        count = len(points)
        spread = [len({p[i] for p in points}) for i in (0, 1)]
        qualifies = count >= 8 and count > runner and count >= 2 * runner and min(spread) >= 3
        folds.append(dict(qualified=qualifies, winner=winner, spread=spread,
                          ranks=[(k, len(v)) for k, v in ranks]))
    agree = all(f['qualified'] for f in folds) and folds[0]['winner'] == folds[1]['winner']
    color = tuple(v * 16 + 8 for v in folds[0]['winner']) if agree else None
    return dict(color=color, folds=folds, physically_independent_pixels=len(sampled))
