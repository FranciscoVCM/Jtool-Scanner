"""Procedural original-source registration and late killblock arbitration."""

import unittest

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.scanner import Detection, ScanResult, _recover_source_registered_killers
from jtool_scanner.source_killers import RegisteredCellEvidence


def fixture(width=160, height=160, count=3):
    raster = Image.new('RGB', (width, height), (60, 60, 60))
    draw = ImageDraw.Draw(raster)
    for index in range(count):
        cx, cy = index % 5, index // 5
        draw.rectangle((round(cx * width / 5), round(cy * height / 5),
                        round((cx + 1) * width / 5) - 1,
                        round((cy + 1) * height / 5) - 1), fill=(180, 30, 20))
    return RGBImage(width, height, raster.tobytes())


def field(cell_size=32, cross=True, header=False):
    size = cell_size * 5
    image = Image.new('RGB', (size, size), (50, 50, 50))
    draw = ImageDraw.Draw(image)
    for cx in range(3):
        draw.rectangle((cx * cell_size, 0, (cx + 1) * cell_size - 1,
                        cell_size - 1), fill=(180, 30, 20))
    a, b = 3 * cell_size, 4 * cell_size - 1
    draw.rectangle((a, a, b, b), fill=(70, 20, 18))
    if cross:
        draw.line((a, a, b, b), fill=(20, 5, 5), width=2)
        draw.line((a, b, b, a), fill=(20, 5, 5), width=2)
    if header:
        draw.rectangle((a, a, b, a + cell_size // 4 - 1), fill=(220, 220, 220))
    return RGBImage(size, size, image.tobytes())


class RegistrationTests(unittest.TestCase):
    def test_integer_and_fractional_source_cells(self):
        for width, height in ((160, 160), (197, 193), (320, 320)):
            with self.subTest(size=(width, height)):
                evidence = RegisteredCellEvidence(fixture(width, height),
                                                  Box(0, 0, width, height), (5, 5))
                self.assertTrue(evidence.active)
                self.assertEqual(evidence.colour_positives, {(0, 0), (1, 0), (2, 0)})

    def test_exact_fractional_area_integral(self):
        evidence = RegisteredCellEvidence(fixture(), Box(0, 0, 160, 160), (5, 5))
        self.assertEqual(evidence.prefix(.5, .5), .25)
        self.assertEqual(evidence.prefix(10.5, 10.5), 110.25)

    def test_one_dark_source_row_votes_real_area_not_one_sixteenth(self):
        raster = Image.new('RGB', (195, 195), (180, 30, 20))
        ImageDraw.Draw(raster).line((0, 194, 194, 194), fill=(60, 10, 5))
        evidence = RegisteredCellEvidence(RGBImage(195, 195, raster.tobytes()),
                                          Box(0, 0, 195, 195), (5, 5))
        self.assertAlmostEqual(evidence.ratios[2, 4], 38 / 39)
        self.assertIn((2, 4), evidence.colour_positives)

    def test_no_source_witness_quorum_or_cropped_context(self):
        image = fixture(count=2)
        for box, grid in ((Box(0, 0, 160, 160), (5, 5)),
                          (Box(-1, 0, 160, 160), (5, 5)),
                          (Box(0, 0, 160, 160), (25, 19))):
            self.assertFalse(RegisteredCellEvidence(image, box, grid).active)

    def test_late_retag_preserves_flags_markers_and_old_backing(self):
        image = fixture()
        left, top = 320, 224
        safe = Detection('safe', 1, left, top, .8, Box(0, 0, 32, 32))
        killer = Detection('oldkiller', 18, left + 32, top, .99, Box(32, 0, 32, 32))
        backing = Detection('oldbacking', 1, left + 32, top, .4, Box(32, 0, 32, 32))
        save = Detection('save', 12, left, top, .92, Box(2, 2, 26, 26))
        before = ScanResult(160, 160, Box(0, 0, 160, 160),
                            [safe, killer, backing, save], infinite_jump=1, dot_kid=1,
                            source_grid=(5, 5), source_geometry=True)
        after = _recover_source_registered_killers(before, image)
        for retained in (save, killer, backing):
            self.assertIn(retained, after.detections)
        self.assertNotIn(safe, after.detections)
        self.assertEqual(before.detections, [safe, killer, backing, save])
        self.assertEqual((after.infinite_jump, after.dot_kid, after.source_geometry),
                         (1, 1, True))

    def test_uncertain_or_low_resolution_board_abstains(self):
        image = fixture(60, 60)
        self.assertFalse(RegisteredCellEvidence(image, Box(0, 0, 60, 60), (5, 5)).active)


class RegisteredCrossTests(unittest.TestCase):
    def test_native_dark_cross_uses_unchanged_shape_predicate(self):
        evidence = RegisteredCellEvidence(field(), Box(0, 0, 160, 160), (5, 5))
        proof = evidence.proof(3, 3)
        self.assertIsNotNone(proof)
        self.assertFalse(proof['colour'])

    def test_plain_dim_red_and_save_header_are_not_crosses(self):
        for options in (dict(cross=False), dict(header=True)):
            evidence = RegisteredCellEvidence(field(**options),
                                              Box(0, 0, 160, 160), (5, 5))
            self.assertIsNone(evidence.proof(3, 3))

    def test_oversampled_small_cross_cannot_duplicate_support(self):
        evidence = RegisteredCellEvidence(field(cell_size=20),
                                          Box(0, 0, 100, 100), (5, 5))
        self.assertIsNone(evidence.proof(3, 3))

    def test_colour_outside_source_crop_is_not_scanned(self):
        base = field(cross=False)
        image = Image.new('RGB', (240, 240), (200, 30, 20))
        image.paste(Image.frombytes('RGB', (160, 160), base.data), (40, 40))
        source = RGBImage(240, 240, image.tobytes())
        for mode in (False, True):
            raw = ScanResult(240, 240, Box(40, 40, 160, 160), [],
                             source_grid=(5, 5), source_geometry=mode)
            result = _recover_source_registered_killers(raw, source)
            self.assertEqual(len(result.detections), 3)
            self.assertTrue(all(40 <= d.image_box.x and d.image_box.right <= 200
                                for d in result.detections))
            self.assertEqual(result.source_geometry, mode)


if __name__ == '__main__':
    unittest.main()
