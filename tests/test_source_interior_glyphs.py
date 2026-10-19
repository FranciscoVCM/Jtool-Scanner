"""Portable touching glyph interiors corroborate geometry, not raw locators."""
from copy import deepcopy
from math import hypot
from types import SimpleNamespace
from unittest import TestCase

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_interior_glyphs import SourceInteriorGlyphEvidence, INTERIOR_POINTS, _oriented
from scripts.source_sampling import SourceFrame


def scene(*, rotation=0, scale=1, transform=lambda c:c, rectangle=False,
          foreground=(210,150,70),background=(20,30,60)):
    raster=Image.new('RGB',(800,608),transform(background))
    teachers=[(3,96,64),(4,208,64),(6,320,64),(5,432,64)]
    cluster=[(5,224,224),(4,256,224),(4,224,240)]
    def point(p):
        x,y=p
        for _ in range(rotation):x,y=256-(y-256),256+(x-256)
        return x,y
    def pose(key):
        t,x,y=key;corners=[point((x+a,y+b)) for a,b in ((0,0),(32,0),(32,32),(0,32))]
        for _ in range(rotation):t={3:4,4:6,6:5,5:3}[t]
        return t,min(a for a,b in corners),min(b for a,b in corners)
    cluster=[pose(k) for k in cluster];target=cluster[-1]
    def inside(poly,p):
        cross=[(poly[(i+1)%3][0]-a)*(p[1]-b)-(poly[(i+1)%3][1]-b)*(p[0]-a)
               for i,(a,b) in enumerate(poly)]
        return min(cross)>=0 or max(cross)<=0
    for t,x,y in teachers+cluster:
        poly=[(x+a,y+b) for a,b in VERTICES[t]]
        for py in range(y,y+32):
            for px in range(x,x+32):
                if not inside(poly,(px+.5,py+.5)):continue
                a,b=px+.5-x,py+.5-y
                u,v=(a,b) if t==3 else (b,32-a) if t==4 else (32-b,a) if t==5 else (32-a,32-b)
                shade=round(.7*(u-16)-.45*(v-16))
                distances=[abs((poly[(i+1)%3][0]-p[0])*(p[1]-py-.5)-(p[0]-px-.5)*(poly[(i+1)%3][1]-p[1]))/
                    hypot(poly[(i+1)%3][0]-p[0],poly[(i+1)%3][1]-p[1]) for i,p in enumerate(poly)]
                if min(distances)<1:shade-=55
                raster.putpixel((px,py),transform(tuple(max(0,min(255,c+shade)) for c in foreground)))
    if rectangle:
        _,x,y=target;ImageDraw.Draw(raster).rectangle((x,y,x+31,y+31),fill=transform(foreground))
    if scale!=1:raster=raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    image=RGBImage(raster.width,raster.height,raster.tobytes());room=Box(0,0,image.width,image.height)
    frame=SourceFrame(image,room)
    original=[SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in teachers+cluster[:-1]]
    return image,room,frame,original,target


def evidence(values,*,source_grid=(25,19)):
    _,_,frame,original,_=values
    filled=FilledGlyphEvidence(frame,original)
    return SourceInteriorGlyphEvidence(filled,original,source_grid=source_grid),filled


