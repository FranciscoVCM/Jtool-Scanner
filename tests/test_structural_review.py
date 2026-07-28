from __future__ import annotations

import unittest

from jtool_scanner.constants import (
    GRID_SIZE,
    OBJ_BLOCK,
    OBJ_SPIKE_DOWN,
    OBJ_SPIKE_UP,
)
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.scanner import (
    Detection,
    _align_unsupported_opposite_spike_pairs,
    structural_scan_warnings,
)


class StructuralReviewTests(unittest.TestCase):
    def test_unsupported_opposite_pair_uses_strong_room_phase(self) -> None:
        image_box = Box(0, 0, GRID_SIZE, GRID_SIZE)
        image = RGBImage(800, 608, bytes(800 * 608 * 3))
        room = Box(0, 0, 800, 608)
        consensus = [
            Detection("spike_up", OBJ_SPIKE_UP, x, 64, 0.9, image_box)
            for x in range(32, 288, 32)
        ]
        pair = [
            Detection("warm_component_spike_up", OBJ_SPIKE_UP, 544, 328, 0.9, image_box),
            Detection("warm_component_spike_down", OBJ_SPIKE_DOWN, 544, 360, 0.9, image_box),
        ]

        aligned = _align_unsupported_opposite_spike_pairs(
            [*consensus, *pair],
            [],
            image,
            room,
        )
        positions = {(item.x, item.y, item.type_id) for item in aligned}

        self.assertIn((544, 320, OBJ_SPIKE_UP), positions)
        self.assertIn((544, 352, OBJ_SPIKE_DOWN), positions)

    def test_structural_review_flags_unsupported_spike_without_reference(self) -> None:
        image_box = Box(0, 0, GRID_SIZE, GRID_SIZE)

        warnings = structural_scan_warnings(
            [
                Detection("spike_up", OBJ_SPIKE_UP, 96, 128, 0.9, image_box),
                Detection("block", OBJ_BLOCK, 320, 320, 0.9, image_box),
            ]
        )

        self.assertEqual(warnings[0]["code"], "unsupported_spike")
        self.assertEqual((warnings[0]["x"], warnings[0]["y"]), (96, 128))

    def test_mixed_grid_room_preserves_multiple_minority_phase_spikes(self) -> None:
        image_box = Box(0, 0, GRID_SIZE, GRID_SIZE)
        image = RGBImage(800, 608, bytes(800 * 608 * 3))
        room = Box(0, 0, 800, 608)
        consensus = [
            Detection("spike_up", OBJ_SPIKE_UP, x, 64, 0.9, image_box)
            for x in range(32, 288, 32)
        ]
        minority = [
            Detection("warm_component_spike_up", OBJ_SPIKE_UP, 544, 328, 0.9, image_box),
            Detection("warm_component_spike_down", OBJ_SPIKE_DOWN, 544, 360, 0.9, image_box),
            Detection("warm_component_spike_up", OBJ_SPIKE_UP, 640, 328, 0.9, image_box),
        ]

        aligned = _align_unsupported_opposite_spike_pairs(
            [*consensus, *minority],
            [],
            image,
            room,
        )
        positions = {(item.x, item.y, item.type_id) for item in aligned}

        self.assertIn((544, 328, OBJ_SPIKE_UP), positions)
        self.assertIn((544, 360, OBJ_SPIKE_DOWN), positions)


if __name__ == "__main__":
    unittest.main()
