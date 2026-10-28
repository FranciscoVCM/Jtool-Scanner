"""Procedural colour/contour and native consumer regressions, no private corpus."""
import random
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.killer_shape import red_cross_shape_supported


def tile_samples(colour=(70, 20, 18), pattern="cross", scale=1, phase=0):
    image = Image.new("RGB", (32, 32), colour)
    draw = ImageDraw.Draw(image)
    dark = tuple(value // 3 for value in colour)
    if pattern in ("cross", "single"):
        draw.line((0, phase, 31, 31 + phase), fill=dark, width=2)
    if pattern == "cross":
        draw.line((0, 31 + phase, 31, phase), fill=dark, width=2)
    if pattern == "brick":
        for y in (8, 16, 24):
            draw.line((0, y, 31, y), fill=dark, width=2)
        for x in (8, 24):
            draw.line((x, 0, x, 31), fill=dark, width=2)
    if pattern == "mini":
        draw.rectangle((16, 0, 31, 31), fill=(90, 90, 90))
        draw.rectangle((0, 16, 31, 31), fill=(90, 90, 90))
    if pattern == "save":
        draw.rectangle((0, 0, 31, 7), fill=(210, 210, 210))
    if pattern == "noise":
        randomizer = random.Random(17)
        for y in range(32):
            for x in range(32):
                image.putpixel((x, y), tuple(max(0, value + randomizer.randrange(-5, 6)) for value in colour))
    if scale != 1:
        scales = scale if isinstance(scale, tuple) else (scale, scale)
        image = image.resize((round(32 * scales[0]), round(32 * scales[1])), Image.Resampling.BILINEAR)

    def sample(size):
        return [image.getpixel((int((x + 0.5) * image.width / size),
                               int((y + 0.5) * image.height / size)))
                for y in range(size) for x in range(size)]

    return sample(16), sample(32)


class KillerShapeTests(unittest.TestCase):
    def test_dim_cross_without_absolute_brightness(self):
        self.assertTrue(red_cross_shape_supported(*tile_samples()))

    def test_brightness_variants(self):
        for colour in ((30, 6, 5), (60, 20, 18), (88, 40, 35)):
            with self.subTest(colour=colour):
                self.assertTrue(red_cross_shape_supported(*tile_samples(colour=colour)))

    def test_fractional_and_double_captures(self):
        for scale in (1.25, 1.75, 2):
            for phase in (-1, 0, 1):
                with self.subTest(scale=scale, phase=phase):
                    self.assertTrue(red_cross_shape_supported(*tile_samples(scale=scale, phase=phase)))

    def test_native_pixel_phase_is_not_lost_between_colour_samples(self):
        for phase in (-1, 0, 1):
            with self.subTest(phase=phase):
                self.assertTrue(red_cross_shape_supported(*tile_samples(phase=phase)))

    def test_gray_and_blue_crosses_are_not_red_killers(self):
        for colour in ((70, 70, 70), (20, 30, 70)):
            with self.subTest(colour=colour):
                self.assertFalse(red_cross_shape_supported(*tile_samples(colour=colour)))

    def test_plain_dim_red_is_not_object_identity(self):
        self.assertFalse(red_cross_shape_supported(*tile_samples(pattern="plain")))

    def test_single_diagonal_bricks_and_noise_abstain(self):
        for pattern in ("single", "brick", "noise"):
            with self.subTest(pattern=pattern):
                self.assertFalse(red_cross_shape_supported(*tile_samples(pattern=pattern)))

    def test_mini_and_save_header_are_not_full_tiles(self):
        for pattern in ("mini", "save"):
            with self.subTest(pattern=pattern):
                self.assertFalse(red_cross_shape_supported(*tile_samples(pattern=pattern)))

    def test_missing_samples_abstain(self):
        colours, detail = tile_samples()
        self.assertFalse(red_cross_shape_supported(colours, []))
        self.assertFalse(red_cross_shape_supported([], detail))

    def test_input_samples_unchanged(self):
        colours, detail = tile_samples()
        saved = list(colours), list(detail)
        red_cross_shape_supported(colours, detail)
        self.assertEqual((colours, detail), saved)

    def test_repeated_physical_pixels_are_not_independent_sites(self):
        colours, detail = tile_samples()
        repeated = tuple(i // 2 for i in range(32))
        self.assertFalse(red_cross_shape_supported(colours, detail, physical_axes=(repeated, repeated)))

    def test_consistently_repeated_small_source_still_needs20_sites(self):
        colours, detail = tile_samples(scale=0.25)
        repeated = tuple(i // 4 for i in range(32))
        self.assertFalse(red_cross_shape_supported(colours, detail, physical_axes=(repeated, repeated)))

    def test_partial_axis_repetition_with_distinct2d_sites_can_qualify(self):
        colours, detail = tile_samples(scale=(0.75, 1))
        axes = tuple(int((i + 0.5) * 24 / 32) for i in range(32)), tuple(range(32))
        self.assertTrue(red_cross_shape_supported(colours, detail, physical_axes=axes))

    def test_unknown_physical_coverage_abstains(self):
        colours, detail = tile_samples()
        self.assertFalse(red_cross_shape_supported(colours, detail, physical_axes=((None,) * 32, tuple(range(32)))))
        self.assertFalse(red_cross_shape_supported(colours, detail, physical_axes=((), ())))


def native_field(grid=(9, 9), mini=False, header=False, ui=False, bright_plain=False):
    canvas = Image.new("RGB", (800, 608), (40, 40, 40))
    draw = ImageDraw.Draw(canvas)
    x = ((25 - grid[0]) // 2) * 32
    y = ((19 - grid[1] + 1) // 2) * 32
    size = 16 if mini else 32
    draw.rectangle((x, y, x + size - 1, y + size - 1), fill=(180, 20, 20) if bright_plain else (70, 20, 18))
    if not bright_plain:
        draw.line((x, y, x + size - 1, y + size - 1), fill=(20, 5, 5), width=2)
        draw.line((x, y + size - 1, x + size - 1, y), fill=(20, 5, 5), width=2)
    if header:
        draw.rectangle((x, y, x + 31, y + 7), fill=(210, 210, 210))
    if ui:
        draw.rectangle((0, 0, 31, 31), fill=(70, 20, 18))
        draw.line((0, 0, 31, 31), fill=(20, 5, 5), width=2)
        draw.line((0, 31, 31, 0), fill=(20, 5, 5), width=2)
    return RGBImage(800, 608, canvas.tobytes()), Box(0, 0, 800, 608), x, y


def detection(type_id, x, y, kind="old"):
    return scanner.Detection(kind, type_id, x, y, 0.91, Box(x, y, 32, 32))


class NativeKillerConsumerTests(unittest.TestCase):
    def setUp(self):
        scanner._PATCH_FEATURE_CACHE.clear()

    def tearDown(self):
        scanner._PATCH_FEATURE_CACHE.clear()

    def test_shared_native_grids_and_old_bright_plain_rule(self):
        for grid in ((9, 9), (19, 13)):
            for bright_plain in (False, True):
                scanner._PATCH_FEATURE_CACHE.clear()
                image, room, x, y = native_field(grid=grid, bright_plain=bright_plain)
                result = scanner._recover_native_compact_killer_tiles([detection(1, x, y)], image, room, grid)
                self.assertEqual([(d.type_id, d.x, d.y) for d in result], [(18, x, y)])

    def test_nonterrain_overlap_and_other_safe_metadata_retained(self):
        image, room, x, y = native_field()
        markers = [detection(t, x, y) for t in (2, 3, 12, 14, 21)]
        safe, old = detection(1, x + 64, y), detection(1, x, y)
        original = [old, safe, *markers]
        result = scanner._recover_native_compact_killer_tiles(original, image, room, (9, 9))
        self.assertEqual(original, [old, safe, *markers])
        self.assertTrue(all(d in result for d in [safe, *markers]))
        self.assertNotIn(old, result)

    def test_mini_and_save_header_do_not_retag_whole_cell(self):
        for options in (dict(mini=True), dict(header=True)):
            scanner._PATCH_FEATURE_CACHE.clear()
            image, room, x, y = native_field(**options)
            old = detection(1, x, y)
            self.assertEqual(scanner._recover_native_compact_killer_tiles([old], image, room, (9, 9)), [old])

    def test_red_ui_outside_localized_board_not_emitted(self):
        image, room, x, y = native_field(ui=True)
        result = scanner._recover_native_compact_killer_tiles([], image, room, (9, 9))
        self.assertEqual([(d.type_id, d.x, d.y) for d in result], [(18, x, y)])

    def test_existing_killer_metadata_retained(self):
        image, room, x, y = native_field()
        old = detection(18, x, y, "original_killer")
        self.assertEqual(scanner._recover_native_compact_killer_tiles([old], image, room, (9, 9)), [old])

    def test_existing_safe_backing_under_known_killer_preserved(self):
        image, room, x, y = native_field()
        killer = detection(18, x, y, "original_killer")
        backing = detection(1, x, y, "original_backing")
        result = scanner._recover_native_compact_killer_tiles([killer, backing], image, room, (9, 9))
        self.assertCountEqual(result, [killer, backing])

    def test_subnative_consumer_supplies_exact_unclamped_physical_axes(self):
        image, _, x, y = native_field(grid=(19, 13))
        raster = Image.frombytes("RGB", (image.width, image.height), image.data)
        raster = raster.resize((700, 532), Image.Resampling.BILINEAR)
        image = RGBImage(700, 532, raster.tobytes())
        room = Box(0, 0, 700, 532)
        with patch.object(scanner, "red_cross_shape_supported", return_value=False) as probe:
            scanner._recover_native_compact_killer_tiles([], image, room, (19, 13))
        self.assertTrue(probe.called)
        axes = probe.call_args.kwargs["physical_axes"]
        self.assertEqual(axes[0], tuple(int((x + i + 0.5) * 700 / 800) for i in range(32)))
        self.assertEqual(axes[1], tuple(int((y + i + 0.5) * 532 / 608) for i in range(32)))
        self.assertLess(len(set(axes[0])), 32)

    def test_unknown_small_or_full_grid_not_activated(self):
        image, room, x, y = native_field()
        old = detection(1, x, y)
        for grid in (None, (25, 19), (3, 3)):
            self.assertEqual(scanner._recover_native_compact_killer_tiles([old], image, room, grid), [old])

    def test_unknown_outside_source_room_not_clamped_into_evidence(self):
        image, _, x, y = native_field()
        old = detection(1, x, y)
        for room in (Box(-1, 0, 800, 608), Box(0, 0, 801, 608), Box(0, -1, 800, 608)):
            self.assertEqual(scanner._recover_native_compact_killer_tiles([old], image, room, (9, 9)), [old])
