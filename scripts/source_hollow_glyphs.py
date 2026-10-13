"""Read-only, source-local full-size hollow triangle evidence.

Original detections locate hypotheses, never supply their directions as truth.
Models require three disjoint, raw-source-verified teachers. RGB identity,
localized directed edges, hollow interiors and inward foreground ownership
must agree at one source-pixel-bounded phase. Queries cannot become teachers.
Closed empty gaps explained by three independently verified opposing glyphs
are not objects. This module does not emit or remove scanner detections.
"""
from __future__ import annotations

from copy import deepcopy
from collections import OrderedDict
from math import dist, hypot
from statistics import median

from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import SourceGlyphEvidence, _bounds, _contains, _fits


MATERIAL_COHERENCE_FRACTION = .1


class _OriginalHollowLibrary:
    """Only raw full32 teachers; no unused filled/mini/signature learning."""
    def __init__(self, frame, spikes, pixel_cache_limit, source_field=None):
        if not isinstance(pixel_cache_limit, int) or isinstance(pixel_cache_limit, bool) or pixel_cache_limit < 0:
            raise ValueError('Pixel cache limit must be a nonnegative integer')
        self.source_frame = frame
        self.pitch = frame.pitch
        if source_field is not None and (source_field.room != frame.extent
                or not frame.matches_source(source_field.image, frame.room)):
            raise ValueError('Shared source field must match the original frame')
        self.raw = source_field if source_field is not None else SourceGlyphEvidence(
            frame.original_snapshot(), frame.extent, source_frame=frame)
        self.anchors = []
        self._pixel_cache_limit = pixel_cache_limit
        self._pixels = OrderedDict()
        positions = sorted({(x, y) for t, x, y in spikes if 3 <= t <= 6})
        for x, y in positions:
            if not frame.rectangle_available(x, y, 32, 32, margin=4):
                continue
            for direction in VERTICES:
                key = direction, x, y
                if self.raw.owner(*key) is not None:
                    self.anchors.append(dict(key=key, size=32, independent_source_proof='raw'))
        self.anchors.sort(key=lambda a: a['key'])

    def pixel(self, x, y):
        if not self._pixel_cache_limit:
            return self.source_frame.pixel(x, y)
        key = x, y
        if key in self._pixels:
            self._pixels.move_to_end(key)
            return self._pixels[key]
        answer = self.source_frame.pixel(x, y)
        self._pixels[key] = answer
        if len(self._pixels) > self._pixel_cache_limit:
            self._pixels.popitem(last=False)
        return answer


