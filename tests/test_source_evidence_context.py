"""Explicit source-local sharing preserves proof identity and teacher isolation."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_contours import SourceContours
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_glyph_prototypes import SourceGlyphLibrary
from scripts.source_terrain_agreement import agree_new_fulls
from tests.test_source_glyph_prototypes import scene


class SourceEvidenceContextTests(TestCase):
    def setUp(self):
        self.image, self.room, self.spikes, self.queries, self.negatives = scene()

    def test_lazy_library_reuse_with_complete_exact_proofs(self):
        context = SourceEvidenceContext(self.image, self.room, self.spikes)
        self.assertEqual(context.statistics()['glyph_builds'], 0)
        old = SourceGlyphLibrary(self.image, self.room, self.spikes)
        new = context.glyph_library(self.image, self.room, iter(self.spikes))
        self.assertIs(new, context.glyph_library(self.image, self.room, reversed(self.spikes)))
        self.assertEqual(new.anchors, old.anchors)
        self.assertEqual(new.models, old.models)
        self.assertEqual(new.pitch, old.pitch)
        for key in self.queries + self.negatives:
            self.assertEqual(new.support(*key), old.support(*key))
        self.assertEqual(context.statistics()['glyph_builds'], 1)
        self.assertEqual(context.statistics()['glyph_reuses'], 1)
        self.assertEqual(context.statistics()['pixel_cache_entries'], 0)
        self.assertEqual(context.statistics()['pixel_cache_limit'], 0)

    def test_geometry_and_appearance_share_the_same_source_contours(self):
        context = SourceEvidenceContext(self.image, self.room, self.spikes)
        field = context.contours()
        key = self.spikes[0]
        faces = field.triangle(*key)
        library = context.glyph_library(self.image, self.room, self.spikes)
        self.assertIs(library.raw.raw.field, field)
        self.assertEqual(faces, library.raw.raw.field.triangle(*key))
        self.assertIs(context.contours(), field)

    def test_pixel_lru_exact_values_eviction_and_bounded_storage(self):
        context = SourceEvidenceContext(self.image, self.room, self.spikes, pixel_cache_limit=2)
        library = context.glyph_library(self.image, self.room, self.spikes)
        library._pixel_results.clear()
        points = [(160.5, 160.5), (161.25, 161.75), (-2.75, 610.25), (160.5, 160.5)]
        with patch.object(library, '_measure_pixel', wraps=library._measure_pixel) as measure:
            for point in points:
                expected = library._measure_pixel(*point)
                self.assertEqual(library.pixel(*point), expected)
                self.assertEqual(library.pixel(*point), expected)
            self.assertEqual(measure.call_count, 8)
        self.assertEqual(context.statistics()['pixel_cache_entries'], 2)
        self.assertEqual(context.statistics()['pixel_cache_peak'], 2)
        self.assertGreater(context.statistics()['pixel_hits'], 0)

    def test_zero_limit_disables_pixel_memo_without_affecting_geometry(self):
        context = SourceEvidenceContext(self.image, self.room, self.spikes, pixel_cache_limit=0)
        library = context.glyph_library(self.image, self.room, self.spikes)
        for key in self.queries:
            self.assertTrue(library.support(*key)['passed'])
        self.assertEqual(context.statistics()['pixel_cache_entries'], 0)
        self.assertEqual(context.statistics()['pixel_hits'], 0)

    def test_teacher_snapshot_cannot_be_extended_with_new_proposals(self):
        spikes = list(self.spikes)
        context = SourceEvidenceContext(self.image, self.room, spikes)
        spikes.append(self.queries[0])
        with self.assertRaisesRegex(ValueError, 'locators changed'):
            context.glyph_library(self.image, self.room, spikes)
        library = context.glyph_library(self.image, self.room, self.spikes)
        anchors = deepcopy(library.anchors)
        library.support(*self.queries[0])
        self.assertEqual(library.anchors, anchors)

    def test_other_source_same_bytes_and_changed_crop_are_rejected(self):
        context = SourceEvidenceContext(self.image, self.room, self.spikes)
        other = RGBImage(self.image.width, self.image.height, self.image.data)
        with self.assertRaisesRegex(ValueError, 'image/data/room changed'):
            context.glyph_library(other, self.room, self.spikes)
        with self.assertRaisesRegex(ValueError, 'image/data/room changed'):
            context.glyph_library(self.image, Box(0, 0, 768, 608), self.spikes)

    def test_changed_original_rgbimage_rejected_and_snapshot_not_poisoned(self):
        context = SourceEvidenceContext(self.image, self.room, self.spikes)
        library = context.glyph_library(self.image, self.room, self.spikes)
        key = self.queries[0]
        before = library.support(*key)
        original_bytes = self.image.data
        self.image.data = bytes(len(original_bytes))
        with self.assertRaisesRegex(ValueError, 'image/data/room changed'):
            context.glyph_library(self.image, self.room, self.spikes)
        self.assertEqual(library.support(*key), before)
        self.assertIs(library.raw.image.data, original_bytes)

    def test_separate_contexts_do_not_share_proofs_or_models(self):
        contexts = [SourceEvidenceContext(self.image, self.room, self.spikes) for _ in range(2)]
        first, second = [c.glyph_library(self.image, self.room, self.spikes) for c in contexts]
        self.assertIsNot(first, second)
        self.assertIsNot(first.raw.raw.field, second.raw.raw.field)
        proof = first.support(*self.queries[0])
        proof['model']['original_source_witnesses'].clear()
        self.assertEqual(second.support(*self.queries[0]), first.support(*self.queries[0]))

    def test_mismatched_contour_native_frame_or_source_rejected(self):
        for field in (SourceContours(self.image, self.room, (400, 304)),
                      SourceContours(RGBImage(800, 608, self.image.data), self.room)):
            with self.assertRaisesRegex(ValueError, 'Shared contours'):
                SourceGlyphLibrary(self.image, self.room, self.spikes, contour_field=field)

    def test_bad_buffers_limits_and_locators_rejected(self):
        for limit in (-1, True, 3.5):
            with self.assertRaises(ValueError):
                SourceEvidenceContext(self.image, self.room, self.spikes, pixel_cache_limit=limit)
            with self.assertRaises(ValueError):
                SourceGlyphLibrary(self.image, self.room, self.spikes, pixel_cache_limit=limit)
        for data in (self.image.data[:-1], bytearray(self.image.data)):
            with self.assertRaisesRegex(ValueError, 'immutable RGB'):
                SourceEvidenceContext(RGBImage(800, 608, data), self.room, self.spikes)
        for spikes in ([(12, 32, 32)], [(3, 32)]):
            with self.assertRaises(ValueError):
                SourceEvidenceContext(self.image, self.room, spikes)

    def test_agreement_validates_context_even_when_no_library_needed(self):
        context = SourceEvidenceContext(self.image, self.room, self.spikes)
        detections = [SimpleNamespace(type_id=t, x=x, y=y) for t, x, y in self.spikes]
        output, proof = agree_new_fulls(self.image, self.room, detections, set(), set(), set(), source_context=context)
        self.assertEqual(output, set())
        self.assertEqual(context.statistics()['glyph_builds'], 0)
        detections.append(SimpleNamespace(type_id=7, x=672, y=320))
        with self.assertRaisesRegex(ValueError, 'locators changed'):
            agree_new_fulls(self.image, self.room, detections, set(), set(), set(), source_context=context)

    def test_portable_context64_positive_and64_negative_proofs(self):
        for size in (16, 32):
            for palette in range(4):
                for scale in (1., 1.25):
                    with self.subTest(size=size, palette=palette, scale=scale):
                        image, room, spikes, positive, negative = scene(size, palette, scale)
                        context = SourceEvidenceContext(image, room, spikes)
                        shared = context.glyph_library(image, room, spikes)
                        standalone = SourceGlyphLibrary(image, room, spikes)
                        self.assertEqual(shared.anchors, standalone.anchors)
                        self.assertEqual(shared.models, standalone.models)
                        for key in positive + negative:
                            self.assertEqual(shared.support(*key), standalone.support(*key))
                        self.assertTrue(all(shared.support(*key)['passed'] for key in positive))
                        self.assertFalse(any(shared.support(*key)['passed'] for key in negative))
