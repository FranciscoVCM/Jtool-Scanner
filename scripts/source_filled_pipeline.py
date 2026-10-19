"""Source-local filled full-spike recovery for explicit source geometry.

The final scanner source stage opts in; ordinary standard scans do not. Original
locators are hypotheses, never coordinate/direction answers. Three disjoint
source-proved filled teachers, complete physical coverage, directed silhouette
and a matching original-source appearance model must agree. New proposals never
teach, retire old objects, or turn unknown/cropped pixels into empty background.
"""
from __future__ import annotations

from copy import deepcopy
from math import dist, hypot

from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import SourceGlyphLibrary, _contains


def filled_hypotheses(original_detections, *, terrain_neighbors=True):
    """Finite original-locator neighborhoods; no second full-image scan."""
    if not isinstance(terrain_neighbors, bool):
        raise ValueError('Terrain-neighbor switch must be a boolean')
    original = tuple(original_detections)
    hypotheses = {(t, d.x+dx, d.y+dy)
                  for d in original if 3 <= d.type_id <= 6
                  for dx in (-16, -8, 0, 8, 16)
                  for dy in (-16, -8, 0, 8, 16) for t in (3, 4, 5, 6)}
    if terrain_neighbors:
        for d in original:
            if d.type_id != 1:
                continue
            for offset in range(-32, 33, 8):
                hypotheses.update(((3, d.x+offset, d.y-32),
                                   (6, d.x+offset, d.y+32),
                                   (4, d.x+32, d.y+offset),
                                   (5, d.x-32, d.y+offset)))
    return {(t, x, y) for t, x, y in hypotheses if 0 <= x <= 768 and 0 <= y <= 576}


