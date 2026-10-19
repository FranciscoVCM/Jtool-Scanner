"""Compound binding reuses original evidence; the ordinary scanner stays stable."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts import source_filled_pipeline as filled
from scripts.source_deferred_platforms import original_platform_vetoes
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_geometry_pipeline import source_proposals
from scripts.source_sampling import SourceFrame
from tests.test_source_compound_conflicts import scene


def detection(t,x,y):
    return scanner.Detection('original',t,x,y,.67,Box(x,y,32,32))


class FilledSourceRecordingTests(TestCase):
    def setUp(self):
        self.image,self.room,self.frame,self.original,self.material=scene()
        self.context=SourceEvidenceContext(self.image,self.room,
            [(d.type_id,d.x,d.y) for d in self.original if 3<=d.type_id<=10])

    def evidence(self,frame=None,original=None):
        return filled.FilledGlyphEvidence(self.frame if frame is None else frame,
            self.original if original is None else original)

    def test_same_instance_record_and_get_without_new_constructor(self):
        evidence=self.evidence()
        self.context.record_filled_source(self.original,self.frame,evidence)
        with patch.object(filled,'FilledGlyphEvidence',type(evidence)):
            self.assertIs(self.context.filled_source(self.original,self.frame),evidence)
        self.context.record_filled_source(self.original,self.frame,evidence)
        self.assertIs(self.context.filled_source(self.original,self.frame),evidence)

    def test_recording_uses_one_actual_instance_and_identical_complete_proof(self):
        actual=filled.FilledGlyphEvidence;constructed=[]
        class ObservedEvidence(actual):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs);constructed.append(self)
        with patch.object(filled,'filled_hypotheses',return_value=set()):
            baseline=filled.recover_source_filled_glyphs(self.frame,self.original)
            with patch.object(filled,'FilledGlyphEvidence',ObservedEvidence):
                recorded=filled.recover_source_filled_glyphs(self.frame,self.original,
                    source_context=self.context)
                self.assertEqual(len(constructed),1)
                self.assertIs(self.context.filled_source(self.original,self.frame),constructed[0])
        self.assertEqual(recorded,baseline)

    def test_missing_record_is_error_not_a_duplicate_library_fallback(self):
        with self.assertRaisesRegex(ValueError,'Missing original filled'):
            self.context.filled_source(self.original,self.frame)

    def test_replacement_evidence_and_equivalent_but_new_frame_rejected(self):
        evidence=self.evidence();self.context.record_filled_source(self.original,self.frame,evidence)
        with self.assertRaisesRegex(ValueError,'cannot be replaced'):
            self.context.record_filled_source(self.original,self.frame,self.evidence())
        other=SourceFrame(self.image,self.room)
        with self.assertRaisesRegex(ValueError,'frame changed'):
            self.context.filled_source(self.original,other)

    def test_new_original_full_or_changed_metadata_cannot_teach(self):
        evidence=self.evidence();self.context.record_filled_source(self.original,self.frame,evidence)
        for originals in (self.original+[detection(1,608,400)],deepcopy(self.original)):
            if len(originals)==len(self.original):originals[0].kind='changed metadata'
            with self.subTest(count=len(originals)),self.assertRaisesRegex(ValueError,'detections changed'):
                self.context.filled_source(originals,self.frame)

    def test_changed_bytes_original_spikes_or_frame_are_rejected(self):
        evidence=self.evidence();self.context.record_filled_source(self.original,self.frame,evidence)
        evidence.original_spikes=evidence.original_spikes[:-1]
        with self.assertRaisesRegex(ValueError,'share the original'):
            self.context.filled_source(self.original,self.frame)
        other_image=RGBImage(self.image.width,self.image.height,bytes(len(self.image.data)))
        other_frame=SourceFrame(other_image,self.room)
        with self.assertRaisesRegex(ValueError,'share the original'):
            self.context.record_filled_source(self.original,other_frame,self.evidence(other_frame))
        self.image.data=bytes(len(self.image.data))
        with self.assertRaisesRegex(ValueError,'image/data/room changed'):
            self.context.filled_source(self.original,self.frame)

    def test_extended_source_evidence_not_recordable(self):
        extended=SourceFrame(self.image,self.room,extent=Box(-8,0,816,608),canonical=self.image)
        with self.assertRaisesRegex(ValueError,'share the original'):
            self.context.record_filled_source(self.original,extended,self.evidence(extended))


class CompoundPipelineRoutingTests(TestCase):
    def setUp(self):
        self.image,self.room,self.frame,self.original,_=scene()

    def test_record_flag_is_strict_boolean_and_requires_filled_recovery(self):
        for value in (None,0,1,'true',[]):
            with self.subTest(value=value),self.assertRaisesRegex(ValueError,'boolean'):
                source_proposals(self.image,self.room,self.original,record_filled_source=value)
        with self.assertRaisesRegex(ValueError,'requires filled'):
            source_proposals(self.image,self.room,self.original,record_filled_source=True)

    def test_extended_recording_rejected_before_any_source_proposal_work(self):
        extended=SourceFrame(self.image,self.room,extent=Box(-8,0,816,608),canonical=self.image)
        with patch('scripts.source_geometry_pipeline.joint_proposals',side_effect=AssertionError('Too early')):
            with self.assertRaisesRegex(ValueError,'direct original frame'):
                source_proposals(self.image,self.room,self.original,source_frame=extended,
                    include_filled_glyphs=True,record_filled_source=True)

    def test_default_does_not_forward_new_context_keyword(self):
        with patch('scripts.source_geometry_pipeline.recover_source_filled_glyphs',
                   return_value=(set(),{'accepted':[]})) as recovery:
            default=source_proposals(self.image,self.room,self.original,include_filled_glyphs=True)
            bypass=source_proposals(self.image,self.room,self.original,
                include_filled_glyphs=True,record_filled_source=False)
        self.assertEqual(default,bypass)
        self.assertTrue(all('source_context' not in c.kwargs for c in recovery.call_args_list))

    def test_opt_in_routes_only_original_tuple_and_same_context(self):
        context=SourceEvidenceContext(self.image,self.room,
            [(d.type_id,d.x,d.y) for d in self.original if 3<=d.type_id<=10])
        before=deepcopy(self.original)
        with patch('scripts.source_geometry_pipeline.recover_source_filled_glyphs',
                   return_value=({(3,608,400)},{'accepted':[]})) as recovery:
            source_proposals(self.image,self.room,self.original,source_context=context,
                source_frame=self.frame,include_filled_glyphs=True,record_filled_source=True)
        self.assertIs(recovery.call_args.kwargs['source_context'],context)
        self.assertEqual(recovery.call_args.args,(self.frame,tuple(before)))
        self.assertEqual(self.original,before)


class CompoundScannerBindingTests(TestCase):
    def setUp(self):
        self.image,self.room,self.frame,original,self.material=scene()
        self.original=[detection(d.type_id,d.x,d.y) for d in original]
        self.original += [detection(2,224,240),detection(12,608,400)]
        self.false=(1,224,240)

    def result(self):
        return scanner.ScanResult(800,608,self.room,list(self.original),source_grid=(25,19),
            recognized_text='unchanged',infinite_jump=1,dot_kid=1)

    def proposals(self,image,room,original,**kwargs):
        if kwargs.get('record_filled_source'):
            context=kwargs['source_context'];context.begin_growth(original)
            context.record_growth_sizing(original,set(),set())
            evidence=filled.FilledGlyphEvidence(kwargs['source_frame'],original)
            context.record_filled_source(original,kwargs['source_frame'],evidence)
        return {self.false,(1,608,352)},set(),{'source_material':self.material}

    def test_consumer_default_off_does_not_request_context_or_run_checker(self):
        self.assertIs(scanner._SOURCE_COMPOUND_CONFLICTS_ENABLED,False)
        with patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals) as proposals, \
             patch('scripts.source_compound_conflicts.source_compound_conflicts',
                   side_effect=AssertionError('Disabled checker')):
            scanner._apply_source_geometry(self.result(),self.image)
        self.assertNotIn('source_context',proposals.call_args.kwargs)
        self.assertNotIn('record_filled_source',proposals.call_args.kwargs)

    def test_final_filter_preserves_ordinary_survivor_order_objects_and_metadata(self):
        with patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals):
            baseline=scanner._apply_source_geometry(self.result(),self.image)
            result=self.result();original=tuple(result.detections)
            with patch.object(scanner,'_SOURCE_COMPOUND_CONFLICTS_ENABLED',True), \
                 patch('scripts.source_compound_conflicts.source_compound_conflicts',
                       return_value=({self.false},{'retired':[self.false]})) as checker, \
                 patch('scripts.source_registered_rectangles.original_rgb_models',
                       side_effect=AssertionError('Compound is not deferred-platform activation')):
                out=scanner._apply_source_geometry(result,self.image)
        self.assertEqual(out.detections,[d for d in baseline.detections if (d.type_id,d.x,d.y)!=self.false])
        self.assertTrue(all(any(d is original_d for d in out.detections)
            for original_d in original if (original_d.type_id,original_d.x,original_d.y)!=self.false))
        self.assertEqual(checker.call_args.args,(self.image,self.room,original))
        self.assertIs(checker.call_args.kwargs['source_material'],self.material)
        self.assertIs(checker.call_args.kwargs['source_filled_evidence'],
            checker.call_args.kwargs['source_context'].filled_source(original,checker.call_args.kwargs['source_frame']))
        self.assertEqual((out.recognized_text,out.infinite_jump,out.dot_kid),('unchanged',1,1))
        self.assertEqual(out.structural_warnings,scanner.structural_scan_warnings(out.detections))

    def test_no_retirements_preserve_entire_ordinary_result(self):
        with patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals):
            baseline=scanner._apply_source_geometry(self.result(),self.image)
            with patch.object(scanner,'_SOURCE_COMPOUND_CONFLICTS_ENABLED',True), \
                 patch('scripts.source_compound_conflicts.source_compound_conflicts',return_value=(set(),{})):
                now=scanner._apply_source_geometry(self.result(),self.image)
        self.assertEqual(now,baseline)

    def test_both_features_share_context_without_duplicate_kwargs_or_new_teachers(self):
        block,platform=detection(1,544,352),detection(13,544,352)
        vetoes=original_platform_vetoes([block,platform])
        with patch.object(scanner,'_SOURCE_COMPOUND_CONFLICTS_ENABLED',True), \
             patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals) as proposals, \
             patch('scripts.source_registered_rectangles.original_rgb_models',return_value=([],{})) as factory, \
             patch('scripts.source_deferred_platforms.recover_deferred_platform_blocks',
                   side_effect=lambda current,*a,**k:(current,{'added':[]})), \
             patch('scripts.source_compound_conflicts.source_compound_conflicts',return_value=(set(),{})) as checker:
            scanner._apply_source_geometry(self.result(),self.image,platform_vetoes=vetoes)
        self.assertIs(proposals.call_args.kwargs['source_context'],factory.call_args.kwargs['source_context'])
        self.assertIs(factory.call_args.kwargs['source_context'],checker.call_args.kwargs['source_context'])
        self.assertEqual(factory.call_args.args[2],checker.call_args.args[2])
        self.assertNotIn((1,608,352),[(d.type_id,d.x,d.y) for d in checker.call_args.args[2]])

    def test_compact_and_extended_frames_never_enter_compound_factory(self):
        for compact in (True,False):
            result=self.result();frame=self.frame
            if compact:result.source_grid=(19,13)
            else:frame=SourceFrame(self.image,self.room,extent=Box(-8,0,816,608),canonical=self.image)
            with self.subTest(compact=compact), \
                 patch.object(scanner,'_SOURCE_COMPOUND_CONFLICTS_ENABLED',True), \
                 patch('scripts.source_geometry_pipeline.source_proposals',return_value=(set(),set(),{})) as proposals, \
                 patch('scripts.source_compound_conflicts.source_compound_conflicts',
                       side_effect=AssertionError('Unqualified source')):
                scanner._apply_source_geometry(result,self.image,source_frame=frame)
            self.assertTrue(all('record_filled_source' not in c.kwargs and 'source_context' not in c.kwargs
                                for c in proposals.call_args_list))
