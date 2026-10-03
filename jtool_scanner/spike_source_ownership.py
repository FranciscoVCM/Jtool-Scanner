"""Source-only ambiguity vetoes for new contained triangle proposals."""

from math import hypot
from statistics import median

def triangle_contains(vertices, points):
    """Closed triangular containment, not merely overlapping sprite boxes."""
    for px, py in points:
        signs = []
        for (ax, ay), (bx, by) in zip(vertices, vertices[1:] + vertices[:1]):
            signs.append((bx-ax)*(py-ay) - (by-ay)*(px-ax))
        if min(signs) < 0 < max(signs):
            return False
    return True

def source_size_owns(observed, mini, parent):
    """Abstain on NEW inner art; does not emit or certify an open full."""
    t, mx, my = mini
    direction, x, y = parent
    if t - 4 != direction or not (4 <= x <= 764 and 4 <= y <= 572):
        return False
    f = observed['field'](32)
    outer = tuple((x+vx, y+vy) for vx, vy in f.vertices[direction])
    inner = tuple((mx+vx/2, my+vy/2) for vx, vy in f.vertices[direction])
    if not triangle_contains(outer, inner):
        return False
    coarse_overlap = any(
        max(x, bx) < min(x+32, bx+w) and max(y, by) < min(y+32, by+h)
        for bx, by, w, h in observed['solids'])
    # This MUST be the pure legacy field/polarity, never the stroke view's
    # max score or substituted exterior/material sign. Its cached buffers
    # are shared, but its original localized scores retain their meaning.
    if f.localized_score(x, y, direction) < 11/12 or f.patch_stats(x, y)[1] < 12:
        return False
    key = x, y, direction
    if key not in observed['materials']:
        tip, *ends = f.vertices[direction]
        cx = sum(vx for vx, _ in f.vertices[direction])/3
        cy = sum(vy for _, vy in f.vertices[direction])/3
        values = []
        for end in ends:
            tx, ty = end[0]-tip[0], end[1]-tip[1]
            nx, ny = -ty, tx
            if nx*(cx-(tip[0]+end[0])/2)+ny*(cy-(tip[1]+end[1])/2) > 0:
                nx, ny = -nx, -ny
            length = hypot(nx, ny);nx, ny = nx/length, ny/length
            for i in range(10):
                q = .2+.6*i/9
                px, py = x+tip[0]+q*tx, y+tip[1]+q*ty
                outer = sum(f.pixel(round(px+j*nx),round(py+j*ny)) for j in (2,3,4))/3
                inner = sum(f.pixel(round(px-j*nx),round(py-j*ny)) for j in (0,1,2))/3
                values.append(outer-inner)
        spread = f.patch_stats(x,y)[1]
        observed['materials'][key] = (median(values)/spread,
            tuple(median(values[i:i+10])/spread for i in (0,10)))
    contrast, sides = observed['materials'][key]
    signed_frame = (abs(contrast) >= .2 and min(abs(s) for s in sides) >= .2
                    and sides[0]*sides[1] > 0)
    if not signed_frame:
        return False
    # Coarse rectangles locate hypotheses, not missing source pixels. A
    # complete independent material/geometry frame may own interior art even
    # when those rectangles overlap. Existing miniature detections are never
    # deleted by this NEW-proposal ambiguity qualifier.
    return not coarse_overlap or _source_frame_base_closed(observed, x, y, direction)

