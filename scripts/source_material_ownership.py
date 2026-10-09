"""Original-source material/glyph arbitration with explicit dependencies.

Context can explain an independently witnessed occlusion or exclude contaminated
reference samples. It cannot invent a rectangle teacher or delete old objects just
because their boxes overlap. Experimental, not default detector binding.
"""
from math import hypot
from statistics import median

from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import SourceGlyphEvidence, SourceGlyphLibrary, _bounds, _contains, _fits
from scripts.source_material_evidence import MaterialBoundary, rectangle_field
from scripts.source_material_patterns import combined_patterns, pattern_cells


def _hypotheses(spikes, cells):
    result = set()
    for type_id, x, y in spikes:
        size = 16 if type_id > 6 else 32
        touched = [p for p in cells if max(p[0], x) < min(p[0]+16, x+size)
                   and max(p[1], y) < min(p[1]+16, y+size)]
        if not touched:
            continue
        for d in (3, 4, 5, 6):
            result.add((d+(4 if size == 16 else 0), x, y))
        for cx, cy in touched:
            for d in (7, 8, 9, 10):
                result.add((d, cx, cy))
    return result


def _rejections(cells, owners):
    rejected = []
    for x, y in sorted(cells):
        for owner in owners:
            count = sum(_contains(owner['poly'], px+.5, py+.5)
                        for py in range(y+4, y+12) for px in range(x+4, x+12))
            if count >= 16:
                rejected.append(dict(native=[x, y], source_owner=owner['key'], core_owned_pixels=count))
                break
    return rejected


def strict_glyph_ownership(image, room, spikes, cells, *, source_context=None):
    raw = rectangle_field(image, room, spikes, source_context)
    field = SourceGlyphEvidence(raw.image, room, contour_field=raw.contours)
    owners = [row for key in sorted(_hypotheses(spikes, cells)) if (row := field.owner(*key)) is not None]
    rejected = _rejections(cells, owners)
    return {tuple(r['native']) for r in rejected}, dict(source_local_glyph_owners=owners,
        source_local_glyph_rejected=rejected, new_objects_not_emitted_from_hypotheses=True,
        existing_objects_not_deleted_from_locator_overlap=True)


