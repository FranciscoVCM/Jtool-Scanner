from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from jtool_scanner.constants import (
    GRID_SIZE,
    OBJ_APPLE,
    OBJ_BLOCK,
    OBJ_JUMP_REFRESHER,
    OBJ_MINI_BLOCK,
    OBJ_MINI_SPIKE_DOWN,
    OBJ_MINI_SPIKE_LEFT,
    OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_UP,
    OBJ_PLATFORM,
    OBJ_SAVE,
    OBJ_SPIKE_DOWN,
    OBJ_SPIKE_LEFT,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_UP,
    OBJ_WARP,
    OBJ_WATER,
    OBJ_WATER_2,
    OBJ_WATER_3,
    OBJ_WALLJUMP_LEFT,
    OBJ_WALLJUMP_RIGHT,
    ROOM_HEIGHT,
)
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.image import load_png
from jtool_scanner.benchmark import compare_jmaps
from jtool_scanner.evaluation import evaluate_scan
from jtool_scanner.jmap import JMap
from jtool_scanner.scanner import (
    Detection,
    FULL_SPIKE_TYPES,
    MINI_SPIKE_TYPES,
    ScanResult,
    _CaptureLatticeAxis,
    _CaptureLatticeNormalization,
    _capture_lattice_axis_has_material_gain,
    _capture_lattice_axis_has_distinct_boundaries,
    _detect_outlined_terrain_saves,
    _detect_outlined_terrain_spikes,
    _dark_save_header_is_label_like,
    _align_unsupported_opposite_spike_pairs,
    _choose_component_spike_candidate,
    _image_box_to_jtool_center,
    _infer_capture_lattice_normalization,
    _infer_source_grid,
    _looks_like_outlined_terrain_room,
    _outlined_terrain_cell_stats,
    _reorient_unsupported_spikes,
    _realign_warm_component_spike_phase,
    _reconcile_terrain_markers,
    _reconcile_walljump_terrain_anchors,
    _scan_lattice_normalized_room,
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


class CaptureLatticeRegressionTests(unittest.TestCase):
    def test_capture_lattice_gain_must_belong_to_a_material_transform(self) -> None:
        self.assertFalse(
            _capture_lattice_axis_has_material_gain(
                _CaptureLatticeAxis(0, 750, 30.0, 10.0),
                749,
            )
        )
        self.assertTrue(
            _capture_lattice_axis_has_material_gain(
                _CaptureLatticeAxis(-3, 750, 30.0, 10.0),
                749,
            )
        )

    def test_capture_lattice_confidence_rejects_tiled_background_alias(self) -> None:
        self.assertFalse(
            _capture_lattice_axis_has_distinct_boundaries(
                _CaptureLatticeAxis(-3, 750, 40.0, 10.0, 2.8),
            )
        )
        self.assertTrue(
            _capture_lattice_axis_has_distinct_boundaries(
                _CaptureLatticeAxis(-3, 750, 40.0, 10.0, 3.2),
            )
        )

    def test_capture_lattice_normalization_requires_measured_phase_gain(self) -> None:
        misaligned = _misaligned_capture_lattice_image()
        with patch(
            "jtool_scanner.scanner._detect_mini_blocks",
            return_value=[object()] * 400,
        ):
            normalization = _infer_capture_lattice_normalization(
                misaligned,
                Box(0, 0, misaligned.width, misaligned.height),
            )
        self.assertIsNotNone(normalization)
        assert normalization is not None
        self.assertGreaterEqual(normalization.x_axis.gain, 1.65)

        tracked = load_png(
            Path("fixtures") / "block_spike" / "cn3-18-game.png"
        )
        self.assertIsNone(
            _infer_capture_lattice_normalization(
                tracked,
                detect_room_box(tracked),
            )
        )

        sparse = load_png(Path("fixtures") / "block_spike" / "nang135-game.png")
        self.assertIsNone(
            _infer_capture_lattice_normalization(
                sparse,
                detect_room_box(sparse),
            )
        )

        for name in ("screen-1-source.png", "screen-3-source.png"):
            with self.subTest(ftfa=name):
                ftfa = load_png(
                    Path("fixtures")
                    / "regressions"
                    / "unseen-rooms"
                    / "ftfa"
                    / name
                )
                self.assertIsNone(
                    _infer_capture_lattice_normalization(
                        ftfa,
                        detect_room_box(ftfa),
                    )
                )

    def test_lattice_merge_preserves_source_save_and_vine_anchors(self) -> None:
        source_room = Box(0, 0, 480, 365)
        normalization = _CaptureLatticeNormalization(
            source_room,
            _CaptureLatticeAxis(-4, 490, 30.0, 15.0),
            _CaptureLatticeAxis(-2, 370, 24.0, 18.0),
        )
        source_result = ScanResult(
            480,
            365,
            source_room,
            detections=[
                Detection("save", OBJ_SAVE, 96, 96, 0.9, Box(50, 50, 20, 20)),
                Detection(
                    "walljump_left",
                    OBJ_WALLJUMP_LEFT,
                    16,
                    32,
                    0.9,
                    Box(10, 20, 10, 20),
                ),
                Detection("warp", OBJ_WARP, 32, 32, 0.9, Box(20, 20, 20, 20)),
            ],
        )
        canonical_result = ScanResult(
            800,
            608,
            Box(0, 0, 800, 608),
            detections=[
                Detection("save", OBJ_SAVE, 96, 104, 0.9, Box(96, 104, 32, 32)),
                Detection(
                    "walljump_left",
                    OBJ_WALLJUMP_LEFT,
                    24,
                    32,
                    0.9,
                    Box(24, 32, 16, 32),
                ),
                Detection("warp", OBJ_WARP, 40, 40, 0.9, Box(40, 40, 32, 32)),
                Detection("block", OBJ_BLOCK, 64, 64, 0.9, Box(64, 64, 32, 32)),
            ],
        )
        image = RGBImage(480, 365, bytes(480 * 365 * 3))
        canonical_image = RGBImage(800, 608, bytes(800 * 608 * 3))
        with (
            patch(
                "jtool_scanner.scanner.scan_image",
                side_effect=[source_result, canonical_result],
            ) as scan,
            patch(
                "jtool_scanner.scanner._resample_capture_lattice_room",
                return_value=canonical_image,
            ),
        ):
            merged = _scan_lattice_normalized_room(
                image,
                normalization,
                grid_step=8,
                include_color_objects=True,
                recognized_text="",
            )

        objects = {(item.type_id, item.x, item.y) for item in merged.detections}
        self.assertIn((OBJ_SAVE, 96, 96), objects)
        self.assertNotIn((OBJ_SAVE, 96, 104), objects)
        self.assertIn((OBJ_WALLJUMP_LEFT, 16, 32), objects)
        self.assertNotIn((OBJ_WALLJUMP_LEFT, 24, 32), objects)
        self.assertIn((OBJ_WARP, 40, 40), objects)
        self.assertNotIn((OBJ_WARP, 32, 32), objects)
        self.assertIn((OBJ_BLOCK, 64, 64), objects)
        self.assertEqual(scan.call_count, 2)
        self.assertFalse(scan.call_args_list[0].kwargs["include_geometry"])
        self.assertTrue(scan.call_args_list[1].kwargs["include_geometry"])


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
        block_positions = {
            (detection.x, detection.y)
            for detection in result.detections
            if detection.type_id == OBJ_BLOCK
        }
        primary_kind_by_type = {
            OBJ_SPIKE_UP: "spike_up",
            OBJ_SPIKE_RIGHT: "spike_right",
            OBJ_SPIKE_LEFT: "spike_left",
            OBJ_SPIKE_DOWN: "spike_down",
        }
        self.assertFalse(
            any(
                (detection.x, detection.y) in block_positions
                and detection.kind != primary_kind_by_type[detection.type_id]
                for detection in result.detections
                if detection.type_id in FULL_SPIKE_TYPES
            )
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

    def test_dark_textured_room_recovers_paired_up_minispikes(self) -> None:
        result = scan_png(
            Path("fixtures") / "block_spike" / "k3-ex-hades-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        upward_minis = {
            (detection.x, detection.y)
            for detection in result.detections
            if detection.type_id == OBJ_MINI_SPIKE_UP
        }
        self.assertEqual(
            upward_minis,
            {
                (544, 112),
                (560, 112),
                (480, 16),
                (464, 16),
                (416, 16),
                (400, 16),
                (240, 496),
                (224, 496),
            },
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

    def test_catharsis_water_tail_recovery_keeps_irkara71_column_phase(self) -> None:
        result = scan_png(
            Path("fixtures") / "irkara" / "irkara-71-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        detected = {
            (detection.x, detection.y)
            for detection in result.detections
            if detection.type_id == OBJ_WATER_2
        }
        truth = {
            (item.x, item.y)
            for item in JMap.from_file(
                Path("fixtures") / "irkara" / "irkara-71.jmap"
            ).objects
            if item.type_id == OBJ_WATER_2
        }

        # The two lower cells are the weak tail immediately after the seeded
        # catharsis-water column.  They must retain their native 32px phase.
        self.assertIn((352, 544), detected)
        self.assertIn((352, 576), detected)
        # This separate column is almost black from top to bottom.  Its three
        # dark cells and structured neutral transition must still be recovered
        # without allowing smooth background columns to become water.
        self.assertTrue(
            {
                (576, 96),
                (576, 128),
                (576, 160),
                (576, 192),
            }
            <= detected
        )
        # The remaining water cells are hidden under full-spike silhouettes;
        # geometry-aware composite recovery must preserve both opposing pairs
        # and the isolated same-cell overlay without adding any other water.
        self.assertTrue(
            {
                (256, 288),
                (288, 288),
                (384, 416),
                (160, 576),
                (192, 576),
            }
            <= detected
        )
        # No palette-relative tail recovery may invent water elsewhere.
        self.assertTrue(detected <= truth)

    def test_boundary_water_recovery_keeps_irkara54_edge_cells(self) -> None:
        result = scan_png(
            Path("fixtures") / "irkara" / "irkara-54-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        detected = {
            (detection.x, detection.y)
            for detection in result.detections
            if detection.type_id == OBJ_WATER_2
        }
        truth = {
            (item.x, item.y)
            for item in JMap.from_file(
                Path("fixtures") / "irkara" / "irkara-54.jmap"
            ).objects
            if item.type_id in (OBJ_WATER, OBJ_WATER_2, OBJ_WATER_3)
        }

        # These two clipped cells are between exact water neighbors at the
        # same room edge; no other edge candidate may be invented.
        self.assertIn((0, 512), detected)
        self.assertIn((768, 512), detected)
        boundary_detected = {
            position
            for position in detected
            if position[0] in (0, 768)
        }
        boundary_truth = {
            position
            for position in truth
            if position[0] in (0, 768)
        }
        self.assertTrue(boundary_detected <= boundary_truth)
        save_overlay = {
            (detection.x, detection.y)
            for detection in result.detections
            if detection.kind == "water_2_save_overlay"
        }
        self.assertEqual(save_overlay, {(32, 64)})
        self.assertFalse(
            any(
                detection.kind == "water_2_save_overlay"
                for detection in self.particle_room.detections
            )
        )

    def test_dark_sparse_save_headers_recover_body_centroid_phase(self) -> None:
        expected = {
            "irkara-49-game.png": [(256, 64), (384, 544)],
            "irkara-49-warp-game.png": [(256, 64), (384, 544)],
        }
        options = {
            "grid_step": 8,
            "include_color_objects": True,
            "include_geometry": True,
            "enable_ocr": False,
        }
        for name, coordinates in expected.items():
            with self.subTest(name=name):
                result = scan_png(Path("fixtures") / "irkara" / name, **options)
                self.assertEqual(
                    sorted(
                        (detection.x, detection.y)
                        for detection in result.detections
                        if detection.type_id == OBJ_SAVE
                    ),
                    coordinates,
                )
        control = scan_png(
            Path("fixtures") / "irkara" / "irkara-71-game.png",
            **options,
        )
        self.assertEqual(
            sorted(
                (detection.x, detection.y)
                for detection in control.detections
                if detection.type_id == OBJ_SAVE
            ),
            [(384, 96), (544, 544)],
        )

    def test_relative_save_headers_recover_cyan_and_lower_cn3_phase(self) -> None:
        expected = {
            "irkara-54-game.png": [(32, 64), (192, 544), (576, 544)],
        }
        options = {
            "grid_step": 8,
            "include_color_objects": True,
            "include_geometry": True,
            "enable_ocr": False,
        }
        for name, coordinates in expected.items():
            with self.subTest(name=name):
                result = scan_png(Path("fixtures") / "irkara" / name, **options)
                self.assertEqual(
                    sorted(
                        (detection.x, detection.y)
                        for detection in result.detections
                        if detection.type_id == OBJ_SAVE
                    ),
                    coordinates,
                )
        result = scan_png(
            Path("fixtures") / "block_spike" / "cn3-18-game.png",
            **options,
        )
        self.assertEqual(
            sorted(
                (detection.x, detection.y)
                for detection in result.detections
                if detection.type_id == OBJ_SAVE
            ),
            [(224, 80), (384, 256), (768, 368)],
        )

    def test_supported_save_body_keeps_flames_origin(self) -> None:
        """A pale terrain seam must not move a supported body one phase up."""

        result = scan_png(
            Path("fixtures") / "block_spike" / "irkara-nr-flames-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        detected = sorted(
            (detection.x, detection.y)
            for detection in result.detections
            if detection.type_id == OBJ_SAVE
        )
        truth = sorted(
            (item.x, item.y)
            for item in JMap.from_file(
                Path("fixtures") / "block_spike" / "irkara-nr-flames.jmap"
            ).objects
            if item.type_id == OBJ_SAVE
        )
        self.assertEqual(detected, truth)

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
        # Green terrain edges at the far right previously produced two
        # sparse-patch walljump impostors.  The morphology gate must remove
        # those bands without changing the four authoritative vine cells.
        self.assertEqual(
            sorted(walljumps),
            [
                (0, 240, 16),
                (128, 320, 17),
                (224, 128, 17),
                (672, 400, 16),
            ],
        )
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

    def test_neutral_blocks_can_coexist_with_supported_walljumps(self) -> None:
        """A vine overlay must not erase an independently supported square."""

        controls = (
            (
                Path("fixtures") / "block_spike" / "irkara-89-game.png",
                {
                    (0, 112),
                    (0, 144),
                    (416, 128),
                    (256, 512),
                },
                {(336, 272), (336, 304), (640, 376)},
            ),
            (
                Path("fixtures") / "irkara" / "irkara-51-game.png",
                {(224, 128), (128, 320)},
                {(0, 240), (672, 400)},
            ),
        )
        for path, expected, unsupported in controls:
            with self.subTest(path=path.name):
                result = scan_png(
                    path,
                    grid_step=8,
                    include_color_objects=True,
                    include_geometry=True,
                    enable_ocr=False,
                )
                blocks = {
                    (detection.x, detection.y)
                    for detection in result.detections
                    if detection.type_id == OBJ_BLOCK
                }
                self.assertTrue(expected.issubset(blocks))
                self.assertTrue(unsupported.isdisjoint(blocks))

    def test_embedded_compact_room_recovers_irkara58_block_lattice(self) -> None:
        """A centered unfamiliar 9x9 room must not become outer-background terrain."""

        source = Path("fixtures") / "irkara" / "irkara-58-game.png"
        result = scan_png(
            source,
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        self.assertEqual(result.source_grid, (9, 9))
        self.assertEqual(result.room_box, Box(307, 216, 342, 324))
        expected = {
            (object_.x, object_.y)
            for object_ in JMap.from_file(
                Path("fixtures") / "irkara" / "irkara-58.jmap"
            ).objects_of_type(OBJ_BLOCK)
        }
        blocks = {
            (detection.x, detection.y)
            for detection in result.detections
            if detection.type_id == OBJ_BLOCK
        }
        self.assertEqual(blocks, expected)
        self.assertTrue(
            all(
                detection.kind == "embedded_compact_relative_block"
                for detection in result.detections
                if detection.type_id == OBJ_BLOCK
            )
        )

        # A full green room with no detached compact island stays on the
        # ordinary terrain path; the embedded rule must not relabel it.
        held_out = scan_png(
            Path("fixtures") / "irkara" / "irkara-57-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        self.assertIsNone(held_out.source_grid)

    def test_embedded_compact_room_recovers_supported_full_spikes(self) -> None:
        """The embedded block lattice supplies independent spike support."""

        source = Path("fixtures") / "irkara" / "irkara-58-game.png"
        result = scan_png(
            source,
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        expected = {
            (object_.x, object_.y, object_.type_id)
            for object_ in JMap.from_file(
                Path("fixtures") / "irkara" / "irkara-58.jmap"
            ).objects
            if object_.type_id in FULL_SPIKE_TYPES
        }
        actual = {
            (detection.x, detection.y, detection.type_id)
            for detection in result.detections
            if detection.type_id in FULL_SPIKE_TYPES
        }
        self.assertEqual(actual, expected)
        self.assertEqual(
            sum(
                detection.kind == "embedded_compact_supported_full_spike"
                for detection in result.detections
            ),
            2,
        )

    def test_bright_filled_reconcile_keeps_recovered_full_spikes(self) -> None:
        """Room-scale bright fill must not discard topology recoveries."""

        result = scan_png(
            Path("fixtures") / "block_spike" / "irkara-nr-flames-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        full_spikes = {
            (detection.x, detection.y, detection.type_id)
            for detection in result.detections
            if detection.type_id in FULL_SPIKE_TYPES
        }
        self.assertTrue(
            {
                (352, 192, OBJ_SPIKE_UP),
                (96, 192, OBJ_SPIKE_LEFT),
                (576, 160, OBJ_SPIKE_LEFT),
                (576, 240, OBJ_SPIKE_LEFT),
            }.issubset(full_spikes)
        )

    def test_bright_filled_reconcile_keeps_clipped_miniblock_room_spikes(self) -> None:
        """Clipped CN3 triangles survive the bright-field rebuild."""

        result = scan_png(
            Path("fixtures") / "block_spike" / "cn3-18-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        full_spikes = {
            (detection.x, detection.y, detection.type_id)
            for detection in result.detections
            if detection.type_id in FULL_SPIKE_TYPES
        }
        self.assertTrue(
            {
                (304, 144, OBJ_SPIKE_UP),
                (448, 288, OBJ_SPIKE_UP),
                (448, 320, OBJ_SPIKE_DOWN),
                (496, 352, OBJ_SPIKE_DOWN),
                (176, 336, OBJ_SPIKE_RIGHT),
                (192, 576, OBJ_SPIKE_UP),
                (224, 576, OBJ_SPIKE_UP),
            }.issubset(full_spikes)
        )
        self.assertNotIn((288, 144, OBJ_SPIKE_LEFT), full_spikes)
        self.assertNotIn((320, 144, OBJ_SPIKE_RIGHT), full_spikes)

    def test_miniblock_weak_spike_phases_match_both_cn3_maps(self) -> None:
        """Weak support seams must not add spikes outside either CN3 JMap."""

        fixture_dir = Path("fixtures") / "block_spike"
        minimum_exact = {"cn3-16": 590, "cn3-18": 491}
        maximum_false_positives = {"cn3-16": 36, "cn3-18": 44}
        geometry_group_limits = {
            "cn3-16": {
                "mini_block": (501, 36, 0),
                "mini_spikes": (54, 0, 0),
            },
            "cn3-18": {
                "mini_block": (374, 42, 0),
                "mini_spikes": (54, 2, 0),
            },
        }
        for pair_id in ("cn3-16", "cn3-18"):
            with self.subTest(pair_id=pair_id):
                result = scan_png(
                    fixture_dir / f"{pair_id}-game.png",
                    grid_step=8,
                    include_color_objects=True,
                    include_geometry=True,
                    enable_ocr=False,
                )
                truth = JMap.from_file(fixture_dir / f"{pair_id}.jmap")
                expected = {
                    (object_.x, object_.y, object_.type_id)
                    for type_id in FULL_SPIKE_TYPES
                    for object_ in truth.objects_of_type(type_id)
                }
                actual = {
                    (detection.x, detection.y, detection.type_id)
                    for detection in result.detections
                    if detection.type_id in FULL_SPIKE_TYPES
                }
                self.assertEqual(actual, expected)
                comparison = compare_jmaps(result.to_jmap(), truth)
                summary = comparison["summary"]
                self.assertGreaterEqual(summary["exact"], minimum_exact[pair_id])
                self.assertLessEqual(
                    summary["false_positive"],
                    maximum_false_positives[pair_id],
                )
                self.assertEqual(summary["shifted"], 0)
                self.assertEqual(summary["wrong_orientation"], 0)
                for group_name, limits in geometry_group_limits[pair_id].items():
                    exact, false_positive, missed = limits
                    group = comparison["groups"][group_name]
                    self.assertGreaterEqual(group["exact"], exact)
                    self.assertLessEqual(group["false_positive"], false_positive)
                    self.assertLessEqual(group["missed"], missed)
                    self.assertEqual(group["shifted"], 0)
                    self.assertEqual(group["wrong_orientation"], 0)

    def test_bright_filled_reconcile_keeps_near_threshold_strong_spike(self) -> None:
        """A strong topology spike survives a narrowly clipped fill profile."""

        result = scan_png(
            Path("fixtures") / "block_spike" / "cn3-16-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        full_spikes = {
            (detection.x, detection.y, detection.type_id)
            for detection in result.detections
            if detection.type_id in FULL_SPIKE_TYPES
        }
        self.assertTrue(
            {
                (96, 400, OBJ_SPIKE_LEFT),
                (240, 576, OBJ_SPIKE_LEFT),
            }.issubset(full_spikes)
        )

    def test_repeated_vine_phase_beats_same_column_terrain_alias(self) -> None:
        """A cadence-confirmed vine keeps its shape-derived half-cell origin."""

        room = Box(0, 0, 800, 608)
        image = RGBImage(room.width, room.height, b"\x00" * (room.width * room.height * 3))
        terrain = Detection("supported_terrain_block", OBJ_BLOCK, 416, 288, 0.8, Box(416, 288, 32, 32))
        vine = Detection(
            "walljump_left_repeated_strip",
            OBJ_WALLJUMP_LEFT,
            400,
            288,
            0.77,
            Box(400, 288, 32, 32),
        )
        right_alias = Detection(
            "walljump_right_repeated_strip",
            OBJ_WALLJUMP_RIGHT,
            432,
            288,
            0.88,
            Box(432, 288, 32, 32),
        )

        result = _reconcile_walljump_terrain_anchors(
            [terrain, vine, right_alias],
            image,
            room,
        )

        self.assertIn(
            (400, 288, OBJ_WALLJUMP_LEFT, "walljump_left_repeated_strip"),
            {(detection.x, detection.y, detection.type_id, detection.kind) for detection in result},
        )
        self.assertIn(
            (416, 288, OBJ_WALLJUMP_LEFT, "walljump_left_terrain_aligned"),
            {(detection.x, detection.y, detection.type_id, detection.kind) for detection in result},
        )

    def test_save_marker_keeps_visual_horizontal_phase_against_support_alias(self) -> None:
        """Terrain support must not move a marker to a neighboring half-cell."""

        room = Box(0, 0, 800, 608)
        image = RGBImage(room.width, room.height, b"\x00" * (room.width * room.height * 3))
        save = Detection(
            "save",
            OBJ_SAVE,
            112,
            328,
            1.0,
            Box(112, 328, 32, 32),
        )
        supports = [
            Detection(
                "block_left",
                OBJ_BLOCK,
                96,
                352,
                0.8,
                Box(96, 352, 32, 32),
            ),
            Detection(
                "block_right",
                OBJ_BLOCK,
                128,
                352,
                0.8,
                Box(128, 352, 32, 32),
            ),
        ]

        result, _ = _reconcile_terrain_markers(
            [save],
            supports,
            image,
            room,
        )
        marker = next(detection for detection in result if detection.type_id == OBJ_SAVE)
        self.assertEqual((marker.x, marker.y), (112, 320))

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
                (112, 32, OBJ_MINI_SPIKE_DOWN),
                (544, 96, OBJ_MINI_SPIKE_RIGHT),
                (560, 144, OBJ_MINI_SPIKE_LEFT),
                (304, 176, OBJ_MINI_SPIKE_UP),
                (752, 352, OBJ_MINI_SPIKE_LEFT),
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
            [(224, 80), (384, 256), (768, 368)],
        )

    def test_short_edge_walljump_uses_component_top_origin(self) -> None:
        result = scan_png(
            Path("fixtures") / "irkara" / "irkara-51-game.png",
            grid_step=8,
            include_color_objects=True,
            include_geometry=True,
            enable_ocr=False,
        )
        walljumps = [
            detection
            for detection in result.detections
            if detection.type_id in (OBJ_WALLJUMP_LEFT, OBJ_WALLJUMP_RIGHT)
        ]
        self.assertIn(
            (0, 240, OBJ_WALLJUMP_LEFT),
            {
                (detection.x, detection.y, detection.type_id)
                for detection in walljumps
            },
        )
        mini_spikes = {
            (detection.x, detection.y, detection.type_id)
            for detection in result.detections
            if detection.type_id in MINI_SPIKE_TYPES
        }
        self.assertTrue(
            {
                (720, 160, OBJ_MINI_SPIKE_LEFT),
                (720, 256, OBJ_MINI_SPIKE_LEFT),
                (416, 288, OBJ_MINI_SPIKE_DOWN),
                (624, 480, OBJ_MINI_SPIKE_DOWN),
                (640, 480, OBJ_MINI_SPIKE_DOWN),
                (384, 512, OBJ_MINI_SPIKE_DOWN),
                (656, 560, OBJ_MINI_SPIKE_UP),
                (576, 176, OBJ_MINI_SPIKE_UP),
            }.issubset(mini_spikes)
        )
        self.assertNotIn((320, 32, OBJ_MINI_SPIKE_RIGHT), mini_spikes)

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


def _misaligned_capture_lattice_image() -> RGBImage:
    width, height = 480, 365
    origin_x, origin_y = -4, -2
    extent_x, extent_y = 490, 370
    data = bytearray(width * height * 3)
    offset = 0
    for y in range(height):
        cell_y = int((y - origin_y) * 38 / extent_y)
        for x in range(width):
            cell_x = int((x - origin_x) * 50 / extent_x)
            value = 212 if (cell_x + cell_y) % 2 else 28
            data[offset : offset + 3] = bytes((value, value, value))
            offset += 3
    return RGBImage(width, height, bytes(data))


if __name__ == "__main__":
    unittest.main()
