"""Frozen, disjoint original-source models for framed rectangular bodies.

Locators are hypotheses, not object labels. Four closed source faces and three
inside-owned border ridges qualify each teacher; three mutually matching,
nonoverlapping teachers qualify a model. Query bodies cannot teach themselves.
No emission, coordinate lookup, uniform-background assumption or private IO.
"""
from itertools import combinations
from math import dist, hypot, sqrt
from statistics import median

from scripts.source_glyph_prototypes import SourceGlyphLibrary
from scripts.source_rectangle_prototypes import _dot, _interior_signature, _qualified


def _overlaps(first, second):
    return abs(first[1]-second[1]) < 32 and abs(first[2]-second[2]) < 32


class SourceObjectFrames:
    def __init__(self, frame, original):
        self.frame, self.rows, self.models = frame, {}, []
        self.library = SourceGlyphLibrary(frame.original_snapshot(), frame.room, [], source_frame=frame)
        self.field = self.library.raw.raw.field
        teachers = []
        for x, y in sorted({(d.x, d.y) for d in original if d.type_id == 1}):
            row = self.measure(x, y)
            if row is None:
                continue
            body = self.body(x, y)
            rgb = tuple(median(v[c] for v in row['border_pixels']) for c in range(3))
            core = tuple(median(v[c] for v in body) for c in range(3))
            contrast = dist(rgb, core)
            if contrast <= 2*sqrt(3):
                continue
            owned = self.owned(row, rgb)
            if sum(v >= 9 for v in owned) >= 3:
                teachers.append(dict(key=(1, x, y), row=row, rgb=rgb, owned=owned,
                                     body=body, contrast=contrast))
        self.teacher_rows = teachers
        # Freeze the original cross-fitted triples BEFORE evaluating queries.
        remaining = list(teachers)
        while remaining:
            seed, *others = remaining
            chosen = None
            for a, b in combinations(others, 2):
                group = [seed, a, b]
                if any(_overlaps(p['key'], q['key'])
                       or _dot(p['row']['whole'], q['row']['whole']) < .9
                       or self.body_error(p['body'], q['body']) > .1*min(p['contrast'], q['contrast'])
                       for p, q in combinations(group, 2)):
                    continue
                chosen = group
                break
            if chosen is None:
                remaining = others
                continue
            identities = {p['key'] for p in chosen}
            remaining = [p for p in remaining if p['key'] not in identities]
            self.models.append(dict(teachers=tuple(p['key'] for p in chosen),
                whole=self.average([p['row']['whole'] for p in chosen]),
                body=tuple(tuple(median(p['body'][i][c] for p in chosen) for c in range(3))
                           for i in range(256)),
                contrast=min(p['contrast'] for p in chosen),
                border=tuple(median(p['rgb'][c] for p in chosen) for c in range(3))))

    @staticmethod
    def average(rows):
        mean = tuple(sum(r[i] for r in rows)/len(rows) for i in range(len(rows[0])))
        length = sqrt(sum(v*v for v in mean))
        return tuple(v/max(1e-12, length) for v in mean)

    def measure(self, x, y):
        if (x, y) in self.rows:
            return self.rows[x, y]
        self.rows[x, y] = None
        if not self.frame.rectangle_available(x, y, 32, 32, margin=4):
            return None
        corners = ((x, y), (x+32, y), (x+32, y+32), (x, y+32))
        faces = self.field.rectangle(x, y, 32)
        if _qualified(faces) < 4:
            ix, iy = .5*self.frame.pitch[0], .5*self.frame.pitch[1]
            inset = ((x+ix, y+iy), (x+32-ix, y+iy), (x+32-ix, y+32-iy), (x+ix, y+32-iy))
            candidate = [self.field.edge(inset[i], inset[(i+1)%4]) for i in range(4)]
            if _qualified(candidate) > _qualified(faces):
                corners, faces = inset, candidate
        if _qualified(faces) < 4 and 32 > 2*max(self.frame.pitch):
            ix, iy = self.frame.pitch
            inset = ((x+ix, y+iy), (x+32-ix, y+iy), (x+32-ix, y+32-iy), (x+ix, y+32-iy))
            candidate = [self.field.edge(inset[i], inset[(i+1)%4]) for i in range(4)]
            if _qualified(candidate) > _qualified(faces):
                corners, faces = inset, candidate
        if _qualified(faces) < 4:
            return None
        inner = _interior_signature(self.library, x, y)
        # A flat body can be informative under independently owned border ridges.
        samples, border_pixels = [], []
        for a, b in zip(corners, corners[1:]+corners[:1]):
            tx, ty = b[0]-a[0], b[1]-a[1]
            length = hypot(tx, ty)
            nx, ny = -ty/length, tx/length
            pitch = abs(nx)*self.frame.pitch[0]+abs(ny)*self.frame.pitch[1]
            edge = []
            for i in range(12):
                q = .15+.7*i/11
                px, py = a[0]+q*tx, a[1]+q*ty
                values = [self.frame.original_pixel(px+off*pitch*nx, py+off*pitch*ny)
                          for off in (.5, -1.5, 3.5)]
                if any(v is None for v in values):
                    return None
                edge.append((self.frame.original_position(px, py), *values))
                border_pixels.append(values[0])
            samples.append(edge)
        row = dict(key=(1, x, y), closed=4, samples=samples, border_pixels=border_pixels,
                   whole=self.library.signature(3, x, y), inner=inner)
        self.rows[x, y] = row
        return row

    @staticmethod
    def owned(row, rgb):
        counts = []
        for edge in row['samples']:
            sites = set()
            for position, inside, outside, core in edge:
                if position is not None and min(dist(outside, rgb), dist(core, rgb))-dist(inside, rgb) > 2*sqrt(3):
                    sites.add(position)
            counts.append(len(sites))
        return counts

    def body(self, x, y):
        return tuple(self.frame.original_pixel(x+4+(i+.5)*1.5, y+4+(j+.5)*1.5)
                     for j in range(16) for i in range(16))

    @staticmethod
    def body_error(first, second):
        return sqrt(sum(sum((x-y)**2 for x, y in zip(u, v)) for u, v in zip(first, second))/len(first))

    def support(self, x, y):
        row = self.measure(x, y)
        if row is None:
            return dict(passed=False, reason='no complete closed source frame')
        key, body, proofs = (1, x, y), self.body(x, y), []
        for model in self.models:
            if any(_overlaps(key, t) for t in model['teachers']):
                continue
            error = self.body_error(body, model['body'])
            if error > .1*model['contrast']:
                continue
            owned = self.owned(row, model['border'])
            if sum(v >= 9 for v in owned) >= 3:
                proofs.append(dict(original_teachers=model['teachers'], closed_source_faces=4,
                    owned=owned, body_error=error, contrast=model['contrast'], query_paint_template_not_required=True))
        return dict(passed=bool(proofs), proof=proofs, original_only=True,
                    query_disjoint_from_all_teachers=True, no_exterior_uniformity_assumption=True)
