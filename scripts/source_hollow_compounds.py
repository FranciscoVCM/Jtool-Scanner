"""Source-only competing boundaries for additional hollow full-spike queries.

New full boundaries may already be explained by independently qualified minis
and original solids. This is not blanket overlap deletion: original geometry
is never removed, and any unexplained full boundary preserves the proposal.
"""
from math import dist, hypot

from jtool_scanner.spike_shape import VERTICES
from scripts.source_hollow_glyphs import HollowGlyphEvidence, MATERIAL_COHERENCE_FRACTION
from scripts.source_object_frames import SourceObjectFrames

_MINI_VERTICES = {t: tuple((u/2, v/2) for u, v in poly) for t, poly in VERTICES.items()}


class MiniHollowQuery(HollowGlyphEvidence):
    """16px queries sharing frozen full32 source teachers, without refitting.

    Only the centroid, ownership polygon and native bounds change. Keep full
    model/paint predicates and the three-peer closed-void safeguard unchanged.
    """

    @classmethod
    def from_full(cls, evidence):
        result = cls.__new__(cls)
        result.__dict__.update(evidence.__dict__)
        for name in ('cores', 'results', 'qualified_results', 'owned_edges'):
            setattr(result, name, {})
        return result

    def core(self, key, model):
        if key not in self.cores:
            t, x, y = key
            cx = x+sum(u for u, v in _MINI_VERTICES[t])/3
            cy = y+sum(v for u, v in _MINI_VERTICES[t])/3
            self.cores[key] = [self.library.pixel(cx+dx, cy+dy)
                               for dx in (-.5, .5) for dy in (-.5, .5)]
        values = self.cores[key]
        if any(v is None for v in values):
            return 0
        vector = tuple(f-b for f, b in zip(model['foreground'], model['background']))
        energy = sum(v*v for v in vector)
        if energy <= 0:
            return 0
        quantum = sum(abs(v) for v in vector)/energy
        def background_role(rgb):
            projection = sum((v-b)*d for v, b, d in zip(rgb, model['background'], vector))/energy
            return (dist(rgb, model['background']) < dist(rgb, model['foreground'])
                    and projection >= -MATERIAL_COHERENCE_FRACTION-quantum)
        return sum(background_role(v) for v in values)/4

    def owns_at(self, key, index):
        t, x, y = key
        poly = [(x+u, y+v) for u, v in _MINI_VERTICES[t]]
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
            if (cx-a[0])*nx+(cy-a[1])*ny < 0:
                nx, ny = -nx, -ny
            cache_key = a, b, index, nx, ny
            if cache_key not in self.owned_edges:
                sites = set()
                for i in range(12):
                    q = .15+.7*i/11
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
        if t not in _MINI_VERTICES:
            raise ValueError('Only oriented mini queries are qualified')
        passed = []
        if self.models and 0 <= x <= 784 and 0 <= y <= 592:
            for dx in (0, -self.library.pitch[0], self.library.pitch[0]):
                for dy in (0, -self.library.pitch[1], self.library.pitch[1]):
                    if not (0 <= x+dx <= 784 and 0 <= y+dy <= 592):
                        continue
                    poly = [(x+dx+u, y+dy+v) for u, v in _MINI_VERTICES[t]]
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
        return {3: ((6, x-8, y), (6, x+8, y), (6, x, y+16)),
                6: ((3, x-8, y), (3, x+8, y), (3, x, y-16)),
                4: ((5, x, y-8), (5, x, y+8), (5, x-16, y)),
                5: ((4, x, y-8), (4, x, y+8), (4, x+16, y))}[t]


def support_mini(evidence, key):
    t, x, y = key
    if not 7 <= t <= 10:
        raise ValueError('Only mini IDs7..10')
    return evidence.support((t-4, x, y))


def _on_segment(point, first, second):
    dx, dy = second[0]-first[0], second[1]-first[1]
    length = hypot(dx, dy)
    return (abs((point[0]-first[0])*dy-(point[1]-first[1])*dx) <= 1e-7*length
            and -1e-7 <= (point[0]-first[0])*dx+(point[1]-first[1])*dy <= length*length+1e-7)


