"""Original-source background prediction under local affine illumination.

Only exterior patches of independently source-qualified glyphs are witnesses.
Ambiguous/insufficient evidence is not a declaration of empty space.
"""
from __future__ import annotations

from copy import deepcopy
from math import hypot
from statistics import median

from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import _contains


class SourceLocalBackground:
    """Scan-local RGB evidence; no references, emitted-object teachers or I/O."""

    def __init__(self, library, is_background):
        self.examples, self.cache = [], {}
        for anchor in library.anchors:
            type_id, x, y = anchor['key']
            size = anchor['size']
            direction = type_id-4 if type_id > 6 else type_id
            polygon = [(x+u*size/32, y+v*size/32) for u, v in VERTICES[direction]]
            margin = size/8
            corners = [(x+margin, y+margin), (x+size-margin, y+margin),
                       (x+size-margin, y+size-margin), (x+margin, y+size-margin)]
            for cx, cy in corners:
                if _contains(polygon, cx, cy):
                    continue
                values = library.raw.sample(cx, cy, size=2 if size == 16 else 4)
                if values is None or sum(is_background(v) for v in values)/len(values) < .95:
                    continue
                mean = tuple(sum(v[c] for v in values)/len(values) for c in range(3))
                self.examples.append(dict(point=(cx, cy), mean=mean, source_anchor=tuple(anchor['key'])))

    def predict(self, x, y, limit):
        """Return isolated evidence; failed prediction must not justify removal."""
        key = x, y, limit
        if key in self.cache:
            return deepcopy(self.cache[key])
        nearby = sorted(self.examples, key=lambda r: (
            hypot(r['point'][0]-x, r['point'][1]-y), r['source_anchor']))
        chosen, regions = [], set()
        for row in nearby:
            chosen.append(row)
            regions.add((row['source_anchor'][1]//32, row['source_anchor'][2]//32))
            if len(chosen) >= 6 and len(regions) >= 3:
                break
        if len(regions) < 3:
            return dict(valid=False, reason='insufficient independent original BG')
        coefficients = []
        for channel in range(3):
            matrix = [[0., 0., 0., 0.] for _ in range(3)]
            for row in chosen:
                sx, sy = row['point']
                axis = (1., (sx-x)/96, (sy-y)/96)
                weight = 1/(16+hypot(sx-x, sy-y))**2
                for i in range(3):
                    for j in range(3):
                        matrix[i][j] += weight*axis[i]*axis[j]
                    matrix[i][3] += weight*axis[i]*row['mean'][channel]
            for k in range(3):
                pivot = max(range(k, 3), key=lambda r: abs(matrix[r][k]))
                if abs(matrix[pivot][k]) < 1e-10:
                    return dict(valid=False, reason='degenerate source BG positions')
                matrix[k], matrix[pivot] = matrix[pivot], matrix[k]
                divisor = matrix[k][k]
                matrix[k] = [value/divisor for value in matrix[k]]
                for r in range(3):
                    if r == k:
                        continue
                    factor = matrix[r][k]
                    matrix[r] = [a-factor*b for a, b in zip(matrix[r], matrix[k])]
            coefficients.append([matrix[i][3] for i in range(3)])
        prediction = tuple(max(0., min(255., c[0])) for c in coefficients)
        residuals = []
        for row in chosen:
            sx, sy = row['point']
            estimate = tuple(max(0., min(255., c[0]+c[1]*(sx-x)/96+c[2]*(sy-y)/96))
                             for c in coefficients)
            residuals.append(hypot(*(a-b for a, b in zip(row['mean'], estimate))))
        residual = median(residuals)
        result = dict(valid=residual <= limit, prediction=prediction, residual=residual, limit=limit,
                      source_witnesses=chosen, independent_source_regions=len(regions), original_source_only=True)
        self.cache[key] = result
        return deepcopy(result)
