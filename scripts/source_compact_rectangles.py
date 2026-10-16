"""Read-only original-source rectangle queries under an explicit capture frame.

Not app-bound. No game IDs, stored palettes, reference maps, global patches or
emitted teachers. Original full spikes locate finite queries; independent source
shape and interior artwork qualify them. A backing query is not a block answer.
"""
from copy import deepcopy
from math import sqrt

from jtool_scanner.image import RGBImage
from scripts.source_contours import SourceContours
from scripts.source_glyph_prototypes import SourceGlyphLibrary
from scripts.source_rectangle_prototypes import _coherent_exterior, _dot, _interior_signature, _qualified


def full_spike_backings(detections):
    """Return nominal 32px backing queries, not assumed solid geometry."""
    result = set()
    for detection in detections:
        if detection.type_id not in (3, 4, 5, 6):
            continue
        dx, dy = {3: (0, 32), 4: (-32, 0), 5: (32, 0), 6: (0, -32)}[detection.type_id]
        x, y = detection.x + dx, detection.y + dy
        if 0 <= x <= 768 and 0 <= y <= 576:
            result.add((x, y))
    return result


def _original_neighborhoods(detections):
    locators = {(d.x, d.y) for d in detections if d.type_id == 1}
    return {(x + dx, y + dy) for x, y in locators
            for dx in (-16, -8, 0, 8, 16) for dy in (-16, -8, 0, 8, 16)
            if 0 <= x + dx <= 768 and 0 <= y + dy <= 576}


def _faces(library, field, x, y):
    nominal = field.rectangle(x, y, 32)
    faces = nominal
    if _qualified(nominal) < 4:
        ix, iy = .5 * library.pitch[0], .5 * library.pitch[1]
        corners = ((x + ix, y + iy), (x + 32 - ix, y + iy),
                   (x + 32 - ix, y + 32 - iy), (x + ix, y + 32 - iy))
        inset = [field.edge(corners[i], corners[(i + 1) % 4]) for i in range(4)]
        if _qualified(inset) > _qualified(nominal):
            faces = inset
    return nominal, faces


def _mean_signature(signatures):
    values = tuple(sum(row[i] for row in signatures) / len(signatures) for i in range(768))
    length = sqrt(sum(v * v for v in values))
    return tuple(v / max(1e-12, length) for v in values)


