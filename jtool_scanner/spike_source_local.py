"""Source-local geometry normalization and candidate-owned ink evidence."""

from math import hypot
from statistics import median
from .spike_shape import _percentile

def mixin(base):
    class EdgeLocalCornerField(base):
        def localized_score(self, x, y, direction):
            if not (0 <= x <= 800 - self.native_size and 0 <= y <= 608 - self.native_size):
                return -1.0
            key = x, y, direction
            if key not in self.edge_local_scores:
                tip, *ends = self.vertices[direction]
                margin = max(.15, 4 / self.native_size)
                coverages = []
                statistics = []
                for end in ends:
                    tx, ty = end[0] - tip[0], end[1] - tip[1]
                    length = hypot(tx, ty)
                    nx, ny = -ty / length, tx / length
                    profiles = []
                    gradients = []
                    for i in range(12):
                        q = margin + (1 - 2 * margin) * i / 11
                        px, py = x + tip[0] + q * tx, y + tip[1] + q * ty
                        points = [(round(px + j * nx), round(py + j * ny)) for j in range(-4, 5)]
                        values = [self.pixel(*p) for p in points]
                        samples = [self.gradient(*p) for p in points[2:7]]
                        profiles.append((values, samples))
                        gradients.extend(hypot(*v) for v in samples)
                    spread = median(max(v) - min(v) for v, _ in profiles)
                    scale = max(1.0, _percentile(gradients, .90))
                    cutoff = max(scale * .25, spread * .15)
                    hits = 0
                    if spread >= 12:
                        hits = sum(any(hypot(gx, gy) >= cutoff
                                       and abs(gx * nx + gy * ny) >= hypot(gx, gy) * .95
                                       for gx, gy in samples) for _, samples in profiles)
                    coverages.append(hits / 12)
                    statistics.append(dict(scale=scale, spread=spread, cutoff=cutoff, hits=hits))
                self.edge_local_scores[key] = min(coverages)
                self.edge_local_statistics[key] = statistics
            return self.edge_local_scores[key]
    return EdgeLocalCornerField

def own_outline_score(field,x,y,direction):
    if not hasattr(field,'stroke_cache'):
        field.stroke_cache,field.profile_templates={},{}
    # Only this candidate's own native16 source samples. No nearby ink witness,
    # other object's size or stroke-only substitution for geometric closure.
    return field.own_outline(x,y,direction)['score']
