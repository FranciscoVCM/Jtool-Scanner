from __future__ import annotations

from pathlib import Path
import unittest

from jtool_scanner.constants import (
    GRID_SIZE,
    OBJ_APPLE,
    OBJ_BLOCK,
    OBJ_JUMP_REFRESHER,
    OBJ_MINI_BLOCK,
    OBJ_MINI_SPIKE_DOWN,
    OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_UP,
    OBJ_PLATFORM,
    OBJ_SAVE,
    OBJ_SPIKE_DOWN,
    OBJ_SPIKE_LEFT,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_UP,
    OBJ_WARP,
    OBJ_WATER_2,
    OBJ_WALLJUMP_LEFT,
    OBJ_WALLJUMP_RIGHT,
    ROOM_HEIGHT,
)
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.image import load_png
from jtool_scanner.evaluation import evaluate_scan
from jtool_scanner.jmap import JMap
from jtool_scanner.scanner import (
    Detection,
    FULL_SPIKE_TYPES,
    MINI_SPIKE_TYPES,
    _detect_outlined_terrain_saves,
    _detect_outlined_terrain_spikes,
    _dark_save_header_is_label_like,
    _align_unsupported_opposite_spike_pairs,
    _choose_component_spike_candidate,
    _image_box_to_jtool_center,
    _infer_source_grid,
    _looks_like_outlined_terrain_room,
    _outlined_terrain_cell_stats,
    _reorient_unsupported_spikes,
    _realign_warm_component_spike_phase,
    _reconcile_terrain_markers,
    _separate_overlapping_opposite_spikes,
    _warm_room_allows_bottom_block_offset,
    detect_room_box,
    scan_png,
    structural_scan_warnings,
)


FIXTURES = Path("fixtures/regressions")
UNSEEN_FIXTURES = FIXTURES / "unseen-rooms"


