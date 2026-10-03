"""Source geometry owns its size even when coarse rectangles are mistaken."""
import unittest

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from jtool_scanner.spike_size import _CachedShapeField
from jtool_scanner.spike_source_ownership import source_size_owns
from tests.test_spike_size import pair


STYLES = (
    ((20, 30, 40), (90, 100, 110), (210, 220, 230)),
    ((235, 225, 215), (180, 165, 150), (40, 50, 60)),
    ((35, 45, 55), (80, 90, 100), (135, 145, 155)),
)
MASKS = ((320, 320, 16, 32), (336, 320, 16, 32),
         (320, 320, 32, 16), (320, 336, 32, 16))


def source_frame(direction, colors, scale, closed):
    """Authored source pixels, independent of detector output or references."""
    ink, fill, background = colors
    raster = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(raster)
    vertices = [(320 + x, 320 + y) for x, y in VERTICES[direction]]
    mini = pair(direction)[0]
    if closed:
        draw.polygon(vertices, fill=fill, outline=ink, width=2)
        # Interior sprite decoration is not another gameplay object.
        draw.polygon([(mini[1] + x / 2, mini[2] + y / 2)
                      for x, y in VERTICES[direction]],
                     fill=fill, outline=ink, width=1)
    else:
        draw.line((vertices[0], vertices[1]), fill=ink, width=2)
        draw.line((vertices[0], vertices[2]), fill=ink, width=2)
    raster = raster.resize((round(800 * scale), round(608 * scale)),
                           Image.Resampling.BILINEAR)
    return RGBImage(raster.width, raster.height, raster.tobytes()), mini


class SourceOwnershipTests(unittest.TestCase):
    def check_source_frames(self, closed):
        for direction in VERTICES:
            for colors in STYLES:
                for scale in (1, 1.25, 1.5):
                    image, mini = source_frame(direction, colors, scale, closed)
                    fields = {}

                    def field(size):
                        if size not in fields:
                            fields[size] = _CachedShapeField(
                                image, Box(0, 0, image.width, image.height),
                                native_size=size)
                        return fields[size]

                    for mask in MASKS:
                        with self.subTest(direction=direction, colors=colors,
                                          scale=scale, mask=mask):
                            state = dict(field=field, solids=[mask], materials={},
                                         rectangles={}, tip_materials={})
                            self.assertEqual(source_size_owns(
                                state, mini, (direction, 320, 320)), closed)

    def test_closed_source_size_survives_false_coarse_rectangle_masks(self):
        self.check_source_frames(True)

    def test_open_slopes_do_not_establish_source_ownership(self):
        self.check_source_frames(False)


if __name__ == '__main__':
    unittest.main()
