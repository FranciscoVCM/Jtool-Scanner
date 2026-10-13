"""Source-proven hollow full-spike recovery from frozen original locators.

Only a uniquely source-proved same-type/size phase repair can replace an old
locator. Failed source evidence alone is not absence: true touching and occluded
spikes survive. All new objects need the complete source predicate; references
and generated proposals cannot teach.
"""
from math import dist

from jtool_scanner.spike_shape import VERTICES
from scripts.source_hollow_glyphs import HollowGlyphEvidence
from scripts.source_hollow_phase import refit_source_hollow_phases


def respect_original_terrain_anchors(proposed, original_detections, evidence):
    """Do not duplicate a source-qualified, more strongly attached original.

    Reuse the same attachment rule as common-room arbitration, rather than
    suppressing arbitrary neighbors/overlaps. Both poses must have complete
    RGB proof from the same original-source model. No originals are changed.
    """
    from jtool_scanner.scanner import _align_warm_spike_to_terrain, _warm_spike_support_overlap
    original = tuple(original_detections)
    existing = {(d.type_id, d.x, d.y) for d in original}
    blocks = {(d.x, d.y) for d in original if d.type_id == 1}
    retained, abstained = set(), []
    for key in sorted(proposed):
        t, x, y = key
        direction = {3: 'up', 4: 'right', 5: 'left', 6: 'down'}[t]
        ax, ay = _align_warm_spike_to_terrain(x, y, direction, blocks)
        aligned = t, ax, ay
        stronger = (abs(ax-x)+abs(ay-y) <= 8
            and _warm_spike_support_overlap(ax, ay, direction, blocks)
            > _warm_spike_support_overlap(x, y, direction, blocks))
        if aligned not in existing or not stronger:
            retained.add(key)
            continue
        current, previous = evidence.support(key), evidence.support(aligned)
        common = ({p['original_teachers'] for p in current['proof']}
                  & {p['original_teachers'] for p in previous['proof']})
        if not common:
            retained.add(key)
            continue
        # Two genuinely visible tips can belong to distinct touching/overlapping
        # objects. Stronger terrain attachment cannot erase that RGB evidence.
        def original_tip_ink(pose, model):
            st, sx, sy = pose
            u, v = VERTICES[st][0]
            values = [evidence.frame.original_pixel(sx+u+dx, sy+v+dy)
                      for dx in (0, -evidence.frame.pitch[0], evidence.frame.pitch[0])
                      for dy in (0, -evidence.frame.pitch[1], evidence.frame.pitch[1])]
            if any(rgb is None for rgb in values):
                return None
            return any(dist(rgb, model['foreground']) < dist(rgb, model['background'])
                       for rgb in values)
        tips = [(original_tip_ink(key, model), original_tip_ink(aligned, model))
                for model in evidence.models if model['independent_teachers'] in common]
        if any(a is None or b is None or (a and b) for a, b in tips):
            retained.add(key)
            continue
        abstained.append(dict(key=key, original=aligned,
            common_original_models=sorted(common), stronger_existing_terrain_face=True,
            no_existing_object_removed=True))
    return retained, abstained


def recover_source_hollow_glyphs(frame, original_detections, *, source_field=None):
    """Return new full32 poses/proofs, without changing any original Detection.

    Search the same finite 8px/16px neighborhood around original full locators;
    all four directions compete. The frame is the existing capture view, not
    a second inferred normalization. No speculative fill or coordinate whitelist.
    """
    original = tuple(original_detections)
    spikes = [(d.type_id, d.x, d.y) for d in original if 3 <= d.type_id <= 10]
    evidence = HollowGlyphEvidence.from_frame(frame, spikes,
        **({'source_field': source_field} if source_field is not None else {}))
    existing = {(d.type_id, d.x, d.y) for d in original}
    proposed = set()
    proofs = []
    if not any(evidence.owned_models.values()):
        return proposed, dict(accepted=[], original_teachers_only=True,
                              reason='no independently owned hollow source model')
    hypotheses = sorted({(t, x+dx, y+dy) for st, x, y in spikes if st <= 6
        for dx in (-16, -8, 0, 8, 16) for dy in (-16, -8, 0, 8, 16)
        for t in (3, 4, 5, 6) if 0 <= x+dx <= 768 and 0 <= y+dy <= 576})
    for key in hypotheses:
        if key in existing:
            continue
        proof = evidence.support(key)
        if proof['passed']:
            proposed.add(key)
            proofs.append(dict(key=key, evidence=proof))
        # Source predicates are deterministic; discard memo entries only, never
        # teacher/proof data. Cache eviction cannot change the evidence bounds.
        for cache, limit in ((evidence.gradients, 100000), (evidence.edges, 10000),
                             (evidence.ink_edges, 5000), (evidence.raw_ink_edges, 10000),
                             (evidence.owned_edges, 10000)):
            if len(cache) > limit:
                cache.clear()
    proposed, abstained = respect_original_terrain_anchors(proposed, original, evidence)
    proofs = [row for row in proofs if tuple(row['key']) in proposed]
    phase_repairs = refit_source_hollow_phases(evidence, original, proposed)
    return proposed, dict(accepted=proofs, original_anchor_abstentions=abstained,
        phase_repairs=phase_repairs,
        original_teachers_only=True,
        original_source_coverage_checked=True, hypotheses=len(hypotheses),
        nominal_models=evidence.nominal_model_count, inset_models=evidence.inset_model_count,
        no_existing_object_retirement=not phase_repairs,
        no_original_mini_nonterrain_or_source_positive_retirement=True)
