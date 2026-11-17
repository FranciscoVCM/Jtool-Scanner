import unittest

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_interior_glyphs import INTERIOR_POINTS
from scripts.source_partial_aperture import whole_source_body_aperture
from scripts.source_pixel_geometry import original_pixel_bounds
from scripts.source_sampling import SourceFrame


class PartialApertureTests(unittest.TestCase):
    def frame(self, width=980, height=747):
        return SourceFrame(RGBImage(width, height, bytes(width * height * 3)),
                           Box(0, 0, width, height))

    def test_original_point_outside_mask_but_its_pixel_intersects(self):
        frame = self.frame()
        x, y = 104, 80
        i = 25
        a, b = INTERIOR_POINTS[i]
        px, py = x + a, y + b
        src = frame.original_position(px, py)
        left, top, right, bottom = original_pixel_bounds(frame, *src)
        # Move the possible wall edge strictly inside the original square,
        # but keep the nominal body sample outside that wall.
        if left < px:
            occluder = (left-8, top-1, (left+px)/2, bottom+1)
        else:
            self.assertGreater(right, px)
            occluder = ((right+px)/2, top-1, right+8, bottom+1)
        clear = whole_source_body_aperture(frame, (3, x, y), (i,), ())
        mixed = whole_source_body_aperture(frame, (3, x, y), (i,), (occluder,))
        self.assertEqual(clear.indices, (i,))
        self.assertEqual(mixed.indices, ())
        self.assertEqual(mixed.occluder_mixed, 1)

    def test_distinct_squares_preserve_requested_order(self):
        frame = self.frame(800, 608)
        result = whole_source_body_aperture(frame, (3, 104, 80), (27, 25, 27, 26), ())
        self.assertEqual(result.indices, (27, 25, 26))
        self.assertEqual(result.shared_original, 1)

    def test_cropped_pixels_do_not_become_body_or_background(self):
        frame = self.frame(800, 608)
        result = whole_source_body_aperture(frame, (3, -48, 80), range(50), ())
        self.assertEqual(result.indices, ())
        self.assertEqual(result.unknown_original, 50)

    def test_typed_index_is_required(self):
        with self.assertRaises(ValueError):
            whole_source_body_aperture(self.frame(), (3, 104, 80), (True,), ())
