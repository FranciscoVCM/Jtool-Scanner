from __future__ import annotations

import unittest
from unittest import mock

from jtool_scanner.constants import (
    OBJ_APPLE,
    OBJ_BLOCK,
    OBJ_MINI_SPIKE_DOWN,
    OBJ_MINI_SPIKE_LEFT,
    OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_UP,
    OBJ_SAVE,
    OBJ_SPIKE_DOWN,
    OBJ_SPIKE_LEFT,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_UP,
    OBJ_WATER_2,
)
from jtool_scanner.geometry import Box
from jtool_scanner.scanner import (
    Detection,
    _GeometryClass,
    _GeometryPatchCandidate,
    _PatchFeatures,
    _accept_block,
    _accept_block_run_gap_patch,
    _accept_full_spike,
    _accept_full_spike_support,
    _accept_mini_spike,
    _can_recover_diagonal_side_mini_spike,
    _can_recover_extended_left_mini_spike,
    _is_adjacent_up_mini_spike_candidate,
    _can_recover_axis_supported_mini_spike,
    _can_recover_horizontal_side_mini_spike,
    _dedupe_geometry,
    _dedupe_overlapping_geometry,
    _dedupe_normalized_full_spikes,
    _can_recover_nearby_hollow_block,
    _is_block_run_gap,
    _is_blocklike_mini_spike_noise_candidate,
    _is_blocklike_full_spike_recovery_candidate,
    _is_blocklike_spike_candidate,
    _is_bottom_edge_up_spike_continuation_anchor,
    _is_bottom_edge_up_spike_continuation_patch,
    _is_center_heavy_block_candidate,
    _is_dark_outline_block_run_fill_patch,
    _is_dark_outline_full_spike_candidate,
    _is_weak_full_spike_shape_recovery,
    _is_dark_outline_half_step_full_spike_candidate,
    _is_strong_full_spike_shape_candidate,
    _is_strong_offgrid_full_spike_shape,
    _is_weak_full_spike_run_shape,
    _is_weak_two_neighbor_support_noise,
    _has_full_spike_run_anchor,
    _full_spike_run_distance,
    _is_edge_outline_block_patch,
    _is_edge_weak_block_patch,
    _is_edge_full_spike_continuation_anchor,
    _is_edge_full_spike_continuation_patch,
    _is_full_spike_run_gap_patch,
    _is_half_step_supported_full_spike_candidate,
    _has_axis_mini_spike_support,
    _has_axis_left_mini_step_support,
    _has_adjacent_up_mini_spike_pair,
    _has_ambiguous_adjacent_up_mini_spike_pair,
    _has_dense_adjacent_up_mini_spike_support,
    _has_diagonal_side_mini_spike_support,
    _has_diagonal_right_mini_step_support,
    _has_extended_left_mini_spike_support,
    _has_horizontal_side_mini_spike_support,
    _has_low_contrast_mini_up_pair,
    _has_mixed_cluster_up_mini_spike_support,
    _has_border_supported_up_mini_spike_support,
    _has_diagonal_anchor_up_mini_spike_support,
    _has_left_spike_supports,
    _has_low_contrast_paired_up_mini_spike_pair,
    _has_low_contrast_paired_up_mini_spike_support,
    _has_low_border_side_mini_spike_support,
    _has_ultra_faint_left_mini_spike_support,
    _is_low_contrast_mini_up_candidate,
    _is_ambiguous_adjacent_up_mini_spike_candidate,
    _is_border_supported_up_mini_spike_candidate,
    _is_dense_adjacent_up_mini_spike_candidate,
    _is_diagonal_anchor_up_mini_spike_candidate,
    _is_low_contrast_paired_up_mini_spike_candidate,
    _is_low_border_side_mini_spike_candidate,
    _is_low_border_side_mini_spike_patch,
    _is_mixed_cluster_up_mini_spike_candidate,
    _is_ultra_faint_left_mini_spike_candidate,
    _is_low_signal_supported_full_spike_candidate,
    _is_residual_mini_spike_noise_candidate,
    _is_outline_apple_component,
    _is_pale_outline_apple_room,
    _is_supported_full_spike_candidate,
    _is_up_spike_full_step_continuation_patch,
    _is_up_spike_half_step_continuation_patch,
    _has_full_spike_perpendicular_neighbor,
    _count_full_spike_perpendicular_neighbors,
    _is_ambiguous_right_full_spike_noise,
    _is_ambiguous_full_spike_noise,
    _is_block_heavy_full_spike_support_noise,
    _is_grid_shape_full_spike_candidate,
    _is_half_grid_full_spike_candidate,
    _is_nearby_half_grid_full_spike_candidate,
    _is_block_heavy_full_spike_candidate,
    _is_boundary_full_spike_candidate,
    _is_isolated_coherent_full_spike_candidate,
    _is_informative_raw_support_density,
    _is_low_texture_raw_support_candidate,
    _is_raw_primary_full_spike_candidate,
    _is_strong_ambiguous_raw_support_candidate,
    _is_supported_shape_full_spike_candidate,
    _is_low_signal_supported_full_spike_recovery,
    _normalize_full_spike_origin,
    _normalize_full_spike_detections,
    _outline_block_score,
    _patch_in_ranges,
    _prune_adaptive_block_noise,
    _prune_adaptive_weak_block_noise,
    _prune_isolated_weak_block_noise,
    _prune_dark_outline_low_signal_blocks,
    _prune_full_spike_shape_noise,
    _prune_isolated_weak_full_spike_noise,
    _prune_isolated_weak_full_spike_shape_noise,
    _prune_primary_isolated_full_spikes,
    _prune_sparse_off_grid_block_noise,
    _recover_dark_outline_supported_low_signal_blocks,
    _recover_dark_outline_long_low_signal_runs,
    _prune_duplicate_mini_spike_cells,
    _prune_recovered_full_spike_noise,
    _recover_full_spike_run_gaps,
    _recover_pruned_full_spikes,
    _recover_blocklike_full_spikes,
    _recover_axis_supported_mini_spikes,
    _recover_supported_block_cells,
    _recover_up_spike_lateral_continuations,
    _triangle_masks,
    _triangle_side_coverage,
    _value_in_range,
    _ColorProfile,
)
from jtool_scanner.image import RGBImage


