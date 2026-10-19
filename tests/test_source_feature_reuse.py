"""Scoped source FEATURES: exact arithmetic, bounds, exceptions and isolation."""
from contextlib import contextmanager
from copy import deepcopy
import unittest
from unittest.mock import patch

from scripts import source_rgb_distribution as rgb
from scripts.source_glyph_prototypes import SourceGlyphLibrary
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_registered_rectangles import registered_rectangle_models
from tests.test_source_rgb_distribution import scene, PARENTS, GLYPHS
from tests.test_source_registered_rectangles import detections


def state(library):
    return (library._pixel_cache_limit, library._pixel_results, library.pixel_cache_hits,
            library.pixel_cache_misses, library.pixel_cache_peak)


class SourceFeatureReuseTests(unittest.TestCase):
    def test_scoped_pixels_keep_exact_rgb_fractional_clamp_and_unknown_values(self):
        points = [(64.5,160.5),(65.25,161.75),(352.125,169.625),(-2.75,610.25)]
        for palette in range(4):
            frame = scene(palette,1.25)
            image = frame.original_snapshot()
            for framed in (None,frame):
                library = SourceGlyphLibrary(image,frame.room,(),source_frame=framed)
                original = state(library)
                expected = [library.pixel(*p) for p in points]
                with library.scoped_pixel_cache(3):
                    for p,value in zip(points,expected):
                        self.assertEqual(library.pixel(*p),value)
                        self.assertEqual(library.pixel(*p),value)
                    self.assertLessEqual(len(library._pixel_results),3)
                    self.assertEqual(library.pixel_cache_peak,3)
                    self.assertGreater(library.pixel_cache_hits,0)
                self.assertEqual(state(library),original)
                self.assertIs(library._pixel_results,original[1])
                self.assertEqual(library._pixel_cache_limit,0)

    def test_nested_scopes_and_exceptions_restore_original_cache_and_counters(self):
        frame = scene()
        library = SourceGlyphLibrary(frame.original_snapshot(),frame.room,(),pixel_cache_limit=2)
        library.pixel(64.5,160.5)
        original = state(library)
        original_entries = dict(original[1])
        with self.assertRaisesRegex(RuntimeError,'outer'):
            with library.scoped_pixel_cache(3):
                library.pixel(72.5,160.5)
                outer = state(library)
                with self.assertRaisesRegex(RuntimeError,'inner'):
                    with library.scoped_pixel_cache(1):
                        library.pixel(80.5,160.5)
                        raise RuntimeError('inner')
                self.assertEqual(state(library),outer)
                self.assertIs(library._pixel_results,outer[1])
                raise RuntimeError('outer')
        self.assertEqual(state(library),original)
        self.assertIs(library._pixel_results,original[1])
        self.assertEqual(dict(library._pixel_results),original_entries)

    def test_invalid_scope_limits_leave_source_state_untouched(self):
        frame = scene()
        library = SourceGlyphLibrary(frame.original_snapshot(),frame.room,())
        original = state(library)
        for limit in (-1,True,1.5,None):
            with self.subTest(limit=limit), self.assertRaisesRegex(ValueError,'nonnegative integer'):
                with library.scoped_pixel_cache(limit):
                    self.fail('Invalid scope entered')
            self.assertEqual(state(library),original)

    def test_failed_registered_factory_restores_shared_context_state(self):
        frame = scene()
        image = frame.original_snapshot()
        original = detections()
        snapshot = deepcopy(original)
        context = SourceEvidenceContext(image,frame.room,GLYPHS)
        library = context.glyph_library(image,frame.room,GLYPHS)
        before = state(library)
        with patch.object(context.contours(),'rectangle',side_effect=RuntimeError('producer')):
            with self.assertRaisesRegex(RuntimeError,'producer'):
                registered_rectangle_models(image,frame.room,original,source_grid=(25,19),
                    source_frame=frame,source_context=context)
        self.assertEqual(state(library),before)
        self.assertIs(library._pixel_results,before[1])
        self.assertEqual(original,snapshot)

    def test_registered_proofs_equal_when_scoped_memo_is_explicitly_bypassed(self):
        @contextmanager
        def bypass(library,limit):
            yield library
        for palette in (0,2):
            frame = scene(palette,1.25)
            image = frame.original_snapshot()
            args = dict(source_grid=(25,19),source_frame=frame)
            with patch.object(SourceGlyphLibrary,'scoped_pixel_cache',bypass):
                expected = registered_rectangle_models(image,frame.room,detections(),**args)
            actual = registered_rectangle_models(image,frame.room,detections(),**args)
            self.assertEqual(actual,expected)

    def test_shared_colour_distances_preserve_all_minima_and_compute_each_once(self):
        frame = scene()
        model = rgb.SourceRGBDistribution(frame,PARENTS,GLYPHS)
        witnesses = model.parents,model.background
        colors = {color for group in witnesses for row in group for color in row.palette}
        queries = [(0,0,0),(255,255,255),(31,75,129),(128,127,126)]
        expected = [tuple(tuple(min(rgb._distance2(query,c) for c in row.palette)
            for row in group) for group in witnesses) for query in queries]
        with patch.object(rgb,'_distance2',wraps=rgb._distance2) as distances:
            for query,value in zip(queries,expected):
                self.assertEqual(model._rgb_distances(query),value)
                self.assertEqual(model._rgb_distances(query),value)
            self.assertEqual(distances.call_count,len(colors)*len(queries))
        self.assertEqual((model.parents,model.background),witnesses)

    def test_source_palettes_and_pixel_scopes_do_not_share_between_sources(self):
        models = [rgb.SourceRGBDistribution(scene(p),PARENTS,GLYPHS) for p in (0,1)]
        for model in models:
            value = model._rgb_distances((40,50,65))
            expected = tuple(tuple(min(rgb._distance2((40,50,65),c) for c in row.palette)
                for row in group) for group in (model.parents,model.background))
            self.assertEqual(value,expected)
        self.assertIsNot(models[0]._distances,models[1]._distances)
        self.assertIsNot(models[0]._palette_colors,models[1]._palette_colors)


if __name__ == '__main__':
    unittest.main()
