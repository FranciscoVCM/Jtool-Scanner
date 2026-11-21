import tempfile
from pathlib import Path
from unittest import TestCase

from PIL import Image

from jtool_scanner import scanner
from jtool_scanner.constants import OBJ_BLOCK, OBJ_MINI_BLOCK, OBJ_SAVE
from jtool_scanner.geometry import Box
from jtool_scanner.image import load_png
from jtool_scanner.scanner import Detection, merge_mini_quads_into_blocks

ASSETS = Path(scanner.__file__).with_name("assets") / "jtool-pat-default"


def _mini(x, y, score=0.9):
    return Detection("mini_block", OBJ_MINI_BLOCK, x, y, score, Box(x, y, 16, 16))


class PixelExactSaveLampTests(TestCase):
    def _scene(self, positions):
        canvas = Image.new("RGB", (800, 608), (211, 211, 211))
        with Image.open(ASSETS / "save-frame0.png") as opened:
            save = opened.convert("RGBA")
        canvas = canvas.convert("RGBA")
        for x, y in positions:
            canvas.alpha_composite(save, (x, y))
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        canvas.convert("RGB").save(tmp.name)
        self.addCleanup(Path(tmp.name).unlink)
        return load_png(tmp.name)

    def test_outlined_lamp_inside_yellow_body_counts_as_save_colour(self):
        positions = [(160, 320), (320, 544), (512, 544)]
        found = scanner._detect_saves(self._scene(positions), Box(0, 0, 800, 608), 8)
        self.assertEqual(sorted((d.type_id, d.x, d.y) for d in found),
                         sorted((OBJ_SAVE, x, y) for x, y in positions))

    def test_yellow_only_square_is_still_not_a_save(self):
        canvas = Image.new("RGB", (800, 608), (211, 211, 211))
        canvas.paste((223, 214, 64), (300, 300, 323, 318))
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        canvas.save(tmp.name)
        self.addCleanup(Path(tmp.name).unlink)
        self.assertEqual(scanner._detect_saves(load_png(tmp.name), Box(0, 0, 800, 608), 8), [])


def _floor(count=2):
    # Ordinary full-block terrain elsewhere, so the room is not mini-dominated.
    return [Detection("block", OBJ_BLOCK, 32 * i, 576, 1.0, Box(32 * i, 576, 32, 32)) for i in range(count)]


def _new(merged, floor):
    return [(d.type_id, d.x, d.y) for d in merged if d not in floor]


class MiniQuadMergeTests(TestCase):
    def test_complete_aligned_quad_becomes_one_block(self):
        floor = _floor()
        dets = floor + [_mini(64, 96), _mini(80, 96), _mini(64, 112), _mini(80, 112, score=0.5)]
        merged = merge_mini_quads_into_blocks(dets)
        self.assertEqual(_new(merged, floor), [(OBJ_BLOCK, 64, 96)])
        self.assertEqual(merged[-1].score, 0.5)
        self.assertEqual(merged[-1].image_box, Box(64, 96, 32, 32))

    def test_offset_quad_merges_when_no_aligned_quad_exists(self):
        floor = _floor()
        dets = floor + [_mini(80, 96), _mini(96, 96), _mini(80, 112), _mini(96, 112)]
        self.assertEqual(_new(merge_mini_quads_into_blocks(dets), floor), [(OBJ_BLOCK, 80, 96)])

    def test_mini_dominated_room_keeps_its_minis(self):
        # Like CN3-16/18: terrain is 16px art with no full blocks at all.
        dets = [_mini(x, y) for x in range(0, 128, 16) for y in (0, 16)]
        self.assertIs(merge_mini_quads_into_blocks(dets), dets)

    def test_incomplete_quads_and_other_objects_are_unchanged(self):
        dets = [_mini(0, 0), _mini(16, 0), _mini(0, 16),
                Detection("spike_up", 3, 32, 0, 0.8, Box(32, 0, 32, 32))]
        self.assertIs(merge_mini_quads_into_blocks(dets), dets)

    def test_aligned_grid_is_preferred_in_a_wider_strip(self):
        # 3x2 minis: x=64..96. Only one 32px block fits; the aligned one wins.
        floor = _floor()
        dets = floor + [_mini(x, y) for x in (64, 80, 96) for y in (0, 16)]
        merged = merge_mini_quads_into_blocks(dets)
        self.assertEqual(sorted(_new(merged, floor)),
                         [(OBJ_BLOCK, 64, 0), (OBJ_MINI_BLOCK, 96, 0), (OBJ_MINI_BLOCK, 96, 16)])

    def test_existing_block_at_origin_is_not_duplicated(self):
        dets = [Detection("block", OBJ_BLOCK, 0, 0, 1.0, Box(0, 0, 32, 32)),
                _mini(0, 0), _mini(16, 0), _mini(0, 16), _mini(16, 16)]
        self.assertIs(merge_mini_quads_into_blocks(dets), dets)
