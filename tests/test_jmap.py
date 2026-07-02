from __future__ import annotations

from collections import Counter
import unittest

from jtool_scanner.codec import base32_to_float, float_to_base32
from jtool_scanner.constants import OBJ_BLOCK, OBJ_PLAYER_START, OBJ_SAVE, OBJ_SPIKE_UP
from jtool_scanner.jmap import JMap, JMapObject
from jtool_scanner.save_picker import choose_save, move_start_to_save


class JMapTests(unittest.TestCase):
    def test_float_codec_matches_known_jtool_values(self) -> None:
        self.assertEqual(float_to_base32(305.0), "40sog00000000")
        self.assertEqual(float_to_base32(151.0), "40on000000000")
        self.assertEqual(base32_to_float("40sog00000000"), 305.0)
        self.assertEqual(base32_to_float("40on000000000"), 151.0)

    def test_round_trip_compact_and_expanded_objects(self) -> None:
        original = JMap(
            player_save_x=49,
            player_save_y=55,
            objects=[
                JMapObject(0, 0, OBJ_BLOCK),
                JMapObject(32, 0, OBJ_BLOCK),
                JMapObject(96, 64, OBJ_SPIKE_UP),
                JMapObject(32, 512, OBJ_SAVE),
                JMapObject(128, 64, OBJ_PLAYER_START),
            ],
        )

        parsed = JMap.from_text(original.to_text())

        self.assertEqual(parsed.version, original.version)
        self.assertEqual(
            Counter((obj.x, obj.y, obj.type_id) for obj in parsed.objects),
            Counter((obj.x, obj.y, obj.type_id) for obj in original.objects),
        )
        self.assertEqual(parsed.player_save_x, 49.0)
        self.assertEqual(parsed.player_save_y, 55.0)

    def test_auto_save_policy_prefers_bottom_left_region(self) -> None:
        jmap = JMap(
            objects=[
                JMapObject(256, 64, OBJ_SAVE),
                JMapObject(384, 544, OBJ_SAVE),
                JMapObject(672, 512, OBJ_SAVE),
            ]
        )

        choice = choose_save(jmap, "auto")

        self.assertIsNotNone(choice)
        self.assertEqual((choice.save.x, choice.save.y), (384, 544))

    def test_save_policy_can_choose_index(self) -> None:
        jmap = JMap(
            objects=[
                JMapObject(384, 544, OBJ_SAVE),
                JMapObject(256, 64, OBJ_SAVE),
                JMapObject(672, 512, OBJ_SAVE),
            ]
        )

        choice = choose_save(jmap, "index:1")

        self.assertIsNotNone(choice)
        self.assertEqual((choice.save.x, choice.save.y), (672, 512))

    def test_move_start_to_save_replaces_existing_start_and_updates_player_save(self) -> None:
        jmap = JMap(
            objects=[
                JMapObject(32, 512, OBJ_SAVE),
                JMapObject(128, 64, OBJ_PLAYER_START),
            ]
        )

        choice = move_start_to_save(jmap, "auto")

        self.assertIsNotNone(choice)
        self.assertEqual([(obj.x, obj.y) for obj in jmap.objects_of_type(OBJ_PLAYER_START)], [(32, 512)])
        self.assertEqual(jmap.player_save_x, 49)
        self.assertEqual(jmap.player_save_y, 535)


if __name__ == "__main__":
    unittest.main()
