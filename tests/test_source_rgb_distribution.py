"""Portable original-source RGB/geometry evidence, no room answers or fixtures."""
import unittest
from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_sampling import SourceFrame
from scripts.source_rgb_distribution import SourceRGBDistribution, _disjoint


PARENTS = ((64, 160), (160, 160), (256, 160))
GLYPHS = ((3, 480, 64), (3, 576, 64), (3, 672, 64))
PALETTES = (((230, 235, 240), (40, 50, 65), (80, 90, 105)),
            ((20, 25, 35), (200, 190, 180), (160, 150, 140)),
            ((0, 130, 0), (255, 0, 0), (220, 35, 10)),
            ((55, 95, 135), (150, 190, 210), (125, 165, 185)))


def scene(palette=0, scale=1., kind='rectangle'):
    bg, dark, light = PALETTES[palette]
    image = Image.new('RGB', (800, 608), bg)
    tile = Image.new('RGB', (32, 32), dark)
    draw = ImageDraw.Draw(tile)
    for i in range(4, 28, 4):
        draw.line((4, i, 27, i), fill=light, width=2)
    for x, y in PARENTS:
        image.paste(tile, (x, y))
    for t, x, y in GLYPHS:
        ImageDraw.Draw(image).polygon(((x, y + 32), (x + 16, y), (x + 32, y + 32)), fill=dark)
    draw = ImageDraw.Draw(image)
    if kind == 'rectangle':
        draw.rectangle((352, 160, 383, 191), fill=dark)
        # Different interior spatial pattern, same actual source RGB material.
        for x in range(356, 380, 4):
            draw.line((x, 164, x, 187), fill=light, width=2)
    elif kind == 'triangle':
        draw.polygon(((352, 192), (368, 160), (384, 192)), fill=dark)
    elif kind == 'empty_frame':
        draw.rectangle((352, 160, 383, 191), outline=dark, width=2)
    elif kind == 'text':
        draw.text((352, 160), '93 -45', fill=dark)
    image = image.resize((round(800 * scale), round(608 * scale)), Image.Resampling.BILINEAR)
    rgb = RGBImage(image.width, image.height, image.tobytes())
    return SourceFrame(rgb, Box(0, 0, rgb.width, rgb.height))


class SourceRGBDistributionTests(unittest.TestCase):
    def test_new_interior_pattern_across_rgb_polarity_isoluminance_and_scale(self):
        for palette in range(len(PALETTES)):
            for scale in (1., 1.25, 1.5):
                with self.subTest(palette=palette, scale=scale):
                    model = SourceRGBDistribution(scene(palette, scale), PARENTS, GLYPHS)
                    self.assertIsNone(model.reason)
                    proof = model.support(352, 160)
                    self.assertTrue(proof['passed'], proof)
                    self.assertEqual(proof['origin'], [352, 160])

    def test_empty_background_triangles_text_and_empty_frames_are_not_terrain(self):
        for kind in ('background', 'triangle', 'empty_frame', 'text'):
            for palette in range(len(PALETTES)):
                with self.subTest(kind=kind, palette=palette):
                    model = SourceRGBDistribution(scene(palette, kind=kind), PARENTS, GLYPHS)
                    self.assertFalse(model.support(352, 160)['passed'])

    def test_two_or_duplicate_parents_do_not_supply_three_original_witnesses(self):
        for parents in (PARENTS[:2], PARENTS[:2] * 3):
            model = SourceRGBDistribution(scene(), parents, GLYPHS)
            self.assertIsNotNone(model.reason)
            self.assertFalse(model.support(352, 160)['passed'])

    def test_two_or_duplicate_background_fronts_do_not_supply_three(self):
        for glyphs in (GLYPHS[:2], GLYPHS[:2] * 3):
            model = SourceRGBDistribution(scene(), PARENTS, glyphs)
            self.assertIsNotNone(model.reason)
            self.assertFalse(model.support(352, 160)['passed'])

    def test_query_cannot_teach_or_use_its_own_parent_body(self):
        model = SourceRGBDistribution(scene(), PARENTS, GLYPHS)
        teachers = model.parents, model.background
        self.assertFalse(model.support(*PARENTS[0])['passed'])
        first = model.support(352, 160)
        first['phases'].clear()
        second = model.support(352, 160)
        self.assertTrue(second['phases'])
        self.assertEqual((model.parents, model.background), teachers)

    def test_unknown_body_context_and_noninteger_inputs_abstain_or_reject(self):
        model = SourceRGBDistribution(scene(), PARENTS, GLYPHS)
        for point in ((-1, 160), (784, 160), (352, 608), (0, 0)):
            with self.subTest(point=point):
                self.assertFalse(model.support(*point)['passed'])
        for point in ((True, 160), (352., 160), (352, float('nan'))):
            with self.assertRaises(ValueError):
                model.support(*point)

    def test_arbitrary_background_front_and_nonfinite_parent_are_not_trusted(self):
        model = SourceRGBDistribution(scene(), PARENTS, ((3, 480, 400),) * 3)
        self.assertIsNotNone(model.reason)
        self.assertFalse(model.support(352, 160)['passed'])
        with self.assertRaises(ValueError):
            SourceRGBDistribution(scene(), ((float('inf'), 160),), GLYPHS)
        with self.assertRaises(ValueError):
            SourceRGBDistribution(scene(), PARENTS, ((1, 480, 64),))

    def test_extended_crop_never_uses_displayed_padding_as_original_evidence(self):
        full = scene()
        image = full.original_snapshot()
        crop = Box(160, 0, 640, 608)
        extended = SourceFrame(image, crop, extent=Box(0, 0, 800, 608), canonical=image)
        model = SourceRGBDistribution(extended, PARENTS, GLYPHS)
        self.assertEqual(model.reason, 'extended source transform not qualified')
        self.assertFalse(model.support(352, 160)['passed'])
        self.assertIsNone(extended.original_pixel(64, 160))

    def test_fractional_physical_pixel_overlap_is_not_independence(self):
        model = SourceRGBDistribution(scene(scale=1.23), PARENTS, GLYPHS)
        first = model._physical(64, 160, 32)
        second = model._physical(96, 160, 32)
        self.assertFalse(_disjoint(first, second))
        self.assertTrue(_disjoint(first, model._physical(104, 160, 32)))

    def test_parent_metadata_does_not_replace_actual_source_geometry(self):
        full = scene()
        # These are empty source regions, even if a caller calls them parents.
        model = SourceRGBDistribution(full, ((64, 400), (160, 400), (256, 400)), GLYPHS)
        self.assertIsNotNone(model.reason)
        self.assertFalse(model.support(352, 160)['passed'])


if __name__ == '__main__':
    unittest.main()