class FilledGlyphEvidence:
    """One immutable source/frame/original-teacher snapshot for all queries."""

    def __init__(self, frame, original_detections, *, source_library=None):
        original = tuple(original_detections)
        self.frame = frame
        self.original_spikes = tuple(sorted({(d.type_id, d.x, d.y) for d in original
                                            if 3 <= d.type_id <= 6}))
        if source_library is not None:
            raw = source_library.raw
            if (raw.room != frame.extent or not frame.matches_source(raw.image, frame.room)
                    or (source_library.source_frame is not None and source_library.source_frame is not frame)):
                raise ValueError('Filled library must match the original source/frame')
            original_origins = {(x, y) for _, x, y in self.original_spikes}
            if any(tuple(a['key'][1:]) not in original_origins for a in source_library.anchors if a['size'] == 32):
                raise ValueError('Filled library contains non-original full-spike teachers')
        # A legacy crop library can include a border anchor with insufficient
        # original context. Do not prune its trained models or relax coverage:
        # rebuild through the SAME original-frame path used without sharing.
        if source_library is None or any(a['size'] == 32 and not frame.rectangle_available(
                *a['key'][1:], 32, 32, margin=4) for a in source_library.anchors):
            source_library = SourceGlyphLibrary(
                frame.original_snapshot(), frame.room, self.original_spikes,
                source_frame=frame, pixel_cache_limit=50000)
        self.library = source_library
        self._qualified_models = {}
        self._results = {}
        self._joint_results = {}
        self._apex_results = {}

    def has_qualified_model(self):
        """Avoid unused shape queries when no original filled model can pass."""
        return any(self._teachers(model) for model in self.library.models
                   if model['native_size'] == 32)

    def _teachers(self, model):
        keys = tuple(map(tuple, model['original_source_witnesses']))
        if keys in self._qualified_models:
            return self._qualified_models[keys]
        # Every contributor to the appearance prototype must have real coverage.
        if any(not self.frame.rectangle_available(x, y, 32, 32, margin=4) for _, x, y in keys):
            self._qualified_models[keys] = ()
            return ()
        independent = []
        for key in sorted(keys):
            if not self.library.filled.evidence(*key)['passed']:
                continue
            _, x, y = key
            if all(abs(x-k[1]) >= 32 or abs(y-k[2]) >= 32 for k in independent):
                independent.append(key)
        answer = tuple(independent) if len(independent) >= 3 else ()
        self._qualified_models[keys] = answer
        return answer

    def support(self, key, *, short_circuit=False):
        """Full diagnostics by default; candidate failures may defer unused work.

        Positive proofs are always complete. Deferred negative diagnostics never
        enter the full-result caches, so a later detailed query still measures
        the entire original proof. Neither mode changes teachers or candidates.
        """
        if not isinstance(short_circuit, bool):
            raise ValueError('Filled short-circuit flag must be a boolean')
        key = tuple(key)
        if len(key) != 3 or key[0] not in (3, 4, 5, 6):
            raise ValueError('Filled recovery needs a full type3..6,x,y triple')
        if key not in self._results:
            cacheable = True
            _, x, y = key
            if not self.frame.rectangle_available(x, y, 32, 32, margin=4):
                result = dict(passed=False, unknown=True, reason='incomplete original source footprint')
            else:
                silhouette = self.library.filled.evidence(*key, short_circuit=short_circuit)
                cacheable = not silhouette.get('diagnostics_deferred', False)
                result = dict(passed=False, unknown=silhouette['unknown'], silhouette=silhouette)
                if silhouette['passed']:
                    appearance = self.library.support(*key)
                    result['appearance'] = appearance
                    if appearance['passed']:
                        teachers = self._teachers(appearance['model'])
                        result.update(passed=bool(teachers), independent_filled_teachers=teachers,
                                      original_teachers_only=True, complete_physical_source=True)
            if cacheable:
                self._results[key] = result
            else:
                return deepcopy(result)
        return deepcopy(self._results[key])

    def support_joint_phase(self, key, *, short_circuit=False):
        """Resolve a known weak base at one coherent physical source phase.

        Nominal positives and unknowns are unchanged. This is not a wider pose
        search: both original slopes and an original appearance model must
        already agree. A fallback needs the ENTIRE same-phase silhouette and
        RGB signature, with the same frozen original teachers and thresholds.
        The native hypothesis is not shifted and no original object is retired.
        """
        nominal = self.support(key, short_circuit=short_circuit)
        key = tuple(key)
        if nominal['passed'] or nominal['unknown']:
            return nominal
        if key in self._joint_results:
            return deepcopy(self._joint_results[key])
        shape = nominal.get('silhouette', {})
        slopes, base = shape.get('slopes', ()), shape.get('raw_base')
        rectangle = shape.get('competing_rectangle_faces', ())
        if (len(slopes) != 2 or any(row['support'] < 9 or row['unknown'] for row in slopes)
                or not base or base[1] or base[0] >= 9
                or not rectangle or min(rectangle) >= 9):
            return nominal
        appearance = self.library.support(*key)
        if not appearance['passed'] or not self._teachers(appearance['model']):
            return nominal
        kind, x, y = key
        px, py = self.frame.pitch
        for dx in (0, -px, px):
            for dy in (0, -py, py):
                if (dx == 0 and dy == 0) or not self.frame.rectangle_available(
                        x+dx, y+dy, 32, 32, margin=4):
                    continue
                phased = self.library.filled.evidence(kind, x+dx, y+dy,
                                                      short_circuit=short_circuit)
                if not phased['passed']:
                    continue
                signature = self.library.signature(kind, x+dx, y+dy)
                best = None
                for model in self.library.models:
                    if model['native_size'] != 32:
                        continue
                    score = sum(a*b for a, b in zip(signature, model['signature']))
                    if best is None or score > best[0]:
                        best = score, model
                if best is None or best[0] < .9:
                    continue
                score, model = best
                teachers = self._teachers(model)
                if not teachers:
                    continue
                result = dict(passed=True, unknown=False, silhouette=phased,
                    appearance=dict(passed=True, correlation=score,
                        model={k:v for k,v in model.items() if k != 'signature'},
                        query_phase=[dx, dy], native_size=32,
                        bounded_by_one_original_source_pixel=True,
                        original_source_witnesses_only=True),
                    independent_filled_teachers=teachers, original_teachers_only=True,
                    complete_physical_source=True, nominal_failure=nominal,
                    joint_source_phase=[dx, dy], same_phase_geometry_and_RGB=True,
                    native_hypothesis_unchanged=True)
                self._joint_results[key] = result
                return deepcopy(result)
        return nominal

    def apex_support(self, key):
        """Known local RGB around an apex, used only to distinguish instances.

        This is not a general object predicate: a shaded or hidden real apex can
        abstain. A single visible apex near two locators identifies a possible
        phase repair, not two objects. No failed apex deletes an original.
        """
        key = tuple(key)
        if key in self._apex_results:
            return deepcopy(self._apex_results[key])
        t, x, y = key
        if t not in VERTICES:
            raise ValueError('Apex evidence needs a full type3..6,x,y triple')
        poly = [(x+u, y+v) for u, v in VERTICES[t]]
        tip = poly[0]
        base = ((poly[1][0]+poly[2][0])/2, (poly[1][1]+poly[2][1])/2)
        ux, uy = base[0]-tip[0], base[1]-tip[1]
        length = hypot(ux, uy)
        ux, uy = ux/length, uy/length
        vx, vy = -uy, ux
        corners = [(x+4,y+4),(x+28,y+4),(x+28,y+28),(x+4,y+28)]
        exterior = [p for p in corners if not _contains(poly, *p)]
        corner_values = [self.library.raw.sample(*p, size=4) for p in exterior]
        bodies = [self.library.raw.sample(sum(w*p[0] for w,p in zip(weights,poly)),
                                          sum(w*p[1] for w,p in zip(weights,poly)))
                  for weights in ((.25,.5,.25),(.25,.25,.5),(.5,.25,.25),(1/3,1/3,1/3))]
        if any(values is None for values in corner_values+bodies):
            result = dict(passed=False, unknown=True, phases=[])
        else:
            def mean(patches):
                return tuple(sum(rgb[c] for p in patches for rgb in p)/sum(map(len,patches)) for c in range(3))
            background, foreground = mean(corner_values), mean(bodies)
            vector = tuple(f-b for f,b in zip(foreground,background))
            energy = sum(v*v for v in vector)
            phases = []
            if energy:
                def is_foreground(rgb):
                    return sum((v-b)*d for v,b,d in zip(rgb,background,vector)) > .5*energy
                px, py = self.frame.pitch
                for dx in (0,-px,px):
                    for dy in (0,-py,py):
                        ax, ay = tip[0]+dx, tip[1]+dy
                        points = [(ax+3*ux*px,ay+3*uy*py),(ax-3*ux*px,ay-3*uy*py),
                                  (ax+3*vx*px,ay+3*vy*py),(ax-3*vx*px,ay-3*vy*py)]
                        values = [self.frame.original_pixel(*p) for p in points]
                        known = all(rgb is not None for rgb in values)
                        labels = [is_foreground(rgb) if rgb is not None else None for rgb in values]
                        passed = bool(known and labels[0] and sum(v is False for v in labels[1:]) >= 2)
                        phases.append(dict(phase=(dx,dy), known=known, foreground=labels, passed=passed))
            result = dict(passed=any(p['passed'] for p in phases),
                          unknown=not any(p['known'] for p in phases), phases=phases,
                          physical_radius=3, no_unknown_as_background=True)
        self._apex_results[key] = result
        return deepcopy(result)


