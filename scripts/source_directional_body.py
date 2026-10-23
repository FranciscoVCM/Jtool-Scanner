"""Unbound source-body/contour evidence across changing backgrounds.

This is an explicit research API, NOT a scanner binding or object emitter.
Original same-direction texture/body evidence and directed RGB geometry provide
an additional positive conjunction. Unknowns never prove absence; no original
objects or legacy evidence are vetoed. Full controls, source QA and cost remain
required before integrating the additional channel into the scanner.
"""
from copy import deepcopy
from math import hypot, isfinite
from types import SimpleNamespace

from scripts.source_hollow_glyphs import HollowGlyphEvidence
from scripts.source_interior_glyphs import (
    INTERIOR_POINTS, SourceInteriorGlyphEvidence, _mean, _normalized, _oriented,
)
from scripts.source_sampling import SourceFrame
from jtool_scanner.spike_shape import VERTICES


class _DirectedRGBField:
    """Reuse geometry only; neither construct nor claim hollow semantic models."""
    gradient = HollowGlyphEvidence.gradient
    directed = HollowGlyphEvidence.directed

    def __init__(self, frame):
        if not isinstance(frame, SourceFrame):
            raise ValueError('Directed body edges need an immutable source frame')
        self.frame = frame
        self.library = SimpleNamespace(pixel=frame.pixel)
        self.gradients, self.edges = {}, {}

    def _position(self, x, y):
        return self.frame.original_position(x, y)


class SourceDirectionalBodyEvidence(SourceInteriorGlyphEvidence):
    """Additional source-only proof; does not require the old background colour.

    The default requires three disjoint ORIGINAL same-direction texture teachers.
    Explicit False preserves the legacy interior API without this alternative.
    Geometry phases change sampling only, never exported native coordinates.
    """
    def __init__(self, filled, original_detections, *, source_grid,
                 require_directional_texture=True):
        super().__init__(filled, original_detections, source_grid=source_grid,
                         require_directional_texture=require_directional_texture)
        self.directed_field = _DirectedRGBField(self.frame)
        self.new_geometry = {}

    def _measure(self, key):
        old = super()._measure(key)
        if old['passed'] or not self._require_directional_texture or not self.qualified:
            return old
        kind, x, y = key
        if (not self.frame.rectangle_available(x, y, 32, 32, margin=4)
                or not self._has_directional_texture(kind)):
            return old
        body = self._body(key)
        if body is None:
            return old
        points = [(x+a, y+b) for a, b in (_oriented(kind, *p) for p in INTERIOR_POINTS)]
        if any(all(a <= px < a+w and b <= py < b+h for px, py in points)
               for a, b, w, h in self._markers):
            return old
        body_mean = _mean(body)
        for cohort in self._cohorts:
            teachers = tuple(k for k in cohort if abs(k[1]-x) >= 32 or abs(k[2]-y) >= 32)
            if len(teachers) < 3:
                continue
            model = self._model(teachers)
            if model is None or model['limit'] <= 0:
                continue
            error = hypot(*(a-b for a, b in zip(body_mean, model['foreground'])))
            if error > model['limit']:
                continue
            pattern = _normalized([v-model['background'][c] for rgb in body for c, v in enumerate(rgb)])
            correlation = sum(a*b for a, b in zip(pattern, model['pattern']))
            if correlation < .9:
                continue
            paint = self._paint_support(model, body)
            if not paint['passed']:
                continue
            texture = self._directional_texture(key, model)
            if not texture['passed']:
                continue
            geometry = self.geometry(key)
            if not geometry['passed']:
                return old
            return dict(key=key, passed=True, original_source_only=True,
                no_new_teachers=True, no_retirement=True, directional_body_alternative=True,
                original_teachers=teachers, mean_RGB_error=error, mean_RGB_limit=model['limit'],
                correlation=correlation, source_paint=paint, directional_source_texture=texture,
                directed_geometry=geometry, no_background_absence_or_hollow_claim=True,
                native_hypothesis_unchanged=True)
        return old

    def geometry(self, key):
        """Return an isolated diagnostic shared-phase full32 proof."""
        try:
            key = tuple(key)
        except TypeError as error:
            raise ValueError('Directed body geometry needs full type3..6,x,y') from error
        if (len(key) != 3 or key[0] not in (3, 4, 5, 6)
                or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v)
                       for v in key[1:])):
            raise ValueError('Directed body geometry needs full type3..6,x,y')
        if key not in self.new_geometry:
            kind, x, y = key
            px, py = self.frame.pitch
            phases = []
            for dx in (0, -px, px):
                for dy in (0, -py, py):
                    known = self.frame.rectangle_available(x+dx, y+dy, 32, 32, margin=4)
                    if not known:
                        phases.append(dict(phase=(dx, dy), known=False, passed=False))
                        continue
                    poly = [(x+a+dx, y+b+dy) for a, b in VERTICES[kind]]
                    triangle = [self.directed_field.directed(a, b)
                                for a, b in zip(poly, poly[1:]+poly[:1])]
                    if min(triangle) < 9:
                        phases.append(dict(phase=(dx, dy), known=True, passed=False, triangle=triangle))
                        continue
                    box = [(x+dx, y+dy), (x+32+dx, y+dy),
                           (x+32+dx, y+32+dy), (x+dx, y+32+dy)]
                    rectangle = [self.directed_field.directed(a, b)
                                 for a, b in zip(box, box[1:]+box[:1])]
                    raw = self.field.rectangle(x+dx, y+dy, 32)
                    competing = min(rectangle) >= 9 or all(e.support >= 9 and not e.unknown for e in raw)
                    phases.append(dict(phase=(dx, dy), known=True, passed=not competing,
                        triangle=triangle, rectangle=rectangle,
                        raw_rectangle=[dict(support=e.support, unknown=e.unknown) for e in raw]))
            self.new_geometry[key] = dict(passed=any(p['passed'] for p in phases), phases=phases,
                common_phase_NOT_native_origin_change=True, RGB_normal_alignment=.95,
                existing_required_support=9)
        return deepcopy(self.new_geometry[key])


