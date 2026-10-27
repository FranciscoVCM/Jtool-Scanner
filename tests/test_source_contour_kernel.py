"""Exact RGB contour arithmetic versus the original generic calculation."""
import random,unittest
from unittest.mock import patch
from math import hypot,sqrt
from statistics import median
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_contours import SourceContours
from scripts.source_sampling import SourceFrame
from scripts.source_contours import _median_four as median4, _rgb_probe_phases as probe_phases

def reference(values,points,squared):
    derivatives=[]
    for j in range(8):
        spacing=hypot(points[j+1][0]-points[j][0],points[j+1][1]-points[j][1])
        derivatives.append(tuple((values[j+1][c]-values[j][c])/spacing for c in range(3)) if spacing else (0.,0.,0.))
    gradient=tuple(median(derivatives[j][c] for j in (0,1,6,7)) for c in range(3))
    def departure(value):
        delta=tuple(value[c]-gradient[c] for c in range(3))
        return sqrt(sum(v*v for v in delta)) if squared else hypot(*delta)
    ref=max(departure(derivatives[j]) for j in (0,1,6,7))
    return {j-3.5 for j in (2,3,4,5) if departure(derivatives[j])>ref}

def image(width=240,height=184):
    data=bytes(c for y in range(height) for x in range(width) for c in ((x*3+y)%256,(y*5+x)%256,(x//7*31+y//5*37)%256))
    return RGBImage(width,height,data)

class ExactContourKernelTests(unittest.TestCase):
    def test_median_same_order_extreme_ties_signed_zero_nan(self):
        values=(-float('inf'),-1e200,-0.,0.,1.,1e-200,1e200,float('inf'),float('nan'))
        rng=random.Random(184)
        for _ in range(3000):
            row=rng.choices(values,k=4);a=median(row);b=median4(*row)
            self.assertEqual(repr(a),repr(b),row)

    def test_random_integer_RGB_and_quantized_or_repeated_spacing(self):
        rng=random.Random(785)
        for _ in range(3000):
            values=[tuple(rng.randrange(256) for _ in range(3)) for _ in range(9)]
            points=[(rng.randrange(8),rng.randrange(8)) for _ in range(9)]
            for squared in (False,True):self.assertEqual(reference(values,points,squared),probe_phases(values,points,squared))

    def test_float_RGB_fractional_spacing_and_extremes(self):
        rng=random.Random(786)
        for _ in range(1500):
            values=[tuple(rng.uniform(-1e100,1e100) for _ in range(3)) for _ in range(9)]
            points=[(rng.uniform(-2,2),rng.uniform(-2,2)) for _ in range(9)]
            for squared in (False,True):self.assertEqual(reference(values,points,squared),probe_phases(values,points,squared))
        for flat in ((float('nan'),0.,1.),(float('inf'),0.,1.),(-0.,0.,-0.)):
            for squared in (False,True):
                self.assertEqual(reference([flat]*9,[(i,0) for i in range(9)],squared),probe_phases([flat]*9,[(i,0) for i in range(9)],squared))

    def compare_fields(self,a,b,queries):
        for first,second in queries:
            with patch("scripts.source_contours._rgb_probe_phases", reference):
                expected = a.edge(first,second)
            self.assertEqual(expected,b.edge(first,second),(first,second))
            self.assertIs(b.edge(first,second),b.edge(first,second))
        self.assertEqual(a._edges,b._edges)
        self.assertEqual((a.probe_cache_hits,a.probe_cache_misses,a.probe_cache_peak),(b.probe_cache_hits,b.probe_cache_misses,b.probe_cache_peak))
        self.assertEqual(a._physical_probes,b._physical_probes)

    def test_entire_edges_arbitrary_directions_lengths_native_scales(self):
        rgb=image();room=Box(0,0,rgb.width,rgb.height);rng=random.Random(787)
        for native in ((240,184),(800,608),(120,92)):
            q=[((rng.uniform(0,native[0]),rng.uniform(0,native[1])),(rng.uniform(0,native[0]),rng.uniform(0,native[1]))) for _ in range(160)]
            q+= [(b,a) for a,b in q[:10]]
            for squared in (False,True):self.compare_fields(SourceContours(rgb,room,native,squared_norm=squared),SourceContours(rgb,room,native,squared_norm=squared),q)

    def test_original_frame_fractional_crop_unknown_and_cache_eviction(self):
        rgb=image();room=Box(7,9,226,166);frame=SourceFrame(rgb,room);rng=random.Random(788)
        q=[((rng.uniform(-10,810),rng.uniform(-10,618)),(rng.uniform(-10,810),rng.uniform(-10,618))) for _ in range(160)]
        q+=q[:20]
        for limit in (0,7,10000):
            self.compare_fields(SourceContours(rgb,room,source_frame=frame,probe_cache_limit=limit),SourceContours(rgb,room,source_frame=frame,probe_cache_limit=limit),q)

    def test_isoluminance_single_byte_gradient_and_constant(self):
        from PIL import Image,ImageDraw
        for fg,bg in (((255,0,0),(0,130,0)),((129,128,128),(128,128,128)),((128,128,128),(128,128,128))):
            im=Image.new('RGB',(192,128),bg);ImageDraw.Draw(im).rectangle((64,32,127,95),fill=fg)
            rgb=RGBImage(192,128,im.tobytes());room=Box(0,0,192,128)
            q=[((64,48),(64,80)),((64,80),(64,48)),((0,48),(0,80)),((127,32),(64,95))]
            self.compare_fields(SourceContours(rgb,room,(192,128)),SourceContours(rgb,room,(192,128)),q)

    def test_zero_length_keeps_original_exception_and_cache(self):
        rgb=image();room=Box(0,0,rgb.width,rgb.height);f=SourceContours(rgb,room)
        with self.assertRaisesRegex(ValueError,'distinct endpoints'):f.edge((32,32),(32,32))
        self.assertEqual(f._edges,{})

if __name__=='__main__':unittest.main(verbosity=2)
