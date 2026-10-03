"""Scan-local coherent outline profiles and native-size material evidence."""

from math import floor, hypot
from statistics import median

def templates(field,d,positions):
 tip,*ends=field.vertices[d]
 cx=sum(p[0] for p in field.vertices[d])/3
 cy=sum(p[1] for p in field.vertices[d])/3
 sides=[]
 for end in ends:
  tx,ty=end[0]-tip[0],end[1]-tip[1];length=hypot(tx,ty)
  nx,ny=-ty/length,tx/length
  if nx*(cx-(tip[0]+end[0])/2)+ny*(cy-(tip[1]+end[1])/2)>0:
   nx,ny=-nx,-ny
  samples=[]
  for q in positions:
   px,py=tip[0]+q*tx,tip[1]+q*ty
   pixels=[]
   for j in range(-4,5):
    vx,vy=px+j*nx,py+j*ny;ix,iy=floor(vx),floor(vy);dx,dy=vx-ix,vy-iy
    pixels.append(((iy*800+ix,(1-dx)*(1-dy)),(iy*800+ix+1,dx*(1-dy)),
                   ((iy+1)*800+ix,(1-dx)*dy),((iy+1)*800+ix+1,dx*dy)))
   gradients=[(round(px+j*nx),round(py+j*ny)) for j in range(-2,3)]
   samples.append((pixels,gradients,nx,ny))
  sides.append(samples)
 return sides

def could_have_stroke(field,x,y,d):
 if not (4<=x<=796-field.native_size and 4<=y<=604-field.native_size):return False
 # EACH slope needs at least8/12 coherent ink samples before it can supplement
 # gradient evidence. Stop only once neither sign can reach eight, counting
 # all unobserved samples as potential hits. This is a true necessary condition,
 # unlike requiring an arbitrary three-point subset to be perfect. No patch
 # statistics or gradients are needed just to rule out an impossible stroke.
 positions=tuple(.2+.5*i/11 for i in range(12));key=d,positions
 if key not in field.profile_templates:
  field.profile_templates[key]=templates(field,d,positions)
 origin=y*800+x;possible={1,-1}
 for side in field.profile_templates[key]:
  counts={1:0,-1:0}
  for tested,i in enumerate((0,5,11,2,8,1,4,7,10,3,6,9),1):
   pixels=side[i][0]
   v=[sum(field.pixels[origin+j]*weight for j,weight in entries) for entries in pixels]
   threshold=max(4.,(max(v)-min(v))*.15)
   dark=min(v[0],v[-1])-min(v[2:7]);light=max(v[2:7])-max(v[0],v[-1])
   sign=1 if dark>=threshold else -1 if light>=threshold else 0
   if sign:counts[sign]+=1
   if not any(counts[sign]+12-tested>=8 for sign in possible):return False
  possible &= {sign for sign in (1,-1) if counts[sign]>=8}
  if not possible:return False
 return bool(possible)

def background_material_matches(x,y,signature,nearby,materials):
 """Interpolate nearby exterior appearance; do not require a globally flat hue.

 A tiny scan-local affine fit allows a gradual background gradient. Large
 non-affine residuals abstain instead of widening the acceptance band. These
 are independently localized source samples, never new proposal answers.
 """
 if not nearby:return False
 values=[(sx,sy,materials[sx,sy]) for _,sx,sy,_ in nearby]
 matrix=[[0.]*4 for _ in range(3)]
 for sx,sy,m in values:
  a=[1.,(sx-x)/96,(sy-y)/96]
  weight=1/(16+hypot(sx-x,sy-y))**2
  for i in range(3):
   for j in range(3):matrix[i][j]+=weight*a[i]*a[j]
   matrix[i][3]+=weight*a[i]*m['background']
 coefficients=None
 if len(values)>=3:
  for column in range(3):
   pivot=max(range(column,3),key=lambda row:abs(matrix[row][column]))
   if abs(matrix[pivot][column])<1e-10:break
   matrix[column],matrix[pivot]=matrix[pivot],matrix[column]
   divisor=matrix[column][column]
   matrix[column]=[v/divisor for v in matrix[column]]
   for row in range(3):
    if row==column:continue
    amount=matrix[row][column]
    matrix[row]=[a-amount*b for a,b in zip(matrix[row],matrix[column])]
  else:coefficients=[matrix[i][3] for i in range(3)]
 if coefficients is None:
  prediction=median(m['background'] for _,_,m in values[:3])
  residual=median(abs(m['background']-prediction) for _,_,m in values[:3])
 else:
  prediction=coefficients[0]
  residual=median(abs(m['background']-(prediction+coefficients[1]*(sx-x)/96
                                 +coefficients[2]*(sy-y)/96)) for sx,sy,m in values)
 noise=max(6.,3*median(m['noise'] for _,_,m in values),3*signature['noise'])
 return residual<=noise and abs(prediction-signature['background'])<=noise

