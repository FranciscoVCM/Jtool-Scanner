import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.scanner import Detection, _recover_directed_mini_runs
from jtool_scanner.spike_shape import (
    SpikeShapeField, VERTICES, corroborated_mini_runs,
)


SEEDS = [(3, 224, 224), (3, 288, 224), (3, 352, 224),
         (6, 224, 448), (6, 288, 448), (6, 352, 448),
         (4, 128, 320), (5, 448, 320)]


def scene(minis=(), *, seeds=SEEDS, fulls=(), foreground=(220, 220, 220),
          background=(35, 35, 35), scale=1):
    image = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(image)
    for size, objects in ((32, [*seeds, *fulls]), (16, minis)):
        for direction, x, y in objects:
            draw.polygon([(x + px * size / 32, y + py * size / 32)
                          for px, py in VERTICES[direction]], fill=foreground)
    if scale != 1:
        image = image.resize((round(800 * scale), round(608 * scale)),
                             Image.Resampling.BILINEAR)
    return RGBImage(image.width, image.height, image.tobytes())


def recover(image, seeds=SEEDS):
    return corroborated_mini_runs(image, Box(0, 0, image.width, image.height), seeds)


class NativeMiniRunTests(unittest.TestCase):
    def test_integration_retains_objects_and_uses_native_source_boxes(self):
        image = scene()
        save = Detection('save', 12, 40, 48, .9, Box(40, 48, 32, 32))
        existing = Detection('mini', 10, 288, 320, .9, Box(288, 320, 16, 16))
        with patch('jtool_scanner.scanner.corroborated_mini_runs',
                   return_value=[(7, 288, 320), (7, 320, 320)]):
            result = _recover_directed_mini_runs([save, existing], image,
                                                 Box(16, 8, 400, 304))
        self.assertEqual(result[:2], [save, existing])
        self.assertEqual(len(result), 3)
        self.assertEqual((result[2].type_id, result[2].x, result[2].y), (7, 320, 320))
        self.assertEqual(result[2].image_box, Box(176, 168, 8, 8))

    def test_native_size_is_explicit_and_bounded(self):
        image = scene([(3, 784, 592)])
        room = Box(0, 0, 800, 608)
        mini = SpikeShapeField(image, room, native_size=16)
        self.assertGreaterEqual(mini.localized_score(784, 592, 3), 10 / 12)
        self.assertEqual(mini.score(785, 592, 3), -1)
        self.assertEqual(SpikeShapeField(image, room).score(784, 592, 3), -1)
        with self.assertRaises(ValueError):
            SpikeShapeField(image, room, native_size=24)

    def test_all_directions_survive_scale_polarity_and_colored_materials(self):
        for direction in VERTICES:
            dx, dy = (16, 0) if direction in (3, 6) else (0, 16)
            objects = [(direction, 288 + i * dx, 320 + i * dy) for i in range(4)]
            expected = {(d + 4, x, y) for d, x, y in objects}
            for foreground, background, scale in (
                ((220, 220, 220), (35, 35, 35), 1),
                ((35, 35, 35), (220, 220, 220), 1.25),
                ((90, 90, 90), (150, 150, 150), 1.5),
                ((210, 170, 95), (65, 35, 90), 1.25),
            ):
                with self.subTest(direction=direction, scale=scale, foreground=foreground):
                    self.assertEqual(set(recover(scene(objects, foreground=foreground,
                        background=background, scale=scale))), expected)

    def test_duplicate_or_insufficient_witnesses_cannot_bootstrap(self):
        minis = [(3, x, 320) for x in (288, 304, 320)]
        image = scene(minis)
        for seeds in ([], SEEDS[:2], SEEDS[:1] * 8):
            with self.subTest(seeds=seeds):
                self.assertEqual(recover(image, seeds), [])

    def test_isolated_and_pair_shapes_do_not_become_a_run(self):
        self.assertEqual(recover(scene([(3, 288, 320), (3, 304, 320)])), [])

    def test_triangle_gaps_and_full_triangle_tips_are_not_minis(self):
        # Offset full spikes have their half-size tips on the native16 lattice.
        fulls = [(3, x, 320) for x in (280, 296, 312, 328)]
        self.assertEqual(recover(scene(fulls=fulls)), [])
        # Mini spikes shifted8 put their complementary background gaps on16.
        minis = [(3, x, 320) for x in (280, 296, 312, 328)]
        self.assertEqual(recover(scene(minis)), [])

    def test_rectangular_repeated_texture_and_floor_text_are_not_minis(self):
        original = scene()
        image = Image.frombytes('RGB', (800, 608), original.data)
        draw = ImageDraw.Draw(image)
        for x in range(256, 400, 16):
            draw.rectangle((x, 320, x + 12, 332), fill=(220, 220, 220))
            draw.line((x, 360, x + 16, 376), fill=(220, 220, 220), width=2)
        draw.text((288, 400), '-45 25 26 27', fill=(220, 220, 220))
        self.assertEqual(recover(RGBImage(800, 608, image.tobytes())), [])

    def test_isoluminant_evidence_abstains_without_discarding_color(self):
        image = scene([(3, x, 320) for x in (288, 304, 320)],
                      foreground=(180, 0, 0), background=(0, 92, 0))
        self.assertEqual(recover(image), [])


if __name__ == '__main__':
    unittest.main()
