"""Source-verified arrow sprites can explain false full-spike geometry.

This is not a bounding-box veto. Verify the existing marker's coloured shaft,
fit its complete original RGB silhouette against filled/outlined arrow shapes,
and require every observed candidate edge to belong to that source ink. Original
RGB contours veto retirement when a faint hazard coexists outside the arrow.
Keep visible overlapping hazards and abstain on unknown/unsupported evidence.
No reference map, game identity or newly emitted teacher enters the proof.
"""
from functools import lru_cache
from math import dist
from dataclasses import asdict

from PIL import Image, ImageDraw, ImageFilter

from jtool_scanner.constants import OBJ_GRAVITY_DOWN, OBJ_GRAVITY_UP
from jtool_scanner.spike_shape import VERTICES
from scripts.source_contours import SourceContours
from scripts.source_sampling import SourceFrame

_FULL_SPIKES = frozenset((3, 4, 5, 6))
_ARROWS = frozenset((OBJ_GRAVITY_UP, OBJ_GRAVITY_DOWN))
_MODEL_FIELDS = ('native_head_height', 'native_head_width', 'native_shaft_width',
                 'native_outline_radius', 'native_source_shape_translation')


@lru_cache(maxsize=2)
def _arrow_models(down):
    """Immutable geometry/style models, without sprite RGB or room coordinates."""
    models = []
    for height in (12, 14, 16, 18, 20):
        for width in (28, 32):
            for shaft in (8, 12, 16):
                base = Image.new('L', (32, 32))
                draw = ImageDraw.Draw(base)
                draw.polygon(((16, 0), (16-width/2, height),
                              (16+width/2, height)), fill=255)
                draw.rectangle((16-shaft/2, height-1, 16+shaft/2, 31), fill=255)
                for stroke in (0, 1, 2):
                    mask = (base if stroke == 0 else
                            base.filter(ImageFilter.MaxFilter(stroke*2+1)))
                    if down:
                        mask = mask.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                    points = {(x, y) for y in range(16) for x in range(16)
                              if mask.getpixel((2*x+1, 2*y+1))}
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            shifted = frozenset((x+dx, y+dy) for x, y in points
                                                if 0 <= x+dx < 16 and 0 <= y+dy < 16)
                            models.append(((height, width, shaft, stroke,
                                            (2*dx, 2*dy)), shifted))
    return tuple(models)


def _outside_arrow_segments(first, last, boxes):
    """Clip original slope intervals, never invent edges around a masked raster."""
    vx, vy = last[0]-first[0], last[1]-first[1]
    breaks = {0., 1.}
    for left, top, right, bottom in boxes:
        for origin, delta, bounds in ((first[0], vx, (left, right)),
                                       (first[1], vy, (top, bottom))):
            if delta:
                breaks.update(t for bound in bounds if 0 < (t := (bound-origin)/delta) < 1)
    intervals = []
    ordered = sorted(breaks)
    for low, high in zip(ordered, ordered[1:]):
        mid = (low+high)/2
        x, y = first[0]+mid*vx, first[1]+mid*vy
        if any(left <= x <= right and top <= y <= bottom
               for left, top, right, bottom in boxes):
            continue
        if intervals and abs(intervals[-1][1]-low) < 1e-10:
            intervals[-1] = intervals[-1][0], high
        else:
            intervals.append((low, high))
    return [(tuple(first[i]+low*(last[i]-first[i]) for i in (0, 1)),
             tuple(first[i]+high*(last[i]-first[i]) for i in (0, 1)))
            for low, high in intervals]


def _rgb_coexistence(image, room, candidate, owner, admissible, source_frame):
    """A necessary retention guard, not proof of absent or present hidden objects.

    A bright marker can conceal a faint triangle from the legacy luminance edge
    mask. Probe only the original candidate slopes outside the SAME two-pixel
    arrow halo, using the shared local-gradient RGB kernel. The base can coincide
    with a real ceiling; it is not an independent visible spike slope.
    """
    frame = SourceFrame(image, room) if source_frame is None else source_frame
    field = SourceContours(frame.original_snapshot(), frame.extent,
                           source_frame=frame, probe_cache_limit=512)
    points = [(candidate.x+x, candidate.y+y) for x, y in VERTICES[candidate.type_id]]
    seen, rows, retain = set(), [], False
    for parameters, ink in admissible:
        ink = frozenset(ink)
        if ink in seen:
            continue
        seen.add(ink)
        boxes = [(owner.x+2*x-2, owner.y+2*y-2,
                  owner.x+2*x+4, owner.y+2*y+4) for x, y in ink]
        for slope, end in enumerate(points[1:]):
            for first, last in _outside_arrow_segments(points[0], end, boxes):
                centers = [frame.original_position(
                    first[0]+(.15+.7*i/11)*(last[0]-first[0]),
                    first[1]+(.15+.7*i/11)*(last[1]-first[1])) for i in range(12)]
                capacity = len({p for p in centers if p is not None})
                raw = field.edge(first, last)
                unknown = None in centers or capacity < 4 or raw.unknown
                required = (3*capacity+3)//4
                independent = not unknown and raw.support >= required
                keep = unknown or independent
                retain |= keep
                rows.append(dict(shape=dict(zip(_MODEL_FIELDS, parameters)),
                    slope=slope, first=first, last=last, source_capacity=capacity,
                    required=required, raw=asdict(raw), unknown=unknown,
                    independent_RGB_edge=independent, retain=keep))
    return dict(retain=retain, rows=rows, original_slopes_only=True,
                no_artificial_mask_edges=True, local_gradient_RGB_preserved=True,
                NOT_absence_proof=True)


