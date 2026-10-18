"""Disabled consumer routing must not invent original provenance from pixels."""
import ast
from dataclasses import replace
import inspect
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage


class RepeatedIdentityConsumerTests(TestCase):
    def setUp(self):
        self.image = RGBImage(800, 608, bytes(800 * 608 * 3))
        self.room = Box(0, 0, 800, 608)
        self.profile = scanner._RepeatedTerrainProfile(frozenset(), frozenset(), 0, 3, 0.)

    def options(self, *, working=None, room=None, grid=(25, 19), mode=True,
                refits=True, profile='plain'):
        return scanner._source_repeated_identity_options(
            self.image if working is None else working,
            self.room if room is None else room, self.image, self.room, grid,
            source_geometry=mode, apply_shape_refits=refits,
            profile=self.profile if profile == 'plain' else profile)

    def test_default_consumer_is_disabled_without_frame_work(self):
        self.assertIs(scanner._SOURCE_REPEATED_IDENTITY_ENABLED, False)
        with patch('scripts.source_sampling.SourceFrame', side_effect=AssertionError('Disabled')):
            self.assertEqual(self.options(), {})

    def test_enabled_consumer_forwards_one_matching_original_frame(self):
        with patch.object(scanner, '_SOURCE_REPEATED_IDENTITY_ENABLED', True):
            options = self.options()
        self.assertIs(options['include_local_identity'], True)
        self.assertTrue(options['source_frame'].matches_source(self.image, self.room))
        self.assertEqual(options['source_frame'].extent, self.room)
        self.assertIs(options['source_frame'].original_snapshot().data, self.image.data)

    def test_standard_mode_bypasses_even_if_research_switch_is_enabled(self):
        with patch.object(scanner, '_SOURCE_REPEATED_IDENTITY_ENABLED', True), \
             patch('scripts.source_sampling.SourceFrame', side_effect=AssertionError('Standard')):
            self.assertEqual(self.options(mode=False), {})

    def test_normalized_inner_pass_bypasses_even_on_original_pixels(self):
        with patch.object(scanner, '_SOURCE_REPEATED_IDENTITY_ENABLED', True), \
             patch('scripts.source_sampling.SourceFrame', side_effect=AssertionError('Inner pass')):
            self.assertEqual(self.options(refits=False), {})

    def test_compact_unknown_or_other_grid_has_no_original_frame_claim(self):
        with patch.object(scanner, '_SOURCE_REPEATED_IDENTITY_ENABLED', True), \
             patch('scripts.source_sampling.SourceFrame', side_effect=AssertionError('Grid')):
            for grid in ((19, 13), (9, 9), None):
                with self.subTest(grid=grid):
                    self.assertEqual(self.options(grid=grid), {})

    def test_equal_bytes_in_another_wrapper_are_not_original_provenance(self):
        clone = RGBImage(self.image.width, self.image.height, self.image.data)
        self.assertEqual(clone.data, self.image.data)
        with patch.object(scanner, '_SOURCE_REPEATED_IDENTITY_ENABLED', True), \
             patch('scripts.source_sampling.SourceFrame', side_effect=AssertionError('Clone')):
            self.assertEqual(self.options(working=clone), {})

    def test_padded_or_resampled_working_raster_bypasses(self):
        other = RGBImage(608, 416, bytes(608 * 416 * 3))
        with patch.object(scanner, '_SOURCE_REPEATED_IDENTITY_ENABLED', True), \
             patch('scripts.source_sampling.SourceFrame', side_effect=AssertionError('Working view')):
            self.assertEqual(self.options(working=other), {})

    def test_changed_physical_crop_bypasses(self):
        with patch.object(scanner, '_SOURCE_REPEATED_IDENTITY_ENABLED', True), \
             patch('scripts.source_sampling.SourceFrame', side_effect=AssertionError('Crop')):
            self.assertEqual(self.options(room=Box(8, 0, 792, 608)), {})

    def test_no_profile_or_independent_strong_profiles_do_not_build_frame(self):
        with patch.object(scanner, '_SOURCE_REPEATED_IDENTITY_ENABLED', True), \
             patch('scripts.source_sampling.SourceFrame', side_effect=AssertionError('Independent proof')):
            for profile in (None, replace(self.profile, complementary_texture=True),
                            replace(self.profile, phase_free_texture=True)):
                with self.subTest(profile=profile):
                    self.assertEqual(self.options(profile=profile), {})

    def test_actual_early_call_forwards_exact_source_and_mode_without_late_binding(self):
        tree = ast.parse(inspect.getsource(scanner.scan_image))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == '_replace_repeated_terrain_geometry']
        self.assertEqual(len(calls), 2)
        early = next(c for c in calls if not any(k.arg == 'blocks_only' for k in c.keywords))
        late = next(c for c in calls if any(k.arg == 'blocks_only' for k in c.keywords))
        expanded = next(k.value for k in early.keywords if k.arg is None)
        self.assertEqual(expanded.func.id, '_source_repeated_identity_options')
        self.assertEqual([a.id for a in expanded.args],
                         ['image', 'box', 'source_image', 'source_box', 'normalized_grid'])
        self.assertEqual({k.arg: k.value.id for k in expanded.keywords},
                         dict(source_geometry='source_geometry', apply_shape_refits='_apply_shape_refits',
                              profile='learned_terrain'))
        self.assertFalse(any(k.arg is None or k.arg in ('include_local_identity', 'source_frame')
                             for k in late.keywords))