class ScannerGeometryTests(unittest.TestCase):
    def test_full_spike_rejects_blocklike_weak_outline_candidate(self) -> None:
        block = _GeometryClass("block", OBJ_BLOCK, 0.50)
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.535,
            direction_margin=0.12,
            outline_delta=0.22,
        )

        self.assertFalse(_accept_full_spike(spike, block))

    def test_full_spike_accepts_clear_outline_candidate(self) -> None:
        block = _GeometryClass("block", OBJ_BLOCK, 0.50)
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.535,
            direction_margin=0.12,
            outline_delta=0.30,
        )

        self.assertTrue(_accept_full_spike(spike, block))

    def test_off_grid_full_spike_support_requires_substantial_directional_shape(self) -> None:
        accepted = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.36, 0.08, 0.14)
        weak_score = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.29, 0.08, 0.14)
        weak_margin = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.36, 0.03, 0.14)
        weak_outline = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.36, 0.08, 0.09)

        self.assertTrue(_accept_full_spike_support(accepted))
        self.assertFalse(_accept_full_spike_support(weak_score))
        self.assertFalse(_accept_full_spike_support(weak_margin))
        self.assertFalse(_accept_full_spike_support(weak_outline))

    def test_full_spike_support_markers_are_not_emitted_at_final_boundary(self) -> None:
        image = RGBImage(1, 1, b"\x00\x00\x00")
        support = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            72,
            104,
            0.70,
            Box(72, 104, 32, 32),
        )
        regular = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            64,
            96,
            0.80,
            Box(64, 96, 32, 32),
        )

        result = _prune_full_spike_shape_noise(
            [support, regular],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertEqual(result, [regular])

    def test_isolated_weak_full_spike_noise_requires_same_direction_neighbor(self) -> None:
        isolated = Detection("spike_up", OBJ_SPIKE_UP, 64, 64, 0.24, Box(64, 64, 32, 32))
        supported = Detection("spike_up", OBJ_SPIKE_UP, 96, 64, 0.24, Box(96, 64, 32, 32))
        second_supported = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            32,
            64,
            0.24,
            Box(32, 64, 32, 32),
        )
        other_direction = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            64,
            96,
            0.24,
            Box(64, 96, 32, 32),
        )

        result = _prune_isolated_weak_full_spike_noise(
            [isolated, supported, second_supported, other_direction]
        )

        self.assertIn(isolated, result)
        self.assertNotIn(supported, result)
        self.assertNotIn(
            isolated,
            _prune_isolated_weak_full_spike_noise([isolated, other_direction]),
        )
        diagonal_neighbor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            80,
            80,
            0.24,
            Box(80, 80, 32, 32),
        )
        self.assertNotIn(
            isolated,
            _prune_isolated_weak_full_spike_noise([isolated, diagonal_neighbor]),
        )
        self.assertNotIn(
            isolated,
            _prune_isolated_weak_full_spike_noise([isolated, supported]),
        )
        stronger_isolated = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            64,
            64,
            0.27,
            Box(64, 64, 32, 32),
        )
        self.assertIn(
            stronger_isolated,
            _prune_isolated_weak_full_spike_noise([stronger_isolated, supported]),
        )

    def test_weak_full_spike_shape_recovery_requires_coherent_triangle(self) -> None:
        image = _textured_test_image()
        room = Box(0, 0, 800, 608)
        weak = Detection("spike_up", OBJ_SPIKE_UP, 64, 64, 0.25, Box(64, 64, 32, 32))

        self.assertFalse(_is_weak_full_spike_shape_recovery(weak, image, room))
        self.assertFalse(
            _is_weak_full_spike_shape_recovery(
                Detection("full_spike_support", OBJ_SPIKE_UP, 64, 64, 0.25, Box(64, 64, 32, 32)),
                image,
                room,
            )
        )

    def test_strong_full_spike_shape_requires_margin_over_block_texture(self) -> None:
        spike = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.60, 0.12, 0.24)
        block = _GeometryClass("block", OBJ_BLOCK, 0.45)
        patch = _PatchFeatures((), edge_density=0.30, border_score=0.20, center_score=0.40)

        self.assertTrue(_is_strong_full_spike_shape_candidate(spike, block, patch, 0.80))
        self.assertFalse(
            _is_strong_full_spike_shape_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.55),
                patch,
                0.80,
            )
        )

    def test_strong_offgrid_full_spike_shape_rejects_block_heavy_patch(self) -> None:
        spike = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.45, 0.10, 0.16)
        patch = _PatchFeatures((), edge_density=0.24, border_score=0.20, center_score=0.30)

        self.assertTrue(
            _is_strong_offgrid_full_spike_shape(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.40),
                patch,
                0.75,
            )
        )
        self.assertFalse(
            _is_strong_offgrid_full_spike_shape(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.56),
                patch,
                0.75,
            )
        )

    def test_weak_full_spike_run_shape_keeps_only_supported_texture(self) -> None:
        spike = _GeometryClass("spike_up", OBJ_SPIKE_UP, 0.30, 0.05, 0.16)
        patch = _PatchFeatures((), edge_density=0.26, border_score=0.18, center_score=0.25)

        self.assertTrue(
            _is_weak_full_spike_run_shape(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.35),
                patch,
                0.70,
            )
        )
        self.assertFalse(
            _is_weak_full_spike_run_shape(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.45),
                patch,
                0.70,
            )
        )

    def test_weak_two_neighbor_support_noise_requires_block_heavy_ambiguity(self) -> None:
        image = _textured_test_image()
        support = Detection("full_spike_support", OBJ_SPIKE_UP, 64, 64, 0.40, Box(64, 64, 32, 32))
        self.assertFalse(
            _is_weak_two_neighbor_support_noise(support, image, Box(0, 0, 800, 608), 1)
        )

    def test_weak_full_spike_run_anchor_uses_perpendicular_axis(self) -> None:
        anchor = Detection("spike_up", OBJ_SPIKE_UP, 112, 64, 0.40, Box(112, 64, 32, 32))
        self.assertTrue(_has_full_spike_run_anchor(OBJ_SPIKE_UP, 64, 64, anchor))
        self.assertEqual(_full_spike_run_distance(OBJ_SPIKE_UP, 64, 64, anchor), 48)
        self.assertFalse(_has_full_spike_run_anchor(OBJ_SPIKE_UP, 64, 80, anchor))

    def test_full_spike_support_requires_perpendicular_same_direction_run(self) -> None:
        up_a = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            64,
            64,
            0.30,
            Box(64, 64, 32, 32),
        )
        up_b = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            112,
            64,
            0.30,
            Box(112, 64, 32, 32),
        )
        up_axis_neighbor = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            64,
            112,
            0.30,
            Box(64, 112, 32, 32),
        )
        down = Detection(
            "full_spike_support",
            OBJ_SPIKE_DOWN,
            64,
            64,
            0.30,
            Box(64, 64, 32, 32),
        )

        self.assertTrue(_has_full_spike_perpendicular_neighbor(up_a, [up_a, up_b]))
        self.assertEqual(
            _count_full_spike_perpendicular_neighbors(up_a, [up_a, up_b]),
            1,
        )
        self.assertFalse(
            _has_full_spike_perpendicular_neighbor(up_a, [up_a, up_axis_neighbor])
        )
        self.assertFalse(_has_full_spike_perpendicular_neighbor(up_a, [up_a, down]))

    def test_pruned_full_spike_recovery_uses_offset_tolerant_run_support(self) -> None:
        image = RGBImage(1, 1, b"\x00\x00\x00")
        room = Box(0, 0, 800, 608)
        candidate = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            64,
            64,
            0.35,
            Box(64, 64, 32, 32),
        )
        anchor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            160,
            72,
            0.70,
            Box(160, 72, 32, 32),
        )
        patch = _PatchFeatures((), edge_density=0.24, border_score=0.20, center_score=0.35)
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.40,
            direction_margin=0.08,
            outline_delta=0.20,
        )
        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=spike),
            mock.patch(
                "jtool_scanner.scanner._classify_block",
                return_value=_GeometryClass("block", OBJ_BLOCK, 0.30),
            ),
            mock.patch("jtool_scanner.scanner._triangle_side_coverage", return_value=0.50),
        ):
            result = _recover_pruned_full_spikes(
                [candidate, anchor],
                [anchor],
                image,
                room,
            )

        self.assertIn(candidate, result)
        self.assertIn(anchor, result)

    def test_pruned_full_spike_recovery_rejects_unsupported_weak_candidate(self) -> None:
        image = RGBImage(1, 1, b"\x00\x00\x00")
        room = Box(0, 0, 800, 608)
        candidate = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            64,
            64,
            0.35,
            Box(64, 64, 32, 32),
        )
        patch = _PatchFeatures((), edge_density=0.24, border_score=0.20, center_score=0.35)
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.40,
            direction_margin=0.05,
            outline_delta=0.12,
        )
        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=spike),
            mock.patch(
                "jtool_scanner.scanner._classify_block",
                return_value=_GeometryClass("block", OBJ_BLOCK, 0.30),
            ),
            mock.patch("jtool_scanner.scanner._triangle_side_coverage", return_value=0.50),
        ):
            result = _recover_pruned_full_spikes(
                [candidate],
                [],
                image,
                room,
            )

        self.assertNotIn(candidate, result)

    def test_ambiguous_full_spike_noise_uses_score_and_orientation_gates(self) -> None:
        image = RGBImage(1, 1, b"\x00\x00\x00")
        room = Box(0, 0, 800, 608)
        patch = _PatchFeatures((), edge_density=0.35, border_score=0.20, center_score=0.35)
        weak_ambiguous = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            64,
            64,
            0.40,
            Box(64, 64, 32, 32),
        )
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.40,
            direction_margin=0.05,
            outline_delta=0.20,
        )
        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=spike),
        ):
            self.assertTrue(_is_ambiguous_full_spike_noise(weak_ambiguous, image, room))
            self.assertFalse(
                _is_ambiguous_full_spike_noise(
                    Detection(
                        "spike_up",
                        OBJ_SPIKE_UP,
                        64,
                        64,
                        0.50,
                        Box(64, 64, 32, 32),
                    ),
                    image,
                    room,
                )
            )
            self.assertFalse(
                _is_ambiguous_full_spike_noise(
                    Detection(
                        "spike_down",
                        OBJ_SPIKE_DOWN,
                        64,
                        64,
                        0.40,
                        Box(64, 64, 32, 32),
                    ),
                    image,
                    room,
                )
            )

    def test_final_support_noise_requires_block_dominance_and_weak_orientation(self) -> None:
        image = RGBImage(1, 1, b"\x00\x00\x00")
        room = Box(0, 0, 800, 608)
        support = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            64,
            64,
            0.50,
            Box(64, 64, 32, 32),
        )
        patch = _PatchFeatures((), edge_density=0.40, border_score=0.20, center_score=0.35)
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.45,
            direction_margin=0.10,
            outline_delta=0.20,
        )
        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=spike),
            mock.patch(
                "jtool_scanner.scanner._classify_block",
                return_value=_GeometryClass("block", OBJ_BLOCK, 0.50),
            ),
        ):
            self.assertTrue(_is_block_heavy_full_spike_support_noise(support, image, room))

        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=spike),
            mock.patch(
                "jtool_scanner.scanner._classify_block",
                return_value=_GeometryClass("block", OBJ_BLOCK, 0.40),
            ),
        ):
            self.assertFalse(_is_block_heavy_full_spike_support_noise(support, image, room))

        weak_margin_spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.45,
            direction_margin=0.12,
            outline_delta=0.20,
        )
        with (
            mock.patch("jtool_scanner.scanner._patch_features", return_value=patch),
            mock.patch("jtool_scanner.scanner._classify_full_spike", return_value=weak_margin_spike),
            mock.patch(
                "jtool_scanner.scanner._classify_block",
                return_value=_GeometryClass("block", OBJ_BLOCK, 0.50),
            ),
        ):
            self.assertFalse(_is_block_heavy_full_spike_support_noise(support, image, room))

    def test_low_signal_supported_recovery_requires_provenance_and_run_support(self) -> None:
        supported = Detection(
            "full_spike_supported",
            OBJ_SPIKE_UP,
            64,
            64,
            0.24,
            Box(64, 64, 32, 32),
        )
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.30,
            direction_margin=0.02,
            outline_delta=0.10,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.40)
        patch = _PatchFeatures((), edge_density=0.16, border_score=0.20, center_score=0.35)

        self.assertTrue(
            _is_low_signal_supported_full_spike_recovery(
                supported,
                spike,
                block,
                patch,
                side_coverage=0.625,
                run_supported=True,
            )
        )
        self.assertFalse(
            _is_low_signal_supported_full_spike_recovery(
                supported,
                spike,
                block,
                patch,
                side_coverage=0.625,
                run_supported=False,
            )
        )
        self.assertFalse(
            _is_low_signal_supported_full_spike_recovery(
                Detection(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    64,
                    64,
                    0.24,
                    Box(64, 64, 32, 32),
                ),
                spike,
                block,
                patch,
                side_coverage=0.625,
                run_supported=True,
            )
        )
        self.assertFalse(
            _is_low_signal_supported_full_spike_recovery(
                supported,
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.21,
                    direction_margin=0.02,
                    outline_delta=0.10,
                ),
                block,
                patch,
                side_coverage=0.625,
                run_supported=True,
            )
        )

    def test_grid_shape_recovery_requires_run_and_triangle_shape(self) -> None:
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.22,
            direction_margin=0.06,
            outline_delta=0.12,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.20)
        patch = _PatchFeatures((), edge_density=0.18, border_score=0.20, center_score=0.35)

        self.assertTrue(
            _is_grid_shape_full_spike_candidate(
                spike,
                block,
                patch,
                side_coverage=0.625,
                run_supported=True,
            )
        )
        self.assertFalse(
            _is_grid_shape_full_spike_candidate(
                spike,
                block,
                patch,
                side_coverage=0.625,
                run_supported=False,
            )
        )
        self.assertFalse(
            _is_grid_shape_full_spike_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.23),
                patch,
                side_coverage=0.625,
                run_supported=True,
            )
        )

    def test_half_grid_recovery_requires_stronger_shape_and_run_support(self) -> None:
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.31,
            direction_margin=0.17,
            outline_delta=0.26,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.20)
        patch = _PatchFeatures((), edge_density=0.13, border_score=0.20, center_score=0.35)
        self.assertTrue(
            _is_half_grid_full_spike_candidate(
                spike,
                block,
                patch,
                side_coverage=0.51,
                run_supported=True,
            )
        )
        self.assertFalse(
            _is_half_grid_full_spike_candidate(
                spike,
                block,
                patch,
                side_coverage=0.51,
                run_supported=False,
            )
        )
        self.assertTrue(
            _is_nearby_half_grid_full_spike_candidate(
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.33,
                    direction_margin=0.11,
                    outline_delta=0.20,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.25),
                _PatchFeatures((), edge_density=0.13, border_score=0.20, center_score=0.35),
                side_coverage=0.51,
                nearby_supported=True,
            )
        )
        self.assertTrue(
            _is_block_heavy_full_spike_candidate(
                _GeometryClass(
                    "spike_left",
                    OBJ_SPIKE_LEFT,
                    0.48,
                    direction_margin=0.20,
                    outline_delta=0.29,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.35),
                _PatchFeatures((), edge_density=0.28, border_score=0.30, center_score=0.22),
                side_coverage=0.80,
                run_supported=True,
            )
        )
        self.assertFalse(
            _is_block_heavy_full_spike_candidate(
                _GeometryClass(
                    "spike_left",
                    OBJ_SPIKE_LEFT,
                    0.48,
                    direction_margin=0.20,
                    outline_delta=0.29,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.35),
                _PatchFeatures((), edge_density=0.28, border_score=0.30, center_score=0.22),
                side_coverage=0.80,
                run_supported=False,
            )
        )
        self.assertTrue(
            _is_boundary_full_spike_candidate(
                _GeometryClass(
                    "spike_right",
                    OBJ_SPIKE_RIGHT,
                    0.72,
                    direction_margin=0.08,
                    outline_delta=0.30,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.65),
                _PatchFeatures((), edge_density=0.42, border_score=0.35, center_score=0.70),
                side_coverage=0.80,
                x=480,
                y=0,
                nearby_supported=True,
            )
        )
        self.assertTrue(
            _is_isolated_coherent_full_spike_candidate(
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.47,
                    direction_margin=0.15,
                    outline_delta=0.37,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.34),
                _PatchFeatures((), edge_density=0.29, border_score=0.25, center_score=0.40),
                side_coverage=0.94,
            )
        )
        self.assertTrue(
            _is_supported_shape_full_spike_candidate(
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.41,
                    direction_margin=0.10,
                    outline_delta=0.26,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.32),
                _PatchFeatures((), edge_density=0.28, border_score=0.30, center_score=0.30),
                side_coverage=0.70,
            )
        )
        self.assertFalse(
            _is_supported_shape_full_spike_candidate(
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.41,
                    direction_margin=0.08,
                    outline_delta=0.26,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.32),
                _PatchFeatures((), edge_density=0.28, border_score=0.30, center_score=0.30),
                side_coverage=0.70,
            )
        )
        self.assertTrue(_is_informative_raw_support_density(0.30))
        self.assertTrue(_is_informative_raw_support_density(0.50))
        self.assertFalse(_is_informative_raw_support_density(0.22))
        self.assertFalse(_is_informative_raw_support_density(0.85))
        image_box = Box(0, 0, 32, 32)
        self.assertTrue(
            _is_raw_primary_full_spike_candidate(
                Detection("spike_left", OBJ_SPIKE_LEFT, 64, 64, 0.45, image_box)
            )
        )
        self.assertFalse(
            _is_raw_primary_full_spike_candidate(
                Detection("spike_left", OBJ_SPIKE_LEFT, 64, 64, 0.44, image_box)
            )
        )
        self.assertFalse(
            _is_raw_primary_full_spike_candidate(
                Detection("spike_down", OBJ_SPIKE_DOWN, 64, 64, 0.90, image_box)
            )
        )
        raw_support = Detection(
            "full_spike_support",
            OBJ_SPIKE_RIGHT,
            64,
            64,
            0.34,
            image_box,
        )
        self.assertTrue(
            _is_strong_ambiguous_raw_support_candidate(
                raw_support,
                _GeometryClass(
                    "spike_down",
                    OBJ_SPIKE_DOWN,
                    0.51,
                    direction_margin=0.16,
                    outline_delta=0.27,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.46),
                _PatchFeatures((), edge_density=0.33, border_score=0.30, center_score=0.30),
                side_coverage=0.625,
            )
        )
        self.assertTrue(
            _is_low_texture_raw_support_candidate(
                Detection(
                    "full_spike_support",
                    OBJ_SPIKE_UP,
                    64,
                    64,
                    0.34,
                    image_box,
                ),
                _GeometryClass(
                    "spike_up",
                    OBJ_SPIKE_UP,
                    0.27,
                    direction_margin=0.13,
                    outline_delta=0.18,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.29),
                _PatchFeatures((), edge_density=0.27, border_score=0.20, center_score=0.20),
                side_coverage=0.375,
            )
        )

    def test_full_spike_origin_normalization_snaps_stable_axis_only(self) -> None:
        self.assertEqual(
            _normalize_full_spike_origin(OBJ_SPIKE_UP, 164, 73),
            (160, 73),
        )
        self.assertEqual(
            _normalize_full_spike_origin(OBJ_SPIKE_DOWN, 167, 73),
            (160, 73),
        )
        self.assertEqual(
            _normalize_full_spike_origin(OBJ_SPIKE_LEFT, 164, 73),
            (164, 80),
        )
        self.assertEqual(
            _normalize_full_spike_origin(OBJ_SPIKE_RIGHT, 164, 73),
            (164, 80),
        )

    def test_shape_recovery_preserves_half_grid_origin(self) -> None:
        image_box = Box(0, 0, 32, 32)
        shape = Detection(
            "full_spike_shape_recovery",
            OBJ_SPIKE_UP,
            168,
            73,
            0.5,
            image_box,
        )
        primary = Detection("spike_up", OBJ_SPIKE_UP, 168, 73, 0.5, image_box)
        normalized = _normalize_full_spike_detections([shape, primary])
        self.assertEqual((normalized[0].x, normalized[0].y), (168, 73))
        self.assertEqual((normalized[1].x, normalized[1].y), (160, 73))

    def test_normalized_full_spike_dedupe_removes_same_direction_duplicate(self) -> None:
        strong = Detection("spike_up", OBJ_SPIKE_UP, 64, 96, 0.80, Box(64, 96, 32, 32))
        weak = Detection("spike_up", OBJ_SPIKE_UP, 72, 104, 0.50, Box(72, 104, 32, 32))
        other_direction = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            72,
            104,
            0.40,
            Box(72, 104, 32, 32),
        )

        result = _dedupe_normalized_full_spikes([weak, other_direction, strong])

        self.assertEqual(
            [(det.type_id, det.x, det.y) for det in result],
            [
                (OBJ_SPIKE_DOWN, 72, 104),
                (OBJ_SPIKE_UP, 64, 96),
            ],
        )

    def test_geometry_dedupe_prefers_primary_grid_spike_over_support_marker(self) -> None:
        primary = Detection("spike_up", OBJ_SPIKE_UP, 480, 256, 0.54, Box(480, 256, 32, 32))
        support = Detection(
            "full_spike_support",
            OBJ_SPIKE_UP,
            480,
            272,
            0.65,
            Box(480, 272, 32, 32),
        )

        result = _dedupe_geometry([support, primary])

        self.assertEqual(result, [primary])

    def test_strong_mini_geometry_survives_full_overlap_noise_prune(self) -> None:
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.64,
                0.84,
                0.33,
                0.55,
                3,
                7,
                1,
                7,
            )
        )

    def test_isolated_weak_full_spike_shape_noise_is_pruned(self) -> None:
        weak = Detection(
            "spike_right",
            OBJ_SPIKE_RIGHT,
            480,
            256,
            0.35,
            Box(480, 256, 32, 32),
        )
        result = _prune_isolated_weak_full_spike_shape_noise(
            [weak],
            _textured_test_image(),
            Box(0, 0, 800, 608),
        )
        self.assertEqual(result, [])

    def test_primary_isolated_full_spike_prune_preserves_run_and_strong_shape(self) -> None:
        weak = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            480,
            256,
            0.60,
            Box(480, 256, 32, 32),
        )
        run_neighbor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            528,
            256,
            0.60,
            Box(528, 256, 32, 32),
        )
        with mock.patch(
            "jtool_scanner.scanner._classify_block",
            return_value=_GeometryClass("block", OBJ_BLOCK, 0.70),
        ), mock.patch(
            "jtool_scanner.scanner._triangle_side_coverage",
            return_value=0.40,
        ):
            result = _prune_primary_isolated_full_spikes(
                [weak],
                _textured_test_image(),
                Box(0, 0, 800, 608),
            )
        self.assertEqual(result, [])

        strong = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            480,
            256,
            0.60,
            Box(480, 256, 32, 32),
        )
        with mock.patch(
            "jtool_scanner.scanner._classify_block",
            return_value=_GeometryClass("block", OBJ_BLOCK, 0.30),
        ), mock.patch(
            "jtool_scanner.scanner._triangle_side_coverage",
            return_value=0.80,
        ):
            result = _prune_primary_isolated_full_spikes(
                [strong],
                _textured_test_image(),
                Box(0, 0, 800, 608),
            )
        self.assertEqual(result, [strong])

        with mock.patch(
            "jtool_scanner.scanner._classify_block",
            return_value=_GeometryClass("block", OBJ_BLOCK, 0.70),
        ), mock.patch(
            "jtool_scanner.scanner._triangle_side_coverage",
            return_value=0.40,
        ):
            result = _prune_primary_isolated_full_spikes(
                [weak, run_neighbor],
                _textured_test_image(),
                Box(0, 0, 800, 608),
            )
        self.assertEqual(result, [weak, run_neighbor])

    def test_final_full_spike_prune_removes_low_score_and_tight_duplicate(self) -> None:
        strong = Detection("spike_up", OBJ_SPIKE_UP, 64, 96, 0.80, Box(64, 96, 32, 32))
        duplicate = Detection("spike_up", OBJ_SPIKE_UP, 68, 100, 0.50, Box(68, 100, 32, 32))
        low_score = Detection("spike_left", OBJ_SPIKE_LEFT, 192, 128, 0.24, Box(192, 128, 32, 32))
        nearby_other_direction = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            68,
            100,
            0.40,
            Box(68, 100, 32, 32),
        )
        save = Detection("save", OBJ_SAVE, 224, 192, 1.00, Box(224, 192, 32, 32))

        result = _prune_recovered_full_spike_noise(
            [duplicate, low_score, nearby_other_direction, save, strong]
        )

        self.assertEqual(
            [(det.type_id, det.x, det.y) for det in result],
            [
                (OBJ_SPIKE_DOWN, 64, 100),
                (OBJ_SAVE, 224, 192),
                (OBJ_SPIKE_UP, 64, 96),
            ],
        )

    def test_duplicate_mini_spike_cell_prune_keeps_highest_score_candidate(self) -> None:
        weak = Detection(
            "mini_spike_up",
            OBJ_MINI_SPIKE_UP,
            96,
            128,
            0.60,
            Box(96, 128, 16, 16),
        )
        strong = Detection(
            "mini_spike_down",
            OBJ_MINI_SPIKE_DOWN,
            96,
            128,
            0.80,
            Box(96, 128, 16, 16),
        )
        separate = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            112,
            128,
            0.50,
            Box(112, 128, 16, 16),
        )

        result = _prune_duplicate_mini_spike_cells([weak, separate, strong])

        self.assertEqual(
            [(det.type_id, det.x, det.y) for det in result],
            [
                (OBJ_MINI_SPIKE_LEFT, 112, 128),
                (OBJ_MINI_SPIKE_DOWN, 96, 128),
            ],
        )

    def test_blocklike_mini_spike_noise_candidate_uses_broad_and_directional_cuts(
        self,
    ) -> None:
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_UP,
                0.90,
                0.50,
                0.0,
                0.0,
                4,
                0,
                4,
                0,
            )
        )
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.78,
                0.50,
                0.0,
                -0.1,
                4,
                0,
                4,
                0,
            )
        )
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.78,
                0.50,
                0.0,
                -0.1,
                4,
                0,
                4,
                0,
            )
        )
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.90,
                0.86,
                0.2,
                0.09,
                0,
                3,
                1,
                4,
            )
        )
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.90,
                0.86,
                0.2,
                0.09,
                0,
                3,
                1,
                4,
            )
        )
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.50,
                0.90,
                0.2,
                0.2,
                0,
                7,
                1,
                0,
            )
        )
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.74,
                0.76,
                0.0,
                0.0,
                4,
                0,
                1,
                0,
            )
        )
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.74,
                0.84,
                0.08,
                0.12,
                4,
                0,
                2,
                0,
            )
        )
        self.assertTrue(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.83,
                0.90,
                0.2,
                0.2,
                4,
                0,
                1,
                0,
            )
        )
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.82,
                0.90,
                0.2,
                0.2,
                4,
                0,
                1,
                0,
            )
        )
        self.assertFalse(
            _is_blocklike_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_UP,
                0.89,
                0.90,
                0.2,
                0.2,
                4,
                0,
                1,
                0,
            )
        )

    def test_residual_mini_spike_noise_candidate_prunes_supported_false_shapes(
        self,
    ) -> None:
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.92,
                0.88,
                0.08,
                0.20,
                0,
                0,
                5,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.65,
                0.70,
                0.15,
                0.40,
                0,
                0,
                3,
                3,
                2,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.65,
                0.70,
                0.15,
                0.40,
                0,
                0,
                3,
                3,
                2,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.65,
                0.70,
                0.15,
                0.40,
                1,
                1,
                3,
                3,
                2,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.40,
                0.30,
                0.18,
                0.50,
                0,
                0,
                5,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.40,
                0.50,
                0.20,
                0.50,
                0,
                0,
                5,
                2,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_UP,
                0.72,
                0.80,
                0.08,
                0.35,
                0,
                0,
                4,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.55,
                0.60,
                0.08,
                0.20,
                0,
                0,
                2,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_UP,
                0.50,
                0.72,
                0.20,
                0.50,
                0,
                0,
                2,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.50,
                0.60,
                0.10,
                0.20,
                0,
                0,
                4,
                2,
                1,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.40,
                0.65,
                0.20,
                0.50,
                0,
                0,
                0,
                0,
                0,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.70,
                0.70,
                0.10,
                0.15,
                0,
                0,
                4,
                3,
                2,
            )
        )
        self.assertTrue(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.40,
                0.80,
                0.20,
                0.50,
                0,
                0,
                5,
                0,
                0,
            )
        )

        self.assertFalse(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_UP,
                0.90,
                0.72,
                -0.05,
                -0.02,
                1,
                2,
                6,
                0,
                0,
            )
        )
        self.assertFalse(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_RIGHT,
                0.12,
                0.20,
                0.0,
                0.05,
                0,
                0,
                0,
                0,
                0,
            )
        )
        self.assertFalse(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_LEFT,
                0.80,
                0.70,
                -0.04,
                0.15,
                1,
                1,
                4,
                1,
                3,
            )
        )
        self.assertFalse(
            _is_residual_mini_spike_noise_candidate(
                OBJ_MINI_SPIKE_DOWN,
                0.88,
                0.86,
                0.07,
                0.22,
                1,
                1,
                1,
                2,
                3,
            )
        )

    def test_diagonal_right_mini_step_support_requires_half_step_pair(self) -> None:
        candidate = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            112,
            544,
            0.70,
            Box(112, 544, 16, 16),
        )
        diagonal_support = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            96,
            512,
            0.65,
            Box(96, 512, 16, 16),
        )
        vertical_only = Detection(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            112,
            512,
            0.65,
            Box(112, 512, 16, 16),
        )

        self.assertTrue(
            _has_diagonal_right_mini_step_support(
                candidate,
                [candidate, diagonal_support],
            )
        )
        self.assertFalse(
            _has_diagonal_right_mini_step_support(
                candidate,
                [candidate, vertical_only],
            )
        )

    def test_axis_left_mini_step_support_requires_vertical_half_step_pair(self) -> None:
        candidate = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            304,
            384,
            0.70,
            Box(304, 384, 16, 16),
        )
        vertical_support = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            304,
            416,
            0.65,
            Box(304, 416, 16, 16),
        )
        diagonal_only = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            320,
            416,
            0.65,
            Box(320, 416, 16, 16),
        )

        self.assertTrue(
            _has_axis_left_mini_step_support(
                candidate,
                [candidate, vertical_support],
            )
        )
        self.assertFalse(
            _has_axis_left_mini_step_support(
                candidate,
                [candidate, diagonal_only],
            )
        )

    def test_adaptive_block_noise_prunes_bimodal_dense_room(self) -> None:
        weak = [
            Detection("block", OBJ_BLOCK, x * 32, 0, 0.35, Box(x * 32, 0, 32, 32))
            for x in range(192)
        ]
        strong = [
            Detection(
                "block",
                OBJ_BLOCK,
                (x + 192) * 32,
                0,
                0.80,
                Box((x + 192) * 32, 0, 32, 32),
            )
            for x in range(64)
        ]
        mini = Detection(
            "mini_spike_up",
            OBJ_MINI_SPIKE_UP,
            0,
            0,
            0.5,
            Box(0, 0, 16, 16),
        )

        result = _prune_adaptive_block_noise([*weak, *strong, mini])

        self.assertEqual(result, [*strong, mini])

    def test_isolated_weak_block_noise_keeps_supported_blocks(self) -> None:
        isolated = Detection("block", OBJ_BLOCK, 128, 0, 0.34, Box(128, 0, 32, 32))
        supported = Detection("block", OBJ_BLOCK, 32, 0, 0.34, Box(32, 0, 32, 32))
        strong = Detection("block", OBJ_BLOCK, 64, 0, 0.50, Box(64, 0, 32, 32))
        filler = [
            Detection("block", OBJ_BLOCK, 1000 + index * 64, 0, 0.50, Box(0, 0, 32, 32))
            for index in range(256)
        ]

        result = _prune_isolated_weak_block_noise([isolated, supported, strong, *filler])

        self.assertNotIn(isolated, result)
        self.assertIn(supported, result)
        self.assertIn(strong, result)

    def test_adaptive_weak_block_noise_keeps_non_block_objects(self) -> None:
        weak = [
            Detection("block", OBJ_BLOCK, index * 32, 0, 0.282, Box(0, 0, 32, 32))
            for index in range(192)
        ]
        strong = [
            Detection("block", OBJ_BLOCK, (index + 192) * 32, 0, 0.70, Box(0, 0, 32, 32))
            for index in range(64)
        ]
        mini = Detection(
            "mini_spike_up",
            OBJ_MINI_SPIKE_UP,
            0,
            0,
            0.282,
            Box(0, 0, 16, 16),
        )

        result = _prune_adaptive_weak_block_noise([*weak, *strong, mini])

        self.assertEqual(result, [*strong, mini])

    def test_adaptive_weak_block_noise_prunes_mid_signal_tail(self) -> None:
        weak = [
            Detection("block", OBJ_BLOCK, index * 32, 64, 0.34, Box(0, 0, 32, 32))
            for index in range(192)
        ]
        strong = [
            Detection("block", OBJ_BLOCK, (index + 192) * 32, 64, 0.52, Box(0, 0, 32, 32))
            for index in range(64)
        ]

        result = _prune_adaptive_weak_block_noise([*weak, *strong])

        self.assertEqual(result, strong)

    def test_adaptive_weak_block_noise_keeps_supported_boundary_tile(self) -> None:
        boundary = Detection("block", OBJ_BLOCK, 288, 0, 0.4998, Box(0, 0, 32, 32))
        support = Detection("block", OBJ_BLOCK, 256, 0, 0.54, Box(0, 0, 32, 32))
        filler = [
            Detection("block", OBJ_BLOCK, 1000 + index * 64, 64, 0.55, Box(0, 0, 32, 32))
            for index in range(256)
        ]

        result = _prune_adaptive_weak_block_noise([boundary, support, *filler])

        self.assertIn(boundary, result)

    def test_supported_block_cells_recover_a_strong_grid_gap(self) -> None:
        image = _textured_test_image()
        first = Detection("block", OBJ_BLOCK, 704, 480, 0.55, Box(704, 480, 32, 32))
        second = Detection("block", OBJ_BLOCK, 768, 480, 0.55, Box(768, 480, 32, 32))
        vertical = Detection("block", OBJ_BLOCK, 736, 448, 0.55, Box(736, 448, 32, 32))

        result = _recover_supported_block_cells(
            [first, second, vertical], image, Box(0, 0, 800, 608)
        )

        self.assertTrue(any(det.x == 736 and det.y == 480 for det in result))

    def test_sparse_off_grid_block_noise_removes_outliers(self) -> None:
        aligned = [
            Detection("block", OBJ_BLOCK, index * 32, 0, 0.5, Box(0, 0, 32, 32))
            for index in range(64)
        ]
        outliers = [
            Detection("block", OBJ_BLOCK, 2048 + index * 32, 8, 0.5, Box(0, 0, 32, 32))
            for index in range(2)
        ]

        result = _prune_sparse_off_grid_block_noise([*aligned, *outliers])

        self.assertEqual(result, aligned)

    def test_sparse_off_grid_block_noise_keeps_real_offset_population(self) -> None:
        aligned = [
            Detection("block", OBJ_BLOCK, index * 32, 0, 0.5, Box(0, 0, 32, 32))
            for index in range(64)
        ]
        outliers = [
            Detection("block", OBJ_BLOCK, 2048 + index * 32, 8, 0.5, Box(0, 0, 32, 32))
            for index in range(4)
        ]

        result = _prune_sparse_off_grid_block_noise([*aligned, *outliers])

        self.assertEqual(result, [*aligned, *outliers])

    def test_dark_outline_low_signal_prune_keeps_other_objects(self) -> None:
        weak = [
            Detection("block", OBJ_BLOCK, index * 32, 0, 0.282, Box(0, 0, 32, 32))
            for index in range(192)
        ]
        strong = [
            Detection("block", OBJ_BLOCK, (index + 192) * 32, 0, 0.80, Box(0, 0, 32, 32))
            for index in range(64)
        ]
        mini = Detection("mini_spike_up", OBJ_MINI_SPIKE_UP, 0, 0, 0.282, Box(0, 0, 16, 16))

        result = _prune_dark_outline_low_signal_blocks([*weak, *strong, mini])

        self.assertEqual(result, [*strong, mini])

    def test_dark_outline_supported_low_signal_recovery_uses_hollow_edges(self) -> None:
        image = _textured_test_image()
        candidate = Detection("block", OBJ_BLOCK, 64, 64, 0.282, Box(64, 64, 32, 32))
        result = _recover_dark_outline_supported_low_signal_blocks(
            [candidate], [], image, Box(0, 0, 800, 608)
        )

        self.assertEqual(result, [])

    def test_dark_outline_long_run_recovery_fills_faint_interior_cells(self) -> None:
        image = _textured_test_image()
        anchors = [
            Detection("block", OBJ_BLOCK, 96, 0, 0.50, Box(96, 0, 32, 32)),
            Detection("block", OBJ_BLOCK, 96, 128, 0.50, Box(96, 128, 32, 32)),
        ]
        faint_patch = _PatchFeatures((), 0.02, 0.0, 0.0)
        with mock.patch(
            "jtool_scanner.scanner._is_dark_outline_room",
            return_value=True,
        ), mock.patch(
            "jtool_scanner.scanner._patch_features",
            return_value=faint_patch,
        ):
            result = _recover_dark_outline_long_low_signal_runs(
                anchors,
                image,
                Box(0, 0, 800, 608),
            )

        self.assertEqual(
            {(det.x, det.y) for det in result if det.type_id == OBJ_BLOCK},
            {(96, 0), (96, 32), (96, 64), (96, 96), (96, 128)},
        )

    def test_full_spike_run_gap_recovery_fills_same_direction_midpoint(self) -> None:
        image = _textured_test_image()
        first = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            192,
            208,
            0.55,
            Box(192, 208, 32, 32),
        )
        second = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            256,
            208,
            0.50,
            Box(256, 208, 32, 32),
        )

        result = _recover_full_spike_run_gaps(
            [first, second],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertIn(
            (OBJ_SPIKE_UP, 224, 208),
            [(det.type_id, det.x, det.y) for det in result],
        )

    def test_full_spike_run_gap_recovery_keeps_existing_midpoint_unique(self) -> None:
        image = _textured_test_image()
        detections = [
            Detection(
                "spike_up",
                OBJ_SPIKE_UP,
                192,
                208,
                0.55,
                Box(192, 208, 32, 32),
            ),
            Detection(
                "spike_up",
                OBJ_SPIKE_UP,
                224,
                208,
                0.60,
                Box(224, 208, 32, 32),
            ),
            Detection(
                "spike_up",
                OBJ_SPIKE_UP,
                256,
                208,
                0.50,
                Box(256, 208, 32, 32),
            ),
        ]

        result = _recover_full_spike_run_gaps(
            detections,
            image,
            Box(0, 0, 800, 608),
        )

        self.assertEqual(
            1,
            sum(
                1
                for det in result
                if det.type_id == OBJ_SPIKE_UP and det.x == 224 and det.y == 208
            ),
        )

    def test_full_spike_run_gap_patch_requires_textured_midpoint(self) -> None:
        self.assertTrue(
            _is_full_spike_run_gap_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.35,
                    border_score=0.20,
                    center_score=0.25,
                )
            )
        )
        self.assertFalse(
            _is_full_spike_run_gap_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.34,
                    border_score=0.20,
                    center_score=0.25,
                )
            )
        )

    def test_blocklike_full_spike_recovery_requires_medium_center_body(self) -> None:
        spike = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.39,
            direction_margin=0.06,
            outline_delta=0.11,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.40)
        patch = _PatchFeatures(
            (),
            edge_density=0.30,
            border_score=0.20,
            center_score=0.25,
        )

        self.assertTrue(
            _is_blocklike_full_spike_recovery_candidate(spike, block, patch)
        )
        self.assertFalse(
            _is_blocklike_full_spike_recovery_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.46),
                patch,
            )
        )
        self.assertFalse(
            _is_blocklike_full_spike_recovery_candidate(
                spike,
                block,
                _PatchFeatures(
                    (),
                    edge_density=0.30,
                    border_score=0.20,
                    center_score=0.40,
                ),
            )
        )

    def test_blocklike_full_spike_recovery_uses_same_direction_support(self) -> None:
        image = _textured_test_image()
        supported = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            224,
            96,
            0.55,
            Box(224, 96, 32, 32),
        )

        result = _recover_blocklike_full_spikes(
            [supported],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertTrue(
            any(
                det.type_id == OBJ_SPIKE_UP
                and 128 <= det.x <= 320
                and det.y == 96
                for det in result
            )
        )

    def test_edge_full_spike_continuation_anchor_requires_facing_room_edge(self) -> None:
        left_edge = Detection(
            "spike_left",
            OBJ_SPIKE_LEFT,
            0,
            192,
            0.75,
            Box(0, 192, 32, 32),
        )
        right_edge = Detection(
            "spike_right",
            OBJ_SPIKE_RIGHT,
            768,
            192,
            0.75,
            Box(768, 192, 32, 32),
        )
        interior = Detection(
            "spike_left",
            OBJ_SPIKE_LEFT,
            32,
            192,
            0.75,
            Box(32, 192, 32, 32),
        )
        weak = Detection(
            "spike_left",
            OBJ_SPIKE_LEFT,
            0,
            192,
            0.74,
            Box(0, 192, 32, 32),
        )

        self.assertTrue(_is_edge_full_spike_continuation_anchor(left_edge))
        self.assertTrue(_is_edge_full_spike_continuation_anchor(right_edge))
        self.assertFalse(_is_edge_full_spike_continuation_anchor(interior))
        self.assertFalse(_is_edge_full_spike_continuation_anchor(weak))

    def test_edge_full_spike_continuation_patch_requires_texture(self) -> None:
        self.assertTrue(
            _is_edge_full_spike_continuation_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.35,
                    border_score=0.20,
                    center_score=0.25,
                )
            )
        )
        self.assertFalse(
            _is_edge_full_spike_continuation_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.34,
                    border_score=0.20,
                    center_score=0.25,
                )
            )
        )

    def test_bottom_edge_up_spike_continuation_anchor_requires_bottom_half_step(self) -> None:
        anchor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            160,
            568,
            0.44,
            Box(160, 568, 32, 32),
        )
        wrong_y = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            160,
            560,
            0.44,
            Box(160, 560, 32, 32),
        )
        weak = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            160,
            568,
            0.43,
            Box(160, 568, 32, 32),
        )

        self.assertTrue(_is_bottom_edge_up_spike_continuation_anchor(anchor))
        self.assertFalse(_is_bottom_edge_up_spike_continuation_anchor(wrong_y))
        self.assertFalse(_is_bottom_edge_up_spike_continuation_anchor(weak))

    def test_bottom_edge_up_spike_continuation_patch_requires_texture(self) -> None:
        self.assertTrue(
            _is_bottom_edge_up_spike_continuation_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.27,
                    border_score=0.15,
                    center_score=0.18,
                )
            )
        )
        self.assertFalse(
            _is_bottom_edge_up_spike_continuation_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.26,
                    border_score=0.15,
                    center_score=0.18,
                )
            )
        )

    def test_up_spike_half_step_continuation_patch_requires_strong_up_outline(self) -> None:
        self.assertTrue(
            _is_up_spike_half_step_continuation_patch(
                _up_outline_patch(
                    edge_density=0.37,
                    border_score=0.25,
                    center_score=0.45,
                )
            )
        )
        self.assertFalse(
            _is_up_spike_half_step_continuation_patch(
                _up_outline_patch(
                    edge_density=0.36,
                    border_score=0.25,
                    center_score=0.45,
                )
            )
        )

    def test_up_spike_full_step_continuation_patch_requires_dense_texture(self) -> None:
        self.assertTrue(
            _is_up_spike_full_step_continuation_patch(
                _up_outline_patch(
                    edge_density=0.48,
                    border_score=0.38,
                    center_score=0.58,
                )
            )
        )
        self.assertFalse(
            _is_up_spike_full_step_continuation_patch(
                _up_outline_patch(
                    edge_density=0.48,
                    border_score=0.38,
                    center_score=0.57,
                )
            )
        )

    def test_up_spike_lateral_continuation_recovers_half_step_run(self) -> None:
        image = _up_spike_test_image([(176, 208)])
        anchor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            192,
            208,
            0.44,
            Box(192, 208, 32, 32),
        )
        run_support = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            256,
            208,
            0.38,
            Box(256, 208, 32, 32),
        )

        result = _recover_up_spike_lateral_continuations(
            [anchor, run_support],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertIn(
            (OBJ_SPIKE_UP, 176, 208),
            [(det.type_id, det.x, det.y) for det in result],
        )

    def test_up_spike_lateral_continuation_recovers_strong_full_step(self) -> None:
        image = _up_spike_test_image([(448, 272)])
        anchor = Detection(
            "spike_up",
            OBJ_SPIKE_UP,
            480,
            272,
            0.60,
            Box(480, 272, 32, 32),
        )

        result = _recover_up_spike_lateral_continuations(
            [anchor],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertIn(
            (OBJ_SPIKE_UP, 448, 272),
            [(det.type_id, det.x, det.y) for det in result],
        )

    def test_patch_range_helper_accepts_values_inside_all_ranges(self) -> None:
        patch = _PatchFeatures((), edge_density=0.25, border_score=0.15, center_score=0.30)

        self.assertTrue(_value_in_range(0.25, (0.20, 0.30)))
        self.assertTrue(
            _patch_in_ranges(
                patch,
                (0.20, 0.30),
                (0.10, 0.20),
                (0.25, 0.35),
            )
        )
        self.assertFalse(_value_in_range(0.31, (0.20, 0.30)))
        self.assertFalse(
            _patch_in_ranges(
                patch,
                (0.26, 0.30),
                (0.10, 0.20),
                (0.25, 0.35),
            )
        )

    def test_left_spike_supports_require_counted_nearby_left_spikes(self) -> None:
        detections = [
            Detection("spike_left", OBJ_SPIKE_LEFT, 704, 96, 0.60, Box(704, 96, 32, 32)),
            Detection("spike_left", OBJ_SPIKE_LEFT, 568, 64, 0.55, Box(568, 64, 32, 32)),
            Detection("spike_left", OBJ_SPIKE_LEFT, 640, 160, 0.70, Box(640, 160, 32, 32)),
            Detection("spike_right", OBJ_SPIKE_RIGHT, 656, 64, 0.90, Box(656, 64, 32, 32)),
        ]

        self.assertTrue(_has_left_spike_supports(detections, 640, 64, 40, 80, 2))
        self.assertFalse(_has_left_spike_supports(detections, 640, 64, 40, 60, 2))
        self.assertFalse(_has_left_spike_supports(detections, 640, 64, 40, 80, 3))

    def test_outline_block_accepts_aligned_empty_center_patch(self) -> None:
        candidate = _GeometryPatchCandidate(
            32,
            64,
            _PatchFeatures((), edge_density=0.06, border_score=0.12, center_score=0.0),
            spike=None,
            block=_GeometryClass("block", OBJ_BLOCK, 0.20),
        )

        self.assertIsNotNone(_outline_block_score(candidate))

    def test_outline_block_rejects_off_grid_patch(self) -> None:
        candidate = _GeometryPatchCandidate(
            40,
            64,
            _PatchFeatures((), edge_density=0.06, border_score=0.12, center_score=0.0),
            spike=None,
            block=_GeometryClass("block", OBJ_BLOCK, 0.20),
        )

        self.assertIsNone(_outline_block_score(candidate))

    def test_mini_spike_rejects_blocklike_weak_direction_candidate(self) -> None:
        block = _GeometryClass("block", OBJ_BLOCK, 0.90)
        mini = _GeometryClass(
            "mini_spike_down",
            OBJ_MINI_SPIKE_DOWN,
            0.80,
            direction_margin=0.05,
            outline_delta=0.30,
        )

        self.assertFalse(_accept_mini_spike(mini, block))

    def test_mini_spike_accepts_blocklike_clear_direction_candidate(self) -> None:
        block = _GeometryClass("block", OBJ_BLOCK, 0.90)
        mini = _GeometryClass(
            "mini_spike_down",
            OBJ_MINI_SPIKE_DOWN,
            0.80,
            direction_margin=0.08,
            outline_delta=0.30,
        )

        self.assertTrue(_accept_mini_spike(mini, block))

    def test_axis_mini_spike_support_uses_same_direction_axis(self) -> None:
        detections = [
            Detection(
                "mini_spike_up",
                OBJ_MINI_SPIKE_UP,
                128,
                96,
                0.50,
                Box(128, 96, 16, 16),
            ),
            Detection(
                "mini_spike_left",
                OBJ_MINI_SPIKE_LEFT,
                320,
                240,
                0.50,
                Box(320, 240, 16, 16),
            ),
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                160,
                96,
                0.90,
                Box(160, 96, 16, 16),
            ),
        ]

        self.assertTrue(
            _has_axis_mini_spike_support(detections, OBJ_MINI_SPIKE_UP, 176, 96)
        )
        self.assertTrue(
            _has_axis_mini_spike_support(detections, OBJ_MINI_SPIKE_LEFT, 320, 288)
        )
        self.assertFalse(
            _has_axis_mini_spike_support(detections, OBJ_MINI_SPIKE_UP, 128, 144)
        )
        self.assertFalse(
            _has_axis_mini_spike_support(detections, OBJ_MINI_SPIKE_RIGHT, 224, 96)
        )

    def test_axis_supported_mini_spike_recovery_rejects_blocklike_noise(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.25,
            border_score=0.25,
            center_score=0.25,
        )
        mini = _GeometryClass(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            0.55,
            direction_margin=0.01,
            outline_delta=0.12,
        )

        self.assertTrue(
            _can_recover_axis_supported_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.50),
                patch,
            )
        )
        self.assertFalse(
            _can_recover_axis_supported_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.90),
                patch,
            )
        )

    def test_axis_supported_mini_spike_recovery_adds_supported_candidate(self) -> None:
        image = _mini_left_test_image([(128, 112)])
        support = Detection(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            128,
            64,
            0.60,
            Box(128, 64, 16, 16),
        )

        result = _recover_axis_supported_mini_spikes(
            [support],
            image,
            Box(0, 0, 800, 608),
        )

        self.assertIn(
            (OBJ_MINI_SPIKE_LEFT, 128, 112),
            [(det.type_id, det.x, det.y) for det in result],
        )

    def test_horizontal_side_mini_support_uses_strong_same_row_anchor(self) -> None:
        detections = [
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                656,
                592,
                0.80,
                Box(656, 592, 16, 16),
            ),
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                704,
                544,
                0.90,
                Box(704, 544, 16, 16),
            ),
        ]

        self.assertTrue(
            _has_horizontal_side_mini_spike_support(
                detections,
                OBJ_MINI_SPIKE_RIGHT,
                704,
                592,
            )
        )
        self.assertFalse(
            _has_horizontal_side_mini_spike_support(
                detections,
                OBJ_MINI_SPIKE_RIGHT,
                704,
                576,
            )
        )

    def test_horizontal_side_mini_recovery_requires_clear_side_shape(self) -> None:
        clear_patch = _PatchFeatures(
            (),
            edge_density=0.45,
            border_score=0.30,
            center_score=0.40,
        )
        weak_patch = _PatchFeatures(
            (),
            edge_density=0.39,
            border_score=0.30,
            center_score=0.40,
        )
        mini = _GeometryClass(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            0.60,
            direction_margin=0.01,
            outline_delta=0.19,
        )

        self.assertTrue(
            _can_recover_horizontal_side_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.50),
                clear_patch,
            )
        )
        self.assertFalse(
            _can_recover_horizontal_side_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.50),
                weak_patch,
            )
        )

    def test_diagonal_side_mini_support_uses_nearby_vertical_offset_anchor(self) -> None:
        detections = [
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                112,
                544,
                0.75,
                Box(112, 544, 16, 16),
            ),
            Detection(
                "mini_spike_right",
                OBJ_MINI_SPIKE_RIGHT,
                160,
                512,
                0.90,
                Box(160, 512, 16, 16),
            ),
        ]

        self.assertTrue(
            _has_diagonal_side_mini_spike_support(
                detections,
                OBJ_MINI_SPIKE_RIGHT,
                96,
                512,
            )
        )
        self.assertFalse(
            _has_diagonal_side_mini_spike_support(
                detections,
                OBJ_MINI_SPIKE_RIGHT,
                96,
                544,
            )
        )

    def test_diagonal_side_mini_recovery_requires_clear_side_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.36,
            border_score=0.30,
            center_score=0.46,
        )
        mini = _GeometryClass(
            "mini_spike_right",
            OBJ_MINI_SPIKE_RIGHT,
            0.53,
            direction_margin=0.0,
            outline_delta=0.29,
        )

        self.assertTrue(
            _can_recover_diagonal_side_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.60),
                patch,
            )
        )
        self.assertFalse(
            _can_recover_diagonal_side_mini_spike(
                _GeometryClass(
                    "mini_spike_right",
                    OBJ_MINI_SPIKE_RIGHT,
                    0.53,
                    direction_margin=-0.06,
                    outline_delta=0.29,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.66),
                patch,
            )
        )

    def test_extended_left_mini_support_uses_farther_vertical_offset_anchor(self) -> None:
        detections = [
            Detection(
                "mini_spike_left",
                OBJ_MINI_SPIKE_LEFT,
                576,
                528,
                0.68,
                Box(576, 528, 16, 16),
            ),
            Detection(
                "mini_spike_left",
                OBJ_MINI_SPIKE_LEFT,
                608,
                560,
                0.90,
                Box(608, 560, 16, 16),
            ),
        ]

        self.assertTrue(_has_extended_left_mini_spike_support(detections, 560, 592))
        self.assertFalse(_has_extended_left_mini_spike_support(detections, 560, 528))

    def test_extended_left_mini_recovery_requires_supported_left_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.41,
            border_score=0.30,
            center_score=0.46,
        )
        mini = _GeometryClass(
            "mini_spike_left",
            OBJ_MINI_SPIKE_LEFT,
            0.46,
            direction_margin=0.0,
            outline_delta=0.13,
        )

        self.assertTrue(
            _can_recover_extended_left_mini_spike(
                mini,
                _GeometryClass("block", OBJ_BLOCK, 0.60),
                patch,
            )
        )
        self.assertFalse(
            _can_recover_extended_left_mini_spike(
                _GeometryClass(
                    "mini_spike_left",
                    OBJ_MINI_SPIKE_LEFT,
                    0.46,
                    direction_margin=-0.06,
                    outline_delta=0.13,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.71),
                patch,
            )
        )

    def test_low_contrast_mini_up_candidate_requires_pairable_weak_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.08,
            border_score=0.05,
            center_score=0.12,
        )

        self.assertTrue(
            _is_low_contrast_mini_up_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.20),
                0.09,
                0.05,
            )
        )
        self.assertFalse(
            _is_low_contrast_mini_up_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.21),
                0.09,
                0.05,
            )
        )
        self.assertTrue(
            _has_low_contrast_mini_up_pair(
                {
                    (544, 112): 0.14,
                    (560, 112): 0.14,
                },
                544,
                112,
            )
        )
        self.assertFalse(
            _has_low_contrast_mini_up_pair(
                {
                    (544, 112): 0.14,
                    (592, 112): 0.14,
                },
                544,
                112,
            )
        )

    def test_adjacent_up_mini_candidate_requires_clear_up_pair_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.43,
            border_score=0.30,
            center_score=0.26,
        )
        mini = _GeometryClass(
            "mini_spike_up",
            OBJ_MINI_SPIKE_UP,
            0.48,
            direction_margin=0.01,
            outline_delta=0.04,
        )

        self.assertTrue(
            _is_adjacent_up_mini_spike_candidate(
                mini,
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.54),
            )
        )
        self.assertFalse(
            _is_adjacent_up_mini_spike_candidate(
                mini,
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.56),
            )
        )
        self.assertTrue(
            _has_adjacent_up_mini_spike_pair(
                {
                    (352, 304): 0.50,
                    (368, 304): 0.55,
                },
                352,
                304,
            )
        )
        self.assertFalse(
            _has_adjacent_up_mini_spike_pair(
                {
                    (352, 304): 0.50,
                    (400, 304): 0.55,
                },
                352,
                304,
            )
        )

    def test_dense_adjacent_up_mini_requires_textured_blocklike_neighbor(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.72,
            border_score=0.40,
            center_score=0.82,
        )

        self.assertTrue(
            _is_dense_adjacent_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.82),
                0.72,
                -0.04,
            )
        )
        self.assertFalse(
            _is_dense_adjacent_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.79),
                0.72,
                -0.04,
            )
        )
        self.assertTrue(
            _has_dense_adjacent_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_up",
                        OBJ_MINI_SPIKE_UP,
                        656,
                        560,
                        0.47,
                        Box(656, 560, 16, 16),
                    )
                ],
                672,
                560,
            )
        )
        self.assertFalse(
            _has_dense_adjacent_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_up",
                        OBJ_MINI_SPIKE_UP,
                        640,
                        560,
                        0.47,
                        Box(640, 560, 16, 16),
                    )
                ],
                672,
                560,
            )
        )

    def test_ambiguous_adjacent_up_mini_requires_paired_blocklike_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.43,
            border_score=0.30,
            center_score=0.44,
        )

        self.assertTrue(
            _is_ambiguous_adjacent_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.44),
                0.24,
                0.50,
            )
        )
        self.assertFalse(
            _is_ambiguous_adjacent_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.47),
                0.24,
                0.50,
            )
        )
        self.assertFalse(
            _is_ambiguous_adjacent_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.44),
                0.24,
                0.53,
            )
        )
        self.assertTrue(
            _has_ambiguous_adjacent_up_mini_spike_pair(
                {
                    (128, 112): 0.28,
                    (144, 112): 0.24,
                },
                128,
                112,
            )
        )
        self.assertFalse(
            _has_ambiguous_adjacent_up_mini_spike_pair(
                {
                    (128, 112): 0.28,
                    (176, 112): 0.24,
                },
                128,
                112,
            )
        )

    def test_mixed_cluster_up_mini_requires_right_and_down_support(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.51,
            border_score=0.40,
            center_score=0.56,
        )

        self.assertTrue(
            _is_mixed_cluster_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.57),
                0.41,
                0.59,
            )
        )
        self.assertFalse(
            _is_mixed_cluster_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.61),
                0.41,
                0.59,
            )
        )
        self.assertTrue(
            _has_mixed_cluster_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_right",
                        OBJ_MINI_SPIKE_RIGHT,
                        64,
                        160,
                        0.62,
                        Box(64, 160, 16, 16),
                    ),
                    Detection(
                        "mini_spike_down",
                        OBJ_MINI_SPIKE_DOWN,
                        48,
                        176,
                        0.85,
                        Box(48, 176, 16, 16),
                    ),
                ],
                48,
                144,
            )
        )
        self.assertFalse(
            _has_mixed_cluster_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_right",
                        OBJ_MINI_SPIKE_RIGHT,
                        64,
                        160,
                        0.62,
                        Box(64, 160, 16, 16),
                    )
                ],
                48,
                144,
            )
        )

    def test_border_supported_up_mini_requires_border_heavy_shape(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.34,
            border_score=0.36,
            center_score=0.24,
        )

        self.assertTrue(
            _is_border_supported_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.40),
                0.29,
                0.36,
            )
        )
        self.assertFalse(
            _is_border_supported_up_mini_spike_candidate(
                _PatchFeatures(
                    (),
                    edge_density=0.34,
                    border_score=0.24,
                    center_score=0.41,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.40),
                0.29,
                0.36,
            )
        )
        self.assertTrue(
            _has_border_supported_up_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        544,
                        144,
                        0.50,
                        Box(544, 144, 32, 32),
                    ),
                    Detection(
                        "spike_up",
                        OBJ_SPIKE_UP,
                        544,
                        144,
                        0.52,
                        Box(544, 144, 32, 32),
                    ),
                ],
                560,
                144,
            )
        )
        self.assertFalse(
            _has_border_supported_up_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        544,
                        144,
                        0.50,
                        Box(544, 144, 32, 32),
                    )
                ],
                560,
                144,
            )
        )

    def test_diagonal_anchor_up_mini_requires_strong_offset_anchor(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.07,
            border_score=0.15,
            center_score=0.0,
        )

        self.assertTrue(
            _is_diagonal_anchor_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.12),
                0.05,
                0.22,
            )
        )
        self.assertFalse(
            _is_diagonal_anchor_up_mini_spike_candidate(
                _PatchFeatures(
                    (),
                    edge_density=0.07,
                    border_score=0.15,
                    center_score=0.08,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.12),
                0.05,
                0.22,
            )
        )
        self.assertTrue(
            _has_diagonal_anchor_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_up",
                        OBJ_MINI_SPIKE_UP,
                        288,
                        528,
                        0.76,
                        Box(288, 528, 16, 16),
                    ),
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        288,
                        576,
                        0.88,
                        Box(288, 576, 32, 32),
                    ),
                ],
                272,
                560,
            )
        )
        self.assertFalse(
            _has_diagonal_anchor_up_mini_spike_support(
                [
                    Detection(
                        "mini_spike_up",
                        OBJ_MINI_SPIKE_UP,
                        288,
                        528,
                        0.76,
                        Box(288, 528, 16, 16),
                    )
                ],
                272,
                560,
            )
        )

    def test_low_contrast_paired_up_mini_requires_pair_and_support(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.09,
            border_score=0.08,
            center_score=0.11,
        )

        self.assertTrue(
            _is_low_contrast_paired_up_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.12),
                0.07,
                0.11,
            )
        )
        self.assertFalse(
            _is_low_contrast_paired_up_mini_spike_candidate(
                _PatchFeatures(
                    (),
                    edge_density=0.13,
                    border_score=0.08,
                    center_score=0.11,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.12),
                0.07,
                0.11,
            )
        )
        self.assertTrue(
            _has_low_contrast_paired_up_mini_spike_pair(
                {
                    (480, 272): 0.07,
                    (528, 272): 0.07,
                },
                480,
                272,
            )
        )
        self.assertFalse(
            _has_low_contrast_paired_up_mini_spike_pair(
                {
                    (480, 272): 0.07,
                    (512, 272): 0.07,
                },
                480,
                272,
            )
        )
        self.assertTrue(
            _has_low_contrast_paired_up_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        480,
                        288,
                        0.28,
                        Box(480, 288, 32, 32),
                    ),
                    Detection(
                        "spike_up",
                        OBJ_SPIKE_UP,
                        496,
                        256,
                        0.28,
                        Box(496, 256, 32, 32),
                    ),
                ],
                480,
                272,
            )
        )
        self.assertFalse(
            _has_low_contrast_paired_up_mini_spike_support(
                [
                    Detection(
                        "spike_up",
                        OBJ_SPIKE_UP,
                        496,
                        256,
                        0.28,
                        Box(496, 256, 32, 32),
                    )
                ],
                480,
                272,
            )
        )

    def test_low_border_side_mini_requires_sparse_block_support(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.09,
            border_score=0.05,
            center_score=0.12,
        )

        self.assertTrue(
            _is_low_border_side_mini_spike_patch(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.08),
                0.20,
            )
        )
        self.assertFalse(
            _is_low_border_side_mini_spike_patch(
                _PatchFeatures(
                    (),
                    edge_density=0.09,
                    border_score=0.09,
                    center_score=0.12,
                ),
                _GeometryClass("block", OBJ_BLOCK, 0.08),
                0.20,
            )
        )
        self.assertTrue(_is_low_border_side_mini_spike_candidate(0.11))
        self.assertFalse(_is_low_border_side_mini_spike_candidate(0.09))
        self.assertTrue(
            _has_low_border_side_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        0,
                        128,
                        0.30,
                        Box(0, 128, 32, 32),
                    ),
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        32,
                        160,
                        0.30,
                        Box(32, 160, 32, 32),
                    ),
                    Detection(
                        "spike_right",
                        OBJ_SPIKE_RIGHT,
                        24,
                        128,
                        0.30,
                        Box(24, 128, 32, 32),
                    ),
                ],
                32,
                128,
                OBJ_MINI_SPIKE_RIGHT,
            )
        )
        self.assertFalse(
            _has_low_border_side_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        0,
                        128,
                        0.30,
                        Box(0, 128, 32, 32),
                    ),
                    Detection(
                        "spike_right",
                        OBJ_SPIKE_RIGHT,
                        24,
                        128,
                        0.30,
                        Box(24, 128, 32, 32),
                    ),
                ],
                32,
                128,
                OBJ_MINI_SPIKE_RIGHT,
            )
        )

    def test_ultra_faint_left_mini_requires_local_spike_and_block_layout(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.074,
            border_score=0.045,
            center_score=0.125,
        )

        self.assertTrue(
            _is_ultra_faint_left_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.08),
                0.01,
                -0.09,
                0.076,
            )
        )
        self.assertFalse(
            _is_ultra_faint_left_mini_spike_candidate(
                patch,
                _GeometryClass("block", OBJ_BLOCK, 0.08),
                0.04,
                -0.09,
                0.076,
            )
        )
        self.assertTrue(
            _has_ultra_faint_left_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        80,
                        384,
                        0.30,
                        Box(80, 384, 32, 32),
                    ),
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        96,
                        416,
                        0.30,
                        Box(96, 416, 32, 32),
                    ),
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        96,
                        384,
                        0.30,
                        Box(96, 384, 32, 32),
                    ),
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        96,
                        448,
                        0.30,
                        Box(96, 448, 32, 32),
                    ),
                    Detection(
                        "spike_right",
                        OBJ_SPIKE_RIGHT,
                        64,
                        400,
                        0.30,
                        Box(64, 400, 32, 32),
                    ),
                    Detection(
                        "spike_left",
                        OBJ_SPIKE_LEFT,
                        88,
                        448,
                        0.30,
                        Box(88, 448, 32, 32),
                    ),
                ],
                80,
                416,
            )
        )
        self.assertFalse(
            _has_ultra_faint_left_mini_spike_support(
                [
                    Detection(
                        "block",
                        OBJ_BLOCK,
                        96,
                        416,
                        0.30,
                        Box(96, 416, 32, 32),
                    ),
                    Detection(
                        "spike_right",
                        OBJ_SPIKE_RIGHT,
                        64,
                        400,
                        0.30,
                        Box(64, 400, 32, 32),
                    ),
                    Detection(
                        "spike_left",
                        OBJ_SPIKE_LEFT,
                        88,
                        448,
                        0.30,
                        Box(88, 448, 32, 32),
                    ),
                ],
                80,
                416,
            )
        )

    def test_block_accepts_weak_aligned_candidate(self) -> None:
        candidate = _GeometryPatchCandidate(
            64,
            96,
            _PatchFeatures((), edge_density=0.05, border_score=0.06, center_score=0.02),
            spike=None,
            block=_GeometryClass("block", OBJ_BLOCK, 0.28),
        )

        self.assertTrue(_accept_block(candidate))

    def test_block_rejects_weak_off_grid_candidate(self) -> None:
        candidate = _GeometryPatchCandidate(
            72,
            96,
            _PatchFeatures((), edge_density=0.05, border_score=0.06, center_score=0.02),
            spike=None,
            block=_GeometryClass("block", OBJ_BLOCK, 0.28),
        )

        self.assertFalse(_accept_block(candidate))

    def test_block_dedupe_prefers_aligned_candidate_over_shifted_neighbor(self) -> None:
        shifted = Detection("block", OBJ_BLOCK, 56, 96, 1.00, Box(56, 96, 32, 32))
        aligned = Detection("block", OBJ_BLOCK, 64, 96, 0.28, Box(64, 96, 32, 32))

        result = _dedupe_geometry([shifted, aligned])

        self.assertEqual([(det.x, det.y) for det in result], [(64, 96)])

    def test_block_dedupe_prefers_32px_alignment_over_16px_alignment(self) -> None:
        half_shifted = Detection("block", OBJ_BLOCK, 80, 96, 1.00, Box(80, 96, 32, 32))
        aligned_32 = Detection("block", OBJ_BLOCK, 96, 96, 0.30, Box(96, 96, 32, 32))

        result = _dedupe_geometry([half_shifted, aligned_32])

        self.assertEqual([(det.x, det.y) for det in result], [(96, 96)])

    def test_strong_block_can_coexist_with_color_anchor(self) -> None:
        water = Detection("water_2", OBJ_WATER_2, 224, 40, 0.50, Box(224, 40, 32, 32))
        strong_block = Detection("block", OBJ_BLOCK, 224, 32, 0.36, Box(224, 32, 32, 32))

        result = _dedupe_overlapping_geometry([water, strong_block])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_WATER_2, 224, 40),
            (OBJ_BLOCK, 224, 32),
        ])

    def test_very_weak_block_still_loses_to_color_anchor(self) -> None:
        water = Detection("water_2", OBJ_WATER_2, 224, 40, 0.50, Box(224, 40, 32, 32))
        weak_block = Detection("block", OBJ_BLOCK, 224, 32, 0.27, Box(224, 32, 32, 32))

        result = _dedupe_overlapping_geometry([water, weak_block])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_WATER_2, 224, 40),
        ])

    def test_block_still_loses_to_apple_anchor(self) -> None:
        apple = Detection("apple", OBJ_APPLE, 224, 40, 0.80, Box(224, 40, 32, 32))
        strong_block = Detection("block", OBJ_BLOCK, 224, 32, 0.80, Box(224, 32, 32, 32))

        result = _dedupe_overlapping_geometry([apple, strong_block])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_APPLE, 224, 40),
        ])

    def test_block_still_loses_to_save_anchor(self) -> None:
        save = Detection("save", OBJ_SAVE, 224, 40, 0.95, Box(224, 40, 32, 32))
        strong_block = Detection("block", OBJ_BLOCK, 224, 32, 0.80, Box(224, 32, 32, 32))

        result = _dedupe_overlapping_geometry([save, strong_block])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_SAVE, 224, 40),
        ])

    def test_strong_full_spike_can_coexist_with_water_anchor(self) -> None:
        water = Detection("water_2", OBJ_WATER_2, 720, 96, 0.60, Box(720, 96, 32, 32))
        strong_spike = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            720,
            96,
            0.49,
            Box(720, 96, 32, 32),
        )

        result = _dedupe_overlapping_geometry([water, strong_spike])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_WATER_2, 720, 96),
            (OBJ_SPIKE_DOWN, 720, 96),
        ])

    def test_weak_full_spike_still_loses_to_water_anchor(self) -> None:
        water = Detection("water_2", OBJ_WATER_2, 720, 96, 0.60, Box(720, 96, 32, 32))
        weak_spike = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            720,
            96,
            0.47,
            Box(720, 96, 32, 32),
        )

        result = _dedupe_overlapping_geometry([water, weak_spike])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_WATER_2, 720, 96),
        ])

    def test_full_spike_still_loses_to_save_anchor(self) -> None:
        save = Detection("save", OBJ_SAVE, 720, 96, 0.95, Box(720, 96, 32, 32))
        strong_spike = Detection(
            "spike_down",
            OBJ_SPIKE_DOWN,
            720,
            96,
            0.80,
            Box(720, 96, 32, 32),
        )

        result = _dedupe_overlapping_geometry([save, strong_spike])

        self.assertEqual([(det.type_id, det.x, det.y) for det in result], [
            (OBJ_SAVE, 720, 96),
        ])

    def test_blocklike_spike_candidate_accepts_hollow_aligned_outline(self) -> None:
        candidate = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.12, border_score=0.16, center_score=0.0),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.26),
            block=_GeometryClass("block", OBJ_BLOCK, 0.15),
        )

        self.assertTrue(_is_blocklike_spike_candidate(candidate))

    def test_blocklike_spike_candidate_rejects_unclear_block_shape(self) -> None:
        high_center = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.12, border_score=0.16, center_score=0.04),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.26),
            block=_GeometryClass("block", OBJ_BLOCK, 0.15),
        )
        off_grid = _GeometryPatchCandidate(
            112,
            128,
            _PatchFeatures((), edge_density=0.12, border_score=0.16, center_score=0.0),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.26),
            block=_GeometryClass("block", OBJ_BLOCK, 0.15),
        )
        strong_spike = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.12, border_score=0.16, center_score=0.0),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.40),
            block=_GeometryClass("block", OBJ_BLOCK, 0.15),
        )

        self.assertFalse(_is_blocklike_spike_candidate(high_center))
        self.assertFalse(_is_blocklike_spike_candidate(off_grid))
        self.assertFalse(_is_blocklike_spike_candidate(strong_spike))

    def test_center_heavy_block_candidate_accepts_textured_block_shape(self) -> None:
        candidate = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.35, border_score=0.10, center_score=0.50),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.45),
            block=_GeometryClass("block", OBJ_BLOCK, 0.32),
        )

        self.assertTrue(_is_center_heavy_block_candidate(candidate))

    def test_center_heavy_block_candidate_rejects_weak_or_off_grid_shape(self) -> None:
        weak_center = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.35, border_score=0.10, center_score=0.49),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.45),
            block=_GeometryClass("block", OBJ_BLOCK, 0.32),
        )
        weak_block = _GeometryPatchCandidate(
            96,
            128,
            _PatchFeatures((), edge_density=0.35, border_score=0.10, center_score=0.50),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.45),
            block=_GeometryClass("block", OBJ_BLOCK, 0.31),
        )
        off_grid = _GeometryPatchCandidate(
            100,
            128,
            _PatchFeatures((), edge_density=0.35, border_score=0.10, center_score=0.50),
            spike=_GeometryClass("spike_up", OBJ_SPIKE_UP, 0.45),
            block=_GeometryClass("block", OBJ_BLOCK, 0.32),
        )

        self.assertFalse(_is_center_heavy_block_candidate(weak_center))
        self.assertFalse(_is_center_heavy_block_candidate(weak_block))
        self.assertFalse(_is_center_heavy_block_candidate(off_grid))

    def test_block_run_gap_accepts_structural_neighbor_pairs(self) -> None:
        self.assertTrue(_is_block_run_gap(64, 96, {(32, 96), (96, 96)}))
        self.assertTrue(_is_block_run_gap(64, 96, {(64, 64), (64, 128)}))
        self.assertTrue(_is_block_run_gap(64, 96, {(32, 96), (64, 128)}))
        self.assertTrue(_is_block_run_gap(64, 96, {(32, 96), (0, 96)}))
        self.assertTrue(_is_block_run_gap(64, 96, {(32, 96)}))
        self.assertFalse(_is_block_run_gap(64, 96, set()))

    def test_block_run_gap_patch_accepts_strong_or_hollow_outline(self) -> None:
        strong_patch = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.02,
            center_score=0.10,
        )
        hollow_patch = _PatchFeatures(
            (),
            edge_density=0.06,
            border_score=0.04,
            center_score=0.0,
        )

        self.assertTrue(
            _accept_block_run_gap_patch(
                strong_patch,
                _GeometryClass("block", OBJ_BLOCK, 0.12),
            )
        )
        self.assertTrue(
            _accept_block_run_gap_patch(
                hollow_patch,
                _GeometryClass("block", OBJ_BLOCK, 0.04),
            )
        )

    def test_block_run_extension_accepts_hollow_outline_patch(self) -> None:
        hollow_patch = _PatchFeatures(
            (),
            edge_density=0.06,
            border_score=0.04,
            center_score=0.0,
        )

        self.assertTrue(
            _accept_block_run_gap_patch(
                hollow_patch,
                _GeometryClass("block", OBJ_BLOCK, 0.04),
                "neighbor_extension",
            )
        )

    def test_nearby_hollow_block_recovery_requires_cluster_support(self) -> None:
        hollow_patch = _PatchFeatures(
            (),
            edge_density=0.06,
            border_score=0.04,
            center_score=0.0,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.04)

        self.assertTrue(
            _can_recover_nearby_hollow_block(hollow_patch, block, "cluster")
        )
        self.assertFalse(
            _can_recover_nearby_hollow_block(
                hollow_patch,
                block,
                "neighbor_extension",
            )
        )

    def test_nearby_hollow_block_recovery_rejects_center_heavy_patch(self) -> None:
        center_heavy_patch = _PatchFeatures(
            (),
            edge_density=0.06,
            border_score=0.04,
            center_score=0.03,
        )

        self.assertFalse(
            _can_recover_nearby_hollow_block(
                center_heavy_patch,
                _GeometryClass("block", OBJ_BLOCK, 0.04),
                "cluster",
            )
        )

    def test_dark_outline_run_fill_patch_accepts_only_low_signal_interiors(self) -> None:
        low_signal = _PatchFeatures(
            (),
            edge_density=0.03,
            border_score=0.02,
            center_score=0.0,
        )
        textured = _PatchFeatures(
            (),
            edge_density=0.08,
            border_score=0.02,
            center_score=0.0,
        )
        border_heavy = _PatchFeatures(
            (),
            edge_density=0.03,
            border_score=0.07,
            center_score=0.0,
        )

        self.assertTrue(_is_dark_outline_block_run_fill_patch(low_signal))
        self.assertFalse(_is_dark_outline_block_run_fill_patch(textured))
        self.assertFalse(_is_dark_outline_block_run_fill_patch(border_heavy))

    def test_dark_outline_full_spike_candidate_uses_triangle_geometry(self) -> None:
        candidate = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.26,
            direction_margin=0.0,
            outline_delta=0.12,
        )
        weak_score = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.25,
            direction_margin=0.0,
            outline_delta=0.12,
        )
        weak_outline = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.26,
            direction_margin=0.0,
            outline_delta=0.11,
        )

        self.assertTrue(_is_dark_outline_full_spike_candidate(candidate))
        self.assertFalse(_is_dark_outline_full_spike_candidate(weak_score))
        self.assertFalse(_is_dark_outline_full_spike_candidate(weak_outline))

    def test_full_spike_side_coverage_rejects_a_single_edge_fragment(self) -> None:
        full_triangle = _up_outline_patch(
            edge_density=0.20,
            border_score=0.20,
            center_score=0.20,
        )
        base_only = [False] * 256
        for x in range(16):
            base_only[15 * 16 + x] = True
        fragment = _PatchFeatures(tuple(base_only), 0.06, 0.06, 0.0)

        self.assertGreaterEqual(_triangle_side_coverage(full_triangle, "up"), 0.45)
        self.assertLess(_triangle_side_coverage(fragment, "up"), 0.45)

    def test_dark_outline_half_step_full_spike_candidate_is_stricter(self) -> None:
        candidate = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.275,
            direction_margin=0.0,
            outline_delta=0.14,
        )
        weak_score = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.274,
            direction_margin=0.0,
            outline_delta=0.14,
        )
        weak_outline = _GeometryClass(
            "spike_up",
            OBJ_SPIKE_UP,
            0.275,
            direction_margin=0.0,
            outline_delta=0.13,
        )

        self.assertTrue(_is_dark_outline_half_step_full_spike_candidate(candidate))
        self.assertFalse(_is_dark_outline_half_step_full_spike_candidate(weak_score))
        self.assertFalse(_is_dark_outline_half_step_full_spike_candidate(weak_outline))

    def test_supported_full_spike_candidate_requires_nonblock_triangle_body(self) -> None:
        spike = _GeometryClass(
            "spike_down",
            OBJ_SPIKE_DOWN,
            0.24,
            direction_margin=0.06,
            outline_delta=0.12,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.32)
        patch = _PatchFeatures(
            (),
            edge_density=0.18,
            border_score=0.08,
            center_score=0.28,
        )

        self.assertTrue(_is_supported_full_spike_candidate(spike, block, patch))
        self.assertFalse(
            _is_supported_full_spike_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.41),
                patch,
            )
        )
        self.assertFalse(
            _is_supported_full_spike_candidate(
                spike,
                block,
                _PatchFeatures(
                    (),
                    edge_density=0.18,
                    border_score=0.08,
                    center_score=0.10,
                ),
            )
        )

    def test_low_signal_supported_full_spike_requires_low_block_score(self) -> None:
        spike = _GeometryClass(
            "spike_down",
            OBJ_SPIKE_DOWN,
            0.18,
            direction_margin=0.02,
            outline_delta=0.08,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.16)
        patch = _PatchFeatures(
            (),
            edge_density=0.15,
            border_score=0.06,
            center_score=0.28,
        )

        self.assertTrue(
            _is_low_signal_supported_full_spike_candidate(spike, block, patch)
        )
        self.assertFalse(
            _is_low_signal_supported_full_spike_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.23),
                patch,
            )
        )
        self.assertFalse(
            _is_low_signal_supported_full_spike_candidate(
                _GeometryClass(
                    "spike_down",
                    OBJ_SPIKE_DOWN,
                    0.18,
                    direction_margin=0.0,
                    outline_delta=0.08,
                ),
                block,
                patch,
            )
        )

    def test_half_step_supported_full_spike_requires_low_block_score(self) -> None:
        spike = _GeometryClass(
            "spike_down",
            OBJ_SPIKE_DOWN,
            0.23,
            direction_margin=0.05,
            outline_delta=0.10,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.20)
        patch = _PatchFeatures(
            (),
            edge_density=0.20,
            border_score=0.08,
            center_score=0.28,
        )

        self.assertTrue(
            _is_half_step_supported_full_spike_candidate(spike, block, patch)
        )
        self.assertFalse(
            _is_half_step_supported_full_spike_candidate(
                spike,
                _GeometryClass("block", OBJ_BLOCK, 0.23),
                patch,
            )
        )
        self.assertFalse(
            _is_half_step_supported_full_spike_candidate(
                _GeometryClass(
                    "spike_down",
                    OBJ_SPIKE_DOWN,
                    0.23,
                    direction_margin=0.04,
                    outline_delta=0.10,
                ),
                block,
                patch,
            )
        )

    def test_pale_outline_apple_room_requires_bright_low_saturation_room(self) -> None:
        self.assertTrue(_is_pale_outline_apple_room(_ColorProfile(230, 232, 231, 0.02)))
        self.assertFalse(_is_pale_outline_apple_room(_ColorProfile(150, 150, 150, 0.02)))
        self.assertFalse(_is_pale_outline_apple_room(_ColorProfile(230, 220, 180, 0.08)))

    def test_outline_apple_component_uses_compact_shape_signal(self) -> None:
        candidate = Box(10, 20, 10, 4)
        features = _PatchFeatures(
            (),
            edge_density=0.28,
            border_score=0.17,
            center_score=0.46,
        )
        profile = _ColorProfile(240, 240, 240, 0.0)

        self.assertTrue(
            _is_outline_apple_component(candidate, 0.47, features, profile)
        )
        self.assertFalse(
            _is_outline_apple_component(
                Box(10, 20, 18, 4),
                0.47,
                features,
                profile,
            )
        )
        self.assertFalse(
            _is_outline_apple_component(
                candidate,
                0.47,
                _PatchFeatures(
                    (),
                    edge_density=0.12,
                    border_score=0.17,
                    center_score=0.46,
                ),
                profile,
            )
        )

    def test_edge_outline_block_patch_accepts_hollow_edge_tile(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.18,
            center_score=0.02,
        )

        self.assertTrue(_is_edge_outline_block_patch(patch))

    def test_edge_outline_block_patch_rejects_weak_or_center_heavy_tile(self) -> None:
        weak_edge = _PatchFeatures(
            (),
            edge_density=0.11,
            border_score=0.18,
            center_score=0.02,
        )
        weak_border = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.17,
            center_score=0.02,
        )
        center_heavy = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.18,
            center_score=0.03,
        )

        self.assertFalse(_is_edge_outline_block_patch(weak_edge))
        self.assertFalse(_is_edge_outline_block_patch(weak_border))
        self.assertFalse(_is_edge_outline_block_patch(center_heavy))

    def test_edge_weak_block_patch_accepts_low_signal_room_edge_tile(self) -> None:
        patch = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.08,
            center_score=0.0,
        )
        block = _GeometryClass("block", OBJ_BLOCK, 0.21)

        self.assertTrue(_is_edge_weak_block_patch(patch, block))

    def test_edge_weak_block_patch_rejects_weak_components(self) -> None:
        block = _GeometryClass("block", OBJ_BLOCK, 0.21)
        weak_block = _GeometryClass("block", OBJ_BLOCK, 0.20)
        weak_edge = _PatchFeatures(
            (),
            edge_density=0.11,
            border_score=0.08,
            center_score=0.0,
        )
        weak_border = _PatchFeatures(
            (),
            edge_density=0.12,
            border_score=0.07,
            center_score=0.0,
        )

        self.assertFalse(
            _is_edge_weak_block_patch(
                _PatchFeatures((), 0.12, 0.08, 0.0),
                weak_block,
            )
        )
        self.assertFalse(_is_edge_weak_block_patch(weak_edge, block))
        self.assertFalse(_is_edge_weak_block_patch(weak_border, block))

    def test_block_run_gap_patch_rejects_weak_noise(self) -> None:
        weak_patch = _PatchFeatures(
            (),
            edge_density=0.05,
            border_score=0.04,
            center_score=0.0,
        )

        self.assertFalse(
            _accept_block_run_gap_patch(
                weak_patch,
                _GeometryClass("block", OBJ_BLOCK, 0.04),
            )
        )


