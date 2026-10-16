"""Joint physical-phase plumbing plus real RGB/crop/teacher protections."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from scripts.source_filled_pipeline import FilledGlyphEvidence, recover_source_filled_glyphs
from tests.test_source_filled_pipeline import scene, TARGET


class SourceFilledJointPhaseTests(TestCase):
    def weak_base(self, evidence):
        # Isolate phase arbitration with a controlled contour failure. The
        # appearance models, original teachers and RGB samples remain real.
        proof = evidence.support(TARGET)
        self.assertTrue(proof['passed'])
        weak = deepcopy(proof)
        weak['passed'] = False
        weak['silhouette']['passed'] = False
        weak['silhouette']['raw_base'] = (8, False)
        return weak, deepcopy(proof['silhouette'])

    def test_nominal_positives_are_verbatim_and_do_not_use_fallback(self):
        for transform in (lambda c:c, lambda c:tuple(255-v for v in c),
                          lambda c:tuple(round(v*.25) for v in c), lambda c:(c[2],c[0],c[1])):
            for scale in (.8,1,1.25):
                frame, original = scene(scale=scale, transform=transform)
                evidence = FilledGlyphEvidence(frame, original)
                before = deepcopy(evidence.library.models), deepcopy(evidence.library.anchors)
                expected = evidence.support(TARGET)
                self.assertTrue(expected['passed'])
                self.assertEqual(evidence.support_joint_phase(TARGET), expected)
                self.assertEqual(evidence._joint_results, {})
                self.assertEqual((evidence.library.models,evidence.library.anchors),before)

    def test_known_weak_base_requires_entire_same_phase_positive(self):
        frame, original = scene(scale=1.25)
        evidence = FilledGlyphEvidence(frame, original)
        weak, positive = self.weak_base(evidence)
        models, anchors = deepcopy(evidence.library.models), deepcopy(evidence.library.anchors)
        phase = (-frame.pitch[0], 0)
        calls = []
        def contour(kind,x,y,**kwargs):
            calls.append((x-TARGET[1],y-TARGET[2]))
            return deepcopy(positive) if (x,y)==(TARGET[1]+phase[0],TARGET[2]) else deepcopy(weak['silhouette'])
        with patch.object(evidence,'support',return_value=weak), patch.object(evidence.library.filled,'evidence',side_effect=contour):
            result = evidence.support_joint_phase(TARGET)
            self.assertTrue(result['passed'])
            self.assertEqual(result['joint_source_phase'],list(phase))
            self.assertEqual(result['appearance']['query_phase'],list(phase))
            self.assertTrue(result['same_phase_geometry_and_RGB'])
            self.assertEqual(result['nominal_failure'],weak)
            self.assertGreaterEqual(len(result['independent_filled_teachers']),3)
            self.assertTrue(all(abs(dx)<=frame.pitch[0]+1e-9 and abs(dy)<=frame.pitch[1]+1e-9 for dx,dy in calls))
            result['silhouette']['raw_base'] = (0,True)
            self.assertTrue(evidence.support_joint_phase(TARGET)['passed'])
            self.assertNotEqual(evidence.support_joint_phase(TARGET)['silhouette']['raw_base'],(0,True))
        self.assertEqual(evidence.library.models,models)
        self.assertEqual(evidence.library.anchors,anchors)

    def test_geometry_and_appearance_from_different_phases_cannot_combine(self):
        frame, original = scene()
        evidence = FilledGlyphEvidence(frame, original)
        weak, positive = self.weak_base(evidence)
        actual_signature = evidence.library.signature
        geometry_phase = (TARGET[1]-frame.pitch[0],TARGET[2])
        def contour(kind,x,y,**kwargs):
            return deepcopy(positive) if (x,y)==geometry_phase else deepcopy(weak['silhouette'])
        def signature(kind,x,y):
            # Appearance matches elsewhere, but NEVER at the passing geometry.
            return (0.,)*768 if (x,y)==geometry_phase else actual_signature(kind,x,y)
        appearance = deepcopy(weak['appearance'])
        with patch.object(evidence,'support',return_value=weak), \
             patch.object(evidence.library,'support',return_value=appearance), \
             patch.object(evidence.library.filled,'evidence',side_effect=contour), \
             patch.object(evidence.library,'signature',side_effect=signature):
            self.assertEqual(evidence.support_joint_phase(TARGET),weak)
        self.assertEqual(evidence._joint_results,{})

    def test_failed_slope_unknown_base_closed_rectangle_never_search(self):
        frame, original = scene()
        evidence = FilledGlyphEvidence(frame, original)
        weak, _ = self.weak_base(evidence)
        failures = []
        value=deepcopy(weak);value['silhouette']['slopes'][0]['support']=8;failures.append(value)
        value=deepcopy(weak);value['silhouette']['slopes'][0]['unknown']=True;failures.append(value)
        value=deepcopy(weak);value['silhouette']['raw_base']=(8,True);failures.append(value)
        value=deepcopy(weak);value['silhouette']['raw_base']=(9,False);failures.append(value)
        value=deepcopy(weak);value['silhouette']['competing_rectangle_faces']=[9]*4;failures.append(value)
        value=deepcopy(weak);value['unknown']=True;failures.append(value)
        for failure in failures:
            with patch.object(evidence,'support',return_value=failure), patch.object(evidence.library,'support') as appearance:
                self.assertEqual(evidence.support_joint_phase(TARGET),failure)
                appearance.assert_not_called()

    def test_no_matching_original_appearance_or_teachers_cannot_search(self):
        frame, original = scene()
        evidence = FilledGlyphEvidence(frame, original)
        weak, _ = self.weak_base(evidence)
        for appearance,teachers in (({'passed':False},()),(weak['appearance'],())):
            with patch.object(evidence,'support',return_value=weak), \
                 patch.object(evidence.library,'support',return_value=appearance), \
                 patch.object(evidence,'_teachers',return_value=teachers), \
                 patch.object(evidence.library.filled,'evidence') as geometry:
                self.assertEqual(evidence.support_joint_phase(TARGET),weak)
                geometry.assert_not_called()

    def test_unknown_crop_and_wrong_direction_remain_negative(self):
        frame, original = scene()
        evidence = FilledGlyphEvidence(frame,original)
        for key in ((3,0,0),(3,160,576),(4,-8,160)):
            nominal=evidence.support(key)
            self.assertTrue(nominal['unknown'])
            self.assertEqual(evidence.support_joint_phase(key),nominal)
        for kind in (3,4,6):
            self.assertFalse(evidence.support_joint_phase((kind,*TARGET[1:]))['passed'])

    def test_detailed_and_short_circuit_joint_proofs_equal(self):
        frame, original = scene()
        results=[]
        for fast in (False,True):
            evidence=FilledGlyphEvidence(frame,original)
            weak,positive=self.weak_base(evidence)
            phase=(TARGET[1]-frame.pitch[0],TARGET[2])
            def contour(kind,x,y,**kwargs):
                return deepcopy(positive) if (x,y)==phase else deepcopy(weak['silhouette'])
            with patch.object(evidence,'support',return_value=weak), patch.object(evidence.library.filled,'evidence',side_effect=contour):
                results.append(evidence.support_joint_phase(TARGET,short_circuit=fast))
        self.assertTrue(results[0]['passed'])
        self.assertEqual(*results)

    def test_default_recovery_never_calls_joint_api(self):
        frame, original = scene()
        expected=recover_source_filled_glyphs(frame,original)
        with patch.object(FilledGlyphEvidence,'support_joint_phase',side_effect=AssertionError('default changed')):
            self.assertEqual(recover_source_filled_glyphs(frame,original,joint_phase=False),expected)

    def test_opt_in_recovery_retains_instance_guard_and_originals(self):
        frame, original = scene()
        before=deepcopy(original)
        nominal=recover_source_filled_glyphs(frame,original)
        joint=recover_source_filled_glyphs(frame,original,joint_phase=True)
        self.assertEqual(joint,nominal)
        self.assertEqual(original,before)

    def test_joint_option_and_cached_support_validate_boolean(self):
        frame, original = scene()
        evidence=FilledGlyphEvidence(frame,original)
        evidence.support_joint_phase(TARGET)
        for bad in (None,0,1,'true',[]):
            with self.assertRaisesRegex(ValueError,'boolean'):
                recover_source_filled_glyphs(frame,original,joint_phase=bad)
            with self.assertRaisesRegex(ValueError,'boolean'):
                evidence.support_joint_phase(TARGET,short_circuit=bad)