def points(field, x, y, direction):
    positions=tuple(.2+.5*i/11 for i in range(12));key=direction,positions
    if key not in field.profile_templates:
        field.profile_templates[key]=templates(field,direction,positions)
    origin=y*800+x;sides=[]
    minimum=max(field.patch_stats(x,y)[0]*.25,field.patch_stats(x,y)[1]*.15)
    for side in field.profile_templates[key]:
        samples=[]
        for pixels,gradients,nx,ny in side:
            values=[sum(field.pixels[origin+i]*weight for i,weight in entries) for entries in pixels]
            spread=max(values)-min(values);threshold=max(4.,spread*.15)
            dark=min(values[0],values[-1])-min(values[2:7])
            light=max(values[2:7])-max(values[0],values[-1])
            sign=1 if dark>=threshold else -1 if light>=threshold else 0
            amplitude=dark if sign==1 else light if sign==-1 else 0.
            directional=False
            for dx,dy in gradients:
                gx,gy=field.gradient(x+dx,y+dy);magnitude=hypot(gx,gy)
                if magnitude>=minimum and abs(gx*nx+gy*ny)>=magnitude*.95:
                    directional=True;break
            ink=min(values[2:7]) if sign==1 else max(values[2:7])
            samples.append((sign,amplitude/max(1.,spread),values[-1],directional,ink))
        sides.append(samples)
    return sides

def profile_signature(field,x,y,direction):
    if not (4<=x<=796-field.native_size and 4<=y<=604-field.native_size):
        return dict(score=0.,contrast=0.,background=0.,noise=0.,ink=0.,ink_noise=0.,ink_sides=(0.,0.),ink_noise_sides=(0.,0.))
    sides=points(field,x,y,direction);scored=[]
    for sign in (1,-1):
        coverage=min(sum(s[0]==sign or s[3] for s in side)/12 for side in sides)
        if min(sum(s[0]==sign for s in side)/12 for side in sides)<2/3:coverage=0.
        scored.append((coverage,sign))
    score,sign=max(scored)
    strengths=[s[1] for side in sides for s in side if s[0]==sign]
    exterior=[s[2] for side in sides for s in side];background=median(exterior)
    ink_samples=[[s[4] for s in side if s[0]==sign] for side in sides]
    all_ink=[v for samples in ink_samples for v in samples];ink=median(all_ink) if all_ink else 0.
    ink_sides=tuple(median(samples) if samples else 0. for samples in ink_samples)
    ink_noise_sides=tuple(median(abs(v-center) for v in samples) if samples else 0.
                          for samples,center in zip(ink_samples,ink_sides))
    return dict(score=score,contrast=sign*median(strengths) if strengths else 0.,
        background=background,noise=median(abs(v-background) for v in exterior),
        ink=ink,ink_noise=median(abs(v-ink) for v in all_ink) if all_ink else 0.,
        ink_sides=ink_sides,ink_noise_sides=ink_noise_sides)

_signature = profile_signature
_background_matches = background_material_matches

def stroke_signature(field,x,y,direction):
    signature=dict(_signature(field,x,y,direction))
    signature['native_size']=field.native_size
    return signature

