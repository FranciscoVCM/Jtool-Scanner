"""RGB phase corrections and real partly wall-occluded full-size protection."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from PIL import Image,ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_hollow_glyphs import HollowGlyphEvidence
from scripts.source_hollow_phase import refit_source_hollow_phases,confirmed_attachment,known_base_ink
from scripts.source_sampling import SourceFrame
from tests.test_source_hollow_glyphs import hollow_scene,rotate,PALETTES


class HollowPhaseTests(TestCase):
    def test_180_source_shifts_across_palette_scale_direction(self):
        repaired=0
        for palette in range(3):
            for scale in (1.,1.25,.75):
                for turns in range(4):
                    with self.subTest(palette=palette,scale=scale,turns=turns):
                        image,room,locators,true,_=hollow_scene(palette,scale,turns)
                        old=[rotate((5 if i%2==0 else 4,408,256+16*i),turns) for i in range(5)]
                        original=[SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in locators+old]
                        before=[vars(d).copy() for d in original]
                        evidence=HollowGlyphEvidence.from_frame(SourceFrame(image,room),locators+old)
                        self.assertTrue(all(evidence.support(k)['passed'] for k in true))
                        proofs=refit_source_hollow_phases(evidence,original,true)
                        self.assertEqual({p['new'] for p in proofs},true)
                        self.assertEqual({p['old'] for p in proofs},set(old))
                        self.assertEqual([vars(d) for d in original],before)
                        self.assertTrue(all(p['old'][0]==p['new'][0] for p in proofs))
                        repaired+=len(proofs)
        self.assertEqual(repaired,180)

    def test_36_real_fulls_with_24_visible_and_8_inside_wall(self):
        for palette in range(3):
            for scale in (1.,1.25,.75):
                for turns in range(4):
                    with self.subTest(palette=palette,scale=scale,turns=turns):
                        bg,fg=PALETTES[palette];raster=Image.new('RGB',(800,608),bg);pen=ImageDraw.Draw(raster)
                        teachers=[(3,x,96) for x in (96,192,288)]
                        for t,x,y in teachers:
                            poly=[(x+u,y+v) for u,v in VERTICES[t]]
                            pen.polygon(poly,fill=tuple(min(255,v+3) for v in bg));pen.line(poly+[poly[0]],fill=fg,width=3)
                        key=rotate((4,400,256),turns);poly=[(key[1]+u,key[2]+v) for u,v in VERTICES[key[0]]]
                        pen.polygon(poly,fill=tuple(min(255,v+3) for v in bg));pen.line(poly+[poly[0]],fill=fg,width=3)
                        corners=[(376,256),(408,256),(408,288),(376,288)]
                        for _ in range(turns):corners=[(432-(y-304),304+(x-432)) for x,y in corners]
                        bx,by=min(x for x,y in corners),min(y for x,y in corners)
                        pen.rectangle((bx,by,bx+31,by+31),fill=fg)
                        raster=raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
                        image=RGBImage(raster.width,raster.height,raster.tobytes());room=Box(0,0,raster.width,raster.height)
                        evidence=HollowGlyphEvidence.from_frame(SourceFrame(image,room),teachers+[key])
                        old=SimpleNamespace(type_id=key[0],x=key[1],y=key[2])
                        confirmed,faces=confirmed_attachment(evidence,old,{(bx,by)})
                        self.assertTrue(confirmed,faces)
                        original=[old,SimpleNamespace(type_id=1,x=bx,y=by)]
                        candidate=(key[0],key[1]+8,key[2])
                        self.assertEqual(refit_source_hollow_phases(evidence,original,{candidate}),[])

    def test_unknown_source_interface_abstains_before_alternative_evidence(self):
        image,room,locators,true,_=hollow_scene()
        old=SimpleNamespace(type_id=5,x=408,y=256)
        evidence=HollowGlyphEvidence.from_frame(SourceFrame(image,room),locators+[(5,408,256)])
        with patch('scripts.source_hollow_phase.confirmed_attachment',return_value=(False,[dict(unknown=True)])):
            self.assertEqual(refit_source_hollow_phases(evidence,[old],true),[])

    def test_no_nearby_alternative_does_not_query_old_source(self):
        evidence=SimpleNamespace(support=lambda key:self.fail('Unrelated pose queried'))
        old=SimpleNamespace(type_id=5,x=96,y=96)
        self.assertEqual(refit_source_hollow_phases(evidence,[old],{(5,400,400)}),[])

    def test_unknown_raw_base_is_not_an_absence_proof(self):
        image,room,locators,true,_=hollow_scene()
        old=SimpleNamespace(type_id=5,x=408,y=256)
        evidence=HollowGlyphEvidence.from_frame(SourceFrame(image,room),locators+[(5,408,256)])
        with patch('scripts.source_hollow_phase.known_base_ink',return_value=None):
            self.assertEqual(refit_source_hollow_phases(evidence,[old],true),[])

    def test_known_base_count_rejects_one_unknown_band_pixel(self):
        frame=SimpleNamespace(original_position=lambda x,y:(int(x),int(y)),
            original_pixel=lambda x,y:None if y>10 else (0,0,0))
        evidence=SimpleNamespace(frame=frame,models=[dict(foreground=(255,255,255),background=(0,0,0))])
        self.assertIsNone(known_base_ink(evidence,(10,10),(42,10),0))

    def test_same_source_repairs_do_not_depend_on_original_object_order(self):
        image,room,locators,true,_=hollow_scene()
        old=[(5 if i%2==0 else 4,408,256+16*i) for i in range(5)]
        original=[SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in locators+old]
        evidence=HollowGlyphEvidence.from_frame(SourceFrame(image,room),locators+old)
        forward=refit_source_hollow_phases(evidence,original,true)
        reverse=refit_source_hollow_phases(evidence,list(reversed(original)),true)
        pairs=lambda proofs:{(p['old'],p['new']) for p in proofs}
        self.assertEqual(pairs(forward),pairs(reverse))
        self.assertEqual({p['new'] for p in forward},true)

    def test_known_raw_base_reports_zero_and_complete_ink_separately(self):
        frame=SimpleNamespace(original_position=lambda x,y:(int(x),int(y)),
            original_pixel=lambda x,y:(0,0,0))
        evidence=SimpleNamespace(frame=frame,models=[dict(foreground=(255,255,255),background=(0,0,0))])
        self.assertEqual(known_base_ink(evidence,(10,10),(42,10),0),0)
        frame.original_pixel=lambda x,y:(255,255,255)
        self.assertEqual(known_base_ink(evidence,(10,10),(42,10),0),12)
