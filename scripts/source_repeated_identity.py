"""Local positive evidence for room-profile-derived terrain components.

Room-wide material votes are not object identity. This read-only observer asks
whether each original repeated-material island has any independently supported
object evidence. Unsupported is ABSTENTION, never proof of empty background;
callers must not turn this diagnostic into deletion without separate qualification.
No map changes, reference answers, generated teachers or scanner binding.
"""
from __future__ import annotations

from dataclasses import asdict

from jtool_scanner import scanner
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_sampling import SourceFrame


def _components(points):
    remaining = set(points)
    while remaining:
        first = min(remaining)
        remaining.remove(first)
        group, queue = {first}, [first]
        while queue:
            x, y = queue.pop()
            for a, b in sorted(remaining):
                ix = min(x + 32, a + 32) - max(x, a)
                iy = min(y + 32, b + 32) - max(y, b)
                # Mixed phases can share area or a positive-length edge. A
                # corner alone does not provide a connected terrain surface.
                if ix >= 0 and iy >= 0 and (ix > 0 or iy > 0):
                    remaining.remove((a, b))
                    group.add((a, b))
                    queue.append((a, b))
        yield tuple(sorted(group))


def _disjoint(first, second):
    size = max(16 if first[0] > 6 else 32, 16 if second[0] > 6 else 32)
    return abs(first[1] - second[1]) >= size or abs(first[2] - second[2]) >= size


def _contains_probe(members, probe):
    x, y, size = probe
    return all(any(bx <= px < bx + 32 and by <= py < by + 32 for bx, by in members)
               for py in range(y, y + size) for px in range(x, x + size))


def _overlaps_marker(members, markers):
    return any(max(x, d.x) < min(x + 32, d.x + 32)
               and max(y, d.y) < min(y + 32, d.y + 32)
               for x, y in members for d in markers)


def _closed_rectangle(field, frame, x, y):
    nominal = field.rectangle(x, y, 32)
    qualified = lambda faces: all(f.support >= 9 and not f.unknown for f in faces)
    if qualified(nominal):
        return dict(method='nominal', faces=[asdict(f) for f in nominal])
    # The established raster-centre alternative is ONE coherent inset frame,
    # not four individually chosen phases or a lower support threshold.
    ix, iy = .5 * frame.pitch[0], .5 * frame.pitch[1]
    corners = ((x + ix, y + iy), (x + 32 - ix, y + iy),
               (x + 32 - ix, y + 32 - iy), (x + ix, y + 32 - iy))
    inset = [field.edge(corners[i], corners[(i + 1) % 4]) for i in range(4)]
    if qualified(inset):
        return dict(method='coherent-raster-inset', faces=[asdict(f) for f in inset])
    return None


def _backing_witness(image, room, frame, context, spikes, members):
    library = None
    for detection in spikes:
        key = detection.type_id, detection.x, detection.y
        size = 16 if key[0] > 6 else 32
        probe = scanner._repeated_terrain_support_probe(detection)
        if not _contains_probe(members, probe):
            continue
        if (not frame.rectangle_available(key[1], key[2], size, size, margin=4)
                or not frame.rectangle_available(*probe[:2], probe[2], probe[2])):
            continue
        if library is None:
            library = context.glyph_library(image, room,
                [(d.type_id, d.x, d.y) for d in spikes])
        source = library.raw.owner(*key)
        if source is None:
            continue
        appearance = library.support(*key)
        if not appearance['passed']:
            continue
        teachers = tuple(map(tuple, appearance['model']['original_source_witnesses']))
        if any(not frame.rectangle_available(t[1], t[2], 16 if t[0] > 6 else 32,
                    16 if t[0] > 6 else 32, margin=4) for t in teachers):
            continue
        independent = []
        for teacher in teachers:
            if all(_disjoint(teacher, other) for other in independent):
                independent.append(teacher)
        if len(independent) < 3:
            continue
        return dict(key=key, probe=probe, source=source, appearance=appearance,
                    independently_known_original_contributors=independent)
    return None


def repeated_material_support(image, room, detections, *, source_frame=None, source_context=None,
                              candidate_points=None):
    """Observe finite ORIGINAL full-profile components without changing objects.

    Existing intrinsic block geometry, known coherent rectangle closure and a
    source-verified original glyph backing are separate positive channels.
    Unknown/clipped context and nongeometry overlap remain explicit abstentions.
    The ordinary scanner does not call this function. No removal set is returned.
    Optional candidate_points locate pending profile queries only; the ORIGINAL
    detections remain the sole source of glyph teachers and marker protections.
    """
    detections = tuple(detections)
    if candidate_points is None:
        points = {(d.x, d.y) for d in detections
                  if d.type_id == 1 and getattr(d, 'kind', None) == 'repeated_terrain_block'}
    else:
        try:
            points = set(map(tuple, candidate_points))
        except TypeError as error:
            raise ValueError('Candidate points must be native integer x,y pairs') from error
        if any(len(point) != 2 or any(not isinstance(v, int) or isinstance(v, bool) for v in point)
               or not (0 <= point[0] <= 768 and 0 <= point[1] <= 576) for point in points):
            raise ValueError('Candidate points must be in-room native integer x,y pairs')
    result = dict(components=[], unsupported_known=[], no_objects_changed=True,
                  no_new_outputs_as_teachers=True, unsupported_is_NOT_empty_background=True)
    if not points:
        return result
    frame = SourceFrame(image, room) if source_frame is None else source_frame
    if not frame.matches_source(image, room):
        raise ValueError('Repeated-material frame must match the original source')
    if frame.extent != room:
        return {**result, 'abstained': 'world-extent transform not qualified for this observer'}
    spikes = tuple(d for d in detections if 3 <= d.type_id <= 10)
    locators = [(d.type_id, d.x, d.y) for d in spikes]
    context = source_context or SourceEvidenceContext(image, room, locators)
    context.validate(image, room, locators)
    markers = tuple(d for d in detections if d.type_id > 10)
    for members in _components(points):
        row = dict(members=members, disposition='unsupported-known', evidence=None)
        if any(not frame.rectangle_available(x, y, 32, 32, margin=4) for x, y in members):
            row['disposition'] = 'abstain-unknown-source'
        elif _overlaps_marker(members, markers):
            row['disposition'] = 'abstain-original-marker-overlap'
        else:
            for x, y in members:
                patch = scanner._patch_features(image, room, x, y, 32)
                score = scanner._classify_block(patch).score
                if score >= scanner.BLOCK_MIN_SCORE:
                    row.update(disposition='supported-intrinsic', evidence=dict(
                        key=(1, x, y), score=score, existing_minimum=scanner.BLOCK_MIN_SCORE))
                    break
            if row['evidence'] is None:
                field = context.contours()
                for x, y in members:
                    proof = _closed_rectangle(field, frame, x, y)
                    if proof is not None:
                        row.update(disposition='supported-rectangle', evidence=dict(key=(1, x, y), **proof))
                        break
            if row['evidence'] is None:
                proof = _backing_witness(image, room, frame, context, spikes, members)
                if proof is not None:
                    row.update(disposition='supported-original-backing', evidence=proof)
            if row['evidence'] is None:
                result['unsupported_known'].extend((1, x, y) for x, y in members)
        result['components'].append(row)
    result['unsupported_known'].sort()
    return result