def mixin(base):
    class StrokeField(base):
        def __init__(self,*args,**kwargs):
            super().__init__(*args,**kwargs);self.stroke_cache={};self.profile_templates={}
        def stroke(self,x,y,d):
            key=x,y,d
            if key not in self.stroke_cache:self.stroke_cache[key]=stroke_signature(self,x,y,d)
            return self.stroke_cache[key]
        def localized_score(self,x,y,d):
            return max(super().localized_score(x,y,d),self.stroke(x,y,d)['score'])
    return StrokeField

def predict(x,y,signature,nearby,values):
    """Existing bounded affine estimator, now exposing its uncertainty interval."""
    rows=[(sx,sy,values[sx,sy]) for _,sx,sy,_ in nearby]
    matrix=[[0.]*4 for _ in range(3)]
    for sx,sy,m in rows:
        a=[1.,(sx-x)/96,(sy-y)/96];weight=1/(16+hypot(sx-x,sy-y))**2
        for i in range(3):
            for j in range(3):matrix[i][j]+=weight*a[i]*a[j]
            matrix[i][3]+=weight*a[i]*m['background']
    coefficients=None
    if len(rows)>=3:
        for c in range(3):
            p=max(range(c,3),key=lambda r:abs(matrix[r][c]))
            if abs(matrix[p][c])<1e-10:break
            matrix[c],matrix[p]=matrix[p],matrix[c];div=matrix[c][c];matrix[c]=[v/div for v in matrix[c]]
            for r in range(3):
                if r==c:continue
                amount=matrix[r][c];matrix[r]=[a-amount*b for a,b in zip(matrix[r],matrix[c])]
        else:coefficients=[matrix[i][3] for i in range(3)]
    if coefficients is None:
        prediction=median(m['background'] for _,_,m in rows[:3])
        residual=median(abs(m['background']-prediction) for _,_,m in rows[:3])
    else:
        prediction=coefficients[0]
        residual=median(abs(m['background']-(prediction+coefficients[1]*(sx-x)/96+coefficients[2]*(sy-y)/96)) for sx,sy,m in rows)
    noise=max(6.,3*median(m['noise'] for _,_,m in rows),3*signature['noise'])
    return prediction,noise,residual<=noise

def same_size_material_matches(x,y,signature,nearby,materials):
    if signature['score']<11/12:return False
    eligible=[row for row in nearby if materials[row[1],row[2]]['score']>=11/12
              and materials[row[1],row[2]]['contrast']*signature['contrast']>0]
    if not eligible or not _background_matches(x,y,signature,eligible,materials):return False
    # Native16 may carry a proportionately thinner outline than native32.
    # Model a bounded attenuation range, not identical foreground intensity.
    # Same-size witnesses do NOT gain a relaxed envelope. Every side still
    # needs its own foreground/exterior agreement and coherent original ink.
    size=signature.get('native_size',16)
    for i,(ink,noise) in enumerate(zip(signature['ink_sides'],signature['ink_noise_sides'])):
        endpoints=[]
        for attenuate in (False,True):
            values={}
            for key,m in materials.items():
                factor=min(1.,size/m.get('native_size',size)) if attenuate else 1.
                foreground=m['ink_sides'][i]
                values[key]=dict(background=m['background']+(foreground-m['background'])*factor,
                                 noise=m['ink_noise_sides'][i])
            prediction,uncertainty,valid=predict(x,y,dict(background=ink,noise=noise),eligible,values)
            if not valid:return False
            endpoints.append((prediction,uncertainty))
        low=min(v-n for v,n in endpoints);high=max(v+n for v,n in endpoints)
        if not low<=ink<=high:return False
    return True

_same_size_matches = same_size_material_matches

def material_matches(x,y,signature,nearby,materials):
    if signature['score']<11/12:return False
    eligible=[row for row in nearby if materials[row[1],row[2]]['score']>=11/12
              and materials[row[1],row[2]]['contrast']*signature['contrast']>0]
    if not eligible or not _background_matches(x,y,signature,eligible,materials):return False
    size=signature['native_size']
    same=[row for row in eligible if materials[row[1],row[2]]['native_size']==size]
    if same:return _same_size_matches(x,y,signature,same,materials)
    # Absolute foreground parity is unproved across different native sprite
    # sizes. The caller retains closed geometry, original coherent ink,
    # exterior agreement and independent full-triangle/rectangle ownership.
    return False
