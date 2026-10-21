"""Recover source-proved ORIGINAL spikes lost during legacy geometry arbitration.

This bounded channel never enumerates new poses. Rejected candidates remain
outside every teacher snapshot; the already-built final original filled field
supplies the unchanged body/texture/RGB geometry and same-instance proofs.
"""
from scripts.source_directional_body import SourceDirectionalBodyEvidence
from scripts.source_filled_pipeline import FilledGlyphEvidence, distinguish_filled_instances
from scripts.source_sampling import SourceFrame


_PRIMARY = {3: 'spike_up', 4: 'spike_right', 5: 'spike_left', 6: 'spike_down'}


def _snapshot(detections):
    from jtool_scanner.scanner import Detection
    value = tuple(detections)
    if any(not isinstance(d, Detection) for d in value):
        raise ValueError('Rejected-primary recovery needs original Detection metadata')
    return value


def rejected_primary_candidates(before, after):
    """Record only exact original primaries removed by a legacy geometry stage."""
    before, after = _snapshot(before), frozenset(_snapshot(after))
    return tuple(d for d in before if d not in after and _PRIMARY.get(d.type_id) == d.kind)


def recover_rejected_primaries(detections, candidates, original_detections, *,
                              source_frame, source_filled_evidence, source_grid,
                              retired=()):
    """Add source-proved old Detection instances; never modify old survivors.

    ``original_detections`` is the immutable BEFORE-source-consumer teacher
    snapshot, NOT ``detections`` after that consumer's additions/retirements.
    A source-supported competing existing apex still controls same-instance
    ambiguity. No missing/unknown proof is used to retire any object.
    """
    current, candidates, original = map(_snapshot, (detections, candidates, original_detections))
    report = dict(candidates=len(candidates), evaluated=0, accepted=[], skipped=[],
                  same_instance_alternatives=[], no_existing_retirement=True,
                  no_new_teachers=True, no_new_pose_enumeration=True)
    if not isinstance(source_frame, SourceFrame):
        raise ValueError('Rejected-primary recovery needs an original SourceFrame')
    if source_grid != (25, 19) or source_frame.extent != source_frame.room:
        return list(current), {**report, 'reason': 'unqualified source mapping'}
    if not candidates:
        return list(current), report
    if (not isinstance(source_filled_evidence, FilledGlyphEvidence)
            or source_filled_evidence.frame is not source_frame):
        raise ValueError('Rejected-primary recovery must reuse the actual original filled field')
    pending = {}
    for detection in candidates:
        key = detection.type_id, detection.x, detection.y
        if _PRIMARY.get(detection.type_id) != detection.kind:
            raise ValueError('Rejected candidate is not an original primary full spike')
        if key in pending and pending[key] != detection:
            raise ValueError('Ambiguous original primary metadata for one pose')
        pending[key] = detection
    existing = {(d.type_id, d.x, d.y) for d in current}
    excluded = existing | set(map(tuple, retired))
    eligible = []
    for key in pending:
        if key in excluded:
            report['skipped'].append(dict(key=key, reason='already current or deliberately retired'))
        else:
            eligible.append(key)
    if not eligible:
        return list(current), report
    evidence = SourceDirectionalBodyEvidence(source_filled_evidence, original,
                                             source_grid=source_grid)
    admitted, proofs = set(), {}
    for key in eligible:
        proof = evidence.support(key)
        report['evaluated'] += 1
        proofs[key] = proof
        if proof['passed']:
            admitted.add(key)
    admitted, alternatives = distinguish_filled_instances(admitted, current, source_filled_evidence)
    report['same_instance_alternatives'] = alternatives
    additions = [pending[key] for key in pending if key in admitted]
    report['accepted'] = [dict(key=key, evidence=proofs[key]) for key in pending if key in admitted]
    if not additions:
        return list(current), report
    return sorted([*current, *additions], key=lambda d: (d.type_id, d.y, d.x)), report