def rectangle_owns(observed,mini):
    """Ambiguity veto only: never emit a block or remove an existing mini."""
    t,mx,my=mini
    if not 7<=t<=10:return False
    for size in(16,32):
        for dx in range(16-size,1,8):
            for dy in range(16-size,1,8):
                x,y=mx+dx,my+dy
                if not(0<=x<=800-size and 0<=y<=608-size):continue
                key=size,x,y
                if key not in observed['rectangles']:
                    f=observed['field'](size);scale,spread=f.patch_stats(x,y)
                    minimum=max(scale*.25,spread*.15);faces=[];clipped=0
                    if spread<12:observed['rectangles'][key]=False;continue
                    for side in range(4):
                        coordinate=(x,x+size,y,y+size)[side];boundary=(0,800,0,608)[side]
                        if coordinate==boundary:
                            clipped+=1;continue
                        hits=0
                        for i in range(12):
                            q=.1+.8*i/11
                            px,py=(coordinate,y+size*q) if side<2 else(x+size*q,coordinate)
                            nx,ny=(1,0) if side<2 else(0,1)
                            for offset in(-1,0,1):
                                gx,gy=f.gradient(round(px+offset*nx),round(py+offset*ny));mag=hypot(gx,gy)
                                if mag>=minimum and abs(gx*nx+gy*ny)>=mag*.95:
                                    hits+=1;break
                        faces.append(hits/12)
                    observed['rectangles'][key]=(clipped<=1 and len(faces)>=3 and min(faces)>=11/12)
                if observed['rectangles'][key]:return True
    return False

strict_owner = source_size_owns

def tip_source_size_owns(state,mini,parent):
 if strict_owner(state,mini,parent):return True
 t,mx,my=mini;d,x,y=parent
 if t-4!=d or not(4<=x<=764 and 4<=y<=572):return False
 f=state['field'](32);vertices=f.vertices[d];tip=vertices[0]
 # A fully contained same-tip half triangle cannot establish a new size
 # merely by shortening the noisy long slopes of its larger source shape.
 # This is ambiguity/abstention on NEW geometry, never emission or deletion.
 if (mx+tip[0]/2,my+tip[1]/2)!=(x+tip[0],y+tip[1]):return False
 if not triangle_contains(tuple((x+vx,y+vy) for vx,vy in vertices),
   tuple((mx+vx/2,my+vy/2) for vx,vy in vertices)):return False
 if min(f.side_scores(x,y,d))<.75 or f.patch_stats(x,y)[1]<12:return False
 key=(x,y,d)
 if key not in state['tip_materials']:
  cx=sum(v[0] for v in vertices)/3;cy=sum(v[1] for v in vertices)/3;values=[]
  for end in vertices[1:]:
   tx,ty=end[0]-tip[0],end[1]-tip[1];nx,ny=-ty,tx
   if nx*(cx-(tip[0]+end[0])/2)+ny*(cy-(tip[1]+end[1])/2)>0:nx,ny=-nx,-ny
   length=hypot(nx,ny);nx,ny=nx/length,ny/length;side=[]
   for i in range(10):
    q=.2+.6*i/9;px,py=x+tip[0]+q*tx,y+tip[1]+q*ty
    outer=sum(f.pixel(round(px+j*nx),round(py+j*ny)) for j in(2,3,4))/3
    inner=sum(f.pixel(round(px-j*nx),round(py-j*ny)) for j in(0,1,2))/3
    side.append(outer-inner)
   values.append(median(side)/f.patch_stats(x,y)[1])
  state['tip_materials'][key]=tuple(values)
 sides=state['tip_materials'][key]
 return min(abs(s) for s in sides)>=.5 and sides[0]*sides[1]>0


def _source_frame_base_closed(state, x, y, direction):
    """Independent full-size middle base with connected support, scan-local."""
    cache = state.setdefault('coarse_overlap_source_closure', {})
    key = x, y, direction
    if key not in cache:
        f = state['field'](32)
        _, first, second = f.vertices[direction]
        tx, ty = second[0] - first[0], second[1] - first[1]
        length = hypot(tx, ty)
        nx, ny = -ty / length, tx / length
        scale, spread = f.patch_stats(x, y)
        hits = run = longest = 0
        for i in range(12):
            q = .3 + .4 * i / 11
            px, py = x + first[0] + q * tx, y + first[1] + q * ty
            found = False
            for offset in (-2, -1, 0, 1, 2):
                gx, gy = f.gradient(round(px + offset * nx), round(py + offset * ny))
                magnitude = hypot(gx, gy)
                if (magnitude >= max(scale * .25, spread * .15)
                        and abs(gx * nx + gy * ny) >= magnitude * .95):
                    found = True
                    break
            hits += found
            run = run + 1 if found else 0
            longest = max(longest, run)
        cache[key] = hits / 12 >= .5 and longest / 12 >= .5
    return cache[key]
