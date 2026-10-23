"""Original-source counterevidence for proposed full-spike relocations.

A paint-envelope fit is only a hypothesis, not a certified camera transform.
Positive original body AND geometry at an old pose can make a local move
ambiguous. No objects, exported frames or native coordinates are produced.
"""
from collections import Counter, deque
from copy import deepcopy
from math import ceil, dist, floor, isfinite

from PIL import Image
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_directional_body import SourceDirectionalBodyEvidence
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_interior_glyphs import _OriginalPaintIndex
from scripts.source_physical_patch import _full_key
from scripts.source_sampling import SourceFrame



def _paint_components(frame,foreground_pixel):
    image=frame.original_snapshot();w,h=image.width,image.height;room=frame.room
    left,top=max(0,ceil(room.x)),max(0,ceil(room.y));right,bottom=min(w,floor(room.right)),min(h,floor(room.bottom))
    mask=bytearray(w*h);cache={}
    for y in range(top,bottom):
        for x in range(left,right):
            i=y*w+x;rgb=image.data[i*3:i*3+3]
            if rgb not in cache:cache[rgb]=bool(foreground_pixel(tuple(rgb)))
            mask[i]=cache[rgb]
    foreground=mask[:];components=[];pw,ph=32*room.width/800,32*room.height/608
    for start in range(w*h):
        if not mask[start]:continue
        mask[start]=0;queue=deque([start]);points=[]
        while queue:
            i=queue.popleft();x,y=i%w,i//w;points.append((x,y))
            for yy in range(max(top,y-1),min(bottom,y+2)):
                for xx in range(max(left,x-1),min(right,x+2)):
                    j=yy*w+xx
                    if mask[j]:mask[j]=0;queue.append(j)
        x0=min(x for x,y in points);x1=max(x for x,y in points)+1;y0=min(y for x,y in points);y1=max(y for x,y in points)+1
        width,height=x1-x0,y1-y0;area=len(points)
        if x0<=left or y0<=top or x1>=right or y1>=bottom:continue
        if not (.75*pw<=width<=1.25*pw and .75*ph<=height<=1.25*ph and .35<=area/(width*height)<=.65):continue
        tq=sum(y<y0+height/4 for x,y in points);bq=sum(y>=y1-height/4 for x,y in points)
        lq=sum(x<x0+width/4 for x,y in points);rq=sum(x>=x1-width/4 for x,y in points)
        vertical,horizontal=(bq-tq)/area,(lq-rq)/area
        kind=(3 if vertical>=.2 and abs(horizontal)<=.1 else 6 if vertical<=-.2 and abs(horizontal)<=.1 else
              4 if horizontal>=.2 and abs(vertical)<=.1 else 5 if horizontal<=-.2 and abs(vertical)<=.1 else None)
        if kind is None:continue
        if sum(foreground[y*w+x] for y in range(y0,y1) for x in range(x0,x1))!=area:continue
        pixels=set(points)
        agreement=(sum((x0+x1-1-x,y) in pixels for x,y in points)/area if kind in (3,6) else
                   sum((x,y0+y1-1-y) in pixels for x,y in points)/area)
        if agreement<.9:continue
        components.append(dict(type_id=kind,box=(x0,y0,width,height),point=((x0+x1)/2,(y0+y1)/2),
            pixels=area,orthogonal_reflection_agreement=agreement))
    return components


