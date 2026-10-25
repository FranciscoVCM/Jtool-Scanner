"""Actual optional final consumer: original provenance, no new-output teachers."""
from contextlib import ExitStack
from copy import deepcopy
import unittest
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from scripts.source_deferred_platforms import original_platform_vetoes
from scripts.source_registered_rectangles import original_rgb_models
from scripts.source_sampling import SourceFrame
from tests.test_source_rgb_distribution import scene, PARENTS, GLYPHS
from tests.test_source_registered_rectangles import material
from tests.source_geometry_stubs import record_requested_original_filled_source


def det(t, x, y):
    return scanner.Detection('original', t, x, y, .67, Box(x, y, 32, 32))


def recorded_proposals(response):
    """Keep the stub's original field separate from its returned proposals."""
    def produce(image, room, original, **options):
        record_requested_original_filled_source(original, options)
        return response
    return produce


class DeferredSourceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.frame = scene()
        self.image = self.frame.original_snapshot()
        self.original = [det(1, *p) for p in PARENTS] + [det(*p) for p in GLYPHS]
        self.block, self.platform = det(1, 352, 160), det(13, 352, 160)
        self.vetoes = original_platform_vetoes([self.block, self.platform])

    def result(self, extra=()):
        return scanner.ScanResult(800, 608, self.frame.room, self.original+list(extra),
            source_grid=(25, 19), infinite_jump=1, recognized_text='original text')

    def test_default_consumer_off_and_no_model_or_extra_context(self):
        self.assertIs(scanner._SOURCE_DEFERRED_PLATFORMS_ENABLED, False)
        result = self.result()
        before = deepcopy(result)
        # Isolate the disabled deferred consumer, not the enabled phase caller.
        with patch.object(scanner, '_SOURCE_FULL_SPIKE_PHASE_ENABLED', False), \
             patch('scripts.source_geometry_pipeline.source_proposals',
                   return_value=(set(), set(), {})) as proposals, \
             patch('scripts.source_registered_rectangles.original_rgb_models',
                   side_effect=AssertionError('Disabled path must not discover models')):
            out = scanner._apply_source_geometry(result, self.image)
        self.assertIs(out, result)
        self.assertEqual(out.detections, before.detections)
        self.assertNotIn('source_context', proposals.call_args.kwargs)

    def test_real_factory_receives_original_tuple_and_shared_source_context(self):
        result = self.result()
        original = tuple(result.detections)
        proposed = (2, 416, 320)
        response = ({proposed}, set(), {'source_material':material()})
        with patch('scripts.source_geometry_pipeline.source_proposals',
                   return_value=response, side_effect=recorded_proposals(response)) as proposals, \
             patch('scripts.source_registered_rectangles.original_rgb_models',
                   wraps=original_rgb_models) as factory:
            out = scanner._apply_source_geometry(result, self.image, platform_vetoes=self.vetoes)
        factory.assert_called_once()
        self.assertEqual(factory.call_args.args[:3], (self.image, self.frame.room, original))
        self.assertIs(factory.call_args.kwargs['source_context'], proposals.call_args.kwargs['source_context'])
        self.assertIs(factory.call_args.kwargs['source_frame'], proposals.call_args.kwargs['source_frame'])
        context=proposals.call_args.kwargs['source_context']
        self.assertIs(context.filled_source(original,proposals.call_args.kwargs['source_frame']).frame,
            factory.call_args.kwargs['source_frame'])
        self.assertIs(factory.call_args.args[3], proposals.return_value[2]['source_material'])
        self.assertTrue(any(d is self.block for d in out.detections))
        self.assertTrue(all(any(d is old for d in out.detections) for old in original))
        self.assertNotIn(proposed, [(d.type_id,d.x,d.y) for d in factory.call_args.args[2]])
        self.assertIn(proposed, [(d.type_id,d.x,d.y) for d in out.detections])
        self.assertEqual(out.recognized_text, 'original text')
        self.assertEqual(out.infinite_jump, 1)

    def test_source_retired_candidate_never_becomes_a_new_teacher(self):
        result = self.result()
        original = tuple(result.detections)
        retired = (1, *PARENTS[0])
        response = (set(), {retired}, {'source_material':material()})
        with patch('scripts.source_geometry_pipeline.source_proposals',
                   side_effect=recorded_proposals(response)), \
             patch('scripts.source_registered_rectangles.original_rgb_models',
                   wraps=original_rgb_models) as factory:
            out = scanner._apply_source_geometry(result, self.image, platform_vetoes=self.vetoes)
        self.assertEqual(factory.call_args.args[2], original)
        self.assertTrue(any(d is self.block for d in out.detections))
        self.assertNotIn(retired, [(d.type_id,d.x,d.y) for d in out.detections])

    def test_surviving_platform_is_still_authoritative(self):
        result = self.result([self.platform])
        before = tuple(result.detections)
        with patch('scripts.source_geometry_pipeline.source_proposals',
                   side_effect=recorded_proposals((set(), set(), {'source_material':material()}))):
            out = scanner._apply_source_geometry(result, self.image, platform_vetoes=self.vetoes)
        self.assertEqual(tuple(out.detections), before)
        self.assertFalse(any(d is self.block for d in out.detections))

    def test_original_save_or_empty_ledger_does_not_build_a_model(self):
        mixed = original_platform_vetoes([self.block, self.platform, det(12, 352, 160)])
        for vetoes in ((), mixed):
            with self.subTest(vetoes=vetoes), \
                 patch.object(scanner, '_SOURCE_FULL_SPIKE_PHASE_ENABLED', False), \
                 patch('scripts.source_geometry_pipeline.source_proposals',
                       return_value=(set(), set(), {})) as proposals, \
                 patch('scripts.source_registered_rectangles.original_rgb_models',
                       side_effect=AssertionError('No platform-only original veto')):
                scanner._apply_source_geometry(self.result(), self.image, platform_vetoes=vetoes)
            self.assertNotIn('source_context', proposals.call_args.kwargs)

    def test_extended_world_does_not_borrow_original_ledger(self):
        frame = SourceFrame(self.image, self.frame.room, extent=Box(-8, 0, 816, 608), canonical=self.image)
        with patch('scripts.source_geometry_pipeline.source_proposals',
                   return_value=(set(), set(), {})) as proposals, \
             patch('scripts.source_registered_rectangles.original_rgb_models',
                   side_effect=AssertionError('Extended frame must bypass')):
            scanner._apply_source_geometry(self.result(), self.image, source_frame=frame,
                platform_vetoes=self.vetoes)
        self.assertNotIn('source_context', proposals.call_args.kwargs)

    def test_compact_frame_never_enters_original_source_factory(self):
        result = self.result()
        result.source_grid = (19, 13)
        with patch('scripts.source_geometry_pipeline.source_proposals',
                   side_effect=AssertionError('Compact original source is unqualified')):
            scanner._apply_source_geometry(result, self.image, platform_vetoes=self.vetoes)

    def test_actual_scan_collects_once_before_first_anchor_veto(self):
        image = scanner.RGBImage(800, 608, bytes(800*608*3))
        with patch.object(scanner, '_SOURCE_DEFERRED_PLATFORMS_ENABLED', True), \
             patch.object(scanner, '_detect_geometry', return_value=[self.block]), \
             patch.object(scanner, '_detect_platforms', return_value=[self.platform]), \
             patch('scripts.source_deferred_platforms.original_platform_vetoes',
                   wraps=original_platform_vetoes) as ledger, \
             patch.object(scanner, '_apply_source_geometry', side_effect=lambda r,i,**k:r) as final:
            scanner.scan_image(image, room_box=Box(0,0,800,608), source_grid=(25,19),
                include_geometry=True, source_geometry=True)
        ledger.assert_called_once()
        final.assert_called_once()
        self.assertIs(final.call_args.args[1], image)
        vetoes = final.call_args.kwargs['platform_vetoes']
        self.assertEqual(vetoes, self.vetoes)
        self.assertIs(vetoes[0].detection, self.block)

    def test_actual_normal_inner_and_compact_scans_do_not_collect_original_ledger(self):
        image = scanner.RGBImage(800, 608, bytes(800*608*3))
        for options in ({'source_geometry':False},
                        {'source_geometry':True,'_apply_shape_refits':False},
                        {'source_geometry':True,'source_grid':(19,13)}):
            with self.subTest(options=options), ExitStack() as stack:
                stack.enter_context(patch.object(scanner, '_SOURCE_DEFERRED_PLATFORMS_ENABLED', True))
                stack.enter_context(patch('scripts.source_deferred_platforms.original_platform_vetoes',
                    side_effect=AssertionError('Not a qualified original source pass')))
                final = stack.enter_context(patch.object(scanner, '_apply_source_geometry',
                    side_effect=lambda r,i,**k:r))
                scanner.scan_image(image, room_box=Box(0,0,800,608), include_geometry=True,
                    **{'source_grid':(25,19), **options})
                self.assertTrue(all('platform_vetoes' not in c.kwargs for c in final.call_args_list))


if __name__ == '__main__':
    unittest.main()
