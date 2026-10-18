"""Optional source-edge recovery preserves defaults, originals and provenance."""
from copy import deepcopy
import ast
import inspect
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts import source_filled_pipeline as filled
from scripts.source_geometry_pipeline import source_proposals
from tests.test_source_capture_base import TARGETS, edge_scene
from tests import test_source_geometry_pipeline as pipeline_fixtures


class CaptureBaseRecoveryIntegrationTests(TestCase):
    def test_default_and_explicit_bypass_have_identical_full_proofs(self):
        frame, original = edge_scene(TARGETS[0])
        with patch('scripts.source_capture_base.CaptureBaseEvidence',
                   side_effect=AssertionError('Disabled path must not build new evidence')):
            default = filled.recover_source_filled_glyphs(frame, original)
            bypass = filled.recover_source_filled_glyphs(frame, original, capture_base=False)
        self.assertEqual(default, bypass)
        self.assertNotIn(TARGETS[0], default[0])

    def test_opt_in_recovers_source_edge_with_one_original_evidence_instance(self):
        frame, original = edge_scene(TARGETS[0])
        before = deepcopy(original)
        actual = filled.FilledGlyphEvidence
        with patch.object(filled, 'FilledGlyphEvidence', wraps=actual) as constructor:
            proposed, diagnostic = filled.recover_source_filled_glyphs(
                frame, original, capture_base=True)
        self.assertEqual(constructor.call_count, 1)
        self.assertEqual(proposed, {TARGETS[0]})
        proof = next(p['evidence'] for p in diagnostic['accepted'] if p['key'] == TARGETS[0])
        self.assertTrue(proof['complete_physical_body_source'])
        self.assertTrue(proof['capture_base_context_censored'])
        self.assertFalse(proof['complete_physical_source'])
        self.assertEqual(original, before)
        self.assertTrue(diagnostic['no_existing_object_retirement'])

    def test_strict_boolean_before_source_model_work(self):
        frame, original = edge_scene(TARGETS[0])
        with patch.object(filled, 'FilledGlyphEvidence', side_effect=AssertionError('No construction')):
            for value in (None, 0, 1, 'true', []):
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'boolean'):
                    filled.recover_source_filled_glyphs(frame, original, capture_base=value)

    def test_no_original_qualified_model_does_not_expand_the_search(self):
        frame, original = edge_scene(TARGETS[0])
        with patch('scripts.source_capture_base.capture_base_hypotheses',
                   side_effect=AssertionError('No identity without original witnesses')):
            proposed, proof = filled.recover_source_filled_glyphs(frame, original[:1], capture_base=True)
        self.assertEqual(proposed, set())
        self.assertEqual(proof['evaluated'], 0)


class CaptureBasePipelineRoutingTests(TestCase):
    def setUp(self):
        # Reuse a portable neutral pipeline fixture, not a real-room answer.
        fixture = pipeline_fixtures.SourceGeometryPipelineTests()
        fixture.setUp()
        self.image, self.room, self.detections = fixture.image, fixture.room, fixture.detections

    def test_capture_flag_requires_boolean(self):
        for value in (None, 0, 1, 'true', []):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'boolean'):
                source_proposals(self.image, self.room, self.detections,
                                 include_filled_glyphs=True, include_filled_capture_base=value)

    def test_capture_flag_requires_filled_recovery(self):
        with self.assertRaisesRegex(ValueError, 'requires filled'):
            source_proposals(self.image, self.room, self.detections, include_filled_capture_base=True)

    def test_default_does_not_forward_the_new_keyword(self):
        with patch('scripts.source_geometry_pipeline.recover_source_filled_glyphs',
                   return_value=(set(), {'accepted': []})) as recovery:
            default = source_proposals(self.image, self.room, self.detections, include_filled_glyphs=True)
            bypass = source_proposals(self.image, self.room, self.detections,
                                      include_filled_glyphs=True, include_filled_capture_base=False)
        self.assertEqual(default, bypass)
        self.assertTrue(all('capture_base' not in call.kwargs for call in recovery.call_args_list))

    def test_opt_in_forwards_same_original_library_and_immutable_detections(self):
        before = deepcopy(self.detections)
        key = (3, 224, 576)
        proof = {'accepted': [{'key': key, 'capture_base_context_censored': True}]}
        with patch('scripts.source_geometry_pipeline.recover_source_filled_glyphs',
                   return_value=({key}, proof)) as recovery:
            proposed, _, diagnostic = source_proposals(
                self.image, self.room, iter(self.detections),
                include_filled_glyphs=True, include_filled_capture_base=True)
        self.assertIs(recovery.call_args.kwargs['capture_base'], True)
        self.assertEqual(recovery.call_args.args[1], tuple(before))
        frame = recovery.call_args.args[0]
        self.assertTrue(frame.matches_source(recovery.call_args.kwargs['source_library'].raw.image, self.room))
        self.assertIn(key, proposed)
        self.assertEqual(diagnostic['source_filled'], proof)
        self.assertEqual(self.detections, before)

    def test_actual_scanner_consumer_enabled_and_only_final_source_call(self):
        self.assertIs(scanner._CAPTURE_BASE_CONTEXT_ENABLED, True)
        tree = ast.parse(inspect.getsource(scanner._apply_source_geometry))
        call = next(n for n in ast.walk(tree) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == 'source_proposals')
        expansion = next(k.value for k in call.keywords if k.arg is None)
        self.assertIsInstance(expansion, ast.IfExp)
        self.assertEqual(expansion.test.id, '_CAPTURE_BASE_CONTEXT_ENABLED')
        self.assertEqual([k.value for k in expansion.body.keys], ['include_filled_capture_base'])
        self.assertEqual([v.value for v in expansion.body.values], [True])
        self.assertEqual(expansion.orelse.keys, [])

    def test_actual_final_call_routes_enabled_and_explicit_bypass(self):
        image = RGBImage(800, 608, bytes(800*608*3))
        for enabled in (True, False):
            with self.subTest(enabled=enabled), \
                 patch.object(scanner, '_CAPTURE_BASE_CONTEXT_ENABLED', enabled), \
                 patch('scripts.source_geometry_pipeline.source_proposals',
                       return_value=(set(), set(), {})) as proposal:
                result = scanner.ScanResult(800, 608, Box(0, 0, 800, 608), [],
                                            source_grid=(25, 19))
                scanner._apply_source_geometry(result, image)
            proposal.assert_called_once()
            if enabled:
                self.assertIs(proposal.call_args.kwargs['include_filled_capture_base'], True)
            else:
                self.assertNotIn('include_filled_capture_base', proposal.call_args.kwargs)
            self.assertEqual(result.detections, [])
