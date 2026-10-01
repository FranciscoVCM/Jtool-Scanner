"""Supplementary terrain measurements must never relax strict map gates."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from jtool_scanner.benchmark import compare_jmaps, compare_solid_occupancy
from jtool_scanner.cli import main
from jtool_scanner.constants import (
    OBJ_BLOCK, OBJ_MINI_BLOCK, OBJ_KILLER_BLOCK, OBJ_SPIKE_UP, OBJ_PLATFORM,
)
from jtool_scanner.geometry import Box
from jtool_scanner.jmap import JMap, JMapObject


def block(x, y, type_id=OBJ_BLOCK):
    return JMapObject(x, y, type_id)


class SolidOccupancyTests(unittest.TestCase):
    def test_equivalent_overlapping_decompositions_keep_exact_errors(self):
        expected = JMap(objects=[block(0, 0), block(0, 16), block(0, 32)])
        detected = JMap(objects=[block(0, 0), block(0, 32)])
        area = compare_solid_occupancy(detected, expected)
        self.assertTrue(area['equivalent'])
        self.assertEqual(area['expected_pixels'], 32 * 64)
        self.assertEqual(area['intersection_over_union'], 1.0)
        self.assertEqual(compare_jmaps(detected, expected)['summary']['missed'], 1)

    def test_four_minis_equal_one_full_block_but_not_exact_objects(self):
        expected = JMap(objects=[block(8, 24)])
        detected = JMap(objects=[block(x, y, OBJ_MINI_BLOCK)
                                 for x in (8, 24) for y in (24, 40)])
        self.assertTrue(compare_solid_occupancy(detected, expected)['equivalent'])
        self.assertGreater(compare_jmaps(detected, expected)['summary']['exact_error_count'], 0)

    def test_duplicates_and_order_do_not_change_union(self):
        expected = JMap(objects=[block(0, 0), block(24, 24)])
        detected = JMap(objects=[block(24, 24), block(0, 0), block(0, 0)])
        self.assertTrue(compare_solid_occupancy(detected, expected)['equivalent'])

    def test_equal_counts_do_not_hide_a_shift_or_hole(self):
        expected = JMap(objects=[block(0, 0)])
        detected = JMap(objects=[block(8, 0)])
        area = compare_solid_occupancy(detected, expected)
        self.assertFalse(area['equivalent'])
        self.assertEqual(area['missing_pixels'], 8 * 32)
        self.assertEqual(area['extra_pixels'], 8 * 32)
        self.assertEqual(area['intersection_pixels'], 24 * 32)

    def test_600_capture_clips_bottom_and_608_retains_hidden_geometry(self):
        expected = JMap(objects=[block(0, 576)])
        detected = JMap(objects=[block(0, 576), block(32, 600)])
        self.assertTrue(compare_solid_occupancy(detected, expected, Box(0, 0, 800, 600))['equivalent'])
        normal = compare_solid_occupancy(detected, expected)
        self.assertFalse(normal['equivalent'])
        self.assertEqual(normal['extra_pixels'], 32 * 8)
        self.assertEqual(compare_solid_occupancy(expected, expected, Box(0, 0, 800, 600))['expected_pixels'], 32 * 24)

    def test_nonzero_viewport_clips_all_four_sides(self):
        view = Box(100, 100, 16, 16)
        for obj in [block(84, 84), block(100, 100), block(92, 92), block(108, 108)]:
            with self.subTest(origin=(obj.x, obj.y)):
                area = compare_solid_occupancy(JMap(objects=[obj]), JMap(), view)
                width = min(116, obj.x + 32) - max(100, obj.x)
                height = min(116, obj.y + 32) - max(100, obj.y)
                self.assertEqual(area['extra_pixels'], width * height)
        offscreen = JMap(objects=[block(-64, -64), block(116, 116)])
        self.assertTrue(compare_solid_occupancy(offscreen, JMap(), view)['equivalent'])

    def test_hazards_and_platforms_do_not_become_solid_block_truth(self):
        objects = [block(0, 0, t) for t in (OBJ_KILLER_BLOCK, OBJ_SPIKE_UP, OBJ_PLATFORM)]
        self.assertTrue(compare_solid_occupancy(JMap(objects=objects), JMap())['equivalent'])
        self.assertEqual(compare_solid_occupancy(JMap(), JMap())['intersection_over_union'], 1.0)

    def test_invalid_viewport_is_rejected(self):
        for view in (Box(0, 0, 0, 16), Box(0, 0, 16, -1)):
            with self.assertRaises(ValueError):
                compare_solid_occupancy(JMap(), JMap(), view)

    def test_cli_is_offline_and_strict_failure_survives_equivalent_area(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected, detected = root / 'expected.jmap', root / 'detected.jmap'
            JMap(objects=[block(0, 0), block(0, 16), block(0, 32)]).to_file(expected)
            JMap(objects=[block(0, 0), block(0, 32)]).to_file(detected)
            before = (expected.read_bytes(), detected.read_bytes())
            report = root / 'report.json'
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(['compare-maps', str(detected), str(expected), '--viewport', '0,0,800,600',
                             '--report-json', str(report), '--fail-on-error'])
            result = json.loads(report.read_text())
            self.assertEqual(code, 1)
            self.assertTrue(result['solid_occupancy']['equivalent'])
            self.assertEqual(result['summary']['missed'], 1)
            self.assertEqual(before, (expected.read_bytes(), detected.read_bytes()))
