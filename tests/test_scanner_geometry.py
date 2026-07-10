from __future__ import annotations

import unittest

from jtool_scanner.constants import (
    OBJ_APPLE,
    OBJ_BLOCK,
    OBJ_MINI_SPIKE_DOWN,
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
    _accept_mini_spike,
    _dedupe_geometry,
    _dedupe_overlapping_geometry,
    _dedupe_normalized_full_spikes,
    _can_recover_nearby_hollow_block,
    _is_block_run_gap,
    _is_blocklike_spike_candidate,
    _is_center_heavy_block_candidate,
    _is_dark_outline_block_run_fill_patch,
    _is_dark_outline_full_spike_candidate,
    _is_dark_outline_half_step_full_spike_candidate,
    _is_edge_outline_block_patch,
    _is_edge_weak_block_patch,
    _is_outline_apple_component,
    _is_pale_outline_apple_room,
    _is_supported_full_spike_candidate,
    _normalize_full_spike_origin,
    _outline_block_score,
    _ColorProfile,
)


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


if __name__ == "__main__":
    unittest.main()
