"""Research-only confidence for independently NEW source terrain.

Original material calibration remains unchanged. These explicit functions only
qualify a separate sidecar or withhold new size/material growth; they do not
change original objects, retire geometry, build teachers or bind the scanner.
No global instrumentation or private imports. One edge memo belongs to one scan.
"""
from copy import deepcopy
from math import hypot, sqrt
from statistics import median

from scripts.source_occupancy import footprint


def precision_aware_edge(field, first, second):
    """Original RGB edge support above quantization/physical-spacing uncertainty."""
    tx, ty = second[0]-first[0], second[1]-first[1]
    length = hypot(tx, ty)
    if not length:
        raise ValueError('A source edge needs two distinct endpoints')
    nx, ny = -ty/length, tx/length
    rows = []
    for i in range(12):
        q = .15+.7*i/11
        px, py = first[0]+q*tx, first[1]+q*ty
        native = [(px+off*nx, py+off*ny) for off in range(-4, 5)]
        if any(not (0 <= x < 800 and 0 <= y < 608) for x, y in native):
            return dict(support=0, unknown=True)
        points = [(int(field.room.x+x*field.room.width/800),
                   int(field.room.y+y*field.room.height/608)) for x, y in native]
        if any(not field.room.contains(x, y) for x, y in points):
            return dict(support=0, unknown=True)
        values = [field.image.pixel(*p) for p in points]
        spacing = [hypot(points[j+1][0]-points[j][0], points[j+1][1]-points[j][1]) for j in range(8)]
        derivatives = [tuple((values[j+1][c]-values[j][c])/spacing[j] for c in range(3))
                       if spacing[j] else (0., 0., 0.) for j in range(8)]
        gradient = tuple(median(derivatives[j][c] for j in (0, 1, 6, 7)) for c in range(3))
        departure = lambda d: sqrt(sum((d[c]-gradient[c])**2 for c in range(3)))
        reference = max(departure(derivatives[j]) for j in (0, 1, 6, 7))
        outer_error = max((1/spacing[j] if spacing[j] else 0.) for j in (0, 1, 6, 7))
        phases = {j-3.5 for j in (2, 3, 4, 5) if spacing[j] and
                  departure(derivatives[j]) > max(reference, sqrt(3)*(1/spacing[j]+outer_error))}
        rows.append((phases, points[4]))
    support = max(len({p for phases, p in rows if any(low <= v <= low+1 for v in phases)})
                  for low in (-1.5, -.5, .5))
    return dict(support=support, unknown=False)


def qualify_source_roles(field, selected, shadow_proof, original_detections, *, edge_memo=None):
    """Qualify shadow-role witnesses without changing the old expansion result.

    Callers retain the original labels/expanded roles/proofs for old consumers.
    ``edge_memo`` must be context-owned and validated before reuse; it is not a
    process-global cache. Original nonterrain excludes teaching neighborhoods,
    not the detected objects themselves. Newly emitted objects cannot teach.
    """
    anchors = [d.image_box for d in original_detections if d.type_id > 10 and d.type_id != 20]
    cache = {} if edge_memo is None else edge_memo
    accepted, qualified, observations = set(selected), [], []
    for role in shadow_proof:
        witnesses, rejected = [], []
        for row in role['original_source_geometry']:
            x, y = row['native']
            left, top = field.room.x+x*field.room.width/800, field.room.y+y*field.room.height/608
            right = field.room.x+(x+16)*field.room.width/800
            bottom = field.room.y+(y+16)*field.room.height/608
            if any(max(left, b.x-b.width/2) < min(right, b.right+b.width/2) and
                   max(top, b.y-b.height/2) < min(bottom, b.bottom+b.height/2) for b in anchors):
                rejected.append(dict(native=[x, y], reason='original nonterrain sprite/label neighborhood'))
                continue
            corners = [(x, y), (x+16, y), (x+16, y+16), (x, y+16)]
            faces = []
            for i in range(4):
                key = field, corners[i], corners[(i+1)%4]
                if key not in cache:
                    cache[key] = precision_aware_edge(field, key[1], key[2])
                faces.append(cache[key])
            if any(f['unknown'] or f['support'] < 9 for f in faces):
                rejected.append(dict(native=[x, y], reason='closure not significant above RGB quantization', faces=faces))
                continue
            witnesses.append({**row, 'precision_aware_faces': faces})
        independent = []
        for witness in witnesses:
            x, y = witness['native']
            if all(abs(x-r['native'][0]) >= 16 or abs(y-r['native'][1]) >= 16 for r in independent):
                independent.append(witness)
        passed = len(independent) >= 3
        observations.append(dict(label=role['label'], qualified_witnesses=independent,
                                 rejected_witnesses=rejected, passed=passed))
        if passed:
            accepted.add(role['label'])
            qualified.append({**role, 'original_source_geometry': independent})
    # Proofs are inspectable output, not a mutable route into source witnesses
    # or a context-owned edge memo.
    return accepted, deepcopy(qualified), deepcopy(observations)


def bounded_texture_parents(key, room):
    """Query-only original32 frames that physically contain a new16 footprint."""
    t, x, y = key
    if t == 1:
        return [(x, y)]
    if t != 2:
        raise ValueError('Growth texture corroboration needs terrain type1 or2')
    if room is None or room.width <= 0 or room.height <= 0:
        return []
    parents = []
    for px in (x-16, x):
        for py in (y-16, y):
            if not (0 <= px <= 768 and 0 <= py <= 576):
                continue
            margins = (px*room.width/800, py*room.height/608,
                       (800-px-32)*room.width/800, (608-py-32)*room.height/608)
            if min(margins) >= 2:
                parents.append((px, py))
    return parents


def qualify_independent_growth(proposals, original_keys, *, sizing, sizing_retired,
                               joint_cells, phase_positive, calibrations, room,
                               original_texture_libraries=()):
    """Return a subset of proposals plus explicit proofs; never retire originals.

    Every supplied calibration contains ORIGINAL source labels and separately
    approved role IDs. Libraries are the existing original-only full textures;
    they are queried, never extended. Producer keys, not generic detection kind,
    identify growth. Required old replacement coverage and phase gains survive.
    """
    proposals, existing = set(proposals), set(original_keys)
    sizing, phase_positive = set(sizing), set(phase_positive)
    joint = {(2, *p) for p in joint_cells}
    retired_pixels = {p for key in sizing_retired for p in footprint(key)}
    candidates = {key for key in (sizing | joint) & proposals if key[0] in (1, 2)
                  and key not in existing and key not in phase_positive
                  and not (footprint(key) & retired_pixels)}
    calibrations = tuple(calibrations)
    libraries = tuple(original_texture_libraries)
    held, proof = [], []
    for key in sorted(candidates):
        t, x, y = key
        size = 32 if t == 1 else 16
        cells = {(x+dx, y+dy) for dx in range(0, size, 16) for dy in range(0, size, 16)}
        role = any(all(p in s['labels'] and s['labels'][p] in s['approved'] for p in cells)
                   for s in calibrations)
        parents = [] if role else bounded_texture_parents(key, room)
        texture = [dict(parent32=[px, py], **lib.support(px, py))
                   for lib in libraries for px, py in parents] if not role else []
        accepted = role or any(p['passed'] for p in texture)
        proof.append(dict(key=key, native_size=size, qualified_source_roles=role,
                          original_full_texture=texture, independent_growth=accepted,
                          existing_object_not_retired=True, texture_is_query_only=True,
                          sizing_origin=key in sizing, joint_material_origin=key in joint))
        if not accepted:
            held.append(key)
    return proposals-set(held), deepcopy(dict(held=held, proof=proof))
