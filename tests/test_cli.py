from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from jtool_scanner.cli import main
from jtool_scanner.constants import OBJ_BLOCK, OBJ_PLAYER_START, OBJ_SAVE, OBJ_WATER_2
from jtool_scanner.jmap import JMap, JMapObject


class CliTests(unittest.TestCase):
    def test_correction_project_cli_import_edit_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source.jmap"
            project = base / "source.jscan.json"
            exported = base / "corrected.jmap"
            preview = base / "corrected.svg"
            diagnostic = base / "diagnostic.svg"
            JMap(
                objects=[
                    JMapObject(32, 64, OBJ_BLOCK),
                    JMapObject(64, 512, OBJ_SAVE),
                    JMapObject(64, 512, OBJ_PLAYER_START),
                ]
            ).to_file(source)

            self.assertEqual(main(["project-import", str(source), str(project)]), 0)
            self.assertEqual(
                main(
                    [
                        "project-edit",
                        str(project),
                        "--disable",
                        "obj-0001",
                        "--add",
                        "96:128:water_2",
                        "--start-save",
                        "obj-0002",
                        "--diagnostic-preview",
                        str(diagnostic),
                    ]
                ),
                0,
            )
            self.assertEqual(
                main(
                    [
                        "project-export",
                        str(project),
                        str(exported),
                        "--preview",
                        str(preview),
                    ]
                ),
                0,
            )

            result = JMap.from_file(exported)
            self.assertFalse(result.objects_of_type(OBJ_BLOCK))
            self.assertEqual(len(result.objects_of_type(OBJ_WATER_2)), 1)
            self.assertEqual(len(result.objects_of_type(OBJ_SAVE)), 1)
            self.assertEqual(len(result.objects_of_type(OBJ_PLAYER_START)), 1)
            self.assertTrue(preview.exists())
            self.assertIn("correction-overlay", diagnostic.read_text(encoding="utf-8"))

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

    def test_analyze_report_prints_diagnostics(self) -> None:
        report = {
            "manifest": "synthetic.json",
            "settings": {"grid_step": 8, "tolerance": 24},
            "pairs": [
                {
                    "id": "example",
                    "details": {
                        "blocks": {
                            "unmatched_detections": [
                                {
                                    "kind": "block",
                                    "type_id": 1,
                                    "type_name": "block",
                                    "x": 32,
                                    "y": 64,
                                    "score": 0.7,
                                    "nearest_truth": None,
                                }
                            ],
                            "missed_truth": [],
                        }
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            output = io.StringIO()

            with redirect_stdout(output):
                exit_code = main(
                    [
                        "analyze-report",
                        str(report_path),
                        "--group",
                        "blocks",
                        "--limit",
                        "1",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("blocks: 1 unmatched detections, 0 missed truth", output.getvalue())


if __name__ == "__main__":
    unittest.main()