def _registration_frame_hypothesis(frame,original,*,source_grid,foreground_pixel,query_keys=()):
    if not isinstance(frame,SourceFrame):raise ValueError('Original source frame required')
    original=tuple(original);queries={tuple(k) for k in query_keys}
    allkeys=[(d.type_id,d.x,d.y) for d in original if 3<=d.type_id<=6]
    if not queries<=set(allkeys):raise ValueError('Only original phase queries may exclude registration witnesses')
    result=dict(qualified_hypothesis=False,mapping_NOT_certified=True,NO_frame_export_OR_object_emission=True,
        orthogonal_sprite_art_bias_NOT_ruled_out=True,components=[],pairs=[],fits=[],excluded_originals=[])
    if source_grid!=(25,19) or frame.extent!=frame.room:return {**result,'reason':'unqualified compact/world domain'}
    counts=Counter(allkeys);keys=[]
    for k in sorted(counts):
        if any(abs(k[1]-q[1])<32 and abs(k[2]-q[2])<32 for q in queries):
            result['excluded_originals'].append(k)
        elif counts[k]==1:keys.append(k)
    if len(keys)<12:return {**result,'reason':'too few independent nonquery original locators'}
    components=_paint_components(frame,foreground_pixel);result['components']=components;room=frame.room;links=[]
    for key in keys:
        expected=(room.x+(key[1]+16)*room.width/800,room.y+(key[2]+16)*room.height/608)
        choices=[i for i,c in enumerate(components) if c['type_id']==key[0]
            and abs(c['point'][0]-expected[0])<=16*room.width/800 and abs(c['point'][1]-expected[1])<=16*room.height/608]
        links.append((key,choices))
    offered=Counter(i for _,choices in links for i in choices)
    for key,choices in links:
        if len(choices)==1 and offered[choices[0]]==1:
            i=choices[0];result['pairs'].append(dict(key=key,native=(key[1]+16,key[2]+16),source=components[i]['point'],component=i))
    pairs=result['pairs']
    if len(pairs)<12:return {**result,'reason':'fewer than12 complete unique source witnesses'}
    a,b=pairs[0]['native'],pairs[1]['native']
    if not any((b[0]-a[0])*(p['native'][1]-a[1])!=(b[1]-a[1])*(p['native'][0]-a[0]) for p in pairs[2:]):
        return {**result,'reason':'collinear source witnesses'}
    for axis,kinds in ((0,(3,6)),(1,(4,5))):
        ps=[p for p in pairs if p['key'][0] in kinds]
        if len(ps)<3 or len({p['native'][axis] for p in ps})<3:
            return {**result,'reason':'insufficient orthogonal orientation/position witnesses'}
        xs=[p['native'][axis] for p in ps];ys=[p['source'][axis] for p in ps]
        span=max(xs)-min(xs)
        if span<128:return {**result,'reason':'insufficient native orthogonal span'}
        xbar=sum(xs)/len(xs);ybar=sum(ys)/len(ys);variance=sum((x-xbar)**2 for x in xs)
        if variance<=0:return {**result,'reason':'no physical registration variance'}
        slope=sum((x-xbar)*(y-ybar) for x,y in zip(xs,ys))/variance;intercept=ybar-slope*xbar
        residuals=[y-(intercept+slope*x) for x,y in zip(xs,ys)]
        result['fits'].append(dict(axis=axis,slope=slope,intercept=intercept,residuals=residuals,
            max_abs_residual=max(map(abs,residuals)),original_keys=[p['key'] for p in ps],native_span=span))
        if slope<=0 or max(map(abs,residuals))>1.5:
            return {**result,'reason':'ALL orthogonal source witnesses do not agree'}
    x,y=result['fits']
    result['candidate_extent']=dict(x=x['intercept'],y=y['intercept'],width=x['slope']*800,height=y['slope']*608)
    result['qualified_hypothesis']=True
    result['reason']='original-paint orthogonal-centre hypothesis;independent geometry/art-bias qualification still required'
    return result


def _paint_within(index, rgb, closed_limit, strict_limit):
    if not index.exact_raw or not index._raw_rgb(rgb):
        distance = index.distance(rgb)
        return distance <= closed_limit and distance < strict_limit
    if closed_limit < 0 or strict_limit <= 0:
        return False
    pending = [(index.root, 0)]
    while pending:
        node, bound = pending.pop()
        if node is None or bound > closed_limit or bound >= strict_limit:
            continue
        axis, paint, left, right = node
        distance = dist(rgb, paint)
        if distance <= closed_limit and distance < strict_limit:
            return True
        delta = rgb[axis]-paint[axis]
        near, far = (left, right) if delta <= 0 else (right, left)
        if far is not None:
            pending.append((far, abs(delta)))
        if near is not None:
            pending.append((near, 0))
    return False


def _foreground_predicate(body, model):
    paints = model['original_paints']
    if paints not in body._paint_indices:
        body._paint_indices[paints] = _OriginalPaintIndex(paints)
    index = body._paint_indices[paints]
    return lambda rgb: _paint_within(index, rgb, model['limit'], .5*dist(rgb, model['background']))


def _hypothesis_view(original_frame,extent):
    if not isinstance(original_frame,SourceFrame):raise ValueError('Original source frame required')
    if min(extent.width,extent.height)<=0 or not all(isfinite(v) for v in (extent.x,extent.y,extent.width,extent.height)):
        raise ValueError('Finite positive world footprint required')
    image=original_frame.original_snapshot()
    canonical=Image.frombytes('RGB',(image.width,image.height),image.data).transform((800,608),Image.Transform.EXTENT,
        (extent.x,extent.y,extent.right,extent.bottom),Image.Resampling.BILINEAR)
    return SourceFrame(image,original_frame.room,extent=extent,canonical=RGBImage(800,608,canonical.tobytes()))