class SourceRectangleContext:
    """One immutable source/frame/COMPLETE original Detection snapshot.

    This deliberately does not reuse a legacy material context whose physical
    room assumes an unpadded 800x608 source. Only contours/appearance are shared
    here; no color-role calibration or other source path is silently reinterpreted.
    """

    def __init__(self, image, room, originals, source_frame):
        if not isinstance(image.data, bytes) or len(image.data) != image.width * image.height * 3:
            raise ValueError('Rectangle evidence requires complete immutable original RGB')
        if not source_frame.matches_source(image, room):
            raise ValueError('Rectangle source frame does not match image/room')
        self._original = image
        self._source = RGBImage(image.width, image.height, image.data)
        self._room, self._frame = room, source_frame
        self._extent, self._canonical = source_frame.extent, source_frame.canonical_rgb
        self._originals = deepcopy(tuple(originals))
        self._field = self._library = self._models = self._model_proof = None

    def validate(self, image, room, originals, source_frame):
        if (image is not self._original or image.data is not self._source.data
                or (image.width, image.height, room) != (self._source.width, self._source.height, self._room)):
            raise ValueError('Rectangle source image/data/room changed')
        if (source_frame is not self._frame or source_frame.extent != self._extent
                or source_frame.canonical_rgb is not self._canonical
                or not source_frame.matches_source(image, room)):
            raise ValueError('Rectangle source frame changed')
        if tuple(originals) != self._originals:
            raise ValueError('Rectangle original detections changed; proposals cannot teach')

    def _appearance(self):
        if self._library is None:
            self._field = SourceContours(self._source, self._frame.extent, source_frame=self._frame)
            # No expensive/irrelevant glyph models, and no glyph teachers.
            self._library = SourceGlyphLibrary(self._source, self._room, (),
                source_frame=self._frame, contour_field=self._field)
        return self._library, self._field

    def _source_models(self):
        if self._models is not None:
            return self._models
        library, field = self._appearance()
        rows, candidates = [], 0
        for x, y in sorted(_original_neighborhoods(self._originals)):
            if not self._frame.rectangle_available(x, y, 32, 32, margin=6):
                continue
            nominal, faces = _faces(library, field, x, y)
            count = _qualified(faces)
            if count < 2:
                continue
            candidates += 1
            if count < 3:
                # Two-face rows can never seed/join either teacher cohort. Do
                # not compute unused appearance/coherence or classify old queries.
                continue
            coherent = _coherent_exterior(library, x, y) if count == 4 else False
            rows.append(dict(point=(x, y), signature=library.signature(3, x, y),
                nominal_teacher=_qualified(nominal) >= 3,
                nominal_strong=_qualified(nominal) == 4 and coherent,
                strong=count == 4 and coherent))
        models, seen = [], set()
        for cohort, flag in (([r for r in rows if r['nominal_teacher']], 'nominal_strong'), (rows, 'strong')):
            for seed in cohort:
                if not seed[flag]:
                    continue
                group = []
                for row in cohort:
                    x, y = row['point']
                    if any(abs(x - p['point'][0]) < 32 and abs(y - p['point'][1]) < 32 for p in group):
                        continue
                    if all(_dot(row['signature'], p['signature']) >= .9 for p in [seed, *group]):
                        group.append(row)
                if len(group) < 3 or sum(row[flag] for row in group) < 2:
                    continue
                teachers = tuple(row['point'] for row in group)
                if teachers in seen:
                    continue
                seen.add(teachers)
                models.append(dict(teachers=teachers,
                    signature=_mean_signature([row['signature'] for row in group]),
                    interior=_mean_signature([_interior_signature(library, *point) for point in teachers])))
        self._models = tuple(models)
        self._model_proof = dict(strong_source_frames=[r['point'] for r in rows if r['strong']],
            models=[dict(teachers=model['teachers']) for model in models], candidates=candidates,
            no_new_outputs_as_teachers=True, physically_disjoint_teacher_frames=True,
            nominal_and_raster_centre_cohorts_separate=True, source_only_not_scanner_binding=True)
        return self._models


def source_backing_rectangles(image, room, detections, *, source_frame, source_context=None):
    """Return query-only hypotheses/proofs, never change or emit a ScanResult.

    Keep the existing original full-pose neighborhoods, including independently
    supported neighboring phases. Only NEW backing queries are excluded from
    teachers. Unknown coverage abstains, not negative or positive source evidence.
    """
    originals = tuple(detections)
    context = source_context or SourceRectangleContext(image, room, originals, source_frame)
    context.validate(image, room, originals, source_frame)
    query_only = full_spike_backings(originals) - _original_neighborhoods(originals)
    rows, accepted = [], set()
    for x, y in sorted(query_only):
        row = dict(point=[x, y], query_only=True, teacher=False, passed=False)
        if not source_frame.rectangle_available(x, y, 32, 32, margin=6):
            row['abstained'] = 'unknown physical/filtered source footprint'
            rows.append(row)
            continue
        library, field = context._appearance()
        _, faces = _faces(library, field, x, y)
        row.update(faces=[f.support for f in faces], unknown_faces=[f.unknown for f in faces])
        if _qualified(faces) < 2:
            row['abstained'] = 'fewer than two source-supported rectangle faces'
        else:
            signature = library.signature(3, x, y)
            interior = _interior_signature(library, x, y)
            row['model_comparisons'] = [dict(teachers=model['teachers'],
                frame_correlation=_dot(signature, model['signature']),
                interior_correlation=_dot(interior, model['interior'])) for model in context._source_models()]
            row['passed'] = any(c['frame_correlation'] >= .9 and c['interior_correlation'] >= .9
                                for c in row['model_comparisons'])
            if row['passed']:
                accepted.add((1, x, y))
        rows.append(row)
    context.validate(image, room, originals, source_frame)
    return accepted, dict(original_rectangle_proof=deepcopy(context._model_proof),
        query_only_points=sorted(query_only), query_rows=rows, no_new_query_teachers=True,
        empty_glyph_teacher_count=0, original_thresholds_unchanged=True,
        original_outputs_NOT_mutated=True, not_app_bound=True)
