"""Source contour ownership for competing native32/native16 hypotheses.

Existing detections locate small tests, not their answers. Independent mini
sides and a base locate two real smaller objects; exposed RGB slope absence
can reject an enclosing alias. Conversely, two strong full-size sides can
outvote a mini with a demonstrably missing side. Hidden, weak and color-only
contours abstain. No reference, palette or room identity enters detection.
"""

from array import array
from functools import lru_cache
from math import hypot, sqrt
from statistics import median

from .geometry import Box
from .image import RGBImage
from .spike_shape import SpikeShapeField, VERTICES, _could_have_strong_slopes as _native_bound
from .spike_source_stroke import mixin, could_have_stroke, material_matches
from .spike_source_ownership import rectangle_owns
from .spike_source_ownership import source_size_owns, tip_source_size_owns as _tip_owner
from .spike_color_evidence import QuantizedColorSlopeField


from .spike_source_corner import mixin as _corner_mixin
from .spike_source_local import mixin as _local_mixin, own_outline_score as _own_outline_score

class _CachedShapeField(SpikeShapeField):
    """Exact half-integer gradients, lazy in two bounded native buffers.

    Source neighborhoods revisit the same pixels for sides, bases and nearby
    alternatives. Two int16 buffers cost less than2MiB per field instead of a
    large tuple dictionary. Border/out-of-range semantics remain the parent's.
    """
    def __init__(self, image, room, *, native_size):
        super().__init__(image, room, native_size=native_size)
        self._gx = array('h', [32767]) * (800 * 608)
        self._gy = array('h', [32767]) * (800 * 608)

    def gradient(self, x, y):
        if not (0 <= x < 800 and 0 <= y < 608):
            return super().gradient(x, y)
        index = y * 800 + x
        if self._gx[index] == 32767:
            if 0 < x < 799 and 0 < y < 607:
                # Exact twice-central differences. Avoid four clamping pixel
                # calls for the common interior case; retain original border
                # and out-of-frame semantics.
                self._gx[index] = self.pixels[index + 1] - self.pixels[index - 1]
                self._gy[index] = self.pixels[index + 800] - self.pixels[index - 800]
            else:
                gx, gy = super().gradient(x, y)
                self._gx[index], self._gy[index] = int(gx * 2), int(gy * 2)
        return self._gx[index] / 2, self._gy[index] / 2

    def pixel(self, x, y):
        if 0 <= x < 800 and 0 <= y < 608:
            return self.pixels[y * 800 + x]
        return super().pixel(x, y)

