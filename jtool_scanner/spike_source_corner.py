"""Additional pure geometry channel with native-distance corner exclusion."""
from math import hypot

def mixin(base):
 class CornerExclusiveField(base):
  def _side_coverages(self,x,y,direction,minimum_strength):
   # Existing native32 samples begin4.8px along each native coordinate.
   # Native16's old2.4px endpoints fall inside corner mixing. Keep a 4px
   # native-coordinate margin: search2 + central difference1 + local fringe1.
   margin=max(.15,4/self.native_size);tip,*ends=self.vertices[direction];coverages=[]
   for end in ends:
    tx,ty=end[0]-tip[0],end[1]-tip[1];length=hypot(tx,ty);nx,ny=-ty/length,tx/length;hits=0
    for i in range(12):
     q=margin+(1-2*margin)*i/11;px,py=x+tip[0]+q*tx,y+tip[1]+q*ty
     for off in(-2,-1,0,1,2):
      gx,gy=self.gradient(round(px+off*nx),round(py+off*ny));magnitude=hypot(gx,gy)
      if magnitude>=minimum_strength and abs(gx*nx+gy*ny)>=magnitude*.95:
       hits+=1;break
    coverages.append(hits/12)
   return tuple(coverages)
  def could_have_strong_slopes(self,x,y,direction):
   if not(0<=x<=800-self.native_size and 0<=y<=608-self.native_size):return False
   # The original bound needs eleven of twelve hits on BOTH sides. Two
   # misses already disprove a side; eleven hits already prove it. Inspect
   # the same sample set, not a weaker arbitrary subset of that set.
   margin=max(.15,4/self.native_size);tip,*ends=self.vertices[direction]
   for end in ends:
    tx,ty=end[0]-tip[0],end[1]-tip[1];length=hypot(tx,ty);nx,ny=-ty/length,tx/length
    hits=misses=0
    for i in(0,5,11,2,8,1,4,7,10,3,6,9):
     q=margin+(1-2*margin)*i/11;px,py=x+tip[0]+q*tx,y+tip[1]+q*ty;found=False
     for off in(-2,-1,0,1,2):
      gx,gy=self.gradient(round(px+off*nx),round(py+off*ny));magnitude=hypot(gx,gy)
      if magnitude>=.25 and abs(gx*nx+gy*ny)>=magnitude*.95:
       found=True;break
     if found:
      hits+=1
      if hits>=11:break
     else:
      misses+=1
      if misses>=2:return False
   return True
 return CornerExclusiveField
