"""Object size is independent of screenshot scale and component brightness."""
import unittest

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.scanner import (
    _ColorProfile, _detect_adaptive_compact_room_spikes,
    _image_box_to_jtool_origin,
)


class ComponentOriginTests(unittest.TestCase):
    def test_native_size_and_capture_scale(self):
        for scale in (1, 1.25, 2):
            for size in (16, 32):
                with self.subTest(scale=scale, size=size):
                    room = Box(12, 20, int(800*scale), int(608*scale))
                    component = Box(12+int(160*scale), 20+int(192*scale),
                                    int(size*scale), int(size*scale))
                    self.assertEqual((160, 192), _image_box_to_jtool_origin(
                        component, room, 8, object_size=size))
                    if size == 32:
                        self.assertEqual((160, 192), _image_box_to_jtool_origin(component, room, 8))

    def test_real_components_all_directions_sizes_and_scales(self):
        for scale in (1, 1.25, 2):
            for background, foreground in ((30, 240), (85, 210)):
                with self.subTest(scale=scale, palette=(background, foreground)):
                    image = Image.new('RGB', (800, 608), (background,)*3)
                    draw = ImageDraw.Draw(image)
                    expected = set()
                    for size, base_type, y in ((16, 7, 160), (32, 3, 256)):
                        for index in range(4):
                            x = 160 + index*96
                            n = size-1
                            vertices = (
                                ((n/2, 0), (0, n), (n, n)),
                                ((n, n/2), (0, 0), (0, n)),
                                ((0, n/2), (n, 0), (n, n)),
                                ((n/2, n), (0, 0), (n, 0)),
                            )[index]
                            draw.polygon([(x+px, y+py) for px, py in vertices], fill=(foreground,)*3)
                            expected.add((base_type+index, x, y))
                    image = image.resize((int(800*scale), int(608*scale)), Image.Resampling.NEAREST)
                    rgb = RGBImage(image.width, image.height, image.tobytes())
                    found = _detect_adaptive_compact_room_spikes(
                        rgb, Box(0, 0, image.width, image.height), _ColorProfile(100, 100, 100, 0))
                    self.assertEqual(expected, {(d.type_id, d.x, d.y) for d in found})