def _contour_channel(
    image: RGBImage, room: Box,
    spikes: list[tuple[int, int, int]],
    solids: list[tuple[int, int, int, int]],
    *, field_factory=None, stroke_mode=False, owns=None, rectangle_owner=None,
    source_seed_fn=None, joined_closure=None, source_evidence=None, material_conflict=None,
) -> tuple[set[tuple[int, int, int]], set[tuple[int, int, int]]]:
    """Return source-supported additions and unsupported size hypotheses.

    Test two mini origins per ambiguous full, then closed miniature contours
    near independently source-localized existing hypotheses. Reuse lazy fields
    and patch metrics; no scanner rerun or reference input. Newly added objects
    never supply evidence for another addition, deletion or material witness.
    """
    present = set(spikes)
    fulls = sorted(k for k in present if 3 <= k[0] <= 6)
    minis = sorted(k for k in present if 7 <= k[0] <= 10)
    fields: dict[int, SpikeShapeField] = {}
    rgb = None
    added: set[tuple[int, int, int]] = set()
    rejected: set[tuple[int, int, int]] = set()
    # Only identical field views share these scalar facts. Closure/rival
    # decisions remain channel-local: a joined contour changes their meaning.
    evidence = {} if source_evidence is None else source_evidence
    bases = evidence.setdefault('bases', {})
    base_runs = evidence.setdefault('base_runs', {})
    polarities = evidence.setdefault('polarities', {})
    boundary_sides = evidence.setdefault('boundary_sides', {})
    source_boundary_sides = evidence.setdefault('source_boundary_sides', {})

    def field(size):
        if size not in fields:
            fields[size] = (field_factory(size) if field_factory else
                            _CachedShapeField(image, room, native_size=size))
        return fields[size]

    def color():
        nonlocal rgb
        if rgb is None:
            rgb = QuantizedColorSlopeField(image, room)
        return rgb

    def clear(points):
        return all(0 <= x < 800 and 0 <= y < 608
                   and not any(bx <= x < bx + w and by <= y < by + h
                               for bx, by, w, h in solids)
                   for x, y in points)

    def base_score(x, y, d, size=16):
        key = size, x, y, d
        if key in bases:
            return bases[key]
        f = field(size)
        _, first, second = f.vertices[d]
        tx, ty = second[0] - first[0], second[1] - first[1]
        length = hypot(tx, ty)
        nx, ny = -ty / length, tx / length
        scale, spread = f.patch_stats(x, y)
        hits = 0
        current = longest = 0
        for i in range(12):
            # Corner joins belong to the diagonals. A short, independent
            # middle-base stroke can close an outlined diamond even when
            # equal fills on its two sides have no across-base color step.
            t = .3 + .4 * i / 11
            px, py = x + first[0] + t * tx, y + first[1] + t * ty
            found = False
            for offset in (-2, -1, 0, 1, 2):
                gx, gy = f.gradient(round(px + offset * nx), round(py + offset * ny))
                magnitude = hypot(gx, gy)
                if (magnitude >= max(scale * .25, spread * .15)
                        and abs(gx * nx + gy * ny) >= magnitude * .95):
                    hits += 1
                    found = True
                    break
            current = current + 1 if found else 0
            longest = max(longest, current)
        base_runs[key] = longest / 12
        bases[key] = hits / 12
        return bases[key]

    @lru_cache(maxsize=None)
    def closed(k, *, size=16, cutoff=11 / 12, source_only=False, independent_base=False):
        t, x, y = k
        d = t - 4 if size == 16 else t
        if not (4 <= x <= 796 - size and 4 <= y <= 604 - size):
            return False
        if not source_only and any(max(x, bx) < min(x + size, bx + w)
               and max(y, by) < min(y + size, by + h) for bx, by, w, h in solids):
            return False
        f = field(size)
        if f.localized_score(x, y, d) < cutoff or f.patch_stats(x, y)[1] < 12:
            return False
        if base_score(x, y, d, size) >= .5 and (
                not independent_base or base_runs[size, x, y, d] >= .5):
            return True
        if size != 16:
            return False
        if joined_closure is not None and joined_closure(k):
            return True
        # A miniature's base can join the opposite full's independently
        # closed base. Its two visible slopes still own its size and origin.
        # Nothing inside a larger triangle or merely near it is a join.
        opposite = {3: 6, 6: 3, 4: 5, 5: 4}[d]
        origins = {
            3: [(x + shift, y + 16) for shift in (-16, -8, 0)],
            6: [(x + shift, y - 32) for shift in (-16, -8, 0)],
            4: [(x - 32, y + shift) for shift in (-16, -8, 0)],
            5: [(x + 16, y + shift) for shift in (-16, -8, 0)],
        }[d]
        mini_polarity = polarity(x, y, d, 16)
        if abs(mini_polarity) < .2:
            return False
        return any(_could_have_strong_slopes(field(32), fx, fy, opposite)
                   and closed((opposite, fx, fy), size=32, source_only=source_only)
                   and abs(polarity(fx, fy, opposite, 32)) >= .2
                   and polarity(fx, fy, opposite, 32) * mini_polarity > 0
                   for fx, fy in origins)

    def polarity(x, y, d, size):
        # A fixed native2px across-edge sample sees a narrow outlined stroke
        # as well as a filled boundary. Full-size's old size/8 sample can skip
        # a perfectly visible thin line and find equal fills on both sides.
        key = size, x, y, d
        if key not in polarities:
            f = field(size)
            tip, *ends = f.vertices[d]
            cx = sum(p[0] for p in f.vertices[d]) / 3
            cy = sum(p[1] for p in f.vertices[d]) / 3
            values = []
            for end in ends:
                tx, ty = end[0] - tip[0], end[1] - tip[1]
                nx, ny = -ty, tx
                if nx * (cx - (tip[0] + end[0]) / 2) + ny * (cy - (tip[1] + end[1]) / 2) > 0:
                    nx, ny = -nx, -ny
                length = hypot(nx, ny)
                nx, ny = nx / length, ny / length
                for i in range(10):
                    q = .2 + .6 * i / 9
                    px, py = x + tip[0] + q * tx, y + tip[1] + q * ty
                    outer = sum(f.pixel(round(px + j * nx), round(py + j * ny))
                                for j in (2, 3, 4)) / 3
                    inner = sum(f.pixel(round(px - j * nx), round(py - j * ny))
                                for j in (0, 1, 2)) / 3
                    values.append(outer - inner)
            polarities[key] = median(values) / f.patch_stats(x, y)[1]
            boundary_sides[key] = tuple(median(values[i:i + 10]) / f.patch_stats(x, y)[1]
                                        for i in (0, 10))
        if key not in source_boundary_sides:
            source_boundary_sides[key] = boundary_sides[key]
        if stroke_mode:
            signature = field(size).stroke(x, y, d)
            if signature['score'] >= 11 / 12:
                polarities[key] = signature['contrast']
                boundary_sides[key] = (signature['contrast'], signature['contrast'])
        return polarities[key]

    def absent_side(x, y, d, size, side, *, leading=False, partial_boundary=False):
        f = field(size)
        c = color()
        tip, *ends = f.vertices[d]
        end = ends[side]
        tx, ty = end[0] - tip[0], end[1] - tip[1]
        length = hypot(tx, ty)
        nx, ny = -ty / length, tx / length
        samples, possible = 0, 0
        # Negative evidence must not use a neighboring full's high gradient
        # percentile to hide a weaker real RGB-only mini boundary. A central
        # RGB difference's six channel components have total quantization
        # error squared <=6*(.5**2). Anything above that bound can protect a
        # possible direction, even when too weak to add a new object.
        minimum = 1.5
        strong_minimum = (c.patch_scale(x, y) * .25) ** 2
        ratio = sqrt(1 - .95 ** 2) / .95
        weak_vectors = []
        for i in range(12):
            t = .15 + (.25 if leading else .70) * i / 11
            px, py = x + tip[0] + t * tx, y + tip[1] + t * ty
            points = [(round(px + offset * nx), round(py + offset * ny))
                      for offset in range(-4, 5)]
            if not clear(points):
                continue
            samples += 1
            compatible = []
            strong = False
            for sx, sy in points[2:7]:
                gx, gy = c.gradient(sx, sy)
                magnitude_squared = sum(a*a + b*b for a, b in zip(gx, gy))
                if magnitude_squared <= minimum:
                    continue
                vector = tuple(a*nx + b*ny for a, b in zip(gx, gy))
                normal = sqrt(sum(a*a for a in vector))
                tangent = sqrt(sum((-a*ny + b*nx)**2 for a, b in zip(gx, gy)))
                # Non-border central differences: each endpoint is rounded
                # to8 bits. Possible RGB directions preserve that uncertainty.
                error = sqrt(3) * .5 * (abs(nx) + abs(ny))
                if max(0, tangent - error) <= (normal + error) * ratio:
                    compatible.append((normal, vector))
                    strong = strong or magnitude_squared >= strong_minimum
            possible += strong
            weak_vectors.append(max(compatible)[1] if compatible else (0., 0., 0.))
        if samples < 10 or possible / samples > .25:
            return False
        if partial_boundary:
            # A direction refit may compete with a partly visible, weaker RGB
            # object. Four coherent necessary-side samples protect that visible
            # part; they need not describe two thirds of an occluded contour.
            # This stricter abstention is not applied to existing size vetoes.
            # A nearby strong luminance edge on the new contour can supply
            # quantization-compatible old directions at a few crossings. This
            # extra partial safeguard concerns color-dominant transitions, not
            # those already rejected by the old luminance-side test.
            vectors = [v for v in weak_vectors if any(v)
                       and abs(.299*v[0] + .587*v[1] + .114*v[2])
                       <= .25 * sqrt(sum(a*a for a in v))]
            if any(sum(abs(sum(a * b for a, b in zip(v, w)))
                       >= .9 * sqrt(sum(a*a for a in v) * sum(b*b for b in w))
                       for w in vectors) >= 4 for v in vectors):
                return False
        # Weak real RGB edges keep a consistent signed channel transition
        # along the slope. Random texture/quantization-compatible directions
        # must not be promoted to geometry, but a coherent weaker boundary
        # must also not be erased merely by the stronger surrounding full.
        center = tuple(median(v[k] for v in weak_vectors) for k in range(3))
        center_norm = sqrt(sum(a*a for a in center))
        coherent = sum(sum(a*b for a, b in zip(v, center))
                       >= .9 * center_norm * sqrt(sum(a*a for a in v))
                       for v in weak_vectors if any(v))
        return center_norm ** 2 <= minimum or coherent / samples < 2 / 3

    for d, x, y in fulls:
        if not (4 <= x <= 764 and 4 <= y <= 572):
            continue
        f = field(32)
        sides = f.side_scores(x, y, d)
        if max(sides) >= .75:
            continue
        positions = ({3: ((x, y + 16), (x + 16, y + 16)),
                      6: ((x, y), (x + 16, y)),
                      4: ((x, y), (x, y + 16)),
                      5: ((x + 16, y), (x + 16, y + 16))}[d])
        pair = [(d + 4, px, py) for px, py in positions]
        if not all(closed(k) for k in pair):
            continue
        added.update(k for k in pair if k not in present)
        # A real half-embedded full has a supported side or hidden leading
        # samples. A weak full score alone does not establish its absence.
        if (f.patch_stats(x, y)[1] >= 12
                and all(absent_side(x, y, d, 32, i, leading=True) for i in (0, 1))):
            rejected.add((d, x, y))

    for t, mx, my in minis:
        d = t - 4
        containing = [(fd, x, y) for fd, x, y in fulls if fd == d
                      and x <= mx and mx + 16 <= x + 32
                      and y <= my and my + 16 <= y + 32]
        if not containing or not (4 <= mx <= 780 and 4 <= my <= 588):
            continue
        if not any(field(32).score(x, y, d) >= 11 / 12
                   and field(32).patch_stats(x, y)[1] >= 12
                   and abs(field(32).contrast(x, y, d)) >= .5
                   for _, x, y in containing):
            continue
        possible = color().possible_side_scores(mx, my, field(16).vertices[d])
        if any(possible[i] <= .25 and absent_side(mx, my, d, 16, i) for i in (0, 1)):
            rejected.add((t, mx, my))

    # Existing locations only bound source tests. Evaluate all directions at
    # those locations: an incorrect coarse label is not a material witness.
    # Native16/32 alternatives can correct a direction from source evidence,
    # but only with a unique closed contour and two observably absent old sides.
    witnesses = []
    witness_materials = {}
    for t, x, y in sorted(present):
        size = 16 if t > 6 else 32
        old = t - 4 if size == 16 else t
        f = field(size)
        scores = sorted((f.localized_score(x, y, d), d) for d in VERTICES)
        score, direction = scores[-1]
        candidate = (direction + 4 if size == 16 else direction, x, y)
        if (score - scores[-2][0] < .25
                or not closed(candidate, size=size, cutoff=.75 if size == 16 else 11 / 12,
                              source_only=True)):
            continue
        contrast = polarity(x, y, direction, size)
        if abs(contrast) < .2:
            continue
        full_overlap = size == 16 and any(
            max(x, fx) < min(x + 16, fx + 32)
            and max(y, fy) < min(y + 16, fy + 32)
            and field(32).localized_score(fx, fy, fd) >= 11 / 12
            for fd, fx, fy in fulls)
        # Material and outline ink remain different quantities. A real
        # full's pure gradient geometry can independently support its size
        # and direction; stroke-only amplitude cannot forge that geometry.
        signed_boundary = size == 16 or (
            min(abs(s) for s in source_boundary_sides[32, x, y, direction]) >= .2
            and source_boundary_sides[32, x, y, direction][0]
                * source_boundary_sides[32, x, y, direction][1] > 0)
        pure_closed_full = (size == 32
            and _CachedShapeField.localized_score(f, x, y, direction) >= 11 / 12
            and min(f.side_scores(x, y, direction)) >= 11 / 12
            and base_score(x, y, direction, size) >= .5)
        full_boundary = signed_boundary or pure_closed_full
        if (direction != old and (t, x, y) not in rejected and full_boundary
                and closed(candidate, size=size, cutoff=.75 if size == 16 else 11 / 12)
                and max(f.side_scores(x, y, old)) <= .25 and not full_overlap
                and all(absent_side(x, y, old, size, side, partial_boundary=True)
                        for side in (0, 1))):
            if candidate not in present:
                added.add(candidate)
            rejected.add((t, x, y))
        if score >= 11 / 12 and abs(contrast) >= .2:
            witnesses.append((x, y, contrast > 0))
            if stroke_mode:
                witness_materials[x, y] = field(size).stroke(x, y, direction)

    # Short/zigzag or isolated contours need not form a straight three-object
    # run. Bounded 8px neighborhoods handle half-phase native16 objects. Every
    # new box still needs BOTH localized slopes, its own middle base and an
    # unambiguous origin/direction. Material polarity is local, not a fixed hue
    # or a global assumption that all foreground is bright/dark.
    # A source-only location witness does not authorize an emission or prove
    # absence behind a solid mask. Coarse terrain can be wrong without hiding
    # the independently closed source contour from neighborhood calibration.
    # Repeated coarse aliases at one source origin must not weight polarity.
    witnesses = sorted(set(witnesses))
    positions = {(sx + dx, sy + dy) for sx, sy, _ in witnesses
                 for dx in range(-64, 65, 8) for dy in range(-64, 65, 8)
                 if 4 <= sx + dx <= 780 and 4 <= sy + dy <= 588}
    if source_seed_fn is not None:
        positions.update(source_seed_fn(field(16), witnesses))
    for x, y in sorted(positions):
        if any(abs(x - mx) <= 8 and abs(y - my) <= 8 for _, mx, my in minis):
            continue
        nearby = sorted((hypot(x - sx, y - sy), sx, sy, sign)
                        for sx, sy, sign in witnesses if hypot(x - sx, y - sy) <= 96)[:5]
        for direction in VERTICES:
            f = field(16)
            if not _could_have_strong_slopes(f, x, y, direction):
                continue
            candidate = (direction + 4, x, y)
            if not closed(candidate, independent_base=True):
                continue
            contrast = polarity(x, y, direction, 16)
            sides = boundary_sides[16, x, y, direction]
            # A texture stroke on one side must not borrow the other actual
            # object's boundary to pass an aggregate contrast statistic.
            if stroke_mode:
                signature = f.stroke(x, y, direction)
                if signature['score'] < 11 / 12 or not material_matches(
                        x, y, signature, nearby, witness_materials):
                    continue
            elif ((min(abs(s) for s in sides) < .2 or sides[0] * sides[1] <= 0
                    or abs(contrast) < .2 or not nearby
                    or sum(sign == (contrast > 0) for _, _, _, sign in nearby) / len(nearby) < .8)
                    and not (joined_closure is not None and (
                        (f.localized_score(x, y, direction) == 1.0
                            and base_score(x, y, direction, 16) == 1.0
                            and base_runs[16, x, y, direction] == 1.0)
                        or joined_closure(candidate)))
                    and not (isinstance(f, _LocalField) and nearby
                        and f.localized_score(x, y, direction) >= 11 / 12
                        and base_score(x, y, direction, 16) >= .5
                        and base_runs[16, x, y, direction] >= .5
                        and _own_outline_score(f, x, y, direction) >= 11 / 12)):
                continue
            # Strong closure can trace a background gap. Only the extra
            # channel uses independently qualified ORIGINAL local material
            # contradiction; never apply this veto to existing/old channels.
            if material_conflict is not None and material_conflict(contrast, nearby):
                continue
            if any(closed((other + 4, x + dx, y + dy), independent_base=True)
                   for dx in (-8, 0, 8) for dy in (-8, 0, 8) for other in VERTICES
                   if (dx, dy, other) != (0, 0, direction)):
                continue
            # A closed smaller contour can be interior sprite artwork.
            # Compare independent source-native sizes, not the coarse label.
            # This vetoes NEW contained proposals; existing minis keep their
            # own RGB/occlusion protection and genuine joins remain outside.
            if any(_could_have_strong_slopes(field(32), x + dx, y + dy, direction)
                   and (closed((direction, x + dx, y + dy), size=32)
                        or (owns is not None and owns(candidate, (direction, x + dx, y + dy))))
                   for dx in (-16, -8, 0) for dy in (-16, -8, 0)):
                continue
            if rectangle_owner is not None and rectangle_owner(candidate):
                continue
            if candidate not in present:
                added.add(candidate)
    return added, rejected