def distinguish_filled_instances(proposed, original_detections, evidence):
    """Separate new objects from unqualified quarter-size pose alternatives.

    Source-filled support alone can validate a shifted crop of an existing
    object. Close same-type/size locators need two separately observed physical
    apices to establish two instances. Otherwise retain the original and record
    a repair candidate; never call it a false source shape or silently delete it.
    """
    retained, alternatives = set(), []
    original = tuple(original_detections)
    for key in sorted(proposed):
        t, x, y = key
        nearby = [(d.type_id,d.x,d.y) for d in original if d.type_id == t
                  and 0 < abs(d.x-x)+abs(d.y-y) <= 32/4]
        ambiguous = []
        for old in nearby:
            new_apex, old_apex = evidence.apex_support(key), evidence.apex_support(old)
            u, v = VERTICES[t][0]
            a = evidence.frame.original_position(x+u, y+v)
            b = evidence.frame.original_position(old[1]+u, old[2]+v)
            separate = a is not None and b is not None and dist(a,b) > 2
            if not (new_apex['passed'] and old_apex['passed'] and separate):
                ambiguous.append(dict(old=old, new_apex=new_apex, old_apex=old_apex,
                                      separate_physical_tip_positions=separate))
        if ambiguous:
            alternatives.append(dict(key=key, original_candidates=ambiguous,
                                     reason='same-instance pose needs independent repair qualification',
                                     source_shape_not_declared_false=True, no_original_retirement=True))
        else:
            retained.add(key)
    return retained, alternatives


