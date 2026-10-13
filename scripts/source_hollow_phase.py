"""Source-backed origin repair of existing same-size/direction hollow glyphs.

Unknown source is not absence. Preserve original source-positive objects and
confirmed terrain interfaces, including a full sprite partly inside a wall.
Only a unique closed alternative may replace an unsupported existing base.
"""
from math import dist, hypot

from jtool_scanner.spike_shape import VERTICES


def known_base_ink(evidence, a, b, index):
    """Count raw ink only with complete original coverage of the bounded band.

    The positive ink API can return None after an early negative. That is not
    an absence proof: explicitly distinguish a known weak base from unknown
    samples before retiring an old locator.
    """
    tx, ty = b[0]-a[0], b[1]-a[1]
    length = hypot(tx, ty)
    nx, ny = -ty/length, tx/length
    model = evidence.models[index]
    found = set()
    for i in range(12):
        q = .15 + .7*i/11
        px, py = a[0]+q*tx, a[1]+q*ty
        position = evidence.frame.original_position(px, py)
        values = [evidence.frame.original_pixel(px+off*nx, py+off*ny)
                  for off in (-2, -1, 0, 1, 2)]
        if position is None or any(rgb is None for rgb in values):
            return None
        if any(dist(rgb, model['foreground']) < dist(rgb, model['background'])
               for rgb in values):
            found.add(position)
    return len(found)


def confirmed_attachment(evidence, detection, blocks):
    """Qualify the supporting image interface, not just a detected block label."""
    t, x, y = detection.type_id, detection.x, detection.y
    candidates = []
    for bx, by in sorted(blocks):
        if t == 3:
            distance = abs(by-(y+32))
            overlap = min(x+32, bx+32)-max(x, bx)
            face = (bx, by), (bx+32, by)
        elif t == 6:
            distance = abs(by+32-y)
            overlap = min(x+32, bx+32)-max(x, bx)
            face = (bx, by+32), (bx+32, by+32)
        elif t == 5:
            distance = abs(bx-(x+32))
            overlap = min(y+32, by+32)-max(y, by)
            face = (bx, by), (bx, by+32)
        else:
            distance = abs(bx+32-x)
            overlap = min(y+32, by+32)-max(y, by)
            face = (bx+32, by), (bx+32, by+32)
        if distance > 8 or max(0, overlap)-distance <= 0:
            continue
        raw = evidence.library.raw.raw.field.edge(*face)
        directed = evidence.directed(*face)
        candidates.append(dict(block=(bx, by), face=face,
            source_support=raw.support, unknown=raw.unknown, directed=directed,
            confirmed=raw.support >= 9 and not raw.unknown and directed >= 9))
    return any(c['confirmed'] for c in candidates), candidates


def refit_source_hollow_phases(evidence, original_detections, source_positive):
    """Return immutable repair proofs; neither emit nor change source teachers."""
    positive = set(map(tuple, source_positive))
    if not positive:
        return []
    original = tuple(original_detections)
    terrain = {(d.x, d.y) for d in original if d.type_id == 1}
    anchors = [d for d in original if d.type_id not in range(1, 11)]
    proofs = []
    for detection in original:
        old = detection.type_id, detection.x, detection.y
        if old[0] not in VERTICES:
            continue
        alternatives = [k for k in positive if k[0] == old[0]
            and abs(k[1]-old[1]) <= 16 and abs(k[2]-old[2]) <= 16 and k != old]
        if not alternatives or evidence.support(old)['passed']:
            continue
        confirmed, interfaces = confirmed_attachment(evidence, detection, terrain)
        if (confirmed or any(face['unknown'] for face in interfaces)
                or not evidence.frame.rectangle_available(old[1], old[2], 32, 32, margin=4)):
            continue
        if any(max(old[1], d.x) < min(old[1]+32, d.x+32)
               and max(old[2], d.y) < min(old[2]+32, d.y+32) for d in anchors):
            continue
        accepted = []
        for new in sorted(alternatives):
            query = evidence.support(new)
            models = []
            for index, model in enumerate(evidence.models):
                if not any(model['independent_teachers'] == p['original_teachers'] for p in query['proof']):
                    continue
                phases = []
                for dx in (0, -evidence.frame.pitch[0], evidence.frame.pitch[0]):
                    for dy in (0, -evidence.frame.pitch[1], evidence.frame.pitch[1]):
                        t, x, y = old
                        poly = [(x+dx+u, y+dy+v) for u, v in VERTICES[t]]
                        edges = list(zip(poly, poly[1:]+poly[:1]))
                        positive_ink = evidence.ink_hits(*edges[1], index)
                        known_ink = (positive_ink if positive_ink is not None
                                     else known_base_ink(evidence, *edges[1], index))
                        phases.append(dict(phase=(dx, dy),
                            base_ink=known_ink, base_source_known=known_ink is not None,
                            slopes=[evidence.directed(*edges[i]) for i in (0, 2)]))
                base_impossible = all(p['base_source_known'] and p['base_ink'] < 9
                                      for p in phases)
                shared_slopes = any(min(p['slopes']) >= 9 for p in phases)
                if base_impossible and shared_slopes:
                    models.append(dict(index=index, phases=phases))
            if models:
                accepted.append(dict(new=new, source_models=models))
        if len(accepted) == 1:
            proofs.append(dict(old=old, **accepted[0], new_complete_source_predicate=True,
                old_source_interfaces=interfaces, old_confirmed_anchor_preserved=True,
                old_known_source_coverage=True, old_base_cannot_meet_ink_bound=True))
    counts = {p['new']: sum(q['new'] == p['new'] for q in proofs) for p in proofs}
    return [p for p in proofs if counts[p['new']] == 1]
