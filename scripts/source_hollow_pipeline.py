"""Source-proven hollow full-spike recovery from frozen original locators.

No existing object is retired here. Failed source evidence is not evidence of
absence: true touching and occluded spikes must survive. All new objects need
the complete source predicate; references and generated proposals cannot teach.
"""
from scripts.source_hollow_glyphs import HollowGlyphEvidence


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
    return proposed, dict(accepted=proofs, original_teachers_only=True,
        original_source_coverage_checked=True, hypotheses=len(hypotheses),
        nominal_models=evidence.nominal_model_count, inset_models=evidence.inset_model_count,
        no_existing_object_retirement=True)
