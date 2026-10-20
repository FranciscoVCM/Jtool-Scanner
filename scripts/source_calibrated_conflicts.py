"""Opt-in backdrop-qualified original rectangle conflicts.

No emitter, new teachers or automatic app activation. Legacy positive decisions
and all rectangle/marker/coverage vetoes win first. An unresolved physical pixel
is never empty space. The fixed model uses original geometry-qualified exteriors.
"""
from collections import Counter
from math import ceil, dist, floor

from scripts import source_compound_conflicts as compound
from scripts.source_glyph_backdrop import SourceGlyphBackdrop
from scripts.source_glyph_prototypes import _contains
from scripts.source_raster_cells import closest_rgb, source_cell


class CalibratedConflictQuery(compound._ConflictQuery):
    """The frozen source-cell + independent-backdrop conjunction."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cells, self.cell_queries, self.new_art_witnesses = {}, {}, []
        self.backdrop = None

    def art_owner(self, nx, ny, rgb):
        old = super().art_owner(nx, ny, rgb)
        if old is not None:
            return old
        key = nx, ny
        if key in self.cell_queries:
            return self.cell_queries[key]
        limit = .25*self.separation
        for owner, model in self.artwork.items():
            t, x, y = owner
            dx, dy = model['phase']
            a, b = nx-x-dx, ny-y-dy
            if not (-4 <= a < 36 and -4 <= b < 36):
                continue
            u, v = compound._upright(t, a, b)
            votes = []
            for tt, tx, ty in model['teachers']:
                aa, bb = compound._oriented(tt, u, v)
                cell_key = tx+aa, ty+bb
                if cell_key not in self.cells:
                    self.cells[cell_key] = source_cell(self.frame, *cell_key)
                local = self.cells[cell_key]
                if local is None:
                    continue
                fitted = closest_rgb(rgb, local['RGB'])
                error = dist(rgb, fitted)
                if error > limit:
                    continue
                positions = set(map(tuple, local['positions']))
                if any(positions & set(map(tuple, q['cell']['positions']))
                       or dist(fitted, q['closest_RGB']) > limit for q in votes):
                    continue
                votes.append(dict(teacher=(tt, tx, ty), cell=local, closest_RGB=fitted, error=error))
                if len(votes) >= 3:
                    self.cell_queries[key] = owner
                    self.new_art_witnesses.append(dict(native_point=(nx, ny), RGB=rgb,
                        owner=owner, limit=limit, witnesses=votes))
                    return owner
        self.cell_queries[key] = None
        return None

    def background_evidence(self):
        """Reuse original filled/source context; build only for unresolved queries."""
        if self.backdrop is None:
            self.backdrop = SourceGlyphBackdrop(self.filled, self.original,
                source_grid=(25, 19), intrinsic=self.intrinsic)
        return self.backdrop

    def query(self, detection):
        legacy = super().query(detection)
        if legacy['retire'] or 'abstained' in legacy:
            return legacy
        d = detection
        key, limit = (1, d.x, d.y), .25*self.separation
        calibration = self.background_evidence()
        model = calibration.model(key, limit)
        if not model.get('valid'):
            return {**legacy, 'backdrop_model': model}
        box = d.x, d.y, d.x+32, d.y+32
        room, source = self.frame.room, self.frame.original_snapshot()
        local = {k: p for k, p in self.polygons.items() if compound._intersects(box, compound._bounds(p))}
        counts, mixed, residual, observed, predicted = Counter(), [], [], [], []
        for sy in range(floor(room.y+d.y*room.height/608), ceil(room.y+(d.y+32)*room.height/608)):
            for sx in range(floor(room.x+d.x*room.width/800), ceil(room.x+(d.x+32)*room.width/800)):
                nx = (sx+.5-room.x)*800/room.width
                ny = (sy+.5-room.y)*608/room.height
                if not (d.x <= nx < d.x+32 and d.y <= ny < d.y+32):
                    continue
                if any(_contains(p, nx, ny) for p in local.values()):
                    counts['other_original_source_triangle'] += 1
                    continue
                if any(other != key and x <= nx < x+32 and y <= ny < y+32
                       for other, (x, y) in self.rectangles.items()):
                    counts['other_original_source_rectangle'] += 1
                    continue
                if (floor(nx/16)*16, floor(ny/16)*16) in self.intrinsic:
                    counts['intrinsic_source_material'] += 1
                    continue
                rgb = source.pixel(sx, sy)
                old_role = self.role(rgb)
                estimate = calibration.predict(model, nx, ny)
                if dist(rgb, estimate) <= limit:
                    counts['bg'] += 1
                    observed.append(rgb)
                    predicted.append(estimate)
                    continue
                if self.art_owner(nx, ny, rgb) is not None:
                    counts['independently_repeated_original_artwork'] += 1
                    continue
                # Keep the ORIGINAL non-BG gate. Area is not RGB ownership.
                if old_role != 'bg':
                    values = [(self.coverage[k].overlap(sx, sy), k) for k in local]
                    positive = [(a, k) for a, k in values if a is not None and a > 1e-9]
                    if positive:
                        area, owner = max(positive)
                        counts['mixed_with_verified_original_glyph'] += 1
                        mixed.append(dict(physical=(sx, sy), owner=owner, area_fraction=area,
                                          RGB=rgb, original_role=old_role))
                        continue
                role = old_role if old_role != 'bg' else 'unknown'
                counts[role] += 1
                residual.append(dict(physical=(sx, sy), native=(nx, ny), RGB=rgb,
                                     role=role, original_role=old_role))
        observed_mean = tuple(sum(c[i] for c in observed)/len(observed) for i in range(3)) if observed else None
        predicted_mean = tuple(sum(c[i] for c in predicted)/len(predicted) for i in range(3)) if predicted else None
        error = dist(observed_mean, predicted_mean) if observed_mean else None
        owned = counts['other_original_source_triangle']+counts['mixed_with_verified_original_glyph']
        retire = bool(owned and counts['bg'] >= 16 and not counts['fg'] and not counts['unknown'] and error <= limit)
        return dict(key=key, retire=retire, own_rectangle=legacy['own_rectangle'], raw_rectangle=legacy['raw_rectangle'],
            counts=dict(counts), mixed_pixels=mixed, unexplained_pixels=residual, mean_bg_error=error,
            unchanged_mean_limit=limit, backdrop_model=model, legacy_retire=False, original_BG_model_expert=True,
            body_owners=False, no_unknown_as_empty=True, no_original_BG_mixture_gate_broadened=True)
