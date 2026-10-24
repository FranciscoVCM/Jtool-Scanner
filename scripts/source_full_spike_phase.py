"""Experimental full-spike phase evidence and a separately gated consumer.

Reports a unique bounded same-instance alternative only with original material,
complete directed geometry and independent positive exclusive FG/BG evidence.
No references, emitted-object teachers or caller mutation. An evidence proposal
is not a scanner correction; the consumer/caller require separate qualification
and default OFF. Neither API is proof of unseen-tileset generalization.
"""
from copy import deepcopy
from math import dist, inf, isfinite
from sys import float_info
from types import SimpleNamespace

from jtool_scanner.spike_shape import VERTICES
from scripts.source_physical_patch import physical_exclusive_patch,_full_key
from scripts.source_directional_body import SourceDirectionalBodyEvidence
from scripts.source_glyph_prototypes import _contains
from scripts.source_interior_glyphs import (
    INTERIOR_POINTS, _mean, _normalized, _oriented, _OriginalPaintIndex,
    SourceInteriorGlyphEvidence,
)
from scripts.source_local_background import SourceLocalBackground
from scripts.source_phase_registration import _paint_within


def _legacy_background_support(body, model, rgb):
    paint = body._paint_support(model, (rgb,))
    distance = dist(rgb, model['background'])
    return distance <= model['limit'] and distance < .5 * paint['max_original_paint_distance']


def _original_background_support(body, model, rgb):
    """Exact original BG decision, without computing an unused nearest value.

    Raw uint8 distances are zero or at least one: halving them is exact. The
    old strict ``d < .5*nearest`` is exactly ``nearest > 2*d``. An empty CLOSED
    radius therefore preserves boundary ties; unsupported data keeps the old
    nearest-distance path. This fits no model and changes no paint threshold.
    """
    # Extensions may supply their own paint oracle/minimal model. The radius
    # identity applies only to the standard original-nearest implementation;
    # do not bypass an override or impose new fields on that older protocol.
    if (getattr(body._paint_support, '__func__', None) is not SourceInteriorGlyphEvidence._paint_support
            or 'original_paints' not in model or not hasattr(body, '_paint_indices')):
        return _legacy_background_support(body, model, rgb)
    paints = model['original_paints']
    if paints not in body._paint_indices:
        body._paint_indices[paints] = _OriginalPaintIndex(paints)
    index = body._paint_indices[paints]
    if not index.exact_raw or not index._raw_rgb(rgb):
        return _legacy_background_support(body, model, rgb)
    distance, limit = dist(rgb, model['background']), model['limit']
    try:
        supported_limit = (isinstance(limit, (int, float)) and not isinstance(limit, bool)
                           and isfinite(limit))
    except OverflowError:
        supported_limit = False
    if not supported_limit or not isfinite(distance) or distance > float_info.max / 2:
        return _legacy_background_support(body, model, rgb)
    return distance <= limit and not _paint_within(index, rgb, 2 * distance, inf)


def _glyph_polygon(key):
    kind,x,y=key
    direction=kind-4 if kind>6 else kind
    size=16 if kind>6 else 32
    return [(x+u*size/32,y+v*size/32) for u,v in VERTICES[direction]]


def _disjoint_full(a,b):
    return abs(a[1]-b[1])>=32 or abs(a[2]-b[2])>=32


