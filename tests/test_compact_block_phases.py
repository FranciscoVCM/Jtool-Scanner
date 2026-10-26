"""Learned compact tile material is independent of the tile's sampling phase."""
from dataclasses import asdict
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageOps

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_contours import EdgeEvidence


def compact_scene(*, background=(85, 85, 85), material=(140, 140, 140),
                  invert=False, dim=1.0, scale=1.0, mini=False, triangle=False):
    image = Image.new("RGB", (800, 608), "black")
    draw = ImageDraw.Draw(image)
    draw.rectangle((96, 96, 703, 511), fill=background)

    def tile(x, y, size=32):
        draw.rectangle((x, y, x+size-1, y+size-1), fill=(15,)*3)
        draw.rectangle((x+2, y+2, x+size-3, y+size-3), fill=(235,)*3)
        draw.rectangle((x+4, y+4, x+size-5, y+size-5), fill=material)
        if size == 32:
            for ox, oy in ((7, 7), (24, 7), (7, 24), (24, 24)):
                draw.ellipse((x+ox-2, y+oy-2, x+ox+2, y+oy+2), outline=(25,)*3)

    for y in range(96, 481, 32):
        for x in range(96, 673, 32):
            if x in (96, 672) or y in (96, 480):
                tile(x, y)
    expected = {(224, 208), (400, 256), (464, 400)}
    for position in expected:
        tile(*position)
    tile(256, 288)
    # An opposed mini pair touching a true offset tile must not steal its pose.
    draw.polygon(((455.5, 400), (448, 415), (463, 415)), fill=(235,)*3, outline=(15,)*3)
    draw.polygon(((448, 416), (463, 416), (455.5, 431)), fill=(235,)*3, outline=(15,)*3)
    if mini:
        tile(560, 224, 16)
    if triangle:
        for x, y in ((336, 352), (560, 352)):
            draw.polygon(((x+16, y), (x, y+31), (x+31, y+31)), fill=material, outline=(15,)*3, width=2)
    if invert:
        image = ImageOps.invert(image)
    if dim != 1:
        image = image.point(lambda value: round(value*dim))
    if scale != 1:
        image = image.resize((round(800*scale), round(608*scale)), Image.Resampling.NEAREST)
    rgb = RGBImage(image.width, image.height, image.tobytes())
    return rgb, Box(0, 0, rgb.width, rgb.height), expected


class CompactBlockPhaseTests(unittest.TestCase):
    def tearDown(self):
        scanner._PATCH_FEATURE_CACHE.clear()

    def check_scene(self, **options):
        image, room, expected = compact_scene(**options)
        with patch.object(scanner, "_recover_adaptive_compact_block_phases", side_effect=lambda native, *args: native):
            native, profile = scanner._detect_adaptive_compact_room_blocks(image, room, image.pixel(0, 0))
        found, same_profile = scanner._detect_adaptive_compact_room_blocks(image, room, image.pixel(0, 0))
        self.assertIsNotNone(profile)
        self.assertEqual(profile, same_profile)
        old = {(d.x, d.y): asdict(d) for d in native}
        new = {(d.x, d.y): asdict(d) for d in found}
        self.assertTrue(expected.isdisjoint(old))
        self.assertEqual(expected, new.keys()-old.keys())
        self.assertTrue(old.keys() <= new.keys())
        self.assertTrue(all(value == new[key] for key, value in old.items()))

    def test_all_half_phases_keep_native_objects(self):
        self.check_scene()

    def test_material_and_background_variation(self):
        for background, material in (((45, 75, 110), (150, 170, 190)),
                                     ((185, 160, 125), (95, 120, 145)),
                                     ((95, 65, 95), (175, 125, 165))):
            with self.subTest(background=background, material=material):
                self.check_scene(background=background, material=material)

    def test_polarity_and_dimming(self):
        for invert, dim in ((True, 1), (False, .7), (True, .7)):
            with self.subTest(invert=invert, dim=dim):
                self.check_scene(invert=invert, dim=dim)

    def test_fractional_and_double_capture(self):
        for scale in (1.25, 2):
            with self.subTest(scale=scale):
                self.check_scene(scale=scale)

    def test_triangle_and_mini_are_not_full_tiles(self):
        self.check_scene(mini=True, triangle=True)

    def test_without_learned_material_output_is_unchanged(self):
        image = RGBImage(800, 608, bytes((90, 90, 90))*800*608)
        self.assertEqual(([], None), scanner._detect_adaptive_compact_room_blocks(image, Box(0, 0, 800, 608), (90,)*3))

    def test_phase_queries_never_probe_normalized_padding(self):
        image, room, _ = compact_scene()
        with patch.object(scanner, "_recover_adaptive_compact_block_phases", side_effect=lambda native, *args: native):
            native, learned = scanner._detect_adaptive_compact_room_blocks(image, room, image.pixel(0, 0))
        # An edge gap must not let the dedup buffer conceal missing availability
        # checks. The real capture ends at x=96, not at the padded canvas's x=0.
        native = [d for d in native if (d.x, d.y) not in ((96, 192), (96, 224))]
        sampled = []
        real = scanner._sample_map_patch_colors

        def observe(image, room, x, y, size):
            sampled.append((x, y))
            return real(image, room, x, y, size)

        with patch.object(scanner, "_sample_map_patch_colors", side_effect=observe):
            scanner._recover_adaptive_compact_block_phases(native, image, room, image.pixel(0, 0), learned)
        self.assertTrue(sampled)
        self.assertTrue(all(100.5 <= x <= 667.5 and 100.5 <= y <= 475.5 for x, y in sampled))

    def test_cannot_combine_sides_from_different_observed_rectangles(self):
        class Incoherent:
            def edge(self, first, second):
                support = 12
                if second[0] > first[0] and first[1] >= 192.25:
                    support = 0
                elif second[0] < first[0] and first[1] <= 224.25:
                    support = 0
                return EdgeEvidence(support, False, ())
        self.assertFalse(scanner._compact_rectangle_contour_closed(Incoherent(), 160, 192, (1, 1)))

    def test_unknown_faces_do_not_support_a_rectangle(self):
        class Unknown:
            def edge(self, first, second):
                return EdgeEvidence(12, True, ())
        self.assertFalse(scanner._compact_rectangle_contour_closed(Unknown(), 160, 192, (1, 1)))
