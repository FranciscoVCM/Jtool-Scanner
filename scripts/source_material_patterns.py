"""Explicit intrinsic/local/distributed original-source terrain appearance.

Newly accepted cells never become teachers. Flat-water negatives, primitive
geometry, source-confirmed glyph teacher exclusions and independent regions remain
separate safeguards. This experimental stage is not bound to scanner defaults.
"""
from math import sqrt

from PIL import Image
from jtool_scanner import scanner
from scripts.source_glyph_prototypes import SourceGlyphLibrary
from scripts.source_material_evidence import (
    BackingCoreRoles, boundary_primitives, container_primitives, rectangle_field,
)


def eligible_primitives(image, room, spikes, *, source_context=None):
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
    accepted = set()
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
    record = {**diagnosis, 'primitive_before_pattern': sorted(primitive),
        'models': [dict(seed=seed, independent_source_witnesses=group,
                        label=pattern(*seed)['label'], flat=pattern(*seed)['flat']) for seed, group in models],
        'accepted': sorted(accepted), 'model_candidates': len(models),
        'no_new_objects_as_texture_witnesses': True, 'model_source_geometry_not_fixed_sprite': True}
    if not intrinsic:
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
    return accepted, {**diag, 'accepted': sorted(accepted), 'source_flat_accepted_cells': sorted(flat),
                      'eligible_local_models': local_diag.get('models', []),
                      'local_and_distributed_original_source_evidence=True': True}
