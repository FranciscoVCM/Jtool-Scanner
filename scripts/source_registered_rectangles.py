"""Automatic ORIGINAL source-frame cohorts for read-only RGB corroboration.

No reference files, stored tilesets, room identities, emissions or scanner binding.
This is the fixed registered-cohort algorithm, not a new rectangle classifier.
Locators select finite original-source queries; no new query can teach another.
"""
from dataclasses import asdict
from itertools import combinations
from math import ceil, floor, sqrt

from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_rectangle_prototypes import _coherent_exterior, _dot, _qualified
from scripts.source_rgb_distribution import SourceRGBDistribution


def _disjoint(first, second):
    x0, y0, x1, y1 = first['physical']
    u0, v0, u1, v1 = second['physical']
    return max(x0, u0) >= min(x1, u1) or max(y0, v0) >= min(y1, v1)


def registered_rectangle_models(image, room, detections, *, source_grid,
                                source_frame, source_context=None):
    """Mine source-only original cohorts; return proof, never terrain proposals.

    Callers must freeze ORIGINAL detections before new proposals. Explicit grid
    identity prevents a compact capture being interpreted as standard800x608.
    Reuse the already-built source frame/context to avoid duplicate evidence.
    """
    detections = tuple(detections)
    if not source_frame.matches_source(image, room):
        raise ValueError('Registered rectangle frame must match original source')
    spikes = [(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10]
    context = source_context or SourceEvidenceContext(image, room, spikes)
    context.validate(image, room, spikes)
    proof = dict(models=[], cohorts=[], candidates=0, query_points=0,
        no_objects_changed=True, no_new_outputs_as_teachers=True,
        original_source_only=True, physically_disjoint_teacher_frames=True)
    if source_grid != (25, 19) or source_frame.extent != room:
        return {**proof, 'abstained': 'native grid/world transform not qualified'}
    locators = {(d.x, d.y) for d in detections if d.type_id == 1}
    if not locators:
        return proof
    library = context.glyph_library(image, room, spikes)
    field = context.contours()

    def faces_at(x, y):
        nominal = field.rectangle(x, y, 32)
        faces, inset = nominal, False
        if _qualified(nominal) < 4:
            ix, iy = .5 * library.pitch[0], .5 * library.pitch[1]
            corners = ((x + ix, y + iy), (x + 32 - ix, y + iy),
                       (x + 32 - ix, y + 32 - iy), (x + ix, y + 32 - iy))
            alternate = [field.edge(corners[i], corners[(i + 1) % 4]) for i in range(4)]
            if _qualified(alternate) > _qualified(nominal):
                faces, inset = alternate, True
        return nominal, faces, inset

    points = {(x + dx, y + dy) for x, y in locators
              for dx in (-16, -8, 0, 8, 16) for dy in (-16, -8, 0, 8, 16)
              if 0 <= x + dx <= 768 and 0 <= y + dy <= 576}
    rows = []
    for x, y in sorted(points):
        nominal, faces, _ = faces_at(x, y)
        count = _qualified(faces)
        if count < 2:
            continue
        coherent = _coherent_exterior(library, x, y)
        rows.append(dict(point=(x, y), teacher=count >= 3,
            nominal_teacher=_qualified(nominal) >= 3,
            nominal_strong=_qualified(nominal) == 4 and coherent,
            strong=count == 4 and coherent))
    variants_cache, geometry_cache, scores, models, seen, cohorts = {}, {}, {}, [], set(), []

    def variants(row, group=()):
        point = row['point']
        if point not in variants_cache:
            values = []
            x, y = point
            for dx in (0, -library.pitch[0], library.pitch[0]):
                for dy in (0, -library.pitch[1], library.pitch[1]):
                    px, py = x + dx, y + dy
                    if not source_frame.rectangle_available(px, py, 32, 32, margin=4):
                        continue
                    values.append(dict(point=point, phase=(dx, dy), registered=(px, py), known=True,
                        physical=(floor(room.x + px * room.width / 800),
                                  floor(room.y + py * room.height / 608),
                                  ceil(room.x + (px + 32) * room.width / 800),
                                  ceil(room.y + (py + 32) * room.height / 608)),
                        signature=library.signature(3, px, py)))
            variants_cache[point] = values
        for candidate in variants_cache[point]:
            # Independent conjunction gates commute. Closed seeds have no
            # group and still materialize every known phase; growing groups
            # need not read contours for an already-incompatible RGB body.
            if group and (not all(_disjoint(candidate, other) for other in group)
                    or min(correlation(candidate, other) for other in group) < .9):
                continue
            key = point, candidate['phase']
            if key not in geometry_cache:
                px, py = candidate['registered']
                nominal, faces, inset = faces_at(px, py)
                count = _qualified(faces)
                geometry_cache[key] = (dict(candidate, faces=[asdict(f) for f in faces],
                    joint_inset=inset, coherent_closed=count == 4 and _coherent_exterior(library, px, py),
                    nominal_teacher=_qualified(nominal) >= 3) if count >= 3 else None)
            if geometry_cache[key] is not None:
                yield geometry_cache[key]

    def correlation(first, second):
        a, b = (first['point'], first['phase']), (second['point'], second['phase'])
        key = (a, b) if a <= b else (b, a)
        if key not in scores:
            scores[key] = _dot(first['signature'], second['signature'])
        return scores[key]

    for cohort, flag, label in (([r for r in rows if r['nominal_teacher']], 'nominal_strong', 'nominal'),
                                (rows, 'strong', 'selected nominal-or-inset')):
        teachers = [r for r in cohort if r['teacher']]
        seeds = [r for r in teachers if r[flag]]
        closed = [dict(v, original_closed_seed=True) for row in seeds for v in variants(row)
                  if v['coherent_closed'] and (label != 'nominal' or v['nominal_teacher'])]
        pairs = [(a, b) for a, b in combinations(closed, 2)
                 if a['point'] != b['point'] and _disjoint(a, b) and correlation(a, b) >= .9]
        cohorts.append(dict(cohort=label, original_teacher_points=len(teachers),
            original_closed_seed_points=len(seeds), eligible_closed_phase_variants=len(closed),
            eligible_disjoint_closed_pair_assignments=len(pairs)))
        for a, b in pairs:
            group = [a, b]
            for row in teachers:
                if any(row['point'] == v['point'] for v in group):
                    continue
                best, best_score = None, -1
                for variant in variants(row, group):
                    if label == 'nominal' and not variant['nominal_teacher']:
                        continue
                    if not all(_disjoint(variant, other) for other in group):
                        continue
                    score = min(correlation(variant, other) for other in group)
                    if score >= .9 and score > best_score:
                        best, best_score = variant, score
                if best is not None:
                    group.append(dict(best, original_closed_seed=bool(row[flag] and best['coherent_closed'])))
            if len(group) < 3 or sum(v['original_closed_seed'] for v in group) < 2:
                continue
            identity = label, tuple(sorted((v['point'], v['phase']) for v in group))
            if identity in seen:
                continue
            seen.add(identity)
            pair_min = min(correlation(a, b) for a, b in combinations(group, 2))
            mean = tuple(sum(v['signature'][i] for v in group) / len(group) for i in range(768))
            length = sqrt(sum(v * v for v in mean))
            mean = tuple(v / max(1e-12, length) for v in mean)
            consensus = min(_dot(v['signature'], mean) for v in group)
            models.append(dict(cohort=label, teacher_count=len(group),
                minimum_pairwise_RGB_correlation=pair_min, minimum_mean_RGB_correlation=consensus,
                all_actual_physical_bodies_disjoint=True,
                teachers=[{k: v for k, v in row.items() if k != 'signature'} for row in group],
                SEMANTIC_SOURCE_QA_PENDING=True, NOT_terrain_emissions=True))
    return {**proof, 'models': models, 'cohorts': cohorts,
            'candidates': len(rows), 'query_points': len(points)}


def original_background_glyphs(detections, material):
    """Select only already-calibrated ORIGINAL background fronts, not new poses."""
    original = {(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10}
    tips = {int(k): v for k, v in material.get('tip_votes', {}).items()}
    backs = {int(k): v for k, v in material.get('background_back_votes', {}).items()}
    background = {c for c, count in tips.items()
                  if count >= 3 and count / (count + backs.get(c, 0)) >= .75}
    keys, seen = [], set()
    for anchor in material.get('background_anchors', ()):
        key = tuple(anchor['key'])
        if key not in original:
            raise ValueError('Background calibration contains a non-original glyph')
        if anchor['front_cluster'] in background and key not in seen:
            seen.add(key)
            keys.append(key)
    return tuple(keys)


def original_rgb_models(image, room, detections, material, *, source_grid,
                        source_frame, source_context=None):
    """Discover/recheck read-only RGB models without hand-picked source positions."""
    detections = tuple(detections)
    proof = registered_rectangle_models(image, room, detections, source_grid=source_grid,
        source_frame=source_frame, source_context=source_context)
    if not proof['models']:
        return (), {**proof, 'RGB_models': 0}
    background = original_background_glyphs(detections, material)
    models, seen = [], set()
    for cohort in proof['models']:
        parents = tuple(tuple(row['registered']) for row in cohort['teachers'])
        if parents in seen:
            continue
        seen.add(parents)
        model = SourceRGBDistribution(source_frame, parents, background)
        if model.reason is None:
            models.append(model)
    return tuple(models), {**proof, 'RGB_models': len(models), 'original_background_glyphs': background}
