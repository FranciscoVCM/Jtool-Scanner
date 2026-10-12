"""Real RGB raster evidence; no reference maps or image-specific production rules."""
from types import SimpleNamespace
import unittest

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_rectangle_prototypes import source_rectangle_proposals


PALETTES = (((235, 235, 235), (80, 20, 30)),
            ((25, 35, 45), (180, 200, 220)),
            ((0, 130, 0), (255, 0, 0)),
            ((115, 130, 145), (60, 75, 90)))


def scene(palette=0, scale=1, teachers=3, kind='rectangles'):
    background, ink = PALETTES[palette]
    raster = Image.new('RGB', (800, 608), background)
    targets = [(168 + 96 * i, 160) for i in range(teachers)]
    locators = []
    for x, y in targets:
        tile = Image.new('RGB', (32, 32), background)
        pen = ImageDraw.Draw(tile)
        pen.rectangle((0, 0, 31, 31), outline=ink, width=2)
        pen.line((0, 0, 31, 31), fill=ink, width=2)
        pen.line((0, 31, 31, 0), fill=ink, width=2)
        pen.line((0, 7, 31, 7), fill=ink)
        pen.line((0, 24, 31, 24), fill=ink)
        if kind == 'triangles':
            mask = Image.new('L', (32, 32))
            ImageDraw.Draw(mask).polygon([(0, 31), (16, 0), (31, 31)], fill=255)
            raster.paste(tile, (x, y), mask)
        else:
            raster.paste(tile, (x, y))
        locators.append(SimpleNamespace(type_id=1, x=x - 8, y=y + 8))
    raster = raster.resize((round(800 * scale), round(608 * scale)), Image.Resampling.BILINEAR)
    image = RGBImage(raster.width, raster.height, raster.tobytes())
    return image, Box(0, 0, image.width, image.height), locators, {(1, x, y) for x, y in targets}


class SourceRectanglePrototypeTests(unittest.TestCase):
    def test_offset_hollow_frames_across_palette_polarity_scale(self):
        for palette in range(4):
            for scale in (1., 1.25):
                with self.subTest(palette=palette, scale=scale):
                    image, room, locators, targets = scene(palette, scale)
                    proposed, proof = source_rectangle_proposals(image, room, locators)
                    self.assertEqual(proposed, targets)
                    for model in proof['models']:
                        self.assertGreaterEqual(len(model['teachers']), 3)
                        for i, (x, y) in enumerate(model['teachers']):
                            for px, py in model['teachers'][:i]:
                                self.assertTrue(abs(x - px) >= 32 or abs(y - py) >= 32)

    def test_two_frames_and_duplicate_locators_do_not_self_teach_third(self):
        image, room, locators, _ = scene(teachers=2)
        proposed, _ = source_rectangle_proposals(image, room, locators * 3)
        self.assertFalse(proposed)

    def test_joined_triangle_artwork_is_not_rectangle_identity(self):
        for palette in range(4):
            with self.subTest(palette=palette):
                image, room, locators, _ = scene(palette, kind='triangles')
                proposed, _ = source_rectangle_proposals(image, room, locators)
                self.assertFalse(proposed)

    def test_unrelated_original_locator_does_not_create_fills(self):
        for scale in (1., 1.25):
            image, room, locators, targets = scene(scale=scale)
            locators.append(SimpleNamespace(type_id=1, x=504, y=168))
            proposed, _ = source_rectangle_proposals(image, room, locators)
            self.assertEqual(proposed, targets)

    def test_open_frames_cannot_teach_closed_frames(self):
        for palette in range(4):
            image, room, locators, targets = scene(palette)
            raster = Image.frombytes('RGB', (image.width, image.height), image.data)
            draw = ImageDraw.Draw(raster)
            for _, x, y in targets:
                draw.rectangle((x + 3, y + 30, x + 28, y + 31), fill=raster.getpixel((0, 0)))
            proposed, _ = source_rectangle_proposals(
                RGBImage(raster.width, raster.height, raster.tobytes()), room, locators)
            self.assertFalse(proposed)

    def test_gradient_alone_is_not_rectangle_identity(self):
        raster = Image.new('RGB', (800, 608))
        draw = ImageDraw.Draw(raster)
        for y in range(608):
            draw.line((0, y, 799, y), fill=(y % 128 + 64, y % 128 + 32, y % 128 + 16))
        image = RGBImage(800, 608, raster.tobytes())
        locators = [SimpleNamespace(type_id=1, x=x, y=168) for x in (160, 256, 352)]
        proposed, _ = source_rectangle_proposals(image, Box(0, 0, 800, 608), locators)
        self.assertFalse(proposed)

    def test_context_reuse_preserves_inputs_and_cannot_add_glyph_teachers(self):
        image, room, locators, targets = scene()
        original_bytes, original_locators = image.data, [vars(d).copy() for d in locators]
        context = SourceEvidenceContext(image, room, [])
        first = source_rectangle_proposals(image, room, locators, source_context=context)
        second = source_rectangle_proposals(image, room, locators, source_context=context)
        self.assertEqual(first, second)
        self.assertEqual(first[0], targets)
        self.assertIs(image.data, original_bytes)
        self.assertEqual([vars(d) for d in locators], original_locators)
        self.assertEqual(context.statistics()['glyph_builds'], 1)
        with self.assertRaisesRegex(ValueError, 'original locators changed'):
            source_rectangle_proposals(image, room,
                locators + [SimpleNamespace(type_id=3, x=168, y=128)], source_context=context)

    def test_no_original_full_locators_does_not_build_appearance(self):
        image, room, _, _ = scene()
        context = SourceEvidenceContext(image, room, [])
        proposed, proof = source_rectangle_proposals(image, room, [], source_context=context)
        self.assertFalse(proposed)
        self.assertEqual(proof['candidates'], 0)
        self.assertEqual(context.statistics()['glyph_builds'], 0)


if __name__ == '__main__':
    unittest.main()