def explain_arrow_owned_spike(image, room, candidate, owner, *, source_grid,
                              source_frame=None):
    """Return positive ownership only; a failed proof never means empty source."""
    # Reuse the maintained marker verification and geometry sampling kernels.
    from jtool_scanner import scanner

    unknown = dict(passed=False, unknown=True,
                   reason='unsupported original geometry/owner/frame')
    if (source_grid != (25, 19) or candidate.type_id not in _FULL_SPIKES
            or owner.type_id not in _ARROWS
            or any(type(v) is not int for v in
                   (candidate.x, candidate.y, owner.x, owner.y))
            or not (0 <= candidate.x <= 768 and 0 <= candidate.y <= 576
                    and 0 <= owner.x <= 768 and 0 <= owner.y <= 576)
            or min(room.width, room.height) <= 0 or room.x < 0 or room.y < 0
            or room.right > image.width or room.bottom > image.height):
        return unknown
    if source_frame is not None and (
            not isinstance(source_frame, SourceFrame) or source_frame.extent != room
            or not source_frame.matches_source(image, room)):
        return unknown
    if (max(candidate.x, owner.x) >= min(candidate.x+32, owner.x+32)
            or max(candidate.y, owner.y) >= min(candidate.y+32, owner.y+32)):
        return dict(passed=False, unknown=False, reason='no candidate/sprite overlap')

    down = owner.type_id == OBJ_GRAVITY_DOWN
    # These are the existing semantic red/blue arrow predicates, not a terrain
    # palette or a background-colour assumption. Unmatched markers abstain.
    predicate = ((lambda r, g, b: b > 130 and b > r+70 and g > r+50) if down else
                 (lambda r, g, b: r > 140 and r > g+30 and r > b+20))
    score, count = scanner._arrow_color_shape_score(
        image, room, owner.x, owner.y, predicate, down)

    def sample(x, y):
        px = int(room.x+(owner.x+x)*room.width/800)
        py = int(room.y+(owner.y+y)*room.height/608)
        return image.pixel(px, py) if 0 <= px < image.width and 0 <= py < image.height else None

    values = {(x, y): sample(2*x+1, 2*y+1) for y in range(16) for x in range(16)}
    if any(rgb is None for rgb in values.values()):
        return unknown
    colored = {p for p, rgb in values.items() if predicate(*rgb)}
    assert len(colored) == count
    ys = tuple(15-y if down else y for y in (12, 14))
    shaft = sum((x, y) in colored for y in ys for x in (6, 7, 8, 9, 10))
    flanks = sum((x, y) in colored for y in ys for x in (2, 3, 13, 14))
    proof = dict(passed=False, unknown=False, arrow_template_score=score,
                 arrow_colored_sites=count, shaft_colored_sites=shaft,
                 shaft_flank_colored_sites=flanks)
    if score < .60 or not 30 <= count <= 150 or shaft < 6 or flanks > 1:
        return {**proof, 'reason': 'source arrow template/independent shaft not certified'}

    corners = []
    for ysites in ((1, 3), (29, 31)):
        for xsites in ((1, 3), (29, 31)):
            patches = [(x, y, sample(x, y)) for y in ysites for x in xsites]
            if any(rgb is None for x, y, rgb in patches):
                return {**proof, 'unknown': True, 'reason': 'unknown source corner'}
            mean = tuple(sum(rgb[c] for x, y, rgb in patches)/4 for c in range(3))
            corners.append((patches, mean))

    def background(x, y):
        u, v = (x-2)/28, (y-2)/28
        return tuple((1-u)*(1-v)*corners[0][1][c]+u*(1-v)*corners[1][1][c]
                     +(1-u)*v*corners[2][1][c]+u*v*corners[3][1][c]
                     for c in range(3))

    contrast = min(dist(values[(x, y)], background(2*x+1, 2*y+1)) for x, y in colored)
    limit = .25*contrast
    error = max(dist(rgb, background(x, y)) for patches, mean in corners
                for x, y, rgb in patches)
    proof.update(source_core_background_contrast=contrast, source_background_limit=limit,
                 source_corner_maximum_error=error)
    if not limit > 0 or error > limit:
        return {**proof, 'reason': 'incoherent original exterior background'}
    foreground = {p for p, rgb in values.items()
                  if dist(rgb, background(2*p[0]+1, 2*p[1]+1)) > limit}
    best, explanations = None, []
    for parameters, expected in _arrow_models(down):
        overlap = len(foreground & expected)
        precision = overlap/max(1, len(foreground))
        recall = overlap/max(1, len(expected))
        rank = (min(precision, recall), precision+recall)
        if best is None or rank > best[0]:
            best = rank, parameters, precision, recall
        explanations.append((rank, parameters, foreground & expected))
    _, parameters, precision, recall = best
    proof.update(full_source_foreground_sites=len(foreground),
                 arrow_shape_precision=precision, arrow_shape_recall=recall,
                 arrow_source_shape=dict(zip(_MODEL_FIELDS, parameters)),
                 foreground_ink_cells=sorted(foreground))
    if precision < .90 or recall < .90:
        return {**proof, 'reason': 'complete source foreground is not a certified arrow silhouette'}
    # Choose from the source silhouette alone, before the candidate's edges.
    # Preserve all tied optimal explanations, not an arbitrary tie winner.
    admissible = [(parameters, ink) for rank, parameters, ink in explanations
                  if rank == best[0]]

    patch = scanner._patch_features(image, room, candidate.x, candidate.y, 32)
    edges = [(candidate.x+(i % 16)*2+1, candidate.y+(i // 16)*2+1)
             for i, hit in enumerate(patch.edge_mask) if hit]

    def owned(x, y, ink):
        # One existing geometry sample: the forward-difference kernel and
        # source interpolation can place its edge just outside observed ink.
        return any(owner.x+2*sx-2 <= x < owner.x+2*sx+4
                   and owner.y+2*sy-2 <= y < owner.y+2*sy+4
                   for sx, sy in ink)

    # A shape fit tolerates a little unexplained source foreground; those
    # pixels are not arrow evidence. Nor may the best fit erase uncertainty
    # in another tied source explanation. Every optimal fit must own the edge.
    model_edges = [(parameters, [p for p in edges if not owned(*p, ink)])
                   for parameters, ink in admissible]
    unowned = [p for p in edges if any(p in missing for _, missing in model_edges)]
    passed = bool(edges) and not unowned
    rgb = (_rgb_coexistence(image, room, candidate, owner, admissible, source_frame)
           if passed else None)
    if rgb is not None and rgb['retain']:
        passed = False
    return {**proof, 'passed': passed, 'candidate_edge_count': len(edges),
            'unowned_candidate_edge_sites': unowned, 'halo_native_pixels': 2,
            'admissible_arrow_shapes': len(admissible),
            'all_admissible_shapes_own_edges': not unowned,
            'shape_ownership': [dict(shape=dict(zip(_MODEL_FIELDS, parameters)),
                                     unowned_edge_sites=missing)
                                for parameters, missing in model_edges],
            'rgb_coexistence': rgb,
            'reason': ('all geometry edges owned by verified full source arrow silhouette'
                       if passed else 'independent or unknown source geometry outside arrow ink'),
            'no_bbox_only_veto_or_hidden_absence_claim': True}


def prune_arrow_owned_spikes(detections, image, room, *, source_grid,
                             source_frame=None):
    """Preserve original instances/order; remove only a positively explained alias."""
    if source_grid != (25, 19) or source_frame is not None and (
            not isinstance(source_frame, SourceFrame) or source_frame.extent != room
            or not source_frame.matches_source(image, room)):
        return detections, dict(retired=[], unknown=True, evidence=[])
    owners = tuple(d for d in detections if d.type_id in _ARROWS)
    if not owners:
        return detections, dict(retired=[], evidence=[])
    kept, retired, evidence = [], [], []
    for detection in detections:
        explained = False
        if detection.type_id in _FULL_SPIKES:
            for owner in owners:
                if (max(detection.x, owner.x) >= min(detection.x+32, owner.x+32)
                        or max(detection.y, owner.y) >= min(detection.y+32, owner.y+32)):
                    continue
                proof = explain_arrow_owned_spike(image, room, detection, owner,
                    source_grid=source_grid, source_frame=source_frame)
                evidence.append(dict(key=(detection.type_id, detection.x, detection.y),
                    owner=(owner.type_id, owner.x, owner.y), evidence=proof))
                if proof['passed']:
                    explained = True
                    break
        if explained:
            retired.append((detection.type_id, detection.x, detection.y))
        else:
            kept.append(detection)
    return (kept if retired else detections), dict(retired=retired, evidence=evidence)
