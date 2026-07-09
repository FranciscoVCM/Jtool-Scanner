from __future__ import annotations

import unittest

from jtool_scanner.constants import (
    OBJ_BLOCK,
    OBJ_MINI_SPIKE_DOWN,
    OBJ_SPIKE_DOWN,
    OBJ_SPIKE_LEFT,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_UP,
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
    _is_block_run_gap,
    _is_blocklike_spike_candidate,
    _normalize_full_spike_origin,
    _outline_block_score,
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

    def test_block_run_gap_requires_opposite_neighbors(self) -> None:
        self.assertTrue(_is_block_run_gap(64, 96, {(32, 96), (96, 96)}))
        self.assertTrue(_is_block_run_gap(64, 96, {(64, 64), (64, 128)}))
        self.assertFalse(_is_block_run_gap(64, 96, {(32, 96), (64, 128)}))

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
