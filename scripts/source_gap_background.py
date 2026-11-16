"""Unbound original-pixel evidence for full spikes nominated in open gaps.

Pose locators are not labels. Complete original base samples are never
discounted. Interior disagreements can be independently accounted for by
a nearby opposing spike, without padding the neighbor's geometry.
"""
from statistics import median

from jtool_scanner.spike_shape import VERTICES
from scripts.source_contours import SourceContours
from scripts.source_pixel_geometry import PolygonPixelCoverage, original_pixel_bounds
from scripts.source_sampling import SourceFrame

OPPOSITE = {3: 6, 4: 5, 5: 4, 6: 3}
TRACKS = (5, 8, 11, 14, 18, 21, 24, 27)


def _distance(a, b):
    return max(abs(u-v) for u,v in zip(a,b))


def _position(key, u, inward):
    t,x,y = key
    if t == 3:
        return x+u, y+32-inward
    if t == 4:
        return x+inward, y+u
    if t == 5:
        return x+32-inward, y+u
    return x+u, y+inward


def _polygon(frame, key):
    t,x,y = key
    return PolygonPixelCoverage(frame, [(x+a,y+b) for a,b in VERTICES[t]])


def _aperture(frame, key):
    strips = [[],[]]
    base, core, seen = [], [], set()
    for u in TRACKS:
        ds = (-10,-6,-2,2,4) + tuple(d for d in (7,10) if 2*min(u,32-u)-d >= 2)
        points = [frame.original_position(*_position(key,u,d)) for d in ds]
        if None in points or len(set(points)) != len(points):
            return None
        a,b = points[2:4]
        # Read all physical base pixels, including those between native taps.
        band = [(x,y) for y in range(min(a[1],b[1]),max(a[1],b[1])+1)
                for x in range(min(a[0],b[0]),max(a[0],b[0])+1)]
        required = points[:2]+band+points[4:]
        if len(set(required)) != len(required) or seen.intersection(required):
            return None
        seen.update(required)
        strips[0].append(points[0]); strips[1].append(points[1])
        base.extend(band); core.extend(points[4:])
    return strips,base,core


class GapBackgroundEvidence:
    """Read-only probe; does not remove, add, or change any detection."""

    def __init__(self, frame, *, owner_poses):
        if not isinstance(frame, SourceFrame):
            raise ValueError('Gap evidence needs immutable original RGB coverage')
        self.frame = frame
        self.image = frame.original_snapshot()
        self.contours = SourceContours(self.image, frame.extent, source_frame=frame)
        self.owners = sorted(set(tuple(key) for key in owner_poses))
        if any(len(key)!=3 or key[0] not in VERTICES or any(type(v) is not int for v in key)
               for key in self.owners):
            raise ValueError('Owner locators must be full integer triangle poses')

    def _source(self, point):
        if original_pixel_bounds(self.frame,*point) is None:
            return None
        return self.image.pixel(*point)

    def _valid_owners(self, query, sky, aperture):
        direction,x,y = query
        query_poly = _polygon(self.frame,query)
        for key in self.owners:
            t,a,b = key
            if t!=OPPOSITE[direction] or abs(a-x)>=48 or abs(b-y)>=48:
                continue
            faces = self.contours.triangle(*key)
            if any(f.unknown or f.support<9 for f in faces):
                continue
            centroid = [(a,b)[i]+sum(v[i] for v in VERTICES[t])/3 for i in (0,1)]
            spot = [self.frame.original_position(centroid[0]+dx,centroid[1]+dy)
                    for dx in (-2,0,2) for dy in (-2,0,2)]
            if (None in spot or len(set(spot))!=9 or aperture.intersection(spot)
                    or any(query_poly.overlap(*p)!=0 or min(_distance(self.image.pixel(*p),k) for k in sky)<25 for p in spot)):
                continue
            yield key,_polygon(self.frame,key)

    def _ray(self, point, axis, sign, owner, sky):
        def step(i):
            if axis==0:
                return point[0]+i*sign,point[1]
            return point[0],point[1]+i*sign

        # The pixel is not excused by a widened polygon. It must be an
        # observed departure that continues directly into a real footprint.
        contact = None
        for i in range(5):
            p=step(i)
            v=self._source(p)
            if v is None or sky(v):
                return None
            if owner.overlap(*p)>=.5:
                contact=i
                break
        if contact is None or contact==0:
            return None
        for i in range(1,5):
            p=step(-i)
            v=self._source(p)
            if v is None or owner.overlap(*p)>0:
                break
            if sky(v):
                return contact
        return None

    def _bridge(self, point, axis, owner, sky):
        for sign in (-1,1):
            d=self._ray(point,axis,sign,owner,sky)
            if d is None:
                continue
            rows=[]
            for cross in (-1,1):
                matches=[]
                for move in (0,-1,1):
                    u=point[0]+(move if axis==0 else cross)
                    v=point[1]+(cross if axis==0 else move)
                    j=self._ray((u,v),axis,sign,owner,sky)
                    if j is not None and abs(move*sign+j-d)<=1:
                        matches.append((u,v,j))
                if not matches:
                    break
                rows.append(matches[0])
            if len(rows)==2:
                return dict(sign=sign,contact=d,adjacent_rows=rows)
        return None

    def query(self, key):
        key = tuple(key)
        if len(key)!=3 or key[0] not in VERTICES or any(type(v) is not int for v in key):
            raise ValueError('Only a full integer triangle can be probed')
        t,x,y=key
        if not (0<=x<=768 and 0<=y<=576):
            return dict(clear=False,reason='clipped triangle')
        samples=_aperture(self.frame,key)
        if samples is None:
            return dict(clear=False,reason='incomplete physical aperture')
        strips,base,core=samples
        donors=[[self.image.pixel(*p) for p in strip] for strip in strips]
        centers=[tuple(map(median,zip(*values))) for values in donors]
        sky=lambda v: all(_distance(v,rgb)<=8 for rgb in centers)
        if not all(sky(v) for values in donors for v in values):
            return dict(clear=False,reason='outside strips do not agree')
        if not all(sky(self.image.pixel(*p)) for p in base):
            return dict(clear=False,reason='base has independent color support')
        dissent=[p for p in core if not sky(self.image.pixel(*p))]
        if not dissent:
            return dict(clear=True,reason='complete aperture agrees',bridges=[])
        owners=list(self._valid_owners(key,centers,set(base+core+strips[0]+strips[1])))
        axis=0 if t in (3,6) else 1
        proofs=[]
        for p in dissent:
            found=[(k,proof) for k,owner in owners
                   if (proof:=self._bridge(p,axis,owner,sky)) is not None]
            if len(found)!=1:
                return dict(clear=False,reason='interior dissent lacks unique ownership',
                            dissent=dissent,qualified_owners=[k for k,_ in owners],previous=proofs)
            proofs.append(dict(point=p,owner=found[0][0],**found[0][1]))
        return dict(clear=True,reason='all dissent accounted for',bridges=proofs)
