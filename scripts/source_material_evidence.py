"""Original-source geometry, backing roles and background-boundary primitives.

Explicit experimental material inputs; no reference maps, private imports, newly
emitted witnesses or default detector binding. Preserve the material kernel's
original sqrt arithmetic for strict contour/proof equality.
"""
from collections import Counter, defaultdict
from math import hypot, sqrt

from jtool_scanner import scanner
from jtool_scanner.spike_shape import VERTICES
from scripts.source_contours import SourceContours
from scripts.source_glyph_prototypes import SourceGlyphEvidence, _contains


class SourceRectangles:
    def __init__(self, image, room):
        self.image, self.room = image, room
        self.colors = {}
        self.contours = SourceContours(image, room, squared_norm=True)

    def color(self, x, y, size):
        key = x, y, size
        if key not in self.colors:
            self.colors[key] = scanner._patch_color_profile(self.image, self.room, x, y, size)
        return self.colors[key]

    def edge(self, first, second):
        evidence = self.contours.edge(first, second)
        return evidence.support, evidence.unknown

    def triangle_closed(self, type_id, x, y):
        return all(face.support >= 9 for face in self.contours.triangle(type_id, x, y))

    def box_faces(self, x, y):
        return [face.support for face in self.contours.rectangle(x, y, 16)]


def rectangle_field(image, room, spikes, source_context=None):
    return (SourceRectangles(image, room) if source_context is None else
            source_context.rectangles(image, room, spikes))


class BackingCoreRoles:
    def __init__(self, field):
        self.field = SourceGlyphEvidence(field.image, field.room, contour_field=field.contours)
        self.cache, self.rejected = {}, []

    def glyph_owner(self, x, y):
        if (x, y) in self.cache:
            return self.cache[x, y]
        self.cache[x, y] = None
        if min(self.field.raw.box_faces(x, y)) >= 9:
            return None
        for size in (16, 32):
            for ox in range(x-size+8, x+1, 8):
                for oy in range(y-size+8, y+1, 8):
                    for direction in (3, 4, 5, 6):
                        poly = [(ox+a*size/32, oy+b*size/32) for a, b in VERTICES[direction]]
                        owned = sum(_contains(poly, px+.5, py+.5)
                                    for py in range(y+4, y+12) for px in range(x+4, x+12))
                        if owned < 48:
                            continue
                        key = direction+(4 if size == 16 else 0), ox, oy
                        owner = self.field.owner(*key)
                        if owner is not None:
                            row = dict(native=[x, y], source_owner=list(key), core_owned_pixels=owned, source_proof=owner)
                            self.cache[x, y] = row
                            self.rejected.append(row)
                            return row
        return None

    def eligible(self, x, y):
        return self.glyph_owner(x, y) is None


def expand_shadows(field, labels, centers, selected, tips, original_backs):
    background = {int(c) for c, v in tips.items() if v >= 3 and v/(v+original_backs.get(int(c), 0)) >= .75}
    rgb = [(c.avg_r, c.avg_g, c.avg_b) for c in centers]
    eligible = []
    for label, value in enumerate(rgb):
        if label in selected or label in background:
            continue
        alternatives = []
        for foreground in selected:
            for bg in background:
                axis = tuple(a-b for a, b in zip(rgb[foreground], rgb[bg]))
                delta = tuple(a-b for a, b in zip(value, rgb[bg]))
                energy, length = sum(v*v for v in axis), sum(v*v for v in delta)
                if not energy or not length:
                    continue
                dot = sum(a*b for a, b in zip(axis, delta))
                attenuation, alignment = dot/energy, dot/sqrt(energy*length)
                if .5 < attenuation <= 1 and alignment >= .95:
                    alternatives.append(dict(foreground=foreground, background=bg, attenuation=attenuation, alignment=alignment))
        if alternatives:
            eligible.append((label, alternatives))
    accepted, proof = set(), []
    for label, alternatives in eligible:
        witnesses = []
        for p, c in labels.items():
            if c != label:
                continue
            faces = field.box_faces(*p)
            if min(faces) >= 9:
                witnesses.append(dict(native=p, raw_faces=faces))
        if witnesses:
            accepted.add(label)
            proof.append(dict(label=label, original_source_geometry=witnesses, independent_color_roles=alternatives))
    return selected | accepted, proof


