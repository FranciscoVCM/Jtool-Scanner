"""Unbound original-source evidence for partially occluded full32 glyphs.

Original detections locate source hypotheses, never supply reference answers.
Independent rectangle phases define definite/possible coverage before query
scores. Only definitely visible source RGB and original contours can support a
new glyph. Unknown masks/crops are not empty; this module never emits, removes
or moves scanner objects. No caller/default binding is implied by this API.
"""
from collections import OrderedDict, defaultdict
from copy import deepcopy
from dataclasses import asdict
from functools import lru_cache
from itertools import combinations
from math import ceil, dist, floor, sqrt
from jtool_scanner.spike_shape import VERTICES
from scripts.source_contours import SourceContours
from scripts.source_directional_body import SourceDirectionalBodyEvidence, _DirectedRGBField
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_glyph_prototypes import SourceGlyphLibrary
from scripts.source_interior_glyphs import INTERIOR_POINTS, _OriginalPaintIndex, _oriented
from scripts.source_sampling import SourceFrame

def intersects(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])

def centered(values):
    if not values:
        return None
    mean = tuple((sum((rgb[c] for rgb in values)) / len(values) for c in range(3)))
    vector = tuple((rgb[c] - mean[c] for rgb in values for c in range(3)))
    length = sqrt(sum((v * v for v in vector)))
    return None if length == 0 else tuple((v / length for v in vector))

def _mean_rectangle_signature(vectors):
    """Fit afresh; zip avoids indexed generators without changing sum order."""
    vectors = tuple(vectors)
    values = tuple(sum(column) / len(vectors) for column in zip(*vectors, strict=True))
    norm = sqrt(sum(v * v for v in values))
    return _SourceSignature(v / norm for v in values)


class _SourceSignature(tuple):
    """Internal immutable float values with their native tuple hash cached once.

    Value equality is unchanged, so independently refitted equal signatures keep
    the original bounded value-LRU reuse. This caches no fitted model or role.
    Only the hash representation changes; scalar arithmetic and order do not.
    """

    def __new__(cls, values):
        instance = tuple.__new__(cls, values)
        object.__setattr__(instance, '_cached_hash', None)
        return instance

    def __hash__(self):
        value = self._cached_hash
        if value is None:
            value = tuple.__hash__(self)
            object.__setattr__(self, '_cached_hash', value)
        return value

    def __setattr__(self, name, value):
        raise AttributeError('Source signature values and cached hash are immutable')


