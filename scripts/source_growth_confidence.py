"""Source-local confidence for independently NEW source terrain.

Original material calibration remains unchanged. These explicit functions only
qualify a separate sidecar or withhold new size/material growth; they do not
change original objects, retire geometry, build teachers or bind the scanner.
No global instrumentation or private imports. One edge memo belongs to one scan.
"""
from copy import deepcopy
from math import hypot, isfinite, sqrt
from statistics import median

from scripts.source_occupancy import footprint


def precision_aware_edge(field, first, second):
    """Original RGB edge support above quantization/physical-spacing uncertainty."""
    tx, ty = second[0]-first[0], second[1]-first[1]
    length = hypot(tx, ty)
    if not length:
        raise ValueError('A source edge needs two distinct endpoints')
    nx, ny = -ty/length, tx/length
    rows = []
    for i in range(12):
        q = .15+.7*i/11
        px, py = first[0]+q*tx, first[1]+q*ty
        native = [(px+off*nx, py+off*ny) for off in range(-4, 5)]
        if any(not (0 <= x < 800 and 0 <= y < 608) for x, y in native):
            return dict(support=0, unknown=True)
        points = [(int(field.room.x+x*field.room.width/800),
                   int(field.room.y+y*field.room.height/608)) for x, y in native]
        if any(not field.room.contains(x, y) for x, y in points):
            return dict(support=0, unknown=True)
        values = [field.image.pixel(*p) for p in points]
        spacing = [hypot(points[j+1][0]-points[j][0], points[j+1][1]-points[j][1]) for j in range(8)]
        derivatives = [tuple((values[j+1][c]-values[j][c])/spacing[j] for c in range(3))
                       if spacing[j] else (0., 0., 0.) for j in range(8)]
        gradient = tuple(median(derivatives[j][c] for j in (0, 1, 6, 7)) for c in range(3))
        departure = lambda d: sqrt(sum((d[c]-gradient[c])**2 for c in range(3)))
        reference = max(departure(derivatives[j]) for j in (0, 1, 6, 7))
        outer_error = max((1/spacing[j] if spacing[j] else 0.) for j in (0, 1, 6, 7))
        phases = {j-3.5 for j in (2, 3, 4, 5) if spacing[j] and
                  departure(derivatives[j]) > max(reference, sqrt(3)*(1/spacing[j]+outer_error))}
        rows.append((phases, points[4]))
    support = max(len({p for phases, p in rows if any(low <= v <= low+1 for v in phases)})
                  for low in (-1.5, -.5, .5))
    return dict(support=support, unknown=False)


def qualify_source_roles(field, selected, shadow_proof, original_detections, *, edge_memo=None):
    """Qualify shadow-role witnesses without changing the old expansion result.

    Callers retain the original labels/expanded roles/proofs for old consumers.
    ``edge_memo`` must be context-owned and validated before reuse; it is not a
    process-global cache. Original nonterrain excludes teaching neighborhoods,
    not the detected objects themselves. Newly emitted objects cannot teach.
    """
    anchors = [d.image_box for d in original_detections if d.type_id > 10 and d.type_id != 20]
    cache = {} if edge_memo is None else edge_memo
    accepted, qualified, observations = set(selected), [], []
    for role in shadow_proof:
        witnesses, rejected = [], []
        for row in role['original_source_geometry']:
            x, y = row['native']
            left, top = field.room.x+x*field.room.width/800, field.room.y+y*field.room.height/608
            right = field.room.x+(x+16)*field.room.width/800
            bottom = field.room.y+(y+16)*field.room.height/608
            if any(max(left, b.x-b.width/2) < min(right, b.right+b.width/2) and
                   max(top, b.y-b.height/2) < min(bottom, b.bottom+b.height/2) for b in anchors):
                rejected.append(dict(native=[x, y], reason='original nonterrain sprite/label neighborhood'))
                continue
            corners = [(x, y), (x+16, y), (x+16, y+16), (x, y+16)]
            faces = []
            for i in range(4):
                key = field, corners[i], corners[(i+1)%4]
                if key not in cache:
                    cache[key] = precision_aware_edge(field, key[1], key[2])
                faces.append(cache[key])
            if any(f['unknown'] or f['support'] < 9 for f in faces):
                rejected.append(dict(native=[x, y], reason='closure not significant above RGB quantization', faces=faces))
                continue
            witnesses.append({**row, 'precision_aware_faces': faces})
        independent = []
        for witness in witnesses:
            x, y = witness['native']
            if all(abs(x-r['native'][0]) >= 16 or abs(y-r['native'][1]) >= 16 for r in independent):
                independent.append(witness)
        passed = len(independent) >= 3
        observations.append(dict(label=role['label'], qualified_witnesses=independent,
                                 rejected_witnesses=rejected, passed=passed))
        if passed:
            accepted.add(role['label'])
            qualified.append({**role, 'original_source_geometry': independent})
    # Proofs are inspectable output, not a mutable route into source witnesses
    # or a context-owned edge memo.
    return accepted, deepcopy(qualified), deepcopy(observations)


