"""Actual recovery caller preserves true joins, failed originals and metadata."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts.source_hollow_pipeline import recover_source_hollow_glyphs, respect_original_terrain_anchors
from scripts.source_sampling import SourceFrame
from tests.test_source_hollow_glyphs import hollow_scene


class HollowPipelineTests(TestCase):
    def test_two_real_nearby_tips_survive_real_rgb_evidence(self):
        from PIL import Image,ImageDraw
        from jtool_scanner.image import RGBImage
        from jtool_scanner.spike_shape import VERTICES
        from scripts.source_hollow_glyphs import HollowGlyphEvidence
        image,room,locators,_,_=hollow_scene()
        raster=Image.frombytes('RGB',(image.width,image.height),image.data)
        pen=ImageDraw.Draw(raster)
        old,new=(3,672,256),(3,680,256)
        for _,x,y in (old,new):
            poly=[(x+u,y+v) for u,v in VERTICES[3]]
            # Outline-only draws retain both real overlapping source sprites.
            pen.line(poly+[poly[0]],fill=(210,220,225),width=3)
        image=RGBImage(raster.width,raster.height,raster.tobytes())
        frame=SourceFrame(image,room)
        evidence=HollowGlyphEvidence.from_frame(frame,locators+[old])
        self.assertTrue(evidence.support(old)['passed'])
        self.assertTrue(evidence.support(new)['passed'])
        original=[SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in locators+[old]]
        original.append(SimpleNamespace(type_id=1,x=672,y=288))
        proposed,abstained=respect_original_terrain_anchors({new},original,evidence)
        self.assertEqual(proposed,{new})
        self.assertEqual(abstained,[])

    def test_anchor_arbitration_is_not_a_blanket_nearby_overlap_filter(self):
        image, room, _, _, _ = hollow_scene()
        frame = SourceFrame(image, room)
        original = [SimpleNamespace(type_id=3,x=96,y=96), SimpleNamespace(type_id=1,x=96,y=128)]
        model = dict(independent_teachers=((3,96,96),(3,192,96),(3,288,96)),
                     foreground=(210,220,225),background=(40,50,60))
        evidence = SimpleNamespace(frame=frame,models=[model],support=lambda k:dict(
            passed=True,proof=[dict(original_teachers=model['independent_teachers'])]))
        before=deepcopy(original)
        # Stronger attachment alone cannot suppress a new, independently visible
        # nearby tip. Here both source tip neighborhoods are foreground.
        from unittest.mock import patch
        with patch.object(frame.__class__,'original_pixel',return_value=model['foreground']):
            proposed,abstained=respect_original_terrain_anchors({(3,104,96)},original,evidence)
        self.assertEqual(proposed,{(3,104,96)})
        self.assertEqual(abstained,[])
        self.assertEqual(original,before)
        with patch.object(frame.__class__,'original_pixel',return_value=None):
            proposed,abstained=respect_original_terrain_anchors({(3,104,96)},original,evidence)
        self.assertEqual(proposed,{(3,104,96)})
        self.assertEqual(abstained,[])

    def test_anchor_arbitration_requires_same_original_source_model(self):
        image,room,_,_,_=hollow_scene();frame=SourceFrame(image,room)
        original=[SimpleNamespace(type_id=3,x=96,y=96),SimpleNamespace(type_id=1,x=96,y=128)]
        evidence=SimpleNamespace(frame=frame,models=[],support=lambda k:dict(passed=True,
            proof=[dict(original_teachers=((3,k[1],k[2]),))]))
        proposed,abstained=respect_original_terrain_anchors({(3,104,96)},original,evidence)
        self.assertEqual(proposed,{(3,104,96)})
        self.assertEqual(abstained,[])

    def test_real_touching_structure_recovered_without_deleting_wrong_original(self):
        image, room, locators, true, false = hollow_scene()
        frame = SourceFrame(image, room)
        detections = [SimpleNamespace(type_id=t, x=x, y=y, score=.3) for t, x, y in locators]
        # Wrong/displaced original cluster hypotheses locate the bounded search;
        # distant teachers alone cannot promise discovery anywhere in the room.
        detections += [SimpleNamespace(type_id=3, x=x-8, y=y, score=.2) for _, x, y in sorted(true)]
        detections += [SimpleNamespace(type_id=t, x=x, y=y, score=.7) for t, x, y in sorted(true)[:1]]
        original = deepcopy(detections)
        proposed, proof = recover_source_hollow_glyphs(frame, detections)
        self.assertEqual(detections, original)
        self.assertTrue(true - {(d.type_id, d.x, d.y) for d in detections} <= proposed)
        self.assertFalse(proposed & false)
        self.assertTrue(proof['no_existing_object_retirement'])

    def test_no_source_teachers_abstains_without_adding_full_scan(self):
        image, room, locators, _, _ = hollow_scene()
        frame = SourceFrame(image, room)
        detections = [SimpleNamespace(type_id=t, x=x, y=y) for t, x, y in locators[:2]]
        proposed, proof = recover_source_hollow_glyphs(frame, detections)
        self.assertEqual(proposed, set())
        self.assertEqual(proof['accepted'], [])

    def test_proposals_are_not_reintroduced_as_teachers(self):
        image, room, locators, _, _ = hollow_scene()
        frame = SourceFrame(image, room)
        detections = [SimpleNamespace(type_id=t, x=x, y=y) for t, x, y in locators]
        teacher = SimpleNamespace(owned_models={0: True}, gradients={}, edges={}, ink_edges={},
            raw_ink_edges={}, owned_edges={}, nominal_model_count=1, inset_model_count=0,
            support=lambda key: dict(passed=True, proof=['original-only']))
        with patch('scripts.source_hollow_pipeline.HollowGlyphEvidence.from_frame', return_value=teacher) as construct:
            proposed, _ = recover_source_hollow_glyphs(frame, detections)
        self.assertTrue(proposed)
        construct.assert_called_once_with(frame, locators)
        self.assertEqual(len(detections), 3)