def native_cells(image, room, spikes, *, source_context=None):
    field = rectangle_field(image, room, spikes, source_context)
    roles = BackingCoreRoles(field)
    background_backs, background_anchors = Counter(), []
    cells = {(x, y): field.color(x+4, y+4, 8) for y in range(0, 593, 16) for x in range(0, 785, 16)}
    labels, centers = scanner._cluster_repeated_terrain_cells(cells, cluster_count=8)
    if len(centers) < 2:
        return set(), dict(reason='no separated source materials')

    def label(probe):
        x, y, size = probe
        if not (0 <= x <= 800-size and 0 <= y <= 608-size):
            return None
        color = field.color(x, y, size)
        return min(range(len(centers)), key=lambda c: scanner._color_profile_distance(color, centers[c]))

    backs, tips, support, anchor_rows = Counter(), Counter(), defaultdict(set), []
    for type_id, x, y in sorted(set(spikes)):
        if not field.triangle_closed(type_id, x, y):
            continue
        size, d = (16, type_id-4) if type_id > 6 else (32, type_id)
        probe, quarter = size//2, size//4
        if d == 3:
            front, points = (x+quarter, y-probe, probe), [(x+q*size, y+size+8) for q in (.25, .75)]
        elif d == 6:
            front, points = (x+quarter, y+size, probe), [(x+q*size, y-8) for q in (.25, .75)]
        elif d == 4:
            front, points = (x+size, y+quarter, probe), [(x-8, y+q*size) for q in (.25, .75)]
        else:
            front, points = (x-probe, y+quarter, probe), [(x+size+8, y+q*size) for q in (.25, .75)]
        f = label(front)
        if f is None:
            continue
        original_backed = {labels[p] for px, py in points
                           for p in [(int(px//16)*16, int(py//16)*16)] if p in labels}
        original_backed.discard(f)
        if not original_backed:
            continue
        for b in original_backed:
            background_backs[b] += 1
        for b in original_backed:
            background_anchors.append(dict(key=[type_id, x, y], back_cluster=b, front_cluster=f))
        tips[f] += 1
        backed = {labels[p] for px, py in points for p in [(int(px//16)*16, int(py//16)*16)]
                  if p in labels and roles.eligible(*p)}
        backed.discard(f)
        if not backed:
            continue
        for b in backed:
            backs[b] += 1
            support[b].add((x//32, y//32))
            anchor_rows.append(dict(key=[type_id, x, y], back_cluster=b, front_cluster=f))
    selected = {c for c in backs if backs[c] >= 3 and len(support[c]) >= 3 and backs[c]/(backs[c]+tips[c]) >= .75}
    selected, shadow_proof = expand_shadows(field, labels, centers, selected, tips, background_backs)
    candidates = {p for p, c in labels.items() if c in selected}
    face_rows = {p: field.box_faces(*p) for p in candidates}
    closed = {p for p, faces in face_rows.items() if min(faces) >= 9}
    vertical = {p for p, f in face_rows.items() if min(f[1], f[3]) >= 11}
    horizontal = {p for p, f in face_rows.items() if min(f[0], f[2]) >= 11}
    strips = set()
    for available, dx, dy in ((vertical, 0, 16), (horizontal, 16, 0)):
        for x, y in sorted(available):
            if (x-dx, y-dy) in available:
                continue
            group = []
            while (x, y) in available:
                group.append((x, y))
                x += dx
                y += dy
            if len(group) >= 3:
                strips.update(group)
    proposed = closed | strips
    repeated = {p for p in proposed if any(q in proposed for q in scanner._axis_neighbors(p, 16))}
    return repeated, dict(selected_clusters=sorted(selected),
        cluster_centers=[dict(r=c.avg_r, g=c.avg_g, b=c.avg_b) for c in centers],
        back_votes=dict(backs), tip_votes=dict(tips), anchors=anchor_rows,
        closed_cells=sorted(closed), strip_cells=sorted(strips),
        rectangle_faces=[dict(native=p, label=labels[p], faces=f) for p, f in sorted(face_rows.items())],
        accepted=sorted(repeated), source_native_grid16_only=True,
        source_geometry_shadow_roles=shadow_proof, source_owned_back_rejections=roles.rejected,
        background_back_votes=dict(background_backs), background_anchors=background_anchors)


def container_primitives(image, room, spikes, *, source_context=None):
    primitive, diag = native_cells(image, room, spikes, source_context=source_context)
    if not primitive and not diag.get('rectangle_faces'):
        return primitive, {**diag, 'native16_primitive': []}
    candidates = {tuple(r['native']) for r in diag['rectangle_faces']}
    field, containers, potential = rectangle_field(image, room, spikes, source_context), [], set(primitive)
    for x, y in sorted(candidates):
        for w, h in ((32, 32), (32, 48), (48, 32)):
            cells = {(x+dx, y+dy) for dy in range(0, h, 16) for dx in range(0, w, 16)}
            if not cells <= candidates:
                continue
            corners = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
            faces = [field.edge(corners[i], corners[(i+1)%4])[0] for i in range(4)]
            if min(faces) >= 9:
                potential.update(cells)
                containers.append(dict(box=[x, y, w, h], faces=faces, cells=sorted(cells)))
    return potential, {**diag, 'native16_primitive': sorted(primitive), 'independent_source_containers': containers}


class MaterialBoundary:
    def __init__(self, image, room, spikes, diagnosis):
        self.image, self.room = image, room
        self.patches, self.rgb_cache, self.models = {}, {}, []
        tips = diagnosis.get('tip_votes', {})
        backs = diagnosis.get('background_back_votes', diagnosis.get('back_votes', {}))
        background = {int(c) for c, v in tips.items() if v >= 3 and v/(v+backs.get(int(c), backs.get(str(c), 0))) >= .75}
        source_keys = {tuple(row['key']) for row in diagnosis.get('background_anchors', diagnosis.get('anchors', []))
                       if row['front_cluster'] in background}
        seen = set()
        for type_id, x, y in sorted(source_keys):
            size, direction = (16, type_id-4) if type_id > 6 else (32, type_id)
            probe = size//2
            if direction == 3:
                center = x+size/2, y-probe/2
            elif direction == 6:
                center = x+size/2, y+size+probe/2
            elif direction == 4:
                center = x+size+probe/2, y+size/2
            else:
                center = x-probe/2, y+size/2
            n = probe//2
            values = self.values(center[0]-n/2, center[1]-n/2, n, n)
            if values is None:
                continue
            bounds = tuple((min(v[c] for v in values), max(v[c] for v in values)) for c in range(3))
            if bounds in seen:
                continue
            seen.add(bounds)
            self.models.append(dict(bounds=bounds, source_anchor=[type_id, x, y], pixel_count=len(values)))

    def pixel(self, x, y):
        if not (0 <= x < 800 and 0 <= y < 608):
            return None
        sx = int(self.room.x+(x+.5)*self.room.width/800)
        sy = int(self.room.y+(y+.5)*self.room.height/608)
        if not (0 <= sx < self.image.width and 0 <= sy < self.image.height):
            return None
        return self.image.pixel(sx, sy)

    def values(self, x, y, w, h):
        key = x, y, w, h
        if key not in self.patches:
            values = [self.pixel(x+dx, y+dy) for dy in range(h) for dx in range(w)]
            self.patches[key] = None if any(v is None for v in values) else values
        return self.patches[key]

    def is_bg(self, rgb):
        if rgb not in self.rgb_cache:
            self.rgb_cache[rgb] = any(all(lo <= v <= hi for v, (lo, hi) in zip(rgb, m['bounds'])) for m in self.models)
        return self.rgb_cache[rgb]

    def patch_background(self, cx, cy, size=2):
        values = self.values(cx-size/2, cy-size/2, size, size)
        if values is None or not self.models:
            return None
        return any(all(all(lo <= v <= hi for v, (lo, hi) in zip(rgb, m['bounds'])) for rgb in values) for m in self.models)

    def face_background(self, first, second, outward):
        tx, ty = second[0]-first[0], second[1]-first[1]
        support, unknown = set(), False
        for i in range(12):
            q = .15+.7*i/11
            x, y = first[0]+q*tx+4*outward[0], first[1]+q*ty+4*outward[1]
            value = self.patch_background(x, y)
            if value is None:
                unknown = True
                continue
            if value:
                sx = int(self.room.x+(x+.5)*self.room.width/800)
                sy = int(self.room.y+(y+.5)*self.room.height/608)
                support.add((sx, sy))
        return len(support), unknown

    def triangle_transitions(self, type_id, x, y):
        size, direction = (16, type_id-4) if type_id > 6 else (32, type_id)
        poly = [(x+a*size/32, y+b*size/32) for a, b in VERTICES[direction]]
        cx, cy = sum(a for a, _ in poly)/3, sum(b for _, b in poly)/3
        rows = []
        for i, (ax, ay) in enumerate(poly):
            bx, by = poly[(i+1)%3]
            dx, dy = bx-ax, by-ay
            if not dx or not dy:
                continue
            length = hypot(dx, dy)
            nx, ny = -dy/length, dx/length
            outward = -1 if nx*(cx-ax)+ny*(cy-ay) > 0 else 1
            votes, unknown = set(), False
            for j in range(12):
                q = .15+.7*j/11
                px, py = ax+q*dx, ay+q*dy
                outer = self.patch_background(px+outward*4*nx, py+outward*4*ny)
                inner = self.patch_background(px-outward*4*nx, py-outward*4*ny)
                if outer is None or inner is None:
                    unknown = True
                    continue
                if outer and not inner:
                    sx = int(self.room.x+(px+.5)*self.room.width/800)
                    sy = int(self.room.y+(py+.5)*self.room.height/608)
                    votes.add((sx, sy))
            rows.append(dict(support=len(votes), unknown=unknown))
        return poly, rows


def add_boundary_primitives(image, room, spikes, potential, diag, *, source_context=None):
    field = MaterialBoundary(image, room, spikes, diag)
    candidates = {tuple(r['native']) for r in diag.get('rectangle_faces', [])}
    opposed, records = {}, []
    for x, y in sorted(candidates):
        faces = [field.face_background(a, b, n) for a, b, n in (
            ((x, y), (x+16, y), (0, -1)), ((x+16, y), (x+16, y+16), (1, 0)),
            ((x+16, y+16), (x, y+16), (0, 1)), ((x, y+16), (x, y), (-1, 0)))]
        opposed[x, y] = faces
        records.append(dict(native=[x, y], faces=faces))
    strips = set()
    for indices, dx, dy in (((1, 3), 0, 16), ((0, 2), 16, 0)):
        available = {p for p, f in opposed.items() if all(f[i][0] >= 9 and not f[i][1] for i in indices)}
        for p in sorted(available):
            if (p[0]-dx, p[1]-dy) in available:
                continue
            group, (x, y) = [], p
            while (x, y) in available:
                group.append((x, y))
                x += dx
                y += dy
            if len(group) >= 3:
                strips.update(group)
    original_bases, containers = [], []
    raw_field = rectangle_field(image, room, spikes, source_context)
    for st, sx, sy in sorted(set(spikes)):
        if not raw_field.triangle_closed(st, sx, sy):
            continue
        size, direction = (16, st-4) if st > 6 else (32, st)
        points = [(sx+a*size/32, sy+b*size/32) for a, b in VERTICES[direction]]
        original_bases.append((points[1], points[2]))
    for x, y in sorted(candidates):
        for w, h in ((32, 32), (32, 48), (48, 32)):
            cells = {(x+dx, y+dy) for dy in range(0, h, 16) for dx in range(0, w, 16)}
            if not cells <= candidates:
                continue
            faces = [field.face_background(a, b, n) for a, b, n in (
                ((x, y), (x+w, y), (0, -1)), ((x+w, y), (x+w, y+h), (1, 0)),
                ((x+w, y+h), (x, y+h), (0, 1)), ((x, y+h), (x, y), (-1, 0)))]
            corners = [(x, y), (x+w, y), (x+w, y+h), (x, y+h)]
            supported = []
            for i, (count, unknown) in enumerate(faces):
                first, second = corners[i], corners[(i+1)%4]
                aligned = any({first, second} == {a, b} for a, b in original_bases)
                supported.append((count >= 9 and not unknown) or aligned)
            if all(supported) and sum(count >= 9 and not unknown for count, unknown in faces) >= 3:
                containers.append(dict(box=[x, y, w, h], cells=sorted(cells), faces=faces))
                potential = potential | cells
    old_native = {tuple(p) for p in diag.get('native16_primitive', [])}
    return potential | strips, {**diag, 'native16_primitive': sorted(old_native | strips),
        'material_boundary_added_primitives': sorted(strips-set(potential)),
        'material_boundary_containers': containers, 'material_boundary_models': field.models,
        'material_boundary_faces': records, 'original_primitives_and_containers_preserved': True}


def boundary_primitives(image, room, spikes, *, source_context=None):
    potential, diag = container_primitives(image, room, spikes, source_context=source_context)
    return add_boundary_primitives(image, room, spikes, potential, diag, source_context=source_context)