class ContextGlyphEvidence(SourceGlyphEvidence):
    """Source-context triangle closure, always RAW competing rectangle evidence."""

    def __init__(self, raw, rectangles, strict_owners):
        super().__init__(raw.image, raw.room, contour_field=raw.contours)
        self.raw_original = self.raw
        self.rectangles, self.strict_owners, self.proofs = rectangles, strict_owners, {}

    def edge(self, first, second):
        tx, ty = second[0]-first[0], second[1]-first[1]
        length = hypot(tx, ty)
        nx, ny = -ty/length, tx/length
        rows, unknown = [], False
        for i in range(12):
            q = .15+.7*i/11
            px, py = first[0]+q*tx, first[1]+q*ty
            native = [(px+off*nx, py+off*ny) for off in range(-4, 5)]
            if any(not (0 <= x < 800 and 0 <= y < 608) for x, y in native):
                unknown = True
                break
            points = [(int(self.room.x+x*self.room.width/800), int(self.room.y+y*self.room.height/608)) for x, y in native]
            if any(not (0 <= x < self.image.width and 0 <= y < self.image.height) for x, y in points):
                unknown = True
                break
            values = [self.image.pixel(*p) for p in points]
            derivatives = []
            for j in range(8):
                spacing = hypot(points[j+1][0]-points[j][0], points[j+1][1]-points[j][1])
                derivatives.append(tuple((values[j+1][c]-values[j][c])/spacing for c in range(3)) if spacing else (0., 0., 0.))
            covered = any(x < px < x+w and y < py < y+h for x, y, w, h in self.rectangles)
            clean = []
            for j in (0, 1, 6, 7):
                contaminated = any(_contains(o['poly'], *native[j]) or _contains(o['poly'], *native[j+1])
                                   for o in self.strict_owners)
                if not contaminated:
                    clean.append(j)
            phases = set()
            if len(clean) >= 2:
                background = tuple(median(derivatives[j][c] for j in clean) for c in range(3))
                departure = lambda value: hypot(*(value[c]-background[c] for c in range(3)))
                outer = max(departure(derivatives[j]) for j in clean)
                phases = {j-3.5 for j in (2, 3, 4, 5) if departure(derivatives[j]) > outer}
            rows.append(dict(index=i, source=points[4], phases=phases, covered=covered, clean=clean))
        best = set()
        if not unknown:
            for lo in (-1.5, -.5, .5):
                supported = {tuple(r['source']) for r in rows if r['covered'] or any(lo <= p <= lo+1 for p in r['phases'])}
                if len(supported) > len(best):
                    best = supported
        self.proofs[first, second] = dict(support=len(best), unknown=unknown,
            original=self.raw_original.edge(first, second), covered_sites=sum(r['covered'] for r in rows),
            reference_filtered_sites=sum(len(r['clean']) < 4 for r in rows), source_positions=sorted(best))
        return len(best), unknown

    def owner(self, type_id, x, y):
        key = type_id, x, y
        if key in self.cache:
            return self.cache[key]
        self.cache[key] = None
        size, direction = (16, type_id-4) if type_id > 6 else (32, type_id)
        poly = [(x+a*size/32, y+b*size/32) for a, b in VERTICES[direction]]
        triangle = [self.edge(poly[i], poly[(i+1)%3]) for i in range(3)]
        if any(count < 9 or unknown for count, unknown in triangle):
            return None
        corners = [(x, y), (x+size, y), (x+size, y+size), (x, y+size)]
        rectangle = [self.raw_original.edge(corners[i], corners[(i+1)%4]) for i in range(4)]
        if all(count >= 9 and not unknown for count, unknown in rectangle):
            return None
        margin = size/8
        points = [(x+margin, y+margin), (x+size-margin, y+margin),
                  (x+size-margin, y+size-margin), (x+margin, y+size-margin)]
        exterior = [p for p in points if not _contains(poly, *p)]
        if len(exterior) != 2:
            return None
        patches = [self.sample(*p, size=2 if size == 16 else 4) for p in exterior]
        if any(p is None for p in patches):
            return None
        models = [_bounds(p) for p in patches]
        body = []
        for weights in ((.25, .5, .25), (.25, .25, .5), (.5, .25, .25), (1/3, 1/3, 1/3)):
            cx, cy = sum(w*p[0] for w, p in zip(weights, poly)), sum(w*p[1] for w, p in zip(weights, poly))
            values = self.sample(cx, cy)
            if values is None:
                return None
            body.append(not any(all(_fits(rgb, m) for rgb in values) for m in models))
        if not all(body):
            return None
        row = dict(key=[type_id, x, y], poly=poly, triangle_faces=triangle,
            competing_rectangle_faces=rectangle, source_exterior_corners=exterior,
            source_body_separate_from_both_corners=body)
        self.cache[key] = row
        return row


def qualify_growth(image, room, spikes, cells, diag, *, source_context=None):
    strict_bad, strict_proof = strict_glyph_ownership(image, room, spikes, cells, source_context=source_context)
    raw = rectangle_field(image, room, spikes, source_context)
    rectangles = [(x, y, 16, 16) for x, y in diag.get('closed_cells', []) if min(raw.box_faces(x, y)) >= 9]
    field = ContextGlyphEvidence(raw, rectangles, strict_proof['source_local_glyph_owners'])
    owners = [row for key in sorted(_hypotheses(spikes, cells)) if (row := field.owner(*key)) is not None]
    rejected = _rejections(cells, owners)
    bad = {tuple(r['native']) for r in rejected} | strict_bad
    return bad, dict(strict_source_proof=strict_proof, context_source_owners=owners,
        context_source_rejected=rejected, source_context_rectangles=field.rectangles,
        source_context_faces=[dict(first=a, second=b, **p) for (a, b), p in field.proofs.items()],
        competing_rectangle_evidence_raw=True, closure_threshold_unchanged=9,
        new_context_owners_never_used_as_witnesses=True, no_existing_object_deletion=True)


