"""A clipped24px body must not become a shifted false32px edge object."""
from unittest import TestCase

from jtool_scanner.geometry import Box
from scripts.source_capture_base import CaptureBaseEvidence, capture_base_hypotheses
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_sampling import SourceFrame
from tests.test_source_capture_base import TARGETS, edge_scene


class CaptureBaseCropAdversaries(TestCase):
    def reject_shifted_body(self, target, physical_crop, shifted):
        full, original = edge_scene(target)
        image = full.original_snapshot()
        frame = SourceFrame(image, physical_crop, extent=full.extent, canonical=image)
        self.assertIn(shifted, capture_base_hypotheses(frame))
        self.assertNotIn(target, capture_base_hypotheses(frame))
        proof = CaptureBaseEvidence(FilledGlyphEvidence(frame, original)).support(shifted)
        self.assertFalse(proof['passed'], proof)

    def test_800x600_bottom_crop_does_not_move_real_up_spike_eight_pixels_up(self):
        self.reject_shifted_body(TARGETS[0], Box(0, 0, 800, 600), (3, 224, 568))

    def test_top_crop_does_not_move_real_down_spike_eight_pixels_down(self):
        self.reject_shifted_body(TARGETS[1], Box(0, 8, 800, 600), (6, 224, 8))

    def test_left_crop_does_not_move_real_right_spike_eight_pixels_right(self):
        self.reject_shifted_body(TARGETS[2], Box(8, 0, 792, 608), (4, 8, 288))

    def test_right_crop_does_not_move_real_left_spike_eight_pixels_left(self):
        self.reject_shifted_body(TARGETS[3], Box(0, 0, 792, 608), (5, 760, 288))
