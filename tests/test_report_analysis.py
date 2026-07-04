from __future__ import annotations

import unittest

from jtool_scanner.report_analysis import analyze_report


class ReportAnalysisTests(unittest.TestCase):
    def test_analyze_report_summarizes_unmatched_and_missed_objects(self) -> None:
        report = {
            "manifest": "fixtures/block_spike/manifest.json",
            "settings": {"grid_step": 8, "tolerance": 24},
            "pairs": [
                {
                    "id": "example",
                    "details": {
                        "full_spikes": {
                            "unmatched_detections": [
                                {
                                    "kind": "spike_up",
                                    "type_id": 3,
                                    "type_name": "spike_up",
                                    "x": 64,
                                    "y": 96,
                                    "score": 0.75,
                                    "nearest_truth": {
                                        "type_id": 3,
                                        "type_name": "spike_up",
                                        "x": 64,
                                        "y": 160,
                                        "distance": 64.0,
                                    },
                                }
                            ],
                            "missed_truth": [
                                {
                                    "type_id": 4,
                                    "type_name": "spike_down",
                                    "x": 128,
                                    "y": 192,
                                    "nearest_detection": {
                                        "kind": "spike_down",
                                        "type_id": 4,
                                        "type_name": "spike_down",
                                        "x": 128,
                                        "y": 160,
                                        "score": 0.5,
                                        "distance": 32.0,
                                    },
                                }
                            ],
                        }
                    },
                }
            ],
        }

        lines = analyze_report(report, groups=["full_spikes"], limit=2)
        text = "\n".join(lines)

        self.assertIn("full_spikes: 1 unmatched detections, 1 missed truth", text)
        self.assertIn("unmatched by type: spike_up=1", text)
        self.assertIn("unmatched score by distance: 49-96 n=1 median=0.750", text)
        self.assertIn("unmatched near misses: none", text)
        self.assertIn("unmatched offsets to nearest truth: (+0,+64)=1", text)
        self.assertIn("unmatched grid residues mod 16: (0,0)=1", text)
        self.assertIn("missed by type: spike_down=1", text)
        self.assertIn("missed near misses: 25-32px=1", text)
        self.assertIn("missed nearest-detection offsets: (+0,-32)=1", text)
        self.assertIn("missed grid residues mod 16: (0,0)=1", text)
        self.assertIn("example spike_up (64,96)", text)


if __name__ == "__main__":
    unittest.main()