class OriginalForegroundQuery:
    """Original sizing RGB evidence, queried without exact cluster-ID membership.

    A brighter part of one material may have a different nearest cluster. Retain
    the original foreground-fraction, dominance and mean-distance thresholds,
    using separately qualified foreground and original background roles. This is
    material corroboration for existing source hypotheses, NOT a shape detector.
    No newly emitted object teaches; source mutation invalidates cached evidence.
    """

    def __init__(self, field, approved, centers, tips, backs):
        self.field = field
        self.image, self.room = field.image, field.room
        self.data = self.image.data
        self.dimensions = self.image.width, self.image.height
        if not isinstance(self.data, bytes) or len(self.data) != self.image.width*self.image.height*3:
            raise ValueError('Original foreground needs complete immutable RGB bytes')
        if self.room.width <= 0 or self.room.height <= 0 or self.room.x < 0 or self.room.y < 0 or self.room.right > self.image.width or self.room.bottom > self.image.height:
            raise ValueError('Foreground source room must be inside the original image')
        colors = tuple(tuple(c) for c in centers)
        if any(len(c) != 3 or any(not isfinite(v) for v in c) for c in colors):
            raise ValueError('Foreground source centers need finite RGB triples')
        approved = frozenset(approved)
        background = {int(c) for c, count in tips.items() if count >= 3 and
                      count/(count+backs.get(c, backs.get(int(c), backs.get(str(c), 0)))) >= .75}
        self.foreground = tuple(colors[k] for k in sorted(approved))
        self.background = tuple(colors[k] for k in sorted(background))
        self.separation = (min(self.distance(f, b) for f in self.foreground for b in self.background)
                           if self.foreground and self.background else None)
        self.membership, self.results = {}, {}

    @staticmethod
    def distance(a, b):
        return sqrt(sum((x-y)**2 for x, y in zip(a, b)))

    def validate(self):
        if self.field.image is not self.image or self.field.room != self.room or self.image.data is not self.data or (self.image.width, self.image.height) != self.dimensions:
            raise ValueError('Original foreground source/frame changed')

    def support(self, x, y):
        self.validate()
        if not all(isinstance(v, int) and not isinstance(v, bool) for v in (x, y)):
            raise ValueError('Original foreground quarter origins must be integers')
        key = x, y
        if key in self.results:
            return deepcopy(self.results[key])
        if self.separation is None or self.separation <= 0 or not (0 <= x <= 784 and 0 <= y <= 592):
            return dict(passed=False, unknown=True, native=[x, y])
        values = []
        for py in range(y+4, y+12):
            for px in range(x+4, x+12):
                sx = int(self.room.x+(px+.5)*self.room.width/800)
                sy = int(self.room.y+(py+.5)*self.room.height/608)
                if not self.room.contains(sx, sy):
                    return dict(passed=False, unknown=True, native=[x, y])
                values.append(self.image.pixel(sx, sy))
        for rgb in values:
            if rgb not in self.membership:
                f = min(self.distance(rgb, c) for c in self.foreground)
                b = min(self.distance(rgb, c) for c in self.background)
                self.membership[rgb] = f < .5*b
        fraction = sum(self.membership[v] for v in values)/len(values)
        mean = tuple(sum(rgb[c] for rgb in values)/len(values) for c in range(3))
        error = min(self.distance(mean, c) for c in self.foreground)
        self.results[key] = dict(passed=fraction >= .95 and error <= .25*self.separation,
            unknown=False, native=[x, y], foreground_fraction=fraction, mean_error=error,
            unchanged_mean_limit=.25*self.separation, original_source_only=True,
            query_only_no_new_teacher=True)
        return deepcopy(self.results[key])


