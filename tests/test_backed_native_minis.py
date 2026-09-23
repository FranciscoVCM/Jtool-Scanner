import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.scanner import (
    Detection, _backed_native_mini_structures,
    _recover_backed_native_mini_structures,
)
from jtool_scanner.spike_shape import VERTICES


def scene(*, directions=(3,), foreground=(220, 220, 220),
          background=(35, 35, 35), scale=1):
    image = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(image)
    for x in (288, 304):
        draw.rectangle((x, 336, x + 15, 351), fill=foreground)
        for direction in directions:
            y = 320 if direction == 3 else 352
            draw.polygon([(x + px / 2, y + py / 2)
                          for px, py in VERTICES[direction]], fill=foreground)
    # A stripe crossing the solid backing creates a visible native-size base
    # termination; an unmarked same-color join would be size-ambiguous.
    draw.rectangle((288, 338, 319, 342), fill=background)
    if 6 in directions:
        draw.rectangle((288, 346, 319, 350), fill=background)
    if scale != 1:
        image = image.resize((round(800 * scale), round(608 * scale)),
                             Image.Resampling.BILINEAR)
    return RGBImage(image.width, image.height, image.tobytes())


class BackedNativeMiniTests(unittest.TestCase):
    def test_backed_pair_transfers_across_palette_and_capture_scale(self):
        for foreground, background, scale in (
            ((220, 220, 220), (35, 35, 35), 1),
            ((40, 40, 40), (210, 210, 210), 1.25),
            ((160, 50, 75), (230, 230, 210), 1.5),
        ):
            with self.subTest(foreground=foreground, scale=scale):
                image = scene(foreground=foreground, background=background,
                              scale=scale)
                self.assertEqual(_backed_native_mini_structures(
                    image, Box(0, 0, image.width, image.height),
                ), ([(7, 288, 320), (7, 304, 320)], []))

    def test_opposing_rails_recover_intervening_solid16(self):
        image = scene(directions=(3, 6))
        minis, solids = _backed_native_mini_structures(
            image, Box(0, 0, image.width, image.height),
        )
        self.assertEqual(minis, [(7, 288, 320), (7, 304, 320),
                                 (10, 288, 352), (10, 304, 352)])
        self.assertEqual(solids, [(288, 336), (304, 336)])

    def test_side_facing_backed_pairs_keep_their_directions(self):
        image = Image.new('RGB', (800, 608), (25, 30, 35))
        draw = ImageDraw.Draw(image)
        draw.rectangle((304, 288, 319, 319), fill=(205, 130, 75))
        for y in (288, 304):
            for direction, x in ((4, 320), (5, 288)):
                draw.polygon([(x + px / 2, y + py / 2)
                              for px, py in VERTICES[direction]],
                             fill=(205, 130, 75))
        draw.rectangle((314, 288, 318, 319), fill=(25, 30, 35))
        draw.rectangle((305, 288, 309, 319), fill=(25, 30, 35))
        rgb = RGBImage(800, 608, image.tobytes())
        minis, solids = _backed_native_mini_structures(rgb, Box(0, 0, 800, 608))
        self.assertEqual(minis, [(8, 320, 288), (8, 320, 304),
                                 (9, 288, 288), (9, 288, 304)])
        self.assertEqual(solids, [])

    def test_full_size_tips_and_floor_text_do_not_recover(self):
        image = Image.new('RGB', (800, 608), (35, 35, 35))
        draw = ImageDraw.Draw(image)
        for x in (280, 296, 312, 328):
            draw.polygon([(x + px, 320 + py) for px, py in VERTICES[3]],
                         fill=(220, 220, 220))
        draw.text((288, 400), '-45 25 26 27', fill=(220, 220, 220))
        rgb = RGBImage(800, 608, image.tobytes())
        self.assertEqual(_backed_native_mini_structures(
            rgb, Box(0, 0, 800, 608),
        ), ([], []))

    def test_recovery_preserves_existing_objects_and_avoids_duplicates(self):
        image = scene(directions=(3, 6))
        room = Box(0, 0, image.width, image.height)
        save = Detection('save', 12, 40, 48, .9, Box(40, 48, 32, 32))
        existing = Detection('mini', 7, 288, 320, .9, Box(288, 320, 16, 16))
        result = _recover_backed_native_mini_structures([save, existing], image, room)
        self.assertEqual(result[:2], [save, existing])
        self.assertEqual({(d.type_id, d.x, d.y) for d in result[2:]}, {
            (7, 304, 320), (10, 288, 352), (10, 304, 352),
            (2, 288, 336), (2, 304, 336),
        })
        self.assertEqual(_recover_backed_native_mini_structures(result, image, room), result)


if __name__ == '__main__':
    unittest.main()
