"""Source-only automatic cohort discovery, original identities and explicit grid."""
from types import SimpleNamespace
import unittest
from unittest import mock
from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_sampling import SourceFrame
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_registered_rectangles import (
    original_background_glyphs, original_rgb_models, registered_rectangle_models,
)
from tests.test_source_rgb_distribution import scene, PARENTS, GLYPHS


def detections():
    return [SimpleNamespace(type_id=1, x=x, y=y) for x, y in PARENTS] + [
        SimpleNamespace(type_id=t, x=x, y=y) for t, x, y in GLYPHS]


def material():
    return dict(tip_votes={1: 3}, background_back_votes={0: 3},
        background_anchors=[dict(key=k, front_cluster=1, back_cluster=0) for k in GLYPHS])


class RegisteredRectangleTests(unittest.TestCase):
    def discover(self, frame, original=None, context=None, grid=(25, 19)):
        return registered_rectangle_models(frame.original_snapshot(), frame.room,
            detections() if original is None else original, source_grid=grid,
            source_frame=frame, source_context=context)

    def test_automatic_cohorts_and_backgrounds_corroborate_unprovided_query(self):
        frame = scene()
        models, proof = original_rgb_models(frame.original_snapshot(), frame.room,
            detections(), material(), source_grid=(25, 19), source_frame=frame)
        self.assertTrue(proof['models'])
        self.assertTrue(models)
        self.assertTrue(any(model.support(352, 160)['passed'] for model in models))
        for cohort in proof['models']:
            self.assertGreaterEqual(cohort['teacher_count'], 3)
            self.assertGreaterEqual(cohort['minimum_pairwise_RGB_correlation'], .9)
            self.assertGreaterEqual(sum(r['original_closed_seed'] for r in cohort['teachers']), 2)

    def test_no_original_fulls_and_nonstandard_grids_do_not_build_library(self):
        frame = scene()
        image = frame.original_snapshot()
        context = SourceEvidenceContext(image, frame.room, [])
        proof = registered_rectangle_models(image, frame.room, [], source_grid=(25, 19),
            source_frame=frame, source_context=context)
        self.assertFalse(proof['models'])
        self.assertEqual(context.statistics()['glyph_builds'], 0)
        for grid in ((19, 13), (9, 9), None):
            result = self.discover(frame, grid=grid)
            self.assertFalse(result['models'])
            self.assertIn('abstained', result)

    def test_duplicate_original_fulls_do_not_supply_three_source_frames(self):
        original = [SimpleNamespace(type_id=1, x=PARENTS[0][0], y=PARENTS[0][1])] * 3
        self.assertFalse(self.discover(scene(), original)['models'])

    def test_two_original_parent_regions_cannot_teach_a_third(self):
        original = [SimpleNamespace(type_id=1, x=x, y=y) for x, y in PARENTS[:2]]
        self.assertFalse(self.discover(scene(), original)['models'])

    def test_background_fronts_need_votes_and_original_membership(self):
        self.assertEqual(original_background_glyphs(detections(), material()), GLYPHS)
        weak = material()
        weak['tip_votes'] = {1: 2}
        self.assertFalse(original_background_glyphs(detections(), weak))
        forged = material()
        forged['background_anchors'].append(dict(key=(3, 400, 400), front_cluster=1))
        with self.assertRaisesRegex(ValueError, 'non-original'):
            original_background_glyphs(detections(), forged)

    def test_mismatched_frame_and_changed_context_source_are_rejected(self):
        frame = scene()
        wrong = RGBImage(800, 608, bytes(800 * 608 * 3))
        with self.assertRaisesRegex(ValueError, 'match original'):
            registered_rectangle_models(wrong, frame.room, detections(), source_grid=(25, 19), source_frame=frame)
        image = frame.original_snapshot()
        context = SourceEvidenceContext(image, frame.room, [])
        with self.assertRaisesRegex(ValueError, 'original locators changed'):
            registered_rectangle_models(image, frame.room, detections(), source_grid=(25, 19),
                source_frame=frame, source_context=context)

    def test_extended_world_abstains_without_sampling_padded_pixels(self):
        frame = scene()
        image = frame.original_snapshot()
        crop = Box(160, 0, 640, 608)
        extended = SourceFrame(image, crop, extent=Box(0, 0, 800, 608), canonical=image)
        result = self.discover(extended)
        self.assertFalse(result['models'])
        self.assertIn('abstained', result)

    def test_discovery_survives_palette_polarity_and_fractional_capture_scale(self):
        for palette in range(4):
            for scale in (1., 1.25, 1.5):
                with self.subTest(palette=palette, scale=scale):
                    self.assertTrue(self.discover(scene(palette, scale))['models'])

    def test_shared_context_reuse_preserves_original_inputs_and_proofs(self):
        frame = scene()
        image = frame.original_snapshot()
        original = detections()
        snapshot = [vars(d).copy() for d in original]
        context = SourceEvidenceContext(image, frame.room, GLYPHS)
        args = dict(source_grid=(25, 19), source_frame=frame, source_context=context)
        first = registered_rectangle_models(image, frame.room, original, **args)
        second = registered_rectangle_models(image, frame.room, original, **args)
        self.assertEqual(first, second)
        self.assertEqual([vars(d) for d in original], snapshot)
        self.assertEqual(context.statistics()['glyph_builds'], 1)

    def test_uncorrelated_three_sided_source_strip_skips_phase_contours(self):
        frame = scene()
        canvas = Image.frombytes('RGB', (800, 608), frame.original_snapshot().data)
        # A plausible three-sided source region, but no matching interior
        # artwork. It is not an original closed seed or another tile answer.
        ImageDraw.Draw(canvas).rectangle((512, 320, 543, 383), fill=(40, 50, 65))
        image = RGBImage(800, 608, canvas.tobytes())
        frame = SourceFrame(image, Box(0, 0, 800, 608))
        original = detections() + [SimpleNamespace(type_id=1, x=512, y=320)]
        context = SourceEvidenceContext(image, frame.room, GLYPHS)
        field = context.contours()
        rectangles, original_rectangle = [], field.rectangle

        def observed(x, y, size=32):
            rectangles.append((x, y))
            return original_rectangle(x, y, size)

        with mock.patch.object(field, 'rectangle', side_effect=observed):
            proof = registered_rectangle_models(image, frame.room, original, source_grid=(25, 19),
                source_frame=frame, source_context=context)
        self.assertTrue(proof['models'])
        # Nominal8px-grid work still occurs; this1px phase can be rejected
        # by its original RGB before geometry. No recognition gate is waived.
        self.assertIn((512, 320), rectangles)
        self.assertNotIn((511, 320), rectangles)


if __name__ == '__main__':
    unittest.main()
