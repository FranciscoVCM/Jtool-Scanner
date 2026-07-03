from __future__ import annotations

import unittest

from jtool_scanner.constants import OBJ_SAVE, OBJ_WATER, OBJ_WATER_2
from jtool_scanner.evaluation import evaluate_scan
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


if __name__ == "__main__":
    unittest.main()