class SourceInteriorGlyphTests(TestCase):
    def test_touching_positive_closed_geometry_and_original_RGB(self):
        values=scene();query,filled=evidence(values);original=deepcopy(values[3])
        proof=query.support(values[4]);self.assertTrue(proof['passed'],proof)
        self.assertFalse(filled.support(values[4])['passed'])
        self.assertTrue(all(e['support']>=9 and not e['unknown'] for e in proof['raw_triangle']))
        self.assertGreaterEqual(len(proof['appearance']['original_teachers']),3)
        self.assertGreaterEqual(proof['appearance']['known_exterior_background_pixels'],16)
        self.assertEqual(values[3],original)

    def test_directions_polarity_palette_brightness_fractional_capture(self):
        transforms=(lambda c:c,lambda c:tuple(255-v for v in c),
            lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(v*.4) for v in c))
        for rotation,transform in enumerate(transforms):
            for scale in (1,1.25):
                with self.subTest(rotation=rotation,scale=scale):
                    values=scene(rotation=rotation,scale=scale,transform=transform)
                    proof=evidence(values)[0].support(values[4]);self.assertTrue(proof['passed'],proof)

    def test_wrong_nearby_pose_cannot_replace_raw_geometry(self):
        query,_=evidence(scene());self.assertFalse(query.support((4,240,232))['passed'])

    def test_background_and_wrong_direction_are_not_positive(self):
        query,_=evidence(scene())
        for key in ((3,608,400),(6,224,240),(5,256,224)):
            with self.subTest(key=key):self.assertFalse(query.support(key)['passed'])

    def test_complete_foreground_rectangle_not_a_triangle(self):
        values=scene(rectangle=True);self.assertFalse(evidence(values)[0].support(values[4])['passed'])

    def test_original_marker_covers_body_but_water_does_not(self):
        for kind in (11,18,14,15,23):
            values=scene();_,x,y=values[4];values[3].append(SimpleNamespace(type_id=kind,x=x,y=y))
            proof=evidence(values)[0].support(values[4])
            with self.subTest(kind=kind):self.assertEqual(proof['passed'],kind in (14,15,23),proof)

    def test_platform_below_glyph_not_fake_32px_occlusion(self):
        values=scene();_,x,y=values[4];values[3].append(SimpleNamespace(type_id=13,x=x,y=y+24))
        self.assertTrue(evidence(values)[0].support(values[4])['passed'])

    def test_three_other_independent_original_teachers_required(self):
        values=scene();values[3][:]=values[3][:2]
        self.assertFalse(evidence(values)[0].support(values[4])['passed'])
        values=scene();values[3][:]=[values[3][0]]*4
        self.assertFalse(evidence(values)[0].support(values[4])['passed'])

    def test_query_cannot_teach_itself_or_use_overlapping_crops(self):
        values=scene();proof=evidence(values)[0].support(values[4]);self.assertTrue(proof['passed'],proof)
        _,x,y=values[4]
        self.assertTrue(all(abs(k[1]-x)>=32 or abs(k[2]-y)>=32 for k in proof['appearance']['original_teachers']))

    def test_crop_and_low_resolution_stay_unknown(self):
        query,_=evidence(scene());proof=query.support((3,0,0))
        self.assertFalse(proof['passed']);self.assertTrue(proof['unknown'])
        values=scene(scale=.125);self.assertFalse(evidence(values)[0].support(values[4])['passed'])

    def test_compact_and_extended_frames_abstain(self):
        values=scene();self.assertFalse(evidence(values,source_grid=(19,13))[0].support(values[4])['passed'])
        image,room,_,original,target=values
        frame=SourceFrame(image,room,extent=Box(-8,0,816,608),canonical=image)
        query=SourceInteriorGlyphEvidence(FilledGlyphEvidence(frame,original),original,source_grid=(25,19))
        self.assertFalse(query.support(target)['passed'])

    def test_new_original_or_invented_teacher_rejected(self):
        values=scene();_,filled=evidence(values)
        changed=values[3]+[SimpleNamespace(type_id=3,x=608,y=400)]
        with self.assertRaisesRegex(ValueError,'detections changed'):
            SourceInteriorGlyphEvidence(filled,changed,source_grid=(25,19))
        filled.library.models.append(dict(native_size=32,original_source_witnesses=[(3,608,400)]))
        with self.assertRaisesRegex(ValueError,'non-original teachers'):
            SourceInteriorGlyphEvidence(filled,values[3],source_grid=(25,19))

    def test_proof_mutation_cannot_change_later_results(self):
        values=scene();query,_=evidence(values);before=query.support(values[4])
        proof=query.support(values[4]);proof['appearance']['original_teachers']=[];proof['raw_triangle'].clear()
        self.assertEqual(query.support(values[4]),before)

    def test_bad_queries_and_constructor_rejected(self):
        values=scene();query,_=evidence(values)
        for key in ((7,224,240),(3,True,64),(3,float('nan'),64),(3,64)):
            with self.subTest(key=key),self.assertRaises(ValueError):query.support(key)
        with self.assertRaisesRegex(ValueError,'actual original filled'):
            SourceInteriorGlyphEvidence(None,values[3],source_grid=(25,19))
        self.assertGreaterEqual(len(INTERIOR_POINTS),16)

    def test_shared_original_pixel_transform_matches_scalar_reads_exactly(self):
        for rotation in range(4):
            values=scene(rotation=rotation,scale=1.25);query,_=evidence(values)
            kind,x,y=values[4]
            points=[(x+a,y+b) for a,b in (_oriented(kind,*p) for p in INTERIOR_POINTS)]
            expected=tuple(values[2].original_pixel(*p) for p in points)
            self.assertEqual(query._body(values[4]),expected)

    def test_library_crop_and_mutated_rgb_cannot_change_source_domain(self):
        values=scene();_,filled=evidence(values)
        filled.library.raw.room=Box(0,0,768,608)
        with self.assertRaisesRegex(ValueError,'original source'):
            SourceInteriorGlyphEvidence(filled,values[3],source_grid=(25,19))

    def test_closed_inverse_background_triangle_and_text_are_not_glyphs(self):
        image,room,_,original,_=scene()
        raster=Image.frombytes('RGB',(800,608),image.data);draw=ImageDraw.Draw(raster)
        draw.rectangle((544,304,608,368),fill=(210,150,70))
        key=(3,560,320)
        draw.polygon([(560+a,320+b) for a,b in VERTICES[3]],fill=(20,30,60))
        draw.line([(640,320),(672,320),(648,352)],fill=(210,150,70),width=3)
        changed=RGBImage(800,608,raster.tobytes());frame=SourceFrame(changed,room)
        filled=FilledGlyphEvidence(frame,original)
        query=SourceInteriorGlyphEvidence(filled,original,source_grid=(25,19))
        self.assertTrue(all(e.support>=9 and not e.unknown for e in query.field.triangle(*key)))
        self.assertFalse(query.support(key)['passed'])
        self.assertFalse(query.support((3,640,320))['passed'])
        values=scene();_,filled=evidence(values)
        filled.library.raw.image=RGBImage(800,608,bytes(800*608*3))
        with self.assertRaisesRegex(ValueError,'original source'):
            SourceInteriorGlyphEvidence(filled,values[3],source_grid=(25,19))
