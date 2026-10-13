"""Capture coordinates never promote display padding to original RGB evidence."""
import unittest

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_contours import SourceContours
from scripts.source_glyph_prototypes import SourceGlyphLibrary
from scripts.source_sampling import SourceFrame
from tests.test_source_glyph_prototypes import scene


def raster(width=800, height=608, color=(17, 130, 240)):
    return RGBImage(width, height, bytes(color) * (width * height))


class SourceSamplingTests(unittest.TestCase):
    def test_identity_centers_and_raw_pixels_retain_rgb(self):
        image = raster()
        frame = SourceFrame(image, Box(0, 0, 800, 608))
        for x, y in ((.5, .5), (799.5, 607.5), (10.75, 13.25)):
            self.assertEqual(frame.pixel(x, y), (17, 130, 240))
            self.assertEqual(frame.original_pixel(x, y), (17, 130, 240))
        self.assertEqual(frame.pitch, (1, 1))

    def test_no_native_edge_clamping(self):
        frame = SourceFrame(raster(), Box(0, 0, 800, 608))
        for x, y in ((0, 20), (800, 20), (20, 0), (20, 608), (-.1, 20)):
            self.assertIsNone(frame.pixel(x, y))
        self.assertIsNone(frame.original_pixel(-.1, 20))

    def test_negative_extent_floor_does_not_truncate_into_pixel_zero(self):
        frame = SourceFrame(raster(), Box(0, 0, 800, 608),
                            extent=Box(-1, 0, 800, 608), canonical=raster())
        self.assertIsNone(frame.original_position(.8, 20))
        self.assertIsNone(frame.original_pixel(.8, 20))
        self.assertEqual(frame.original_position(1, 20), (0, 20))

    def test_capture_edge_extension_is_unknown_even_if_rgb_looks_valid(self):
        frame = SourceFrame(raster(982, 747), Box(0, 0, 982, 747),
                            extent=Box(-5, -1, 988, 750), canonical=raster())
        for point in ((.5, 100), (799.5, 100), (100, .5), (100, 607.5)):
            self.assertIsNone(frame.pixel(*point))
        self.assertEqual(frame.pixel(20, 20), (17, 130, 240))
        self.assertEqual(frame.original_position(120, 48), (143, 58))
        self.assertEqual(frame.pitch, (800 / 988, 608 / 750))

    def test_interpolated_tap_cannot_borrow_padding(self):
        frame = SourceFrame(raster(), Box(0, 0, 800, 608),
                            extent=Box(-1, 0, 800, 608), canonical=raster())
        self.assertIsNone(frame.pixel(1.25, 20))
        self.assertEqual(frame.pixel(1.5, 20), (17, 130, 240))

    def test_physical_crop_is_coverage_not_whole_image(self):
        frame = SourceFrame(raster(1000, 800), Box(100, 100, 800, 608),
                            extent=Box(96, 100, 800, 608), canonical=raster())
        self.assertIsNone(frame.original_position(2, 20))
        self.assertIsNone(frame.pixel(2, 20))
        self.assertEqual(frame.original_position(4, 20), (100, 120))

    def test_original_patch_and_teacher_footprints_reject_partial_coverage(self):
        frame = SourceFrame(raster(982, 747), Box(0, 0, 982, 747),
                            extent=Box(-5, -1, 988, 750), canonical=raster())
        self.assertIsNone(frame.original_patch(4, 20, 4))
        self.assertFalse(frame.rectangle_available(0, 48, 32, 32, margin=4))
        self.assertTrue(frame.rectangle_available(32, 48, 32, 32, margin=4))
        self.assertEqual(len(frame.original_patch(32, 48, 4)), 16)

    def test_snapshot_ignores_replacing_callers_rgb_fields(self):
        image, canonical = raster(), raster()
        frame = SourceFrame(image, Box(0, 0, 800, 608), canonical=canonical)
        image.data = bytes((0, 0, 0)) * (800 * 608)
        canonical.data = image.data
        image.width = 1
        self.assertEqual(frame.original_pixel(10, 20), (17, 130, 240))
        self.assertEqual(frame.pixel(10, 20), (17, 130, 240))

    def test_invalid_data_rooms_extents_and_missing_capture_view(self):
        for image, room, kwargs in (
            (RGBImage(2, 2, b'bad'), Box(0, 0, 2, 2), {}),
            (raster(), Box(-1, 0, 800, 608), {}),
            (raster(), Box(0, 0, 800, 608), dict(extent=Box(0, 0, 0, 608))),
            (raster(), Box(0, 0, 800, 608), dict(extent=Box(-1, 0, 800, 608))),
            (raster(), Box(0, 0, 800, 608), dict(canonical=raster(10, 10))),
        ):
            with self.subTest(room=room, kwargs=tuple(kwargs)):
                with self.assertRaises(ValueError):
                    SourceFrame(image, room, **kwargs)

    def test_raw_contours_use_original_positions_and_mark_padding_unknown(self):
        image = raster()
        frame = SourceFrame(image, Box(0, 0, 800, 608),
                            extent=Box(-4, 0, 800, 608), canonical=raster())
        contours = SourceContours(image, frame.extent, source_frame=frame)
        edge = contours.edge((2, 48), (2, 80))
        self.assertTrue(edge.unknown)
        self.assertEqual(edge.support, 0)

    def test_optional_library_frame_preserves_interior_source_teachers(self):
        image, room, locators, positives, negatives = scene(size=32)
        legacy = SourceGlyphLibrary(image, room, locators)
        framed = SourceGlyphLibrary(image, room, locators, source_frame=SourceFrame(image, room))
        self.assertEqual(legacy.anchors, framed.anchors)
        self.assertEqual(legacy.models, framed.models)
        for key in positives + negatives:
            self.assertEqual(legacy.support(*key), framed.support(*key))
        self.assertFalse(framed.support(3, 0, 48)['passed'])

    def test_optional_library_rejects_different_source(self):
        image, room, locators, _, _ = scene(size=32)
        frame = SourceFrame(raster(), room)
        with self.assertRaisesRegex(ValueError, 'must match'):
            SourceGlyphLibrary(image, room, locators, source_frame=frame)

    def test_framed_contours_and_library_can_reuse_frozen_raw_field(self):
        image, room, locators, _, _ = scene(size=32)
        frame = SourceFrame(image, room)
        contours = SourceContours(image, room, source_frame=frame)
        library = SourceGlyphLibrary(image, room, locators, source_frame=frame, contour_field=contours)
        before = contours.triangle(3, 160, 160)
        image.data = bytes(800 * 608 * 3)
        self.assertIs(library.raw.raw.field, contours)
        self.assertEqual(before, contours.triangle(3, 160, 160))
        self.assertEqual(contours.image.pixel(176, 180), (220, 190, 130))

    def test_mismatched_frame_is_rejected_by_raw_contours(self):
        frame = SourceFrame(raster(), Box(0, 0, 800, 608))
        with self.assertRaises(ValueError):
            SourceContours(raster(color=(0, 0, 0)), frame.extent, source_frame=frame)


if __name__ == '__main__':
    unittest.main()
