from __future__ import annotations

from pathlib import Path
import unittest

from jtool_scanner.constants import (
    OBJ_BLOCK,
    OBJ_MINI_BLOCK,
    OBJ_SAVE,
    OBJ_WARP,
)
from jtool_scanner.geometry import Box
from jtool_scanner.scanner import (
    FULL_SPIKE_TYPES,
    MINI_SPIKE_TYPES,
    _infer_source_grid,
    scan_png,
)


FIXTURES = Path("fixtures/regressions")


class UnseenScreenRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        options = {
            "grid_step": 8,
            "include_color_objects": True,
            "include_geometry": True,
            "enable_ocr": False,
        }
        cls.particle_room = scan_png(
            FIXTURES / "infinite-jump-particle-water.png",
            **options,
        )
        cls.brick_room = scan_png(
            FIXTURES / "brick-save-impostors.png",
            **options,
        )

    def test_particle_field_does_not_become_upper_room_geometry(self) -> None:
        geometry_types = {OBJ_BLOCK, *FULL_SPIKE_TYPES, *MINI_SPIKE_TYPES}
        upper = [
            detection
            for detection in self.particle_room.detections
            if detection.type_id in geometry_types and detection.y < 200
        ]

        self.assertEqual(upper, [])
        self.assertEqual(
            [(detection.kind, detection.x, detection.y)
             for detection in self.particle_room.detections
             if detection.type_id == OBJ_SAVE],
            [("save_outline", 736, 264)],
        )
        self.assertEqual(
            len([
                detection
                for detection in self.particle_room.detections
                if detection.type_id == OBJ_WARP
            ]),
            1,
        )

    def test_brick_tiles_do_not_become_miniblock_room_saves(self) -> None:
        saves = [
            detection
            for detection in self.brick_room.detections
            if detection.type_id == OBJ_SAVE
        ]

        self.assertEqual(
            [(detection.kind, detection.x, detection.y) for detection in saves],
            [("save", 480, 552)],
        )
        self.assertFalse(
            any(
                detection.type_id == OBJ_MINI_BLOCK
                for detection in self.brick_room.detections
            )
        )
        self.assertGreaterEqual(
            sum(
                detection.type_id == OBJ_BLOCK
                for detection in self.brick_room.detections
            ),
            100,
        )

    def test_known_room_profiles_are_inferred_without_user_input(self) -> None:
        self.assertEqual(_infer_source_grid(Box(0, 0, 1000, 760)), (25, 19))
        self.assertEqual(_infer_source_grid(Box(0, 0, 760, 520)), (19, 13))
        self.assertEqual(_infer_source_grid(Box(0, 0, 800, 480)), (20, 12))
        self.assertIsNone(_infer_source_grid(Box(0, 0, 1000, 500)))


if __name__ == "__main__":
    unittest.main()