class SourcePartialVisibilityEvidence:
    """Frozen original-source context; an additional proof, never a veto.

    Parent and glyph pixels cannot fit their own witnesses. Models are rebuilt
    for each pruned neighborhood; only exact same-source measurements are shared.
    """

    def __init__(self, frame, original, *, source_grid):
        if not isinstance(frame, SourceFrame):
            raise ValueError('Partial visibility needs an immutable original SourceFrame')
        if not isinstance(source_grid, tuple) or len(source_grid) != 2 or any((type(v) is not int or v <= 0 for v in source_grid)):
            raise ValueError('Source grid must be a positive two-integer tuple')
        try:
            original = tuple(original)
        except TypeError as error:
            raise ValueError('Partial visibility needs original detection locators') from error
        if any((any((type(getattr(d, name, None)) is not int for name in ('type_id', 'x', 'y'))) or d.type_id < 1 for d in original)):
            raise ValueError('Original locators need positive integer types and native integer coordinates')
        self._source_grid = source_grid
        self.frame = frame
        self._original = deepcopy(tuple(original))
        self._rectangle_origins = tuple(sorted({(d.x, d.y) for d in self._original if d.type_id == 1}))
        self.markers = tuple(((d.x, d.y, d.x + 32, d.y + (8 if d.type_id == 13 else 32)) for d in self._original if d.type_id > 10))
        self.phases = tuple(((dx, dy) for dx in (0, -frame.pitch[0], frame.pitch[0]) for dy in (0, -frame.pitch[1], frame.pitch[1])))
        self.contours = SourceContours(frame.original_snapshot(), frame.extent, source_frame=frame,
                                       probe_cache_limit=32768)
        self.source_directed = _DirectedRGBField(self.frame)
        self.signature = lru_cache(maxsize=8192)(self.signature)
        self.faces = lru_cache(maxsize=8192)(self.faces)
        self.exact_dot = lru_cache(maxsize=200000)(self.exact_dot)
        self._rectangle_features, self._rectangle_pairs = OrderedDict(), OrderedDict()
        self._rectangle_feature_limit, self._rectangle_pair_limit = 8192, 200000
        self._next_rectangle_token = 0
        self._pair_hits = self._pair_misses = 0
        self._feature_evictions = self._pair_evictions = 0

    def footprint(self, x, y):
        px, py = self.frame.pitch
        return (x - 4 - px, y - 4 - py, x + 36 + px, y + 36 + py)

    def signature(self, x, y, inset):
        size = 32 - 2 * inset
        samples = [(i - 7.5, j - 7.5, self.frame.original_pixel(x + inset + (i + 0.5) * size / 16, y + inset + (j + 0.5) * size / 16)) for j in range(16) for i in range(16)]
        if any((rgb is None for _, _, rgb in samples)):
            return None
        means = tuple((sum((rgb[c] for _, _, rgb in samples)) / 256 for c in range(3)))
        dx = sum((a * a for a, b, rgb in samples))
        dy = sum((b * b for a, b, rgb in samples))
        sx = tuple((sum((a * rgb[c] for a, b, rgb in samples)) / dx for c in range(3)))
        sy = tuple((sum((b * rgb[c] for a, b, rgb in samples)) / dy for c in range(3)))
        residual = tuple((rgb[c] - means[c] - sx[c] * a - sy[c] * b for a, b, rgb in samples for c in range(3)))
        norm = sqrt(sum((v * v for v in residual)))
        return None if norm <= sqrt(768) else _SourceSignature(v / norm for v in residual)

    def faces(self, x, y):
        px, py = self.frame.pitch
        corners = ((x + 0.5 * px, y + 0.5 * py), (x + 32 - 0.5 * px, y + 0.5 * py), (x + 32 - 0.5 * px, y + 32 - 0.5 * py), (x + 0.5 * px, y + 32 - 0.5 * py))
        return (tuple(self.contours.rectangle(x, y, 32)), tuple((self.contours.edge(corners[i], corners[(i + 1) % 4]) for i in range(4))))

    @staticmethod
    def closed(faces):
        return all((f.support >= 9 and (not f.unknown) for f in faces))

    @staticmethod
    def adjacent(faces):
        good = [f.support >= 9 and (not f.unknown) for f in faces]
        return any((good[i] and good[(i + 1) % 4] for i in range(4)))

    def _record_rectangle_variants(self, variants):
        """Tokens identify exact immutable raw features, never a fitted role."""
        for variant in variants:
            key = variant['origin'], variant['phase']
            values = variant['physical'], variant['full'], variant['inner']
            if key in self._rectangle_features:
                previous, token = self._rectangle_features[key]
                assert values == previous, 'Immutable source rectangle features changed'
                self._rectangle_features.move_to_end(key)
            else:
                self._next_rectangle_token += 1
                token = self._next_rectangle_token
                self._rectangle_features[key] = values, token
                if len(self._rectangle_features) > self._rectangle_feature_limit:
                    self._rectangle_features.popitem(last=False)
                    self._feature_evictions += 1
            variant['_source_feature_token'] = token

    def _rectangle_pair_compatible(self, first, second):
        key = first['_source_feature_token'], second['_source_feature_token']
        if key in self._rectangle_pairs:
            self._pair_hits += 1
            self._rectangle_pairs.move_to_end(key)
            return self._rectangle_pairs[key]
        self._pair_misses += 1
        answer = (first['origin'] != second['origin']
                  and not intersects(first['physical'], second['physical'])
                  and sum(a*b for a, b in zip(first['full'], second['full'])) >= .9
                  and sum(a*b for a, b in zip(first['inner'], second['inner'])) >= .9)
        self._rectangle_pairs[key] = answer
        if len(self._rectangle_pairs) > self._rectangle_pair_limit:
            self._rectangle_pairs.popitem(last=False)
            self._pair_evictions += 1
        return answer

    def _measure_parent(self, parent, *, short_circuit=False):
        assert tuple(parent) in self._rectangle_origins
        x, y = parent
        fan = (x - 24, y - 24, x + 56, y + 56)
        px, py = self.frame.pitch
        queries = tuple((p for p in self._rectangle_origins if intersects((p[0], p[1], p[0] + 32, p[1] + 32), fan)))
        domains = ((fan[0] - 4 - px, fan[1] - 4 - py, fan[2] + 4 + px, fan[3] + 4 + py),) + tuple((self.footprint(*p) for p in queries))
        # Exclude the WHOLE candidate fan and every potential mask-query window
        # before fitting anything; a later successful query never becomes ink.
        outside = lambda box: not any((intersects(box, d) for d in domains))
        teacher_origins = tuple((p for p in self._rectangle_origins if outside(self.footprint(*p))))
        variants = []
        for a, b in teacher_origins:
            for dx, dy in self.phases:
                xx, yy = (a + dx, b + dy)
                if not self.frame.rectangle_available(xx, yy, 32, 32, margin=4):
                    continue
                if any((intersects((xx, yy, xx + 32, yy + 32), m) for m in self.markers)):
                    continue
                assert outside((xx - 4, yy - 4, xx + 36, yy + 36))
                if not any((self.closed(f) for f in self.faces(xx, yy))):
                    continue
                full, inner = (self.signature(xx, yy, 0), self.signature(xx, yy, 4))
                if full is None or inner is None:
                    continue
                physical = (floor(self.frame.extent.x + xx * self.frame.extent.width / 800), floor(self.frame.extent.y + yy * self.frame.extent.height / 608), ceil(self.frame.extent.x + (xx + 32) * self.frame.extent.width / 800), ceil(self.frame.extent.y + (yy + 32) * self.frame.extent.height / 608))
                variants.append(dict(origin=(a, b), phase=(dx, dy), physical=physical, full=full, inner=inner))
        self._record_rectangle_variants(variants)
        groups, seen = ([], set())
        dot = self.exact_dot
        for seed in variants:
            group = [seed]
            for other in variants:
                if all(self._rectangle_pair_compatible(other, p) for p in group):
                    group.append(other)
            key = tuple(sorted(((v['origin'], v['phase']) for v in group)))
            if len(group) < 3 or key in seen:
                continue
            seen.add(key)

            def mean(name):
                return _mean_rectangle_signature(v[name] for v in group)
            groups.append(dict(teachers=key, full=mean('full'), inner=mean('inner')))
        masks, rect_rows = ([], [])
        # Complete every source-supported rectangle phase before triangle scores.
        for a, b in queries:
            phases = []
            if not any((intersects((a, b, a + 32, b + 32), m) for m in self.markers)):
                for dx, dy in self.phases:
                    xx, yy = (a + dx, b + dy)
                    full, inner = (self.signature(xx, yy, 0), self.signature(xx, yy, 4))
                    if full is None or inner is None or (not any((self.adjacent(f) for f in self.faces(xx, yy)))):
                        continue
                    matches = tuple((g['teachers'] for g in groups if dot(full, g['full']) >= 0.9 and dot(inner, g['inner']) >= 0.9))
                    if matches:
                        phases.append(dict(phase=(dx, dy), box=(xx, yy, xx + 32, yy + 32), teachers=matches))
            box = None
            if phases:
                box = (max((p['box'][0] for p in phases)), max((p['box'][1] for p in phases)), min((p['box'][2] for p in phases)), min((p['box'][3] for p in phases)))
                masks.append(dict(origin=(a, b), intersection=box, phases=phases))
            rect_rows.append(dict(origin=(a, b), intersection=box, positive_phases=len(phases), unknown_NOT_empty=not phases))
        metadata = dict(parent=parent, fan=fan, exclusion_domains=domains, rectangle_query_origins=queries, independent_rectangle_origins=teacher_origins, qualified_rectangle_variants=len(variants), independent_rectangle_cohorts=[g['teachers'] for g in groups], rectangle_queries=rect_rows, masks=masks, mask_completed_BEFORE_spike_scores=True, NO_emission_OR_native_phase_change=True)
        if not any((tuple(m['origin']) == tuple(parent) for m in masks)):
            return {**metadata, 'rows': [], 'mini_rows': [], 'parent_unknown': True}
        original = tuple((d for d in self._original if not 3 <= d.type_id <= 6 or outside(self.footprint(d.x, d.y))))
        spikes = tuple(sorted({(d.type_id, d.x, d.y) for d in original if 3 <= d.type_id <= 6}))
        # The freshly pruned source still fits its OWN anchors/models. Share only
        # original raw contours, never a previous parent's library or teacher role.
        library = SourceGlyphLibrary(self.frame.original_snapshot(), self.frame.room, spikes,
            contour_field=self.contours, source_frame=self.frame, pixel_cache_limit=50000)
        filled = FilledGlyphEvidence(self.frame, original, source_library=library)
        field = SourceDirectionalBodyEvidence(filled, original, source_grid=(25, 19))
        # These caches contain source RGB geometry, not fitted teacher roles.
        field.field = self.contours
        field.directed_field = self.source_directed
        metadata['original_glyph_cohorts'] = field._cohorts
        assert all((outside(self.footprint(a, b)) for group in field._cohorts for _, a, b in group))
        session = _PartialVisibilitySession(self.frame, field, masks, self.markers)
        origins = defaultdict(list)
        # A wall's face does not determine a partly hidden spike's direction.
        for depth in (8, 16, 24):
            for offset in range(-24, 32, 8):
                for face, keys in (('top', [(t, x + offset, y + depth - 32) for t in (3, 4, 5, 6)]), ('bottom', [(t, x + offset, y + 32 - depth) for t in (3, 4, 5, 6)]), ('left', [(t, x + depth - 32, y + offset) for t in (3, 4, 5, 6)]), ('right', [(t, x + 32 - depth, y + offset) for t in (3, 4, 5, 6)])):
                    for key in keys:
                        if 0 <= key[1] <= 768 and 0 <= key[2] <= 576:
                            origins[key].append(dict(face=face, depth=depth, tangent_offset=offset))
        rows = [dict(key=k, seed=origins[k], phases=session.support(k, 32, True, self.phases,
            short_circuit=short_circuit)) for k in sorted(origins)]
        for row in rows:
            row['provisional'] = any((p['passed'] for p in row['phases']))
        challenges = {(t, a, b) for row in rows if row['provisional'] for _, xx, yy in (row['key'],) for t in (3, 4, 5, 6) for a in range(xx - 8, xx + 33, 8) for b in range(yy - 8, yy + 33, 8) if 0 <= a <= 784 and 0 <= b <= 592}
        minis = [dict(key=k, phases=session.support(k, 16, False, self.phases,
            short_circuit=short_circuit)) for k in sorted(challenges)]
        return {**metadata, 'rows': rows, 'mini_rows': minis, 'parent_unknown': False}

    @staticmethod
    def exact_dot(a, b):
        return sum((u * v for u, v in zip(a, b)))

    @property
    def rectangle_origins(self):
        """Immutable ORIGINAL full-rectangle locators, not source-positive labels."""
        return self._rectangle_origins

    def support_parent(self, parent, *, short_circuit=False):
        """Isolated evidence for one original parent; never an object emitter.

        Full diagnostics are the default. Explicit True defers unused negative
        work only; every positive key keeps its entire original nine-phase proof.
        Compact/unsupported grids remain unknown before fitting any models.
        """
        if not isinstance(short_circuit, bool):
            raise ValueError('Partial diagnostic short-circuit mode must be a boolean')
        try:
            parent = tuple(parent)
        except TypeError as error:
            raise ValueError('Parent must be an original native integer x,y pair') from error
        if len(parent) != 2 or any((type(v) is not int for v in parent)) or parent not in self._rectangle_origins:
            raise ValueError('Parent must be an original native integer x,y pair')
        if self._source_grid != (25, 19):
            return dict(qualified=False, unknown=True, evidence=None, reason='unsupported original source grid; not empty')
        return dict(qualified=True, evidence=deepcopy(self._measure_parent(parent,
            **({'short_circuit': True} if short_circuit else {}))))

    def cache_diagnostics(self):
        """Source-local exact measurements only, never shared model/teacher roles."""
        return {**{name: getattr(self, name).cache_info()._asdict() for name in ('signature', 'faces', 'exact_dot')},
            'source_raw_edges': len(self.contours._edges), 'source_directed_edges': len(self.source_directed.edges),
            'source_RGB_gradients': len(self.source_directed.gradients), 'no_shared_fitted_models_OR_teacher_roles': True,
            'rectangle_pair_features': len(self._rectangle_features), 'rectangle_pair_booleans': len(self._rectangle_pairs),
            'rectangle_pair_hits': self._pair_hits, 'rectangle_pair_misses': self._pair_misses,
            'rectangle_feature_evictions': self._feature_evictions, 'rectangle_pair_evictions': self._pair_evictions,
            'rectangle_source_tokens': self._next_rectangle_token,
            'physical_probe_cache_hits': self.contours.probe_cache_hits,
            'physical_probe_cache_misses': self.contours.probe_cache_misses,
            'physical_probe_cache_peak': self.contours.probe_cache_peak,
            'physical_probe_cache_limit': self.contours.probe_cache_limit}

