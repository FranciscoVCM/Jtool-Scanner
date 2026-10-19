"""Original-source interior appearance for touching, closed full-spike glyphs.

The existing whole-frame appearance gate remains unchanged. This independent
positive channel requires three raw contour edges AND original interior RGB
cohorts. It never retires objects, treats unknown as empty, or learns outputs.
"""
from copy import deepcopy
from math import dist, hypot, isfinite, sqrt

from jtool_scanner.spike_shape import VERTICES
from scripts.source_filled_pipeline import FilledGlyphEvidence


def _oriented(kind, u, v):
    return ((u, v) if kind == 3 else (32-v, u) if kind == 4 else
            (v, 32-u) if kind == 5 else (32-u, 32-v))


def _distance(point, first, second):
    return abs((second[0]-first[0])*(first[1]-point[1]) -
               (first[0]-point[0])*(second[1]-first[1])) / hypot(
                   second[0]-first[0], second[1]-first[1])


def _interior_points():
    poly = VERTICES[3]
    return tuple((2*i+1, 2*j+1) for j in range(16) for i in range(16)
                 if 2*j+1 >= 2*abs(2*i+1-16)
                 and min(_distance((2*i+1, 2*j+1), poly[k], poly[(k+1)%3])
                         for k in range(3)) >= 4)


INTERIOR_POINTS = _interior_points()
EXTERIOR_POINTS = tuple((2*i+1, 2*j+1) for j in range(16) for i in range(16)
                        if 2*j+1 < 2*abs(2*i+1-16))


def _mean(values):
    return tuple(sum(v[c] for v in values)/len(values) for c in range(3))


def _normalized(values):
    length = sqrt(sum(v*v for v in values))
    return tuple(v/max(1e-12, length) for v in values)