class SourcePhaseRegistrationAmbiguity:
    """One original snapshot and one shared domain for all frozen proposals."""
    def __init__(self, phase_field, original, pairs, *, source_grid):
        self.original = tuple(original)
        if (not isinstance(getattr(phase_field, 'body', None), SourceDirectionalBodyEvidence)
                or not isinstance(getattr(phase_field, 'frame', None), SourceFrame)
                or phase_field.body.frame is not phase_field.frame):
            raise ValueError('Registration ambiguity needs the actual original body/frame')
        if self.original != phase_field.original:
            raise ValueError('Registration ambiguity must share actual original teachers')
        self.pairs = tuple((_full_key(old), _full_key(new)) for old, new in pairs)
        originals = [(d.type_id, d.x, d.y) for d in self.original]
        for old, new in self.pairs:
            delta = abs(old[1]-new[1]), abs(old[2]-new[2])
            if (originals.count(old) != 1 or old[0] != new[0]
                    or delta not in ((8, 0), (16, 0), (0, 8), (0, 16))):
                raise ValueError('Only unique original bounded full phase hypotheses qualify')
        if len({old for old, new in self.pairs}) != len(self.pairs):
            raise ValueError('Duplicate old phase hypothesis')
        self.phase_field = phase_field
        self.source_grid = source_grid
        self._proof = self._body = None
        self._rows = {}

    def _prepare(self):
        if self._proof is not None:
            return
        self._proof = dict(available=False, original_source_only=True,
            NO_frame_export_OR_objects_OR_native_changes=True,
            mapping_NOT_certified=True, first_independent_model_only=True)
        if not self.pairs:
            self._proof['reason'] = 'no proposed relocations; no source work'
            return
        frame = self.phase_field.frame
        if self.source_grid != (25, 19) or frame.extent != frame.room:
            self._proof['reason'] = 'unqualified compact/world entry'
            return
        boxes = tuple(key for pair in self.pairs for key in pair)
        independent = tuple(d for d in self.original if not (3 <= d.type_id <= 6 and
            any(abs(d.x-q[1]) < 32 and abs(d.y-q[2]) < 32 for q in boxes)))
        independent_keys = {(d.type_id, d.x, d.y) for d in independent if 3 <= d.type_id <= 6}
        self._proof['excluded_fulls'] = sorted({(d.type_id, d.x, d.y) for d in self.original
                                               if 3 <= d.type_id <= 6} - independent_keys)
        model = None
        for cohort in self.phase_field.body._cohorts:
            teachers = tuple(k for k in cohort if k in independent_keys)
            if len(teachers) < 3:
                continue
            candidate = self.phase_field.body._model(teachers)
            if candidate is not None and candidate['limit'] > 0:
                model = candidate
                self._proof['paint_teachers'] = teachers
                break
        if model is None:
            self._proof['reason'] = 'no independent original paint cohort'
            return
        foreground = _foreground_predicate(self.phase_field.body, model)
        hypothesis = _registration_frame_hypothesis(frame, independent,
            source_grid=self.source_grid, foreground_pixel=foreground)
        self._proof['hypothesis'] = hypothesis
        if not hypothesis['qualified_hypothesis']:
            self._proof['reason'] = 'no independent coherent alternate paint mapping'
            return
        from jtool_scanner.geometry import Box
        mapped = _hypothesis_view(frame, Box(**hypothesis['candidate_extent']))
        filled = FilledGlyphEvidence(mapped, independent)
        self._body = SourceDirectionalBodyEvidence(filled, independent, source_grid=self.source_grid)
        self._proof.update(available=True, reason='independent source-paint hypothesis; positive counterproof only',
                           child_original_fulls=sorted(independent_keys))

    def probe(self, old, new):
        pair = _full_key(old), _full_key(new)
        if pair not in self.pairs:
            raise ValueError('Query must belong to the original frozen phase proposals')
        self._prepare()
        if pair not in self._rows:
            row = dict(old=pair[0], new=pair[1], ambiguous=False, source_proof=self._proof,
                       NO_emission_OR_retirement_OR_coordinate_transform=True)
            if self._body is not None:
                old_body, old_geometry = self._body.support(pair[0]), self._body.geometry(pair[0])
                new_body, new_geometry = self._body.support(pair[1]), self._body.geometry(pair[1])
                row.update(old_body=old_body, old_geometry=old_geometry,
                           new_body=new_body, new_geometry=new_geometry,
                           ambiguous=old_body['passed'] and old_geometry['passed'])
            self._rows[pair] = row
        return deepcopy(self._rows[pair])

    def proof(self):
        self._prepare()
        return deepcopy(self._proof)
