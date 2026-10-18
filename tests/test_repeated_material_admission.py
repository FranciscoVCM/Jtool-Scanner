"""Upstream new-proposal admission, never unsupported-as-empty map deletion."""
from copy import deepcopy
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_sampling import SourceFrame


class RepeatedMaterialAdmissionTests(TestCase):
    def setUp(self):
        self.image = RGBImage(800, 608, bytes(800 * 608 * 3))
        self.room = Box(0, 0, 800, 608)
        self.frame = SourceFrame(self.image, self.room)
        self.points = frozenset((x, 160) for x in range(96, 480, 32))
        cells = frozenset((x + dx, y + dy) for x, y in self.points for dx in (0, 16) for dy in (0, 16))
        self.profile = scanner._RepeatedTerrainProfile(cells, self.points, 0, 20, 1.)

    def block(self, x, y):
        return scanner.Detection('block', 1, x, y, .8, Box(x, y, 32, 32))

    def run_replacement(self, original, **kwargs):
        return scanner._replace_repeated_terrain_geometry(original, self.image, self.room,
            profile=self.profile, already_learned=True, **kwargs)

    def test_default_false_ablation_does_not_query_new_evidence(self):
        with patch('scripts.source_repeated_identity.repeated_material_support', side_effect=AssertionError('Unbound')):
            ordinary = self.run_replacement([])
            bypass = self.run_replacement([], include_local_identity=False)
        self.assertEqual(ordinary, bypass)
        self.assertTrue(ordinary[1])

    def test_flag_must_be_strict_boolean(self):
        for value in (None, 0, 1, 'true', []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'boolean'):
                self.run_replacement([], include_local_identity=value)

    def test_optin_requires_matching_original_frame(self):
        changed = RGBImage(800, 608, bytes([1]) * (800 * 608 * 3))
        for frame in (None, object(), SourceFrame(changed, self.room)):
            with self.subTest(frame=frame), self.assertRaisesRegex(ValueError, 'ORIGINAL source frame'):
                self.run_replacement([], include_local_identity=True, source_frame=frame)

    def test_only_new_profile_proposals_can_be_withheld(self):
        original = [self.block(96, 160), scanner.Detection('save', 12, 640, 400, .9, Box(640, 400, 32, 32))]
        before = deepcopy(original)
        proof = dict(unsupported_known=[(1, 96, 160), (1, 128, 160)])
        with patch('scripts.source_repeated_identity.repeated_material_support', return_value=proof) as observe:
            result, changed = self.run_replacement(original, include_local_identity=True, source_frame=self.frame)
        self.assertTrue(changed)
        keys = {(d.type_id, d.x, d.y) for d in result}
        self.assertIn((1, 96, 160), keys)
        self.assertNotIn((1, 128, 160), keys)
        self.assertIn(original[1], result)
        self.assertEqual(original, before)
        self.assertIs(observe.call_args.args[2], original)
        self.assertIs(observe.call_args.kwargs['candidate_points'], self.profile.full_blocks)
        self.assertIs(observe.call_args.kwargs['source_frame'], self.frame)

    def test_unadmitted_profile_cannot_replace_original_map_with_empty(self):
        original = [self.block(640, 320)]
        with patch('scripts.source_repeated_identity.repeated_material_support',
                   return_value=dict(unsupported_known=[(1, *p) for p in self.points])):
            result, changed = self.run_replacement(original, include_local_identity=True, source_frame=self.frame)
        self.assertFalse(changed)
        self.assertIs(result, original)

    def test_stronger_existing_profile_proofs_are_not_reclassified(self):
        for flag in ('complementary_texture', 'phase_free_texture'):
            with self.subTest(flag=flag):
                profile = replace(self.profile, **{flag: True})
                with patch('scripts.source_repeated_identity.repeated_material_support', side_effect=AssertionError('Independent proof')):
                    result, changed = scanner._replace_repeated_terrain_geometry([], self.image, self.room,
                        profile=profile, already_learned=True, include_local_identity=True, source_frame=self.frame)
                self.assertTrue(changed)
                self.assertEqual({(d.x, d.y) for d in result}, self.points)

    def test_real_unknown_context_abstains_instead_of_withholding(self):
        # One unknown edge member connects to the entire proposed strip.
        points = frozenset((x, 160) for x in range(0, 384, 32))
        profile = replace(self.profile, full_blocks=points)
        result, changed = scanner._replace_repeated_terrain_geometry([], self.image, self.room,
            profile=profile, already_learned=True, include_local_identity=True, source_frame=self.frame)
        self.assertTrue(changed)
        self.assertEqual({(d.x, d.y) for d in result}, points)

    def test_extended_source_frame_does_not_supply_false_empty_evidence(self):
        frame = SourceFrame(self.image, self.room, extent=Box(-8, 0, 816, 608), canonical=self.image)
        result, changed = self.run_replacement([], include_local_identity=True, source_frame=frame)
        self.assertTrue(changed)
        self.assertEqual({(d.x, d.y) for d in result}, self.points)

    def test_high_coverage_gate_does_not_query_or_reteach(self):
        original = [self.block(x, y) for x, y in self.points]
        with patch('scripts.source_repeated_identity.repeated_material_support', side_effect=AssertionError('No replacement')):
            result, changed = self.run_replacement(original, include_local_identity=True, source_frame=self.frame)
        self.assertFalse(changed)
        self.assertIs(result, original)
