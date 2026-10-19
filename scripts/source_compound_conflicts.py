"""Source-only full-rectangle conflicts with independently verified filled glyphs.

UNBOUND research API: returns original keys to review, never edits a map. It
needs original source/context/calibration, not reference maps or emitted poses.
Actual source pixel squares, not widened shape halos, explain raster mixtures.
Positive rectangle evidence, real markers and unresolved pixels remain vetoes.
"""
from copy import deepcopy
from dataclasses import asdict
from math import ceil, floor, sqrt

from jtool_scanner.spike_shape import VERTICES
from scripts.source_block_prototypes import SourceBlockLibrary
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_glyph_prototypes import _contains
from scripts.source_material_ownership import material_cells
from scripts.source_pixel_geometry import PolygonPixelCoverage
from scripts.source_rectangle_prototypes import _interior_signature


def _distance(a, b):
    return sqrt(sum((x-y)**2 for x, y in zip(a, b)))


def _intersects(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def _bounds(poly):
    return min(x for x, y in poly), min(y for x, y in poly), max(x for x, y in poly), max(y for x, y in poly)


def _upright(t, a, b):
    return (a,b) if t == 3 else (b,32-a) if t == 4 else (32-b,a) if t == 5 else (32-a,32-b)


def _oriented(t, u, v):
    return (u,v) if t == 3 else (32-v,u) if t == 4 else (v,32-u) if t == 5 else (32-u,32-v)


class _ConflictQuery:
    def __init__(self, frame, context, original, material, library, blocks, filled):
        self.frame, self.context, self.original = frame, context, original
        self.library, self.blocks, self.filled = library, blocks, filled
        self.foreground = [tuple(material['cluster_centers'][i][c] for c in ('r','g','b'))
                           for i in sorted(material['selected_clusters'])]
        tips = material.get('tip_votes', {})
        backs = material.get('background_back_votes', material.get('back_votes', {}))
        bg = {int(c) for c, votes in tips.items()
              if votes >= 3 and votes/(votes+backs.get(int(c), backs.get(str(c), 0))) >= .75}
        self.background = [tuple(material['cluster_centers'][i][c] for c in ('r','g','b')) for i in sorted(bg)]
        self.separation = min(_distance(a,b) for a in self.foreground for b in self.background)
        self.intrinsic = set(map(tuple, material.get('intrinsic_geometry_appearance_evidence_retained', ())))
        self.membership, self.art_cache = {}, {}
        self.polygons, self.glyph_proofs, self.coverage, self.artwork = {}, [], {}, {}
        self.rectangles, self.rectangle_proofs = {}, []
        self._inner, self._inner_models = {}, {}

    def role(self, rgb):
        if rgb not in self.membership:
            f = min(_distance(rgb,c) for c in self.foreground)
            b = min(_distance(rgb,c) for c in self.background)
            self.membership[rgb] = 'fg' if f < .5*b else 'bg' if b < .5*f else 'unknown'
        return self.membership[rgb]

    def glyphs(self):
        for key in sorted(self.filled.original_spikes):
            proof = self.filled.support_joint_phase(key, short_circuit=True)
            self.glyph_proofs.append(dict(key=key, proof=proof))
            if not (proof['passed'] and proof.get('original_teachers_only')
                    and proof.get('complete_physical_source')
                    and len(proof.get('independent_filled_teachers', ())) >= 3):
                continue
            t,x,y = key
            dx,dy = proof.get('joint_source_phase', (0,0))
            # A joint phase registers SOURCE SAMPLING, not the native object.
            # FilledGlyphEvidence explicitly leaves the hypothesis key fixed.
            poly = [(x+u,y+v) for u,v in VERTICES[t]]
            self.polygons[key] = poly
            self.coverage[key] = PolygonPixelCoverage(self.frame,poly)
            signature = self.filled.library.signature(t,x+dx,y+dy)
            choices = []
            for model in self.filled.library.models:
                if model['native_size'] != 32:
                    continue
                score = sum(a*b for a,b in zip(signature,model['signature']))
                if score < .9:
                    continue
                others = tuple(k for k in self.filled._teachers(model) if abs(k[1]-x) >= 32 or abs(k[2]-y) >= 32)
                if len(others) >= 3:
                    choices.append((score,others))
            if choices:
                score,teachers = max(choices,key=lambda p:p[0])
                self.artwork[key] = dict(phase=(dx,dy),teachers=teachers,correlation=score)

    def _interior(self, point):
        if point not in self._inner:
            self._inner[point] = _interior_signature(self.library,*point)
        return self._inner[point]

    def rectangle_explanations(self, candidates):
        for d in self.original:
            if d.type_id != 1 or not any(_intersects((d.x,d.y,d.x+32,d.y+32),box) for box in candidates):
                continue
            own = self.blocks.support(d.x,d.y)
            if not own['passed']:
                continue
            dx,dy = own['phase']
            point = d.x+dx,d.y+dy
            if not self.frame.rectangle_available(*point,32,32,margin=4):
                continue
            faces = self.context.contours().rectangle(*point,32)
            if sum(f.support >= 9 and not f.unknown for f in faces) < 2:
                continue
            teachers = tuple(map(tuple,own['source_teachers']))
            if any(not self.frame.rectangle_available(*p,32,32,margin=4) for p in teachers):
                continue
            other = []
            for x,y in teachers:
                if abs(x-d.x) < 32 and abs(y-d.y) < 32:
                    continue
                if all(abs(x-a) >= 32 or abs(y-b) >= 32 for a,b in other):
                    other.append((x,y))
            if len(other) < 3:
                continue
            if teachers not in self._inner_models:
                mean = tuple(sum(self._interior(p)[i] for p in teachers)/len(teachers) for i in range(768))
                length = sqrt(sum(v*v for v in mean))
                self._inner_models[teachers] = tuple(v/max(1e-12,length) for v in mean)
            score = sum(a*b for a,b in zip(self._interior(point),self._inner_models[teachers]))
            if score >= .9:
                key = 1,d.x,d.y
                self.rectangles[key] = (d.x,d.y)
                self.rectangle_proofs.append(dict(key=key,point=(d.x,d.y),sampling_point=point,
                    sampling_phase=(dx,dy),interior_correlation=score,
                    full_correlation=own['correlation'],phase_faces=[asdict(f) for f in faces],
                    other_original_teachers=other))

    def raw_rectangle(self, x, y):
        px,py = self.frame.pitch
        for dx in (0,-px,px):
            for dy in (0,-py,py):
                if not self.frame.rectangle_available(x+dx,y+dy,32,32,margin=4):
                    continue
                faces = self.context.contours().rectangle(x+dx,y+dy,32)
                if all(f.support >= 9 and not f.unknown for f in faces):
                    return dict(passed=True,phase=(dx,dy),faces=[asdict(f) for f in faces])
        return dict(passed=False)

    def art_owner(self, nx, ny, rgb):
        if (nx,ny) in self.art_cache:
            return self.art_cache[nx,ny]
        for owner,model in self.artwork.items():
            t,x,y = owner
            dx,dy = model['phase']
            a,b = nx-x-dx,ny-y-dy
            if not (-4 <= a < 36 and -4 <= b < 36):
                continue
            u,v = _upright(t,a,b)
            votes = []
            for tt,tx,ty in model['teachers']:
                aa,bb = _oriented(tt,u,v)
                value = self.frame.original_pixel(tx+aa,ty+bb)
                if value is None or _distance(rgb,value) > .25*self.separation:
                    continue
                if any(_distance(value,c) > .25*self.separation for c in votes):
                    continue
                votes.append(value)
                if len(votes) >= 3:
                    self.art_cache[nx,ny] = owner
                    return owner
        self.art_cache[nx,ny] = None
        return None

    def query(self, d):
        from collections import Counter
        key = 1,d.x,d.y
        result = dict(key=key,retire=False)
        if not self.frame.rectangle_available(d.x,d.y,32,32,margin=4):
            return {**result,'abstained':'incomplete original source footprint'}
        box = d.x,d.y,d.x+32,d.y+32
        if any(a.type_id > 10 and _intersects(box,(a.x,a.y,a.x+32,a.y+32)) for a in self.original):
            return {**result,'abstained':'original nongeometry overlap'}
        own = self.blocks.support(d.x,d.y)
        if own['passed']:
            return {**result,'abstained':'own original rectangle appearance','own_rectangle':own}
        closure = self.raw_rectangle(d.x,d.y)
        if closure['passed']:
            return {**result,'abstained':'coherent raw rectangle closure','raw_rectangle':closure}
        counts,unexplained,mixed,residual = Counter(),[],[],[]
        room = self.frame.room
        source = self.frame.original_snapshot()
        local = {k:p for k,p in self.polygons.items() if _intersects(box,_bounds(p))}
        for sy in range(floor(room.y+d.y*room.height/608),ceil(room.y+(d.y+32)*room.height/608)):
            for sx in range(floor(room.x+d.x*room.width/800),ceil(room.x+(d.x+32)*room.width/800)):
                nx,ny = (sx+.5-room.x)*800/room.width,(sy+.5-room.y)*608/room.height
                if not (d.x <= nx < d.x+32 and d.y <= ny < d.y+32):
                    continue
                if any(_contains(p,nx,ny) for p in local.values()):
                    counts['other_original_source_triangle'] += 1
                    continue
                if any(other != key and x <= nx < x+32 and y <= ny < y+32 for other,(x,y) in self.rectangles.items()):
                    counts['other_original_source_rectangle'] += 1
                    continue
                if (floor(nx/16)*16,floor(ny/16)*16) in self.intrinsic:
                    counts['intrinsic_source_material'] += 1
                    continue
                rgb = source.pixel(sx,sy)
                role = self.role(rgb)
                if role != 'bg' and self.art_owner(nx,ny,rgb) is not None:
                    counts['independently_repeated_original_artwork'] += 1
                    continue
                if role != 'bg':
                    values = [(self.coverage[k].overlap(sx,sy),k) for k in local]
                    positive = [(a,k) for a,k in values if a is not None and a > 1e-9]
                    if positive:
                        area,owner = max(positive)
                        counts['mixed_with_verified_original_glyph'] += 1
                        mixed.append(dict(physical=(sx,sy),owner=owner,area_fraction=area,RGB=rgb,original_role=role))
                        continue
                counts[role] += 1
                unexplained.append(rgb)
                if role != 'bg':
                    residual.append(dict(physical=(sx,sy),native=(nx,ny),RGB=rgb,role=role))
        mean = tuple(sum(c[i] for c in unexplained)/len(unexplained) for i in range(3)) if unexplained else None
        error = min(_distance(mean,c) for c in self.background) if mean else None
        owned = counts['other_original_source_triangle']+counts['mixed_with_verified_original_glyph']
        retire = bool(owned and counts['bg'] >= 16 and not counts['fg'] and not counts['unknown']
                      and error <= .25*self.separation)
        return {**result,'retire':retire,'own_rectangle':own,'raw_rectangle':closure,
            'counts':dict(counts),'mixed_pixels':mixed,'unexplained_pixels':residual,
            'mean_bg_error':error,'unchanged_mean_limit':.25*self.separation}


def source_compound_conflicts(image, room, detections, *, source_grid, source_frame,
                             source_context=None, source_material=None,
                             source_block_library=None, source_filled_evidence=None):
    """Return reviewable original full-block keys and source-only evidence.

    The caller must freeze ORIGINAL detections before new proposals. Supplied
    material/libraries must belong to that source/context. Reuse existing stages
    during integration; only standalone diagnostics compute absent material.
    No automatic scanner binding, map edits or expanded teacher set.
    """
    original = tuple(detections)
    if not source_frame.matches_source(image,room):
        raise ValueError('Compound frame must match the original source')
    proof = dict(rows=[],retired=[],no_objects_emitted=True,no_origin_changes=True,
        no_new_outputs_as_teachers=True,original_source_only=True)
    if source_grid != (25,19) or source_frame.extent != room:
        return set(),{**proof,'abstained':'native grid/world transform not qualified'}
    spikes = [(d.type_id,d.x,d.y) for d in original if 3 <= d.type_id <= 10]
    context = source_context or SourceEvidenceContext(image,room,spikes)
    context.validate(image,room,spikes)
    context._validate_growth_originals(original)
    material = source_material
    if material is None:
        water = [(d.x,d.y,32,32) for d in original if d.type_id in (14,15,23)]
        _,material = material_cells(image,room,spikes,water,source_context=context)
    foreground = set(material.get('selected_clusters',()))
    tips = material.get('tip_votes',{})
    backs = material.get('background_back_votes',material.get('back_votes',{}))
    background = {int(c) for c,v in tips.items() if v >= 3 and v/(v+backs.get(int(c),backs.get(str(c),0))) >= .75}
    if not foreground or not background or foreground & background:
        return set(),{**proof,'abstained':'no disjoint original material roles'}
    library = context.glyph_library(image,room,spikes)
    filled = source_filled_evidence or FilledGlyphEvidence(source_frame,original,source_library=library)
    if (not isinstance(filled,FilledGlyphEvidence) or filled.frame is not source_frame
            or filled.original_spikes != tuple(sorted({(d.type_id,d.x,d.y) for d in original if 3 <= d.type_id <= 6}))):
        raise ValueError('Filled evidence must share original frame and detections')
    glyph_origins = {(d.x,d.y) for d in original if 3 <= d.type_id <= 6}
    if (not source_frame.matches_source(filled.library.raw.image,room)
            or any((x,y) not in glyph_origins for model in filled.library.models if model['native_size'] == 32
                   for t,x,y in model['original_source_witnesses'])):
        raise ValueError('Filled models must contain only original source teachers')
    if not filled.has_qualified_model():
        return set(),{**proof,'abstained':'no independent original filled model'}
    blocks = source_block_library
    textured = set(map(tuple,material.get('accepted',())))-set(map(tuple,material.get('source_flat_accepted_cells',())))
    if blocks is None:
        polygons = []
        for anchor in library.anchors:
            t,x,y = anchor['key'];size = anchor['size'];kind = t-4 if t > 6 else t
            polygons.append([(x+u*size/32,y+v*size/32) for u,v in VERTICES[kind]])
        blocks = SourceBlockLibrary(library,{(d.x,d.y) for d in original if d.type_id == 1},textured,polygons)
    fulls = {(d.x,d.y) for d in original if d.type_id == 1}
    if (not isinstance(blocks,SourceBlockLibrary) or blocks.library is not library
            or not set(blocks.teachers) <= fulls
            or any(not {(x,y),(x+16,y),(x,y+16),(x+16,y+16)} <= textured for x,y in blocks.teachers)
            or any(tuple(p) not in set(blocks.teachers) for model in blocks.models for p in model['source_teachers'])):
        raise ValueError('Block library must contain only original source teachers')
    query = _ConflictQuery(source_frame,context,original,material,library,blocks,filled)
    if query.separation <= 0:
        return set(),{**proof,'abstained':'no source colour separation'}
    query.glyphs()
    bounds = [_bounds(p) for p in query.polygons.values()]
    candidates = [d for d in original if d.type_id == 1 and any(_intersects((d.x,d.y,d.x+32,d.y+32),b) for b in bounds)]
    query.rectangle_explanations([(d.x,d.y,d.x+32,d.y+32) for d in candidates])
    rows = [query.query(d) for d in candidates]
    retired = {tuple(r['key']) for r in rows if r['retire']}
    return retired,deepcopy({**proof,'rows':rows,'retired':sorted(retired),
        'original_glyph_proofs':query.glyph_proofs,'original_rectangle_proofs':query.rectangle_proofs,
        'original_artwork_proofs':[dict(key=k,**v) for k,v in query.artwork.items()],
        'source_material_reused':source_material is not None,'source_block_library_reused':source_block_library is not None,
        'source_filled_evidence_reused':source_filled_evidence is not None})
