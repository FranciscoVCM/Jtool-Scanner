"""Procedural original-source size evidence and equivalent-union safeguards."""
from copy import deepcopy
from dataclasses import asdict
import unittest
from PIL import Image
from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_sampling import SourceFrame
from scripts.source_occupancy import footprint
from scripts.source_full_representation import recover_full_representations,quad

TEACHERS=((96,96),(224,96),(352,96),(96,224));TARGET=(432,320)
def scene(*,scale=(800,608),background=(20,30,40),paint=(200,150,90),mini=False,
          ambiguous=False,flat=False,dim=False,crop=False,pair=False):
    image=Image.new('RGB',(800,608),background)
    def patch(x,y,size,period16=False,attenuation=1):
        for j in range(size):
            for i in range(size):
                u,v=(i%16,j%16) if period16 else (i,j)
                delta=0 if flat else 35 if (u+2*v)%17<3 else -15 if (2*u-v)%13<2 else 0
                rgb=tuple(max(0,min(255,round((c+delta)*attenuation))) for c in paint)
                image.putpixel((x+i,y+j),rgb)
    for x,y in TEACHERS:patch(x,y,32,period16=ambiguous)
    targets=[TARGET,(464,320)] if pair else [TARGET]
    for x,y in targets:
        if mini:
            for a,b in sorted(quad(x,y)):patch(a,b,16,period16=True)
        else:patch(x,y,32,period16=ambiguous,attenuation=.6 if dim else 1)
    canonical=RGBImage(800,608,image.tobytes())
    image=image.resize(scale,Image.Resampling.BILINEAR)
    source=RGBImage(image.width,image.height,image.tobytes());room=Box(0,0,*scale)
    frame=SourceFrame(source,room)
    if crop:frame=SourceFrame(source,Box(4,4,scale[0]-8,scale[1]-8),extent=room,canonical=canonical)
    original=tuple(scanner.Detection('original full locator',1,x,y,.8,Box(x,y,32,32)) for x,y in TEACHERS)
    material={p for a,b in (*TEACHERS,*targets) for p in quad(a,b)}
    proposals={(2,*p) for a,b in targets for p in quad(a,b)}
    return frame,original,proposals,material,set(material),targets

def evaluate(case):
    frame,original,proposals,material,certainty,targets=case
    frozen=deepcopy(([asdict(d) for d in original],proposals,material,certainty))
    result,diag=recover_full_representations(frame,original,proposals,set(),material,certainty)
    assert frozen==([asdict(d) for d in original],proposals,material,certainty)
    assert {p for k in proposals for p in footprint(k)}=={p for k in result for p in footprint(k)}
    return result,diag

class RepresentationTests(unittest.TestCase):
    def test_full_identity_palettes_and_fractional_scales(self):
        palettes=[((20,30,40),(200,150,90)),((230,235,240),(70,90,110)),
                  ((20,135,80),(190,45,160)),((90,110,120),(140,85,145))]
        for background,paint in palettes:
            for scale in ((800,608),(1000,760),(720,547),(968,711)):
                with self.subTest(paint=paint,scale=scale):
                    result,_=evaluate(scene(background=background,paint=paint,scale=scale))
                    self.assertEqual(result,{(1,*TARGET)})
    def test_dimmed_texture_not_fixed_brightness(self):
        self.assertEqual(evaluate(scene(dim=True))[0],{(1,*TARGET)})
    def test_four_real16_sprites_are_not_merged(self):
        for scale in ((800,608),(1000,760),(720,547)):
            with self.subTest(scale=scale):
                case=scene(mini=True,scale=scale);self.assertEqual(evaluate(case)[0],case[2])
    def test_identical_render_size_ambiguity_abstains(self):
        for scale in ((800,608),(1000,760),(720,547)):
            with self.subTest(scale=scale):
                case=scene(ambiguous=True,scale=scale);self.assertEqual(evaluate(case)[0],case[2])
    def test_original_minis_and_fulls_are_never_removed(self):
        for kind in (1,2):
            case=list(scene());original=case[1]+(scanner.Detection('real original',kind,*TARGET,.8,Box(*TARGET,16,16)),)
            case[1]=original;self.assertEqual(evaluate(case)[0],case[2])
    def test_missing_material_certainty_or_proposal_does_not_fill(self):
        for index in (2,3,4):
            case=list(scene());case[index]=set(case[index]);case[index].remove((2,*TARGET) if index==2 else TARGET)
            self.assertEqual(evaluate(case)[0],case[2])
    def test_flat_and_unknown_frames_abstain(self):
        for case in (scene(flat=True),scene(crop=True)):
            self.assertEqual(evaluate(case)[0],case[2])
    def test_multiple_targets_preserve_union_and_native_phase(self):
        self.assertEqual(evaluate(scene(pair=True))[0],{(1,432,320),(1,464,320)})
    def test_original_order_duplicate_and_query_cannot_teach(self):
        case=scene();expected,diag=evaluate(case)
        other=list(case);other[1]=tuple(reversed(case[1]))+(case[1][0],)
        self.assertEqual(evaluate(other)[0],expected)
        for row in diag['rows']:
            if row['passed']:
                self.assertNotIn(TARGET,map(tuple,row['source_proof']['source_teachers']))

    def test_adjacent_original_terrain_does_not_veto_equivalent_recovery(self):
        case=list(scene());case[1]=case[1]+(scanner.Detection('touching original',1,400,320,.8,Box(400,320,32,32)),)
        self.assertEqual(evaluate(case)[0],{(1,*TARGET)})

    def test_source_rejected_full_is_never_reintroduced(self):
        frame,original,proposed,material,certainty,_=scene()
        result,diag=recover_full_representations(frame,original,proposed,{(1,*TARGET)},material,certainty)
        self.assertEqual(result,proposed)
        self.assertFalse(any(row['passed'] for row in diag['rows']))

    def test_proposed_fulls_do_not_supply_missing_original_teachers(self):
        frame,original,proposed,material,certainty,_=scene()
        proposed=proposed|{(1,*p) for p in TEACHERS[2:]}
        result,_=recover_full_representations(frame,original[:2],proposed,set(),material,certainty)
        self.assertEqual(result,proposed)
        self.assertNotIn((1,*TARGET),result)