class BoundaryExplanation:
    def __init__(self, frame, original, evidence):
        self.frame, self.original, self.full = frame, tuple(original), evidence
        self.mini = MiniHollowQuery.from_full(evidence)
        self.mini_proofs, self.rectangles = {}, None

    def explain(self, key, proof):
        t, x, y = key
        neighbors = sorted({(d.type_id, d.x, d.y) for d in self.original if 7 <= d.type_id <= 10
            and d.x <= x+32 and d.x+16 >= x and d.y <= y+32 and d.y+16 >= y})
        if len(neighbors) < 2:
            return dict(abstain=False, reason='fewer than two original mini locators')
        for k in neighbors:
            if k not in self.mini_proofs:
                self.mini_proofs[k] = support_mini(self.mini, k)
        if sum(self.mini_proofs[k]['passed'] for k in neighbors) < 2:
            return dict(abstain=False, reason='fewer than two source-qualified minis')
        if self.rectangles is None:
            from scripts.source_rectangle_prototypes import source_rectangle_proposals
            proposals, _ = source_rectangle_proposals(self.frame.original_snapshot(), self.frame.room, self.original)
            old = {(d.type_id, d.x, d.y) for d in self.original if d.type_id == 1}
            self.rectangles = sorted(proposals & old)
        explanations = []
        for fullproof in proof['proof']:
            teachers, mini_edges, qualified = fullproof['original_teachers'], [], []
            for k in neighbors:
                for mp in self.mini_proofs[k]['proof']:
                    if mp['original_teachers'] != teachers:
                        continue
                    st, sx, sy = k
                    dx, dy = mp['phase']
                    poly = [(sx+dx+u/2, sy+dy+v/2) for u, v in VERTICES[st-4]]
                    mini_edges.extend(zip(poly, poly[1:]+poly[:1]))
                    qualified.append(k)
            if len(set(qualified)) < 2:
                return dict(abstain=False, reason='no shared independent RGB model')
            dx, dy = fullproof['phase']
            poly = [(x+dx+u, y+dy+v) for u, v in VERTICES[t]]
            faces = []
            for a, b in zip(poly, poly[1:]+poly[:1]):
                sites = []
                for i in range(12):
                    q = .15+.7*i/11
                    p = a[0]+q*(b[0]-a[0]), a[1]+q*(b[1]-a[1])
                    mini_owned = any(_on_segment(p, c, d) for c, d in mini_edges)
                    solid_owned = any(bx <= p[0] <= bx+32 and by <= p[1] <= by+32
                                      for _, bx, by in self.rectangles)
                    sites.append(mini_owned or solid_owned)
                faces.append(sum(sites))
            if faces != [12, 12, 12]:
                return dict(abstain=False, reason='new full has unexplained boundary', faces=faces)
            explanations.append(dict(phase=fullproof['phase'], original_minis=sorted(set(qualified)), faces=faces))
        return dict(abstain=bool(explanations),
            reason='all qualified full boundaries explained by source minis/original solids', proof=explanations)


def qualify_new_boundaries(frame, original, evidence, proposed):
    legacy = {(t, d.x+dx, d.y+dy) for d in original if 3 <= d.type_id <= 6
        for dx in (-16, -8, 0, 8, 16) for dy in (-16, -8, 0, 8, 16) for t in (3, 4, 5, 6)
        if 0 <= d.x+dx <= 768 and 0 <= d.y+dy <= 576}
    eligible = [k for k in sorted(proposed-legacy) if sum(7 <= d.type_id <= 10
        and d.x <= k[1]+32 and d.x+16 >= k[1] and d.y <= k[2]+32 and d.y+16 >= k[2]
        for d in original) >= 2]
    if not eligible or frame.room != frame.extent:
        return proposed, []
    bodies = SourceObjectFrames(frame, original)
    if not bodies.models:
        return proposed, []
    explanation = BoundaryExplanation(frame, original, evidence)
    explanation.rectangles = sorted({(1, d.x, d.y) for d in original
        if d.type_id == 1 and bodies.support(d.x, d.y)['passed']})
    nearby = {(d.type_id, d.x, d.y) for d in original if 7 <= d.type_id <= 10 and any(
        d.x <= k[1]+32 and d.x+16 >= k[1] and d.y <= k[2]+32 and d.y+16 >= k[2] for k in eligible)}
    explanation.mini_proofs = {k: support_mini(explanation.mini, k) for k in nearby}
    abstained = []
    for key in eligible:
        proof = explanation.explain(key, evidence.support(key))
        if proof['abstain']:
            abstained.append(dict(key=key, evidence=proof, original_solid_proofs=explanation.rectangles))
    return proposed-{tuple(row['key']) for row in abstained}, abstained
