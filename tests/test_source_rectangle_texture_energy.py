"""Interior identity needs texture distinguishable from RGB quantization.

These are descriptor tests, not object labels: a zero descriptor is no usable
texture evidence, never evidence that terrain or an occluded object is absent.
"""
from math import sqrt
from types import SimpleNamespace
import unittest

from PIL import Image

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_rectangle_prototypes import _interior_signature
from scripts.source_sampling import SourceFrame


ZERO = (0.0,) * 768


def old_signature(pixel, x=0, y=0):
    """Frozen pre-fix arithmetic; genuine above-bound texture stays identical."""
    values = [(i - 7.5, j - 7.5,
               pixel(x + 4 + (i + .5) * 1.5, y + 4 + (j + .5) * 1.5))
              for j in range(16) for i in range(16)]
    mean = tuple(sum(rgb[c] for _, _, rgb in values) / 256 for c in range(3))
    dx, dy = sum(u * u for u, _, _ in values), sum(v * v for _, v, _ in values)
    sx = tuple(sum(u * rgb[c] for u, _, rgb in values) / dx for c in range(3))
    sy = tuple(sum(v * rgb[c] for _, v, rgb in values) / dy for c in range(3))
    residual = tuple(rgb[c] - mean[c] - sx[c] * u - sy[c] * v
                     for u, v, rgb in values for c in range(3))
    length = sqrt(sum(v * v for v in residual))
    return tuple(v / max(length, 1e-12) for v in residual), length / 16


class InteriorTextureEnergyTests(unittest.TestCase):
    def test_exact_flat_and_linear_rgb_have_no_interior_identity(self):
        for pixel in (lambda x, y: (120., 80., 30.),
                      lambda x, y: (30 + .125*x + .25*y,
                                    70 + .25*x - .125*y, 100 - .125*x)):
            self.assertEqual(_interior_signature(SimpleNamespace(pixel=pixel), 0, 0), ZERO)

    def test_rounded_rgb_plane_does_not_turn_quantization_into_texture(self):
        pixel = lambda x, y: (round(30 + .173*x + .219*y),
                              round(90 - .117*x + .293*y),
                              round(130 + .153*x - .127*y))
        before, rms = old_signature(pixel)
        self.assertGreater(rms, .01)
        self.assertAlmostEqual(sum(v*v for v in before), 1.)
        self.assertLess(rms, sqrt(3))
        self.assertEqual(_interior_signature(SimpleNamespace(pixel=pixel), 0, 0), ZERO)

    def test_linear_capture_resampling_across_scales_has_no_identity(self):
        for scale in (.5, 1., 1.25):
            with self.subTest(scale=scale):
                width, height = round(800*scale), round(608*scale)
                # A linear physical RGB field, independently quantized at capture.
                data = bytes(channel for y in range(height) for x in range(width)
                             for channel in (round(25 + .07*x + .03*y),
                                             round(100 - .03*x + .05*y),
                                             round(70 + .04*x - .02*y)))
                image = RGBImage(width, height, data)
                frame = SourceFrame(image, Box(0, 0, width, height))
                self.assertEqual(_interior_signature(frame, 160, 160), ZERO)

    def test_real_above_bound_texture_is_bit_for_bit_unchanged(self):
        for base, amplitude in ((80, 2), (140, 8), (30, 24)):
            for invert in (1, -1):
                with self.subTest(base=base, amplitude=amplitude, invert=invert):
                    def pixel(x, y):
                        sign = 1 if int(x / 3) % 2 == int(y / 3) % 2 else -1
                        ink = invert * amplitude * sign
                        return base + ink, base - ink, base + ink
                    before, rms = old_signature(pixel)
                    self.assertGreater(rms, sqrt(3))
                    after = _interior_signature(SimpleNamespace(pixel=pixel), 0, 0)
                    self.assertEqual(after, before)
                    self.assertAlmostEqual(sum(v*v for v in after), 1.)

    def test_resampled_texture_retains_all_rgb_channels(self):
        for scale in (.5, 1., 1.25):
            with self.subTest(scale=scale):
                # Equal channel sum: this would disappear in a naive grayscale pass.
                colors = ((60, 150, 90), (150, 60, 90))
                raster = Image.new('RGB', (800, 608))
                raster.putdata([colors[((x//4) + (y//4)) % 2]
                                for y in range(608) for x in range(800)])
                raster = raster.resize((round(800*scale), round(608*scale)),
                                       Image.Resampling.BILINEAR)
                image = RGBImage(raster.width, raster.height, raster.tobytes())
                frame = SourceFrame(image, Box(0, 0, image.width, image.height))
                before, rms = old_signature(frame.pixel, 160, 160)
                self.assertGreater(rms, sqrt(3))
                self.assertEqual(_interior_signature(frame, 160, 160), before)

    def test_border_art_cannot_supply_missing_interior_texture(self):
        def pixel(x, y):
            return (10, 20, 30) if 4 <= x < 28 and 4 <= y < 28 else (240, 250, 230)
        self.assertEqual(_interior_signature(SimpleNamespace(pixel=pixel), 0, 0), ZERO)

    def test_unknown_rgb_is_not_converted_to_a_zero_or_background_descriptor(self):
        library = SimpleNamespace(pixel=lambda x, y: None if x > 15 else (80, 90, 100))
        with self.assertRaises(TypeError):
            _interior_signature(library, 0, 0)

    def test_same_256_source_samples_without_an_additional_pass(self):
        calls = []
        def pixel(x, y):
            calls.append((x, y))
            return (90, 100, 110)
        self.assertEqual(_interior_signature(SimpleNamespace(pixel=pixel), 8, 16), ZERO)
        self.assertEqual(calls, [(8+4+(i+.5)*1.5, 16+4+(j+.5)*1.5)
                                 for j in range(16) for i in range(16)])


if __name__ == '__main__':
    unittest.main()