class SourceFullSpikePhaseEvidence:
    """Report unique source-supported alternatives; never change any caller list."""
    def __init__(self,filled,original,*,source_grid):
        self.original=tuple(original)
        self.original_keys=frozenset((d.type_id,d.x,d.y) for d in self.original)
        self.filled=filled
        self.body=SourceDirectionalBodyEvidence(filled,self.original,source_grid=source_grid)
        self.frame=filled.frame

    def probe(self,old,current,*,short_circuit=False):
        if not isinstance(short_circuit, bool):
            raise ValueError('Phase short-circuit flag must be a boolean')
        old=_full_key(old)
        current=tuple(current)
        keys=frozenset((d.type_id,d.x,d.y) for d in current)
        result=dict(old=old,proposed=None,candidates=[],original_source_only=True,
                    NO_emission_OR_retirement_OR_new_teachers=True)
        if not self.body.qualified or self.frame.extent!=self.frame.room:
            return {**result,'abstained':'unqualified direct original frame'}
        if old not in self.original_keys or old not in keys:
            return {**result,'abstained':'not an original and current full locator'}
        if not any((d.type_id,d.x,d.y)==old and d in current for d in self.original):
            return {**result,'abstained':'original locator metadata no longer current'}
        if not self.frame.rectangle_available(old[1],old[2],32,32,margin=4):
            return {**result,'abstained':'unknown original old footprint'}
        nominal = self.body._nominal_geometry(old) if short_circuit else None
        if nominal is not None and nominal['passed']:
            # A complete positive phase only RETAINS an original. Never place
            # this partial diagnostic in the all-nine-phase result cache.
            old_geometry = dict(passed=True, phases=[nominal],
                common_phase_NOT_native_origin_change=True, RGB_normal_alignment=.95,
                existing_required_support=9, diagnostics_deferred=True,
                ONLY_proven_original_retention_NOT_new_pose=True)
        else:
            old_geometry=self.body.geometry(old)
        if old_geometry['passed']:
            return {**result,'abstained':'positive old original contour retained','old_geometry':old_geometry}
        old_values=self.body._body(old)
        if old_values is None:
            return {**result,'abstained':'unknown old original body'}
        def sampled_native_center(point):
            # RGB belongs to an ORIGINAL physical pixel, not the arbitrary
            # subpixel native request that selected it. Preserve that identity
            # for both positive retention and new-exclusive classification.
            sx,sy=self.frame.original_position(*point)
            return ((sx+.5-self.frame.extent.x)*800/self.frame.extent.width,
                    (sy+.5-self.frame.extent.y)*608/self.frame.extent.height)
        old_points=[sampled_native_center((old[1]+u,old[2]+v))
                    for u,v in (_oriented(old[0],*p) for p in INTERIOR_POINTS)]
        markers=[d for d in self.original if d.type_id>10 and d.type_id not in (14,15,23)]
        def marker_contact(key):
            return any(max(key[1],d.x)<min(key[1]+32,d.x+32) and
                max(key[2],d.y)<min(key[2]+32,d.y+(8 if d.type_id==13 else 32)) for d in markers)
        if marker_contact(old):
            return {**result,'abstained':'original marker contact retained'}
        old_poly=_glyph_polygon(old)
        qualified=[]
        for amount in (8,16):
            for dx,dy in ((amount,0),(-amount,0),(0,amount),(0,-amount)):
                new=(old[0],old[1]+dx,old[2]+dy)
                row=dict(new=new,passed=False)
                result['candidates'].append(row)
                if new in keys or marker_contact(new) or not self.frame.rectangle_available(new[1],new[2],32,32,margin=4):
                    row['abstained']='already current/marker/unknown new footprint'
                    continue
                geometry=self.body.geometry(new)
                row['new_geometry']=geometry
                if not geometry['passed']:
                    continue
                values=self.body._body(new)
                if values is None:
                    continue
                excluded=[]
                for key in sorted(keys-{old}):
                    kind,x,y=key
                    if kind in (14,15,23):
                        continue
                    if 3<=kind<=10:
                        excluded.append(_glyph_polygon(key))
                    else:
                        size=16 if kind==2 else 32
                        height=8 if kind==13 else size
                        excluded.append([(x,y),(x+size,y),(x+size,y+height),(x,y+height)])
                patch=physical_exclusive_patch(self.frame,old,new,excluded_polygons=excluded)
                row['physical_patch']=patch
                if not patch['known']:
                    continue
                patch_points=[tuple(p['native']) for p in patch['samples']]
                def explained(key,point):
                    kind,x,y=key
                    if 3<=kind<=10:
                        return _contains(_glyph_polygon(key),*point)
                    size=16 if kind==2 else 32
                    return x<=point[0]<x+size and y<=point[1]<y+(8 if kind==13 else size)
                if any(explained(k,p) for k in keys-{old} if k[0] not in (14,15,23) for p in patch_points):
                    row['abstained']='other current object explains old-only patch;unknown ownership'
                    continue
                patch_values=[]
                for sample in patch['samples']:
                    position,rgb=self.frame.original_sample(*sample['native'])
                    assert position==sample['physical'] and rgb is not None
                    patch_values.append(rgb)
                new_points=[sampled_native_center((new[1]+u,new[2]+v))
                            for u,v in (_oriented(new[0],*p) for p in INTERIOR_POINTS)]
                new_poly=_glyph_polygon(new)
                row['cohorts']=[]
                for cohort in self.body._cohorts:
                    teachers=tuple(t for t in cohort if _disjoint_full(t,old) and _disjoint_full(t,new))
                    if len(teachers)<3:
                        continue
                    model=self.body._model(teachers)
                    if model is None or model['limit']<=0:
                        continue
                    m=dict(teachers=teachers,passed=False)
                    row['cohorts'].append(m)
                    error=dist(_mean(values),model['foreground'])
                    pattern=_normalized([v-model['background'][c] for rgb in values for c,v in enumerate(rgb)])
                    correlation=sum(a*b for a,b in zip(pattern,model['pattern']))
                    paint=self.body._paint_support(model,values)
                    m.update(mean_error=error,limit=model['limit'],correlation=correlation,body_paint=paint)
                    if error>model['limit'] or correlation<.9 or not paint['passed']:
                        continue
                    def fg(rgb):
                        p=self.body._paint_support(model,(rgb,))
                        return p['passed'] and p['max_original_paint_distance']<.5*dist(rgb,model['background'])
                    new_only={self.frame.original_position(*p) for p,rgb in zip(new_points,values)
                              if not _contains(old_poly,*p) and fg(rgb)}
                    lost_old=[p for p,rgb in zip(old_points,old_values) if fg(rgb) and not _contains(new_poly,*p)]
                    m.update(new_only_independent_FG=len(new_only),old_positive_body_outside_replacement=lost_old)
                    if len(new_only)<4 or lost_old:
                        continue
                    def bg(rgb):
                        return _original_background_support(self.body, model, rgb)
                    if not all(bg(rgb) for rgb in patch_values):
                        m['abstained']='old-only patch not coherently original BG-like'
                        continue
                    anchors=[a for a in self.filled.library.anchors if _disjoint_full(a['key'],old) and _disjoint_full(a['key'],new)]
                    local=SourceLocalBackground(SimpleNamespace(anchors=anchors,raw=self.filled.library.raw),bg)
                    cx=sum(p[0] for p in patch_points)/9
                    cy=sum(p[1] for p in patch_points)/9
                    prediction=local.predict(cx,cy,model['limit'])
                    m['independent_original_local_BG']=prediction
                    if not prediction['valid'] or not all(dist(rgb,prediction['prediction'])<=model['limit'] for rgb in patch_values):
                        continue
                    m['passed']=True
                row['passed']=any(m['passed'] for m in row['cohorts'])
                if row['passed']:
                    qualified.append(new)
        result['qualified_alternatives']=qualified
        if len(qualified)==1:
            result['proposed']=qualified[0]
        elif qualified:
            result['abstained']='multiple independently supported alternatives'
        else:
            result['abstained']='no complete source-exclusive conjunction'
        return deepcopy(result)


