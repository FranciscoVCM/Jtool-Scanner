"""Exact palette distance arithmetic, including the unchanged float fallback."""
from random import Random
from types import SimpleNamespace
import unittest

from scripts.source_rgb_distribution import SourceRGBDistribution
from tests.test_source_rgb_distribution import scene, PARENTS, GLYPHS


def generic_distances(model, rgb):
    return tuple(tuple(min(sum((a - b) ** 2 for a, b in zip(rgb, color))
                           for color in witness.palette)
                       for witness in group)
                 for group in (model.parents, model.background))


def palette_model(parents, background):
    # Arithmetic-only unit: no source/model/semantic qualification is implied.
    model = SourceRGBDistribution.__new__(SourceRGBDistribution)
    model.parents = tuple(SimpleNamespace(palette=tuple(p)) for p in parents)
    model.background = tuple(SimpleNamespace(palette=tuple(p)) for p in background)
    model._distances = {}
    return model


class SourceRGBDistanceArithmeticTests(unittest.TestCase):
    def assert_exact(self, model, values):
        for rgb in values:
            with self.subTest(rgb=rgb):
                expected = generic_distances(model, rgb)
                actual = model._rgb_distances(rgb)
                self.assertEqual(actual, expected)
                self.assertEqual(tuple(tuple(type(v) for v in row) for row in actual),
                                 tuple(tuple(type(v) for v in row) for row in expected))
                self.assertIs(actual, model._rgb_distances(rgb))

    def test_integer_rgb_extremes_random_values_and_unbounded_python_integers(self):
        palette = ((0, 0, 0), (255, 255, 255), (255, 0, 128), (17, 91, 203))
        model = palette_model((palette[:2], palette[1:]), (palette,))
        random = Random(819)
        values = [tuple(random.randrange(256) for _ in range(3)) for _ in range(256)]
        self.assert_exact(model, (*palette, *values, (-4, 1000, 17),
                                 (10 ** 100, -10 ** 90, 10 ** 80)))
        self.assertTrue(model._integer_rgb_palette)

    def test_real_source_palettes_fractional_capture_and_parent_order(self):
        for palette in range(4):
            for scale in (1., 1.23):
                model = SourceRGBDistribution(scene(palette, scale), PARENTS, GLYPHS)
                self.assertIsNone(model.reason)
                values = tuple(dict.fromkeys(color for group in (model.parents, model.background)
                                              for witness in group for color in witness.palette))
                self.assert_exact(model, values)

    def test_float_queries_keep_generic_rounding_and_types(self):
        palette = ((0, 0, 0), (255, 255, 255), (31, 99, 241))
        model = palette_model((palette,), (palette[1:],))
        self.assert_exact(model, ((.1, .2, .3), (1e100, -1e99, .125),
                                 (12.123456789, 77.987654321, 234.9999999)))

    def test_noninteger_palette_keeps_generic_arithmetic(self):
        model = palette_model((((.1, .2, .3), (1., 2., 3.)),),
                              (((33.125, 91.375, 201.625),),))
        self.assert_exact(model, ((17, 91, 203), (.3, .7, .9), (255, 0, 255)))
        self.assertFalse(model._integer_rgb_palette)

    def test_bool_and_integer_subclass_queries_keep_fallback(self):
        class CustomInt(int):
            pass
        model = palette_model((((0, 0, 0), (255, 255, 255)),), (((11, 22, 33),),))
        self.assert_exact(model, ((True, False, True), (CustomInt(17), 91, 203)))

    def test_other_tuple_lengths_preserve_generic_zip_semantics(self):
        model = palette_model((((0, 0, 0), (255, 255, 255)),), (((11, 22, 33),),))
        self.assert_exact(model, ((), (10,), (10, 20), (10, 20, 30, 40)))

    def test_duplicate_palettes_do_not_change_group_minima_or_order(self):
        colors = ((7, 19, 37), (51, 81, 101))
        model = palette_model((colors, colors[:1], colors), (colors[1:], colors))
        self.assert_exact(model, ((0, 0, 0), (7, 19, 37), (81, 1, 211)))

    def test_hashable_non_tuple_palettes_keep_the_generic_iterable_path(self):
        model = palette_model(((frozenset((0, 1, 2)),),),
                              ((frozenset((11, 22, 33)),),))
        self.assert_exact(model, ((10, 20, 30), (91, 31, 211)))

    def test_hashable_iterator_query_keeps_generic_consumption_semantics(self):
        model = palette_model((((0, 0, 0),),), (((255, 255, 255),),))
        self.assertEqual(model._rgb_distances(iter((1, 2, 3))), ((14,), (0,)))


if __name__ == '__main__':
    unittest.main()