def bounded_texture_parents(key, room):
    """Query-only original32 frames that physically contain a new16 footprint."""
    t, x, y = key
    if t == 1:
        return [(x, y)]
    if t != 2:
        raise ValueError('Growth texture corroboration needs terrain type1 or2')
    if room is None or room.width <= 0 or room.height <= 0:
        return []
    parents = []
    for px in (x-16, x):
        for py in (y-16, y):
            if not (0 <= px <= 768 and 0 <= py <= 576):
                continue
            margins = (px*room.width/800, py*room.height/608,
                       (800-px-32)*room.width/800, (608-py-32)*room.height/608)
            if min(margins) >= 2:
                parents.append((px, py))
    return parents


def qualify_independent_growth(proposals, original_keys, *, sizing, sizing_retired,
                               joint_cells, phase_positive, calibrations, room,
                               original_texture_libraries=(), original_foreground_queries=()):
    """Return a subset of proposals plus explicit proofs; never retire originals.

    Every supplied calibration contains ORIGINAL source labels and separately
    approved role IDs. Libraries are the existing original-only full textures;
    they are queried, never extended. Producer keys, not generic detection kind,
    identify growth. Required old replacement coverage and phase gains survive.
    """
    proposals, existing = set(proposals), set(original_keys)
    sizing, phase_positive = set(sizing), set(phase_positive)
    joint = {(2, *p) for p in joint_cells}
    retired_pixels = {p for key in sizing_retired for p in footprint(key)}
    candidates = {key for key in (sizing | joint) & proposals if key[0] in (1, 2)
                  and key not in existing and key not in phase_positive
                  and not (footprint(key) & retired_pixels)}
    calibrations = tuple(calibrations)
    libraries = tuple(original_texture_libraries)
    foreground_queries = tuple(original_foreground_queries)
    held, proof = [], []
    for key in sorted(candidates):
        t, x, y = key
        size = 32 if t == 1 else 16
        cells = {(x+dx, y+dy) for dx in range(0, size, 16) for dy in range(0, size, 16)}
        role = any(all(p in s['labels'] and s['labels'][p] in s['approved'] for p in cells)
                   for s in calibrations)
        positive = ([] if role else [[query.support(*p) for p in sorted(cells)] for query in foreground_queries])
        source_positive = any(all(p['passed'] and not p.get('unknown', True) for p in group) for group in positive)
        parents = [] if role or source_positive else bounded_texture_parents(key, room)
        texture = [dict(parent32=[px, py], **lib.support(px, py))
                   for lib in libraries for px, py in parents] if not role and not source_positive else []
        accepted = role or source_positive or any(p['passed'] for p in texture)
        proof.append(dict(key=key, native_size=size, qualified_source_roles=role,
                          original_full_texture=texture, independent_growth=accepted,
                          existing_object_not_retired=True, texture_is_query_only=True,
                          sizing_origin=key in sizing, joint_material_origin=key in joint))
        if foreground_queries:
            proof[-1].update(original_foreground_evidence=positive, original_foreground_positive=source_positive)
        if not accepted:
            held.append(key)
    return proposals-set(held), deepcopy(dict(held=held, proof=proof))
