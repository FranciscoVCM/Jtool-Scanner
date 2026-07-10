from __future__ import annotations

import unittest

from jtool_scanner.constants import (
    OBJ_BLOCK,
    OBJ_SAVE,
    OBJ_SPIKE_UP,
    OBJ_WATER,
    OBJ_WATER_2,
)
from jtool_scanner.evaluation import (
    aggregate_evaluations,
    build_match_details,
    evaluate_scan,
)
from jtool_scanner.geometry import Box
from jtool_scanner.jmap import JMap, JMapObject
from jtool_scanner.scanner import Detection


class EvaluationTests(unittest.TestCase):
    def test_evaluate_scan_scores_existing_detections(self) -> None:
        truth = JMap(
            objects=[
                JMapObject(64, 96, OBJ_SAVE),
                JMapObject(160, 128, OBJ_WATER),
            ]
        )
        detections = [
            Detection("save", OBJ_SAVE, 64, 96, 1.0, Box(0, 0, 24, 24)),
            Detection("water_2", OBJ_WATER_2, 160, 128, 0.9, Box(0, 0, 32, 32)),
        ]

        evaluation = evaluate_scan("synthetic", detections, truth, tolerance=8)

        self.assertEqual(evaluation.matched_saves, 1)
        self.assertEqual(evaluation.matched_water, 1)
        self.assertEqual(evaluation.detected_water, 1)

    def test_aggregate_evaluations_sums_metric_fields(self) -> None:
        truth = JMap(
            objects=[
                JMapObject(64, 96, OBJ_SAVE),
                JMapObject(160, 128, OBJ_WATER),
            ]
        )
        detections = [
            Detection("save", OBJ_SAVE, 64, 96, 1.0, Box(0, 0, 24, 24)),
            Detection("water_2", OBJ_WATER_2, 160, 128, 0.9, Box(0, 0, 32, 32)),
        ]
        first = evaluate_scan("first", detections, truth, tolerance=8)
        second = evaluate_scan("second", detections, truth, tolerance=8)

        totals = aggregate_evaluations([first, second])

        self.assertEqual(totals["pairs"], 2)
        self.assertEqual(totals["matched_saves"], 2)
        self.assertEqual(totals["truth_water"], 2)
        self.assertEqual(totals["detected_water"], 2)

    def test_build_match_details_lists_unmatched_and_missed_objects(self) -> None:
        truth = JMap(
            objects=[
                JMapObject(64, 96, OBJ_SAVE),
                JMapObject(160, 128, OBJ_WATER),
                JMapObject(320, 320, OBJ_BLOCK),
            ]
        )
        detections = [
            Detection("save", OBJ_SAVE, 64, 96, 1.0, Box(0, 0, 24, 24)),
            Detection("water_2", OBJ_WATER_2, 160, 128, 0.9, Box(0, 0, 32, 32)),
            Detection("water_2", OBJ_WATER_2, 400, 400, 0.5, Box(0, 0, 32, 32)),
        ]

        details = build_match_details(detections, truth, tolerance=8)

        self.assertEqual(details["water"]["unmatched_detection_count"], 1)
        self.assertEqual(details["blocks"]["missed_truth_count"], 1)
        self.assertEqual(details["water"]["unmatched_detections"][0]["x"], 400)
        self.assertEqual(
            details["water"]["unmatched_detections"][0]["nearest_truth"]["type_id"],
            OBJ_WATER,
        )
        self.assertEqual(details["blocks"]["missed_truth"][0]["x"], 320)
        self.assertIsNone(details["blocks"]["missed_truth"][0]["nearest_detection"])

    def test_evaluate_scan_uses_maximum_matching_for_close_candidates(self) -> None:
        truth = JMap(
            objects=[
                JMapObject(100, 100, OBJ_SPIKE_UP),
                JMapObject(124, 100, OBJ_SPIKE_UP),
            ]
        )
        detections = [
            Detection("spike_up", OBJ_SPIKE_UP, 112, 100, 0.9, Box(0, 0, 32, 32)),
            Detection("spike_up", OBJ_SPIKE_UP, 100, 100, 0.8, Box(0, 0, 32, 32)),
        ]

        evaluation = evaluate_scan("synthetic", detections, truth, tolerance=16)

        self.assertEqual(evaluation.matched_full_spikes, 2)

    def test_match_details_use_maximum_matching_for_missed_lists(self) -> None:
        truth = JMap(
            objects=[
                JMapObject(100, 100, OBJ_SPIKE_UP),
                JMapObject(124, 100, OBJ_SPIKE_UP),
            ]
        )
        detections = [
            Detection("spike_up", OBJ_SPIKE_UP, 112, 100, 0.9, Box(0, 0, 32, 32)),
            Detection("spike_up", OBJ_SPIKE_UP, 100, 100, 0.8, Box(0, 0, 32, 32)),
        ]

        details = build_match_details(detections, truth, tolerance=16)

        self.assertEqual(details["full_spikes"]["unmatched_detection_count"], 0)
        self.assertEqual(details["full_spikes"]["missed_truth_count"], 0)


if __name__ == "__main__":
    unittest.main()
