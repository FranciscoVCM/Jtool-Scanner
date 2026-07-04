from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from jtool_scanner.cli import main


class CliTests(unittest.TestCase):
    def test_scan_fixtures_can_write_report_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = tmp_path / "scans"
            report_path = tmp_path / "report.json"

            exit_code = main(
                [
                    "scan-fixtures",
                    "fixtures/irkara/manifest.json",
                    "--pair",
                    "irkara-58",
                    "--out-dir",
                    str(out_dir),
                    "--report-json",
                    str(report_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(Path(report["manifest"]), Path("fixtures/irkara/manifest.json"))
            self.assertEqual(report["settings"]["pair_ids"], ["irkara-58"])
            self.assertEqual(report["settings"]["out_dir"], str(out_dir))
            self.assertEqual(report["totals"]["pairs"], 1)
            self.assertEqual(report["pairs"][0]["id"], "irkara-58")

            artifacts = report["pairs"][0]["artifacts"]
            self.assertTrue(Path(artifacts["scan_jmap"]).exists())
            self.assertTrue(Path(artifacts["scan_svg"]).exists())
            self.assertIn("matched_saves", report["pairs"][0]["metrics"])
            self.assertIn("details", report["pairs"][0])
            self.assertIn("unmatched_detections", report["pairs"][0]["details"]["saves"])
            self.assertIn("missed_truth", report["pairs"][0]["details"]["full_spikes"])


if __name__ == "__main__":
    unittest.main()
