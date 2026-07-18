from __future__ import annotations

from collections import Counter
from pathlib import Path
import tempfile
import unittest

from jtool_scanner.constants import (
    OBJ_BLOCK,
    OBJ_MINI_BLOCK,
    OBJ_PLAYER_START,
    OBJ_SAVE,
    OBJ_SAVE_FLIP,
    OBJ_SPIKE_RIGHT,
    OBJ_WALLJUMP_LEFT,
    OBJ_WALLJUMP_RIGHT,
    OBJ_WATER,
    OBJ_WATER_2,
)
from jtool_scanner.correction import (
    CorrectionProject,
    parse_object_type,
    render_correction_svg,
)
from jtool_scanner.geometry import Box
from jtool_scanner.jmap import JMap, JMapObject
from jtool_scanner.scanner import Detection, ScanResult


class CorrectionProjectTests(unittest.TestCase):
    def test_scan_project_round_trip_preserves_provenance_and_stable_ids(self) -> None:
        result = ScanResult(
            image_width=960,
            image_height=720,
            room_box=Box(10, 20, 800, 608),
            detections=[
                Detection("save", OBJ_SAVE, 64, 512, 0.99, Box(74, 532, 32, 32)),
                Detection("block", OBJ_BLOCK, 32, 64, 0.81, Box(42, 84, 32, 32)),
            ],
        )

        project = result.to_correction_project("screen.png", grid_step=8)

        self.assertEqual([obj.object_id for obj in project.objects], ["obj-0001", "obj-0002"])
        self.assertEqual(project.objects[0].type_id, OBJ_BLOCK)
        self.assertEqual(project.objects[0].detection_kind, "block")
        self.assertEqual(project.objects[0].original, {"x": 32, "y": 64, "type_id": OBJ_BLOCK})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "screen.jscan.json"
            project.to_file(path)
            restored = CorrectionProject.from_file(path)

        self.assertEqual(restored.to_dict(), project.to_dict())

    def test_edits_export_overlaps_bulk_types_and_exact_start_save(self) -> None:
        project = CorrectionProject.from_jmap(
            JMap(
                objects=[
                    JMapObject(32, 64, OBJ_BLOCK),
                    JMapObject(64, 512, OBJ_SAVE),
                    JMapObject(256, 64, OBJ_WATER),
                    JMapObject(288, 64, OBJ_WATER),
                    JMapObject(64, 512, OBJ_PLAYER_START),
                ]
            )
        )
        block = next(obj for obj in project.objects if obj.type_id == OBJ_BLOCK)
        save = next(obj for obj in project.objects if obj.type_id == OBJ_SAVE)
        project.set_enabled(block.object_id, False)
        project.replace_type(OBJ_WATER, OBJ_WATER_2)
        project.add_object(160, 160, OBJ_SPIKE_RIGHT)
        project.add_object(160, 160, OBJ_SPIKE_RIGHT)
        project.choose_start_save(save.object_id)

        exported = project.to_jmap()
        counts = Counter((obj.x, obj.y, obj.type_id) for obj in exported.objects)

        self.assertEqual(counts[(160, 160, OBJ_SPIKE_RIGHT)], 2)
        self.assertEqual(counts[(256, 64, OBJ_WATER_2)], 1)
        self.assertEqual(counts[(288, 64, OBJ_WATER_2)], 1)
        self.assertNotIn((32, 64, OBJ_BLOCK), counts)
        self.assertEqual(counts[(64, 512, OBJ_PLAYER_START)], 1)
        self.assertEqual((exported.player_save_x, exported.player_save_y), (81, 535))

    def test_direction_can_be_corrected_without_moving_object(self) -> None:
        project = CorrectionProject(objects=[])
        vine = project.add_object(96, 128, OBJ_WALLJUMP_LEFT)

        project.set_object_type(vine.object_id, OBJ_WALLJUMP_RIGHT)

        exported = project.to_jmap()
        self.assertIn(JMapObject(96, 128, OBJ_WALLJUMP_RIGHT), exported.objects)

    def test_import_preserves_non_save_start_as_exact_position(self) -> None:
        project = CorrectionProject.from_jmap(
            JMap(
                objects=[
                    JMapObject(64, 512, OBJ_SAVE),
                    JMapObject(320, 224, OBJ_PLAYER_START),
                ]
            )
        )

        self.assertIsNone(project.start_save_id)
        self.assertEqual(project.start_position, (320, 224))
        self.assertIn(JMapObject(320, 224, OBJ_PLAYER_START), project.to_jmap().objects)

    def test_auto_start_can_use_flipped_save(self) -> None:
        project = CorrectionProject(objects=[])
        project.add_object(96, 512, OBJ_SAVE_FLIP)

        exported = project.to_jmap()

        self.assertIn(JMapObject(96, 512, OBJ_PLAYER_START), exported.objects)

    def test_selected_start_save_cannot_be_disabled(self) -> None:
        project = CorrectionProject(objects=[])
        save = project.add_object(96, 512, OBJ_SAVE)
        project.choose_start_save(save.object_id)
        project.set_enabled(save.object_id, False)

        with self.assertRaisesRegex(ValueError, "enabled save"):
            project.validate()

    def test_diagnostic_preview_labels_and_shows_disabled_candidates(self) -> None:
        project = CorrectionProject(objects=[])
        obj = project.add_object(32, 64, OBJ_MINI_BLOCK)
        project.set_enabled(obj.object_id, False)

        svg = render_correction_svg(project, show_ids=True, show_disabled=True)

        self.assertIn('id="correction-overlay"', svg)
        self.assertIn("stroke-dasharray", svg)
        self.assertIn("0001", svg)

    def test_object_type_parser_accepts_names_aliases_and_ids(self) -> None:
        self.assertEqual(parse_object_type("mini-block"), OBJ_MINI_BLOCK)
        self.assertEqual(parse_object_type("vine_right"), OBJ_WALLJUMP_RIGHT)
        self.assertEqual(parse_object_type(str(OBJ_WATER_2)), OBJ_WATER_2)

    def test_every_fixture_jmap_survives_correction_project_round_trip(self) -> None:
        fixture_paths = sorted(Path("fixtures").rglob("*.jmap"))
        self.assertTrue(fixture_paths)
        for fixture_path in fixture_paths:
            with self.subTest(jmap=fixture_path):
                original = JMap.from_file(fixture_path)
                exported = CorrectionProject.from_jmap(original, fixture_path).to_jmap()
                self.assertEqual(
                    Counter((obj.x, obj.y, obj.type_id) for obj in exported.objects),
                    Counter((obj.x, obj.y, obj.type_id) for obj in original.objects),
                )


if __name__ == "__main__":
    unittest.main()
