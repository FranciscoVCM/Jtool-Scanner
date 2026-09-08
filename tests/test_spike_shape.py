import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage, load_png
from jtool_scanner.scanner import Detection, _reconcile_directed_material_spikes
from jtool_scanner.spike_shape import SpikeShapeField, VERTICES, corroborated_refits


def scene(objects, foreground=35, background=220, scale=1):
    image = Image.new('RGB', (800, 608), (background,) * 3)
    draw = ImageDraw.Draw(image)
    for direction, x, y in objects:
        draw.polygon([(x + px, y + py) for px, py in VERTICES[direction]], fill=(foreground,) * 3)
    image = image.resize((round(800 * scale), round(608 * scale)), Image.Resampling.BILINEAR)
    return RGBImage(image.width, image.height, image.tobytes())


class SpikeShapeTests(unittest.TestCase):
    def test_shape_direction_survives_brightness_inversion_and_capture_scale(self):
        for foreground, background, scale in ((35, 220, 1), (220, 35, 1.25), (90, 150, 1.5)):
            for direction in VERTICES:
                with self.subTest(direction=direction, scale=scale):
                    image = scene([(direction, 320, 320)], foreground, background, scale)
                    field = SpikeShapeField(image, Box(0, 0, image.width, image.height))
                    self.assertGreaterEqual(field.score(320, 320, direction), 0.9)
                    self.assertGreaterEqual(abs(field.contrast(320, 320, direction)), 0.5)
                    self.assertEqual(field.score(-8, 320, direction), -1)

    def test_partial_contour_position_ambiguity_abstains(self):
        seeds = [(3, 240, 256), (3, 320, 224), (3, 400, 256), (3, 432, 336)]
        image = scene([*seeds, (4, 320, 320)])
        self.assertEqual(
            corroborated_refits(image, Box(0, 0, 800, 608), [*seeds, (6, 320, 328)]),
            {},
        )

    def test_neon_source_refits_direction_with_independent_local_support(self):
        image = load_png(Path(__file__).resolve().parents[1] / 'fixtures/regressions/unseen-rooms/cn3-neon/floor-09-source.png')
        seeds = [(6,176,320),(3,176,352),(6,128,448),(3,256,448),(3,144,512)]
        inverted = RGBImage(image.width, image.height, image.data.translate(bytes(range(255, -1, -1))))
        for source in (image, inverted):
            with self.subTest(inverted=source is inverted):
                result = corroborated_refits(source, Box(0,0,source.width,source.height), [*seeds,(4,160,416)])
                self.assertEqual(result, {(4,160,416):(6,160,416)})

    def test_duplicate_hypotheses_are_not_independent_material_witnesses(self):
        image = load_png(Path(__file__).resolve().parents[1] / 'fixtures/regressions/unseen-rooms/cn3-neon/floor-09-source.png')
        result = corroborated_refits(image, Box(0,0,image.width,image.height), [(6,128,448)] * 3 + [(4,160,416)])
        self.assertEqual(result, {})

    def test_background_triangle_gap_is_not_corroborated(self):
        seeds = [(3, 240, 256), (3, 320, 224), (3, 400, 256), (3, 432, 336)]
        image = scene([*seeds, (3, 304, 320), (3, 336, 320)])
        field = SpikeShapeField(image, Box(0, 0, 800, 608))
        self.assertGreaterEqual(field.score(320, 320, 6), 0.9)
        self.assertLess(field.contrast(320, 320, 6), 0)
        self.assertNotIn((4, 320, 320), corroborated_refits(image, Box(0, 0, 800, 608), [*seeds, (4, 320, 320)]))

    def test_too_few_reliable_neighbors_abstains(self):
        image = scene([(3, 240, 256), (4, 320, 320)])
        self.assertEqual(corroborated_refits(image, Box(0, 0, 800, 608), [(3, 240, 256), (6, 320, 328)]), {})

    def test_refit_onto_existing_target_removes_only_duplicate(self):
        image = scene([(4, 320, 320)])
        target = Detection('spike_right', 4, 320, 320, .8, Box(320, 320, 32, 32))
        alias = Detection('spike_down', 6, 320, 328, .4, Box(320, 328, 32, 32))
        with patch('jtool_scanner.scanner.corroborated_refits', return_value={(6, 320, 328): (4, 320, 320)}):
            self.assertEqual(_reconcile_directed_material_spikes([alias, target], image, Box(0, 0, 800, 608)), [target])


if __name__ == '__main__':
    unittest.main()