def recover_source_filled_glyphs(frame, original_detections, *, source_library=None,
                                 terrain_neighbors=True, short_circuit=True,
                                 joint_phase=False, capture_base=False, source_context=None):
    """Return new source-proved full poses and proofs; never remove originals."""
    if not isinstance(short_circuit, bool):
        raise ValueError('Filled short-circuit flag must be a boolean')
    if not isinstance(joint_phase, bool):
        raise ValueError('Joint phase flag must be a boolean')
    if not isinstance(capture_base, bool):
        raise ValueError('Capture-base flag must be a boolean')
    original = tuple(original_detections)
    existing = {(d.type_id, d.x, d.y) for d in original}
    evidence = FilledGlyphEvidence(frame, original, source_library=source_library)
    if source_context is not None:
        source_context.record_filled_source(original, frame, evidence)
    hypotheses = sorted(filled_hypotheses(original, terrain_neighbors=terrain_neighbors)-existing)
    if not evidence.has_qualified_model():
        return set(), dict(accepted=[], hypotheses=len(hypotheses), evaluated=0,
                           reason='no three independent source-filled teachers',
                           original_teachers_only=True, complete_physical_source_required=True,
                           no_existing_object_retirement=True, no_new_objects_as_witnesses=True,
                           research_only_not_scanner_bound=False)
    capture_evidence = None
    if capture_base:
        from scripts.source_capture_base import CaptureBaseEvidence, capture_base_hypotheses
        capture_evidence = CaptureBaseEvidence(evidence)
        hypotheses = sorted((set(hypotheses) | capture_base_hypotheses(frame))-existing)
    proposed, proofs = set(), []
    for key in hypotheses:
        proof = (evidence.support_joint_phase(key, short_circuit=short_circuit) if joint_phase
                 else evidence.support(key, short_circuit=short_circuit))
        if capture_base and not proof['passed'] and capture_evidence.boundary(key):
            supplemental = capture_evidence.support(key)
            if supplemental['passed']:
                proof = {**supplemental, 'capture_base_context_censored': True,
                         'complete_physical_body_source': True,
                         'complete_physical_source': False, 'original_teachers_only': True}
        if proof['passed']:
            proposed.add(key)
            proofs.append(dict(key=key, evidence=proof))
    proposed, alternatives = distinguish_filled_instances(proposed, original, evidence)
    proofs = [p for p in proofs if tuple(p['key']) in proposed]
    return proposed, dict(accepted=proofs, hypotheses=len(hypotheses), evaluated=len(hypotheses), original_teachers_only=True,
                         same_instance_repair_candidates=alternatives,
                         complete_physical_source_required=True, no_existing_object_retirement=True,
                         no_new_objects_as_witnesses=True, research_only_not_scanner_bound=False)
