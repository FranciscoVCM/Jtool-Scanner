"""Portable source ownership: authored pixels, never room/reference answers."""
import unittest

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_color_evidence import QuantizedColorSlopeField
from jtool_scanner.spike_shape import VERTICES
from jtool_scanner.spike_source_artwork import CrossArtworkOwner


def rgb_field(raster):
    image = RGBImage(raster.width, raster.height, raster.tobytes())
    return QuantizedColorSlopeField(image, Box(0, 0, image.width, image.height))


def artwork(direction, *, palette=0, scale=1., triangle=None, arms=4, shadow=False):
    colors = [((160, 90, 115), (40, 30, 55)), ((45, 65, 75), (210, 230, 235)),
              ((110, 125, 135), (75, 90, 100)), ((185, 205, 195), (215, 235, 225))]
    background, ink = colors[palette]
    raster = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(raster)
    parent = (320, 240)
    x, y = parent
    for ex, ey in ((0, 0), (32, 0), (0, 32), (32, 32))[:arms]:
        draw.line((x + ex, y + ey, x + 16, y + 16), fill=ink, width=2)
    draw.rectangle((x, y, x + 32, y + 32), outline=ink, width=1)
    dx, dy = {3: (8, 16), 4: (0, 8), 5: (16, 8), 6: (8, 0)}[direction]
    mini = (direction + 4, x + dx, y + dy)
    if triangle:
        points = [(mini[1] + vx / 2, mini[2] + vy / 2) for vx, vy in VERTICES[direction]]
        if triangle == 'filled':
            draw.polygon(points, fill=(250, 245, 225))
        else:
            draw.line(points + points[:1], fill=(10, 5, 20) if triangle == 'outline'
                      else (45, 165, 15), width=2)
    if scale != 1:
        raster = raster.resize((round(800 * scale), round(608 * scale)), Image.Resampling.BILINEAR)
    rgb = rgb_field(raster)
    if shadow:
        # Recapture blur and a broad illumination layer, with unchanged truth.
        raster = Image.frombytes('RGB', (800, 608), rgb.pixels)
        for py in range(224, 288):
            for px in range(304, 368):
                multiplier = .48 if px < 332 else 1.
                raster.putpixel((px, py), tuple(round(c * multiplier) for c in raster.getpixel((px, py))))
        if scale != 1:
            raster = raster.resize((round(800 * scale), round(608 * scale)), Image.Resampling.BILINEAR)
        rgb = rgb_field(raster)
    return rgb, mini, parent


def supplemental(direction, mode, scale):
    background, ink = (110, 130, 150), (80, 100, 120)
    if mode == 'water_triangle':
        background, ink = (30, 65, 135), (15, 40, 65)
    raster = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(raster)
    parent = (320, 240)
    x, y = parent
    if mode not in ('standalone', 'mini_pair'):
        ends = ((0, 0), (32, 0), (0, 32), (32, 32)) if mode != 'open_v' else ((0, 0), (32, 0))
        for ex, ey in ends:
            draw.line((x + ex, y + ey, x + 16, y + 16), fill=ink, width=2)
        draw.rectangle((x, y, x + 32, y + 32), outline=ink, width=1)
    dx, dy = {3: (8, 16), 4: (0, 8), 5: (16, 8), 6: (8, 0)}[direction]
    mini = (direction + 4, x + dx, y + dy)
    if mode == 'cross_boundary':
        mini = (direction + 4, x + 24, y + 24)
    points = [(mini[1] + vx / 2, mini[2] + vy / 2) for vx, vy in VERTICES[direction]]
    if mode != 'open_v':
        if mode == 'same_ink_outline':
            draw.line(points + points[:1], fill=ink, width=2)
        else:
            draw.polygon(points, fill=ink if mode != 'water_triangle' else (190, 205, 225))
    if mode == 'mini_pair':
        other = (direction + 4, x + (0 if dx else 16), y + (0 if dy else 16))
        draw.polygon([(other[1] + vx / 2, other[2] + vy / 2) for vx, vy in VERTICES[direction]], fill=ink)
    if scale != 1:
        raster = raster.resize((round(800 * scale), round(608 * scale)), Image.Resampling.BILINEAR)
    return rgb_field(raster), mini, parent


class SourceArtworkTests(unittest.TestCase):
    def test_crossed_art_owns_only_without_independent_real_triangle(self):
        for direction in VERTICES:
            for palette in range(4):
                for scale in (1., 1.25):
                    for triangle in (None, 'filled', 'outline', 'isoluminant'):
                        with self.subTest(direction=direction, palette=palette, scale=scale, triangle=triangle):
                            rgb, mini, parent = artwork(direction, palette=palette, scale=scale, triangle=triangle)
                            self.assertEqual(CrossArtworkOwner(lambda: rgb).owns_at(mini, parent), triangle is None)

    def test_column_illumination_and_recapture_preserve_all_authored_roles(self):
        for direction in VERTICES:
            for palette in range(4):
                for scale in (1., 1.25):
                    for triangle in (None, 'filled', 'outline', 'isoluminant'):
                        with self.subTest(direction=direction, palette=palette, scale=scale, triangle=triangle):
                            rgb, mini, parent = artwork(direction, palette=palette, scale=scale, triangle=triangle, shadow=True)
                            self.assertEqual(CrossArtworkOwner(lambda: rgb).owns_at(mini, parent), triangle is None)

    def test_open_or_incomplete_cross_cannot_own_geometry(self):
        for direction in VERTICES:
            for arms in range(4):
                with self.subTest(direction=direction, arms=arms):
                    rgb, mini, parent = artwork(direction, arms=arms)
                    self.assertFalse(CrossArtworkOwner(lambda: rgb).owns_at(mini, parent))

    def test_same_material_partial_pairs_and_water_do_not_supply_false_owner(self):
        for direction in VERTICES:
            for scale in (1., 1.25):
                for mode in ('standalone', 'same_ink_outline', 'same_ink_filled', 'cross_boundary',
                             'mini_pair', 'open_v', 'water_triangle'):
                    with self.subTest(direction=direction, scale=scale, mode=mode):
                        rgb, mini, parent = supplemental(direction, mode, scale)
                        self.assertFalse(CrossArtworkOwner(lambda: rgb).owns_at(mini, parent))

    def test_invalid_and_clipped_hypotheses_do_not_construct_color_field(self):
        def no_color():
            self.fail('unqualified frame must not request RGB features')
        owner = CrossArtworkOwner(no_color)
        for mini, parent in (((3, 320, 240), (320, 240)), ((7, 320, 240), (0, 240)),
                             ((7, 320, 240), (320, 0)), ((7, 344, 264), (320, 240))):
            self.assertFalse(owner.owns_at(mini, parent))

    def test_normal_frame_cache_and_results_reuse_source_features(self):
        rgb, mini, parent = artwork(6)
        calls = []
        owner = CrossArtworkOwner(lambda: calls.append(True) or rgb)
        self.assertTrue(owner.owns_at(mini, parent))
        frame = owner.frames[parent]
        self.assertTrue(owner.owns_at(mini, parent))
        self.assertIs(owner.frames[parent], frame)
        self.assertTrue(owner.owns(mini))
        count = len(calls)
        self.assertTrue(owner.owns(mini))
        self.assertEqual(len(calls), count)


if __name__ == '__main__':
    unittest.main()
