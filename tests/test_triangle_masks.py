from __future__ import annotations

import random
from types import SimpleNamespace
import unittest
from unittest import mock

from jtool_scanner import scanner


def legacy_masks(direction: str) -> tuple[list[int], list[int]]:
    """Independent copy of the pre-cache algorithm, including index order."""
    sample = 16
    center = (sample - 1) / 2
    outline = []
    outside = []
    for sy in range(sample):
        for sx in range(sample):
            if direction == "up":
                side = abs(sx - center) * 2
                edge_dist = min(abs(sy - side), abs(sy - (sample - 1)))
                inside = sy >= side - 1
            elif direction == "down":
                side = (sample - 1) - abs(sx - center) * 2
                edge_dist = min(abs(sy - side), sy)
                inside = sy <= side + 1
            elif direction == "right":
                side = (sample - 1) - abs(sy - center) * 2
                edge_dist = min(abs(sx - side), sx)
                inside = sx <= side + 1
            else:
                side = abs(sy - center) * 2
                edge_dist = min(abs(sx - side), abs(sx - (sample - 1)))
                inside = sx >= side - 1
            pos = sy * sample + sx
            if edge_dist <= 1.15:
                outline.append(pos)
            elif not inside:
                outside.append(pos)
    return outline, outside


class TriangleMaskTests(unittest.TestCase):
    def test_all_ordered_indices_equal_legacy(self):
        for direction in ("up", "down", "right", "left", "", "diagonal", "UP"):
            with self.subTest(direction=direction):
                expected = legacy_masks(direction)
                actual = scanner._triangle_masks(direction)
                self.assertEqual(actual, tuple(tuple(mask) for mask in expected))
                for mask in actual:
                    self.assertEqual(len(mask), len(set(mask)))
                    self.assertTrue(all(0 <= index < 256 for index in mask))

    def test_masks_and_table_are_immutable(self):
        masks = scanner._triangle_masks("up")
        with self.assertRaises(TypeError):
            masks[0][0] = 0
        with self.assertRaises(TypeError):
            masks[0] = ()
        with self.assertRaises(TypeError):
            scanner._TRIANGLE_MASKS["up"] = ((), ())
        self.assertEqual(len(scanner._TRIANGLE_MASKS), 4)

    def test_repeated_lookup_reuses_masks_without_rebuilding(self):
        with mock.patch.object(scanner, "_build_triangle_masks", side_effect=AssertionError):
            for direction in ("up", "down", "right", "left"):
                first = scanner._triangle_masks(direction)
                for _ in range(10):
                    self.assertIs(scanner._triangle_masks(direction), first)
            self.assertIs(scanner._triangle_masks("unknown"), scanner._triangle_masks("left"))

    def test_scores_equal_legacy_for_every_pixel_and_random_edge_masks(self):
        rng = random.Random(108)
        edge_masks = [[index == selected for index in range(256)] for selected in range(256)]
        edge_masks += [[False] * 256, [True] * 256]
        edge_masks += [[rng.random() < density for _ in range(256)]
                       for density in (0.05, 0.25, 0.5, 0.75, 0.95) for _ in range(12)]
        for direction in ("up", "down", "right", "left", "unknown"):
            outline, outside = legacy_masks(direction)
            for mask in edge_masks:
                patch = SimpleNamespace(edge_mask=mask, edge_density=sum(mask) / 256)
                outline_hits = sum(1 for pos in outline if mask[pos]) / len(outline)
                outside_hits = sum(1 for pos in outside if mask[pos]) / max(1, len(outside))
                expected = (outline_hits * 0.78 + patch.edge_density * 0.38 - outside_hits * 0.18,
                            outline_hits - outside_hits)
                self.assertEqual(scanner._triangle_direction_score(patch, direction), expected)


if __name__ == "__main__":
    unittest.main()
