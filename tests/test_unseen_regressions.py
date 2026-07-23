from __future__ import annotations

from pathlib import Path
import unittest

from jtool_scanner.constants import (
    GRID_SIZE,
    OBJ_APPLE,
    OBJ_BLOCK,
    OBJ_MINI_BLOCK,
    OBJ_PLATFORM,
    OBJ_SAVE,
    OBJ_SPIKE_DOWN,
    OBJ_SPIKE_LEFT,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_UP,
    OBJ_WARP,
    OBJ_WATER_2,
    ROOM_HEIGHT,
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
        cls.brick_room_rescaled = scan_png(
            FIXTURES / "brick-focused-source-rescaled.png",
            **options,
        )
        cls.brick_room_exact = scan_png(
            FIXTURES / "brick-focused-source.png",
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
            140,
        )
        self.assertLessEqual(
            sum(
                detection.type_id == OBJ_BLOCK
                for detection in self.brick_room.detections
            ),
            170,
        )
        self.assertFalse(
            any(
                detection.type_id in MINI_SPIKE_TYPES
                for detection in self.brick_room.detections
            )
        )
        self.assertFalse(
            any(
                detection.type_id == OBJ_APPLE
                for detection in self.brick_room.detections
            )
        )
        self.assertGreaterEqual(
            sum(
                detection.type_id == OBJ_WATER_2
                for detection in self.brick_room.detections
            ),
            25,
        )
        full_spikes = sum(
            detection.type_id in FULL_SPIKE_TYPES
            for detection in self.brick_room.detections
        )
        self.assertGreaterEqual(full_spikes, 70)
        self.assertLessEqual(full_spikes, 100)
        self.assertLessEqual(len(self.brick_room.detections), 300)
        self.assertEqual(
            [
                (detection.x, detection.y)
                for detection in self.brick_room.detections
                if detection.kind == "water_2_half_width"
            ],
            [(304, 256)],
        )

    def test_known_room_profiles_are_inferred_without_user_input(self) -> None:
        self.assertEqual(_infer_source_grid(Box(0, 0, 1000, 760)), (25, 19))
        self.assertEqual(_infer_source_grid(Box(0, 0, 760, 520)), (19, 13))
        self.assertEqual(_infer_source_grid(Box(0, 0, 800, 480)), (20, 12))
        self.assertIsNone(_infer_source_grid(Box(0, 0, 1000, 500)))

    def test_rescaled_brick_room_keeps_structural_geometry(self) -> None:
        detections = self.brick_room_rescaled.detections
        self.assertEqual(
            [
                (detection.kind, detection.x, detection.y)
                for detection in detections
                if detection.type_id == OBJ_SAVE
            ],
            [("save", 480, 560)],
        )
        self.assertFalse(
            any(
                detection.type_id in {OBJ_MINI_BLOCK, *MINI_SPIKE_TYPES}
                for detection in detections
            )
        )
        self.assertLessEqual(len(detections), 290)
        self.assertTrue(
            150
            <= sum(detection.type_id == OBJ_BLOCK for detection in detections)
            <= 175
        )
        self.assertTrue(
            60
            <= sum(detection.type_id in FULL_SPIKE_TYPES for detection in detections)
            <= 90
        )
        self.assertEqual(
            [
                (detection.x, detection.y)
                for detection in detections
                if detection.kind == "water_2_half_width"
            ],
            [(304, 256)],
        )

    def test_exact_brick_room_reconstructs_visible_silhouettes(self) -> None:
        detections = self.brick_room_exact.detections
        self.assertEqual(
            sum(detection.type_id == OBJ_BLOCK for detection in detections),
            163,
        )
        self.assertEqual(
            sum(detection.type_id in FULL_SPIKE_TYPES for detection in detections),
            73,
        )
        component_spikes = [
            detection
            for detection in detections
            if detection.kind.startswith("warm_component_spike_")
        ]
        self.assertTrue(
            all(
                detection.x % 16 == 0
                for detection in component_spikes
                if detection.type_id in {OBJ_SPIKE_UP, OBJ_SPIKE_DOWN}
            )
        )
        self.assertTrue(
            all(
                detection.y % 16 == 0
                for detection in component_spikes
                if detection.type_id in {OBJ_SPIKE_RIGHT, OBJ_SPIKE_LEFT}
            )
        )
        self.assertEqual(
            sum(detection.type_id == OBJ_WATER_2 for detection in detections),
            32,
        )
        self.assertEqual(
            [
                (detection.kind, detection.x, detection.y)
                for detection in detections
                if detection.type_id == OBJ_SAVE
            ],
            [("save", 480, 552)],
        )
        self.assertFalse(
            any(
                detection.type_id
                in {OBJ_MINI_BLOCK, OBJ_PLATFORM, OBJ_APPLE, *MINI_SPIKE_TYPES}
                for detection in detections
            )
        )
        self.assertEqual(
            [
                (detection.x, detection.y)
                for detection in detections
                if detection.kind == "water_2_half_width"
            ],
            [(304, 256)],
        )
        self.assertTrue(
            any(
                detection.type_id == OBJ_BLOCK and detection.y == 584
                for detection in detections
            )
        )
        self.assertGreater(
            sum(
                detection.type_id == OBJ_BLOCK and detection.y == 584
                for detection in detections
            ),
            sum(
                detection.type_id == OBJ_BLOCK
                and detection.y == ROOM_HEIGHT - GRID_SIZE
                for detection in detections
            ),
        )


if __name__ == "__main__":
    unittest.main()
