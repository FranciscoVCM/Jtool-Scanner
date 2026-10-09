"""Causal full-pose gates protect ambiguity, known solids and original objects."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_full_pose import refit_full_poses


class SourceFullPoseTests(TestCase):
    def setUp(self):
        self.image = RGBImage(800, 608, bytes(800*608*3))
        self.room = Box(0, 0, 800, 608)
        self.old, self.new = (1, 160, 160), (1, 176, 160)
        self.detections = [SimpleNamespace(type_id=1, x=160, y=160)]
        self.material = dict(accepted=[(176, 160), (176, 176), (192, 160), (192, 176)],
            selected_clusters=[0], cluster_centers=[dict(r=200, g=200, b=200), dict(r=0, g=0, b=0)],
            tip_votes={'1': 3}, background_back_votes={'1': 0})
        self.library = SimpleNamespace(anchors=[])

    def run_rule(self, supported=None, bg_valid=True, bg_prediction=(0, 0, 0), proposed=None):
        supported = {self.new[1:]} if supported is None else supported
        with patch('scripts.source_full_pose.SourceGlyphLibrary', return_value=self.library), \
             patch('scripts.source_full_pose.SourceBlockLibrary') as texture, \
             patch('scripts.source_full_pose.SourceLocalBackground') as bg:
            texture.return_value.teachers = [(256, 256), (320, 256), (384, 256)]
            texture.return_value.models = []
            texture.return_value.support.side_effect = lambda x, y: dict(passed=(x, y) in supported)
            bg.return_value.predict.return_value = dict(valid=bg_valid, prediction=bg_prediction)
            return refit_full_poses(self.image, self.room, self.detections,
                {self.old} if proposed is None else proposed, set(), self.material)

    def test_unique_positive_pose_and_source_empty_margin_can_refit(self):
        proposed, removed, diag = self.run_rule()
        self.assertIn(self.new, proposed)
        self.assertEqual(removed, {self.old})
        proof = diag['texture_pose_proofs'][0]
        self.assertTrue(proof['all_old_source_foreground_pixels_retained'])
        self.assertGreater(len(proof['visible_empty_source_patches']), 0)

    def test_retired_original_also_present_in_proposals_cannot_be_reintroduced(self):
        proposed, removed, _ = self.run_rule(proposed={self.old})
        self.assertEqual(removed, {self.old})
        self.assertNotIn(self.old, proposed)
        self.assertEqual(proposed, {self.new})

    def test_old_whole_frame_support_preserves_pose(self):
        proposed, removed, diag = self.run_rule(supported={self.old[1:], self.new[1:]})
        self.assertEqual(proposed, {self.old})
        self.assertFalse(removed)
        self.assertEqual(diag['texture_pose_proofs'], [])

    def test_unknown_or_failed_local_background_is_not_a_negative(self):
        for valid, prediction in ((False, (0, 0, 0)), (True, (255, 255, 255))):
            with self.subTest(valid=valid, prediction=prediction):
                proposed, removed, diag = self.run_rule(bg_valid=valid, bg_prediction=prediction)
                self.assertEqual(proposed, {self.old})
                self.assertFalse(removed)

    def test_missing_positive_whole32_match_abstains(self):
        proposed, removed, _ = self.run_rule(supported=set())
        self.assertEqual(proposed, {self.old})
        self.assertFalse(removed)

    def test_all_known_positive_pixels_must_survive(self):
        self.material['accepted'].append((160, 160))
        proposed, removed, _ = self.run_rule()
        self.assertEqual(proposed, {self.old})
        self.assertFalse(removed)

    def test_two_plausible_positive_poses_are_ambiguous(self):
        self.material['accepted'] = [(176, 160), (192, 160), (176, 144), (192, 144)]
        proposed, removed, diag = self.run_rule(supported={(176, 160), (176, 144)})
        self.assertEqual(proposed, {self.old})
        self.assertFalse(removed)
        self.assertEqual(diag['texture_pose_proofs'], [])

    def test_original_mini_preserved_new_duplicate_only_is_repacked(self):
        original_mini = (2, 176, 160)
        self.detections.append(SimpleNamespace(type_id=2, x=176, y=160))
        new_mini = (2, 192, 160)
        proposed, removed, diag = self.run_rule(proposed={self.old, original_mini, new_mini})
        self.assertIn(original_mini, proposed)
        self.assertNotIn(original_mini, removed)
        self.assertNotIn(new_mini, proposed)
        self.assertEqual(diag['only_new_mini_duplicates_removed'], [new_mini])

    def test_source_confirmed_glyph_margin_is_not_empty(self):
        self.library.anchors = [dict(key=(5, 144, 160), size=32)]
        proposed, removed, _ = self.run_rule()
        self.assertEqual(proposed, {self.old})
        self.assertFalse(removed)

    def test_nonterrain_anchor_overlap_and_non16_pose_are_protected(self):
        for x, anchor in ((160, True), (168, False)):
            self.detections = [SimpleNamespace(type_id=1, x=x, y=160)]
            if anchor:
                self.detections.append(SimpleNamespace(type_id=11, x=176, y=160))
            original = (1, x, 160)
            proposed, removed, diag = self.run_rule(proposed={original})
            self.assertEqual(proposed, {original})
            self.assertFalse(removed)

    def test_no_independent_roles_abstains_without_building_library(self):
        self.material['selected_clusters'] = []
        with patch('scripts.source_full_pose.SourceGlyphLibrary', side_effect=AssertionError('Not needed')):
            proposed, removed, diag = refit_full_poses(self.image, self.room, self.detections,
                {self.old}, set(), self.material)
        self.assertEqual(proposed, {self.old})
        self.assertFalse(removed)
        self.assertIn('texture_pose_abstention', diag)

    def test_inputs_and_original_teacher_poses_are_not_mutated(self):
        before = deepcopy(self.material)
        proposed = {self.old, (2, 192, 160)}
        rejected = set()
        with patch('scripts.source_full_pose.SourceGlyphLibrary', return_value=self.library), \
             patch('scripts.source_full_pose.SourceBlockLibrary') as texture, \
             patch('scripts.source_full_pose.SourceLocalBackground') as bg:
            texture.return_value.teachers, texture.return_value.models = [], []
            texture.return_value.support.side_effect = lambda x, y: dict(passed=(x, y) == self.new[1:])
            bg.return_value.predict.return_value = dict(valid=True, prediction=(0, 0, 0))
            refit_full_poses(self.image, self.room, self.detections, proposed, rejected, self.material)
            self.assertEqual(texture.call_args.args[1], {self.old[1:]})
        self.assertEqual(self.material, before)
        self.assertEqual(proposed, {self.old, (2, 192, 160)})
        self.assertEqual(rejected, set())
