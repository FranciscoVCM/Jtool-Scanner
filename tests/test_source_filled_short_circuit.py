"""Exact failed-candidate work avoidance, never fewer source hypotheses."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts.source_filled_pipeline import FilledGlyphEvidence, filled_hypotheses, recover_source_filled_glyphs
from tests.test_source_filled_pipeline import scene, TARGET


class SourceFilledShortCircuitTests(TestCase):
    def test_proven_slope_failure_skips_irrelevant_contours_not_diagnostics_api(self):
        frame, original = scene()
        query = (5, TARGET[1], TARGET[2]-8)
        evidence = FilledGlyphEvidence(frame, original)
        expected = FilledGlyphEvidence(frame, original).support(query)
        self.assertFalse(expected['passed'])
        self.assertIn('raw_base', expected['silhouette'])
        with patch.object(evidence.library.raw.raw, 'edge', wraps=evidence.library.raw.raw.edge) as edge:
            fast = evidence.support(query, short_circuit=True)
            self.assertFalse(fast['passed'])
            self.assertFalse(fast['unknown'])
            self.assertTrue(fast['silhouette']['diagnostics_deferred'])
            edge.assert_not_called()
            self.assertNotIn(query, evidence._results)
            self.assertNotIn(query, evidence.library.filled.cache)
            self.assertEqual(evidence.support(query), expected)
            self.assertGreater(edge.call_count, 0)
        self.assertEqual(evidence.support(query, short_circuit=True), expected)

    def test_positive_proofs_are_complete_and_independent_cold_or_warm(self):
        frame, original = scene()
        expected = FilledGlyphEvidence(frame, original).support(TARGET)
        evidence = FilledGlyphEvidence(frame, original)
        fast = evidence.support(TARGET, short_circuit=True)
        self.assertEqual(fast, expected)
        self.assertTrue(fast['passed'])
        self.assertIn('raw_base', fast['silhouette'])
        self.assertIn('competing_rectangle_faces', fast['silhouette'])
        fast['silhouette']['slopes'][0]['support'] = 0
        self.assertEqual(evidence.support(TARGET), expected)
        self.assertEqual(evidence.support(TARGET, short_circuit=True), expected)

    def test_detailed_failure_before_fast_retains_complete_cached_proof(self):
        frame, original = scene()
        query = (5, TARGET[1], TARGET[2]-8)
        evidence = FilledGlyphEvidence(frame, original)
        expected = evidence.support(query)
        self.assertEqual(evidence.support(query, short_circuit=True), expected)

    def test_rgb_polarity_dim_isoluminant_and_fractional_decisions_equal(self):
        for transform in (lambda c:c, lambda c:tuple(255-v for v in c),
                          lambda c:tuple(round(v*.25) for v in c)):
            for scale in (1, 1.25):
                frame, original = scene(background=(80,120,40), foreground=(150,80,65),
                                        transform=transform, scale=scale)
                detailed = FilledGlyphEvidence(frame, original)
                fast = FilledGlyphEvidence(frame, original)
                for kind in (3,4,5,6):
                    for dy in (-8,0,8):
                        key = (kind,TARGET[1],TARGET[2]+dy)
                        full, quick = detailed.support(key), fast.support(key,short_circuit=True)
                        self.assertEqual((full['passed'],full['unknown']),
                                         (quick['passed'],quick['unknown']))
                        if full['passed']:
                            self.assertEqual(quick,full)
                        self.assertEqual(fast.support(key),full)

    def test_unknown_cropped_footprints_remain_unknown_not_empty(self):
        frame, original = scene()
        evidence = FilledGlyphEvidence(frame,original)
        for key in ((3,0,0),(3,160,576),(4,-8,160)):
            full = evidence.support(key)
            quick = evidence.support(key,short_circuit=True)
            self.assertEqual(quick,full)
            self.assertTrue(quick['unknown'])
            self.assertFalse(quick['passed'])

    def test_complete_recovery_proof_equals_full_path_without_new_teachers(self):
        frame, original = scene()
        original.append(SimpleNamespace(type_id=3,x=216,y=288))
        snapshot = deepcopy(original)
        detailed = recover_source_filled_glyphs(frame,original,short_circuit=False)
        quick = recover_source_filled_glyphs(frame,original)
        self.assertEqual(quick,detailed)
        self.assertIn(TARGET,quick[0])
        self.assertEqual(original,snapshot)

    def test_every_original_hypothesis_is_still_queried(self):
        frame, original = scene()
        original.append(SimpleNamespace(type_id=3,x=216,y=288))
        expected = sorted(filled_hypotheses(original)-{(d.type_id,d.x,d.y) for d in original})
        calls = []
        actual = FilledGlyphEvidence.support
        def observed(evidence,key,**kwargs):
            calls.append((key,kwargs))
            return actual(evidence,key,**kwargs)
        with patch.object(FilledGlyphEvidence,'support',observed):
            _, proof = recover_source_filled_glyphs(frame,original)
        self.assertEqual([key for key,_ in calls],expected)
        self.assertTrue(all(kwargs=={'short_circuit':True} for _,kwargs in calls))
        self.assertEqual(proof['evaluated'],len(expected))

    def test_switch_is_strict_boolean_on_cold_and_warm_queries(self):
        frame, original = scene()
        evidence = FilledGlyphEvidence(frame,original)
        evidence.support(TARGET)
        for bad in (None,0,1,'true',[]):
            with self.assertRaisesRegex(ValueError,'boolean'):
                evidence.support(TARGET,short_circuit=bad)
            with self.assertRaisesRegex(ValueError,'boolean'):
                evidence.library.filled.evidence(*TARGET,short_circuit=bad)
            with self.assertRaisesRegex(ValueError,'boolean'):
                recover_source_filled_glyphs(frame,original,short_circuit=bad)
