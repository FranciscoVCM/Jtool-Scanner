"""Qualifier for source-mismatched hollow full proposals, not blanket deletion."""
from math import hypot
from .spike_shape import SpikeShapeField
from .spike_color_evidence import QuantizedColorSlopeField
from .spike_source_corner import mixin


def mismatched_outline_pairs(image, room, candidates, blocks):
    if not candidates:return set()
    fields={}
    def mini():
        if 'mini' not in fields:fields['mini']=mixin(SpikeShapeField)(image,room,native_size=16)
        return fields['mini']
    def color():
        if 'color' not in fields:fields['color']=QuantizedColorSlopeField(image,room)
        return fields['color']
    def closed(x,y,d):
        f=mini()
        if f.localized_score(x,y,d)<11/12 or f.patch_stats(x,y)[1]<12:return False
        _,first,second=f.vertices[d]
        tx,ty=second[0]-first[0],second[1]-first[1];length=hypot(tx,ty)
        nx,ny=-ty/length,tx/length;scale,spread=f.patch_stats(x,y);hits=0
        for i in range(12):
            q=.3+.4*i/11;px,py=x+first[0]+q*tx,y+first[1]+q*ty
            for off in(-2,-1,0,1,2):
                gx,gy=f.gradient(round(px+off*nx),round(py+off*ny));mag=hypot(gx,gy)
                if mag>=max(scale*.25,spread*.15) and abs(gx*nx+gy*ny)>=mag*.95:
                    hits+=1;break
        return hits/12>=.5
    aliases=set()
    for candidate in candidates:
        d,x,y=candidate.type_id,candidate.x,candidate.y
        if not(4<=x<=764 and 4<=y<=572):continue
        if any(max(x,bx)<min(x+32,bx+32) and max(y,by)<min(y+32,by+32) for bx,by in blocks):continue
        f=mini()
        full_vertices=tuple((a*2,b*2) for a,b in f.vertices[d])
        if max(color().possible_side_scores(x,y,full_vertices))>=.75:continue
        positions={3:((x,y+16),(x+16,y+16)),6:((x,y),(x+16,y)),
                   4:((x,y),(x,y+16)),5:((x+16,y),(x+16,y+16))}[d]
        if all(closed(px,py,d) for px,py in positions):aliases.add((d,x,y))
    return aliases