def refit_source_full_spike_phases(detections, original_detections, *, source_frame,
                                  source_filled_evidence, source_grid, retired=(),
                                  short_circuit=False):
    """Apply only unique original-source phase proofs; preserve every other object.

    Query one frozen current snapshot, never an incrementally corrected teacher
    list. Keep original kind/type/score; only native origin and corresponding
    physical image_box change. Ambiguous origins/targets and retired keys stay.
    """
    from collections import Counter
    from dataclasses import asdict, replace
    from jtool_scanner.geometry import Box
    from jtool_scanner.scanner import Detection
    from scripts.source_filled_pipeline import FilledGlyphEvidence
    from scripts.source_sampling import SourceFrame

    if not isinstance(short_circuit, bool):
        raise ValueError('Phase short-circuit flag must be a boolean')
    current, original = tuple(detections), tuple(original_detections)
    if any(not isinstance(d, Detection) or any(isinstance(v, bool) or not isinstance(v, int)
            for v in (d.type_id, d.x, d.y)) for d in (*current, *original)):
        raise ValueError('Source phase correction needs original integer Detection metadata')
    report = dict(evaluated=0, corrected=[], withheld=[], source_proofs=[],
                  no_new_teachers=True, object_count_unchanged=True,
                  unchanged_objects_and_order_preserved=True)
    if not isinstance(source_frame, SourceFrame):
        raise ValueError('Source phase correction needs an immutable original SourceFrame')
    if source_grid != (25, 19) or source_frame.extent != source_frame.room:
        return list(current), {**report, 'reason': 'unqualified direct original source mapping'}
    if (not isinstance(source_filled_evidence, FilledGlyphEvidence)
            or source_filled_evidence.frame is not source_frame):
        raise ValueError('Source phase correction must reuse the actual original filled field')
    key = lambda d: (d.type_id, d.x, d.y)
    current_counts = Counter(map(key, current))
    original_counts = Counter(map(key, original))
    excluded = set(map(tuple, retired))
    eligible = [d for d in current if 3 <= d.type_id <= 6 and d in original
                and current_counts[key(d)] == original_counts[key(d)] == 1 and key(d) not in excluded]
    if not eligible:
        return list(current), report
    evidence = SourceFullSpikePhaseEvidence(source_filled_evidence, original, source_grid=source_grid)
    if not evidence.body._cohorts:
        return list(current), {**report, 'reason': 'no independent original source material cohorts'}
    proposed = []
    for detection in eligible:
        old = key(detection)
        proof = evidence.probe(old, current, **({'short_circuit': True} if short_circuit else {}))
        report['evaluated'] += 1
        report['source_proofs'].append(proof)
        if proof['proposed'] is None:
            continue
        new = _full_key(proof['proposed'])
        delta = abs(new[1] - old[1]), abs(new[2] - old[2])
        if (new[0] != old[0] or delta not in ((8, 0), (16, 0), (0, 8), (0, 16))
                or any(isinstance(v, bool) or not isinstance(v, int) for v in new)):
            raise ValueError('Source phase proof proposed an unqualified replacement')
        if new in excluded or new in current_counts:
            report['withheld'].append(dict(old=old, new=new, reason='retired or already current target'))
            continue
        proposed.append((detection, new, proof))
    target_counts = Counter(new for _, new, _ in proposed)
    unambiguous_targets = [(detection, new) for detection, new, _ in proposed if target_counts[new] == 1]
    registration = None
    if unambiguous_targets:
        from scripts.source_phase_registration import SourcePhaseRegistrationAmbiguity
        registration = SourcePhaseRegistrationAmbiguity(evidence, original,
            [(key(detection), new) for detection, new in unambiguous_targets], source_grid=source_grid)
        report['registration_source_hypothesis'] = registration.proof()
    replacements = {}
    frame = source_frame.extent
    for detection, new, proof in proposed:
        old = key(detection)
        if target_counts[new] != 1:
            report['withheld'].append(dict(old=old, new=new, reason='conflicting replacement targets'))
            continue
        counterproof = registration.probe(old, new)
        if counterproof['ambiguous']:
            report['withheld'].append(dict(old=old, new=new,
                reason='independent source registration supports the original pose',
                registration_counterproof=counterproof))
            continue
        image_box = Box(round(frame.x + new[1] * frame.width / 800),
                        round(frame.y + new[2] * frame.height / 608),
                        max(1, round(32 * frame.width / 800)), max(1, round(32 * frame.height / 608)))
        corrected = replace(detection, x=new[1], y=new[2], image_box=image_box)
        replacements[old] = corrected
        report['corrected'].append(dict(old=old, new=new, before=asdict(detection),
                                        after=asdict(corrected), source_evidence=proof,
                                        registration_counterproof=counterproof))
    return [replacements.get(key(d), d) for d in current], report
