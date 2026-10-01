import unittest

from PIL import Image, ImageDraw

from jtool_scanner.constants import OBJ_APPLE, OBJ_SPIKE_LEFT, OBJ_SPIKE_UP
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.interstitial_geometry import interstitial_triangle_aliases
from jtool_scanner.scanner import Detection, _dedupe_overlapping_geometry
from jtool_scanner.spike_shape import VERTICES


def scene(direction, size, foreground, background, scale=1,
          true_middle=False, outline=None, texture=False):
    image = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(image)
    if texture:
        alternate = tuple(max(0, min(255, c + 9)) for c in background)
        for y in range(0, 608, 8):
            for x in range(0, 800, 8):
                if (x // 8 + y // 8) % 2:
                    draw.rectangle((x, y, x + 7, y + 7), fill=alternate)
    opposite = {3: 6, 6: 3, 4: 5, 5: 4}[direction]
    x, y = 320, 320
    dx, dy = (size // 2, 0) if direction in (3, 6) else (0, size // 2)
    keys = [(opposite, x - dx, y - dy), (opposite, x + dx, y + dy),
            (direction, x, y)]
    for d, px, py in keys[:2]:
        draw.polygon([(px + a * size / 32, py + b * size / 32)
                      for a, b in VERTICES[d]], fill=foreground)
    if true_middle:
        polygon = [(x + a * size / 32, y + b * size / 32)
                   for a, b in VERTICES[direction]]
        draw.polygon(polygon, fill=background if outline else foreground,
                     outline=outline, width=2)
    if size == 16:
        keys = [(d + 4, px, py) for d, px, py in keys]
    image = image.resize((round(800 * scale), round(608 * scale)),
                         Image.Resampling.BILINEAR)
    return RGBImage(image.width, image.height, image.tobytes()), keys


class InterstitialGeometryTests(unittest.TestCase):
    def test_gap_and_genuine_interlocked_triple(self):
        variants = (((35, 45, 65), (220, 225, 235), 1, False),
                    ((230, 215, 190), (30, 40, 50), 1.25, False),
                    ((80, 90, 105), (145, 155, 165), 1.5, True))
        for size in (16, 32):
            for direction in VERTICES:
                for foreground, background, scale, texture in variants:
                    with self.subTest(size=size, direction=direction, scale=scale):
                        image, keys = scene(direction, size, foreground, background,
                                            scale, texture=texture)
                        room = Box(0, 0, image.width, image.height)
                        self.assertEqual(interstitial_triangle_aliases(image, room, keys, []),
                                         {keys[-1]})
                        image, keys = scene(direction, size, foreground, background,
                                            scale, true_middle=True, texture=texture)
                        self.assertEqual(interstitial_triangle_aliases(image, room, keys, []),
                                         set())

    def test_opposite_fill_real_triangle_with_explicit_base_is_not_gap(self):
        for direction in VERTICES:
            with self.subTest(direction=direction):
                image, keys = scene(direction, 32, (45, 55, 75), (225, 230, 240),
                                    true_middle=True, outline=(5, 5, 5))
                self.assertEqual(interstitial_triangle_aliases(image, Box(0, 0, 800, 608),
                                                              keys, []), set())

    def test_weak_and_isoluminant_evidence_abstains(self):
        for foreground, background in (((100, 100, 100), (103, 103, 103)),
                                       ((255, 0, 0), (0, 130, 0))):
            image, keys = scene(6, 32, foreground, background)
            self.assertEqual(interstitial_triangle_aliases(image, Box(0, 0, 800, 608),
                                                          keys, []), set())

    def test_hidden_base_preserves_uncertainty(self):
        image, keys = scene(6, 32, (45, 45, 45), (225, 225, 225))
        self.assertEqual(interstitial_triangle_aliases(image, Box(0, 0, 800, 608),
                                                      keys, [(320, 312, 32, 16)]), set())

    def test_backing_blocks_do_not_mask_gap_base(self):
        image, keys = scene(6, 32, (45, 45, 45), (225, 225, 225))
        self.assertEqual(interstitial_triangle_aliases(image, Box(0, 0, 800, 608),
                                                      keys, [(304, 352, 64, 32)]), {keys[-1]})

    def test_no_peer_or_partial_peer_abstains(self):
        image, keys = scene(6, 32, (45, 45, 45), (225, 225, 225))
        self.assertEqual(interstitial_triangle_aliases(image, Box(0, 0, 800, 608),
                                                      keys[1:], []), set())
        proposed = [keys[0], (3, 344, 320), keys[-1]]
        self.assertEqual(interstitial_triangle_aliases(image, Box(0, 0, 800, 608),
                                                      proposed, []), set())

    def test_offscreen_configuration_abstains(self):
        image, _ = scene(6, 32, (45, 45, 45), (225, 225, 225))
        # Missing base samples must not be fabricated by clamped border pixels.
        keys = [(3, 304, 0), (3, 336, 0), (6, 320, 0)]
        self.assertEqual(interstitial_triangle_aliases(image, Box(0, 0, 800, 608),
                                                      keys, []), set())

    def test_half_embedded_real_triangle_is_preserved(self):
        image, keys = scene(6, 32, (45, 45, 45), (225, 225, 225), true_middle=True)
        raster = Image.frombytes('RGB', (800, 608), image.data)
        ImageDraw.Draw(raster).rectangle((320, 320, 351, 335), fill=(50, 105, 85))
        image = RGBImage(800, 608, raster.tobytes())
        self.assertEqual(interstitial_triangle_aliases(image, Box(0, 0, 800, 608),
                                                      keys, [(320, 320, 32, 16)]), set())


class AppleGeometryBoundsTests(unittest.TestCase):
    def arbitrate(self, apple, spike, image=None):
        return _dedupe_overlapping_geometry(
            [apple, spike], anchor_types=frozenset({OBJ_APPLE}),
            source_image=image,
            source_room=Box(0, 0, image.width, image.height) if image else None,
        )

    def test_separate_triangle_survives_raw_origin_proximity_at_capture_scales(self):
        for scale in (1, 1.25, 1.5):
            with self.subTest(scale=scale):
                apple = Detection('apple', OBJ_APPLE, 320, 320, .8,
                                  Box(round(310 * scale), round(308 * scale),
                                      round(21 * scale), round(24 * scale)))
                spike = Detection('spike_left', OBJ_SPIKE_LEFT, 336, 304, .8,
                                  Box(round(336 * scale), round(304 * scale),
                                      round(32 * scale), round(32 * scale)))
                raster = Image.new('RGB', (800, 608), (220, 215, 210))
                ImageDraw.Draw(raster).polygon(
                    [(336 + x, 304 + y) for x, y in VERTICES[OBJ_SPIKE_LEFT]],
                    fill=(40, 45, 50),
                )
                raster = raster.resize((round(800 * scale), round(608 * scale)),
                                       Image.Resampling.BILINEAR)
                image = RGBImage(raster.width, raster.height, raster.tobytes())
                self.assertEqual(self.arbitrate(apple, spike, image), [apple, spike])
                self.assertEqual(self.arbitrate(apple, spike), [apple])

    def test_disjoint_boxes_without_complete_source_triangle_still_lose(self):
        apple = Detection('apple', OBJ_APPLE, 320, 320, .8, Box(310, 308, 21, 24))
        spike = Detection('spike_left', OBJ_SPIKE_LEFT, 336, 304, .8, Box(336, 304, 32, 32))
        raster = Image.new('RGB', (800, 608), (220, 215, 210))
        image = RGBImage(raster.width, raster.height, raster.tobytes())
        self.assertEqual(self.arbitrate(apple, spike, image), [apple])

    def test_source_overlapping_custom_fruit_still_protects_marker(self):
        apple = Detection('apple', OBJ_APPLE, 320, 320, .8, Box(308, 304, 40, 40))
        spike = Detection('spike_left', OBJ_SPIKE_LEFT, 336, 304, .8, Box(336, 304, 32, 32))
        raster = Image.new('RGB', (800, 608), (220, 215, 210))
        ImageDraw.Draw(raster).polygon(
            [(336 + x, 304 + y) for x, y in VERTICES[OBJ_SPIKE_LEFT]],
            fill=(40, 45, 50),
        )
        image = RGBImage(raster.width, raster.height, raster.tobytes())
        self.assertEqual(self.arbitrate(apple, spike, image), [apple])

    def test_native_overlap_or_missing_source_bounds_cannot_relax_precedence(self):
        apple = Detection('apple', OBJ_APPLE, 320, 320, .8, Box(310, 308, 21, 24))
        overlap = Detection('spike_up', OBJ_SPIKE_UP, 304, 304, .8, Box(304, 304, 32, 32))
        raster = Image.new('RGB', (800, 608), (220, 215, 210))
        draw = ImageDraw.Draw(raster)
        draw.polygon([(304 + x, 304 + y) for x, y in VERTICES[OBJ_SPIKE_UP]],
                     fill=(40, 45, 50))
        draw.polygon([(336 + x, 304 + y) for x, y in VERTICES[OBJ_SPIKE_LEFT]],
                     fill=(40, 45, 50))
        image = RGBImage(raster.width, raster.height, raster.tobytes())
        self.assertEqual(self.arbitrate(apple, overlap, image), [apple])
        missing = Detection('spike_left', OBJ_SPIKE_LEFT, 336, 304, .8, Box(336, 304, 0, 0))
        self.assertEqual(self.arbitrate(apple, missing, image), [apple])


if __name__ == '__main__':
    unittest.main()
