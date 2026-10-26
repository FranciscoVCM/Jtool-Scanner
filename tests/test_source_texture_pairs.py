"""Exact source-local work reuse, not a new texture recognition predicate."""
from copy import deepcopy
from itertools import combinations
from math import nextafter, sqrt
from unittest import TestCase

from scripts.source_interior_glyphs import SourceInteriorGlyphEvidence
from tests.test_source_directional_texture import query, textured_scene


class UncachedPairs(SourceInteriorGlyphEvidence):
    """The original per-comparison arithmetic, without the new memoization."""

    def _texture_compatible(self, first, second):
        return ((abs(first[1]-second[1]) >= 32 or abs(first[2]-second[2]) >= 32)
                and sum(a*b for a, b in zip(self._texture_vectors[first],
                                           self._texture_vectors[second])) >= .9)


def field(cls, vectors, cohorts):
    result = object.__new__(cls)
    result._texture_vectors = dict(vectors)
    result._texture_originals = frozenset(vectors)
    result._texture_models = {}
    result._texture_pairs = {}
    result._texture_eligibility = {}
    result._cohorts = cohorts
    result._texture_vector = vectors.get
    return result


class TexturePairReuseTests(TestCase):
    def test_exact_threshold_and_disjointness_include_negative_results(self):
        a, b, close = (3, 64, 64), (3, 96, 64), (3, 95, 64)
        for dot in (nextafter(.9, 0), .9, nextafter(.9, 1)):
            vectors = {a: (1., 0.), b: (dot, sqrt(1-dot*dot)), close: (1., 0.)}
            cached = field(SourceInteriorGlyphEvidence, vectors, [(a, b, close)])
            old = field(UncachedPairs, vectors, [(a, b, close)])
            for pair in ((a, b), (b, a), (a, close), (a, a)):
                self.assertIs(cached._texture_compatible(*pair), old._texture_compatible(*pair))
                self.assertIn(pair, cached._texture_pairs)
                self.assertIs(cached._texture_compatible(*pair), old._texture_compatible(*pair))
            self.assertEqual(len(cached._texture_pairs), 4)

    def test_each_ordered_original_pair_evaluated_at_most_once(self):
        class Vector(tuple):
            visits = 0

            def __iter__(self):
                self.visits += 1
                return super().__iter__()

        a, b, c = ((3, x, 64) for x in (64, 192, 320))
        vectors = {a: Vector((1., 0.)), b: Vector((1., 0.)), c: Vector((0., 1.))}
        cached = field(SourceInteriorGlyphEvidence, vectors, [(a, b, c)])
        for pair in ((a, b), (a, c), (b, a)):
            cached._texture_compatible(*pair)
        visits = sum(v.visits for v in vectors.values())
        for _ in range(20):
            for pair in ((a, b), (a, c), (b, a)):
                cached._texture_compatible(*pair)
        self.assertEqual(sum(v.visits for v in vectors.values()), visits)
        self.assertEqual(visits, 6)

    def test_all_pruned_teacher_subsets_retain_entire_greedy_models_and_proofs(self):
        for kind in (3, 4, 5, 6):
            keys = tuple((kind, x, y) for x, y in
                         ((64, 64), (80, 64), (128, 64), (256, 64),
                          (384, 64), (512, 64), (640, 64)))
            vectors = {k: ((1., 0., 0.) if i < 3 else (.96, .28, 0.)
                           if i < 6 else (0., 0., 1.)) for i, k in enumerate(keys)}
            cohorts = [keys, keys[1:]]
            cached = field(SourceInteriorGlyphEvidence, vectors, cohorts)
            old = field(UncachedPairs, vectors, cohorts)
            self.assertEqual(cached._has_directional_texture(kind), old._has_directional_texture(kind))
            for size in range(3, len(keys)+1):
                for subset in combinations(keys, size):
                    model = {'teachers': subset}
                    for target in (keys[0], keys[3], (kind, 64, 192)):
                        vectors[target] = vectors.get(target, (1., 0., 0.))
                        self.assertEqual(cached._directional_texture(target, model),
                                         old._directional_texture(target, model))
            self.assertEqual(cached._texture_models, old._texture_models)

    def test_pair_cache_is_not_a_teacher_or_cross_cohort_permission(self):
        a, b, c, d = ((3, x, 64) for x in (64, 192, 320, 448))
        vectors = {k: (1., 0.) for k in (a, b, c, d)}
        cached = field(SourceInteriorGlyphEvidence, vectors, [(a, b), (c, d)])
        for first in vectors:
            for second in vectors:
                cached._texture_compatible(first, second)
        self.assertFalse(cached._has_directional_texture(3))
        with self.assertRaises(ValueError):
            cached._directional_texture(a, {'teachers': (a, b, (3, 700, 64))})

    def test_frame_instances_do_not_share_even_identically_named_originals(self):
        a, b = (3, 64, 64), (3, 192, 64)
        first = field(SourceInteriorGlyphEvidence, {a: (1., 0.), b: (1., 0.)}, [(a, b)])
        second = field(SourceInteriorGlyphEvidence, {a: (1., 0.), b: (0., 1.)}, [(a, b)])
        self.assertTrue(first._texture_compatible(a, b))
        self.assertFalse(second._texture_compatible(a, b))
        self.assertIsNot(first._texture_pairs, second._texture_pairs)

    def test_known_original_vector_requirement_and_unknown_graph_are_unchanged(self):
        a, b, c = ((3, x, 64) for x in (64, 192, 320))
        cached = field(SourceInteriorGlyphEvidence, {a: (1., 0.), b: None, c: (1., 0.)}, [(a, b, c)])
        self.assertFalse(cached._has_directional_texture(3))
        self.assertNotIn((a, b), cached._texture_pairs)
        self.assertNotIn((b, c), cached._texture_pairs)

    def test_full_physical_source_proof_parity_across_directions_and_scales(self):
        for kind in range(4):
            for scale in (1, 1.25):
                with self.subTest(direction=kind, scale=scale):
                    values = textured_scene(rotation=kind, scale=scale)
                    cached = query(values)
                    uncached = UncachedPairs.__new__(UncachedPairs)
                    uncached.__dict__.update(deepcopy(cached.__dict__))
                    old = uncached.support(values[4])
                    self.assertTrue(old['passed'])
                    self.assertEqual(cached.support(values[4]), old)
                    changed = cached.support(values[4])
                    changed['passed'] = False
                    self.assertEqual(cached.support(values[4]), old)

    def test_current_query_texture_remains_separate_from_original_pair_cache(self):
        a, b, c, target = ((3, x, 64) for x in (64, 192, 320, 448))
        vectors = {k: (1., 0.) for k in (a, b, c)}
        cached = field(SourceInteriorGlyphEvidence, vectors, [(a, b, c)])
        cached._texture_vector = lambda key: (1., 0.) if key != target else (0., 1.)
        proof = cached._directional_texture(target, {'teachers': (a, b, c)})
        self.assertFalse(proof['passed'])
        self.assertTrue(proof['query_known'])
        self.assertTrue(cached._texture_pairs)
        self.assertFalse(any(target in pair for pair in cached._texture_pairs))
