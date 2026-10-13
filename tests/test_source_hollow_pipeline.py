"""Actual recovery caller preserves true joins, failed originals and metadata."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts.source_hollow_pipeline import recover_source_hollow_glyphs
from scripts.source_sampling import SourceFrame
from tests.test_source_hollow_glyphs import hollow_scene


class HollowPipelineTests(TestCase):
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
