"""Exact original-RGB search must reproduce exhaustive distances and proofs."""
from copy import deepcopy
from itertools import product
from math import dist, isnan
from random import Random
from unittest import TestCase
from unittest.mock import patch

from scripts import source_interior_glyphs as interior


class OriginalPaintSearchTests(TestCase):
    def test_random_raw_palettes_match_exhaustive_math_dist_exactly(self):
        rng = Random(18271)
        for size in (1, 2, 3, 16, 65, 257, 1024):
            paints = tuple(tuple(rng.randrange(256) for _ in range(3)) for _ in range(size))
            index = interior._OriginalPaintIndex(paints)
            for rgb in paints[:20]+tuple(tuple(rng.randrange(256) for _ in range(3)) for _ in range(350)):
                self.assertEqual(index.distance(rgb), min(dist(rgb, p) for p in paints))

    def test_every_small_boundary_grid_query_and_reversed_palette(self):
        grid = tuple(product((0, 1, 127, 128, 254, 255), repeat=3))
        for paints in (grid, tuple(reversed(grid))):
            index = interior._OriginalPaintIndex(paints)
            for rgb in grid:
                self.assertEqual(index.distance(rgb), min(dist(rgb, p) for p in paints))

    def test_ties_duplicates_and_split_plane_search(self):
        palettes = (((0, 0, 0),)*3, ((0, 0, 0), (2, 0, 0), (1, 1, 0)),
                    ((0, 200, 0), (127, 200, 0), (255, 0, 0), (128, 128, 128)))
        for paints in palettes:
            index = interior._OriginalPaintIndex(paints)
            for rgb in ((1, 0, 0), (127, 0, 0), (0, 0, 0), (128, 200, 128), (255, 255, 255)):
                self.assertEqual(index.distance(rgb), min(dist(rgb, p) for p in paints))

    def test_non_uint8_queries_use_original_exhaustive_result(self):
        paints = ((0, 0, 0), (255, 255, 255))
        index = interior._OriginalPaintIndex(paints)
        for rgb in ((1., 2., 3.), (True, 3, 4), (-1, 300, 2)):
            self.assertEqual(index.distance(rgb), min(dist(rgb, p) for p in paints))

    def test_non_uint8_palettes_and_nan_keep_exhaustive_behavior(self):
        for paints in (((0., 1., 2.), (3., 4., 5.)), ((-100, 300, 2), (0, 0, 0))):
            index = interior._OriginalPaintIndex(paints)
            self.assertFalse(index.exact_raw)
            self.assertEqual(index.distance((1, 2, 3)), min(dist((1, 2, 3), p) for p in paints))
        self.assertTrue(isnan(interior._OriginalPaintIndex(((float('nan'), 0, 0),)).distance((0, 0, 0))))
        with self.assertRaises(ValueError):
            interior._OriginalPaintIndex(()).distance((0, 0, 0))

    def test_original_palette_is_not_changed_or_augmented_by_query(self):
        paints = ((10, 20, 30), (50, 60, 70), (100, 110, 120))
        before = deepcopy(paints)
        index = interior._OriginalPaintIndex(paints)
        root = deepcopy(index.root)
        index.distance((0, 0, 0))
        self.assertEqual(paints, before)
        self.assertEqual(index.root, root)
        self.assertEqual(index.paints, before)

    def test_lower_bound_prunes_work_without_approximating_distance(self):
        paints = tuple(product((0, 1, 127, 128, 254, 255), repeat=3))
        index = interior._OriginalPaintIndex(paints)
        with patch.object(interior, 'dist', wraps=dist) as measured:
            for rgb in paints:
                self.assertEqual(index.distance(rgb), 0.)
        self.assertLess(measured.call_count, len(paints)*len(paints)//4)

    def test_complete_paint_proof_and_existing_cache_values_are_unchanged(self):
        query = object.__new__(interior.SourceInteriorGlyphEvidence)
        query._paint_indices = {}
        paints = ((10, 20, 30), (50, 60, 70), (100, 110, 120))
        model = dict(original_paints=paints, paint_distance_cache={}, limit=12.)
        body = ((11, 21, 31), (50, 60, 70), (200, 210, 220))
        maximum = max(min(dist(rgb, p) for p in paints) for rgb in body)
        expected = dict(passed=maximum <= model['limit'], max_original_paint_distance=maximum,
                        original_RGB_limit=model['limit'], original_paint_count=len(paints),
                        every_interior_sample_source_supported=maximum <= model['limit'],
                        texture_placement_not_required=True)
        self.assertEqual(query._paint_support(model, body), expected)
        self.assertEqual(model['paint_distance_cache'], {rgb:min(dist(rgb, p) for p in paints) for rgb in body})
        self.assertEqual(query._paint_support(model, body[::-1]+body), expected)
        self.assertEqual(len(query._paint_indices), 1)

    def test_different_original_palettes_and_evidence_instances_stay_isolated(self):
        first = object.__new__(interior.SourceInteriorGlyphEvidence)
        second = object.__new__(interior.SourceInteriorGlyphEvidence)
        first._paint_indices, second._paint_indices = {}, {}
        for query, paints, value in ((first, ((0, 0, 0),), 0.),
                                     (first, ((2, 0, 0),), 2.), (second, ((3, 0, 0),), 3.)):
            model = dict(original_paints=paints, paint_distance_cache={}, limit=1.)
            self.assertEqual(query._paint_support(model, ((0, 0, 0),))['max_original_paint_distance'], value)
        self.assertEqual(len(first._paint_indices), 2)
        self.assertEqual(len(second._paint_indices), 1)
