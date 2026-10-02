import unittest

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from jtool_scanner.spike_size import contour_size_changes


def scene(objects, foreground=(35, 45, 65), background=(220, 225, 235),
          *, scale=1, outlined=False, texture=False, erase_base=False):
    raster = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(raster)
    if texture:
        alternate = tuple(max(0, min(255, c + 7)) for c in background)
        for y in range(0, 608, 8):
            for x in range(0, 800, 8):
                if (x // 8 + y // 8) % 2:
                    draw.rectangle((x, y, x + 7, y + 7), fill=alternate)
    for t, x, y in objects:
        size, d = (16, t - 4) if t > 6 else (32, t)
        points = [(x + a * size / 32, y + b * size / 32) for a, b in VERTICES[d]]
        if erase_base:
            draw.line((points[0], points[1]), fill=foreground, width=2)
            draw.line((points[0], points[2]), fill=foreground, width=2)
        else:
            draw.polygon(points, fill=background if outlined else foreground,
                         outline=foreground if outlined else None, width=2)
    raster = raster.resize((round(800 * scale), round(608 * scale)),
                           Image.Resampling.BILINEAR)
    return RGBImage(raster.width, raster.height, raster.tobytes())


def pair(d, x=320, y=320):
    points = {3: ((x, y + 16), (x + 16, y + 16)),
              6: ((x, y), (x + 16, y)),
              4: ((x, y), (x, y + 16)),
              5: ((x + 16, y), (x + 16, y + 16))}[d]
    return [(d + 4, px, py) for px, py in points]


def changes(image, keys, solids=()):
    return contour_size_changes(image, Box(0, 0, image.width, image.height), keys, list(solids))


class SpikeSizeTests(unittest.TestCase):
    def test_real_pairs_recover_instead_of_full_at_varied_polarity_texture_and_scale(self):
        for d in VERTICES:
            for foreground, background, scale, texture in (
                ((35, 45, 65), (220, 225, 235), 1, False),
                ((230, 215, 190), (30, 40, 50), 1.25, False),
                ((80, 90, 105), (145, 155, 165), 1.5, True),
            ):
                with self.subTest(direction=d, scale=scale):
                    real = pair(d)
                    image = scene(real, foreground, background, scale=scale, texture=texture)
                    self.assertEqual(changes(image, [(d, 320, 320)]),
                                     (set(real), {(d, 320, 320)}))

    def test_closed_outlines_locate_minis_without_across_base_fill_difference(self):
        for d in VERTICES:
            for scale in (1, 1.25, 1.5):
                with self.subTest(direction=d, scale=scale):
                    real = pair(d)
                    image = scene(real, outlined=True, scale=scale)
                    self.assertEqual(changes(image, [(d, 320, 320)]),
                                     (set(real), {(d, 320, 320)}))

    def test_real_full_rejects_unobservable_mini_side_not_all_overlaps(self):
        for d in VERTICES:
            for scale in (1, 1.25, 1.5):
                with self.subTest(direction=d, scale=scale):
                    full = (d, 320, 320)
                    alias = (d + 4, 320, 320)
                    image = scene([full], scale=scale)
                    self.assertEqual(changes(image, [full, alias]), (set(), {alias}))

    def test_independent_full_and_mini_contours_are_not_blanket_overlap_removed(self):
        for d in VERTICES:
            with self.subTest(direction=d):
                full = (d, 320, 320)
                mini = (d + 4, 320, 320)
                image = scene([full, mini], outlined=True)
                self.assertEqual(changes(image, [full, mini]), (set(), set()))

    def test_mini_pair_with_hidden_full_tip_cannot_establish_full_absence(self):
        for d in VERTICES:
            with self.subTest(direction=d):
                full = (d, 320, 320)
                real = pair(d)
                mask = {3: (320, 320, 32, 16), 6: (320, 336, 32, 16),
                        4: (336, 320, 16, 32), 5: (320, 320, 16, 32)}[d]
                self.assertEqual(changes(scene(real), [full], [mask]), (set(real), set()))

    def test_masked_mini_side_remains_uncertain(self):
        full, mini = (6, 320, 320), (10, 320, 320)
        self.assertEqual(changes(scene([full]), [full, mini], [(320, 320, 16, 16)]),
                         (set(), set()))

    def test_half_embedded_real_full_is_not_erased_by_small_contour_ambiguity(self):
        full = (3, 320, 320)
        image = scene([full], outlined=True)
        raster = Image.frombytes('RGB', (800, 608), image.data)
        ImageDraw.Draw(raster).rectangle((336, 320, 351, 351), fill=(55, 85, 65))
        image = RGBImage(800, 608, raster.tobytes())
        self.assertNotIn(full, changes(image, [full], [(336, 320, 16, 32)])[1])

    def test_differently_directed_mini_is_not_deleted_by_full_size_preference(self):
        full, mini = (3, 320, 320), (10, 320, 320)
        self.assertEqual(changes(scene([full]), [full, mini]), (set(), set()))

    def test_scanner_wrapper_preserves_markers_and_source_boxes(self):
        from jtool_scanner.scanner import Detection, _reconcile_source_triangle_sizes
        full, real = (3, 320, 320), pair(3)
        marker = Detection('save', 20, 64, 64, .8, Box(64, 64, 32, 32))
        alias = Detection('spike_up', *full, .8, Box(320, 320, 32, 32))
        image = scene(real, scale=1.25)
        result = _reconcile_source_triangle_sizes([marker, alias], image, Box(0, 0, 1000, 760))
        self.assertIs(result[0], marker)
        self.assertEqual({(d.type_id, d.x, d.y) for d in result[1:]}, set(real))
        self.assertTrue(all(d.image_box.width == 20 and d.image_box.height == 20
                            for d in result[1:]))

    def test_open_v_strokes_are_not_positive_closed_mini_evidence(self):
        for d in VERTICES:
            with self.subTest(direction=d):
                self.assertEqual(changes(scene(pair(d), erase_base=True), [(d, 320, 320)]),
                                 (set(), set()))

    def test_weak_and_isoluminant_evidence_abstains(self):
        for foreground, background in (((100, 100, 100), (103, 103, 103)),
                                       ((255, 0, 0), (0, 130, 0))):
            for real, hypotheses in ((pair(3), [(3, 320, 320)]),
                                     ([(6, 320, 320)], [(6, 320, 320), (10, 320, 320)])):
                with self.subTest(foreground=foreground, real=real):
                    self.assertEqual(changes(scene(real, foreground, background), hypotheses),
                                     (set(), set()))

    def test_weak_rgb_only_mini_inside_strong_luminance_full_is_preserved(self):
        # Equal integer luminance, weaker RGB boundary than the surrounding
        # full. This failed v1 despite its whole-patch isoluminance safeguard.
        full, mini = (6, 320, 320), (10, 320, 320)
        image = scene([full], (220, 220, 220), (35, 35, 35))
        raster = Image.frombytes('RGB', (800, 608), image.data)
        for color in ((233, 220, 188), (224, 220, 210), (222, 220, 215)):
            with self.subTest(color=color):
                variant = raster.copy()
                ImageDraw.Draw(variant).polygon(
                    [(320 + x / 2, 320 + y / 2) for x, y in VERTICES[6]], fill=color,
                )
                image = RGBImage(800, 608, variant.tobytes())
                self.assertEqual(changes(image, [full, mini]), (set(), set()))

    def test_existing_mini_pair_does_not_get_readded_or_supply_a_chain(self):
        full, real = (3, 320, 320), pair(3)
        self.assertEqual(changes(scene(real), [full, *real]), (set(), {full}))
        self.assertEqual(changes(scene(real), real), (set(), set()))

    def test_clipped_pair_is_not_inferred_from_clamped_border_pixels(self):
        full = (3, 0, 320)
        self.assertEqual(changes(scene(pair(3, 0, 320)), [full]), (set(), set()))

    def test_outlined_full_inner_art_is_not_a_mini_despite_wrong_coarse_direction(self):
        from pathlib import Path
        from jtool_scanner.image import load_png
        image = load_png(Path(__file__).resolve().parents[1]
                         / 'fixtures/regressions/unseen-rooms/cn3-neon/floor-08-source.png')
        # Two existing hypotheses locate this test. The interior right-facing
        # artwork is not another 16px game object, even when the coarse full
        # label is wrong. Future genuine direction/mini recovery stays allowed.
        added, _ = contour_size_changes(
            image, Box(0, 0, image.width, image.height),
            [(5, 320, 320), (3, 352, 288)], [])
        self.assertNotIn((8, 328, 328), added)


    def test_existing_full_target_is_not_reemitted_for_a_competing_alias(self):
        # Returning a correct existing target as an addition creates a duplicate
        # at the scanner boundary. Allow future removal of the false direction;
        # do not require that current abstention or incorrect labels persist.
        for direction in VERTICES:
            target = (direction, 320, 320)
            alias = ({3: 4, 4: 5, 5: 4, 6: 5}[direction], 320, 320)
            for scale in (1, 1.25):
                with self.subTest(direction=direction, scale=scale):
                    added, _ = changes(scene([target], outlined=True, scale=scale),
                                       [target, alias])
                    self.assertNotIn(target, added)


    def test_glowing_full_spike_inner_art_is_not_additional_mini_geometry(self):
        from pathlib import Path
        from jtool_scanner.image import load_png
        image = load_png(Path(__file__).resolve().parents[1]
                         / 'fixtures/regressions/unseen-rooms/cn3-neon/floor-07-source.png')
        # These hollow, glowing 32px sprites contain sharply drawn triangular
        # holes. A source-relative stroke must not turn those holes into new
        # 16px objects. Existing coarse full hypotheses only locate source
        # tests; they do not make every overlapped miniature invalid.
        fulls = [(4, 304, 48), (6, 320, 208), (6, 432, 192), (6, 544, 288)]
        # Nearby existing source hypotheses provide calibration/search anchors,
        # as in a real late stage. The four forbidden minis are NOT inputs.
        neighbors = [(6, 336, 32), (6, 320, 144), (3, 320, 240),
                     (5, 400, 256), (10, 496, 352), (10, 512, 352)]
        artwork = [(8, 312, 56), (10, 328, 216), (10, 440, 200), (10, 552, 296)]
        added, _ = contour_size_changes(
            image, Box(0, 0, image.width, image.height), fulls + neighbors, [])
        for target in artwork:
            with self.subTest(target=target):
                self.assertNotIn(target, added)


if __name__ == '__main__':
    unittest.main()
