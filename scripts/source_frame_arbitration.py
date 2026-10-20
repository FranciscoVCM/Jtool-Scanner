"""Conservative original-object evidence for choosing an existing source frame.

Neither frame is a coordinate answer. Keep the offered mapping if even one of
its independently source-owned original full spikes loses that proof. Physical
preference also needs three disjoint, non-collinear witnesses whose ORIGINAL
image boxes agree to pixel quantization. No generated proposals can vote.
"""
from math import ceil, floor

from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_glyph_prototypes import SourceGlyphEvidence
from scripts.source_sampling import SourceFrame


def _box_agrees(box, key, room):
    _, x, y = key
    expected = (room.x + x * room.width / 800,
                room.y + y * room.height / 608,
                32 * room.width / 800, 32 * room.height / 608)
    return all(actual in (floor(value), ceil(value)) for actual, value in zip(
        (box.x, box.y, box.width, box.height), expected))


def _independent(keys):
    result = []
    for key in sorted(set(keys)):
        if all(abs(key[1] - other[1]) >= 32 or abs(key[2] - other[2]) >= 32
               for other in result):
            result.append(key)
    return result


def _noncollinear(keys):
    if len(keys) < 3:
        return False
    a, b = keys[:2]
    return any((b[1] - a[1]) * (c[2] - a[2]) !=
               (b[2] - a[2]) * (c[1] - a[1]) for c in keys[2:])


def select_source_glyph_frame(image, room, original_detections, offered_frame, *,
                              source_grid, source_context=None):
    """Return (frame, reusable raw field, proof); never mutate detections.

    This does not infer a transform, score palettes, scan twice or retire an
    original object. Only explicit full-room source mode calls this API. Compact
    mappings and direct frames bypass without building any extra evidence.
    """
    if not isinstance(offered_frame, SourceFrame) or not offered_frame.matches_source(image, room):
        raise ValueError('Offered source frame must match the original image/crop')
    originals = tuple(original_detections)
    spikes = [(d.type_id, d.x, d.y) for d in originals if 3 <= d.type_id <= 10]
    context = source_context
    if context is not None:
        context.validate(image, room, spikes)
    proof = dict(selected_physical=False, offered_owners=[], physical_only=[],
                 disjoint_witnesses=[], original_objects_unchanged=True)
    if source_grid != (25, 19) or offered_frame.extent == room:
        return offered_frame, None, {**proof, 'reason': 'direct or compact frame bypass'}
    if context is None:
        context = SourceEvidenceContext(image, room, spikes)
    physical_raw = context.glyph_field(image, room, spikes)
    offered_raw = SourceGlyphEvidence(offered_frame.original_snapshot(), offered_frame.extent,
                                     source_frame=offered_frame)
    physical_frame = SourceFrame(image, room)
    fulls = {}
    for detection in originals:
        if 3 <= detection.type_id <= 6:
            fulls.setdefault((detection.type_id, detection.x, detection.y), []).append(detection)
    witnesses = []
    for key, detections in sorted(fulls.items()):
        _, x, y = key
        offered = (offered_frame.rectangle_available(x, y, 32, 32, margin=4)
                   and offered_raw.owner(*key) is not None)
        physical = (physical_frame.rectangle_available(x, y, 32, 32, margin=4)
                    and physical_raw.owner(*key) is not None)
        if offered:
            proof['offered_owners'].append(key)
            if not physical:
                return offered_frame, offered_raw, {**proof,
                    'reason': 'offered source ownership conflicts', 'conflict': key}
        if physical and not offered and any(_box_agrees(d.image_box, key, room) for d in detections):
            witnesses.append(key)
    independent = _independent(witnesses)
    proof.update(physical_only=witnesses, disjoint_witnesses=independent)
    if not _noncollinear(independent):
        return offered_frame, offered_raw, {**proof, 'reason': 'no independent two-dimensional dominance'}
    return physical_frame, physical_raw, {**proof, 'selected_physical': True,
        'reason': 'all offered owners preserved; independent original physical witnesses'}
