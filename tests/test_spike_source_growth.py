"""Portable controls for calibrated source seeds and joined native minis."""
import unittest
from random import Random

from PIL import Image

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import SpikeShapeField, VERTICES
from jtool_scanner.spike_size import _CachedShapeField, contour_size_changes, source_seed_size_changes
from jtool_scanner.spike_source_growth import LargerSourceOwner, native_source_seeds
from jtool_scanner.spike_color_evidence import QuantizedColorSlopeField
from tests.test_spike_size import scene


class SourceGrowthTests(unittest.TestCase):
    def test_unanchored_seed_search_abstains_without_touching_source(self):
        class ForbiddenField:
            def could_have_strong_slopes(self, *args):
                raise AssertionError('uncalibrated source must not guess a lattice')

        self.assertEqual(native_source_seeds(ForbiddenField(), []), set())

    def test_source_seeds_follow_each_original_phase_without_zero_fallback(self):
        class BoundField:
            def could_have_strong_slopes(self, x, y, direction):
                return direction == 3 and 320 <= x <= 327 and 240 <= y <= 247

        for phase in (0, 1, 7):
            with self.subTest(phase=phase):
                witnesses = [(96 + phase, 96 + phase, True)] * 2
                self.assertEqual(native_source_seeds(BoundField(), witnesses),
                                 {(320 + phase, 240 + phase)})

    def test_fast_pixels_gradients_and_patch_statistics_equal_original(self):
        rng = Random(155)
        raster = Image.frombytes('RGB', (800, 608), rng.randbytes(800 * 608 * 3))
        image = RGBImage(800, 608, raster.tobytes())
        room = Box(0, 0, 800, 608)
        points = [(x, y) for x in (-2, -1, 0, 1, 399, 798, 799, 800, 801)
                  for y in (-2, -1, 0, 1, 303, 606, 607, 608, 609)]
        points += [(rng.randrange(800), rng.randrange(608)) for _ in range(300)]
        for size in (16, 32):
            legacy = SpikeShapeField(image, room, native_size=size)
            cached = _CachedShapeField(image, room, native_size=size)
            for x, y in points:
                with self.subTest(size=size, origin=(x, y)):
                    self.assertEqual(cached.pixel(x, y), legacy.pixel(x, y))
                    self.assertEqual(cached.gradient(x, y), legacy.gradient(x, y))
                    self.assertEqual(cached.gradient(x, y), legacy.gradient(x, y))
            for x, y in ((-8, -8), (0, 0), (320, 240), (800-size, 608-size), (799, 607)):
                self.assertEqual(cached.patch_stats(x, y), legacy.patch_stats(x, y))

    def test_equal_material_external_pair_recovers_without_inventing_inner_base(self):
        anchor = (3, 96, 96)
        real = [(7, 320, 240), (10, 320, 256)]
        for foreground, background, scale in (
                ((35, 45, 65), (220, 225, 235), 1),
                ((230, 215, 190), (30, 40, 50), 1.25)):
            with self.subTest(scale=scale):
                image = scene([anchor] + real, foreground, background, scale=scale)
                added, rejected = source_seed_size_changes(
                    image, Box(0, 0, image.width, image.height), [anchor], [])
                self.assertEqual(added, set(real))
                self.assertEqual(rejected, set())

    def test_joined_pair_is_not_emitted_through_a_real_occluding_wall(self):
        anchor = (3, 96, 96)
        real = [(7, 320, 240), (10, 320, 256)]
        image = scene([anchor] + real)
        added, _ = source_seed_size_changes(image, Box(0, 0, 800, 608), [anchor],
                                           [(320, 256, 16, 16)])
        self.assertFalse(set(real) & added)

    def test_two_color_only_slopes_do_not_become_luminance_source_seeds(self):
        anchor, real = (3, 96, 96), (7, 320, 240)
        image = scene([anchor, real], (255, 0, 0), (0, 130, 0))
        self.assertEqual(source_seed_size_changes(image, Box(0, 0, 800, 608), [anchor], []),
                         (set(), set()))

    def test_original_full_source_frame_owns_inner_alias_despite_pixel_phase(self):
        for direction in VERTICES:
            for foreground, background, scale in (
                    ((235, 225, 215), (60, 80, 100), 1),
                    ((35, 45, 65), (220, 225, 235), 1.25)):
                with self.subTest(direction=direction, scale=scale):
                    parent = (direction, 320, 240)
                    image = scene([(direction, 319, 241)], foreground, background,
                                  scale=scale, texture=True)
                    room = Box(0, 0, image.width, image.height)
                    context = []
                    contour_size_changes(image, room, [parent], [],
                                         _context_callback=context.append)
                    field, stroke, _, ownership, _ = context[0]
                    owner = LargerSourceOwner([parent], field, stroke,
                        lambda: QuantizedColorSlopeField(image, room), ownership)
                    self.assertTrue(owner.owns((direction + 4, 328, 248)))

    def test_false_full_proposal_cannot_own_a_real_independent_mini(self):
        for direction in VERTICES:
            with self.subTest(direction=direction):
                parent = (direction, 320, 240)
                real = (direction + 4, 328, 248)
                image = scene([real], texture=True)
                room = Box(0, 0, image.width, image.height)
                context = []
                contour_size_changes(image, room, [parent], [],
                                     _context_callback=context.append)
                field, stroke, _, ownership, _ = context[0]
                owner = LargerSourceOwner([parent], field, stroke,
                    lambda: QuantizedColorSlopeField(image, room), ownership)
                self.assertFalse(owner.owns(real))


if __name__ == '__main__':
    unittest.main()
