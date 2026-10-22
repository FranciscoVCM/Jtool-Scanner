"""Read-only original-source rectangle/appearance evidence.

Hollow terrain can resemble background in mean colour. Repeated raw source frames
can establish a separate appearance hypothesis without changing colour roles.
These read-only APIs produce hypotheses, not an emitted or certified map. The
experimental scanner caller owns qualification/binding; these routines do not
retire old objects or resolve compound spikes. No references or tileset IDs.
"""
from __future__ import annotations

from math import sqrt

from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_occupancy import footprint


def _interior_signature(library, x, y):
    """RGB pattern inside the border; a flat/linear interior supplies no shape.

    Two neighboring borders can correlate with a whole-frame model in genuinely
    empty space. Exclude the outer eighth on each side, retaining independently
    learned original interior artwork rather than letting those borders teach it.
    """
    values = [(i - 7.5, j - 7.5,
               library.pixel(x + 4 + (i + .5) * 1.5, y + 4 + (j + .5) * 1.5))
              for j in range(16) for i in range(16)]
    mean = tuple(sum(rgb[c] for _, _, rgb in values) / 256 for c in range(3))
    dx, dy = sum(u * u for u, _, _ in values), sum(v * v for _, v, _ in values)
    sx = tuple(sum(u * rgb[c] for u, _, rgb in values) / dx for c in range(3))
    sy = tuple(sum(v * rgb[c] for _, v, rgb in values) / dy for c in range(3))
    residual = tuple(rgb[c] - mean[c] - sx[c] * u - sy[c] * v
                     for u, v, rgb in values for c in range(3))
    length = sqrt(sum(value * value for value in residual))
    # Capture rounding and the canonical 8-bit bilinear raster can each add
    # <= .5 per channel to a linear field. Convex interpolation and least-
    # squares plane removal cannot increase that L2 bound. Do not amplify this
    # quantization into unit-strength artwork. Zero means insufficient texture,
    # NOT empty background or permission to delete an existing object.
    if length <= sqrt(3 * len(values)):
        return (0.0,) * len(residual)
    return tuple(value / max(1e-12, length) for value in residual)


def _dot(first, second):
    return sum(a * b for a, b in zip(first, second))


def _distance(first, second):
    return sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _qualified(faces):
    return sum(face.support >= 9 and not face.unknown for face in faces)


def _coherent_exterior(library, x, y):
    values = [library.pixel(x + (i + .5) * 2, y + (j + .5) * 2)
              for j in range(16) for i in range(16)]
    mean = tuple(sum(value[c] for value in values) / len(values) for c in range(3))
    exterior = []
    for px, py in ((x + 16, y - 4), (x + 36, y + 16),
                   (x + 16, y + 36), (x - 4, y + 16)):
        patch = library.raw.sample(px, py, size=4)
        if patch is None:
            continue
        average = tuple(sum(value[c] for value in patch) / len(patch) for c in range(3))
        residual = sqrt(sum(sum((value[c] - average[c]) ** 2 for c in range(3))
                            for value in patch) / len(patch))
        contrast = _distance(average, mean)
        if contrast > 0 and residual <= .1 * contrast:
            exterior.append((average, .1 * contrast))
    return any(sum(_distance(average, other) <= min(limit, other_limit)
                   for other, other_limit in exterior) >= 3
               for average, limit in exterior)


