"""Covered source-exclusive physical patches; no RGB reads or object decisions."""
from math import ceil, floor, hypot, isfinite

from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import _contains
from scripts.source_sampling import SourceFrame


def _full_key(value):
    if (not isinstance(value,(tuple,list)) or len(value)!=3 or
        isinstance(value[0],bool) or value[0] not in VERTICES or
        any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) for v in value[1:])):
        raise ValueError('Exclusive patch needs finite full type3..6,x,y')
    return tuple(value)


def _edge_distance(poly,point):
    """Distance to finite segments (not extension lines)."""
    distances=[]
    for first,second in zip(poly,poly[1:]+poly[:1]):
        dx,dy=second[0]-first[0],second[1]-first[1]
        t=max(0,min(1,((point[0]-first[0])*dx+(point[1]-first[1])*dy)/(dx*dx+dy*dy)))
        distances.append(hypot(point[0]-first[0]-t*dx,point[1]-first[1]-t*dy))
    return min(distances)


def physical_exclusive_patch(frame,old,new,*,excluded_polygons=()):
    """Nearest complete guarded3x3 patch in old\new, without reading RGB.

    Pixels outside the physical crop/native extent never supply support. A
    return value is a coordinate/coverage proof ONLY, not background evidence.
    """
    if not isinstance(frame,SourceFrame):
        raise ValueError('Exclusive patch needs an immutable original SourceFrame')
    excluded_polygons=tuple(tuple(tuple(p) for p in poly) for poly in excluded_polygons)
    if any(len(poly)<3 or any(len(p)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) for v in p) for p in poly) for poly in excluded_polygons):
        raise ValueError('Protected polygons need finite native point pairs')
    old,new=_full_key(old),_full_key(new)
    if old[0]!=new[0] or old[1:]==new[1:]:
        raise ValueError('Exclusive patch needs displaced SAME-direction fulls')
    def polygon(key):
        return [(frame.extent.x+(key[1]+a)*frame.extent.width/800,
                 frame.extent.y+(key[2]+b)*frame.extent.height/608)
                for a,b in VERTICES[key[0]]]
    a,b=polygon(old),polygon(new)
    lo_x=max(frame.room.x,ceil(min(p[0] for p in a)-.5))
    hi_x=min(frame.room.right-1,floor(max(p[0] for p in a)-.5))
    lo_y=max(frame.room.y,ceil(min(p[1] for p in a)-.5))
    hi_y=min(frame.room.bottom-1,floor(max(p[1] for p in a)-.5))
    eligible=set()
    for y in range(lo_y,hi_y+1):
        for x in range(lo_x,hi_x+1):
            point=(x+.5,y+.5)
            if (_contains(a,*point) and _edge_distance(a,point)>=1 and
                not _contains(b,*point) and _edge_distance(b,point)>=1):
                native=((point[0]-frame.extent.x)*800/frame.extent.width,
                        (point[1]-frame.extent.y)*608/frame.extent.height)
                if frame.original_position(*native)==(x,y) and not any(_contains(poly,*native) for poly in excluded_polygons):
                    eligible.add((x,y))
    centers=[(x,y) for x,y in eligible if all((x+dx,y+dy) in eligible
        for dy in (-1,0,1) for dx in (-1,0,1))]
    if not centers:
        return dict(known=False,reason='no complete guarded physical old-exclusive patch',
                    eligible_physical_centres=len(eligible),RGB_not_queried=True)
    cx,cy=min(centers,key=lambda p:((p[0]+.5-a[0][0])**2+(p[1]+.5-a[0][1])**2,p[1],p[0]))
    samples=[]
    for y in range(cy-1,cy+2):
        for x in range(cx-1,cx+2):
            native=((x+.5-frame.extent.x)*800/frame.extent.width,
                    (y+.5-frame.extent.y)*608/frame.extent.height)
            samples.append(dict(native=native,physical=(x,y)))
    return dict(known=True,center=(cx,cy),samples=samples,
        physical_margin=1,eligible_physical_centres=len(eligible),
        RGB_not_queried=True,NOT_semantic_background_OR_pose_decision=True)
