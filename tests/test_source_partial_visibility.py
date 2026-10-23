"""Procedural full/mini/unknown evidence; no game, archive or reference maps."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import _contains
from scripts.source_partial_visibility import (
    SourcePartialVisibilityEvidence, _PartialVisibilitySession, intersects,
)
from scripts.source_sampling import SourceFrame


def partial_scene(kind=3, *, placement=None, scale=1, transform=lambda c:c,
                  foreground=(210,150,70), background=(20,30,60), negative=None):
    """Three independent glyphs/tiles and one partly hidden query glyph."""
    raster = Image.new('RGB',(800,608),transform(background))
    parent = (160,64)
    query = {3:(3,160,80),4:(4,144,64),6:(6,160,48),5:(5,176,64)}[kind] if placement is None else (kind,*placement)
    teachers = [(kind,x,160) for x in (400,480,560)]
    for t,x,y in teachers+[query]:
        poly = [(x+a,y+b) for a,b in VERTICES[t]]
        for py in range(y,y+32):
            for px in range(x,x+32):
                if not _contains(poly,px+.5,py+.5):
                    continue
                a,b = px+.5-x,py+.5-y
                u,v = ((a,b) if t == 3 else (b,32-a) if t == 4 else (32-b,a) if t == 5 else (32-a,32-b))
                shade = round(.7*(u-16)-.45*(v-16))
                distances = [abs((poly[(i+1)%3][0]-p[0])*(p[1]-py-.5)-(p[0]-px-.5)*(poly[(i+1)%3][1]-p[1])) /
                    ((poly[(i+1)%3][0]-p[0])**2+(poly[(i+1)%3][1]-p[1])**2)**.5 for i,p in enumerate(poly)]
                if min(distances) < 1:
                    shade -= 55
                raster.putpixel((px,py),transform(tuple(max(0,min(255,c+shade)) for c in foreground)))
    rectangles = [parent]+[(x,352) for x in (400,480,560)]
    for x,y in rectangles:
        for b in range(32):
            for a in range(32):
                color = (25,35,15) if min(a,b,31-a,31-b) < 2 else (
                    (90,190,130) if ((a//6)+(b//6))%2 else (150,105,185))
                raster.putpixel((x+a,y+b),transform(color))
    original = [SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in teachers]
    original += [SimpleNamespace(type_id=1,x=x,y=y) for x,y in rectangles]
    if negative == 'two_rectangle_witnesses':
        original = [d for d in original if not (d.type_id == 1 and (d.x,d.y) == (560,352))]
    if negative == 'unmatched_parent_pattern':
        ImageDraw.Draw(raster).rectangle((160,64,191,95),fill=(240,80,35),outline=(10,10,10),width=2)
    if negative == 'original_marker_cover':
        original.append(SimpleNamespace(type_id=12,x=query[1],y=query[2]))
    if negative in ('empty_visible_region','real_mini_not_full'):
        draw = ImageDraw.Draw(raster)
        draw.rectangle((160,96,191,111),fill=background)
        if negative == 'real_mini_not_full':
            poly = [(168+a/2,96+b/2) for a,b in VERTICES[3]]
            draw.polygon(poly,fill=foreground)
            draw.line(poly+[poly[0]],fill=(40,40,40),width=1)
    if scale != 1:
        raster = raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    image = RGBImage(raster.width,raster.height,raster.tobytes())
    return SourceFrame(image,Box(0,0,image.width,image.height)),original,parent,query


def positive_keys(result):
    return [tuple(row['key']) for row in result['evidence']['rows'] if row['provisional']]


class SourcePartialVisibilityTests(TestCase):
    def evidence(self,values,*,grid=(25,19)):
        return SourcePartialVisibilityEvidence(values[0],values[1],source_grid=grid)

    def check_positive(self,values):
        field = self.evidence(values)
        before = deepcopy(values[1])
        result = field.support_parent(values[2])
        self.assertTrue(result['qualified'])
        self.assertEqual(positive_keys(result),[values[3]])
        self.assertEqual(values[1],before)
        for row in result['evidence']['rows']:
            for phase in row['phases']:
                if phase['passed']:
                    self.assertGreaterEqual(phase['eligibility']['unique'],16)
                    self.assertGreater(phase['eligibility']['hidden'],0)
                    self.assertTrue(phase['body']['paint']['passed'])
        return field,result

    def test_tip_occlusions_across_all_directions_and_palettes(self):
        transforms = (lambda c:c,lambda c:tuple(255-v for v in c),
                      lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(v*.4) for v in c))
        for kind,transform in zip((3,4,6,5),transforms):
            with self.subTest(kind=kind):
                self.check_positive(partial_scene(kind,transform=transform))

    def test_side_occlusions_across_directions_and_fractional_capture(self):
        cases = ((3,(144,64)),(3,(176,64)),(4,(160,48)),(4,(160,80)),
                 (6,(144,64)),(6,(176,64)),(5,(160,48)),(5,(160,80)))
        transforms = (lambda c:c,lambda c:tuple(255-v for v in c),
                      lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(v*.4) for v in c))
        for n,(kind,placement) in enumerate(cases):
            with self.subTest(kind=kind,placement=placement):
                self.check_positive(partial_scene(kind,placement=placement,
                    scale=1 if n%2 == 0 else 1.25,transform=transforms[n%4]))

    def test_all_five_negative_material_marker_mini_and_empty_cases(self):
        for case in ('two_rectangle_witnesses','unmatched_parent_pattern',
                     'original_marker_cover','empty_visible_region','real_mini_not_full'):
            with self.subTest(case=case):
                values = partial_scene(negative=case)
                result = self.evidence(values).support_parent(values[2])
                self.assertEqual(positive_keys(result),[])

    def test_isoluminant_RGB_body_does_not_need_grayscale_separation(self):
        foreground,background = (150,80,65),(80,120,40)
        self.assertEqual(Image.new('RGB',(1,1),foreground).convert('L').getpixel((0,0)),
                         Image.new('RGB',(1,1),background).convert('L').getpixel((0,0)))
        self.check_positive(partial_scene(foreground=foreground,background=background))

    def test_original_query_pixels_never_fit_their_own_witness_models(self):
        values = partial_scene()
        values[1].append(SimpleNamespace(type_id=values[3][0],x=values[3][1],y=values[3][2]))
        _,result = self.check_positive(values)
        evidence = result['evidence']
        self.assertNotIn(values[3],{tuple(k) for group in evidence['original_glyph_cohorts'] for k in group})
        for group in evidence['independent_rectangle_cohorts']:
            for (x,y),(dx,dy) in group:
                self.assertFalse(any(intersects((x+dx-4,y+dy-4,x+dx+36,y+dy+36),box)
                                     for box in evidence['exclusion_domains']))

    def test_caller_locator_and_marker_mutation_cannot_reteach_the_snapshot(self):
        values = partial_scene(negative='original_marker_cover')
        field = self.evidence(values)
        values[1][0].x += 8
        values[1][-1].x += 128
        self.assertEqual(positive_keys(field.support_parent(values[2])),[])

    def test_result_mutation_cannot_corrupt_the_next_proof(self):
        values = partial_scene()
        field,result = self.check_positive(values)
        expected = deepcopy(result)
        result['evidence']['masks'].clear()
        result['evidence']['original_glyph_cohorts'].clear()
        self.assertEqual(field.support_parent(values[2]),expected)

    def test_same_coordinates_on_another_source_have_isolated_caches(self):
        first = partial_scene()
        self.check_positive(first)
        second = partial_scene(negative='empty_visible_region')
        self.assertEqual(positive_keys(self.evidence(second).support_parent(second[2])),[])

    def test_compact_grid_is_unknown_without_fitting_or_sampling(self):
        values = partial_scene()
        field = self.evidence(values,grid=(19,13))
        with patch.object(field,'_measure_parent',side_effect=AssertionError('No compact fitting')):
            result = field.support_parent(values[2])
        self.assertFalse(result['qualified'])
        self.assertTrue(result['unknown'])
        self.assertIsNone(result['evidence'])

    def test_padding_cannot_supply_a_missing_original_parent(self):
        frame,original,parent,_ = partial_scene()
        raster = Image.frombytes('RGB',(800,608),frame.canonical_rgb).crop((168,0,800,608))
        image = RGBImage(raster.width,raster.height,raster.tobytes())
        cropped = SourceFrame(image,Box(0,0,image.width,image.height),extent=Box(-168,0,800,608),
            canonical=RGBImage(800,608,frame.canonical_rgb))
        result = SourcePartialVisibilityEvidence(cropped,original,source_grid=(25,19)).support_parent(parent)
        self.assertTrue(result['evidence']['parent_unknown'])
        self.assertEqual(positive_keys(result),[])

    def test_flat_or_linear_source_is_not_a_repeated_rectangle_texture(self):
        raster = Image.new('RGB',(800,608),(40,40,40))
        for y in range(608):
            for x in range(800):
                raster.putpixel((x,y),(30+x//32,40+y//32,60))
        image = RGBImage(800,608,raster.tobytes())
        field = SourcePartialVisibilityEvidence(SourceFrame(image,Box(0,0,800,608)),[],source_grid=(25,19))
        # Inside a single plateau the residual is zero, not unit artwork.
        self.assertIsNone(field.signature(64,64,4))
        for y in range(608):
            for x in range(800):
                raster.putpixel((x,y),(20+x//8,30+y//8,50+(x+y)//16))
        image = RGBImage(800,608,raster.tobytes())
        field = SourcePartialVisibilityEvidence(SourceFrame(image,Box(0,0,800,608)),[],source_grid=(25,19))
        self.assertIsNone(field.signature(64,64,0))
        self.assertIsNone(field.signature(64,64,4))

    def test_wall_perimeter_is_not_an_observed_glyph_edge(self):
        mask = dict(intersection=(10,0,20,10),phases=[dict(box=(10,0,20,10))])
        session = _PartialVisibilitySession(None,None,[mask],())
        self.assertTrue(session.covered(20,10))
        self.assertEqual(session.segments((0,10),(32,10)),[((0.,10.),(10.,10.)),((20.,10.),(32.,10.))])

    def test_uncertain_samples_are_neither_visible_nor_definitely_hidden(self):
        image = RGBImage(800,608,bytes((40,50,60))*(800*608))
        frame = SourceFrame(image,Box(0,0,800,608))
        mask = dict(intersection=(10,10,40,40),phases=[dict(box=(8,8,40,40)),dict(box=(10,10,42,42))])
        session = _PartialVisibilitySession(frame,None,[mask],())
        proof = session.eligibility((3,0,0),32,False)
        self.assertTrue(proof['uncertainty_is_NOT_foreground_OR_background_evidence'])
        self.assertGreater(proof['uncertain'],0)
        self.assertFalse(set(proof['indices']) & set(proof['uncertain_indices']))
        self.assertFalse(set(proof['definitely_hidden_indices']) & set(proof['uncertain_indices']))

    def test_invalid_inputs_and_nonoriginal_parents_are_rejected(self):
        values = partial_scene()
        for grid in (None,[25,19],(25,),(-1,19),(True,19)):
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                self.evidence(values,grid=grid)
        with self.assertRaises(ValueError):
            SourcePartialVisibilityEvidence(None,values[1],source_grid=(25,19))
        with self.assertRaises(ValueError):
            SourcePartialVisibilityEvidence(values[0],[SimpleNamespace(type_id=1,x=160.,y=64)],source_grid=(25,19))
        field = self.evidence(values)
        self.assertIsInstance(field.rectangle_origins,tuple)
        for parent in (None,(True,64),(160.,64),(160,64,32),(999,999)):
            with self.subTest(parent=parent), self.assertRaises(ValueError):
                field.support_parent(parent)
