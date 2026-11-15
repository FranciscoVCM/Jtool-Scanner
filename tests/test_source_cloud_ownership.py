from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner as sc
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.source_cloud_ownership import apply_late_clouds, proves_separated_cloud


class SourceCloudOwnershipTests(TestCase):
    def test_guarded_component_is_packet_only_and_does_not_rescan(self):
        image = RGBImage(800, 608, bytes(800 * 608 * 3))
        room, box = Box(0, 0, 800, 608), Box(106, 123, 20, 22)
        sink = []
        with patch.object(sc, "_cloud_warp_palettes", return_value=(("bright", sc._is_bright_cloud_candidate),)), \
             patch.object(sc, "_connected_components", return_value=[(box, list((x, y)
                 for y in range(123, 145) for x in range(106, 126)))]) as components, \
             patch.object(sc, "_is_filled_cloud_warp_metrics", side_effect=lambda **m: m["ring_share"] <= .15), \
             patch.object(sc, "_component_ring_predicate_share", return_value=.68), \
             patch.object(sc, "proves_separated_cloud", return_value=True) as proof, \
             patch.object(sc, "_filled_cloud_warp_shadow_is_background_like", return_value=False), \
             patch.object(sc, "_filled_cloud_warp_is_dense_spike_enclosure", return_value=False) as enclosure:
            self.assertEqual(sc._detect_filled_cloud_warps(image, room, 8), [])
            proof.assert_not_called()
            self.assertEqual(sc._detect_filled_cloud_warps(image, room, 8, late_cloud_sink=sink), [])
            self.assertEqual([m.type_id for m in sink], [21])
            self.assertEqual(components.call_count, 2)
            proof.assert_called_once()
            enclosure.return_value = True
            self.assertEqual(sc._detect_filled_cloud_warps(image, room, 8, late_cloud_sink=[]), [])
            self.assertEqual(components.call_count, 3)

    def test_late_consumer_explains_only_the_fully_false_body(self):
        room = Box(0, 0, 800, 608)
        marker = sc.Detection("warp_filled_cloud_bright", 21, 96, 112, .93, Box(104, 120, 16, 18))
        top = sc.Detection("block", 1, 96, 96, .5, Box(96, 96, 32, 32))
        lower = sc.Detection("block", 1, 96, 128, .5, Box(96, 128, 32, 32))
        spike = sc.Detection("spike_up", 3, 192, 96, .75, Box(192, 96, 32, 32))
        original = sc.ScanResult(800, 608, room, [top, lower, spike], source_grid=(25, 19), source_geometry=True)
        image = bytearray(b"\xe9" * (800 * 608 * 3))
        def paint(x0, y0, x1, y1, shade):
            for y in range(y0, y1):
                start = (800 * y + x0) * 3
                image[start:start + (x1 - x0) * 3] = bytes([shade]) * (x1 - x0) * 3
        paint(104, 120, 120, 138, 252)
        paint(96, 143, 128, 160, 55)
        def run(result=original):
            return apply_late_clouds(result, RGBImage(800, 608, bytes(image)), [marker],
                                     bright_pixel=sc._is_bright_cloud_candidate, warnings=lambda ds: [])
        self.assertEqual(run().detections, [lower, spike, marker])
        self.assertIs(run(replace(original, source_geometry=False)).detections, original.detections)
        duplicate = replace(original, detections=[*original.detections, marker])
        self.assertIs(run(duplicate), duplicate)
        paint(98, 102, 117, 105, 235)  # Low-contrast independent structure, not background.
        self.assertEqual(run().detections, [top, lower, spike, marker])

    def test_missing_original_coverage_abstains(self):
        image = RGBImage(800, 608, bytes(800 * 608 * 3))
        self.assertFalse(proves_separated_cloud(image, Box(-8, 0, 800, 608), Box(4, 4, 20, 22),
                                               [], 0, 0, bright_pixel=sc._is_bright_cloud_candidate))

    def test_selector_is_off_and_lattice_sink_belongs_only_to_original_consensus(self):
        self.assertFalse(sc._SOURCE_LATE_CLOUD_OWNERSHIP_ENABLED)
        room = Box(0, 0, 800, 608)
        image = RGBImage(800, 608, bytes(800 * 608 * 3))
        norm = sc._CaptureLatticeNormalization(room, sc._CaptureLatticeAxis(0, 800, 1, 1),
                                               sc._CaptureLatticeAxis(0, 608, 1, 1))
        result = sc.ScanResult(800, 608, room, [], source_grid=(25, 19))
        for consensus, source_mode in ((True, True), (False, True), (True, False)):
            with self.subTest(consensus=consensus, source_mode=source_mode), \
                 patch.object(sc, "_SOURCE_LATE_CLOUD_OWNERSHIP_ENABLED", True), \
                 patch.object(sc, "_capture_lattice_consensus_enabled", return_value=consensus), \
                 patch.object(sc, "_resample_capture_lattice_room", return_value=image), \
                 patch.object(sc, "_apply_source_geometry", return_value=result), \
                 patch.object(sc, "_recover_source_gravity_arrows", return_value=result), \
                 patch.object(sc, "scan_image", side_effect=[result, result]) as scanner:
                sc._scan_lattice_normalized_room(image, norm, grid_step=8, include_color_objects=True,
                                                 recognized_text=None, source_geometry=source_mode)
            self.assertEqual("_late_cloud_sink" in scanner.call_args_list[0].kwargs, consensus and source_mode)
            self.assertNotIn("_late_cloud_sink", scanner.call_args_list[1].kwargs)