class OutlinedTerrainRegressionTests(unittest.TestCase):
    def test_neon_rooms_use_hue_independent_terrain_geometry(self) -> None:
        fixture_dir = UNSEEN_FIXTURES / "cn3-neon"
        expected = {
            "07": (103, 48, 4),
            "08": (83, 57, 3),
            "09": (85, 63, 3),
        }

        for floor, expected_counts in expected.items():
            with self.subTest(floor=floor):
                image = load_png(fixture_dir / f"floor-{floor}-source.png")
                room = detect_room_box(image)
                self.assertTrue(_looks_like_outlined_terrain_room(image, room))
                block_positions = _outlined_terrain_cell_stats(image, room)[3]
                spikes = _detect_outlined_terrain_spikes(
                    image,
                    room,
                    block_positions,
                )
                saves = _detect_outlined_terrain_saves(image, room)
                self.assertEqual(
                    (len(block_positions), len(spikes), len(saves)),
                    expected_counts,
                )
                self.assertTrue(
                    all(
                        detection.type_id in FULL_SPIKE_TYPES
                        for detection in spikes
                    )
                )


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
            UNSEEN_FIXTURES / "ftfa" / "screen-4-source.png",
            **options,
        )
        cls.brick_room_cropped = scan_png(
            UNSEEN_FIXTURES / "ftfa" / "screen-4-cropped-source.png",
            **options,
        )
        cls.brick_room_truth = JMap.from_file(
            UNSEEN_FIXTURES / "ftfa" / "screen-4.jmap"
        )
        cls.ftfa_room_01 = scan_png(
            UNSEEN_FIXTURES / "ftfa" / "screen-1-source.png",
            **options,
        )
        cls.lap_first = scan_png(
            UNSEEN_FIXTURES / "lap-around" / "screen-01-source.png",
            **options,
        )
        cls.lap_active_save = scan_png(
            UNSEEN_FIXTURES / "lap-around" / "screen-11-source.png",
            **options,
        )
        cls.lap_bottom_edge = scan_png(
            UNSEEN_FIXTURES / "lap-around" / "screen-06-source.png",
            **options,
        )
        cls.lap_room_08 = scan_png(
            UNSEEN_FIXTURES / "lap-around" / "screen-08-source.png",
            **options,
        )
        cls.lap_room_09 = scan_png(
            UNSEEN_FIXTURES / "lap-around" / "screen-09-source.png",
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
            0,
        )
        self.assertFalse(
            any(
                detection.type_id == OBJ_JUMP_REFRESHER
                for detection in self.particle_room.detections
            )
        )
        full_spikes = [
            detection
            for detection in self.particle_room.detections
            if detection.type_id in FULL_SPIKE_TYPES
        ]
        self.assertTrue(45 <= len(full_spikes) <= 65)
        blocks = [
            detection
            for detection in self.particle_room.detections
            if detection.type_id == OBJ_BLOCK
        ]
        self.assertLessEqual(
            max(
                self._overlap_area(spike, block)
                for spike in full_spikes
                for block in blocks
            ),
            GRID_SIZE * 16,
        )

    def test_terrain_save_prefers_exact_support_cell_over_partial_overlap(self) -> None:
        image = load_png(UNSEEN_FIXTURES / "ftfa" / "screen-2-source.png")
        room = detect_room_box(image)
        marker = Detection(
            "save",
            OBJ_SAVE,
            120,
            560,
            0.9,
            Box(176, 759, 24, 22),
        )
        # The old support score gives both x=120 and x=128 a full 32px
        # support because x=120 straddles these neighboring cells.  The
        # canonical JTool anchor is the exact x=128 support cell.
        blocks = [
            Detection("warm_terrain_block", OBJ_BLOCK, 96, 576, 0.9, Box(0, 0, 32, 32)),
            Detection("warm_terrain_block", OBJ_BLOCK, 128, 576, 0.9, Box(0, 0, 32, 32)),
        ]

        reconciled, _ = _reconcile_terrain_markers(
            [marker],
            blocks,
            image,
            room,
        )

        saves = [detection for detection in reconciled if detection.type_id == OBJ_SAVE]
        self.assertEqual([(detection.x, detection.y) for detection in saves], [(128, 544)])

    def test_bright_outlined_room_reanchors_save_after_late_terrain_cells(self) -> None:
        result = scan_png(
            Path("fixtures") / "block_spike" / "irkara-89-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        saves = [
            detection
            for detection in result.detections
            if detection.type_id == OBJ_SAVE
        ]
        self.assertEqual([(save.x, save.y) for save in saves], [(352, 544)])
        platforms = [
            detection
            for detection in result.detections
            if detection.type_id == OBJ_PLATFORM
        ]
        self.assertEqual(
            [(platform.x, platform.y) for platform in platforms],
            [(704, 288)],
        )
        walljumps = [
            detection
            for detection in result.detections
            if detection.type_id in (16, 17)
        ]
        self.assertEqual(
            sorted((detection.x, detection.y, detection.type_id) for detection in walljumps),
            [
                (0, 112, 16),
                (0, 144, 16),
                (256, 512, 17),
                (336, 272, 17),
                (336, 304, 17),
                (416, 128, 16),
                (416, 544, 16),
                (416, 576, 16),
                (640, 376, 16),
            ],
        )

    def test_dark_relative_platform_recovers_partially_scaled_bar(self) -> None:
        result = scan_png(
            Path("fixtures") / "block_spike" / "k3-ex-hades-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        platforms = [
            detection
            for detection in result.detections
            if detection.type_id == OBJ_PLATFORM
        ]
        self.assertEqual(
            sorted((platform.x, platform.y) for platform in platforms),
            [(144, 448), (512, 336)],
        )

    def test_dark_sparse_outline_rooms_reject_platform_edge_impostors(self) -> None:
        options = {
            "grid_step": 8,
            "include_color_objects": True,
            "include_geometry": True,
            "enable_ocr": False,
        }
        for name in ("irkara-49-game.png", "irkara-49-warp-game.png"):
            with self.subTest(name=name):
                result = scan_png(Path("fixtures") / "irkara" / name, **options)
                self.assertEqual(
                    [
                        detection
                        for detection in result.detections
                        if detection.type_id == OBJ_PLATFORM
                    ],
                    [],
                )
        control = scan_png(
            Path("fixtures") / "irkara" / "irkara-71-game.png",
            **options,
        )
        self.assertEqual(
            sorted(
                (detection.x, detection.y)
                for detection in control.detections
                if detection.type_id == OBJ_PLATFORM
            ),
            [(32, 480), (64, 128), (384, 288), (544, 128), (736, 352)],
        )

    def test_terrain_vine_phase_aligns_irkara51_supported_column(self) -> None:
        result = scan_png(
            Path("fixtures") / "irkara" / "irkara-51-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        walljumps = {
            (detection.x, detection.y, detection.type_id)
            for detection in result.detections
            if detection.type_id in (16, 17)
        }
        self.assertIn((224, 128, 17), walljumps)
        self.assertIn((672, 400, 16), walljumps)
        full_spikes = {
            (detection.x, detection.y, detection.type_id)
            for detection in result.detections
            if detection.type_id in FULL_SPIKE_TYPES
        }
        # In this green/white tileset, several 32px spikes are exposed as two
        # coherent 16px halves.  The paired-silhouette recovery must retain
        # those full objects while leaving genuine mini-spikes alone.
        self.assertTrue(
            {
                (608, 96, OBJ_SPIKE_RIGHT),
                (336, 112, OBJ_SPIKE_RIGHT),
                (64, 32, OBJ_SPIKE_DOWN),
                (576, 192, OBJ_SPIKE_DOWN),
            }.issubset(full_spikes)
        )
        mini_spikes = {
            (detection.x, detection.y, detection.type_id)
            for detection in result.detections
            if detection.type_id in MINI_SPIKE_TYPES
        }
        self.assertIn((544, 32, OBJ_MINI_SPIKE_DOWN), mini_spikes)
        self.assertNotIn((608, 96, OBJ_MINI_SPIKE_RIGHT), mini_spikes)

    def test_late_mini_spike_recovery_handles_split_palette_silhouettes(self) -> None:
        result = scan_png(
            Path("fixtures") / "irkara" / "irkara-52-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        mini_spikes = {
            (detection.x, detection.y, detection.type_id)
            for detection in result.detections
            if detection.type_id in MINI_SPIKE_TYPES
        }
        self.assertTrue(
            {
                (80, 80, OBJ_MINI_SPIKE_DOWN),
                (144, 80, OBJ_MINI_SPIKE_DOWN),
                (480, 192, OBJ_MINI_SPIKE_RIGHT),
                (736, 256, OBJ_MINI_SPIKE_RIGHT),
                (736, 432, OBJ_MINI_SPIKE_RIGHT),
                (80, 64, OBJ_MINI_SPIKE_UP),
                (240, 528, OBJ_MINI_SPIKE_UP),
            }.issubset(mini_spikes)
        )
        self.assertNotIn((320, 448, OBJ_MINI_SPIKE_DOWN), mini_spikes)
        self.assertNotIn((336, 448, OBJ_MINI_SPIKE_DOWN), mini_spikes)
        self.assertNotIn((624, 480, OBJ_MINI_SPIKE_DOWN), mini_spikes)
        self.assertNotIn((640, 480, OBJ_MINI_SPIKE_DOWN), mini_spikes)

    def test_walljump_phase_recovery_centers_split_unknown_tileset_vines(self) -> None:
        result = scan_png(
            Path("fixtures") / "irkara" / "irkara-52-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        walljumps = {
            (detection.x, detection.y, detection.type_id)
            for detection in result.detections
            if detection.type_id in (OBJ_WALLJUMP_LEFT, OBJ_WALLJUMP_RIGHT)
        }
        self.assertEqual(
            walljumps,
            {
                (112, 528, OBJ_WALLJUMP_RIGHT),
                (16, 416, OBJ_WALLJUMP_RIGHT),
                (272, 320, OBJ_WALLJUMP_LEFT),
            },
        )

    def test_clipped_walljump_phase_aliases_use_jtool_edge_origin(self) -> None:
        result = scan_png(
            Path("fixtures") / "block_spike" / "cn3-18-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        walljumps = [
            detection
            for detection in result.detections
            if detection.type_id in (16, 17)
        ]
        self.assertEqual(
            sorted((detection.x, detection.y, detection.type_id) for detection in walljumps),
            [(-16, 336, 16), (-16, 368, 16), (-16, 416, 16), (-16, 448, 16)],
        )
        saves = [
            detection
            for detection in result.detections
            if detection.type_id == OBJ_SAVE
        ]
        self.assertEqual(
            sorted((save.x, save.y) for save in saves),
            [(224, 80), (384, 256), (768, 376)],
        )

    def test_brick_tiles_do_not_become_miniblock_room_saves(self) -> None:
        saves = [
            detection
            for detection in self.brick_room.detections
            if detection.type_id == OBJ_SAVE
        ]

        self.assertEqual(
            [(detection.kind, detection.x, detection.y) for detection in saves],
            [("save_terrain_aligned", 480, 544)],
        )
        self.assertFalse(
            any(
                detection.type_id == OBJ_MINI_BLOCK
                for detection in self.brick_room.detections
            )
        )
        block_count = sum(
            detection.type_id == OBJ_BLOCK
            for detection in self.brick_room.detections
        )
        self.assertTrue(125 <= block_count <= 145)
        self.assertEqual(
            sum(
                detection.type_id in MINI_SPIKE_TYPES
                for detection in self.brick_room.detections
            ),
            2,
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
            [(288, 256)],
        )

    def test_known_room_profiles_are_inferred_without_user_input(self) -> None:
        self.assertEqual(_infer_source_grid(Box(0, 0, 1000, 760)), (25, 19))
        self.assertEqual(_infer_source_grid(Box(0, 0, 760, 520)), (19, 13))
        self.assertEqual(_infer_source_grid(Box(0, 0, 800, 480)), (20, 12))
        self.assertIsNone(_infer_source_grid(Box(0, 0, 1000, 500)))

    def test_bottom_crop_uses_the_room_boundary_lattice(self) -> None:
        framed_top = {(x, 0) for x in range(0, 448, GRID_SIZE)}
        sparse_top = {(x, 0) for x in range(0, 192, GRID_SIZE)}

        self.assertFalse(_warm_room_allows_bottom_block_offset(framed_top))
        self.assertTrue(_warm_room_allows_bottom_block_offset(sparse_top))

    def test_bottom_clipped_up_spike_run_is_kept_in_the_last_cell(self) -> None:
        bottom_up_spikes = {
            detection.x
            for detection in self.lap_bottom_edge.detections
            if detection.type_id == OBJ_SPIKE_UP
            and detection.y == ROOM_HEIGHT - GRID_SIZE
        }

        self.assertTrue({32, 64, 96, 128, 160} <= bottom_up_spikes)

    def test_supported_spike_direction_wins_when_shape_is_plausible(self) -> None:
        candidates = [
            (0, 1.4, "up", 96, 64),
            (32, 0.4, "right", 104, 64),
            (0, -0.4, "left", 88, 64),
            (0, -1.4, "down", 96, 72),
        ]

        chosen = _choose_component_spike_candidate(
            candidates,
            {"up": 1.4, "right": 0.4, "left": -0.4, "down": -1.4},
        )

        self.assertEqual(chosen[2], "right")

    def test_terrain_resolves_an_ambiguous_spike_shape(self) -> None:
        candidates = [
            (0, 0.24, "up", 96, 64),
            (32, 0.20, "right", 104, 64),
            (0, -0.20, "left", 88, 64),
            (0, -0.24, "down", 96, 72),
        ]

        chosen = _choose_component_spike_candidate(
            candidates,
            {"up": 0.24, "right": 0.20, "left": -0.20, "down": -0.24},
        )

        self.assertEqual(chosen[2], "right")

    def test_rescaled_brick_room_keeps_structural_geometry(self) -> None:
        detections = self.brick_room_rescaled.detections
        self.assertEqual(
            [
                (detection.kind, detection.x, detection.y)
                for detection in detections
                if detection.type_id == OBJ_SAVE
            ],
            [("save_terrain_aligned", 480, 544)],
        )
        self.assertFalse(
            any(detection.type_id == OBJ_MINI_BLOCK for detection in detections)
        )
        self.assertEqual(
            sum(
                detection.type_id in MINI_SPIKE_TYPES
                for detection in detections
            ),
            2,
        )
        self.assertLessEqual(len(detections), 290)
        self.assertTrue(
            125
            <= sum(detection.type_id == OBJ_BLOCK for detection in detections)
            <= 145
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
            [(288, 256)],
        )

    def test_exact_brick_room_reconstructs_visible_silhouettes(self) -> None:
        detections = self.brick_room_exact.detections
        self.assertEqual(
            sum(detection.type_id == OBJ_BLOCK for detection in detections),
            138,
        )
        self.assertEqual(
            sum(detection.type_id in FULL_SPIKE_TYPES for detection in detections),
            76,
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
            [("save_terrain_aligned", 480, 544)],
        )
        self.assertFalse(
            any(
                detection.type_id
                in {OBJ_MINI_BLOCK, OBJ_PLATFORM, OBJ_APPLE}
                for detection in detections
            )
        )
        self.assertEqual(
            sum(
                detection.type_id in MINI_SPIKE_TYPES
                for detection in detections
            ),
            2,
        )
        self.assertEqual(
            [
                (detection.x, detection.y)
                for detection in detections
            if detection.kind == "water_2_half_width"
            ],
            [(288, 256)],
        )
        blocks = [
            detection
            for detection in detections
            if detection.type_id == OBJ_BLOCK
        ]
        spikes = [
            detection
            for detection in detections
            if detection.type_id in FULL_SPIKE_TYPES
        ]
        overlaps = [
            max(
                0,
                min(spike.x + GRID_SIZE, block.x + GRID_SIZE)
                - max(spike.x, block.x),
            )
            * max(
                0,
                min(spike.y + GRID_SIZE, block.y + GRID_SIZE)
                - max(spike.y, block.y),
            )
            for spike in spikes
            for block in blocks
        ]
        self.assertEqual(max(overlaps), 0)
        self.assertTrue(
            any(
                detection.type_id == OBJ_BLOCK
                and detection.y == ROOM_HEIGHT - GRID_SIZE
                for detection in detections
            )
        )
        self.assertFalse(
            any(
                detection.type_id == OBJ_BLOCK and detection.y == 584
                for detection in detections
            )
        )

    def test_exact_brick_room_matches_the_hand_authored_jmap(self) -> None:
        evaluation = evaluate_scan(
            "ftfa-screen-4",
            self.brick_room_exact.detections,
            self.brick_room_truth,
            tolerance=24,
        )

        self.assertEqual(evaluation.matched_saves, evaluation.truth_saves)
        self.assertEqual(evaluation.matched_water, evaluation.truth_water)
        self.assertEqual(
            evaluation.matched_blocks,
            evaluation.truth_blocks,
        )
        self.assertEqual(
            evaluation.matched_full_spikes,
            evaluation.truth_full_spikes,
        )
        self.assertEqual(
            evaluation.matched_mini_spikes,
            evaluation.truth_mini_spikes,
        )
        self.assertLessEqual(evaluation.detected_blocks, 165)
        self.assertLessEqual(evaluation.detected_full_spikes, 76)
        self.assertEqual(evaluation.detected_mini_spikes, 2)

    def test_exact_brick_room_preserves_corrected_lower_spike_landmarks(self) -> None:
        spikes = {
            (detection.type_id, detection.x, detection.y)
            for detection in self.brick_room_exact.detections
            if detection.type_id in FULL_SPIKE_TYPES
        }

        self.assertIn((OBJ_SPIKE_LEFT, 32, 544), spikes)
        self.assertIn((OBJ_SPIKE_LEFT, 128, 512), spikes)
        self.assertIn((OBJ_SPIKE_UP, 240, 352), spikes)
        self.assertIn((OBJ_SPIKE_LEFT, 448, 384), spikes)
        self.assertIn((OBJ_SPIKE_LEFT, 208, 384), spikes)
        self.assertNotIn((OBJ_SPIKE_DOWN, 208, 384), spikes)
        self.assertNotIn((OBJ_SPIKE_UP, 240, 360), spikes)

    def test_cropped_brick_room_preserves_spike_geometry_phase(self) -> None:
        spikes = {
            (detection.type_id, detection.x, detection.y)
            for detection in self.brick_room_cropped.detections
            if detection.type_id in FULL_SPIKE_TYPES
        }

        self.assertIn((OBJ_SPIKE_LEFT, 32, 544), spikes)
        self.assertIn((OBJ_SPIKE_LEFT, 448, 384), spikes)
        self.assertIn((OBJ_SPIKE_UP, 240, 352), spikes)
        self.assertNotIn((OBJ_SPIKE_UP, 240, 360), spikes)

    def test_exact_brick_room_does_not_union_competing_block_phases(self) -> None:
        detected_blocks = {
            (detection.x, detection.y)
            for detection in self.brick_room_exact.detections
            if detection.type_id == OBJ_BLOCK
        }
        truth_blocks = {
            (obj.x, obj.y)
            for obj in self.brick_room_truth.objects
            if obj.type_id == OBJ_BLOCK
        }

        self.assertEqual(detected_blocks - truth_blocks, set())

    def test_ftfa_room_01_rejects_weak_lower_right_boundary_sliver(self) -> None:
        blocks = {
            (detection.x, detection.y)
            for detection in self.ftfa_room_01.detections
            if detection.type_id == OBJ_BLOCK
        }

        self.assertNotIn((768, 480), blocks)

    def test_dark_room_profile_separates_saves_warps_and_terrain(self) -> None:
        detections = self.lap_first.detections
        self.assertEqual(
            [
                (detection.x, detection.y)
                for detection in detections
                if detection.type_id == OBJ_SAVE
            ],
            [(448, 288), (512, 544)],
        )
        self.assertEqual(
            [
                (detection.x, detection.y)
                for detection in detections
                if detection.type_id == OBJ_WARP
            ],
            [(64, 352)],
        )
        self.assertEqual(
            sum(detection.type_id == OBJ_BLOCK for detection in detections),
            130,
        )
        self.assertEqual(
            sum(detection.type_id in FULL_SPIKE_TYPES for detection in detections),
            93,
        )
        self.assertEqual(self._terrain_spike_overlaps(detections), 0)

    def test_adaptive_dark_save_header_rejects_warp_body_without_label(self) -> None:
        save_mask = tuple(
            int(row.replace(".", "0").replace("#", "1")[::-1], 2)
            for row in (
                "................",
                "..#..#.#.##.....",
                "..####.#..#.#...",
                "..##......###...",
            )
        ) + (0,) * 12
        warp_mask = tuple(
            int(row.replace(".", "0").replace("#", "1")[::-1], 2)
            for row in (
                "................",
                "...##..#........",
                "..#########.....",
                ".####....###....",
            )
        ) + (0,) * 12
        self.assertTrue(_dark_save_header_is_label_like(save_mask))
        self.assertFalse(_dark_save_header_is_label_like(warp_mask))

    def test_lit_grayscale_save_is_not_a_warp(self) -> None:
        detections = self.lap_active_save.detections
        self.assertEqual(
            [
                (detection.kind, detection.x, detection.y)
                for detection in detections
                if detection.type_id == OBJ_SAVE
            ],
            [("dark_save_active_terrain_aligned", 416, 544)],
        )
        self.assertFalse(
            any(detection.type_id == OBJ_WARP for detection in detections)
        )
        self.assertEqual(self._terrain_spike_overlaps(detections), 0)

    def test_only_uniquely_supported_spikes_are_reoriented(self) -> None:
        image_box = Box(0, 0, GRID_SIZE, GRID_SIZE)
        unsupported_up = Detection(
            "test_up",
            OBJ_SPIKE_UP,
            32,
            32,
            0.9,
            image_box,
        )
        floating_up = Detection(
            "floating_up",
            OBJ_SPIKE_UP,
            160,
            160,
            0.9,
            image_box,
        )
        right_support = Detection(
            "block",
            OBJ_BLOCK,
            64,
            32,
            0.9,
            image_box,
        )

        reconciled = _reorient_unsupported_spikes(
            [unsupported_up, floating_up],
            [right_support],
        )

        self.assertEqual(reconciled[0].type_id, OBJ_SPIKE_LEFT)
        self.assertEqual(reconciled[0].kind, "test_up_support_reoriented_left")
        self.assertEqual(reconciled[1], floating_up)

    def test_room_edge_support_does_not_reorient_a_cropped_spike(self) -> None:
        image_box = Box(0, 0, GRID_SIZE, GRID_SIZE)
        bottom_up = Detection(
            "bottom_up",
            OBJ_SPIKE_UP,
            32,
            ROOM_HEIGHT - GRID_SIZE,
            0.9,
            image_box,
        )
        side_block = Detection(
            "block",
            OBJ_BLOCK,
            64,
            ROOM_HEIGHT - GRID_SIZE,
            0.9,
            image_box,
        )

        self.assertEqual(
            _reorient_unsupported_spikes([bottom_up], [side_block]),
            [bottom_up],
        )

    def test_lap_room_08_separates_the_bottom_right_opposite_pair(self) -> None:
        spikes = {
            (detection.type_id, detection.x, detection.y)
            for detection in self.lap_room_08.detections
            if detection.type_id in FULL_SPIKE_TYPES
        }

        self.assertIn((OBJ_SPIKE_UP, 704, 480), spikes)
        self.assertIn((OBJ_SPIKE_DOWN, 704, 512), spikes)
        self.assertNotIn((OBJ_SPIKE_UP, 704, 488), spikes)

    def test_lap_room_09_preserves_three_clear_upward_spikes(self) -> None:
        spikes = {
            (detection.type_id, detection.x, detection.y)
            for detection in self.lap_room_09.detections
            if detection.type_id in FULL_SPIKE_TYPES
        }

        self.assertIn((OBJ_SPIKE_UP, 448, 288), spikes)
        self.assertIn((OBJ_SPIKE_UP, 384, 288), spikes)
        self.assertIn((OBJ_SPIKE_UP, 288, 384), spikes)

    def test_lap_room_09_uses_local_silhouette_for_middle_down_spike(self) -> None:
        spikes = {
            (detection.type_id, detection.x, detection.y)
            for detection in self.lap_room_09.detections
            if detection.type_id in FULL_SPIKE_TYPES
        }

        self.assertIn((OBJ_SPIKE_DOWN, 384, 320), spikes)
        self.assertNotIn((OBJ_SPIKE_RIGHT, 384, 320), spikes)

    def test_component_spike_direction_is_not_overridden_by_incidental_support(
        self,
    ) -> None:
        image_box = Box(0, 0, GRID_SIZE, GRID_SIZE)
        component_up = Detection(
            "dark_component_spike_up",
            OBJ_SPIKE_UP,
            32,
            32,
            0.9,
            image_box,
        )
        side_block = Detection(
            "block",
            OBJ_BLOCK,
            64,
            32,
            0.9,
            image_box,
        )

        self.assertEqual(
            _reorient_unsupported_spikes([component_up], [side_block]),
            [component_up],
        )

    def test_component_spike_aligns_to_its_unique_adjacent_support(self) -> None:
        image_box = Box(0, 0, GRID_SIZE, GRID_SIZE)
        image = RGBImage(128, 128, bytes(128 * 128 * 3))
        room = Box(0, 0, 128, 128)
        spike = Detection(
            "warm_component_spike_right",
            OBJ_SPIKE_RIGHT,
            64,
            64,
            0.9,
            image_box,
        )
        support = Detection(
            "warm_terrain_block",
            OBJ_BLOCK,
            32,
            48,
            0.9,
            image_box,
        )

        aligned = _realign_warm_component_spike_phase(
            [spike],
            [support],
            image,
            room,
        )

        self.assertEqual((aligned[0].x, aligned[0].y), (64, 48))
        self.assertEqual(aligned[0].type_id, OBJ_SPIKE_RIGHT)

    def test_compressed_opposite_pair_moves_off_phase_spike_outward(
        self,
    ) -> None:
        image_box = Box(0, 0, GRID_SIZE, GRID_SIZE)
        upper = Detection(
            "component_up",
            OBJ_SPIKE_UP,
            704,
            488,
            0.9,
            image_box,
        )
        lower = Detection(
            "component_down",
            OBJ_SPIKE_DOWN,
            704,
            512,
            0.9,
            image_box,
        )

        reconciled = _separate_overlapping_opposite_spikes([upper, lower])

        self.assertEqual((reconciled[0].x, reconciled[0].y), (704, 480))
        self.assertEqual(reconciled[0].type_id, OBJ_SPIKE_UP)
        self.assertEqual((reconciled[1].x, reconciled[1].y), (704, 512))

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

        self.assertIn((544, 320, OBJ_SPIKE_UP), {(item.x, item.y, item.type_id) for item in aligned})
        self.assertIn((544, 352, OBJ_SPIKE_DOWN), {(item.x, item.y, item.type_id) for item in aligned})

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

    def test_point_objects_use_their_center_as_the_jmap_coordinate(self) -> None:
        room = Box(0, 0, 800, 608)

        self.assertEqual(
            _image_box_to_jtool_center(Box(390, 38, 20, 20), room, 8),
            (400, 48),
        )

    @staticmethod
    def _terrain_spike_overlaps(detections) -> int:
        blocks = [
            detection
            for detection in detections
            if detection.type_id == OBJ_BLOCK
        ]
        spikes = [
            detection
            for detection in detections
            if detection.type_id in FULL_SPIKE_TYPES
        ]
        return max(
            (
                max(
                    0,
                    min(spike.x + GRID_SIZE, block.x + GRID_SIZE)
                    - max(spike.x, block.x),
                )
                * max(
                    0,
                    min(spike.y + GRID_SIZE, block.y + GRID_SIZE)
                    - max(spike.y, block.y),
                )
                for spike in spikes
                for block in blocks
            ),
            default=0,
        )

    @staticmethod
    def _overlap_area(first, second) -> int:
        return (
            max(
                0,
                min(first.x + GRID_SIZE, second.x + GRID_SIZE)
                - max(first.x, second.x),
            )
            * max(
                0,
                min(first.y + GRID_SIZE, second.y + GRID_SIZE)
                - max(first.y, second.y),
            )
        )


if __name__ == "__main__":
    unittest.main()
