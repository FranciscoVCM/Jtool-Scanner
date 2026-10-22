"""Actual final-source caller, original evidence reuse and all bypass routes."""
from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts import source_full_spike_phase as phases
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_sampling import SourceFrame
from tests.test_source_full_spike_phase_consumer import values


FLAG='_SOURCE_FULL_SPIKE_PHASE_ENABLED'


class FullSpikePhaseIntegrationTests(TestCase):
    def setUp(self):
        self.scene=values()
        self.calls=[];self.fields=[]

    def result(self):
        return scanner.ScanResult(self.scene[0].width,self.scene[0].height,self.scene[1],
            list(self.scene[3]),source_grid=(25,19),recognized_text='unchanged',infinite_jump=1)

    def proposals(self,added=(),retired=()):
        def stage(image,room,original,**kwargs):
            self.calls.append((tuple(original),kwargs))
            if kwargs.get('record_filled_source'):
                field=FilledGlyphEvidence(kwargs['source_frame'],tuple(original))
                self.fields.append(field)
                kwargs['source_context'].record_filled_source(tuple(original),kwargs['source_frame'],field)
            return set(added),set(retired),{}
        return stage

    def test_enabled_final_caller_corrects_from_actual_original_shared_field(self):
        result=self.result();before=deepcopy(result)
        original_consumer=phases.refit_source_full_spike_phases
        seen=[]
        def observed(*args,**kwargs):
            seen.append((args,kwargs))
            return original_consumer(*args,**kwargs)
        with patch.object(scanner,FLAG,True,create=True), \
                patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals()), \
                patch.object(phases,'refit_source_full_spike_phases',side_effect=observed):
            after=scanner._apply_source_geometry(result,self.scene[0])
        self.assertEqual(len(seen),1)
        self.assertEqual(len(self.fields),1)
        self.assertIs(seen[0][1]['source_filled_evidence'],self.fields[0])
        self.assertIs(seen[0][1]['source_frame'],self.fields[0].frame)
        self.assertEqual(seen[0][0][1],tuple(before.detections))
        self.assertIn(self.scene[5],{(d.type_id,d.x,d.y) for d in after.detections})
        self.assertNotIn(self.scene[6],{(d.type_id,d.x,d.y) for d in after.detections})
        self.assertEqual(after.recognized_text,before.recognized_text)
        self.assertEqual(after.infinite_jump,before.infinite_jump)

    def test_disabled_caller_retains_old_options_and_does_not_construct_field(self):
        result=self.result();before=deepcopy(result.detections)
        with patch.object(scanner,FLAG,False,create=True), \
                patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals()), \
                patch.object(phases,'refit_source_full_spike_phases',side_effect=AssertionError('Disabled')):
            scanner._apply_source_geometry(result,self.scene[0])
        self.assertEqual(result.detections,before)
        self.assertNotIn('record_filled_source',self.calls[0][1])
        self.assertNotIn('source_context',self.calls[0][1])
        self.assertFalse(self.fields)

    def test_compact_and_extended_world_frames_do_not_enable_phase(self):
        frame=SourceFrame(self.scene[0],self.scene[1],
            extent=Box(-4,0,self.scene[1].width+8,self.scene[1].height),
            canonical=RGBImage(800,608,self.scene[2].canonical_rgb))
        result=self.result()
        with patch.object(scanner,FLAG,True,create=True), \
                patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals()), \
                patch.object(phases,'refit_source_full_spike_phases',side_effect=AssertionError('Unqualified')):
            scanner._apply_source_geometry(result,self.scene[0],source_frame=frame)
        self.assertNotIn('record_filled_source',self.calls[0][1])
        result=self.result();result.source_grid=(19,13)
        with patch.object(scanner,FLAG,True,create=True), \
                patch('scripts.source_geometry_pipeline.source_proposals',side_effect=AssertionError('Compact')):
            scanner._apply_source_geometry(result,self.scene[0])

    def test_prior_additions_and_retirements_do_not_change_original_teachers(self):
        result=self.result();before=tuple(result.detections)
        retired=(before[0].type_id,before[0].x,before[0].y)
        added=(1,704,448)
        seen=[];original_consumer=phases.refit_source_full_spike_phases
        def observed(*args,**kwargs):
            seen.append((tuple(args[0]),tuple(args[1]),set(kwargs['retired'])))
            return original_consumer(*args,**kwargs)
        with patch.object(scanner,FLAG,True,create=True), \
                patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals((added,),(retired,))), \
                patch.object(phases,'refit_source_full_spike_phases',side_effect=observed):
            scanner._apply_source_geometry(result,self.scene[0])
        self.assertEqual(seen[0][1],before)
        self.assertIn(added,{(d.type_id,d.x,d.y) for d in seen[0][0]})
        self.assertNotIn(retired,{(d.type_id,d.x,d.y) for d in seen[0][0]})
        self.assertIn(retired,seen[0][2])
        self.assertNotIn(added,self.fields[0].original_spikes)

    def test_retired_phase_target_is_not_restored_by_final_caller(self):
        result=self.result()
        with patch.object(scanner,FLAG,True,create=True), \
                patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals(retired=(self.scene[5],))):
            scanner._apply_source_geometry(result,self.scene[0])
        self.assertIn(self.scene[6],{(d.type_id,d.x,d.y) for d in result.detections})
        self.assertNotIn(self.scene[5],{(d.type_id,d.x,d.y) for d in result.detections})

    def test_warning_refresh_occurs_only_for_an_actual_correction(self):
        result=self.result()
        with patch.object(scanner,FLAG,True,create=True), \
                patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals()), \
                patch.object(scanner,'structural_scan_warnings',return_value=[{'kind':'measured'}]) as warnings:
            scanner._apply_source_geometry(result,self.scene[0])
        self.assertEqual(warnings.call_count,1)
        self.assertEqual(result.structural_warnings,[{'kind':'measured'}])

    def test_standard_scan_does_not_call_phase_even_when_selector_is_true(self):
        with patch.object(scanner,FLAG,True,create=True), \
                patch.object(phases,'refit_source_full_spike_phases',side_effect=AssertionError('Standard')):
            result=scanner.scan_image(self.scene[0],include_geometry=False,source_grid=(25,19))
        self.assertFalse(result.source_geometry)
