"""Complete explicit experimental source geometry pipeline.

No private imports, compiled wrappers, references or newly generated teachers.
This module does not yet bind the default scanner; ordinary qualification is
required before adoption. All evidence remains local to one original image/frame.
"""
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_full_pose import refit_full_poses
from scripts.source_material_ownership import material_cells
from scripts.source_occupancy import footprint, source_size_repair
from scripts.source_terrain_agreement import agree_new_fulls


def joint_proposals(image, room, detections, *, source_context=None):
    spikes = [(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10]
    water = [(d.x, d.y, 32, 32) for d in detections if d.type_id in (14, 15, 23)]
    sizing, rejected, size_diag = source_size_repair(image, room, detections, source_context=source_context)
    intrinsic = set(map(tuple, size_diag.get('source_calibration', {}).get('accepted', [])))
    material, diag = material_cells(image, room, spikes, water, source_context=source_context)
    existing = {(d.type_id, d.x, d.y) for d in detections}
    occupied = {p for key in existing-rejected if key[0] in (1, 2) for p in footprint(key)}
    occupied |= {p for key in sizing if key[0] == 1 for p in footprint(key)}
    supported_intrinsic, supplemental = material & intrinsic, material-intrinsic
    redundant = {p for p in supplemental if footprint((2, *p)) <= occupied}
    growth = {(2, x, y) for x, y in supported_intrinsic | (supplemental-redundant)}
    return sizing | growth, rejected, dict(source_sizing=size_diag, source_material=diag,
        intrinsic_source_cells_retained=sorted(supported_intrinsic), supplemental_source_cells=sorted(supplemental),
        supplemental_duplicate_coverage_abstained=sorted(redundant), current_source_evidence_not_previous_answers=True,
        source_supported_full_representation_not_new_witnesses=True, no_existing_mini_deletion_or_new_object_witnesses=True)


def source_proposals(image, room, detections, *, source_context=None):
    """Return proposals/removals/full proofs, without touching original objects."""
    detections = tuple(detections)
    spikes = [(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10]
    context = source_context if source_context is not None else SourceEvidenceContext(image, room, spikes)
    context.validate(image, room, spikes)
    proposed, rejected, diag = joint_proposals(image, room, detections, source_context=context)
    existing = {(d.type_id, d.x, d.y) for d in detections}
    flat = set(map(tuple, diag['source_material'].get('source_flat_accepted_cells', [])))
    water = [(d.x, d.y) for d in detections if d.type_id in (14, 15, 23)]
    parents = [key for key in existing-rejected if key[0] == 1 and any(
        max(key[1], x) < min(key[1]+32, x+32) and max(key[2], y) < min(key[2]+32, y+32) for x, y in water)]
    ambiguous = {key for key in proposed-existing if key[0] == 2 and key[1:] in flat and any(
        parent[1] <= key[1] and parent[2] <= key[2] and key[1]+16 <= parent[1]+32 and key[2]+16 <= parent[2]+32
        for parent in parents)}
    proposed -= ambiguous
    diag = {**diag, 'new_flat_mini_identity_under_occluded_full_abstained': sorted(ambiguous),
            'independent_textured16_evidence_preserved': True, 'existing_objects_not_deleted_for_occlusion_alone': True}
    material = diag['source_material']
    proposed, rejected, pose = refit_full_poses(image, room, detections, proposed, rejected, material, source_context=context)
    cells = set(map(tuple, material.get('accepted', [])))
    flat = set(map(tuple, material.get('source_flat_accepted_cells', [])))
    proposed, agreement = agree_new_fulls(image, room, detections, proposed, rejected, cells, flat, source_context=context)
    return proposed, rejected, {**diag, **pose, **agreement}
