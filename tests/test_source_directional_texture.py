"""Optional original-direction texture corroboration is not a global veto."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase

from PIL import Image, ImageDraw

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_filled_pipeline import FilledGlyphEvidence, recover_source_filled_glyphs
from scripts.source_geometry_pipeline import source_proposals
from scripts.source_glyph_prototypes import _contains
from scripts.source_interior_glyphs import SourceInteriorGlyphEvidence, INTERIOR_POINTS, _oriented
from scripts.source_sampling import SourceFrame
from tests.test_source_interior_glyphs import scene
from tests.source_geometry_stubs import record_requested_original_filled_source


def textured_scene(*, rotation=0, scale=1, transform=lambda c:c,
                   foreground=(210,150,70),background=(20,30,60)):
    image, room, _, original, target = scene(rotation=rotation,transform=transform,
        foreground=foreground,background=background)
    raster = Image.frombytes('RGB',(800,608),image.data)
    kind = target[0]
    for x,y in ((64,352),(192,352),(320,352)):
        poly = [(x+a,y+b) for a,b in VERTICES[kind]]
        for py in range(y,y+32):
            for px in range(x,x+32):
                a,b = px+.5-x,py+.5-y
                if not _contains(poly,px+.5,py+.5):
                    continue
                u,v = ((a,b) if kind==3 else (b,32-a) if kind==4 else
                       (32-b,a) if kind==5 else (32-a,32-b))
                shade = round(.7*(u-16)-.45*(v-16))
                distances = [abs((poly[(i+1)%3][0]-p[0])*(p[1]-py-.5)-
                    (p[0]-px-.5)*(poly[(i+1)%3][1]-p[1])) /
                    ((poly[(i+1)%3][0]-p[0])**2+(poly[(i+1)%3][1]-p[1])**2)**.5
                    for i,p in enumerate(poly)]
                if min(distances)<1:
                    shade -= 55
                raster.putpixel((px,py),transform(tuple(max(0,min(255,c+shade)) for c in foreground)))
        original.append(SimpleNamespace(type_id=kind,x=x,y=y))
    if scale!=1:
        raster=raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    image=RGBImage(raster.width,raster.height,raster.tobytes())
    room=Box(0,0,image.width,image.height)
    return image,room,SourceFrame(image,room),original,target


def query(values,required=True):
    _,_,frame,original,_=values
    return SourceInteriorGlyphEvidence(FilledGlyphEvidence(frame,original),original,
        source_grid=(25,19),require_directional_texture=required)


class SourceDirectionalTextureTests(TestCase):
    def test_necessary_graph_requires_three_known_disjoint_same_cohort_witnesses(self):
        from unittest.mock import patch
        kind=3
        a,b,c,d=((kind,x,64) for x in (64,192,320,448))
        field=object.__new__(SourceInteriorGlyphEvidence)
        for cohorts,vectors,expected in (
                ([(a,b,c)],{a:(1.,0.),b:(1.,0.),c:(1.,0.)},True),
                ([(a,b,c)],{a:(1.,0.),b:(1.,0.),c:None},False),
                ([(a,b,c)],{a:(1.,0.),b:(0.,1.),c:(1.,0.)},False),
                ([(a,b),(c,d)],{a:(1.,0.),b:(1.,0.),c:(1.,0.),d:(1.,0.)},False),
                ([(a,(3,72,64),c)],{a:(1.,0.),(3,72,64):(1.,0.),c:(1.,0.)},False),
                ([(a,b,(4,320,64))],{a:(1.,0.),b:(1.,0.),(4,320,64):(1.,0.)},False)):
            with self.subTest(cohorts=cohorts,vectors=vectors):
                field._cohorts=cohorts;field._texture_vectors={};field._texture_eligibility={};field._texture_pairs={}
                with patch.object(field,'_texture_vector',side_effect=vectors.get) as sample:
                    self.assertIs(field._has_directional_texture(kind),expected)
                    count=sample.call_count
                    self.assertIs(field._has_directional_texture(kind),expected)
                    self.assertEqual(sample.call_count,count)

    def test_graph_search_does_not_substitute_greedy_models_for_necessary_triangles(self):
        from unittest.mock import patch
        from math import sqrt
        # Three mutually correlated originals plus earlier distractors that
        # would obstruct greedy models. A real triangle must remain eligible.
        a,b,c=((3,x,160) for x in (320,448,576))
        d,e,f=((3,x,64) for x in (64,96,128))
        vertices=[d,e,f,a,b,c]
        vectors={a:(1.,0.,0.),b:(.92,sqrt(1-.92**2),0.),
                 c:(.96,.08,sqrt(1-.96**2-.08**2)),d:(.92,-sqrt(1-.92**2),0.),
                 e:(sqrt(.5),sqrt(.5),0.),f:(.85,0.,sqrt(1-.85**2))}
        def compatible(first,second):
            return (abs(first[1]-second[1])>=32 or abs(first[2]-second[2])>=32) and sum(
                x*y for x,y in zip(vectors[first],vectors[second]))>=.9
        greedy=[]
        for seed in sorted(vertices):
            clique=[seed]
            for teacher in sorted(vertices):
                if teacher!=seed and all(compatible(teacher,other) for other in clique):
                    clique.append(teacher)
            greedy.append(clique)
        self.assertEqual(max(map(len,greedy)),2)
        field=object.__new__(SourceInteriorGlyphEvidence)
        field._cohorts=[tuple(vertices)];field._texture_vectors={};field._texture_eligibility={};field._texture_pairs={}
        with patch.object(field,'_texture_vector',side_effect=vectors.get):
            self.assertTrue(field._has_directional_texture(3))

    def test_impossible_texture_skips_query_body_without_claiming_object_absence(self):
        from unittest.mock import patch
        values=textured_scene();field=query(values)
        teachers=sorted(field._texture_originals)
        vectors={key:tuple(float(i==j) for j in range(len(teachers))) for i,key in enumerate(teachers)}
        with patch.object(field,'_texture_vector',side_effect=vectors.get), \
                patch.object(field,'_body',wraps=field._body) as body:
            proof=field.support(values[4])
        self.assertFalse(proof['passed']);self.assertTrue(proof['unknown'])
        body.assert_not_called()
        self.assertTrue(proof['no_retirement'])

    def test_eligible_queries_retain_entire_positive_proof(self):
        from unittest.mock import patch
        for rotation in range(4):
            values=textured_scene(rotation=rotation)
            with patch.object(SourceInteriorGlyphEvidence,'_has_directional_texture',return_value=True):
                before=query(values).support(values[4])
            self.assertTrue(before['passed'])
            self.assertEqual(query(values).support(values[4]),before)

    def test_legacy_channel_does_not_compute_directional_eligibility(self):
        from unittest.mock import patch
        values=scene();field=query(values,False)
        with patch.object(field,'_has_directional_texture',side_effect=AssertionError('legacy used new gate')):
            self.assertTrue(field.support(values[4])['passed'])

    def test_isoluminant_palette_uses_rgb_not_a_grayscale_texture_pass(self):
        foreground,background=(150,80,65),(80,120,40)
        self.assertEqual(Image.new('RGB',(1,1),foreground).convert('L').getpixel((0,0)),
                         Image.new('RGB',(1,1),background).convert('L').getpixel((0,0)))
        values=textured_scene(foreground=foreground,background=background)
        self.assertTrue(query(values).support(values[4])['passed'])

    def test_small_sprite_variation_does_not_require_exact_paint_or_pixels(self):
        image,room,_,original,key=textured_scene();kind,x,y=key
        raster=Image.frombytes('RGB',(800,608),image.data)
        for index,(a,b) in enumerate(_oriented(kind,*p) for p in INTERIOR_POINTS):
            if index%3==0:
                old=raster.getpixel((x+a,y+b))
                raster.putpixel((x+a,y+b),tuple(v+1 for v in old))
        changed=RGBImage(800,608,raster.tobytes())
        self.assertTrue(query((changed,room,SourceFrame(changed,room),original,key)).support(key)['passed'])

    def test_cropped_capture_uses_existing_world_mapping_without_padding_evidence(self):
        image,_,frame,original,key=textured_scene()
        raster=Image.frombytes('RGB',(800,608),image.data).crop((8,8,792,600))
        physical=RGBImage(raster.width,raster.height,raster.tobytes());room=Box(0,0,physical.width,physical.height)
        world=SourceFrame(physical,room,extent=Box(-8,-8,800,608),canonical=RGBImage(800,608,frame.canonical_rgb))
        field=query((physical,room,world,original,key))
        self.assertTrue(field.support(key)['passed'])
        edge=field.support((key[0],0,0));self.assertFalse(edge['passed']);self.assertTrue(edge['unknown'])

    def test_uninformative_flat_body_abstains_instead_of_claiming_absence(self):
        image,room,_,original,key=textured_scene();kind,x,y=key
        raster=Image.frombytes('RGB',(800,608),image.data)
        for a,b in (_oriented(kind,*p) for p in INTERIOR_POINTS):
            raster.putpixel((x+a,y+b),(210,150,70))
        changed=RGBImage(800,608,raster.tobytes());field=query((changed,room,SourceFrame(changed,room),original,key))
        self.assertIsNone(field._texture_vector(key))
        self.assertFalse(field.support(key)['passed'])

    def test_portable_positive_directions_rgb_polarity_brightness_and_fractional_scale(self):
        transforms=(lambda c:c,lambda c:tuple(255-v for v in c),
                    lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(v*.4) for v in c))
        for rotation,transform in enumerate(transforms):
            for scale in (1,1.25):
                with self.subTest(rotation=rotation,scale=scale):
                    values=textured_scene(rotation=rotation,scale=scale,transform=transform)
                    proof=query(values).support(values[4])
                    self.assertTrue(proof['passed'],proof)
                    texture=proof['appearance']['directional_source_texture']
                    self.assertTrue(texture['passed'])
                    self.assertGreaterEqual(texture['qualified_models'],1)
                    for model in texture['models']:
                        self.assertGreaterEqual(len(model['teachers']),3)
                        self.assertTrue(all(k[0]==values[4][0] for k in model['teachers']))

    def test_no_directional_teachers_abstains_without_changing_legacy_evidence(self):
        values=scene()
        self.assertTrue(query(values,False).support(values[4])['passed'])
        proof=query(values).support(values[4])
        self.assertFalse(proof['passed'])
        self.assertTrue(proof['unknown'])
        self.assertIn('same-direction',proof['abstained'])

    def test_interior_paint_permutation_is_not_source_texture_identity(self):
        image,room,_,original,key=textured_scene()
        raster=Image.frombytes('RGB',(800,608),image.data)
        kind,x,y=key;positions=[(x+a,y+b) for a,b in (_oriented(kind,*p) for p in INTERIOR_POINTS)]
        paints=[raster.getpixel(p) for p in positions]
        for position,rgb in zip(positions,reversed(paints)):
            raster.putpixel(position,rgb)
        changed=RGBImage(800,608,raster.tobytes());values=(changed,room,SourceFrame(changed,room),original,key)
        self.assertTrue(query(values,False).support(key)['passed'])
        self.assertFalse(query(values).support(key)['passed'])

    def test_query_and_returned_proof_cannot_extend_or_mutate_original_teachers(self):
        values=textured_scene();field=query(values);before=deepcopy(field._cohorts)
        proof=field.support(values[4]);self.assertTrue(proof['passed'])
        proof['appearance']['directional_source_texture']['models'].clear()
        self.assertTrue(field.support(values[4])['appearance']['directional_source_texture']['models'])
        self.assertEqual(field._cohorts,before)
        self.assertTrue(set(field._texture_vectors)<=field._texture_originals)
        with self.assertRaisesRegex(ValueError,'original source witnesses'):
            field._directional_texture(values[4],{'teachers':[(values[4][0],704,480)]})

    def test_true_geometry_remains_necessary_even_with_matching_body_material(self):
        values=textured_scene();image,room,_,original,_=values
        raster=Image.frombytes('RGB',(800,608),image.data)
        ImageDraw.Draw(raster).rectangle((592,384,671,463),fill=(210,150,70))
        changed=RGBImage(800,608,raster.tobytes())
        field=query((changed,room,SourceFrame(changed,room),original,values[4]))
        self.assertFalse(field.support((3,608,400))['passed'])
        self.assertFalse(field.support((4,0,0))['passed'])
        self.assertTrue(field.support((4,0,0))['unknown'])

    def test_existing_filled_recoveries_and_original_objects_are_not_vetoed(self):
        values=textured_scene();_,_,frame,original,target=values;before=deepcopy(original)
        ordinary,_=recover_source_filled_glyphs(frame,original,joint_phase=True)
        extended,diag=recover_source_filled_glyphs(frame,original,joint_phase=True,
            interior_grid=(25,19),interior_texture=True)
        self.assertTrue(ordinary<=extended)
        self.assertIn(target,extended)
        self.assertTrue(diag['no_existing_object_retirement'])
        self.assertEqual(original,before)

    def test_api_requirements_are_explicit_and_boolean(self):
        values=textured_scene();image,room,frame,original,_=values;filled=FilledGlyphEvidence(frame,original)
        for value in (None,0,1,'yes',[]):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'boolean'):
                SourceInteriorGlyphEvidence(filled,original,source_grid=(25,19),require_directional_texture=value)
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'boolean'):
                recover_source_filled_glyphs(frame,original,interior_texture=value)
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'boolean'):
                source_proposals(image,room,original,include_filled_interior_texture=value)
        with self.assertRaisesRegex(ValueError,'requires interior'):
            recover_source_filled_glyphs(frame,original,interior_texture=True)
        with self.assertRaisesRegex(ValueError,'requires interior'):
            source_proposals(image,room,original,include_filled_interior_texture=True)

    def test_scanner_opt_in_always_requests_the_qualified_positive_channel(self):
        from unittest.mock import patch
        values=textured_scene();image,room,_,_,_=values
        fields=[]
        def stage(image,room,detections,**kwargs):
            fields.append(record_requested_original_filled_source(detections,kwargs))
            return set(),set(),{}
        with patch.object(scanner,'_SOURCE_INTERIOR_GLYPHS_ENABLED',True), \
                patch('scripts.source_geometry_pipeline.source_proposals',side_effect=stage) as proposal:
            scanner._apply_source_geometry(scanner.ScanResult(800,608,room,[],source_grid=(25,19)),image)
        self.assertIs(proposal.call_args.kwargs['include_filled_interior_texture'],True)
        self.assertEqual(len(fields),1)
        self.assertIs(proposal.call_args.kwargs['source_context'].filled_source(
            (),proposal.call_args.kwargs['source_frame']),fields[0])

    def test_pipeline_forwards_texture_only_on_explicit_interior_request(self):
        from unittest.mock import patch
        image,room,_,original,_=textured_scene()
        with patch('scripts.source_geometry_pipeline.recover_source_filled_glyphs',
                   return_value=(set(),{'accepted':[]})) as recovery:
            source_proposals(image,room,original,include_filled_glyphs=True,
                include_filled_interior=True,include_filled_interior_texture=True)
        self.assertIs(recovery.call_args.kwargs['interior_texture'],True)
        self.assertEqual(recovery.call_args.kwargs['interior_grid'],(25,19))
        self.assertEqual(recovery.call_args.args[1],tuple(original))