_StrokeField = mixin(_CachedShapeField)
_CornerField = _corner_mixin(_CachedShapeField)
_LocalField = _local_mixin(_CornerField)
_LocalField.own_outline = _StrokeField.stroke

def _legacy_could_have_strong_slopes(field, x, y, direction):
    return (_native_bound(field, x, y, direction)
            or isinstance(field, _StrokeField) and could_have_stroke(field, x, y, direction))

def _bind_corner_slopes(corner_class, old_bound):
 def bound(field,x,y,d):
  return field.could_have_strong_slopes(x,y,d) if isinstance(field,corner_class) else old_bound(field,x,y,d)
 return bound

_could_have_strong_slopes = _bind_corner_slopes(_CornerField, _legacy_could_have_strong_slopes)

def contour_size_changes(image, room, spikes, solids, *,
                         _context_callback=None, _local_evidence=None):
    fields, strokes, corners = {}, {}, {}
    def field(size):
        if size not in fields:
            fields[size] = _CachedShapeField(image, room, native_size=size)
        return fields[size]
    def stroke_field(size):
        if size not in strokes:
            view = _StrokeField.__new__(_StrokeField)
            view.__dict__.update(field(size).__dict__)
            view.stroke_cache, view.profile_templates = {}, {}
            strokes[size] = view
        return strokes[size]
    def corner_field(size):
        if size not in corners:
            view = _CornerField.__new__(_CornerField)
            view.__dict__.update(field(size).__dict__)
            view.scores, view.sides, view.localized_scores = {}, {}, {}
            corners[size] = view
        return corners[size]
    local_fields = {}
    def local_field(size):
        if size != 16:
            return corner_field(size)
        if size not in local_fields:
            view = _LocalField.__new__(_LocalField)
            view.__dict__.update(corner_field(size).__dict__)
            view.edge_local_scores, view.edge_local_statistics = {}, {}
            local_fields[size] = view
        return local_fields[size]
    ownership = dict(field=field, solids=solids, materials={}, rectangles={})
    tip_state = dict(**ownership, tip_materials={})
    owns_tip = lambda mini, parent: _tip_owner(tip_state, mini, parent)
    owns = lambda mini, parent: source_size_owns(ownership, mini, parent)
    rect = lambda mini: rectangle_owns(ownership, mini)
    old_a, old_r = _contour_channel(image, room, spikes, solids, field_factory=field)
    ink_a, ink_r = _contour_channel(image, room, spikes, solids, field_factory=stroke_field,
        stroke_mode=True, owns=owns, rectangle_owner=rect)
    corner_a, corner_r = _contour_channel(image, room, spikes, solids, field_factory=corner_field,
        owns=owns_tip, rectangle_owner=rect)
    # Every new mini from the extra channel, including alias split pairs,
    # must have independent source-size/frame ownership protection.
    safe = set()
    for k in corner_a:
        t, x, y = k
        if t <= 6 or (not rect(k) and not any(owns_tip(k,(t-4,x+dx,y+dy))
                for dx in(-16,-8,0) for dy in(-16,-8,0))):
            safe.add(k)
    # A newly proven alias split cannot remove its old hypothesis if any of
    # that channel's associated new geometry failed independent ownership.
    denied = corner_a - safe
    corner_r = {k for k in corner_r if not any(
        abs(k[1]-m[1])<=32 and abs(k[2]-m[2])<=32 for m in denied)}
    local_a, _ = _contour_channel(image, room, spikes, solids,
        field_factory=local_field, owns=owns_tip, rectangle_owner=rect,
        source_evidence=_local_evidence)
    local_safe = {k for k in local_a if k[0] > 6
        and not any(t > 6 and (sx, sy) == k[1:] for t, sx, sy in spikes)
        and not rect(k) and not any(owns_tip(k, (k[0]-4, k[1]+dx, k[2]+dy))
            for dx in (-16,-8,0) for dy in (-16,-8,0))}
    added = old_a | ink_a | safe | local_safe
    if _context_callback is not None:
        _context_callback((field, stroke_field, local_field, ownership, tip_state))
    return added, (old_r | ink_r | corner_r) - added


