"""Independent pixel oracles for clipped hollow full/mini synthetic fixtures."""
from math import hypot
from unittest import TestCase

from PIL import Image, ImageDraw

from jtool_scanner.spike_shape import VERTICES
from tests.source_sprite_fixtures import hollow_triangle_tile


class HollowSpriteFixtureTests(TestCase):
    BG = (10, 20, 30)
    INK = (210, 220, 230)
    CORE = (13, 23, 33)

    def tile(self, direction=3, size=16, **kwargs):
        return hollow_triangle_tile(direction, size, background=self.BG,
                                    ink=self.INK, interior=self.CORE, **kwargs)

    def test_even_width_line_on_exclusive_bottom_loses_old_mini_base(self):
        # Regression oracle for the old private scene: don't change/relabel it.
        old = Image.new('RGB', (16, 16), self.BG)
        polygon = [(u/2, v/2) for u, v in VERTICES[3]]
        pen = ImageDraw.Draw(old)
        pen.polygon(polygon, fill=self.CORE)
        pen.line(polygon+[polygon[0]], fill=self.INK, width=2)
        self.assertNotEqual(old.getpixel((8, 15)), self.INK)
        self.assertEqual(self.tile().getpixel((8, 15)), self.INK)

    def test_all_three_faces_have_ink_in_all_directions_sizes_and_palettes(self):
        palettes = ((self.BG, self.INK, self.CORE),
                    ((225, 220, 215), (30, 40, 50), (228, 223, 218)),
                    ((0, 130, 0), (255, 0, 0), (3, 133, 3)))
        for size in (16, 32):
            for direction in VERTICES:
                for bg, ink, core in palettes:
                    with self.subTest(size=size, direction=direction, background=bg):
                        tile = hollow_triangle_tile(direction, size, background=bg,
                                                    ink=ink, interior=core)
                        poly = [(u*size/32, v*size/32) for u, v in VERTICES[direction]]
                        for a, b in zip(poly, poly[1:]+poly[:1]):
                            # Oracle uses distance to the middle half of each
                            # edge; it doesn't call the fixture's inside test.
                            tx, ty = b[0]-a[0], b[1]-a[1]
                            length = hypot(tx, ty)
                            hits = []
                            for y in range(size):
                                for x in range(size):
                                    q = ((x+.5-a[0])*tx+(y+.5-a[1])*ty)/length**2
                                    distance = abs(tx*(y+.5-a[1])-ty*(x+.5-a[0]))/length
                                    if .25 <= q <= .75 and distance <= 1:
                                        hits.append(tile.getpixel((x, y)) == ink)
                            self.assertGreaterEqual(sum(hits), size//4)
                        self.assertIn(core, [tile.getpixel((x, y))
                                             for y in range(size) for x in range(size)])

    def test_exact_footprint_does_not_paint_neighbour_or_background_corners(self):
        for direction in VERTICES:
            tile = self.tile(direction)
            room = Image.new('RGB', (48, 48), self.BG)
            room.paste(tile, (16, 16))
            for y in range(48):
                for x in range(48):
                    if not (16 <= x < 32 and 16 <= y < 32):
                        self.assertEqual(room.getpixel((x, y)), self.BG)
            values = [tile.getpixel((x, y)) for y in range(16) for x in range(16)]
            self.assertGreaterEqual(values.count(self.BG), 80)

    def test_invalid_geometry_and_strokes_rejected(self):
        for direction, size, stroke in ((True, 16, 2), (7, 16, 2),
                                        (3, True, 2), (3, 24, 2),
                                        (3, 16, 0), (3, 16, -1),
                                        (3, 16, float('nan')), (3, 16, float('inf')),
                                        (3, 16, True), (3, 16, 5)):
            with self.subTest(direction=direction, size=size, stroke=stroke):
                with self.assertRaises(ValueError):
                    self.tile(direction, size, stroke_width=stroke)
