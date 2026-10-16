"""Portable filled-object geometry and immutable-source recovery checks."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_filled_pipeline import FilledGlyphEvidence, distinguish_filled_instances, filled_hypotheses, recover_source_filled_glyphs
from scripts.source_glyph_prototypes import SourceGlyphLibrary, _contains
from scripts.source_sampling import SourceFrame

TEACHERS = ((3, 160, 160), (4, 256, 160), (6, 352, 160))
TARGET = (5, 224, 288)


def scene(background=(20,30,60), foreground=(210,150,70), transform=lambda c:c, scale=1):
    raster = Image.new('RGB', (800,608), transform(background))
    draw = ImageDraw.Draw(raster)
    for kind,x,y in TEACHERS+(TARGET,):
        # Pixel-center triangle membership avoids painting a base outside its box.
        poly=[(x+u,y+v) for u,v in VERTICES[kind]]
        for py in range(y,y+32):
            for px in range(x,x+32):
                if _contains(poly,px+.5,py+.5):
                    draw.point((px,py),fill=transform(foreground))
    if scale != 1:
        raster=raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    image=RGBImage(raster.width,raster.height,raster.tobytes())
    frame=SourceFrame(image,Box(0,0,image.width,image.height))
    original=[SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in TEACHERS]
    return frame,original


class SourceFilledPipelineTests(TestCase):
    def with_raster(self, frame, edit):
        image=frame.original_snapshot()
        raster=Image.frombytes('RGB',(image.width,image.height),image.data)
        edit(raster)
        changed=RGBImage(raster.width,raster.height,raster.tobytes())
        return SourceFrame(changed,Box(0,0,changed.width,changed.height))

    def test_source_proved_full_filled_target(self):
        frame,original=scene()
        proof=FilledGlyphEvidence(frame,original).support(TARGET)
        self.assertTrue(proof['passed'],proof)
        self.assertEqual(len(proof['independent_filled_teachers']),3)

    def test_palette_polarity_and_fractional_scale(self):
        for transform in (lambda c:c, lambda c:tuple(255-v for v in c),lambda c:(c[2],c[0],c[1])):
            for scale in (1,1.25):
                frame,original=scene(transform=transform,scale=scale)
                self.assertTrue(FilledGlyphEvidence(frame,original).support(TARGET)['passed'])

    def test_wrong_direction_and_background_are_not_filled_objects(self):
        frame,original=scene()
        evidence=FilledGlyphEvidence(frame,original)
        self.assertFalse(evidence.support((3,TARGET[1],TARGET[2]))['passed'])
        self.assertFalse(evidence.support((3,512,352))['passed'])

    def test_isoluminant_and_dim_objects_use_rgb_not_grayscale(self):
        bg,fg=(80,120,40),(150,80,65)
        self.assertEqual(Image.new('RGB',(1,1),bg).convert('L').getpixel((0,0)),
                         Image.new('RGB',(1,1),fg).convert('L').getpixel((0,0)))
        for transform in (lambda c:c,lambda c:tuple(round(v*.25) for v in c)):
            frame,original=scene(background=bg,foreground=fg,transform=transform)
            self.assertTrue(FilledGlyphEvidence(frame,original).support(TARGET)['passed'])

    def test_real_objects_with_local_brightness_texture(self):
        frame,original=scene()
        def edit(raster):
            for kind,x,y in TEACHERS+(TARGET,):
                poly=[(x+u,y+v) for u,v in VERTICES[kind]]
                for py in range(y,y+32):
                    for px in range(x,x+32):
                        if _contains(poly,px+.5,py+.5):
                            delta=(px-x+py-y)//4-8
                            raster.putpixel((px,py),tuple(v+delta for v in (210,150,70)))
        textured=self.with_raster(frame,edit)
        self.assertTrue(FilledGlyphEvidence(textured,original).support(TARGET)['passed'])

    def test_rectangles_diagonals_and_text_are_not_triangles(self):
        frame,original=scene()
        def edit(raster):
            draw=ImageDraw.Draw(raster)
            draw.rectangle((512,352,543,383),fill=(210,150,70))
            draw.rectangle((560,352,591,383),outline=(210,150,70),width=2)
            draw.line((560,352,591,383),fill=(210,150,70),width=2)
            draw.text((608,352),'8',fill=(210,150,70))
        evidence=FilledGlyphEvidence(self.with_raster(frame,edit),original)
        for x in (512,560,608):
            for kind in (3,4,5,6):
                self.assertFalse(evidence.support((kind,x,352))['passed'])

    def test_hollow_outline_is_not_a_filled_teacher_or_object(self):
        frame,original=scene()
        def edit(raster):
            poly=[(512+u,352+v) for u,v in VERTICES[3]]
            ImageDraw.Draw(raster).line(poly+[poly[0]],fill=(210,150,70),width=2)
        self.assertFalse(FilledGlyphEvidence(self.with_raster(frame,edit),original).support((3,512,352))['passed'])

    def test_closed_opposing_triangle_void_is_not_an_object(self):
        frame,original=scene()
        def edit(raster):
            draw=ImageDraw.Draw(raster)
            for t,x,y in ((6,496,320),(6,528,320),(6,512,352)):
                poly=[(x+u,y+v) for u,v in VERTICES[t]]
                for py in range(y,y+32):
                    for px in range(x,x+32):
                        if _contains(poly,px+.5,py+.5):draw.point((px,py),fill=(210,150,70))
        self.assertFalse(FilledGlyphEvidence(self.with_raster(frame,edit),original).support((3,512,320))['passed'])

    def test_wrong_locator_direction_is_not_a_teacher_answer(self):
        frame,original=scene()
        wrong=[SimpleNamespace(type_id=4,x=d.x,y=d.y) for d in original]
        self.assertTrue(FilledGlyphEvidence(frame,wrong).support(TARGET)['passed'])

    def test_shared_library_source_directions_can_correct_original_locators(self):
        frame,original=scene()
        wrong=[SimpleNamespace(type_id=4,x=d.x,y=d.y) for d in original]
        library=SourceGlyphLibrary(frame.original_snapshot(),frame.room,
                                   [(d.type_id,d.x,d.y) for d in wrong],source_frame=frame)
        self.assertTrue(FilledGlyphEvidence(frame,wrong,source_library=library).support(TARGET)['passed'])

    def test_shared_library_never_borrows_new_teacher_origins(self):
        frame,original=scene()
        library=SourceGlyphLibrary(frame.original_snapshot(),frame.room,TEACHERS+(TARGET,),source_frame=frame)
        with self.assertRaisesRegex(ValueError,'non-original'):
            FilledGlyphEvidence(frame,original,source_library=library)

    def test_legacy_border_teacher_rebuilds_without_pruning_or_unknown_teachers(self):
        frame, original = scene()
        border = (4, 768, 320)
        poly = [(border[1]+u, border[2]+v) for u,v in VERTICES[border[0]]]
        def paint(raster):
            draw = ImageDraw.Draw(raster)
            for y in range(320, 352):
                for x in range(768, 800):
                    if _contains(poly, x+.5, y+.5):
                        draw.point((x,y), fill=(210,150,70))
        frame = self.with_raster(frame, paint)
        original += [SimpleNamespace(type_id=border[0], x=border[1], y=border[2])]
        library = SourceGlyphLibrary(frame.original_snapshot(), frame.room,
                                     [(d.type_id,d.x,d.y) for d in original])
        self.assertTrue(any(tuple(a['key']) == border for a in library.anchors))
        original_anchors = deepcopy(library.anchors)
        shared = FilledGlyphEvidence(frame, original, source_library=library)
        fresh = FilledGlyphEvidence(frame, original)
        self.assertIsNot(shared.library, library)
        self.assertEqual(library.anchors, original_anchors)
        self.assertTrue(shared.support(TARGET)['passed'])
        self.assertEqual(shared.support(TARGET), fresh.support(TARGET))
        self.assertTrue(shared.support(border)['unknown'])
        self.assertFalse(any(tuple(a['key']) == border for a in shared.library.anchors))

    def test_library_from_another_source_is_rejected(self):
        frame,original=scene()
        different,_=scene(background=(90,20,10))
        library=SourceGlyphLibrary(different.original_snapshot(),different.room,TEACHERS,source_frame=different)
        with self.assertRaisesRegex(ValueError,'original source'):
            FilledGlyphEvidence(frame,original,source_library=library)

    def test_duplicate_locators_do_not_create_independent_teachers(self):
        frame,original=scene()
        self.assertFalse(FilledGlyphEvidence(frame,[original[0]]*3).support(TARGET)['passed'])

    def test_one_apex_cannot_turn_a_close_phase_alternative_into_two_objects(self):
        frame,original=scene()
        snapshot=deepcopy(original)
        alias=(3,160,168)
        proposed,alternatives=distinguish_filled_instances({alias},original,FilledGlyphEvidence(frame,original))
        self.assertEqual(proposed,set())
        self.assertEqual(tuple(alternatives[0]['key']),alias)
        self.assertTrue(alternatives[0]['source_shape_not_declared_false'])
        self.assertEqual(original,snapshot)

    def test_real_close_same_direction_apices_are_not_blanket_overlap_removed(self):
        frame,original=scene()
        extra=(3,168,160)
        def edit(raster):
            poly=[(extra[1]+u,extra[2]+v) for u,v in VERTICES[extra[0]]]
            for py in range(extra[2],extra[2]+32):
                for px in range(extra[1],extra[1]+32):
                    if _contains(poly,px+.5,py+.5):raster.putpixel((px,py),(210,150,70))
        evidence=FilledGlyphEvidence(self.with_raster(frame,edit),original)
        proposed,alternatives=distinguish_filled_instances({extra},original,evidence)
        self.assertEqual(proposed,{extra})
        self.assertEqual(alternatives,[])

    def test_real_repair_is_recorded_not_silently_emitted_as_a_duplicate(self):
        frame,original=scene()
        original[0]=SimpleNamespace(type_id=3,x=160,y=168)
        proposed,alternatives=distinguish_filled_instances({(3,160,160)},original,FilledGlyphEvidence(frame,original))
        self.assertEqual(proposed,set())
        self.assertTrue(alternatives[0]['no_original_retirement'])

    def test_unknown_apex_is_not_a_background_or_retirement_proof(self):
        frame,original=scene()
        evidence=FilledGlyphEvidence(frame,original)
        self.assertTrue(evidence.apex_support((3,160,0))['unknown'])

    def test_apex_diagnostics_do_not_poison_cached_evidence(self):
        frame,original=scene()
        evidence=FilledGlyphEvidence(frame,original)
        first=evidence.apex_support(TEACHERS[0])
        self.assertTrue(first['passed'])
        first['passed']=False
        self.assertTrue(evidence.apex_support(TEACHERS[0])['passed'])

    def test_an_unsupported_original_hint_can_locate_but_never_teach(self):
        frame,original=scene()
        original.append(SimpleNamespace(type_id=3,x=216,y=288))
        proposed,proof=recover_source_filled_glyphs(frame,original,terrain_neighbors=False)
        self.assertIn(TARGET,proposed)
        target=next(r for r in proof['accepted'] if tuple(r['key'])==TARGET)
        self.assertNotIn((3,216,288),target['evidence']['independent_filled_teachers'])

    def test_two_teachers_cannot_validate_new_objects(self):
        frame,original=scene()
        self.assertFalse(FilledGlyphEvidence(frame,original[:2]).support(TARGET)['passed'])

    def test_no_qualified_model_skips_recovery_queries(self):
        frame,original=scene()
        from unittest.mock import patch
        with patch.object(FilledGlyphEvidence,'support',side_effect=AssertionError('No unused source queries')):
            proposed,proof=recover_source_filled_glyphs(frame,original[:2])
        self.assertEqual(proposed,set())
        self.assertEqual(proof['evaluated'],0)

    def test_source_queries_never_add_teachers(self):
        frame,original=scene()
        evidence=FilledGlyphEvidence(frame,original[:2])
        for key in TEACHERS+(TARGET,):
            evidence.support(key)
        self.assertEqual(evidence.original_spikes,TEACHERS[:2])
        self.assertFalse(evidence.support(TARGET)['passed'])

    def test_boundary_is_unknown_not_padded_negative(self):
        frame,original=scene()
        proof=FilledGlyphEvidence(frame,original).support((3,160,576))
        self.assertTrue(proof['unknown'])
        self.assertFalse(proof['passed'])

    def test_diagnostics_are_independent_copies(self):
        frame,original=scene()
        evidence=FilledGlyphEvidence(frame,original)
        first=evidence.support(TARGET)
        first['passed']=False
        self.assertTrue(evidence.support(TARGET)['passed'])

    def test_original_terrain_seeds_attached_spike_without_teacher_growth(self):
        original=[SimpleNamespace(type_id=1,x=192,y=64)]
        before=deepcopy(original)
        self.assertIn((5,160,64),filled_hypotheses(original))
        self.assertEqual(original,before)
        self.assertNotIn((5,160,64),filled_hypotheses(original,terrain_neighbors=False))

    def test_neighbor_switch_requires_boolean(self):
        with self.assertRaises(ValueError):
            filled_hypotheses([],terrain_neighbors=1)

    def test_recovery_does_not_mutate_inputs_or_propose_existing(self):
        frame,original=scene()
        snapshot=deepcopy(original)
        proposed,proof=recover_source_filled_glyphs(frame,original,terrain_neighbors=False)
        self.assertFalse(set(TEACHERS)&proposed)
        self.assertEqual(original,snapshot)
        self.assertTrue(proof['no_existing_object_retirement'])
