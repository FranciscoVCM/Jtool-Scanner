from __future__ import annotations

import unittest

from jtool_scanner.app import (
    app_metadata,
    export_jmap_text,
    import_jmap_text,
    preview_project,
    scan_image_bytes,
)
from jtool_scanner.constants import OBJ_BLOCK, OBJ_PLAYER_START, OBJ_WARP
from jtool_scanner.jmap import JMap


SAMPLE_JMAP = (
    "jtool|1.3.5|inf:1|dot:0|sav:1|bor:0|"
    "px:40u8g00000000|py:40ubg00000000|ps:1|pg:1|"
    "objects:-h01f01g01h0-g0kg0\n"
)


class GraphicalAppTests(unittest.TestCase):
    def test_metadata_exposes_room_and_supported_objects(self) -> None:
        metadata = app_metadata()

        self.assertEqual(metadata["room"], {"width": 800, "height": 608})
        object_types = {item["id"]: item["name"] for item in metadata["object_types"]}
        self.assertEqual(object_types[OBJ_BLOCK], "block")
        self.assertEqual(object_types[OBJ_WARP], "warp")

    def test_jmap_import_preview_and_export_round_trip(self) -> None:
        project = import_jmap_text(SAMPLE_JMAP, "infinite.jmap")

        self.assertEqual(project.infinite_jump, 1)
        self.assertEqual(len(project.objects), 3)
        preview = preview_project(project.to_dict())
        self.assertIn("<svg", preview)
        self.assertIn(">start<", preview)

        exported = JMap.from_text(export_jmap_text(project.to_dict()))
        self.assertEqual(exported.infinite_jump, 1)
        self.assertEqual(len(exported.objects), 4)
        self.assertEqual(
            sum(obj.type_id == OBJ_PLAYER_START for obj in exported.objects),
            1,
        )

    def test_scan_rejects_non_png_upload(self) -> None:
        with self.assertRaisesRegex(ValueError, "accepts PNG"):
            scan_image_bytes(b"not an image", "screen.jpg")


if __name__ == "__main__":
    unittest.main()