class _PartialVisibilitySession:
    """Intersection is hidden; envelope-minus-intersection stays UNKNOWN."""

    def __init__(self, frame, field, masks, markers):
        self.definite = tuple((tuple(m['intersection']) for m in masks))
        envelopes = []
        for m in masks:
            boxes = [p['box'] for p in m['phases']]
            envelopes.append((min((b[0] for b in boxes)), min((b[1] for b in boxes)), max((b[2] for b in boxes)), max((b[3] for b in boxes))))
        self.possible = tuple(envelopes)
        self.frame, self.field, self.masks, self.markers = (frame, field, [dict(intersection=b) for b in self.possible], markers)
        self.paint_cache = {}

    def covered(self, x, y):
        # A line on a wall perimeter is not independently visible glyph ink.
        return any((a <= x <= b and c <= y <= d for a, c, b, d in self.possible))

    def segments(self, a, b):
        breaks = {0.0, 1.0}
        vx, vy = (b[0] - a[0], b[1] - a[1])
        for m in self.masks:
            x0, y0, x1, y1 = m['intersection']
            for origin, delta, bounds in ((a[0], vx, (x0, x1)), (a[1], vy, (y0, y1))):
                if delta:
                    breaks.update((t for bound in bounds if 0 < (t := ((bound - origin) / delta)) < 1))
        visible = []
        ordered = sorted(breaks)
        for u, v in zip(ordered, ordered[1:]):
            middle = (u + v) / 2
            if self.covered(a[0] + middle * vx, a[1] + middle * vy):
                continue
            if visible and abs(visible[-1][1] - u) < 1e-10:
                visible[-1] = (visible[-1][0], v)
            else:
                visible.append((u, v))
        return [(tuple((a[i] + u * (b[i] - a[i]) for i in (0, 1))), tuple((a[i] + v * (b[i] - a[i]) for i in (0, 1)))) for u, v in visible]

    def eligibility(self, key, size, partial):
        t, x, y = key
        points = [(x + a * size / 32, y + b * size / 32) for a, b in (_oriented(t, *p) for p in INTERIOR_POINTS)]
        definite = tuple((i for i, (px, py) in enumerate(points) if any((a <= px < b and c <= py < d for a, c, b, d in self.definite))))
        visible = tuple((i for i, p in enumerate(points) if not self.covered(*p)))
        uncertain = tuple((i for i in range(len(points)) if i not in definite and i not in visible))
        positions = [self.frame.original_position(*points[i]) for i in visible]
        unique = len(set((p for p in positions if p is not None)))
        known = self.frame.rectangle_available(x, y, size, size, margin=4) and None not in positions
        actor = bool(visible) and any((all((a <= points[i][0] < b and c <= points[i][1] < d for i in visible)) for a, c, b, d in self.markers))
        assert len(definite) + len(uncertain) + len(visible) == len(points)
        return dict(indices=visible, unique=unique, definitely_hidden_indices=definite, uncertain_indices=uncertain, visible_samples=len(visible), hidden=len(definite), uncertain=len(uncertain), known=known, actor=actor, eligible=known and unique >= 16 and (not actor) and (not partial or bool(definite)), uncertainty_is_NOT_foreground_OR_background_evidence=True)

    def geometry(self, key, size, *, short_circuit=False):
        t, x, y = key
        poly = [(x + a * size / 32, y + b * size / 32) for a, b in VERTICES[t]]
        visible = [self.segments(a, b) for a, b in zip(poly, poly[1:] + poly[:1])]
        if short_circuit and sum(bool(segments) for segments in visible) < 2:
            return dict(passed=False, diagnostics_deferred=True,
                reason='insufficient observable ORIGINAL edges; hidden is unknown, not empty')
        edges = []
        for original_segments in visible:
            segments = []
            for p, q in original_segments:
                raw = self.field.field.edge(p, q)
                if short_circuit and (raw.support < 9 or raw.unknown):
                    return dict(passed=False, diagnostics_deferred=True,
                        reason='required original raw segment failed; unused work deferred',
                        first_failed_segment=dict(first=p, last=q, raw=asdict(raw)),
                        source_unknown_NOT_empty=raw.unknown)
                directed = self.field.directed_field.directed(p, q)
                if short_circuit and directed < 9:
                    return dict(passed=False, diagnostics_deferred=True,
                        reason='required original directed segment failed; unused work deferred',
                        first_failed_segment=dict(first=p, last=q, raw=asdict(raw), directed=directed))
                segments.append(dict(first=p, last=q, directed=directed, raw=asdict(raw), passed=raw.support >= 9 and (not raw.unknown) and (directed >= 9)))
            edges.append(dict(segments=segments, fully_unobservable_under_source_mask_uncertainty=not segments, passed=bool(segments) and all((p['passed'] for p in segments))))
        exposed = [e for e in edges if not e['fully_unobservable_under_source_mask_uncertainty']]
        proof = dict(edges=edges, passed=len(exposed) >= 2 and all((e['passed'] for e in exposed)))
        proof['only_definitely_visible_ORIGINAL_segments_measured'] = True
        proof['no_artificial_mask_boundary_edge'] = True
        return proof

    def paint(self, triple, indices, values):
        cache_key = (triple, indices)
        if cache_key not in self.paint_cache:
            samples = [tuple((self.field._body(t)[i] for i in indices)) for t in triple]
            means = [tuple((sum((rgb[c] for rgb in v)) / len(v) for c in range(3))) for v in samples]
            backs = [self.field._teacher(t)[1] for t in triple]
            self.paint_cache[cache_key] = dict(index=_OriginalPaintIndex(tuple(sorted({rgb for v in samples for rgb in v}))), limit=0.25 * min((dist(a, b) for a, b in zip(means, backs))), mean=tuple((sum((v[c] for v in means)) / 3 for c in range(3))))
        model = self.paint_cache[cache_key]
        maximum = max((model['index'].distance(rgb) for rgb in set(values)))
        mean = tuple((sum((rgb[c] for rgb in values)) / len(values) for c in range(3)))
        error = dist(mean, model['mean'])
        return dict(passed=model['limit'] > 0 and maximum <= model['limit'] and (error <= model['limit']), maximum_original_paint_distance=maximum, mean_RGB_error=error, original_RGB_limit=model['limit'])

    def body(self, key, indices):
        body = self.field._body(key)
        if body is None:
            return dict(passed=False, unknown=True)
        values = tuple((body[i] for i in indices))
        query = centered(values)
        if query is None:
            return dict(passed=False, reason='uninformative visible source')
        t, x, y = key
        for group in self.field._cohorts:
            teachers = tuple((k for k in group if k[0] == t and (abs(k[1] - x) >= 32 or abs(k[2] - y) >= 32)))
            vectors = {k: centered([self.field._body(k)[i] for i in indices]) for k in teachers}
            possible = [k for k in teachers if vectors[k] is not None]
            scores = {k: sum((a * b for a, b in zip(query, vectors[k]))) for k in possible}
            mutual = {(a, b): sum((u * v for u, v in zip(vectors[a], vectors[b]))) for a, b in combinations(possible, 2) if abs(a[1] - b[1]) >= 32 or abs(a[2] - b[2]) >= 32}
            for triple in combinations(possible, 3):
                if min((scores[k] for k in triple)) < 0.9 or not all((mutual.get((a, b), -1) >= 0.9 for a, b in combinations(triple, 2))):
                    continue
                paint = self.paint(triple, indices, values)
                if paint['passed']:
                    return dict(passed=True, teachers=triple, minimum_query_correlation=min((scores[k] for k in triple)), paint=paint)
        return dict(passed=False, reason='no independent complete original-source body/paint proof')

    def support(self, key, size, partial, phases, *, short_circuit=False):
        result = self._support(key, size, partial, phases, short_circuit=short_circuit)
        if short_circuit and any(phase['passed'] for phase in result):
            return self._support(key, size, partial, phases, short_circuit=False)
        return result

    def _support(self, key, size, partial, phases, *, short_circuit):
        t, x, y = key
        out = []
        for dx, dy in phases:
            sampled = (t, x + dx, y + dy)
            eligible = self.eligibility(sampled, size, partial)
            geometry = self.geometry(sampled, size, short_circuit=short_circuit) if eligible['eligible'] else None
            body = self.body(sampled, eligible['indices']) if size == 32 and geometry and geometry['passed'] else None
            out.append(dict(phase=(dx, dy), eligibility=eligible, geometry=geometry, body=body, passed=bool(geometry and geometry['passed'] and (size == 16 or (body and body['passed']))), geometry_only_NOT_mini_identity=size == 16))
        return out
