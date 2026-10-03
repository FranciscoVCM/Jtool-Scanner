"""Exact eleven-of-twelve bound; early exits must not change recognition."""
import unittest

from jtool_scanner.geometry import Box
from jtool_scanner.spike_shape import VERTICES
from jtool_scanner.spike_size import _CachedShapeField
from jtool_scanner.spike_source_corner import mixin
from tests.test_spike_size import pair, scene


CornerField = mixin(_CachedShapeField)


def original_bound(field, x, y, direction):
    if not (0 <= x <= 800 - field.native_size
            and 0 <= y <= 608 - field.native_size):
        return False
    return min(field._side_coverages(x, y, direction, .25)) >= 11 / 12


class CornerBoundTests(unittest.TestCase):
    def test_same_boolean_for_full_sample_set_across_source_appearances(self):
        for direction in VERTICES:
            for objects in ([(direction, 320, 320)], pair(direction)):
                for foreground, background, scale, outlined, opened, texture in (
                    ((35, 45, 65), (220, 225, 235), 1, False, False, False),
                    ((230, 215, 190), (30, 40, 50), 1.25, False, False, True),
                    ((80, 90, 105), (145, 155, 165), 1.5, True, False, True),
                    ((35, 45, 65), (220, 225, 235), 1, False, True, False),
                ):
                    image = scene(objects, foreground, background, scale=scale,
                                  outlined=outlined, erase_base=opened,
                                  texture=texture)
                    for size in (16, 32):
                        field = CornerField(image, Box(0, 0, image.width, image.height),
                                            native_size=size)
                        origins = [(x, y) for y in range(296, 353, 8)
                                   for x in range(296, 353, 8)]
                        origins += [(0, 0), (800 - size, 608 - size),
                                    (-1, 320), (320, -1),
                                    (801 - size, 320), (320, 609 - size)]
                        for x, y in origins:
                            for candidate_direction in VERTICES:
                                with self.subTest(direction=direction, size=size,
                                                  origin=(x, y),
                                                  candidate=candidate_direction,
                                                  scale=scale, outlined=outlined):
                                    self.assertEqual(
                                        field.could_have_strong_slopes(x, y, candidate_direction),
                                        original_bound(field, x, y, candidate_direction))

    def test_blank_source_disproves_bound_without_testing_every_sample(self):
        class BlankField(CornerField):
            def __init__(self):
                self.native_size = 32
                self.vertices = VERTICES
                self.calls = 0

            def gradient(self, x, y):
                self.calls += 1
                return 0., 0.

        field = BlankField()
        self.assertFalse(original_bound(field, 320, 320, 3))
        original_calls = field.calls
        field.calls = 0
        self.assertFalse(field.could_have_strong_slopes(320, 320, 3))
        self.assertLess(field.calls, original_calls)


if __name__ == '__main__':
    unittest.main()
