"""Read-only source RGB variation corroboration for finite rectangle queries.

Registered original source frames are locators, not answers. Recheck their
geometry, independent physical coverage and existing .9 RGB-pattern agreement.
Keep RGB variation separate from spatial template matching: a striped tile can
share material with a framed tile without having the same interior artwork.
No references, private imports, detector binding, emissions or retirement.
Callers still own original-only provenance, marker/occlusion arbitration, and
whole-map qualification. A successful query is not a certified JTool object.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import ceil, floor, isfinite, sqrt

from scripts.source_contours import SourceContours
from scripts.source_glyph_prototypes import SourceGlyphLibrary
from scripts.source_rectangle_prototypes import _coherent_exterior, _dot, _qualified
from scripts.source_repeated_identity import _closed_rectangle


def _distance2(first, second):
    return sum((a - b) ** 2 for a, b in zip(first, second))


def _mean(values):
    return tuple(sum(rgb[c] for rgb in values) / len(values) for c in range(3))


def _disjoint(first, second):
    return (max(first[0], second[0]) >= min(first[2], second[2])
            or max(first[1], second[1]) >= min(first[3], second[3]))


def _finite(values, length):
    return (len(values) == length and all(isinstance(v, (int, float))
            and not isinstance(v, bool) and isfinite(v) for v in values))


@dataclass(frozen=True)
class _Witness:
    origin: tuple
    physical: tuple
    palette: tuple
    mean: tuple
    closed: bool = False


class SourceRGBDistribution:
    """One immutable source, original registered parents and background fronts.

    ``parents`` are registered native32 x,y source frames from an independently
    mined ORIGINAL cohort, not new hypotheses or supplied map answers.
    ``background_glyphs`` are ORIGINAL type,x,y locators whose front material
    already passed source-local background-role calibration. Their triangles,
    fronts and independent physical support are rechecked, not trusted labels.
    Compact/extended-world use remains unqualified and conservatively abstains.
    Queries never extend either teacher cohort. Returned proofs are isolated.
    """

    def __init__(self, frame, parents, background_glyphs):
        self.frame = frame
        self.parents, self.background = (), ()
        self._distances, self._results = {}, {}
        self.reason = 'insufficient independent original source witnesses'
        image = frame.original_snapshot()
        self.field = SourceContours(image, frame.extent, source_frame=frame)
        if frame.extent != frame.room:
            self.reason = 'extended source transform not qualified'
            return
        library = SourceGlyphLibrary(image, frame.room, (), source_frame=frame)
        parent_rows, signatures = [], []
        for point in parents:
            if not _finite(point, 2):
                raise ValueError('Parent locators must be finite native x,y pairs')
            x, y = point
            if not frame.rectangle_available(x, y, 32, 32, margin=4):
                continue
            faces = self.field.rectangle(x, y, 32)
            if _qualified(faces) < 4:
                ix, iy = .5 * frame.pitch[0], .5 * frame.pitch[1]
                corners = ((x + ix, y + iy), (x + 32 - ix, y + iy),
                           (x + 32 - ix, y + 32 - iy), (x + ix, y + 32 - iy))
                alternate = [self.field.edge(corners[i], corners[(i + 1) % 4])
                             for i in range(4)]
                if _qualified(alternate) > _qualified(faces):
                    faces = alternate
            if _qualified(faces) < 3:
                continue
            physical = self._physical(x, y, 32)
            if any(not _disjoint(physical, row.physical) for row in parent_rows):
                continue
            signature = library.signature(3, x, y)
            if any(_dot(signature, other) < .9 for other in signatures):
                continue
            values = self._sample(x + 4, y + 4, 24, 16)
            parent_rows.append(_Witness(tuple(point), physical, tuple(sorted(set(values))),
                _mean(values), _qualified(faces) == 4 and _coherent_exterior(library, x, y)))
            signatures.append(signature)
        background_rows = []
        for key in background_glyphs:
            if (not _finite(key, 3) or key[0] not in range(3, 11)
                    or any(not isinstance(v, int) for v in key)):
                raise ValueError('Background glyphs must be original integer type,x,y triples')
            type_id, x, y = key
            if not all(f.support >= 9 and not f.unknown
                       for f in self.field.triangle(type_id, x, y)):
                continue
            size = 16 if type_id > 6 else 32
            direction = type_id - 4 if type_id > 6 else type_id
            n = size / 2
            fx, fy = {3: (x + size / 4, y - n), 6: (x + size / 4, y + size),
                      4: (x + size, y + size / 4), 5: (x - n, y + size / 4)}[direction]
            if not frame.rectangle_available(fx, fy, n, n):
                continue
            physical = self._physical(fx, fy, n)
            if any(not _disjoint(physical, row.physical) for row in background_rows):
                continue
            values = self._sample(fx + n / 4, fy + n / 4, n / 2, 8)
            background_rows.append(_Witness(tuple(key), physical,
                tuple(sorted(set(values))), _mean(values)))
        self.parents, self.background = tuple(parent_rows), tuple(background_rows)
        if (len(self.parents) >= 3 and sum(row.closed for row in self.parents) >= 2
                and len(self.background) >= 3):
            self.reason = None

    def _physical(self, x, y, size):
        extent = self.frame.extent
        return (floor(extent.x + x * extent.width / 800),
                floor(extent.y + y * extent.height / 608),
                ceil(extent.x + (x + size) * extent.width / 800),
                ceil(extent.y + (y + size) * extent.height / 608))

    def _sample(self, x, y, size, count):
        samples = [self.frame.original_sample(x + (i + .5) * size / count,
                   y + (j + .5) * size / count) for j in range(count) for i in range(count)]
        if any(position is None or rgb is None for position, rgb in samples):
            raise ValueError('Unknown source samples cannot supply a colour witness')
        return [rgb for position, rgb in samples]

    def _rgb_distances(self, rgb):
        if rgb not in self._distances:
            self._distances[rgb] = tuple(tuple(min(_distance2(rgb, color)
                for color in row.palette) for row in group)
                for group in (self.parents, self.background))
        return self._distances[rgb]

    def support(self, x, y):
        """Query a finite original integer locator; no phase changes its origin."""
        if any(not isinstance(v, int) or isinstance(v, bool) for v in (x, y)):
            raise ValueError('Queries must be integer native x,y locators')
        if (x, y) in self._results:
            return deepcopy(self._results[x, y])
        result = dict(passed=False, origin=[x, y], phases=[], reason=self.reason,
                      no_objects_changed=True, no_query_as_teacher=True)
        if self.reason is not None or not (0 <= x <= 768 and 0 <= y <= 576):
            result['reason'] = self.reason or 'unknown source body'
            return result
        for dx in (0, -self.frame.pitch[0], self.frame.pitch[0]):
            for dy in (0, -self.frame.pitch[1], self.frame.pitch[1]):
                px, py = x + dx, y + dy
                if not self.frame.rectangle_available(px, py, 32, 32, margin=4):
                    continue
                physical = self._physical(px, py, 32)
                eligible = [i for i, p in enumerate(self.parents) if _disjoint(physical, p.physical)]
                negatives = [i for i, p in enumerate(self.background) if _disjoint(physical, p.physical)]
                if (len(eligible) < 3 or sum(self.parents[i].closed for i in eligible) < 2
                        or len(negatives) < 3):
                    continue
                separation = min(sqrt(_distance2(self.parents[i].mean, self.background[j].mean))
                                 for i in eligible for j in negatives)
                if separation <= 0:
                    continue
                quarters = []
                for oy in (0, 16):
                    for ox in (0, 16):
                        values = self._sample(px + ox + 4, py + oy + 4, 8, 8)
                        matched = 0
                        for rgb in values:
                            positive, negative = self._rgb_distances(rgb)
                            bg = min(negative[j] for j in negatives)
                            # Squared .5 distance ratio, unchanged RGB threshold.
                            matched += sum(positive[i] < .25 * bg for i in eligible) >= 3
                        fraction = matched / len(values)
                        error = min(sqrt(_distance2(_mean(values), self.parents[i].mean)) for i in eligible)
                        quarters.append(dict(passed=fraction >= .95 and error <= .25 * separation,
                            foreground_fraction=fraction, mean_error=error, mean_limit=.25 * separation))
                closure = _closed_rectangle(self.field, self.frame, px, py)
                passed = all(q['passed'] for q in quarters) and closure is not None
                proof = dict(phase=[dx, dy], passed=passed, quarters=quarters, closure=closure,
                    other_original_parents=[list(self.parents[i].origin) for i in eligible],
                    other_background_glyphs=[list(self.background[i].origin) for i in negatives])
                result['phases'].append(proof)
                if passed and not result['passed']:
                    result.update(passed=True, first_valid_proof=proof)
        if not result['passed']:
            result['reason'] = 'source RGB variation or coherent closure not established'
        self._results[x, y] = result
        return deepcopy(result)
