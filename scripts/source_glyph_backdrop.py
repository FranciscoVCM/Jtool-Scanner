"""Original geometry-qualified sprite exteriors, not terrain palette labels.

This scan-local model does not emit objects or declare empty space. Consumers
must retain their own competing-object, physical-coverage and unknown vetoes.
No newly emitted hypotheses or reference maps may become source teachers.
"""
from copy import deepcopy
from math import dist, hypot, isfinite

from jtool_scanner.spike_shape import VERTICES
from scripts.source_directional_body import SourceDirectionalBodyEvidence
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_glyph_prototypes import _contains
from scripts.source_interior_glyphs import _mean
from scripts.source_local_background import SourceLocalBackground
from scripts.source_pixel_geometry import PolygonPixelCoverage, original_pixel_bounds


def _intersects(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def _limit(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or value <= 0:
        raise ValueError('A finite positive source colour bound is required')


class SourceGlyphBackdrop:
    """Independent original-source backdrop with isolated cached evidence."""

    def __init__(self, filled, original, *, source_grid, intrinsic=()):
        original = tuple(original)
        if (not isinstance(filled, FilledGlyphEvidence) or filled.original_spikes != tuple(sorted({
                (d.type_id, d.x, d.y) for d in original if 3 <= d.type_id <= 6}))):
            raise ValueError('Backdrop needs the same filled frame and original detections')
        self.filled, self.frame, self.original = filled, filled.frame, original
        self.body = SourceDirectionalBodyEvidence(filled, original, source_grid=source_grid,
                                                  require_directional_texture=True)
        self.spec = tuple((d.type_id, d.x, d.y) for d in original)
        self._source = self.frame.original_snapshot()
        self.qualified, self.masks = {}, {}
        for key in filled.original_spikes:
            proof = self.body.support(key)
            if proof['passed']:
                self.qualified[key] = proof
            old = filled.support_joint_phase(key, short_circuit=True)
            if proof['passed'] or old['passed']:
                t, x, y = key
                self.masks[key] = PolygonPixelCoverage(self.frame, [(x+a, y+b) for a, b in VERTICES[t]])
        self.opaque = []
        for t, x, y in self.spec:
            if t in (1, 2) or 7 <= t <= 10 or t > 10:
                size = 16 if t in (2, 7, 8, 9, 10) else 32
                self.opaque.append((x, y, x+size, y+size))
        self.opaque.extend((x, y, x+16, y+16) for x, y in intrinsic)
        self.anchor_results, self.models = {}, {}

    def _patch(self, cx, cy, limit):
        samples = []
        for j in range(4):
            for i in range(4):
                position = self.frame.original_position(cx-1.5+i, cy-1.5+j)
                if position is None:
                    return dict(passed=False, reason='unknown physical exterior patch')
                samples.append((position, self._source.pixel(*position)))
        positions = sorted({p for p, value in samples})
        if len(positions) < 9:
            return dict(passed=False, reason='insufficient distinct physical exterior centres')
        bounds = [original_pixel_bounds(self.frame, *p) for p in positions]
        if any(b is None for b in bounds):
            return dict(passed=False, reason='unknown physical square support')
        box = (min(b[0] for b in bounds), min(b[1] for b in bounds),
               max(b[2] for b in bounds), max(b[3] for b in bounds))
        if any(_intersects(box, b) for b in self.opaque):
            return dict(passed=False, reason='exterior touches original terrain/mini/nongeometry/intrinsic box')
        for coverage in self.masks.values():
            polygon = coverage.vertices
            pb = (min(p[0] for p in polygon), min(p[1] for p in polygon),
                  max(p[0] for p in polygon), max(p[1] for p in polygon))
            if _intersects(box, pb) and any((coverage.overlap(*p) or 0) > 1e-9 for p in positions):
                return dict(passed=False, reason='exterior intersects independently qualified original glyph')
        values = [rgb for p, rgb in samples]
        average = _mean(values)
        maximum = max(dist(rgb, average) for rgb in values)
        if maximum > limit:
            return dict(passed=False, reason='exterior source RGB not coherent within existing bound', maximum=maximum)
        return dict(passed=True, point=(cx, cy), mean=average, positions=positions,
                    RGB=values, maximum_deviation=maximum)

    def anchors(self, limit):
        """Two excluded/coherent source exteriors per original qualified spike."""
        _limit(limit)
        if limit in self.anchor_results:
            return deepcopy(self.anchor_results[limit])
        accepted, rejected = [], []
        for key, proof in sorted(self.qualified.items()):
            t, x, y = key
            if not self.frame.rectangle_available(x, y, 32, 32, margin=4):
                continue
            polygon = [(x+a, y+b) for a, b in VERTICES[t]]
            corners = [(x+a, y+b) for a, b in ((4, 4), (28, 4), (28, 28), (4, 28))
                       if not _contains(polygon, x+a, y+b)]
            patches = [self._patch(*p, limit) for p in corners]
            if not all(p['passed'] for p in patches):
                rejected.append(dict(key=key, reasons=[p.get('reason') for p in patches if not p['passed']]))
                continue
            body = self.body._body(key)
            if body is None:
                rejected.append(dict(key=key, reasons=['unknown original body']))
                continue
            body_mean = _mean(body)
            contrast = min(dist(body_mean, p['mean']) for p in patches)
            difference = dist(patches[0]['mean'], patches[1]['mean'])
            if contrast <= 0 or difference > .1*contrast:
                rejected.append(dict(key=key, reasons=['exterior pair not coherent under existing .1contrast'],
                                     contrast=contrast, difference=difference))
                continue
            accepted.append(dict(key=key, patches=patches, body_RGB=body_mean, contrast=contrast,
                                 corner_difference=difference, original_body_proof=proof))
        result = dict(accepted=accepted, rejected=rejected, qualified_original_glyphs=len(self.qualified), old_limit=limit)
        self.anchor_results[limit] = deepcopy(result)
        return result

    def model(self, key, limit):
        """One fixed affine model from OTHER disjoint original anchors only."""
        _limit(limit)
        try:
            key = tuple(key)
        except TypeError as error:
            raise ValueError('Backdrop query needs full-block type1,x,y') from error
        if (len(key) != 3 or isinstance(key[0], bool) or key[0] != 1 or any(isinstance(v, bool) or not isinstance(v, (int, float))
                or not isfinite(v) for v in key[1:])):
            raise ValueError('Backdrop query needs full-block type1,x,y')
        identity = key, limit
        if identity in self.models:
            return deepcopy(self.models[identity])
        _, x, y = key
        cx, cy = x+16, y+16
        context = x-4, y-4, x+36, y+36
        selected, boxes = [], []
        choices = self.anchors(limit)['accepted']
        for anchor in sorted(choices, key=lambda a: (hypot(a['key'][1]+16-cx, a['key'][2]+16-cy), a['key'])):
            t, a, b = anchor['key']
            box = a, b, a+32, b+32
            if _intersects(context, box) or any(_intersects(box, p) for p in boxes):
                continue
            boxes.append(box)
            selected.extend(dict(point=p['point'], mean=p['mean'], source_anchor=anchor['key']) for p in anchor['patches'])
        if len(boxes) < 3:
            failed = dict(valid=False, reason='insufficient OTHER disjoint geometry-qualified BG anchors', other_anchor_boxes=boxes)
            self.models[identity] = failed
            return deepcopy(failed)
        model = object.__new__(SourceLocalBackground)
        model.examples, model.cache = deepcopy(selected), {}
        proof = model.predict(cx, cy, limit, include_plane=True)
        if proof.get('valid'):
            errors = [dist(self.predict(proof, *row['point']), row['mean']) for row in proof['source_witnesses']]
            proof['maximum_original_witness_residual'] = max(errors)
            proof['valid'] = max(errors) <= limit
        proof.update(other_anchor_boxes=boxes, no_terrain_palette_labels_used=True,
                     original_geometry_qualified_exterior_ONLY=True, query_not_teacher=True,
                     old_limit=limit, query_context=context)
        self.models[identity] = deepcopy(proof)
        return proof

    @staticmethod
    def predict(model, x, y):
        if not model.get('valid'):
            return None
        cx, cy = model['source_affine_centre']
        return tuple(max(0., min(255., c[0]+c[1]*(x-cx)/96+c[2]*(y-cy)/96))
                     for c in model['source_affine_coefficients'])