def _textured_test_image(width: int = 800, height: int = 608) -> RGBImage:
    data = bytearray()
    for y in range(height):
        for x in range(width):
            value = 255 if (x // 2 + y // 2) % 2 else 0
            data.extend((value, value, value))
    return RGBImage(width, height, bytes(data))


def _up_outline_patch(
    *,
    edge_density: float,
    border_score: float,
    center_score: float,
) -> _PatchFeatures:
    edge_mask = [False] * 256
    outline, _outside = _triangle_masks("up")
    for position in outline:
        edge_mask[position] = True
    return _PatchFeatures(tuple(edge_mask), edge_density, border_score, center_score)


def _up_spike_test_image(
    targets: list[tuple[int, int]],
    width: int = 800,
    height: int = 608,
) -> RGBImage:
    data = bytearray([255] * (width * height * 3))
    for x, y in targets:
        for local_y in range(32):
            for local_x in range(32):
                side = abs(local_x - 15.5) * 2
                if local_y < side - 2:
                    continue
                value = 0 if (local_x // 2 + local_y // 2) % 2 else 255
                offset = ((y + local_y) * width + x + local_x) * 3
                data[offset : offset + 3] = bytes((value, value, value))
    return RGBImage(width, height, bytes(data))


def _mini_left_test_image(
    targets: list[tuple[int, int]],
    width: int = 800,
    height: int = 608,
) -> RGBImage:
    data = bytearray([255] * (width * height * 3))
    for x, y in targets:
        for local_y in range(16):
            for local_x in range(16):
                side = abs(local_y - 7.5) * 2
                if local_x < side - 1:
                    continue
                value = 0 if (local_x // 2 + local_y // 2) % 2 else 255
                offset = ((y + local_y) * width + x + local_x) * 3
                data[offset : offset + 3] = bytes((value, value, value))
    return RGBImage(width, height, bytes(data))


if __name__ == "__main__":
    unittest.main()
