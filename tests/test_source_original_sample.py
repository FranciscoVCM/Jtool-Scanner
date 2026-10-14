"""One raw lookup retains exact original coordinates, RGB and unknown coverage."""
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_sampling import SourceFrame


def raster(width=800, height=608, color=(17, 130, 240)):
    return RGBImage(width, height, bytes(color) * width * height)


class OriginalSampleTests(TestCase):
    def test_original_coordinate_conversion_runs_once(self):
        frame = SourceFrame(raster(), Box(0, 0, 800, 608))
        original = SourceFrame.original_position
        with patch.object(SourceFrame, 'original_position', autospec=True,
                          side_effect=original) as position:
            self.assertEqual(frame.original_sample(96.375, 240.875),
                             ((96, 240), (17, 130, 240)))
        position.assert_called_once_with(frame, 96.375, 240.875)

    def test_raw_sample_equals_existing_position_and_pixel_at_multiple_scales(self):
        for width, height in ((800, 608), (1000, 760), (1200, 912)):
            image = raster(width, height)
            frame = SourceFrame(image, Box(0, 0, width, height))
            for x in (.5, 1, 96.375, 120, 799.5):
                for y in (.5, 48, 240.875, 368, 607.5):
                    with self.subTest(width=width, height=height, x=x, y=y):
                        self.assertEqual(frame.original_sample(x, y),
                                         (frame.original_position(x, y), frame.original_pixel(x, y)))

    def test_native_outside_and_nonfinite_stay_unknown(self):
        frame = SourceFrame(raster(), Box(0, 0, 800, 608))
        for point in ((-.2, 20), (800, 20), (20, -.2), (20, 608),
                      (float('nan'), 20), (20, float('inf'))):
            with self.subTest(point=point):
                self.assertEqual(frame.original_sample(*point), (None, None))

    def test_negative_capture_extent_floors_before_crop_check(self):
        frame = SourceFrame(raster(), Box(0, 0, 800, 608),
                            extent=Box(-1, 0, 800, 608), canonical=raster(color=(255, 0, 0)))
        self.assertEqual(frame.original_sample(.8, 20), (None, None))
        self.assertEqual(frame.original_sample(1, 20), ((0, 20), (17, 130, 240)))

    def test_physical_crop_not_display_padding_supplies_raw_rgb(self):
        frame = SourceFrame(raster(1000, 800), Box(100, 100, 800, 608),
                            extent=Box(96, 100, 800, 608), canonical=raster(color=(255, 0, 0)))
        self.assertEqual(frame.original_sample(2, 20), (None, None))
        self.assertEqual(frame.original_sample(4, 20), ((100, 120), (17, 130, 240)))

    def test_caller_and_exposed_snapshot_mutation_cannot_change_sample(self):
        image = raster()
        frame = SourceFrame(image, Box(0, 0, 800, 608))
        snapshot = frame.original_snapshot()
        before = frame.original_sample(96.375, 240.875)
        image.data = bytes((255, 0, 0)) * 800 * 608
        snapshot.data = bytes((0, 255, 0)) * 800 * 608
        self.assertEqual(frame.original_sample(96.375, 240.875), before)

    def test_sample_retains_all_rgb_channels_and_returns_immutable_pair(self):
        for color in ((255, 0, 0), (0, 255, 0), (130, 240, 17), (5, 5, 5)):
            frame = SourceFrame(raster(color=color), Box(0, 0, 800, 608))
            position, rgb = frame.original_sample(96.375, 240.875)
            self.assertIsInstance(position, tuple)
            self.assertIsInstance(rgb, tuple)
            self.assertEqual(rgb, color)