def material_owned_cells(image, room, spikes, water_boxes=(), *, source_context=None):
    accepted, diag = combined_patterns(image, room, spikes, water_boxes, source_context=source_context)
    field = MaterialBoundary(image, room, spikes, diag)
    owners = []
    for type_id, x, y in sorted(set(spikes)):
        if not 3 <= type_id <= 6:
            continue
        poly, slopes = field.triangle_transitions(type_id, x, y)
        if len(slopes) == 2 and all(r['support'] >= 9 and not r['unknown'] for r in slopes):
            owners.append(dict(key=[type_id, x, y], poly=poly, material_slope_transitions=slopes))
    rejected = _rejections(accepted, owners)
    bad = {tuple(r['native']) for r in rejected}
    return accepted-bad, {**diag, 'accepted': sorted(accepted-bad), 'material_owned_rejected': rejected,
                          'material_source_owners': owners, 'no_existing_object_deletion_or_generated_box_veto': True}


def material_cells(image, room, spikes, water_boxes=(), *, source_context=None):
    """Complete source material generator; original object lists remain untouched."""
    base, base_diag = pattern_cells(image, room, spikes, water_boxes, mode='intrinsic', source_context=source_context)
    cells, diag = material_owned_cells(image, room, spikes, water_boxes, source_context=source_context)
    bad, proof = qualify_growth(image, room, spikes, cells-base, diag, source_context=source_context)
    accepted = base | (cells-bad)
    flat = (set(map(tuple, diag.get('source_flat_accepted_cells', [])))-bad) | set(map(tuple, base_diag.get('source_flat_accepted_cells', [])))
    diag = {**diag, **proof, 'accepted': sorted(accepted), 'source_flat_accepted_cells': sorted(flat),
            'intrinsic_geometry_appearance_evidence_retained': sorted(base), 'original_source_owned_back_calibration=True': True}
    weak = accepted-base
    library = (SourceGlyphLibrary(image, room, spikes) if source_context is None else
               source_context.glyph_library(image, room, spikes))
    owners = []
    for key in sorted(_hypotheses(spikes, weak)):
        type_id, x, y = key
        size, direction = (16, type_id-4) if type_id > 6 else (32, type_id)
        corners = [(x, y), (x+size, y), (x+size, y+size), (x, y+size)]
        faces = [library.raw.raw.edge(corners[i], corners[(i+1)%4]) for i in range(4)]
        if all(n >= 9 and not unknown for n, unknown in faces):
            continue
        source_proof = library.support(*key)
        if not source_proof['passed']:
            continue
        poly = [(x+u*size/32, y+v*size/32) for u, v in VERTICES[direction]]
        owners.append(dict(key=key, poly=poly, source_model_proof=source_proof))
    rejected = _rejections(weak, owners)
    bad = {tuple(r['native']) for r in rejected}
    accepted = accepted-bad
    return accepted, {**diag, 'accepted': sorted(accepted),
        'source_flat_accepted_cells': sorted(set(map(tuple, diag.get('source_flat_accepted_cells', [])))-bad),
        'source_glyph_prototype_owners': owners, 'source_glyph_prototype_rejected': rejected,
        'source_glyph_anchor_count': len(library.anchors),
        'source_glyph_models': [{k: v for k, v in m.items() if k != 'signature'} for m in library.models],
        'only_original_source_hypotheses_as_teachers=True': True, 'no_existing_objects_removed_by_overlap=True': True}