class SourceInteriorGlyphEvidence:
    """One frozen original frame/model domain; proofs are independent copies."""

    def __init__(self, filled, original_detections, *, source_grid):
        if not isinstance(filled, FilledGlyphEvidence):
            raise ValueError('Interior glyphs need actual original filled evidence')
        original = tuple(original_detections)
        spikes = tuple(sorted({(d.type_id, d.x, d.y) for d in original
                               if 3 <= d.type_id <= 6}))
        if spikes != filled.original_spikes:
            raise ValueError('Interior glyph original detections changed')
        self.frame = filled.frame
        self._pixels = self.frame.original_snapshot()
        self._markers = tuple((d.x, d.y, 32, 8 if d.type_id == 13 else 32)
                              for d in original if d.type_id > 10 and d.type_id not in (14, 15, 23))
        self.qualified = source_grid == (25, 19) and self.frame.extent == self.frame.room
        self.field = filled.library.raw.raw.field
        if (not self.frame.matches_source(filled.library.raw.image, self.frame.room)
                or filled.library.raw.room != self.frame.extent
                or self.field.room != self.frame.extent
                or self.field.native_size != (800, 608)
                or self.field.source_frame is not None and self.field.source_frame is not self.frame):
            raise ValueError('Interior glyph library must match the original source')
        origins = {(x, y) for _, x, y in spikes}
        self._cohorts = []
        seen = set()
        for model in filled.library.models:
            if model['native_size'] != 32:
                continue
            if any((x, y) not in origins for _, x, y in model['original_source_witnesses']):
                raise ValueError('Interior glyph models contain non-original teachers')
            teachers = tuple(filled._teachers(model))
            if len(teachers) >= 3 and teachers not in seen:
                self._cohorts.append(teachers)
                seen.add(teachers)
        self._body_cache, self._teacher_cache, self._model_cache, self._results = {}, {}, {}, {}

    def _body(self, key):
        if key not in self._body_cache:
            kind, x, y = key
            points = [(x+a, y+b) for a, b in (_oriented(kind, *p) for p in INTERIOR_POINTS)]
            positions = [self.frame.original_position(*p) for p in points]
            known = all(p is not None for p in positions) and len(set(positions)) >= 16
            self._body_cache[key] = tuple(self._pixels.pixel(*p) for p in positions) if known else None
        return self._body_cache[key]

    def _teacher(self, key):
        if key not in self._teacher_cache:
            kind, x, y = key
            body = self._body(key)
            corners = [self.frame.original_patch(x+a, y+b, 4) for a, b in
                       (_oriented(kind, *p) for p in ((4, 4), (28, 4)))]
            if body is None or any(p is None for p in corners):
                self._teacher_cache[key] = None
            else:
                background = _mean([v for patch in corners for v in patch])
                separation = hypot(*(a-b for a, b in zip(_mean(body), background)))
                self._teacher_cache[key] = body, background, separation
        return self._teacher_cache[key]

    def _model(self, teachers):
        if teachers not in self._model_cache:
            rows = [self._teacher(k) for k in teachers]
            if any(r is None for r in rows):
                self._model_cache[teachers] = None
            else:
                background = _mean([r[1] for r in rows])
                foreground = _mean([_mean(r[0]) for r in rows])
                samples = [tuple(sum(r[0][i][c]-r[1][c] for r in rows)/len(rows)
                                 for c in range(3)) for i in range(len(INTERIOR_POINTS))]
                self._model_cache[teachers] = dict(
                    teachers=teachers, background=background, foreground=foreground,
                    limit=.25*min(r[2] for r in rows),
                    pattern=_normalized([v for p in samples for v in p]),
                    # Paint variation belongs to the source sprite; its exact
                    # texture placement must not become object identity.
                    original_paints=tuple(sorted({rgb for r in rows for rgb in r[0]})),
                    paint_distance_cache={})
        return self._model_cache[teachers]

    def _paint_support(self, model, body):
        cache = model['paint_distance_cache']
        for rgb in set(body):
            if rgb not in cache:
                cache[rgb] = min(dist(rgb, paint) for paint in model['original_paints'])
        maximum = max(cache[rgb] for rgb in body)
        return dict(passed=maximum <= model['limit'],
                    max_original_paint_distance=maximum, original_RGB_limit=model['limit'],
                    original_paint_count=len(model['original_paints']),
                    every_interior_sample_source_supported=maximum <= model['limit'],
                    texture_placement_not_required=True)

    def _tip_support(self, key, model):
        kind, x, y = key
        poly = VERTICES[kind]
        tx, ty = x+poly[0][0], y+poly[0][1]
        ux = (poly[1][0]+poly[2][0])/2-poly[0][0]
        uy = (poly[1][1]+poly[2][1])/2-poly[0][1]
        length = hypot(ux, uy)
        ux, uy = ux/length, uy/length
        vx, vy = -uy, ux
        px, py = self.frame.pitch
        background, foreground = model['background'], model['foreground']
        vector = tuple(f-b for f, b in zip(foreground, background))
        energy = sum(v*v for v in vector)
        phases = []
        for dx in (0, -px, px):
            for dy in (0, -py, py):
                ax, ay = tx+dx, ty+dy
                points = [(ax+3*ux*px, ay+3*uy*py), (ax-3*ux*px, ay-3*uy*py),
                          (ax+3*vx*px, ay+3*vy*py), (ax-3*vx*px, ay-3*vy*py)]
                positions = [self.frame.original_position(*p) for p in points]
                values = [self._pixels.pixel(*p) if p is not None else None for p in positions]
                projections = [sum((v-b)*d for v, b, d in zip(rgb, background, vector))/energy
                               if rgb is not None and energy else None for rgb in values]
                known = all(p is not None for p in projections) and len(set(positions)) == 4
                labels = [p > .5 if p is not None else None for p in projections]
                passed = bool(known and labels[0] and sum(v is False for v in labels[1:]) >= 2)
                phases.append(dict(phase=(dx, dy), positions=positions, RGB=values,
                                   foreground_projection=projections, known=known, passed=passed))
        return dict(passed=any(p['passed'] for p in phases), phases=phases,
                    unknown=not any(p['known'] for p in phases), original_cohort_not_query_corners=True,
                    coherent_single_original_pixel_phase=True, physical_radius=3)

    def support(self, key):
        """Corroborate a finite original-locator hypothesis; never emit it."""
        key = tuple(key)
        if (len(key) != 3 or key[0] not in (3, 4, 5, 6) or
                any(isinstance(v, bool) or not isinstance(v, (int, float)) or not isfinite(v)
                    for v in key[1:])):
            raise ValueError('Interior glyph query needs full type3..6,x,y')
        if key not in self._results:
            self._results[key] = self._measure(key)
        return deepcopy(self._results[key])

    def _measure(self, key):
        kind, x, y = key
        proof = dict(key=key, passed=False, original_source_only=True,
                     no_new_teachers=True, no_retirement=True, native_hypothesis_unchanged=True)
        if not self.qualified:
            return {**proof, 'abstained': 'unqualified grid/world frame'}
        if not self.frame.rectangle_available(x, y, 32, 32, margin=4):
            return {**proof, 'unknown': True, 'abstained': 'incomplete original source footprint'}
        body = self._body(key)
        if body is None:
            return {**proof, 'unknown': True, 'abstained': 'insufficient independent original body pixels'}
        interior = [(x+a, y+b) for a, b in
                    (_oriented(kind, *p) for p in INTERIOR_POINTS)]
        if any(all(a <= px < a+w and b <= py < b+h for px, py in interior)
               for a, b, w, h in self._markers):
            return {**proof, 'abstained': 'original nongeometry covers the body'}
        exterior = [(x+a, y+b) for a, b in
                    (_oriented(kind, *p) for p in EXTERIOR_POINTS)]
        body_mean = _mean(body)
        exterior_pixels = None
        best = None
        triangle = rectangle = None
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
            pattern = _normalized([v-model['background'][c] for p in body for c, v in enumerate(p)])
            correlation = sum(a*b for a, b in zip(pattern, model['pattern']))
            if correlation >= .9:
                if best is not None and correlation <= best['correlation']:
                    continue
                # Some exterior must independently match ORIGINAL background.
                # Other foreground/unknown exterior pixels remain unexplained;
                # they are not relabelled empty or used as new teachers.
                if exterior_pixels is None:
                    positions = [self.frame.original_position(*p) for p in exterior]
                    exterior_pixels = [(p, self._pixels.pixel(*p)) for p in positions if p is not None]
                known_background = {p for p, rgb in exterior_pixels
                    if hypot(*(a-b for a, b in zip(rgb, model['background']))) <= model['limit']}
                if len(known_background) < 16:
                    continue
                # Geometry does not depend on the appearance cohort. A proven
                # failed conjunction cannot become true with another model.
                if triangle is None:
                    triangle = self.field.triangle(*key)
                    if any(e.unknown or e.support < 9 for e in triangle):
                        return {**proof, 'abstained': 'raw source triangle not closed',
                                'raw_triangle': [dict(support=e.support, unknown=e.unknown) for e in triangle]}
                    rectangle = self.field.rectangle(x, y, 32)
                    if all(e.support >= 9 and not e.unknown for e in rectangle):
                        return {**proof, 'abstained': 'competing complete source rectangle'}
                paint = self._paint_support(model, body)
                if not paint['passed']:
                    continue
                tip = self._tip_support(key, model)
                if not tip['passed']:
                    continue
                best = dict(correlation=correlation, mean_RGB_error=error,
                            mean_RGB_limit=model['limit'], original_teachers=teachers,
                            known_exterior_background_pixels=len(known_background),
                            source_paint=paint, source_tip=tip)
        if best is None:
            return {**proof, 'abstained': 'no independent source interior appearance',
                    'independent_body_samples': len(INTERIOR_POINTS)}
        return {**proof, 'passed': True, 'unknown': False, 'appearance': best,
                'raw_triangle': [dict(support=e.support, unknown=e.unknown,
                                      independent_source_positions=e.independent_source_positions)
                                 for e in triangle],
                'competing_rectangle': [dict(support=e.support, unknown=e.unknown) for e in rectangle],
                'interior_RGB_not_query_exterior': True,
                'independent_body_samples': len(INTERIOR_POINTS),
                'all_original_teachers_disjoint_from_query': True}
