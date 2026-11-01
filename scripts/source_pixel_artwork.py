"""Independent original-pixel artwork, without a background-model fallback.

Physical RGB cells describe resampling uncertainty at one corresponding source
point. Three disjoint original witnesses must agree; they do not label unknown
background as empty or weaken the compound query's rectangle/marker vetoes.
"""
from math import dist

from scripts import source_compound_conflicts as compound
from scripts.source_raster_cells import closest_rgb, source_cell


class RepeatedPixelArtworkQuery(compound._ConflictQuery):
    """Keep the strict ownership query; extend only repeated-artwork evidence."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cells, self.cell_queries, self.new_art_witnesses = {}, {}, []

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
                votes.append(dict(teacher=(tt, tx, ty), cell=local,
                                  closest_RGB=fitted, error=error))
                if len(votes) >= 3:
                    self.cell_queries[key] = owner
                    self.new_art_witnesses.append(dict(native_point=(nx, ny), RGB=rgb,
                        owner=owner, limit=limit, witnesses=votes))
                    return owner
        self.cell_queries[key] = None
        return None


class PixelArtworkConflictQuery(RepeatedPixelArtworkQuery):
    """Neither point nor cell teachers may overlap the block being judged.

    Artwork decisions depend on the current query's exclusions. Pixel cells
    themselves are immutable original-source samples and can safely be shared.
    """

    def query(self, detection):
        box = detection.x, detection.y, detection.x+32, detection.y+32
        # Existing artwork sampling includes four native pixels of context.
        # Also exclude any whole physical tap that could cross the query edge.
        mx = 4 + 800/self.frame.extent.width
        my = 4 + 608/self.frame.extent.height
        artwork, art_cache, cell_queries = self.artwork, self.art_cache, self.cell_queries
        eligible, excluded = {}, set()
        for owner, model in artwork.items():
            teachers = []
            for key in model['teachers']:
                _, x, y = key
                footprint = x-mx, y-my, x+32+mx, y+32+my
                if compound._intersects(box, footprint):
                    excluded.add(key)
                else:
                    teachers.append(key)
            if len(teachers) >= 3:
                eligible[owner] = {**model, 'teachers': tuple(teachers)}
        self.artwork, self.art_cache, self.cell_queries = eligible, {}, {}
        try:
            result = super().query(detection)
            return {**result, 'artwork_query_disjoint': True,
                    'artwork_query_excluded_teachers': sorted(excluded)}
        finally:
            self.artwork, self.art_cache, self.cell_queries = artwork, art_cache, cell_queries