def source_seed_size_changes(image, room, spikes, solids):
    """Candidate shared-source recovery; not wired into the scanner yet.

    Preserve every original channel decision and qualify only extra minis.
    Original and extended local channels reuse scalar source measurements,
    but their closure/rival decisions deliberately remain independent.
    """
    from .spike_source_growth import (
        LargerSourceOwner, JoinedMiniClosure, native_source_seeds, source_material_conflicts)

    context = []
    evidence = {}
    base_added, base_rejected = contour_size_changes(
        image, room, spikes, solids, _context_callback=context.append,
        _local_evidence=evidence)
    field, stroke, local, ownership, tip_state = context[0]
    rgb = None

    def color():
        nonlocal rgb
        if rgb is None:
            rgb = QuantizedColorSlopeField(image, room)
        return rgb

    owns = lambda mini, parent: _tip_owner(tip_state, mini, parent)
    rect = lambda mini: rectangle_owns(ownership, mini)
    joined = JoinedMiniClosure(local, solids)
    extra, _ = _contour_channel(
        image, room, spikes, solids, field_factory=local,
        owns=owns, rectangle_owner=rect, source_seed_fn=native_source_seeds,
        joined_closure=joined.closed, source_evidence=evidence,
        material_conflict=source_material_conflicts)
    normalized_full = None

    def full_local_field():
        nonlocal normalized_full
        if normalized_full is None:
            view = _LocalField.__new__(_LocalField)
            view.__dict__.update(field(32).__dict__)
            view.edge_local_scores, view.edge_local_statistics = {}, {}
            normalized_full = view
        return normalized_full

    owner = LargerSourceOwner(spikes, field, stroke, color, ownership,
                              normalized_full=full_local_field)
    original_mini_origins = {(x, y) for t, x, y in spikes if t > 6}
    eligible = {k for k in extra - base_added if k[0] > 6
                and k[1:] not in original_mini_origins
                and not rect(k) and not any(owns(k, (k[0] - 4, k[1] + dx, k[2] + dy))
                    for dx in (-16, -8, 0) for dy in (-16, -8, 0))}
    new = {k for k in eligible if not owner.owns(k)}
    return base_added | new, base_rejected - new
