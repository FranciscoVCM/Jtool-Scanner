"""Signed original-pixel interpolation cannot classify an unseen material."""
from dataclasses import FrozenInstanceError
import unittest

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_rgb_bracket import bracket_original_rgb
from scripts.source_sampling import SourceFrame


WALL = (39, 126, 50)
INK = (150, 52, 124)
MIX = (95, 89, 87)
NATIVE = ((10.5, 11.5), (12.5, 11.5), (14.5, 11.5))


def frame_for(taps=(), *, width=800, height=608, extent=None):
    data = bytearray(bytes((8, 9, 10)) * (width * height))
    for (x, y), color in taps:
        i = (y * width + x) * 3
        data[i:i + 3] = bytes(color)
    image = RGBImage(width, height, bytes(data))
    room = Box(0, 0, width, height)
    if extent is None:
        return SourceFrame(image, room)
    canonical = RGBImage(800, 608, bytes(800 * 608 * 3))
    return SourceFrame(image, room, extent=extent, canonical=canonical)


def measure(frame, points=NATIVE, first=WALL, last=INK):
    return bracket_original_rgb(frame, *points, first_role=first, last_role=last)


class SourceRGBBracketTests(unittest.TestCase):
    def test_near_isoluminant_rgb_mixture_has_physical_evidence(self):
        f = frame_for(zip(((10, 11), (12, 11), (14, 11)), (WALL, MIX, INK)))
        witness = measure(f)
        self.assertIsNotNone(witness)
        self.assertEqual(witness.middle, ((12, 11), MIX))
        self.assertAlmostEqual(witness.alpha, .5, delta=.01)
        self.assertLess(witness.max_rgb_residual, 1)
        with self.assertRaises(FrozenInstanceError):
            witness.alpha_numerator = 0

    def test_fractional_capture_vertical_normal_and_reversed_roles(self):
        geometry = dict(width=980, height=746, extent=Box(-3, -2, 986, 752))
        blank = frame_for(**geometry)
        offset = 2 * blank.pitch[1]
        points = ((28.5, 34.5 - offset), (28.5, 34.5), (28.5, 34.5 + offset))
        actual = [blank.original_position(*p) for p in points]
        self.assertEqual(len(set(actual)), 3)
        f = frame_for(zip(actual, (WALL, MIX, INK)), **geometry)
        forward = measure(f, points)
        backward = measure(f, points[::-1], INK, WALL)
        self.assertIsNotNone(forward)
        self.assertIsNotNone(backward)
        self.assertEqual(forward.first, backward.last)
        self.assertEqual(forward.middle, backward.middle)
        self.assertAlmostEqual(forward.alpha + backward.alpha, 1)
        self.assertIsNone(measure(f, points[::-1]))

    def test_off_segment_paint_is_not_an_edge_blend(self):
        f = frame_for(zip(((10, 11), (12, 11), (14, 11)), (WALL, (95, 132, 87), INK)))
        self.assertIsNone(measure(f))

    def test_same_physical_address_is_not_two_votes(self):
        f = frame_for(zip(((10, 11), (12, 11), (14, 11)), (WALL, MIX, INK)))
        self.assertIsNone(measure(f, (NATIVE[0], (10.75, 11.5), NATIVE[2])))

    def test_out_of_crop_never_uses_visible_canonical_padding(self):
        f = frame_for(width=800, height=600, extent=Box(0, 0, 800, 608))
        self.assertIsNone(measure(f, ((22.5, 597.5), (22.5, 599.5), (22.5, 601.5))))

    def test_requires_same_physical_axis_with_middle_between_endpoints(self):
        f = frame_for(zip(((10, 11), (12, 12), (14, 11)), (WALL, MIX, INK)))
        self.assertIsNone(measure(f, (NATIVE[0], (12.5, 12.5), NATIVE[2])))
        f = frame_for(zip(((10, 11), (15, 11), (14, 11)), (WALL, MIX, INK)))
        self.assertIsNone(measure(f, (NATIVE[0], (15.5, 11.5), NATIVE[2])))

    def test_distant_matching_colors_are_not_a_local_edge_witness(self):
        f = frame_for(zip(((10, 11), (12, 11), (15, 11)), (WALL, MIX, INK)))
        self.assertIsNone(measure(f, (*NATIVE[:2], (15.5, 11.5))))

    def test_exact_alpha_and_residual_boundaries(self):
        a, b = (50, 30, 90), (150, 30, 90)
        for red, green, expected in ((60, 38, True), (140, 38, True), (59, 38, False),
                                     (141, 38, False), (100, 39, False)):
            with self.subTest(red=red, green=green):
                f = frame_for(zip(((10, 11), (12, 11), (14, 11)), (a, (red, green, 90), b)))
                self.assertEqual(measure(f, first=a, last=b) is not None, expected)

    def test_no_witness_from_unseparated_roles(self):
        f = frame_for(zip(((10, 11), (12, 11), (14, 11)), (WALL, MIX, INK)))
        self.assertIsNone(measure(f, first=(39, 126, 50), last=(48, 119, 61)))

    def test_role_validation_does_not_accept_nan_or_bool(self):
        f = frame_for()
        for bad in ((0, 0, float("nan")), (1, True, 2), (1, 2), (1, 2, 260)):
            with self.subTest(role=bad), self.assertRaises(ValueError):
                measure(f, first=bad)


if __name__ == "__main__":
    unittest.main()
