"""Read-only original-source rectangle/appearance evidence.

Hollow terrain can resemble background in mean colour. Repeated raw source frames
can establish a separate appearance hypothesis without changing colour roles.
This diagnostic is NOT bound to the scanner: its hypotheses do not retire old
objects, resolve compound spikes, or certify a map. No references or tileset IDs.
"""
from __future__ import annotations

from math import sqrt

from scripts.source_evidence_context import SourceEvidenceContext


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
    Three-sided teachers and two-sided whole-texture queries are distinct.
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
    proposed = {(1, *row['point']) for row in rows
                if any(_dot(row['signature'], model['signature']) >= .9 for model in models)}
    return proposed, dict(strong_source_frames=[r['point'] for r in rows if r['strong']],
                          models=[dict(teachers=m['teachers']) for m in models],
                          candidates=len(rows), no_new_outputs_as_teachers=True,
                          physically_disjoint_teacher_frames=True,
                          nominal_and_raster_centre_cohorts_separate=True,
                          source_only_not_scanner_binding=True)
