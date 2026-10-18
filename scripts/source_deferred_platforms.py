"""Pure FINAL source-validated original platform-veto recovery, not app-bound.

The caller freezes original proposals in their original source frame and keeps
the old phase/arbitration pipeline unchanged. Only independently corroborated
original solids can return after their provisional platform anchors disappear.
No raw spikes, reference answers, deletion, rephasing or generated teachers.
"""
from dataclasses import dataclass

from jtool_scanner import scanner


@dataclass(frozen=True)
class OriginalGeometryVeto:
    detection: scanner.Detection
    anchors: tuple[scanner.Detection, ...]


def original_platform_vetoes(detections):
    """Observe original full-block vetoes without changing candidates/anchors.

    Retain nonplatform conflicts as explicit abstentions, not hidden omissions.
    Detection/Box objects are frozen. Caller must collect before the ORIGINAL
    first anchor pass, not feed later recoveries back as an original snapshot.
    """
    detections = tuple(detections)
    anchors = tuple(d for d in detections if d.type_id not in scanner.GEOMETRY_TYPES)
    rows = []
    for detection in detections:
        if detection.type_id != scanner.OBJ_BLOCK:
            continue
        conflicts = tuple(a for a in anchors if scanner._geometry_anchor_conflicts(detection, a))
        if conflicts:
            rows.append(OriginalGeometryVeto(detection, conflicts))
    return tuple(rows)


def recover_deferred_platform_blocks(detections, vetoes, models, *, source_grid,
                                     source_frame):
    """Query independent source models after FINAL phase/marker decisions.

    This low-level caller assumes original standard-frame coordinates; it does
    not infer compact identity or normalize/reproject a working-image ledger.
    Return original objects plus novel qualified solids and an isolated proof.
    No model is taught from these proposals or from another query result.
    """
    models = tuple(models)
    proof = dict(added=[], queries=[], abstained=[], no_objects_retired=True,
                 no_origin_changes=True, no_new_outputs_as_teachers=True)
    if source_grid != (25, 19) or source_frame.extent != source_frame.room:
        return detections, {**proof, 'bypassed': 'native grid/world transform not qualified'}
    if any(model.frame is not source_frame for model in models):
        raise ValueError('Deferred source models must share the original source frame')
    if not models:
        return detections, {**proof, 'bypassed': 'no independent original source model'}
    markers = [d for d in detections if d.type_id not in scanner.GEOMETRY_TYPES]
    markerkeys = {(d.type_id, d.x, d.y) for d in markers}
    existing = {(d.type_id, d.x, d.y) for d in detections}
    candidates = []
    for row in vetoes:
        detection = row.detection
        if detection.type_id != scanner.OBJ_BLOCK or not row.anchors:
            raise ValueError('A deferred record needs an original full-block veto')
        key = detection.type_id, detection.x, detection.y
        reason = None
        if key in existing:
            reason = 'original already survives'
        elif any(a.type_id != scanner.OBJ_PLATFORM for a in row.anchors):
            reason = 'original nonplatform veto'
        elif any((a.type_id, a.x, a.y) in markerkeys for a in row.anchors):
            reason = 'original platform survives'
        elif any(scanner._geometry_anchor_conflicts(detection, a, include_diagonal_overlap=True)
                 for a in markers):
            reason = 'surviving marker conflict'
        if reason is not None:
            proof['abstained'].append(dict(key=key, reason=reason))
            continue
        evidence = []
        for index, model in enumerate(models):
            result = model.support(detection.x, detection.y)
            evidence.append(dict(model=index, proof=result))
            if result['passed']:
                candidates.append(detection)
                break
        proof['queries'].append(dict(key=key, source=evidence))
    merged = scanner._merge_source_supported_terrain_blocks(detections, candidates)
    proof['added'] = [(d.type_id, d.x, d.y) for d in merged[len(detections):]]
    return merged, proof
