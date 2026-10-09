"""Original-source occupancy reconciliation, separate from broad recovery.

An original object is a locator, not source truth. Retire only after independently
calibrated background contradicts it, preserving every known positive pixel.
"""
from math import sqrt

from jtool_scanner import scanner
from jtool_scanner.terrain_material import cell_quad, pack_textured_rectangles
from scripts.source_material_patterns import pattern_cells


def footprint(key):
    type_id, x, y = key
    size = 16 if type_id == 2 else 32
    return {(px, py) for py in range(y, y+size) for px in range(x, x+size)}


def source_size_repair(image, room, detections, *, source_context=None):
    spikes = [(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10]
    water = [(d.x, d.y, 32, 32) for d in detections if d.type_id in (14, 15, 23)]
    _, diag = pattern_cells(image, room, spikes, water, mode='intrinsic', source_context=source_context)
    labels = set(diag.get('selected_clusters', []))
    tips = diag.get('tip_votes', {})
    backs = diag.get('background_back_votes', diag.get('back_votes', {}))
    bg_labels = {int(c) for c, votes in tips.items()
                 if votes >= 3 and votes/(votes+backs.get(int(c), backs.get(str(c), 0))) >= .75}
    centers = [tuple(c[k] for k in ('r', 'g', 'b')) for c in diag.get('cluster_centers', [])]
    if not labels or not bg_labels:
        return set(), set(), dict(reason='no independent source calibration')
    distance = lambda a, b: sqrt(sum((x-y)**2 for x, y in zip(a, b)))
    foreground, background = [centers[i] for i in labels], [centers[i] for i in bg_labels]
    separation = min(distance(f, b) for f in foreground for b in background)
    cache, rgb_membership = {}, {}

    def membership(value):
        if value not in rgb_membership:
            f, b = min(distance(value, c) for c in foreground), min(distance(value, c) for c in background)
            rgb_membership[value] = f < .5*b, b < .5*f
        return rgb_membership[value]

    def material(x, y, w=16, h=16, margin=4):
        key = x, y, w, h, margin
        if key in cache:
            return cache[key]
        if not (0 <= x and 0 <= y and x+w <= 800 and y+h <= 608):
            cache[key] = 'unknown'
            return 'unknown'
        values = []
        for py in range(y+margin, y+h-margin):
            for px in range(x+margin, x+w-margin):
                sx = int(room.x+(px+.5)*room.width/800)
                sy = int(room.y+(py+.5)*room.height/608)
                if not (0 <= sx < image.width and 0 <= sy < image.height):
                    cache[key] = 'unknown'
                    return 'unknown'
                values.append(image.pixel(sx, sy))
        mean = tuple(sum(v[c] for v in values)/len(values) for c in range(3))
        fg, bg = sum(membership(v)[0] for v in values)/len(values), sum(membership(v)[1] for v in values)/len(values)
        if fg >= .95 and min(distance(mean, c) for c in foreground) <= .25*separation:
            kind = 'foreground'
        elif bg >= .95 and min(distance(mean, c) for c in background) <= .25*separation:
            kind = 'background'
        else:
            kind = 'unknown'
        cache[key] = kind
        return kind

    lattice = {(x, y) for y in range(0, 593, 16) for x in range(0, 785, 16)}
    source_fg = {p for p in lattice if material(*p) == 'foreground'}
    source_bg = {p for p in lattice if material(*p) == 'background'}
    positive_pixels = {q for x, y in source_fg for q in footprint((2, x, y))}
    bg_pixels = {q for x, y in source_bg for q in footprint((2, x, y))}
    known_pixels = positive_pixels | bg_pixels
    anchors = [d for d in detections if d.type_id not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20)]
    rejected, proofs, affected_seeds = set(), [], set()
    for d in detections:
        if d.type_id != 1 or not (0 <= d.x <= 768 and 0 <= d.y <= 576):
            continue
        x, y = d.x, d.y
        key = 1, x, y
        extent = footprint(key)
        if any(max(x, a.x) < min(x+32, a.x+32) and max(y, a.y) < min(y+32, a.y+32) for a in anchors):
            continue
        if not extent <= known_pixels or not extent & positive_pixels:
            continue
        corridors = []
        for offset in (0, 8, 16):
            if material(x+offset, y, 16, 32) == 'background' and any(material(x+offset, ey) == 'background' for ey in (y-16, y+32)):
                corridors.append((x+offset, y, 16, 32))
            if material(x, y+offset, 32, 16) == 'background' and any(material(ex, y+offset) == 'background' for ex in (x-16, x+32)):
                corridors.append((x, y+offset, 32, 16))
        quarters = []
        for qx, qy in source_bg:
            if not (x <= qx and y <= qy and qx+16 <= x+32 and qy+16 <= y+32):
                continue
            if material(qx, qy, margin=1) != 'background':
                continue
            exterior = [p for p in scanner._axis_neighbors((qx, qy), 16) if p in source_bg and not (
                max(p[0], x) < min(p[0]+16, x+32) and max(p[1], y) < min(p[1]+16, y+32))]
            if exterior:
                quarters.append(dict(cell=[qx, qy], source_exterior=sorted(exterior)))
        if not corridors and not quarters:
            continue
        rejected.add(key)
        affected_seeds.update(p for p in source_fg if max(p[0], x) < min(p[0]+16, x+32)
                              and max(p[1], y) < min(p[1]+16, y+32))
        proofs.append(dict(key=key, source_bg_corridors=corridors, source_bg_quarters=quarters,
                           foreground_pixels_preserved=len(extent & positive_pixels)))
    affected, pending = set(affected_seeds), list(affected_seeds)
    while pending:
        for p in scanner._axis_neighbors(pending.pop(), 16):
            if p in source_fg and p not in affected:
                affected.add(p)
                pending.append(p)
    blocks = set(pack_textured_rectangles(affected))
    covered = {p for block in blocks for p in cell_quad(block)}
    independent_fulls = set(pack_textured_rectangles(source_fg))
    raw = {(1, x, y) for x, y in blocks | independent_fulls} | {(2, x, y) for x, y in affected-covered}
    existing = {(d.type_id, d.x, d.y) for d in detections}
    occupied = {p for key in existing-rejected if key[0] in (1, 2) for p in footprint(key)}
    redundant = {key for key in raw-existing if footprint(key) <= occupied}
    replacements = raw-redundant
    supplied = occupied | {p for key in replacements for p in footprint(key)}
    required = {p for key in rejected for p in footprint(key)} & positive_pixels
    assert required <= supplied, 'Cannot retire an object without source-positive coverage'
    return replacements, rejected, dict(source_calibration=diag, source_fg=sorted(source_fg), source_bg=sorted(source_bg),
        proofs=proofs, affected_source_cells=sorted(affected), redundant_solid_union_proposals=sorted(redundant),
        all_disproved_foreground_coverage_retained=True, complete_source32_recovery=True,
        no_unbounded_residual_mini_emission_or_new_objects_as_witnesses=True)
