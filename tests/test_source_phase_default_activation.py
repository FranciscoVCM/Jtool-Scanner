"""Qualified default source-mode phase caller; standard/unknown modes stay intact."""
from copy import deepcopy
import inspect
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts import source_full_spike_phase as phase
from scripts.scanner_feature_profiles import snapshot_feature_profile
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_sampling import SourceFrame
from tests.test_source_full_spike_phase_consumer import values


class PhaseDefaultActivationTests(TestCase):
    def test_only_qualified_source_selectors_are_enabled(self):
        profile=snapshot_feature_profile(scanner)
        self.assertEqual({k for k,v in profile['switches'].items() if v}, {
            '_SOURCE_REPEATED_IDENTITY_ENABLED','_CAPTURE_BASE_CONTEXT_ENABLED',
            '_SOURCE_FULL_SPIKE_PHASE_ENABLED'})

    def test_actual_default_source_caller_reuses_original_field_and_fast_mode(self):
        scene=values();original=tuple(scene[3]);fields=[];calls=[]
        result=scanner.ScanResult(scene[0].width,scene[0].height,scene[1],list(original),
            source_grid=(25,19),recognized_text='unchanged',infinite_jump=1)
        before=deepcopy(result);real=phase.refit_source_full_spike_phases
        def proposals(image,room,detections,**kwargs):
            self.assertEqual(tuple(detections),original)
            field=FilledGlyphEvidence(kwargs['source_frame'],tuple(detections));fields.append(field)
            kwargs['source_context'].record_filled_source(tuple(detections),kwargs['source_frame'],field)
            return set(),set(),{}
        def refit(*args,**kwargs):
            calls.append((args,kwargs));return real(*args,**kwargs)
        with patch('scripts.source_geometry_pipeline.source_proposals',side_effect=proposals), \
                patch.object(phase,'refit_source_full_spike_phases',side_effect=refit):
            after=scanner._apply_source_geometry(result,scene[0])
        self.assertEqual(len(calls),1);self.assertEqual(len(fields),1)
        self.assertIs(calls[0][1]['short_circuit'],True)
        self.assertIs(calls[0][1]['source_filled_evidence'],fields[0])
        self.assertEqual(calls[0][0][1],tuple(before.detections))
        keys={(d.type_id,d.x,d.y) for d in after.detections}
        self.assertIn(scene[5],keys);self.assertNotIn(scene[6],keys)
        self.assertEqual(after.recognized_text,before.recognized_text)
        self.assertEqual(after.infinite_jump,before.infinite_jump)

    def test_standard_mode_never_enters_phase_refit(self):
        scene=values()
        with patch.object(phase,'refit_source_full_spike_phases',side_effect=AssertionError('Standard mode')):
            result=scanner.scan_image(scene[0],include_geometry=False,include_color_objects=False,
                source_grid=(25,19),source_geometry=False)
        self.assertFalse(result.source_geometry)

    def test_default_phase_caller_keeps_compact_and_extended_bypasses(self):
        scene=values()
        extended=SourceFrame(scene[0],scene[1],extent=Box(-4,0,scene[1].width+8,scene[1].height),
            canonical=RGBImage(800,608,scene[2].canonical_rgb))
        for grid,frame in (((19,13),None),((25,19),extended)):
            result=scanner.ScanResult(scene[0].width,scene[0].height,scene[1],list(scene[3]),source_grid=grid)
            before=deepcopy(result.detections)
            with patch('scripts.source_geometry_pipeline.source_proposals',return_value=(set(),set(),{})), \
                    patch.object(phase,'refit_source_full_spike_phases',side_effect=AssertionError('Unknown mapping')):
                scanner._apply_source_geometry(result,scene[0],**({'source_frame':frame} if frame else {}))
            self.assertEqual(result.detections,before)

    def test_evidence_and_consumer_diagnostic_defaults_still_require_explicit_shortcut(self):
        self.assertIs(inspect.signature(phase.SourceFullSpikePhaseEvidence.probe).parameters['short_circuit'].default,False)
        self.assertIs(inspect.signature(phase.refit_source_full_spike_phases).parameters['short_circuit'].default,False)
