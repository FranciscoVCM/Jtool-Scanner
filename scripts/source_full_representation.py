"""Experimental, read-only full/mini representation from original source evidence.

This helper has no scanner or application binding. It may consolidate four NEW
material-cell proposals, never original objects, only when independent original
full-block artwork supports the 32px representation. Repeated 16px artwork and
unknown capture evidence abstain. The native solid union is unchanged.

Callers must supply original detections and independently source-qualified
material/certainty cell origins, all in the same direct 800x608 native frame.
References, previously emitted detections and corrected maps are not inputs.
"""
from math import sqrt
from itertools import combinations

from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import SourceGlyphLibrary
from scripts.source_block_prototypes import SourceBlockLibrary
from scripts.source_rectangle_prototypes import _dot,_interior_signature


def quad(x,y):
    return {(x,y),(x+16,y),(x,y+16),(x+16,y+16)}


def interior16(library,x,y):
    values=[(i-3.5,j-3.5,library.pixel(x+2+(i+.5)*1.5,y+2+(j+.5)*1.5))
            for j in range(8) for i in range(8)]
    mean=tuple(sum(rgb[c] for _,_,rgb in values)/64 for c in range(3))
    dx=sum(u*u for u,_,_ in values);dy=sum(v*v for _,v,_ in values)
    sx=tuple(sum(u*rgb[c] for u,_,rgb in values)/dx for c in range(3))
    sy=tuple(sum(v*rgb[c] for _,v,rgb in values)/dy for c in range(3))
    residual=tuple(rgb[c]-mean[c]-sx[c]*u-sy[c]*v for u,v,rgb in values for c in range(3))
    length=sqrt(sum(v*v for v in residual))
    return tuple(v/length for v in residual) if length>sqrt(192) else None


def recover_full_representations(frame,original,proposed,rejected,material,certainty):
    original=tuple(original);proposed=set(proposed);rejected=set(rejected)
    material,certainty=set(material),set(certainty)
    existing={(d.type_id,d.x,d.y) for d in original}
    new_minis={k[1:] for k in proposed-existing if k[0]==2}
    candidates=sorted(p for p in new_minis if quad(*p)<=new_minis&material&certainty)
    if frame.extent!=frame.room or not candidates:
        return proposed,dict(rows=[],reason='no direct-frame complete new source quad',no_original_object_removed=True)
    frame_source=frame.original_snapshot();spikes=[k for k in existing if 3<=k[0]<=10]
    library=SourceGlyphLibrary(frame_source,frame.room,spikes,source_frame=frame)
    polygons=[]
    for anchor in library.anchors:
        kind,x,y=anchor['key'];size=anchor['size'];direction=kind-4 if kind>6 else kind
        polygons.append([(x+u*size/32,y+v*size/32) for u,v in VERTICES[direction]])
    mx,my=2*frame.pitch[0],2*frame.pitch[1]
    def intersects(a,b,w=32,h=32):
        return a[0]<b[0]+w+mx and b[0]-mx<a[0]+32 and a[1]<b[1]+h+my and b[1]-my<a[1]+32
    rows=[];retained=set(proposed)
    for point in candidates:
        x,y=point;keys={(2,*p) for p in quad(x,y)}
        if not keys<=retained-existing:
            continue
        if (1,x,y) in rejected:
            rows.append(dict(point=point,passed=False,reason='prior source rejection preserved'));continue
        if any(x<d.x+(16 if d.type_id==2 else 32) and d.x<x+32
               and y<d.y+(16 if d.type_id==2 else 32) and d.y<y+32
               for d in original if d.type_id in (1,2)):
            rows.append(dict(point=point,passed=False,reason='original terrain body/context protected'));continue
        if not frame.rectangle_available(x,y,32,32,margin=max(mx,my)):
            rows.append(dict(point=point,passed=False,reason='unknown physical query footprint'));continue
        if not any(_interior_signature(library,x,y)):
            rows.append(dict(point=point,passed=False,reason='no above-rounding interior size evidence'));continue
        # Identical repeated16 artwork cannot prove32 sprite identity, even when
        # a32 teacher happens to use the same periodic texture. Keep ambiguous
        # minis rather than inventing a unique latent sprite size from pixels.
        parts=[interior16(library,*p) for p in sorted(quad(x,y))]
        if any(p is None for p in parts) or all(_dot(a,b)>=.9 for a,b in combinations(parts,2)):
            rows.append(dict(point=point,passed=False,reason='repeated16 appearance leaves size ambiguous'));continue
        teachers=[]
        for p in sorted({(d.x,d.y) for d in original if d.type_id==1}):
            if not quad(*p)<=material or not frame.rectangle_available(*p,32,32,margin=max(mx,my)):
                continue
            if intersects(p,point) or any(intersects(p,t) for t in teachers):
                continue
            if not any(_interior_signature(library,*p)):
                continue
            teachers.append(p)
        model=SourceBlockLibrary(library,teachers,material,polygons)
        proof=model.support(x,y)
        row=dict(point=point,passed=proof['passed'],source_proof=proof,
                 independent_qualified_teachers=model.teachers,models=len(model.models),
                 no_new_solid_area=True,no_original_object_removed=True)
        rows.append(row)
        if proof['passed']:
            retained-=keys;retained.add((1,x,y))
    return retained,dict(rows=rows,no_new_solid_area=True,no_original_object_removed=True,
        only_original_source_teachers=True,size_ambiguous_abstains=True)