def source_rectangle_proposals(image, room, detections, *, source_context=None):
    """Return source-only full-frame hypotheses and independently derived proof.

    ``detections`` must be the ORIGINAL input snapshot. Fulls locate nearby source
    queries; spikes populate the existing scan-local appearance sampler. Newly
    proposed geometry must never be passed back as teachers. Native mapping is
    800x608; compact-frame adoption remains unqualified.

    Keep nominal and half-source-pixel inset teacher cohorts separate: introducing
    sharper raster evidence must not displace an independently valid nominal
    model. Thresholds are identical. Every model needs three physically disjoint
    original source frames, including two closed frames with coherent exteriors.
    Three-sided teachers and two-sided queries are distinct. A two-sided query
    additionally needs matching interior texture, not just neighboring borders.
    """
    detections = tuple(detections)
    spikes = [(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10]
    context = source_context or SourceEvidenceContext(image, room, spikes)
    context.validate(image, room, spikes)
    locators = {(d.x, d.y) for d in detections if d.type_id == 1}
    if not locators:
        return set(), dict(strong_source_frames=[], models=[], candidates=0,
                           no_new_outputs_as_teachers=True,
                           physically_disjoint_teacher_frames=True,
                           nominal_and_raster_centre_cohorts_separate=True,
                           source_only_not_scanner_binding=True)
    library = context.glyph_library(image, room, spikes)
    field = context.contours()
    points = {(x + dx, y + dy) for x, y in locators
              for dx in (-16, -8, 0, 8, 16) for dy in (-16, -8, 0, 8, 16)
              if 0 <= x + dx <= 768 and 0 <= y + dy <= 576}
    rows = []
    for x, y in sorted(points):
        nominal = field.rectangle(x, y, 32)
        faces = nominal
        if _qualified(nominal) < 4:
            ix, iy = .5 * library.pitch[0], .5 * library.pitch[1]
            corners = ((x + ix, y + iy), (x + 32 - ix, y + iy),
                       (x + 32 - ix, y + 32 - iy), (x + ix, y + 32 - iy))
            inset = [field.edge(corners[i], corners[(i + 1) % 4]) for i in range(4)]
            # One jointly inset rectangle, not four independently selected edges.
            if _qualified(inset) > _qualified(nominal):
                faces = inset
        count = _qualified(faces)
        if count < 2:
            continue
        coherent = _coherent_exterior(library, x, y)
        rows.append(dict(point=(x, y), signature=library.signature(3, x, y),
                         faces=[face.support for face in faces], teacher=count >= 3,
                         nominal_teacher=_qualified(nominal) >= 3,
                         nominal_strong=_qualified(nominal) == 4 and coherent,
                         strong=count == 4 and coherent))
    models, seen = [], set()
    for cohort, strong_flag in (([r for r in rows if r['nominal_teacher']], 'nominal_strong'),
                                (rows, 'strong')):
        for seed in cohort:
            if not seed[strong_flag]:
                continue
            group = []
            for row in cohort:
                if not row['teacher']:
                    continue
                x, y = row['point']
                if any(abs(x - p['point'][0]) < 32 and abs(y - p['point'][1]) < 32
                       for p in group):
                    continue
                if all(_dot(row['signature'], p['signature']) >= .9 for p in [seed, *group]):
                    group.append(row)
            if len(group) < 3 or sum(row[strong_flag] for row in group) < 2:
                continue
            identity = tuple(row['point'] for row in group)
            if identity in seen:
                continue
            seen.add(identity)
            mean = tuple(sum(row['signature'][i] for row in group) / len(group)
                         for i in range(768))
            length = sqrt(sum(value * value for value in mean))
            models.append(dict(teachers=identity,
                               signature=tuple(value / max(length, 1e-12) for value in mean)))
    interior, inner_models, proposed = {}, {}, set()
    def body(point):
        if point not in interior:
            interior[point] = _interior_signature(library, *point)
        return interior[point]
    for row in rows:
        for model in models:
            if _dot(row['signature'], model['signature']) < .9:
                continue
            if not row['teacher']:
                identity = model['teachers']
                if identity not in inner_models:
                    mean = tuple(sum(body(point)[i] for point in identity) / len(identity)
                                 for i in range(768))
                    length = sqrt(sum(value * value for value in mean))
                    inner_models[identity] = tuple(value / max(length, 1e-12) for value in mean)
                if _dot(body(row['point']), inner_models[identity]) < .9:
                    continue
            proposed.add((1, *row['point']))
            break
    return proposed, dict(strong_source_frames=[r['point'] for r in rows if r['strong']],
                          models=[dict(teachers=m['teachers']) for m in models],
                          candidates=len(rows), no_new_outputs_as_teachers=True,
                          physically_disjoint_teacher_frames=True,
                          nominal_and_raster_centre_cohorts_separate=True,
                          source_only_not_scanner_binding=True)


def supplement_source_rectangles(image, room, detections, proposed, rejected,
                                 material_labels, *, source_context=None):
    """Read-only additive trial for the uncalibrated foreground-material branch.

    Preserve prior arbitration and original teachers. Do not duplicate existing
    full/mini coverage or resurrect a rejected key. This trial does not retire
    old poses; the experimental caller owns integration. It must independently
    qualify source identity, whole-map deltas, controls and runtime before adoption.
    """
    proposed, rejected = set(proposed), set(rejected)
    if material_labels:
        return proposed, dict(abstained='independent foreground material already available')
    detections = tuple(detections)
    rectangles, proof = source_rectangle_proposals(
        image, room, detections, source_context=source_context)
    existing = {(d.type_id, d.x, d.y) for d in detections}
    occupied = {p for key in (existing - rejected) | proposed if key[0] in (1, 2)
                for p in footprint(key)}
    additions = {key for key in rectangles - rejected if not footprint(key) <= occupied}
    return proposed | additions, dict(proof=proof, added=sorted(additions),
                                     redundant_abstained=sorted((rectangles - rejected) - additions),
                                     prior_rejected_abstained=sorted(rectangles & rejected),
                                     no_original_objects_retired=True)
