"""Original compact material can support a genuine overlapping block pose."""
from dataclasses import asdict, replace
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageOps

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_contours import EdgeEvidence


def continuous_scene(direction, *, material=(140, 160, 180), background=(85, 85, 85),
                     invert=False, dim=1, scale=1, hole=False, mini=False, triangle=False):
    image = Image.new('RGB', (800, 608), (0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((96, 96, 703, 511), fill=background)
    x, y = 320, 288
    dx, dy = direction
    draw.rectangle((x, y, x+31, y+31), fill=(15,)*3)
    draw.rectangle((x+2, y+2, x+29, y+29), fill=(235,)*3)
    draw.rectangle((x+4, y+4, x+27, y+27), fill=material)
    for a, b in ((7, 7), (24, 7), (7, 24), (24, 24)):
        draw.ellipse((x+a-2, y+b-2, x+a+2, y+b+2), outline=(25,)*3)
    sx = x+32 if dx > 0 else x-16 if dx < 0 else x
    sy = y+32 if dy > 0 else y-16 if dy < 0 else y
    w, h = (16, 32) if dx else (32, 16)
    draw.rectangle((sx, sy, sx+w-1, sy+h-1), fill=(15,)*3)
    draw.rectangle((sx+1, sy+1, sx+w-2, sy+h-2), fill=material)
    if dx:
        draw.line((sx+1, sy+2, sx+w-2, sy+2), fill=(235,)*3, width=2)
        draw.line((sx+1, sy+h-3, sx+w-2, sy+h-3), fill=(235,)*3, width=2)
    else:
        draw.line((sx+2, sy+1, sx+2, sy+h-2), fill=(235,)*3, width=2)
        draw.line((sx+w-3, sy+1, sx+w-3, sy+h-2), fill=(235,)*3, width=2)
    if hole:
        draw.rectangle((sx+2, sy+2, sx+w-3, sy+h//2-1), fill=background)
    if mini or triangle:
        draw.rectangle((sx, sy, sx+w-1, sy+h-1), fill=background)
        draw.polygon(((sx+w//2, sy), (sx, sy+h-1), (sx+w-1, sy+h-1)),
                     fill=material, outline=(15,)*3, width=2)
        if mini:
            draw.rectangle((sx, sy+16, sx+w-1, sy+h-1), fill=background)
    if invert:
        image = ImageOps.invert(image)
    if dim != 1:
        image = image.point(lambda value: round(value*dim))
    if scale != 1:
        image = image.resize((round(800*scale), round(608*scale)), Image.Resampling.NEAREST)
    rgb = RGBImage(image.width, image.height, image.tobytes())
    room = Box(0, 0, rgb.width, rgb.height)
    parent = scanner._geometry_detection('compact_adaptive_block', 1, x, y, .84, rgb, room, 32)
    learned = scanner._patch_color_profile(rgb, room, x, y, 32)
    return rgb, room, parent, learned, (x+dx, y+dy)


class CompactBlockContinuityTests(unittest.TestCase):
    def tearDown(self):
        scanner._PATCH_FEATURE_CACHE.clear()

    def outcome(self, direction, **options):
        image, room, parent, learned, expected = continuous_scene(direction, **options)
        old = asdict(parent)
        added = scanner._recover_adaptive_compact_continuous_blocks(
            [parent], [parent], image, room, image.pixel(0, 0), learned)
        self.assertEqual(old, asdict(parent))
        return [(d.x, d.y) for d in added], expected

    def test_four_directions_preserve_original_parent(self):
        for direction in ((16, 0), (-16, 0), (0, 16), (0, -16)):
            with self.subTest(direction=direction):
                added, expected = self.outcome(direction)
                self.assertEqual([expected], added)

    def test_palette_background_polarity_brightness(self):
        for options in (dict(material=(180, 140, 160), background=(95,)*3),
                        dict(material=(160, 180, 140), background=(75, 90, 100)),
                        dict(invert=True), dict(dim=.7), dict(invert=True, dim=.7)):
            with self.subTest(options=options):
                added, expected = self.outcome((16, 0), **options)
                self.assertEqual([expected], added)

    def test_fractional_and_double_capture(self):
        for scale in (1.25, 2):
            with self.subTest(scale=scale):
                added, expected = self.outcome((16, 0), scale=scale)
                self.assertEqual([expected], added)

    def test_hole_not_filled(self):
        self.assertEqual([], self.outcome((16, 0), hole=True)[0])

    def test_mini_and_triangle_not_rectangles(self):
        for options in (dict(mini=True), dict(triangle=True)):
            with self.subTest(options=options):
                self.assertEqual([], self.outcome((16, 0), **options)[0])

    def test_achromatic_role_ambiguity_does_not_invent_geometry(self):
        self.assertEqual([], self.outcome((16, 0), material=(155,)*3)[0])

    def test_emitted_hypotheses_cannot_be_teachers(self):
        image, room, parent, learned, _ = continuous_scene((16, 0))
        for candidate in (replace(parent, kind='compact_continuous_block'),
                          replace(parent, x=parent.x+16)):
            with self.subTest(candidate=candidate):
                self.assertEqual([], scanner._recover_adaptive_compact_continuous_blocks(
                    [candidate], [candidate], image, room, image.pixel(0, 0), learned))

    def test_existing_mini_coverage_is_not_a_new_gain(self):
        image, room, parent, learned, _ = continuous_scene((16, 0))
        minis = [scanner._geometry_detection('mini_block', 2, 352, y, .9, image, room, 16)
                 for y in (288, 304)]
        self.assertEqual([], scanner._recover_adaptive_compact_continuous_blocks(
            [parent, *minis], [parent], image, room, image.pixel(0, 0), learned))

    def test_unknown_or_padded_exterior_cannot_be_background(self):
        image, room, parent, learned, _ = continuous_scene((16, 0))
        with patch.object(scanner, '_patch_color_profile', side_effect=AssertionError('unknown probe')):
            self.assertFalse(scanner._compact_extension_material_supported(image, room, 688, 288, 16, 0, learned))

    def test_unknown_contour_does_not_support_a_long_envelope(self):
        class Unknown:
            def edge(self, first, second):
                return EdgeEvidence(12, True, ())
        self.assertFalse(scanner._compact_rectangle_contour_closed(
            Unknown(), 320, 288, (1, 1), width=48, height=32))
