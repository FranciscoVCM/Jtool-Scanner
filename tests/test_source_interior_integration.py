"""Opt-in interior evidence reuses the actual original filled instance."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from scripts import source_filled_pipeline as filled
from scripts.source_geometry_pipeline import source_proposals
from scripts.source_interior_glyphs import SourceInteriorGlyphEvidence
from scripts.source_sampling import SourceFrame
from tests.test_source_interior_glyphs import scene, cropped_scene
from tests.source_geometry_stubs import record_requested_original_filled_source


class InteriorRecoveryIntegrationTests(TestCase):
    def test_default_and_explicit_bypass_preserve_entire_old_proof(self):
        _,_,frame,original,_=scene()
        with patch('scripts.source_interior_glyphs.SourceInteriorGlyphEvidence',
                   side_effect=AssertionError('Disabled path must not construct')):
            default=filled.recover_source_filled_glyphs(frame,original,joint_phase=True)
            bypass=filled.recover_source_filled_glyphs(frame,original,joint_phase=True,interior_grid=None)
        self.assertEqual(default,bypass)

    def test_real_positive_reuses_one_filled_instance_and_no_new_teachers(self):
        _,_,frame,original,target=scene();before=deepcopy(original)
        baseline=filled.recover_source_filled_glyphs(frame,original,joint_phase=True)
        actual=filled.FilledGlyphEvidence;built=[];interior_built=[]
        class ObservedFilled(actual):
            def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);built.append(self)
        class ObservedInterior(SourceInteriorGlyphEvidence):
            def __init__(self,*args,**kwargs):super().__init__(*args,**kwargs);interior_built.append(args)
        with patch.object(filled,'FilledGlyphEvidence',ObservedFilled), \
             patch('scripts.source_interior_glyphs.SourceInteriorGlyphEvidence',ObservedInterior):
            proposed,proof=filled.recover_source_filled_glyphs(frame,original,joint_phase=True,interior_grid=(25,19))
        self.assertEqual(len(built),1);self.assertEqual(len(interior_built),1)
        self.assertIs(interior_built[0][0],built[0]);self.assertEqual(interior_built[0][1],tuple(original))
        self.assertEqual(proposed-baseline[0],{target})
        self.assertTrue(baseline[0]<=proposed)
        self.assertEqual(original,before)
        accepted=next(r['evidence'] for r in proof['accepted'] if tuple(r['key'])==target)
        self.assertTrue(accepted['interior_appearance_recovery'])
        self.assertTrue(accepted['original_teachers_only'])
        self.assertTrue(accepted['complete_physical_source'])
        self.assertTrue(accepted['no_retirement'])
        oldproofs={tuple(r['key']):r for r in baseline[1]['accepted']}
        self.assertEqual({tuple(r['key']):r for r in proof['accepted'] if tuple(r['key']) in oldproofs},oldproofs)

    def test_invalid_grid_rejected_before_construction(self):
        image,room,frame,original,_=scene()
        for grid in ((19,13),False,[25,19],'25x19'):
            with self.subTest(grid=grid),patch.object(filled,'FilledGlyphEvidence',side_effect=AssertionError('No construction')):
                with self.assertRaisesRegex(ValueError,'qualified25x19'):
                    filled.recover_source_filled_glyphs(frame,original,interior_grid=grid)

    def test_extended_world_positive_and_entire_default_bypass_preserved(self):
        _,_,frame,original,target=cropped_scene(scale=1.25)
        before=deepcopy(original)
        with patch('scripts.source_interior_glyphs.SourceInteriorGlyphEvidence',
                   side_effect=AssertionError('Disabled path must not construct')):
            baseline=filled.recover_source_filled_glyphs(frame,original,joint_phase=True)
            bypass=filled.recover_source_filled_glyphs(frame,original,joint_phase=True,interior_grid=None)
        self.assertEqual(baseline,bypass)
        proposed,proof=filled.recover_source_filled_glyphs(frame,original,joint_phase=True,interior_grid=(25,19))
        self.assertEqual(proposed-baseline[0],{target});self.assertEqual(original,before)
        oldproofs={tuple(r['key']):r for r in baseline[1]['accepted']}
        self.assertEqual({tuple(r['key']):r for r in proof['accepted'] if tuple(r['key']) in oldproofs},oldproofs)

    def test_original_context_record_and_interior_share_actual_evidence(self):
        from scripts.source_evidence_context import SourceEvidenceContext
        image,room,frame,original,target=scene()
        context=SourceEvidenceContext(image,room,[(d.type_id,d.x,d.y) for d in original])
        library=context.glyph_library(image,room,context._spikes)
        proposed,_=filled.recover_source_filled_glyphs(frame,original,source_library=library,
            source_context=context,joint_phase=True,interior_grid=(25,19))
        self.assertIn(target,proposed)
        saved=context.filled_source(original,frame)
        self.assertIs(saved.library,library)
        self.assertNotIn(target,saved.original_spikes)


class InteriorPipelineRoutingTests(TestCase):
    def setUp(self):
        # A neutral routing fixture avoids paying for unrelated scene calibration.
        from tests import test_source_geometry_pipeline as fixtures
        fixture=fixtures.SourceGeometryPipelineTests();fixture.setUp()
        self.image,self.room,self.original=fixture.image,fixture.room,fixture.detections

    def test_boolean_and_filled_preconditions(self):
        for value in (None,0,1,'true',[]):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'boolean'):
                source_proposals(self.image,self.room,self.original,include_filled_interior=value)
        with self.assertRaisesRegex(ValueError,'requires filled'):
            source_proposals(self.image,self.room,self.original,include_filled_interior=True)

    def test_default_does_not_forward_new_grid_keyword(self):
        with patch('scripts.source_geometry_pipeline.recover_source_filled_glyphs',return_value=(set(),{'accepted':[]})) as recover:
            default=source_proposals(self.image,self.room,self.original,include_filled_glyphs=True)
            bypass=source_proposals(self.image,self.room,self.original,include_filled_glyphs=True,include_filled_interior=False)
        self.assertEqual(default,bypass)
        self.assertTrue(all('interior_grid' not in c.kwargs for c in recover.call_args_list))

    def test_opt_in_routes_exact_originals_and_direct_grid(self):
        with patch('scripts.source_geometry_pipeline.recover_source_filled_glyphs',return_value=(set(),{'accepted':[]})) as recover:
            source_proposals(self.image,self.room,self.original,include_filled_glyphs=True,include_filled_interior=True)
        self.assertEqual(recover.call_args.args[1],tuple(self.original))
        self.assertEqual(recover.call_args.kwargs['interior_grid'],(25,19))
        self.assertTrue(recover.call_args.args[0].matches_source(recover.call_args.kwargs['source_library'].raw.image,self.room))

    def test_extended_world_record_remains_separate_from_interior_routing(self):
        frame=SourceFrame(self.image,self.room,extent=Box(-8,0,816,608),canonical=self.image)
        with patch('scripts.source_geometry_pipeline.joint_proposals',side_effect=AssertionError('Too early')):
            with self.assertRaisesRegex(ValueError,'direct original'):
                source_proposals(self.image,self.room,self.original,source_frame=frame,
                    include_filled_glyphs=True,include_filled_interior=True,record_filled_source=True)
        with patch('scripts.source_geometry_pipeline.recover_source_filled_glyphs',return_value=(set(),{'accepted':[]})) as recover:
            source_proposals(self.image,self.room,self.original,source_frame=frame,
                include_filled_glyphs=True,include_filled_interior=True)
        self.assertIs(recover.call_args.args[0],frame)
        self.assertIsNone(recover.call_args.kwargs['source_library'])
        self.assertEqual(recover.call_args.kwargs['interior_grid'],(25,19))

    def test_actual_scanner_default_off_and_direct_opt_in_only(self):
        self.assertIs(scanner._SOURCE_INTERIOR_GLYPHS_ENABLED,False)
        def proposals_with_original_field(image,room,original,**options):
            record_requested_original_filled_source(original,options)
            return set(),set(),{}
        for enabled in (False,True):
            with self.subTest(enabled=enabled),patch.object(scanner,'_SOURCE_INTERIOR_GLYPHS_ENABLED',enabled), \
                 patch('scripts.source_geometry_pipeline.source_proposals',side_effect=proposals_with_original_field) as proposals:
                result=scanner.ScanResult(800,608,self.room,[],source_grid=(25,19))
                scanner._apply_source_geometry(result,self.image)
            if enabled:self.assertIs(proposals.call_args.kwargs['include_filled_interior'],True)
            else:self.assertNotIn('include_filled_interior',proposals.call_args.kwargs)
            options=proposals.call_args.kwargs
            self.assertIs(options['source_context'].filled_source((),options['source_frame']).frame,
                options['source_frame'])

    def test_compact_bypasses_but_extended_world_routes_only_explicit_opt_in(self):
        for compact in (False,True):
            frame=SourceFrame(self.image,self.room) if compact else SourceFrame(self.image,self.room,
                extent=Box(-8,0,816,608),canonical=self.image)
            result=scanner.ScanResult(800,608,self.room,[],source_grid=(19,13) if compact else (25,19))
            with self.subTest(compact=compact),patch.object(scanner,'_SOURCE_INTERIOR_GLYPHS_ENABLED',True), \
                 patch('scripts.source_geometry_pipeline.source_proposals',return_value=(set(),set(),{})) as proposals:
                scanner._apply_source_geometry(result,self.image,source_frame=frame)
            if compact:self.assertFalse(proposals.called)
            else:
                self.assertIs(proposals.call_args.kwargs['include_filled_interior'],True)
                self.assertIs(proposals.call_args.kwargs['source_frame'],frame)
