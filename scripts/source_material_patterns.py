"""Explicit intrinsic/local/distributed original-source terrain appearance.

Newly accepted cells never become teachers. Flat-water negatives, primitive
geometry, source-confirmed glyph teacher exclusions and independent regions remain
separate safeguards. This experimental stage is not bound to scanner defaults.
"""
from math import sqrt

from PIL import Image
from jtool_scanner import scanner
from scripts.source_glyph_prototypes import SourceGlyphEvidence, SourceGlyphLibrary
from scripts.source_material_evidence import (
    BackingCoreRoles, boundary_primitives, container_primitives, rectangle_field,
)


class _NewCellEvidence:
    """Higher-confidence original teachers for NEW mini growth, not calibration.

    Keeping these channels separate matters: withdrawing uncertain material from
    full-pose calibration can undo real narrow/hollow terrain corrections. A
    correlated texture is still useful calibration, but is not object identity.
    """

    def __init__(self, field, pixels, nearest, selected, containers=()):
        self.field, self.pixels = field, pixels
        self.nearest, self.selected = nearest, selected
        self.glyphs = SourceGlyphEvidence(field.image, field.room,
            contour_field=field.contours)
        self.membership, self.rectangles = {}, {}
        # These containers are independently bounded in the ORIGINAL source;
        # their cells are not newly emitted terrain or reference-map answers.
        self.background_bounded = {tuple(point) for container in containers
            if sum(count >= 9 and not unknown for count, unknown in container['faces']) >= 3
            for point in container['cells']}

    def majority(self, point):
        if point not in self.membership:
            x, y = point
            values = [tuple(self.pixels[((y+py)*800+x+px)*3:((y+py)*800+x+px)*3+3])
                      for py in range(2, 14) for px in range(2, 14)]
            count = sum(self.nearest(v) in self.selected for v in values)
            # Patterned terrain can split its interior evenly between material
            # and dark texture. Only independent geometry may corroborate a tie.
            self.membership[point] = count >= (72 if point in self.background_bounded else 73)
        return self.membership[point]

    def closed_rectangle(self, point):
        if point in self.rectangles:
            return self.rectangles[point]
        x, y = point
        result = min(self.field.box_faces(x, y)) >= 9
        if not result:
            pitch_x, pitch_y = 800/self.field.room.width, 608/self.field.room.height
            for ox in (x-16, x):
                for oy in (y-16, y):
                    nominal = self.field.contours.rectangle(ox, oy, 32)
                    # One source-pixel phase may complete ONE weak face. It may
                    # not turn an otherwise weak background grid into a frame.
                    if sum(f.support >= 9 and not f.unknown for f in nominal) < 3:
                        continue
                    for dx in (0, -pitch_x, pitch_x):
                        for dy in (0, -pitch_y, pitch_y):
                            if not (0 <= ox+dx <= 768 and 0 <= oy+dy <= 576):
                                continue
                            faces = self.field.contours.rectangle(ox+dx, oy+dy, 32)
                            if all(f.support >= 9 and not f.unknown for f in faces):
                                result = True
                                break
                        if result:
                            break
                    if result:
                        break
                if result:
                    break
        self.rectangles[point] = result
        return result

    def rectangular_teacher(self, point):
        if self.closed_rectangle(point):
            return True
        faces = self.field.box_faces(*point)
        if max(min(faces[0], faces[2]), min(faces[1], faces[3])) < 9:
            return False
        # Joined triangles can borrow a neighboring base as an opposing edge.
        # Existing locators need not identify every constituent for raw source
        # geometry/body/exterior evidence to disqualify a teacher.
        return not any(self.glyphs.owner(t, *point) is not None for t in (7, 8, 9, 10))

    def seeds(self, models, pattern, mode):
        seeds = []
        for seed, group in models:
            if pattern(*seed)['flat']:
                seeds.append(seed)
                continue
            witnessed = [p for p in group if self.majority(p) or self.closed_rectangle(p)]
            enough_regions = mode != 'distributed' or len({(x//32, y//32) for x, y in witnessed}) >= 3
            bounded = {p for p in witnessed if p in self.background_bounded and self.majority(p)}
            bounded_regions = {(x//32, y//32) for x, y in bounded}
            # A raw16 rectangle is not required inside every larger patterned
            # source container. Three independent original peers remain needed.
            bounded_model = len(bounded) >= 3 and (mode != 'distributed' or len(bounded_regions) >= 3)
            # The image edge can hide the exterior of one peer. This is not an
            # interior gap-fill rule: keep three original appearance witnesses,
            # two independently bounded regions, and refuse unsupported interior
            # peers. The band is one native full-object width, not a room identity.
            border_bridge = (len(group) >= 3
                and len({(x//32, y//32) for x, y in group}) >= 3
                and len(bounded) >= 2 and len(bounded_regions) >= 2
                and all(p in bounded or p[0] < 32 or p[1] < 32 or p[0] >= 768 or p[1] >= 576
                        for p in group))
            rectangular_model = any(self.rectangular_teacher(p) for p in witnessed)
            if border_bridge or (len(witnessed) >= 3 and enough_regions and (rectangular_model or bounded_model)):
                seeds.append(seed if border_bridge or seed in witnessed else min(witnessed))
        return seeds


def eligible_primitives(image, room, spikes, *, source_context=None):
    if source_context is not None and isinstance(spikes, (list, tuple)):
        return source_context.material_result(image, room, spikes, 'eligible', (),
            lambda: _eligible_primitives(image, room, spikes, source_context=source_context))
    return _eligible_primitives(image, room, spikes, source_context=source_context)


def _eligible_primitives(image, room, spikes, *, source_context=None):
    primitive, diag = boundary_primitives(image, room, spikes, source_context=source_context)
    library = (SourceGlyphLibrary(image, room, spikes) if source_context is None else
               source_context.glyph_library(image, room, spikes))
    verified = []
    for type_id, x, y in sorted(set(spikes)):
        size = 16 if type_id > 6 else 32
        for direction in (3, 4, 5, 6):
            key = direction+(4 if size == 16 else 0), x, y
            proof = library.support(*key)
            if proof['passed']:
                verified.append(dict(key=key, size=size, proof=proof))
    rejected = []
    for x, y in sorted(primitive):
        glyphs = [v['key'] for v in verified
                  if max(x, v['key'][1]) < min(x+16, v['key'][1]+v['size'])
                  and max(y, v['key'][2]) < min(y+16, v['key'][2]+v['size'])]
        if glyphs:
            rejected.append(dict(native=(x, y), source_confirmed_glyphs=glyphs))
    blocked = {tuple(r['native']) for r in rejected}
    return primitive-blocked, {**diag, 'source_pattern_teacher_exclusions': rejected,
                              'teaching_only_no_existing_geometry_removal': True}


def pattern_cells(image, room, spikes, water_boxes=(), *, mode='intrinsic', source_context=None):
    """Return independently source-taught16px cells and full diagnostic evidence.

    Modes are algorithm stages, not room identities. Intrinsic evidence retains
    its original appearance-connected/first-model behavior; local/distributed
    modes use geometry connectivity/multiple roles and filtered teacher evidence.
    """
    if mode not in ('intrinsic', 'local', 'distributed'):
        raise ValueError('Pattern mode must be intrinsic, local or distributed')
    # Stateful iterables retain their uncached behavior. Original pipeline inputs
    # are snapshots; copying overlay coordinates prevents later list mutation
    # from relabelling an already-computed water-sensitive proof.
    if source_context is not None and isinstance(spikes, (list, tuple)) and isinstance(water_boxes, (list, tuple)):
        settings = tuple(tuple(box) for box in water_boxes)
        return source_context.material_result(image, room, spikes, mode, settings,
            lambda: _pattern_cells(image, room, spikes, settings, mode=mode, source_context=source_context))
    return _pattern_cells(image, room, spikes, water_boxes, mode=mode, source_context=source_context)


def _pattern_cells(image, room, spikes, water_boxes=(), *, mode='intrinsic', source_context=None):
    intrinsic = mode == 'intrinsic'
    provider = container_primitives if intrinsic else eligible_primitives
    primitive, diagnosis = provider(image, room, spikes, source_context=source_context)
    native16_primitive = set(map(tuple, diagnosis.get('native16_primitive', [])))
    if not primitive:
        return set(), {**diagnosis, 'models': []}
    centers = [scanner._ColorProfile(c['r'], c['g'], c['b'], 0.) for c in diagnosis['cluster_centers']]
    selected = set(diagnosis['selected_clusters'])
    field = rectangle_field(image, room, spikes, source_context)
    if source_context is None:
        source = Image.frombytes('RGB', (image.width, image.height), image.data)
        raw = source.crop((room.x, room.y, room.right, room.bottom)).resize((800, 608), Image.Resampling.BILINEAR).tobytes()
    else:
        raw = source_context.native_pixels(image, room)
    cache = {}

    def nearest(value):
        return min(range(len(centers)), key=lambda c:
                   sum((value[k]-(centers[c].avg_r, centers[c].avg_g, centers[c].avg_b)[k])**2 for k in range(3)))

    def pattern(x, y):
        key = x, y
        if key in cache:
            return cache[key]
        values = []
        for py in range(2, 14):
            for px in range(2, 14):
                offset = ((y+py)*800+x+px)*3
                values.append((px-7.5, py-7.5, tuple(raw[offset:offset+3])))
        mean = tuple(sum(v[k] for _, _, v in values)/144 for k in range(3))
        dx, dy = sum(px*px for px, _, _ in values), sum(py*py for _, py, _ in values)
        sx = tuple(sum(px*v[k] for px, _, v in values)/dx for k in range(3))
        sy = tuple(sum(py*v[k] for _, py, v in values)/dy for k in range(3))
        residual = tuple(v[k]-mean[k]-sx[k]*px-sy[k]*py for px, py, v in values for k in range(3))
        length = sqrt(sum(v*v for v in residual))
        energy = length/sqrt(144)
        core = field.color(x+4, y+4, 8)
        label = nearest((core.avg_r, core.avg_g, core.avg_b))
        separation = min(scanner._color_profile_distance(centers[label], c)
                         for i, c in enumerate(centers) if i not in selected)
        flat = energy <= .05*separation
        signature = tuple(v/max(1e-12, length) for v in residual)
        membership = (sum(nearest(v) in selected for _, _, v in values)/144 if flat else 1.) if label in selected else 0.
        cache[key] = dict(label=label, flat=flat, energy=energy, separation=separation,
                          signature=signature, membership=membership)
        return cache[key]

    def matches(a, b):
        if a['label'] != b['label'] or a['flat'] != b['flat']:
            return False
        if a['flat']:
            return min(a['membership'], b['membership']) >= .9
        return sum(x*y for x, y in zip(a['signature'], b['signature'])) >= .9

    unseen, groups = set(primitive), []
    while unseen:
        first = min(unseen)
        unseen.remove(first)
        group, pending = {first}, [first]
        while pending:
            p = pending.pop()
            for q in scanner._axis_neighbors(p, 16):
                if q in unseen and (not intrinsic or matches(pattern(*p), pattern(*q))):
                    unseen.remove(q)
                    group.add(q)
                    pending.append(q)
        if len(group) >= 3:
            groups.append(sorted(group))
    roles = None
    if mode == 'distributed':
        roles = BackingCoreRoles(field)
        eligible = {p for p in primitive if roles.eligible(*p)}
        groups = [sorted(eligible)] if len(eligible) >= 3 else []
    models = []
    for group in groups:
        modeled = set()
        for seed in group:
            if not intrinsic and seed in modeled:
                continue
            qualified = [p for p in group if matches(pattern(*seed), pattern(*p))]
            enough_regions = mode != 'distributed' or len({(px//32, py//32) for px, py in qualified}) >= 3
            if len(qualified) >= 3 and enough_regions:
                models.append((seed, qualified))
                if intrinsic:
                    break
                modeled.update(qualified)
    certain_seeds = ([] if intrinsic else
        _NewCellEvidence(field, raw, nearest, selected,
            diagnosis.get('material_boundary_containers', ())).seeds(models, pattern, mode))
    accepted = set()
    new_certain = set()
    for y in range(0, 593, 16):
        for x in range(0, 785, 16):
            candidate = pattern(x, y)
            if candidate['label'] not in selected or candidate['membership'] < .9:
                continue
            if candidate['flat'] and ((x, y) not in native16_primitive or any(
                max(x, bx) < min(x+16, bx+w) and max(y, by) < min(y+16, by+h) for bx, by, w, h in water_boxes)):
                continue
            if any(matches(candidate, pattern(*seed)) for seed, _ in models):
                accepted.add((x, y))
                if intrinsic or any(matches(candidate, pattern(*seed)) for seed in certain_seeds):
                    new_certain.add((x, y))
    record = {**diagnosis, 'primitive_before_pattern': sorted(primitive),
        'models': [dict(seed=seed, independent_source_witnesses=group,
                        label=pattern(*seed)['label'], flat=pattern(*seed)['flat']) for seed, group in models],
        'accepted': sorted(accepted), 'model_candidates': len(models),
        'no_new_objects_as_texture_witnesses': True, 'model_source_geometry_not_fixed_sprite': True}
    if not intrinsic:
        record['source_new_cell_certainty'] = sorted(new_certain)
        record['source_new_cell_certainty_separate_from_calibration'] = True
        record.update(source_flat_accepted_cells=sorted(p for p in accepted if pattern(*p)['flat']),
                      geometry_components_with_independent_appearance_roles=True, source_geometry_component_count=len(groups))
    if roles is not None:
        record.update(distributed_original_geometry_witnesses=True, source_glyph_owned_witnesses_excluded=roles.rejected)
    return accepted, record


def combined_patterns(image, room, spikes, water_boxes=(), *, source_context=None):
    local, local_diag = pattern_cells(image, room, spikes, water_boxes, mode='local', source_context=source_context)
    distributed, diag = pattern_cells(image, room, spikes, water_boxes, mode='distributed', source_context=source_context)
    accepted = local | distributed
    flat = set(map(tuple, local_diag.get('source_flat_accepted_cells', []))) | set(map(tuple, diag.get('source_flat_accepted_cells', [])))
    certainty = (set(map(tuple, local_diag.get('source_new_cell_certainty', local))) |
                 set(map(tuple, diag.get('source_new_cell_certainty', distributed))))
    return accepted, {**diag, 'accepted': sorted(accepted), 'source_new_cell_certainty': sorted(certainty),
                      'source_flat_accepted_cells': sorted(flat),
                      'eligible_local_models': local_diag.get('models', []),
                      'local_and_distributed_original_source_evidence=True': True}