class HollowGlyphEvidence:
    """A scan-local evidence snapshot, optionally with capture-frame coverage.

    ``library`` and ``original_spikes`` must be frozen before proposals. A
    SourceFrame-backed library maps raw ink to physical source pixels; filtered
    samples outside original support are unknown, not repeated-edge votes.
    Signed-edge memoization includes its inward orientation.
    """
    @classmethod
    def from_frame(cls, frame, original_spikes, *, pixel_cache_limit=50000, source_field=None):
        """Reuse a frozen frame without learning unrelated sprite signatures."""
        spikes = tuple(sorted(set(map(tuple, original_spikes))))
        if any(len(key) != 3 or not 3 <= key[0] <= 10 for key in spikes):
            raise ValueError('Original spike locators must be type3..10,x,y triples')
        return cls(_OriginalHollowLibrary(frame, spikes, pixel_cache_limit, source_field), spikes)

    def __init__(self, library, original_spikes):
        self.library = library
        self.frame = library.source_frame
        self.original_spikes = tuple(sorted(set(map(tuple, original_spikes))))
        self.gradients, self.edges, self.cores = {}, {}, {}
        self.ink_edges, self.raw_ink_edges, self.owned_edges = {}, {}, {}
        self.results, self.qualified_results = {}, {}
        full_origins = {(x, y) for t, x, y in self.original_spikes if 3 <= t <= 6}
        nominal = [(tuple(anchor['key']), library.raw.owner(*anchor['key']))
                   for anchor in library.anchors
                   if anchor['size'] == 32 and anchor['independent_source_proof'] == 'raw'
                   and tuple(anchor['key'][1:]) in full_origins]
        self.models = self._models(nominal)
        self.nominal_model_count = len(self.models)
        self.inset_original_owners = self._inset_owners()
        inset = self._models(list(self.inset_original_owners.items()))
        self.inset_model_count = len(inset)
        self.models.extend(inset)
        self.owned_models = {}
        for index, model in enumerate(self.models):
            teachers = tuple(key for key in model['independent_teachers'] if self.owns_at(key, index))
            self.owned_models[index] = teachers if len(teachers) >= 3 else ()

    def _position(self, x, y):
        if self.frame is not None:
            return self.frame.original_position(x, y)
        if not (0 <= x < 800 and 0 <= y < 608):
            return None
        room = self.library.raw.room
        return int(room.x + x * room.width / 800), int(room.y + y * room.height / 608)

    def _inset_owners(self):
        owners = {}
        ix, iy = .5 * self.library.pitch[0], .5 * self.library.pitch[1]
        for x, y in sorted({(x, y) for t, x, y in self.original_spikes if 3 <= t <= 6}):
            if not (0 <= x <= 768 and 0 <= y <= 576):
                continue
            if self.frame is not None and not self.frame.rectangle_available(x, y, 32, 32, margin=4):
                continue
            for direction in VERTICES:
                key = direction, x, y
                if self.library.raw.owner(*key) is not None:
                    continue
                nominal = [(x + u, y + v) for u, v in VERTICES[direction]]
                poly = [(x + 16 + (u - 16) * (32 - 2 * ix) / 32,
                         y + 16 + (v - 16) * (32 - 2 * iy) / 32)
                        for u, v in VERTICES[direction]]
                faces = [self.library.raw.raw.edge(a, b) for a, b in zip(poly, poly[1:] + poly[:1])]
                if any(count < 9 or unknown for count, unknown in faces):
                    continue
                corners = [(x, y), (x + 32, y), (x + 32, y + 32), (x, y + 32)]
                rectangle = [self.library.raw.raw.edge(a, b)
                             for a, b in zip(corners, corners[1:] + corners[:1])]
                if all(count >= 9 and not unknown for count, unknown in rectangle):
                    continue
                points = [(x + 4, y + 4), (x + 28, y + 4), (x + 28, y + 28), (x + 4, y + 28)]
                exterior = [p for p in points if not _contains(nominal, *p)]
                if len(exterior) != 2:
                    continue
                patches = [self.library.raw.sample(*p, size=4) for p in exterior]
                if any(p is None for p in patches):
                    continue
                models, bodies = [_bounds(p) for p in patches], []
                for weights in ((.25, .5, .25), (.25, .25, .5), (.5, .25, .25), (1/3, 1/3, 1/3)):
                    cx = sum(w * p[0] for w, p in zip(weights, nominal))
                    cy = sum(w * p[1] for w, p in zip(weights, nominal))
                    values = self.library.raw.sample(cx, cy)
                    if values is None:
                        break
                    bodies.append(not any(all(_fits(rgb, m) for rgb in values) for m in models))
                if len(bodies) == 4 and all(bodies):
                    owners[key] = dict(poly=nominal, source_exterior_corners=exterior,
                                       joint_inset_faces=faces, unchanged_body_proof=bodies)
        return owners

    def band(self, a, b, width):
        tx, ty = b[0] - a[0], b[1] - a[1]
        length = hypot(tx, ty)
        nx, ny = -ty / length, tx / length
        for i in range(12):
            q = .15 + .7 * i / 11
            px, py = a[0] + q * tx, a[1] + q * ty
            points = [(px + off * nx, py + off * ny) for off in range(-width, width + 1)]
            if any(not (0 <= x < 800 and 0 <= y < 608) for x, y in points):
                yield None, None
                continue
            values = [self.library.pixel(x, y) for x, y in points]
            position = self._position(px, py)
            yield ((position, values) if position is not None and all(v is not None for v in values)
                   else (None, None))

    def core(self, key, model):
        if key not in self.cores:
            t, x, y = key
            cx = x + sum(u for u, v in VERTICES[t]) / 3
            cy = y + sum(v for u, v in VERTICES[t]) / 3
            self.cores[key] = [self.library.pixel(cx + dx, cy + dy)
                               for dx in (-.5, .5) for dy in (-.5, .5)]
        values = self.cores[key]
        if any(v is None for v in values):
            return 0
        vector = tuple(f-b for f, b in zip(model['foreground'], model['background']))
        energy = sum(v*v for v in vector)
        if energy <= 0:
            return 0
        quantum = sum(abs(v) for v in vector) / energy
        def background_role(rgb):
            # Nearest-to-background alone also accepts a filled core on the
            # *far* side of the learned background (e.g. brighter gray). Keep
            # the original material-coherence allowance and RGB quantization;
            # neither game colors nor luminance-only thresholds define roles.
            projection = sum((v-b)*d for v, b, d in zip(rgb, model['background'], vector)) / energy
            return (dist(rgb, model['background']) < dist(rgb, model['foreground'])
                    and projection >= -MATERIAL_COHERENCE_FRACTION-quantum)
        return sum(background_role(v) for v in values) / 4

    def _models(self, owners):
        teachers = []
        for key, proof in owners:
            if proof is None:
                continue
            patches = [self.library.raw.sample(*p, size=4) for p in proof['source_exterior_corners']]
            if any(p is None for p in patches):
                continue
            background = tuple(median([rgb[c] for patch in patches for rgb in patch]) for c in range(3))
            samples = []
            for end in proof['poly'][1:]:
                for _, values in self.band(proof['poly'][0], end, 2):
                    if values is not None:
                        samples.append(max(values, key=lambda rgb: dist(rgb, background)))
            if len(samples) != 24:
                continue
            foreground = tuple(median([rgb[c] for rgb in samples]) for c in range(3))
            separation = dist(foreground, background)
            if separation > 0:
                teachers.append(dict(key=key, foreground=foreground, background=background,
                                     separation=separation))
        def matches(a, b):
            return max(dist(a['foreground'], b['foreground']), dist(a['background'], b['background'])) <= (
                MATERIAL_COHERENCE_FRACTION * min(a['separation'], b['separation']))
        models, seen = [], set()
        for seed in teachers:
            group = []
            for row in sorted([r for r in teachers if matches(seed, r)], key=lambda r: r['key']):
                if all(matches(row, other) for other in group):
                    group.append(row)
            identity = tuple(r['key'] for r in group)
            if identity in seen or len({(k[1] // 32, k[2] // 32) for k in identity}) < 3:
                continue
            seen.add(identity)
            model = dict(teachers=identity,
                         foreground=tuple(median([r['foreground'][c] for r in group]) for c in range(3)),
                         background=tuple(median([r['background'][c] for r in group]) for c in range(3)))
            hollow = [key for key in identity if self.core(key, model) >= .95]
            independent = []
            for key in hollow:
                if all(max(key[1], other[1]) >= min(key[1] + 32, other[1] + 32)
                       or max(key[2], other[2]) >= min(key[2] + 32, other[2] + 32) for other in independent):
                    independent.append(key)
            if len(independent) >= 3:
                models.append(dict(model, core_teachers=tuple(hollow), independent_teachers=tuple(independent)))
        return models

    def gradient(self, x, y):
        key = x, y
        if key not in self.gradients:
            values = [self.library.pixel(px, py) for px, py in
                      ((x+1, y), (x-1, y), (x, y+1), (x, y-1))]
            if any(v is None for v in values):
                self.gradients[key] = None
            else:
                right, left, below, above = values
                self.gradients[key] = (tuple((a-b)/2 for a, b in zip(right, left)),
                                       tuple((a-b)/2 for a, b in zip(below, above)))
        return self.gradients[key]

    def directed(self, a, b):
        key = a, b
        if key in self.edges:
            return self.edges[key]
        tx, ty = b[0]-a[0], b[1]-a[1]
        length = hypot(tx, ty)
        nx, ny = -ty/length, tx/length
        found = set()
        for i in range(12):
            q = .15 + .7*i/11
            px, py = a[0]+q*tx, a[1]+q*ty
            position = self._position(px, py)
            if position is None:
                continue
            for off in (-2, -1, 0, 1, 2):
                sx, sy = px+off*nx, py+off*ny
                if not (1 <= sx < 799 and 1 <= sy < 607):
                    continue
                gradient = self.gradient(sx, sy)
                if gradient is None:
                    continue
                gx, gy = gradient
                energy = sum(v*v+w*w for v, w in zip(gx, gy))
                normal = sum((v*nx+w*ny)**2 for v, w in zip(gx, gy))
                if energy > 1.5 and normal >= energy * .95**2:
                    found.add(position)
                    break
        self.edges[key] = len(found)
        return len(found)

    def ink_hits(self, a, b, index):
        key = a, b, index
        if key in self.ink_edges:
            normalized = self.ink_edges[key]
        else:
            model = self.models[index]
            found = set()
            normalized = None
            for i, (position, values) in enumerate(self.band(a, b, 2)):
                if values is not None and any(dist(rgb, model['foreground']) < dist(rgb, model['background'])
                                              for rgb in values):
                    found.add(position)
                if len(found) + 11 - i < 9:
                    break
            else:
                normalized = len(found)
            self.ink_edges[key] = normalized
        if normalized is not None:
            return normalized
        if key in self.raw_ink_edges:
            return self.raw_ink_edges[key]
        model = self.models[index]
        tx, ty = b[0]-a[0], b[1]-a[1]
        length = hypot(tx, ty)
        nx, ny = -ty/length, tx/length
        found, answer = set(), None
        for i in range(12):
            q = .15 + .7*i/11
            px, py = a[0]+q*tx, a[1]+q*ty
            position = self._position(px, py)
            if position is not None:
                for off in (-2, -1, 0, 1, 2):
                    x, y = px+off*nx, py+off*ny
                    source_position = self._position(x, y)
                    if source_position is None:
                        continue
                    rgb = (self.frame.original_pixel(x, y) if self.frame is not None
                           else self.library.raw.image.pixel(*source_position))
                    if dist(rgb, model['foreground']) < dist(rgb, model['background']):
                        found.add(position)
                        break
            if len(found) + 11 - i < 9:
                break
        else:
            answer = len(found)
        self.raw_ink_edges[key] = answer
        return answer

    def owns_at(self, key, index):
        t, x, y = key
        poly = [(x+u, y+v) for u, v in VERTICES[t]]
        cx, cy = sum(p[0] for p in poly)/3, sum(p[1] for p in poly)/3
        model = self.models[index]
        vector = tuple(f-b for f, b in zip(model['foreground'], model['background']))
        energy = sum(v*v for v in vector)
        if energy <= 0:
            return False
        error = sum(abs(v) for v in vector)/energy
        def projection(rgb):
            return sum((a-b)*v for a, b, v in zip(rgb, model['background'], vector))/energy
        for a, b in zip(poly, poly[1:]+poly[:1]):
            tx, ty = b[0]-a[0], b[1]-a[1]
            length = hypot(tx, ty)
            nx, ny = -ty/length, tx/length
            if (cx-a[0])*nx + (cy-a[1])*ny < 0:
                nx, ny = -nx, -ny
            cache_key = a, b, index, nx, ny
            if cache_key not in self.owned_edges:
                sites = set()
                for i in range(12):
                    q = .15 + .7*i/11
                    px, py = a[0]+q*tx, a[1]+q*ty
                    positions = [(px+off*nx, py+off*ny) for off in (-4, -3, -2, -1, 1, 2, 3, 4)]
                    if any(not (0 <= sx < 800 and 0 <= sy < 608) for sx, sy in positions):
                        continue
                    values = [self.library.pixel(sx, sy) for sx, sy in positions]
                    position = self._position(px, py)
                    if position is None or any(v is None for v in values):
                        continue
                    outside = sum(projection(rgb) for rgb in reversed(values[:4]))/4
                    inside = sum(projection(rgb) for rgb in values[4:])/4
                    if inside-outside > error:
                        sites.add(position)
                self.owned_edges[cache_key] = len(sites)
            if self.owned_edges[cache_key] >= 9:
                return True
        return False

    def _base_support(self, key):
        key = tuple(key)
        if key in self.results:
            return self.results[key]
        t, x, y = key
        if t not in VERTICES:
            raise ValueError('Only full32 glyphs are qualified')
        passed = []
        if self.models and 0 <= x <= 768 and 0 <= y <= 576:
            for dx in (0, -self.library.pitch[0], self.library.pitch[0]):
                for dy in (0, -self.library.pitch[1], self.library.pitch[1]):
                    if not (0 <= x+dx <= 768 and 0 <= y+dy <= 576):
                        continue
                    poly = [(x+dx+u, y+dy+v) for u, v in VERTICES[t]]
                    edges = list(zip(poly, poly[1:]+poly[:1]))
                    eligible = []
                    for index, model in enumerate(self.models):
                        if not self.owned_models[index] or self.core((t, x+dx, y+dy), model) < .95:
                            continue
                        ink = []
                        for a, b in edges:
                            count = self.ink_hits(a, b, index)
                            if count is None:
                                break
                            ink.append(count)
                        if len(ink) == 3 and min(ink) >= 9:
                            eligible.append((index, model, ink))
                    if not eligible:
                        continue
                    direction = [self.directed(a, b) for a, b in edges]
                    if min(direction) < 9:
                        continue
                    for index, model, ink in eligible:
                        if self.owns_at((t, x+dx, y+dy), index):
                            passed.append(dict(phase=(dx, dy), direction=direction, ink=ink,
                                               original_teachers=model['independent_teachers']))
        answer = dict(passed=bool(passed), proof=passed)
        self.results[key] = answer
        return answer

    @staticmethod
    def neighbors(key):
        t, x, y = key
        return {3: ((6, x-16, y), (6, x+16, y), (6, x, y+32)),
                6: ((3, x-16, y), (3, x+16, y), (3, x, y-32)),
                4: ((5, x, y-16), (5, x, y+16), (5, x-32, y)),
                5: ((4, x, y-16), (4, x, y+16), (4, x+32, y))}[t]

    def support(self, key):
        key = tuple(key)
        if key not in self.qualified_results:
            original = self._base_support(key)
            proof, explained = list(original['proof']), []
            if proof:
                peers = [self._base_support(neighbor) for neighbor in self.neighbors(key)]
                if all(peer['passed'] for peer in peers):
                    def identity(p):
                        return p['original_teachers']
                    common = {identity(p) for p in proof}
                    for peer in peers:
                        common &= {identity(p) for p in peer['proof']}
                    if common:
                        explained = [p for p in proof if identity(p) in common]
                        proof = [p for p in proof if identity(p) not in common]
            self.qualified_results[key] = dict(passed=bool(proof), proof=proof,
                source_neighbor_explained_proof=explained, original_source_neighbor_keys=self.neighbors(key),
                read_only=True, original_source_witnesses_only=True,
                capture_coverage_checked=self.frame is not None)
        return deepcopy(self.qualified_results[key])
