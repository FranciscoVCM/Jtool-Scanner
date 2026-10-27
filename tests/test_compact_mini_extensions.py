"""Source-sized mini extensions independent of a recognized sprite silhouette."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont, ImageOps

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_contours import EdgeEvidence
from tests.test_compact_block_continuity import continuous_scene


def mini_scene(direction=(16, 0), half=0, *, material=(140, 160, 180),
               background=(85, 85, 85), scale=1, dim=1, invert=False,
               hole=False, triangle=False, text=False, bar=False, full=False):
    image, room, parent, learned, unused = continuous_scene(
        direction, material=material, background=background)
    canvas = Image.frombytes('RGB', (image.width, image.height), image.data)
    draw = ImageDraw.Draw(canvas)
    dx, dy = direction
    ax = parent.x + (32 if dx > 0 else -16 if dx < 0 else 0)
    ay = parent.y + (32 if dy > 0 else -16 if dy < 0 else 0)
    draw.rectangle((ax, ay, ax + (15 if dx else 31), ay + (31 if dx else 15)),
                   fill=background)
    x, y = ax + (16 * half if dy else 0), ay + (16 * half if dx else 0)
    if triangle:
        draw.polygon(((x + 8, y), (x, y + 15), (x + 15, y + 15)),
                     fill=material, outline=(15, 15, 15))
    elif text:
        draw.text((x, y), 'F', fill=material)
    else:
        w, h = ((32, 16) if bar else (16, 32) if full and dx else
                (32, 16) if full else (16, 16))
        draw.rectangle((x, y, x + w - 1, y + h - 1), fill=(15, 15, 15))
        draw.rectangle((x + 1, y + 1, x + w - 2, y + h - 2), fill=material)
        draw.line((x + 1, y + 2, x + w - 2, y + 2), fill=(235, 235, 235), width=2)
        draw.line((x + 1, y + h - 3, x + w - 2, y + h - 3),
                  fill=(235, 235, 235), width=2)
        if hole:
            draw.rectangle((x + 2, y + 2, x + 7, y + 7), fill=background)
    if invert:
        canvas = ImageOps.invert(canvas)
    if dim != 1:
        canvas = canvas.point(lambda value: round(value * dim))
    if scale != 1:
        canvas = canvas.resize((round(800 * scale), round(608 * scale)),
                               Image.Resampling.NEAREST)
    image = RGBImage(canvas.width, canvas.height, canvas.tobytes())
    room = Box(0, 0, image.width, image.height)
    parent = scanner._geometry_detection('compact_adaptive_block', 1,
        parent.x, parent.y, .84, image, room, 32)
    learned = scanner._patch_color_profile(image, room, parent.x, parent.y, 32)
    return image, room, parent, learned, (2, x, y)


class CompactMiniExtensionTests(unittest.TestCase):
    def tearDown(self):
        scanner._PATCH_FEATURE_CACHE.clear()

    def run_scene(self, *args, **kwargs):
        image, room, parent, learned, expected = mini_scene(*args, **kwargs)
        before = deepcopy(parent)
        result = scanner._recover_adaptive_compact_mini_extensions(
            [parent], [parent], image, room, image.pixel(0, 0), learned)
        self.assertEqual(parent, before)
        return [(d.type_id, d.x, d.y) for d in result], expected

    def test_four_faces_and_both_half_side_positions(self):
        for direction in ((16, 0), (-16, 0), (0, 16), (0, -16)):
            for half in (0, 1):
                with self.subTest(direction=direction, half=half):
                    added, expected = self.run_scene(direction, half)
                    self.assertEqual(added, [expected])

    def test_palette_background_polarity_and_brightness(self):
        for options in (dict(material=(180, 140, 160), background=(95, 95, 95)),
                        dict(material=(160, 180, 140), background=(75, 90, 100)),
                        dict(invert=True), dict(dim=.7), dict(invert=True, dim=.7)):
            with self.subTest(options=options):
                added, expected = self.run_scene(**options)
                self.assertEqual(added, [expected])

    def test_fractional_and_double_capture(self):
        for scale in (1.25, 1.5, 2):
            with self.subTest(scale=scale):
                added, expected = self.run_scene(scale=scale)
                self.assertEqual(added, [expected])

    def test_achromatic_role_ambiguity_abstains(self):
        self.assertEqual(self.run_scene(material=(155, 155, 155))[0], [])

    def test_triangle_is_not_a_miniblock(self):
        self.assertEqual(self.run_scene(triangle=True)[0], [])

    def test_distributed_hole_is_not_filled(self):
        self.assertEqual(self.run_scene(hole=True)[0], [])

    def test_text_foreground_is_not_material(self):
        self.assertEqual(self.run_scene(text=True)[0], [])

    def test_long_bar_cannot_be_cut_into_minis(self):
        self.assertEqual(self.run_scene(bar=True)[0], [])

    def test_full_strip_cannot_be_tessellated_as_two_minis(self):
        self.assertEqual(self.run_scene(full=True)[0], [])

    def test_existing_real_full_extension_stays_full(self):
        image, room, parent, learned, expected = continuous_scene((16, 0))
        full = scanner._recover_adaptive_compact_continuous_blocks(
            [parent], [parent], image, room, image.pixel(0, 0), learned)
        self.assertEqual(len(full), 1)
        self.assertEqual(scanner._recover_adaptive_compact_mini_extensions(
            [parent, *full], [parent], image, room, image.pixel(0, 0), learned), [])

    def test_emitted_or_half_phase_parent_cannot_teach(self):
        image, room, parent, learned, expected = mini_scene()
        for value in (replace(parent, kind='compact_source_mini_extension'),
                      replace(parent, x=parent.x + 16)):
            with self.subTest(parent=value):
                self.assertEqual(scanner._recover_adaptive_compact_mini_extensions(
                    [value], [value], image, room, image.pixel(0, 0), learned), [])

    def test_existing_or_partial_terrain_coverage_not_duplicated(self):
        image, room, parent, learned, key = mini_scene()
        for x, y in ((key[1], key[2]), (key[1] + 8, key[2] + 8)):
            old = scanner._geometry_detection('existing_source_mini', 2,
                                               x, y, .9, image, room, 16)
            values = [parent, old]
            before = deepcopy(values)
            self.assertEqual(scanner._recover_adaptive_compact_mini_extensions(
                values, [parent], image, room, image.pixel(0, 0), learned), [])
            self.assertEqual(values, before)

    def test_original_actor_overlap_abstains_without_removing_actor(self):
        image, room, parent, learned, key = mini_scene()
        actor = scanner._geometry_detection('existing_save', 18,
            key[1], key[2], .9, image, room, 32)
        values = [parent, actor]
        before = deepcopy(values)
        self.assertEqual(scanner._recover_adaptive_compact_mini_extensions(
            values, [parent], image, room, image.pixel(0, 0), learned), [])
        self.assertEqual(values, before)

    def test_occupied_exterior_is_not_certified_background(self):
        image, room, parent, learned, key = mini_scene()
        for type_id in (1, 3, 18):
            with self.subTest(type_id=type_id):
                other = scanner._geometry_detection('existing_exterior_object',
                    type_id, key[1] + 16, key[2], .9, image, room, 32)
                values = [parent, other]
                before = deepcopy(values)
                self.assertEqual(scanner._recover_adaptive_compact_mini_extensions(
                    values, [parent], image, room, image.pixel(0, 0), learned), [])
                self.assertEqual(values, before)

    def test_unknown_contour_abstains(self):
        with patch('scripts.source_contours.SourceContours.edge',
                   return_value=EdgeEvidence(12, True, ())):
            self.assertEqual(self.run_scene()[0], [])

    def test_invalid_physical_source_room_never_queries_palette(self):
        image, room, parent, learned, key = mini_scene()
        with patch.object(scanner, '_patch_color_profile',
                          side_effect=AssertionError('unknown source')):
            self.assertEqual(scanner._recover_adaptive_compact_mini_extensions(
                [parent], [parent], image, Box(-1, 0, 800, 608),
                image.pixel(0, 0), learned), [])

    def test_padded_canvas_does_not_supply_source_evidence(self):
        image, room, parent, learned, key = mini_scene()
        parent = replace(parent, x=64, y=64)
        with patch.object(scanner, '_patch_color_profile',
                          side_effect=AssertionError('padding is not source')):
            self.assertEqual(scanner._recover_adaptive_compact_mini_extensions(
                [parent], [parent], image, room, image.pixel(0, 0), learned), [])

    def test_rgb_closed_mini_without_recognized_legacy_silhouette(self):
        image, room, parent, learned, key = mini_scene(background=(156, 156, 156))
        canvas = Image.frombytes('RGB', (image.width, image.height), image.data)
        draw = ImageDraw.Draw(canvas)
        x, y = key[1:]
        for row in range(16):
            delta = (8 if row in (2, 3, 12, 13) else
                     -8 if row in (0, 1, 14, 15) else 0)
            draw.line((x, y + row, x + 15, y + row),
                      fill=tuple(c + delta for c in (140, 160, 180)))
        actual = RGBImage(image.width, image.height, canvas.tobytes())
        old = scanner._classify_block(scanner._patch_features(actual, room, x, y, 16)).score
        self.assertLess(old, .30)
        added = scanner._recover_adaptive_compact_mini_extensions(
            [parent], [parent], actual, room, actual.pixel(0, 0), learned)
        self.assertEqual([(d.type_id, d.x, d.y) for d in added], [key])

    def test_floor_digit_and_outline_impostors_are_not_minis(self):
        for shape in ('8', '0', '9', 'boxed_8', 'outline'):
            with self.subTest(shape=shape):
                image, room, parent, learned, key = mini_scene()
                canvas = Image.frombytes('RGB', (image.width, image.height), image.data)
                draw = ImageDraw.Draw(canvas)
                x, y = key[1:]
                draw.rectangle((x, y, x + 15, y + 15), fill=(85, 85, 85))
                color = (140, 160, 180)
                if shape in ('boxed_8', 'outline'):
                    draw.rectangle((x, y, x + 15, y + 15), outline=color, width=3)
                    if shape == 'boxed_8':
                        draw.line((x, y + 8, x + 15, y + 8), fill=color, width=3)
                else:
                    # Portable default font, no machine-specific font file or
                    # newly required Pillow size= API. Normalize only the test glyph.
                    glyph = Image.new('L', (32, 32))
                    ImageDraw.Draw(glyph).text((4, 4), shape, fill=255,
                                              font=ImageFont.load_default(), stroke_width=1)
                    glyph = glyph.crop(glyph.getbbox()).resize((14, 16), Image.Resampling.NEAREST)
                    canvas.paste(color, (x, y), glyph)
                actual = RGBImage(image.width, image.height, canvas.tobytes())
                self.assertEqual(scanner._recover_adaptive_compact_mini_extensions(
                    [parent], [parent], actual, room, actual.pixel(0, 0), learned), [], shape)
