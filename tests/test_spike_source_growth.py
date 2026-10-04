"""Portable controls for calibrated source seeds and joined native minis."""
import unittest
from random import Random

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import SpikeShapeField, VERTICES
from jtool_scanner.spike_size import (
    _CachedShapeField, _LocalField, contour_size_changes, source_seed_size_changes)
from jtool_scanner.spike_source_growth import (
    LargerSourceOwner, independent_extent_owns, native_source_seeds, source_material_conflicts)
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


class IndependentExtentTests(unittest.TestCase):
    @staticmethod
    def field(image):
        field = _LocalField(image, Box(0, 0, image.width, image.height), native_size=32)
        field.edge_local_scores, field.edge_local_statistics = {}, {}
        return field

    @staticmethod
    def child_of(direction):
        dx, dy = {3: (8, 16), 4: (0, 8), 5: (16, 8), 6: (8, 0)}[direction]
        return direction + 4, 320 + dx, 240 + dy

    def test_full_frame_remains_identifiable_beside_dominant_artifact(self):
        for direction in VERTICES:
            for fg, bg, artifact in (
                    ((125, 135, 145), (100, 110, 120), (255, 255, 255)),
                    ((185, 195, 205), (210, 220, 230), (0, 0, 0))):
                for scale in (1., 1.25):
                    with self.subTest(direction=direction, fg=fg, scale=scale):
                        image = scene([(direction, 320, 240)], fg, bg)
                        raster = Image.frombytes('RGB', (800, 608), image.data)
                        ax, ay = {3: (320, 240), 4: (344, 240),
                                  5: (320, 240), 6: (320, 264)}[direction]
                        ImageDraw.Draw(raster).rectangle((ax, ay, ax + 7, ay + 7), fill=artifact)
                        if scale != 1:
                            raster = raster.resize((round(800 * scale), round(608 * scale)),
                                                   Image.Resampling.BILINEAR)
                        image = RGBImage(raster.width, raster.height, raster.tobytes())
                        pure = _CachedShapeField(image, Box(0, 0, image.width, image.height), native_size=32)
                        self.assertLess(pure.localized_score(320, 240, direction), 11 / 12)
                        self.assertTrue(independent_extent_owns(
                            self.field(image), self.child_of(direction), (direction, 320, 240)))

    def test_fake_full_cannot_own_true_standalone_mini(self):
        for direction in VERTICES:
            for scale in (1., 1.25):
                with self.subTest(direction=direction, scale=scale):
                    child = self.child_of(direction)
                    image = scene([child], texture=True, scale=scale)
                    self.assertFalse(independent_extent_owns(
                        self.field(image), child, (direction, 320, 240)))

    def test_real_mini_crossing_parent_boundary_remains_independent(self):
        for direction in VERTICES:
            with self.subTest(direction=direction):
                parent, child = (direction, 320, 240), (direction + 4, 344, 264)
                self.assertFalse(independent_extent_owns(self.field(scene([parent, child])), child, parent))

    def test_short_shared_contour_cannot_borrow_child_edges(self):
        for direction in VERTICES:
            with self.subTest(direction=direction):
                parent, child = (direction, 320, 240), (direction + 4, 328, 248)
                self.assertFalse(independent_extent_owns(self.field(scene([parent])), child, parent))

    def test_open_v_is_not_a_closed_larger_owner(self):
        for direction in VERTICES:
            with self.subTest(direction=direction):
                raster = Image.new('RGB', (800, 608), (220, 225, 235))
                draw = ImageDraw.Draw(raster)
                tip, *ends = VERTICES[direction]
                for end in ends:
                    draw.line((320 + tip[0], 240 + tip[1], 320 + end[0], 240 + end[1]),
                              fill=(35, 45, 65), width=2)
                image = RGBImage(800, 608, raster.tobytes())
                self.assertFalse(independent_extent_owns(
                    self.field(image), self.child_of(direction), (direction, 320, 240)))

    def test_isoluminant_true_mini_cannot_be_erased_by_luminance_owner(self):
        for direction in VERTICES:
            with self.subTest(direction=direction):
                child = self.child_of(direction)
                image = scene([child], (255, 0, 0), (0, 130, 0))
                self.assertFalse(independent_extent_owns(self.field(image), child, (direction, 320, 240)))


class OriginalMaterialConflictTests(unittest.TestCase):
    def test_unanimous_original_material_conflict_is_polarity_symmetric(self):
        for contrast in (-.45, .45):
            with self.subTest(contrast=contrast):
                witnesses = [(96, 96, 4, contrast < 0), (128, 96, 8, contrast < 0),
                             (160, 96, 12, contrast < 0)]
                self.assertTrue(source_material_conflicts(contrast, witnesses))
                self.assertFalse(source_material_conflicts(-contrast, witnesses))

    def test_insufficient_original_witnesses_do_not_veto_new_material(self):
        for count in range(3):
            self.assertFalse(source_material_conflicts(.45, [(96 + 32 * i, 96, i, False)
                                                             for i in range(count)]))

    def test_mixed_original_materials_do_not_veto_new_material(self):
        for sign in (False, True):
            witnesses = [(96, 96, 4, sign), (128, 96, 8, not sign), (160, 96, 12, sign)]
            for contrast in (-.45, .45):
                self.assertFalse(source_material_conflicts(contrast, witnesses))

    def test_weak_candidate_polarity_does_not_veto_new_material(self):
        for contrast in (-.199, 0., .199):
            witnesses = [(96 + 32 * i, 96, i, contrast < 0) for i in range(3)]
            self.assertFalse(source_material_conflicts(contrast, witnesses))


if __name__ == '__main__':
    unittest.main()
