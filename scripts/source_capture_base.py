"""Read-only filled-glyph evidence when only external base context is censored.

Not a scanner binding. Original body pixels, both directed slopes and a model
from three disjoint original filled witnesses are still required. No missing
pixel is background, no proposal teaches, and no original object is retired.
"""
from copy import deepcopy
from math import sqrt

from jtool_scanner.spike_shape import VERTICES
from scripts.source_filled_pipeline import FilledGlyphEvidence


def capture_base_hypotheses(frame, step=8):
    """Finite 1D capture edges, not a full raster or reference-origin search."""
    if not isinstance(step, int) or isinstance(step, bool) or step <= 0:
        raise ValueError('Positive integer lattice step required')
    extent, room = frame.extent, frame.room
    edges = ((3, (room.bottom-extent.y)*608/extent.height-32, False),
             (6, (room.y-extent.y)*608/extent.height, False),
             (4, (room.x-extent.x)*800/extent.width, True),
             (5, (room.right-extent.x)*800/extent.width-32, True))
    result = set()
    for kind, base_origin, vertical in edges:
        rounded = round(base_origin)
        if abs(rounded-base_origin) > 1e-7 or rounded % step:
            continue
        for offset in range(0, (608 if vertical else 800)-31, step):
            x, y = (rounded, offset) if vertical else (offset, rounded)
            if 0 <= x <= 768 and 0 <= y <= 576:
                result.add((kind, x, y))
    return result


def _cells(key):
    kind, x, y = key
    for j in range(16):
        for i in range(16):
            u, v = 2*i+1, 2*j+1
            a, b = ((u, v) if kind == 3 else (32-v, u) if kind == 4
                    else (v, 32-u) if kind == 5 else (32-u, 32-v))
            yield i-7.5, j-7.5, v, x+a, y+b


def _signature(values):
    """Remove affine RGB illumination on exactly the observed cells."""
    n = len(values)
    mu, mv = (sum(row[c] for row in values)/n for c in (0, 1))
    mean = tuple(sum(row[2][c] for row in values)/n for c in range(3))
    aa = sum((u-mu)**2 for u, v, rgb in values)
    bb = sum((v-mv)**2 for u, v, rgb in values)
    ab = sum((u-mu)*(v-mv) for u, v, rgb in values)
    det = aa*bb-ab*ab
    if det <= 0:
        return None
    au = tuple(sum((u-mu)*(rgb[c]-mean[c]) for u, v, rgb in values) for c in range(3))
    av = tuple(sum((v-mv)*(rgb[c]-mean[c]) for u, v, rgb in values) for c in range(3))
    sx = tuple((au[c]*bb-av[c]*ab)/det for c in range(3))
    sy = tuple((av[c]*aa-au[c]*ab)/det for c in range(3))
    residual = tuple(rgb[c]-mean[c]-sx[c]*(u-mu)-sy[c]*(v-mv)
                     for u, v, rgb in values for c in range(3))
    length = sqrt(sum(z*z for z in residual))
    return None if not length else tuple(z/length for z in residual)


class CaptureBaseEvidence:
    """One immutable original-source filled library; supplementary proof only."""

    def __init__(self, evidence):
        if not isinstance(evidence, FilledGlyphEvidence):
            raise ValueError('Original filled-glyph evidence required')
        self.evidence, self.frame = evidence, evidence.frame
        self._models, self._results = {}, {}

    @staticmethod
    def _key(key):
        key = tuple(key)
        if (len(key) != 3 or any(not isinstance(v, int) or isinstance(v, bool) for v in key)
                or key[0] not in (3, 4, 5, 6) or not 0 <= key[1] <= 768
                or not 0 <= key[2] <= 576):
            raise ValueError('A native full-spike type3..6,x,y triple is required')
        return key

    def boundary(self, key):
        kind, x, y = self._key(key)
        frame = self.frame
        ends = [(x+u, y+v) for u, v in VERTICES[kind][1:]]
        if ends[0][0] == ends[1][0]:
            physical = frame.extent.x+ends[0][0]*frame.extent.width/800
            edge = frame.room.x if kind == 4 else frame.room.right
        else:
            physical = frame.extent.y+ends[0][1]*frame.extent.height/608
            edge = frame.room.y if kind == 6 else frame.room.bottom
        # Arithmetic equality tolerance, not a widened positional allowance.
        return abs(physical-edge) <= 1e-7

    def support(self, key):
        key = self._key(key)
        if key not in self._results:
            self._results[key] = self._measure(key)
        return deepcopy(self._results[key])

    def _measure(self, key):
        if not self.boundary(key):
            return dict(passed=False, reason='base is not on actual capture boundary')
        shape = self.evidence.library.filled.evidence(*key)
        slopes, base = shape.get('slopes', ()), shape.get('raw_base')
        if (len(slopes) != 2 or any(s['support'] < 9 or s['unknown'] for s in slopes)
                or not base or not base[1]):
            return dict(passed=False, reason='not a completely visible two-slope censored-base glyph', silhouette=shape)
        known, values = [], []
        for index, (u, v, base_distance, x, y) in enumerate(_cells(key)):
            if self.frame.original_position(x, y) is None:
                return dict(passed=False, unknown=True, reason='missing original body/source cell')
            rgb = self.frame.pixel(x, y)
            if rgb is None:
                if base_distance <= 28:
                    return dict(passed=False, unknown=True, reason='unknown away from base context')
                continue
            known.append(index)
            values.append((u, v, rgb))
        query = _signature(values)
        if query is None:
            return dict(passed=False, reason='no source appearance residual')
        mask, best = tuple(known), None
        selected = frozenset(mask)
        for model in self.evidence.library.models:
            if model['native_size'] != 32:
                continue
            teachers = self.evidence._teachers(model)
            if not teachers:
                continue
            cache_key = (tuple(map(tuple, model['original_source_witnesses'])), mask)
            if cache_key not in self._models:
                signatures = []
                for witness in model['original_source_witnesses']:
                    measured = [(u, v, self.frame.pixel(x, y))
                                for index, (u, v, _, x, y) in enumerate(_cells(witness)) if index in selected]
                    if len(measured) != len(mask) or any(rgb is None for _, _, rgb in measured):
                        raise ValueError('Original model witness lost source coverage')
                    signatures.append(_signature(measured))
                if any(s is None for s in signatures):
                    raise ValueError('Original model witness has no RGB residual')
                prototype = tuple(sum(s[c] for s in signatures)/len(signatures) for c in range(len(query)))
                norm = sqrt(sum(z*z for z in prototype))
                if not norm:
                    continue
                self._models[cache_key] = tuple(z/norm for z in prototype)
            score = sum(a*b for a, b in zip(query, self._models[cache_key]))
            if best is None or score > best['correlation']:
                best = dict(correlation=score, original_source_witnesses=model['original_source_witnesses'],
                            independent_filled_teachers=teachers)
        return dict(passed=best is not None and best['correlation'] >= .9,
            unknown=False, silhouette=shape, known_cells=len(known), omitted_cells=256-len(known),
            mask=known, best=best, actual_capture_base=True, missing_source_never_background=True,
            no_new_teacher=True, no_original_retirement=True)
