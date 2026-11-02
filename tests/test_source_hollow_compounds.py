"""Mini/full identity and finite original-terrain queries, not overlap filters."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_hollow_glyphs import HollowGlyphEvidence
from scripts.source_hollow_compounds import MiniHollowQuery, BoundaryExplanation, support_mini, qualify_new_boundaries
from scripts.source_hollow_pipeline import recover_source_hollow_glyphs
from scripts.source_sampling import SourceFrame
from tests.source_sprite_fixtures import hollow_triangle_tile
from tests.test_source_hollow_glyphs import hollow_scene


def mini_scene(palette,scale):
    bg,ink = (((40,50,60),(210,220,225)),((225,220,215),(30,40,50)),((0,130,0),(255,0,0)))[palette]
    inner = tuple(min(255,c+3) for c in bg)
    image = Image.new('RGB',(800,608),bg)
    teachers = [(3,96,96),(3,192,96),(3,288,96)]
    true = {(7,96,320),(8,192,320),(9,288,320),(10,384,320)}
    peers = {(10,400,192),(10,416,192),(10,408,208)}
    false = {(7,408,192),(7,568,400)}
    for t,x,y in teachers+[(3,560,400)]:
        image.paste(hollow_triangle_tile(t,32,background=bg,ink=ink,interior=inner,stroke_width=3),(x,y))
    for t,x,y in sorted(true|peers):
        image.paste(hollow_triangle_tile(t-4,16,background=bg,ink=ink,interior=inner,stroke_width=2),(x,y))
    raster = image.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    frame = SourceFrame(RGBImage(raster.width,raster.height,raster.tobytes()),Box(0,0,raster.width,raster.height))
    return frame,teachers,true|peers,false


class MiniHollowQueryTests(TestCase):
    def test_all_directions_palettes_and_capture_scales(self):
        for palette in range(3):
            for scale in (1.,1.25,.75):
                with self.subTest(palette=palette,scale=scale):
                    frame,teachers,true,false = mini_scene(palette,scale)
                    full = HollowGlyphEvidence.from_frame(frame,teachers)
                    models = deepcopy(full.models)
                    mini = MiniHollowQuery.from_full(full)
                    self.assertTrue(models)
                    for key in sorted(true):
                        self.assertTrue(support_mini(mini,key)['passed'],key)
                    for key in sorted(false):
                        self.assertFalse(support_mini(mini,key)['passed'],key)
                    self.assertEqual(full.models,models)
                    self.assertEqual(mini.models,models)
                    self.assertEqual(full.qualified_results,{})

    def test_missing_models_or_wrong_size_cannot_identify_mini(self):
        frame,teachers,true,_ = mini_scene(0,1.)
        mini = MiniHollowQuery.from_full(HollowGlyphEvidence.from_frame(frame,teachers[:2]))
        for key in true:
            self.assertFalse(support_mini(mini,key)['passed'])
        with self.assertRaises(ValueError):
            support_mini(mini,(3,96,320))

    def test_query_order_and_returned_proof_are_independent(self):
        frame,teachers,true,false = mini_scene(0,1.)
        full = HollowGlyphEvidence.from_frame(frame,teachers)
        a,b = MiniHollowQuery.from_full(full),MiniHollowQuery.from_full(full)
        keys = sorted(true|false)
        forward = {k:support_mini(a,k) for k in keys}
        reverse = {k:support_mini(b,k) for k in reversed(keys)}
        self.assertEqual(forward,reverse)
        proof = support_mini(a,keys[0]);proof['proof'].clear()
        self.assertEqual(support_mini(a,keys[0]),forward[keys[0]])


class HollowTerrainQueryTests(TestCase):
    def test_default_and_explicit_false_preserve_entire_proof(self):
        image,room,locators,_,_ = hollow_scene()
        original = [SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in locators]
        frame = SourceFrame(image,room)
        self.assertEqual(recover_source_hollow_glyphs(frame,original),
                         recover_source_hollow_glyphs(frame,original,terrain_neighbors=False))

    def test_mode_is_boolean_before_any_source_work(self):
        for value in (0,1,None,'true',[]):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'boolean'):
                recover_source_hollow_glyphs(None,(),terrain_neighbors=value)

    def test_expansion_is_from_original_terrain_not_outputs(self):
        image,room,_,_,_ = hollow_scene();frame = SourceFrame(image,room)
        original = [SimpleNamespace(type_id=3,x=96,y=96),SimpleNamespace(type_id=1,x=400,y=300)]
        keys = []
        def support(key):
            keys.append(key)
            return dict(passed=False,proof=[])
        evidence = SimpleNamespace(owned_models={0:True},support=support,
            gradients={},edges={},ink_edges={},raw_ink_edges={},owned_edges={},
            nominal_model_count=1,inset_model_count=0)
        with patch('scripts.source_hollow_pipeline.HollowGlyphEvidence.from_frame',return_value=evidence), \
             patch('scripts.source_hollow_pipeline.refit_source_hollow_phases',return_value=[]):
            proposed,_ = recover_source_hollow_glyphs(frame,original,terrain_neighbors=True)
        self.assertFalse(proposed)
        self.assertIn((3,400,268),keys)
        self.assertTrue(all(0 <= x <= 768 and 0 <= y <= 576 for _,x,y in keys))

    def test_extended_world_frame_never_waives_boundary_guard(self):
        frame = SimpleNamespace(room=Box(0,0,800,608),extent=Box(-4,0,808,608))
        original = [SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in ((7,400,300),(8,416,300))]
        proposed = {(3,400,268)}
        with patch('scripts.source_hollow_compounds.SourceObjectFrames',side_effect=AssertionError('Unqualified frame')):
            self.assertEqual(qualify_new_boundaries(frame,original,None,proposed),(proposed,[]))

    def test_one_mini_or_unqualified_mini_is_not_an_overlap_veto(self):
        original = [SimpleNamespace(type_id=7,x=96,y=96)]
        with patch('scripts.source_hollow_compounds.MiniHollowQuery.from_full',return_value=None):
            explanation = BoundaryExplanation(None,original,None)
        self.assertFalse(explanation.explain((3,96,96),dict(proof=[]))['abstain'])
        original.append(SimpleNamespace(type_id=8,x=112,y=96))
        with patch('scripts.source_hollow_compounds.MiniHollowQuery.from_full',return_value=None):
            explanation = BoundaryExplanation(None,original,None)
        explanation.mini_proofs = {(d.type_id,d.x,d.y):dict(passed=False,proof=[]) for d in original}
        self.assertFalse(explanation.explain((3,96,96),dict(proof=[]))['abstain'])
