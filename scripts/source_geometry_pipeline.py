"""Complete explicit experimental source geometry pipeline.

No private imports, compiled wrappers, references or newly generated teachers.
Used only by explicit source-geometry mode; ordinary standard scans never enter
this pipeline. All evidence remains local to one original image/frame.
"""
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_full_pose import refit_full_poses
from scripts.source_material_ownership import material_cells
from scripts.source_occupancy import footprint, source_size_repair
from scripts.source_rectangle_prototypes import supplement_source_rectangles
from scripts.source_terrain_agreement import agree_new_fulls
from scripts.source_hollow_pipeline import recover_source_hollow_glyphs
from scripts.source_filled_pipeline import recover_source_filled_glyphs
from scripts.source_sampling import SourceFrame


def joint_proposals(image, room, detections, *, source_context=None, include_growth_confidence=False):
    spikes = [(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10]
    water = [(d.x, d.y, 32, 32) for d in detections if d.type_id in (14, 15, 23)]
    sizing, rejected, size_diag = source_size_repair(image, room, detections, source_context=source_context)
    if include_growth_confidence:
        source_context.record_growth_sizing(detections, sizing, rejected)
    intrinsic = set(map(tuple, size_diag.get('source_calibration', {}).get('accepted', [])))
    material, diag = material_cells(image, room, spikes, water, source_context=source_context)
    existing = {(d.type_id, d.x, d.y) for d in detections}
    occupied = {p for key in existing-rejected if key[0] in (1, 2) for p in footprint(key)}
    occupied |= {p for key in sizing if key[0] == 1 for p in footprint(key)}
    # Do not reinterpret uncertain texture calibration as empty source terrain:
    # pose/size consumers below retain ALL original material evidence. Require
    # the separate source qualification only for supplemental NEW mini growth.
    certainty = set(map(tuple, diag.get('source_new_cell_certainty', material)))
    certainty |= set(map(tuple, diag.get('intrinsic_geometry_appearance_evidence_retained', [])))
    growth_material = material & certainty
    supported_intrinsic, supplemental = growth_material & intrinsic, growth_material-intrinsic
    redundant = {p for p in supplemental if footprint((2, *p)) <= occupied}
    growth = {(2, x, y) for x, y in supported_intrinsic | (supplemental-redundant)}
    return sizing | growth, rejected, dict(source_sizing=size_diag, source_material=diag,
        intrinsic_source_cells_retained=sorted(supported_intrinsic), supplemental_source_cells=sorted(supplemental),
        supplemental_duplicate_coverage_abstained=sorted(redundant), current_source_evidence_not_previous_answers=True,
        source_supported_full_representation_not_new_witnesses=True, no_existing_mini_deletion_or_new_object_witnesses=True)


def source_proposals(image, room, detections, *, source_context=None, source_frame=None,
                     include_hollow_glyphs=True, include_growth_confidence=False,
                     include_filled_glyphs=False, include_filled_joint_phase=False):
    """Return proposals/removals/full proofs, without touching original objects."""
    if not isinstance(include_hollow_glyphs, bool):
        raise ValueError('Hollow recovery flag must be a boolean')
    if not isinstance(include_growth_confidence, bool):
        raise ValueError('Growth confidence flag must be a boolean')
    if not isinstance(include_filled_glyphs, bool):
        raise ValueError('Filled recovery flag must be a boolean')
    if not isinstance(include_filled_joint_phase, bool):
        raise ValueError('Filled joint phase flag must be a boolean')
    if include_filled_joint_phase and not include_filled_glyphs:
        raise ValueError('Joint phase requires filled recovery')
    detections = tuple(detections)
    spikes = [(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10]
    context = source_context if source_context is not None else SourceEvidenceContext(image, room, spikes)
    context.validate(image, room, spikes)
    if include_growth_confidence:
        context.begin_growth(detections)
        proposed, rejected, diag = joint_proposals(image, room, detections, source_context=context,
                                                  include_growth_confidence=True)
    else:
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
    proposed, rejected, pose = refit_full_poses(image, room, detections, proposed, rejected, material,
        source_context=context, source_empty_candidates=diag.get('source_sizing', {}).get('source_empty_full_candidates', ()))
    cells = set(map(tuple, material.get('accepted', [])))
    flat = set(map(tuple, material.get('source_flat_accepted_cells', [])))
    proposed, agreement = agree_new_fulls(image, room, detections, proposed, rejected, cells, flat, source_context=context)
    # Mean-colour roles can abstain on pale hollow terrain. Independent ORIGINAL
    # source rectangles provide a separate, nonredundant positive channel without
    # changing calibration, teaching from outputs, or retiring previous geometry.
    proposed, rectangle = supplement_source_rectangles(
        image, room, detections, proposed, rejected, material.get('selected_clusters', ()),
        source_context=context)
    frame = SourceFrame(image, room) if source_frame is None else source_frame
    if not frame.matches_source(image, room):
        raise ValueError('Hollow source frame does not match the original image/crop')
    # The scanner reaches this pipeline only in explicit source-geometry mode.
    # Preserve a direct numerical ablation switch; standard scanning never enters
    # this stage. Teachers remain frozen original detections, not these proposals.
    hollow_diag = dict(accepted=[], enabled=False, reason='explicit hollow recovery bypass')
    if include_hollow_glyphs:
        # Old material/size/pose retain their physical crop. Only new evidence
        # uses the existing world frame. Never remap or reteach the old stages.
        source_field = context.glyph_library(image, room, spikes).raw if frame.extent == room else None
        hollow, hollow_diag = recover_source_hollow_glyphs(frame, detections, source_field=source_field)
        proposed |= hollow
        # Only source-proved SAME type/size phase replacements can retire old
        # locators. Unverified terrain labels cannot act as coordinate answers.
        rejected |= {tuple(p['old']) for p in hollow_diag.get('phase_repairs', ())}
    diagnostics = {**diag, **pose, **agreement, 'rectangle_fallback': rectangle, 'source_hollow': hollow_diag}
    if include_filled_glyphs:
        # Explicit research opt-in: reuse ORIGINAL source evidence, never the
        # accumulated proposals. A legacy crop library cannot serve an extended
        # world frame; the consumer constructs a correctly framed one instead.
        library = context.glyph_library(image, room, spikes) if frame.extent == room else None
        filled, filled_diag = recover_source_filled_glyphs(
            frame, detections, source_library=library, joint_phase=include_filled_joint_phase)
        proposed |= filled
        diagnostics['source_filled'] = filled_diag
    if include_growth_confidence:
        from scripts.source_growth_confidence import qualify_independent_growth
        evidence = context.growth_evidence(detections)
        observations = evidence.pop('observations')
        joint_cells = set(map(tuple, diag.get('intrinsic_source_cells_retained', ())))
        joint_cells |= set(map(tuple, diag.get('supplemental_source_cells', ())))
        before_growth = set(proposed)
        phase_positive = {tuple(p['new']) for p in pose.get('texture_pose_proofs', ())}
        proposed, growth = qualify_independent_growth(proposed, existing, room=room,
            phase_positive=phase_positive, joint_cells=joint_cells, **evidence)
        diagnostics['source_growth_confidence'] = {**growth, 'qualified_shadow_roles': observations,
            'original_proposals': sorted(before_growth), 'original_retired': sorted(rejected),
            'protected_phase_positive_keys': sorted(phase_positive),
            'original_material_evidence_unchanged': True}
    return proposed, rejected, diagnostics
