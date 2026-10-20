"""Original geometry/exterior witnesses, unknowns and query independence."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from PIL import Image
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_glyph_backdrop import SourceGlyphBackdrop
from scripts.source_local_background import SourceLocalBackground
from scripts.source_pixel_geometry import PolygonPixelCoverage
from scripts.source_sampling import SourceFrame
from tests.test_source_directional_texture import textured_scene


def field(colour=(20,30,40),scale=1):
    image=RGBImage(round(800*scale),round(608*scale),bytes(colour)*round(800*scale)*round(608*scale))
    query=object.__new__(SourceGlyphBackdrop)
    query.frame=SourceFrame(image,Box(0,0,image.width,image.height))
    query._source=query.frame.original_snapshot()
    query.opaque,query.masks,query.anchor_results,query.models=[],{},{},{}
    return query


def anchor(x,y,colour=(20,30,40)):
    return dict(key=(3,x,y),patches=[dict(point=(x+4,y+4),mean=colour),dict(point=(x+28,y+4),mean=colour)])


class SourceGlyphBackdropTests(TestCase):
    def test_known_coherent_source_patch_needs_no_terrain_palette_label(self):
        proof=field()._patch(100,100,10)
        self.assertTrue(proof['passed']);self.assertEqual(proof['mean'],(20,30,40))
        self.assertEqual(len(proof['positions']),16)

    def test_fractional_scale_retains_raw_physical_positions(self):
        proof=field(scale=1.25)._patch(100,100,10)
        self.assertTrue(proof['passed'])
        self.assertTrue(all(isinstance(v,int) for p in proof['positions'] for v in p))

    def test_insufficient_distinct_centres_abstain(self):
        self.assertFalse(field(scale=.5)._patch(100,100,10)['passed'])

    def test_unknown_crop_never_clamped_or_empty(self):
        self.assertFalse(field()._patch(0,0,10)['passed'])

    def test_original_terrain_marker_mini_intrinsic_boxes_exclude_patches(self):
        for box in ((98,98,130,130),(96,96,112,112),(99,99,115,115)):
            query=field();query.opaque=[box]
            self.assertFalse(query._patch(100,100,10)['passed'])

    def test_any_glyph_coverage_of_physical_square_excludes_patch(self):
        query=field();query.masks={(3,96,96):PolygonPixelCoverage(query.frame,[(96,96),(128,96),(128,128)])}
        self.assertFalse(query._patch(100,100,10)['passed'])

    def test_one_incoherent_rgb_sample_rejects_entire_patch(self):
        query=field();raster=Image.new('RGB',(800,608),(20,30,40));raster.putpixel((99,99),(200,30,40))
        query.frame=SourceFrame(RGBImage(800,608,raster.tobytes()),Box(0,0,800,608))
        query._source=query.frame.original_snapshot()
        self.assertFalse(query._patch(100,100,10)['passed'])

    def test_three_other_disjoint_original_anchors_support_fixed_model(self):
        query=field();query.anchor_results[10]=dict(accepted=[anchor(64,64),anchor(192,64),anchor(64,192)])
        proof=query.model((1,400,400),10)
        self.assertTrue(proof['valid']);self.assertEqual(len(proof['other_anchor_boxes']),3)
        self.assertLess(proof['maximum_original_witness_residual'],1e-8)
        for a,b in zip(query.predict(proof,410,410),(20,30,40)):self.assertAlmostEqual(a,b)

    def test_query_context_cannot_be_background_teacher(self):
        query=field();query.anchor_results[10]=dict(accepted=[anchor(64,64),anchor(192,64),anchor(64,192)])
        self.assertFalse(query.model((1,64,64),10)['valid'])

    def test_overlapping_boxes_do_not_supply_independence(self):
        query=field();query.anchor_results[10]=dict(accepted=[anchor(64,64),anchor(72,64),anchor(64,192)])
        self.assertFalse(query.model((1,400,400),10)['valid'])

    def test_nested_cache_proofs_are_isolated(self):
        query=field();query.anchor_results[10]=dict(accepted=[anchor(64,64),anchor(192,64),anchor(64,192)])
        proof=query.model((1,400,400),10);proof['valid']=False;proof['other_anchor_boxes'].clear()
        proof=query.model((1,400,400),10)
        self.assertTrue(proof['valid']);self.assertEqual(len(proof['other_anchor_boxes']),3)

    def test_all_chosen_witnesses_not_only_median_must_fit(self):
        query=field();query.anchor_results[10]=dict(accepted=[anchor(64,64),anchor(192,64),anchor(64,192)])
        prediction=dict(valid=True,source_affine_coefficients=[[20,0,0],[30,0,0],[40,0,0]],source_affine_centre=(416,416),
            source_witnesses=[dict(point=(68,68),mean=(200,30,40)),dict(point=(196,68),mean=(20,30,40))],residual=0)
        with patch.object(SourceLocalBackground,'predict',return_value=prediction):proof=query.model((1,400,400),10)
        self.assertFalse(proof['valid']);self.assertGreater(proof['maximum_original_witness_residual'],10)

    def test_real_original_qualification_across_direction_palette_brightness_scale(self):
        transforms=(lambda c:c,lambda c:tuple(255-v for v in c),lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(v*.4) for v in c))
        for rotation,transform in enumerate(transforms):
            for scale in (1,1.25):
                with self.subTest(rotation=rotation,scale=scale):
                    _,_,frame,original,_=textured_scene(rotation=rotation,scale=scale,transform=transform)
                    before=deepcopy([(d.type_id,d.x,d.y) for d in original])
                    query=SourceGlyphBackdrop(FilledGlyphEvidence(frame,original),original,source_grid=(25,19))
                    proof=query.anchors(15)
                    self.assertGreaterEqual(len(proof['accepted']),3)
                    self.assertEqual(before,[(d.type_id,d.x,d.y) for d in original])
                    self.assertTrue(all(a['original_body_proof']['passed'] for a in proof['accepted']))

    def test_mismatched_original_teacher_set_rejected(self):
        _,_,frame,original,_=textured_scene();filled=FilledGlyphEvidence(frame,original)
        with self.assertRaises(ValueError):SourceGlyphBackdrop(filled,original[:-1],source_grid=(25,19))

    def test_invalid_colour_limits_and_query_types_rejected(self):
        query=field()
        for limit in (True,0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):query.anchors(limit)
        for key in (None,12,(True,100,100),(3,100,100),(1,True,100),(1,float('nan'),100),(1,100)):
            with self.assertRaises(ValueError):query.model(key,10)