class SourceClosedInteriorGlyphEvidence(SourceDirectionalBodyEvidence):
    """Unbound positive evidence for flat or otherwise unmodelled artwork.

    A complete original interior-material proof AND the existing directed
    three-edge proof can identify a triangle without recognizable texture.
    Neither one alone suffices. Existing strict positives retain their complete
    proofs. No unmatched-background alternative, new teachers, native transform,
    object emission or retirement is authorized by this API.
    """

    def __init__(self, filled, original_detections, *, source_grid,
                 require_directional_texture=True):
        original = tuple(original_detections)
        super().__init__(filled, original, source_grid=source_grid,
                         require_directional_texture=require_directional_texture)
        # The lazy view must use construction-time locators/markers even if a
        # caller later edits its mutable Detection wrappers.
        self._closed_original = deepcopy(original)
        self._closed_filled = filled
        self._closed_grid = source_grid
        self._closed_interior = None

    def _measure(self, key):
        # Deliberately bypass the parent's separate, textured unmatched-
        # background alternative. Its adoption is not implied by this API.
        strict = SourceInteriorGlyphEvidence._measure(self, key)
        if strict['passed'] or not self._require_directional_texture or not self.qualified:
            return strict
        if self._closed_interior is None:
            self._closed_interior = SourceInteriorGlyphEvidence(
                self._closed_filled, self._closed_original, source_grid=self._closed_grid)
        interior = self._closed_interior.support(key)
        if not interior['passed']:
            return strict
        geometry = self.geometry(key)
        if not geometry['passed']:
            return strict
        return {**interior, 'source_closed_body_alternative': True,
                'directed_geometry': geometry, 'strict_channel_abstention': strict,
                'whole_original_body_AND_directed_edges_required': True,
                'no_background_absence_or_hollow_claim': True,
                'texture_not_required_for_closed_source_identity': True}
