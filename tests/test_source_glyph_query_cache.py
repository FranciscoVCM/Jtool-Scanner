"""Exact, image-local memoization; mutable evidence must not poison later queries."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from scripts.source_glyph_prototypes import SourceGlyphLibrary
from tests.test_source_glyph_prototypes import scene


class SourceGlyphQueryCacheTests(TestCase):
    def setUp(self):
        self.image, self.room, self.locators, self.queries, self.negatives = scene()
        self.library = SourceGlyphLibrary(self.image, self.room, self.locators)

    def test_repeated_query_measures_once_with_exact_evidence(self):
        key = self.queries[0]
        expected = self.library._measure_support(*key)
        with patch.object(self.library, '_measure_support', wraps=self.library._measure_support) as measure:
            first = self.library.support(*key)
            second = self.library.support(*key)
        self.assertEqual(measure.call_count, 1)
        self.assertEqual(first, expected)
        self.assertEqual(second, expected)
        self.assertIsNot(first, second)

    def test_nested_returned_proof_mutation_does_not_change_cache_or_models(self):
        key = self.queries[0]
        models = deepcopy(self.library.models)
        expected = self.library.support(*key)
        altered = self.library.support(*key)
        altered['passed'] = False
        altered['query_phase'][0] = 99
        altered['model']['original_source_witnesses'].clear()
        self.assertEqual(self.library.support(*key), expected)
        self.assertEqual(self.library.models, models)

    def test_size_direction_and_coordinates_have_distinct_entries(self):
        _, x, y = self.queries[0]
        keys = [(3,x,y), (4,x,y), (7,x,y), (3,x+16,y), (3,x,y+16)]
        with patch.object(self.library, '_measure_support', wraps=self.library._measure_support) as measure:
            for key in keys:
                expected = self.library._measure_support(*key)
                self.assertEqual(self.library.support(*key), expected)
                self.assertEqual(self.library.support(*key), expected)
        self.assertEqual(measure.call_count, 2*len(keys))
        self.assertEqual(len(self.library._support_results), len(keys))

    def test_negative_and_clipped_queries_are_cached_without_training(self):
        anchors, models = deepcopy(self.library.anchors), deepcopy(self.library.models)
        for key in self.negatives + [(7,-32,320)]:
            expected = self.library._measure_support(*key)
            self.assertFalse(expected['passed'])
            self.assertEqual(self.library.support(*key), expected)
            self.assertEqual(self.library.support(*key), expected)
        self.assertEqual(self.library.anchors, anchors)
        self.assertEqual(self.library.models, models)

    def test_cache_is_not_shared_between_source_instances(self):
        key = self.queries[0]
        self.library.support(*key)
        other = SourceGlyphLibrary(self.image, self.room, self.locators)
        self.assertEqual(other._support_results, {})
        with patch.object(other, '_measure_support', wraps=other._measure_support) as measure:
            self.assertEqual(other.support(*key), self.library.support(*key))
        self.assertEqual(measure.call_count, 1)

    def test_invalid_type_raises_without_creating_cache_entry(self):
        with self.assertRaises(ValueError):
            self.library.support(12,256,320)
        self.assertEqual(self.library._support_results, {})
