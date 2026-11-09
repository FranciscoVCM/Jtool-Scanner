from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.fruit_spike_evidence import FruitSupportBudget, _physical_taps, original_fruit_support_budget
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage


class FruitSpikeEvidenceTests(TestCase):
    room = Box(0, 0, 800, 608)

    def setUp(self):
        self.image = RGBImage(800, 608, bytes(800 * 608 * 3))

    def test_exact_taps_and_invalid_frames(self):
        taps = _physical_taps(self.image, self.room, 88, 104)
        self.assertEqual(len(set(taps)), 256)
        self.assertEqual((taps[0], taps[-1]), ((89, 105), (119, 135)))
        for room, x in ((self.room, -8), (self.room, 776), (Box(-1, 0, 800, 608), 88),
                        (Box(0, 0, 250, 200), 88)):
            self.assertIsNone(_physical_taps(self.image, room, x, 104))

    def test_exact_mask_and_warm_vote_floor(self):
        outline, _ = scanner._triangle_masks('up')
        for mask in ((False,) * 256, (True,) * 256, (False,)):
            with self.subTest(mask=mask[:1]), patch(
                'jtool_scanner.fruit_spike_evidence._held_sides',
                side_effect=AssertionError('No proof warrants side work'),
            ):
                self.assertIsNone(original_fruit_support_budget(
                    self.image, self.room, 88, 104, 3, {(89, 105)}, outline=outline, edge_mask=mask))

    def test_optimistic_score_or_either_held_side_protects_support(self):
        self.assertTrue(FruitSupportBudget(6, 9, .29, (3, 1)).withholds(.30))
        self.assertFalse(FruitSupportBudget(6, 9, .30, (0, 1)).withholds(.30))
        self.assertFalse(FruitSupportBudget(6, 9, .29, (0, 4)).withholds(.30))
        self.assertFalse(FruitSupportBudget(6, 9, .29, (4, 0)).withholds(.30))

    def test_only_exact_legacy_support_and_body_intersection_are_eligible(self):
        patch_features = scanner._PatchFeatures((False,) * 256, 0, 0, 0)
        cls = scanner._GeometryClass('spike_up', 3, .4)
        item = scanner.Detection('full_spike_support', 3, 88, 104, .4, Box(88, 104, 32, 32))
        retained = [replace(item, score=.45), replace(item, type_id=4), replace(item, kind='spike_up'),
                    replace(item, image_box=Box(56, 104, 32, 32))]
        proposals = [retained[0], item, *retained[1:]]
        ink = {(90, 110)}
        with patch.object(scanner, '_patch_features', return_value=patch_features), \
             patch.object(scanner, '_classify_full_spike', return_value=cls), \
             patch.object(scanner, 'original_fruit_support_budget',
                          return_value=FruitSupportBudget(6, 6, .2, (0, 0))) as evidence:
            kept = scanner._withhold_fruit_owned_support(self.image, self.room, proposals,
                                                         [(Box(90, 110, 12, 12), ink)])
        evidence.assert_called_once()
        self.assertEqual(evidence.call_args.args, (self.image, self.room, 88, 104, 3, ink))
        self.assertEqual(kept, retained)
        self.assertIs(proposals[1], item)

    def test_color_sink_contains_only_accepted_exact_component_pixels(self):
        body = Box(96, 104, 14, 14)
        points = [(x, y) for y in range(body.y, body.bottom) for x in range(body.x, body.right)
                  if (x, y) != (100, 110)]
        impostor = Box(300, 300, 16, 16)
        sink = []
        with patch.object(scanner, '_connected_components',
                          return_value=[(body, points), (impostor, [(300, 300)])]) as components, \
             patch.object(scanner, '_detect_outline_apples', return_value=[]):
            found = scanner._detect_apples(self.image, self.room, 8, [], fruit_bodies=sink)
        components.assert_called_once()
        self.assertEqual(len(found), 1)
        self.assertEqual(sink, [(body, set(points))])
        self.assertNotIn((100, 110), sink[0][1])

    def test_direct_caller_does_not_collect_on_standard_or_default_off(self):
        for enabled, source_mode in ((False, True), (True, False), (True, True)):
            with self.subTest(enabled=enabled, source_mode=source_mode), \
                 patch.object(scanner, '_SOURCE_FRUIT_SUPPORT_OWNERSHIP_ENABLED', enabled), \
                 patch.object(scanner, '_detect_saves', return_value=[]), \
                 patch.object(scanner, '_detect_warps', return_value=[]), \
                 patch.object(scanner, '_detect_color_objects', return_value=[]) as color, \
                 patch.object(scanner, '_detect_mini_blocks', return_value=[]), \
                 patch.object(scanner, '_detect_geometry', return_value=[]), \
                 patch.object(scanner, '_withhold_fruit_owned_support',
                              side_effect=AssertionError('No fruit body was collected')):
                scanner.scan_image(self.image, room_box=self.room, source_grid=(25, 19),
                    include_geometry=True, include_color_objects=True, source_geometry=source_mode,
                    _apply_shape_refits=False)
            self.assertEqual('fruit_bodies' in color.call_args.kwargs, enabled and source_mode)

    def test_only_original_consensus_pass_receives_the_handoff(self):
        norm = scanner._CaptureLatticeNormalization(self.room,
            scanner._CaptureLatticeAxis(0, 800, 1, 1), scanner._CaptureLatticeAxis(0, 608, 1, 1))
        blank = scanner.ScanResult(800, 608, self.room, [], source_grid=(25, 19))
        for consensus, source_mode in ((True, True), (False, True), (True, False)):
            with self.subTest(consensus=consensus, source_mode=source_mode), \
                 patch.object(scanner, '_SOURCE_FRUIT_SUPPORT_OWNERSHIP_ENABLED', True), \
                 patch.object(scanner, '_capture_lattice_consensus_enabled', return_value=consensus), \
                 patch.object(scanner, '_resample_capture_lattice_room', return_value=self.image), \
                 patch.object(scanner, 'scan_image', side_effect=[blank, blank]) as scan:
                scanner._scan_lattice_normalized_room(self.image, norm, grid_step=8, include_color_objects=True,
                    recognized_text=None, source_geometry=source_mode, _apply_shape_refits=False)
            self.assertEqual('_original_fruit_support' in scan.call_args_list[0].kwargs, consensus and source_mode)
            self.assertNotIn('_original_fruit_support', scan.call_args_list[1].kwargs)
