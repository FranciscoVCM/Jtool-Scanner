"""Original RGB evidence for periodic, full-size rail-like terrain bodies.

This is a source diagnostic, not an object classifier. It proposes body
footprints and phase evidence without access to JMaps or scanner output.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from statistics import median

from jtool_scanner.constants import ROOM_HEIGHT, ROOM_WIDTH
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage

_SPACING = 8
_CELL = 32
_TRACKS = (3, 9, 16, 22, 28)


def _project(u: int, span: int, start: int, size: int) -> int:
    # Center-to-cell projection; integer floor handles negative extents.
    return start + (2 * u + 1) * size // (2 * span)


def _dist(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))


def _median_rgb(colors):
    return tuple(median(c) for c in zip(*colors))


def _median_three(a, b, c):
    return tuple(x + y + z - min(x, y, z) - max(x, y, z) for x, y, z in zip(a, b, c))


@dataclass(frozen=True, slots=True)
class RailBodyScore:
    edges: tuple[int, int]
    stable_rows: int
    varied_rows: int
    changes: int
    aligned_error: float
    shifted_errors: tuple[float, float]


@dataclass(frozen=True, slots=True)
class RailBodySurvey:
    scores: dict[tuple[int, int], RailBodyScore]
    positions: tuple[tuple[int, int], ...]
    phase: int | None
    fold_rows: tuple[int, int]
    profile_calls: int


def survey_rail_bodies(image: RGBImage, capture: Box, extent: Box, *, vertical: bool = False) -> RailBodySurvey:
    """Check both physical faces and repeated depth in one chosen orientation.

    Extent is the mapping of the logical room into original image coordinates;
    it may include padding outside the physical capture. Only distinct,
    fully observed physical samples may vote. Orthogonal phase witnesses
    always come from disjoint bands outside every candidate body.
    """
    if (min(capture.width, capture.height, extent.width, extent.height) <= 0
            or capture.x < 0 or capture.y < 0 or capture.right > image.width
            or capture.bottom > image.height):
        raise ValueError("Invalid original capture or extent")
    if vertical:
        U, V = ROOM_HEIGHT, ROOM_WIDTH
        u_origin, v_origin, u_len, v_len = extent.y, extent.x, extent.height, extent.width
        u_min, u_max, v_min, v_max = capture.y, capture.bottom, capture.x, capture.right

        def pixel(u, v):
            return image.pixel(v, u)
    else:
        U, V = ROOM_WIDTH, ROOM_HEIGHT
        u_origin, v_origin, u_len, v_len = extent.x, extent.y, extent.width, extent.height
        u_min, u_max, v_min, v_max = capture.x, capture.right, capture.y, capture.bottom
        pixel = image.pixel

    def u_at(u):
        return _project(u, U, u_origin, u_len)

    def v_at(v):
        return _project(v, V, v_origin, v_len)

    windows = {}
    for u in range(0, U - _CELL + 1, _SPACING):
        cols = tuple(tuple(u_at(u + c + d) for d in (-1, 0, 1)) for c in _TRACKS)
        flat = tuple(j for group in cols for j in group)
        if (len(set(flat)) == 15 and all(u_min <= j < u_max for j in flat)
                and u_min <= u_at(u) <= u_at(u+31) < u_max):
            windows[u] = cols

    @lru_cache(maxsize=65_536)
    def sample_track(cols, v):
        a, b, c = cols
        return _median_three(pixel(a, v), pixel(b, v), pixel(c, v))

    def edge_count(cols, rows):
        count = 0
        for group in cols:
            a, b, c, d = (sample_track(group, v) for v in rows)
            if any(abs(i + j - k - l) >= 24 for i, j, k, l in zip(a, b, c, d)):
                count += 1
        return count

    all_scores = {}
    calls = 0
    for v in range(0, V - _CELL + 1, _SPACING):
        rows = tuple(v_at(k) for k in range(v - 2, v + 34))
        if len(set(rows)) != 36 or rows[0] < v_min or rows[-1] >= v_max:
            continue
        for u, cols in windows.items():
            top = edge_count(cols, rows[:4])
            if top < 4:
                continue
            bottom = edge_count(cols, rows[32:])
            if bottom < 4:
                continue
            calls += 1
            interior = tuple(tuple(sample_track(c, y) for c in cols) for y in rows[4:32])
            common = tuple(_median_rgb(tracks) for tracks in interior)
            stable = sum(sum(_dist(c, m) <= 10 for c in row) >= 4
                         for row, m in zip(interior, common))
            if stable < 21:
                continue
            center = _median_rgb(common)
            varied = sum(_dist(c, center) >= 6 for c in common)
            changes = sum(_dist(a, b) >= 3 for a, b in zip(common, common[1:]))
            if varied < 10 or changes < 7:
                continue

            def error(a, b):
                return median(_dist(r[i], s[i+2]) for r, s in zip(a, b) for i in range(3))

            aligned = error(interior, interior)
            shifted = error(interior[8:], interior[:-8]), error(interior[:-8], interior[8:])
            if min(shifted) - aligned >= 5:
                all_scores[u, v] = RailBodyScore((top, bottom), stable, varied, changes, aligned, shifted)
    sample_track.cache_clear()

    unique = {p for p in all_scores if not any((p[0], p[1] + d) in all_scores for d in (-8, 8))}
    used_v = {v for _, v in unique}
    folds = []
    counts = []
    for fold in (0, 1):
        rows = [v_at(v) for v in range(0, V, 4)
                if (v // _CELL) % 2 == fold and all(not y - 8 <= v < y + 40 for y in used_v)
                and v_min <= v_at(v) < v_max]
        counts.append(len(rows))
        if len(rows) < 24 or len(set(rows)) != len(rows):
            folds.append(None)
            continue
        groups = {p: [] for p in range(0, _CELL, _SPACING)}
        for u in range(8, U - 8, 8):
            a, b = u_at(u - 2), u_at(u + 1)
            if u_min <= a < b < u_max:
                groups[u % _CELL].append(sum(_dist(pixel(a, v), pixel(b, v)) >= 26 for v in rows) / len(rows))
        values = {p: sum(s) / len(s) if s else 0.0 for p, s in groups.items()}
        best, second, *_ = sorted(values, key=values.get, reverse=True)
        folds.append(best if values[best] - values[second] >= .025
                     and sum(z >= .12 for z in groups[best]) >= 5 else None)
    phase = folds[0] if folds[0] == folds[1] else None
    accepted = [p for p in unique if phase is not None and p[0] % _CELL == phase]
    if vertical:
        all_scores = {(v, u): score for (u, v), score in all_scores.items()}
        accepted = [(v, u) for u, v in accepted]
    return RailBodySurvey(all_scores, tuple(sorted(accepted)), phase, tuple(counts), calls)
