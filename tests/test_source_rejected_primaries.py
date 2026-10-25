"""Bounded original rejection repair cannot teach from its own restorations."""
from copy import deepcopy
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_rejected_primaries import rejected_primary_candidates, recover_rejected_primaries
from scripts.source_sampling import SourceFrame
from jtool_scanner.spike_shape import VERTICES
from tests.test_source_directional_body import changed_background


KINDS = {3: 'spike_up', 4: 'spike_right', 5: 'spike_left', 6: 'spike_down'}


def detection(kind, x, y, room, *, score=.57):
    return scanner.Detection(KINDS.get(kind, 'original'), kind, x, y, score,
        Box(round(room.x+x*room.width/800), round(room.y+y*room.height/608),
            round(32*room.width/800), round(32*room.height/608)))


def scene(**kwargs):
    image, room, frame, raw, key = changed_background(**kwargs)
    original = tuple(detection(d.type_id, d.x, d.y, room) for d in raw)
    candidate = detection(*key, room)
    filled = FilledGlyphEvidence(frame, original)
    return image, room, frame, original, candidate, filled


def recover(values, *, current=None, candidates=None, original=None, **kwargs):
    _, _, frame, teachers, candidate, filled = values
    return recover_rejected_primaries(teachers if current is None else current,
        (candidate,) if candidates is None else candidates,
        teachers if original is None else original, source_frame=frame,
        source_filled_evidence=filled, source_grid=(25,19), **kwargs)


class RejectedPrimaryEvidenceTests(TestCase):
    def test_capture_only_exact_removed_original_primary_objects(self):
        room = Box(0,0,800,608)
        primary = detection(3,128,96,room)
        retained = detection(4,256,96,room)
        recovery = replace(primary, kind='full_spike_shape_recovery', x=320)
        block = detection(1,64,64,room)
        before = [primary, retained, recovery, block]
        after = [retained, recovery, block]
        captured = rejected_primary_candidates(before, after)
        self.assertEqual(captured, (primary,))
        self.assertIs(captured[0], primary)
        self.assertEqual(before, [primary, retained, recovery, block])

    def test_transfer_all_directions_palette_brightness_background_and_fractional_scale(self):
        transforms=(lambda c:c, lambda c:tuple(255-v for v in c),
            lambda c:(c[2],c[0],c[1]), lambda c:tuple(round(v*.4) for v in c))
        for rotation,transform in enumerate(transforms):
            for scale in (1,1.25):
                with self.subTest(rotation=rotation,scale=scale):
                    values=scene(rotation=rotation,scale=scale,transform=transform)
                    _,_,_,original,candidate,filled=values
                    old=deepcopy((filled.library.anchors,filled.library.models))
                    merged,report=recover(values)
                    self.assertEqual(len(merged),len(original)+1)
                    self.assertTrue(any(d is candidate for d in merged))
                    self.assertTrue(all(any(d is teacher for d in merged) for teacher in original))
                    self.assertEqual(report['accepted'][0]['key'],(candidate.type_id,candidate.x,candidate.y))
                    self.assertEqual((filled.library.anchors,filled.library.models),old)
                    self.assertNotIn((candidate.type_id,candidate.x,candidate.y),filled.original_spikes)

    def test_original_candidate_score_provenance_and_image_box_are_not_replaced(self):
        values=scene()
        candidate=replace(values[4],score=.312345,image_box=Box(447,351,33,33))
        merged,report=recover(values,candidates=(candidate,))
        restored=next(d for d in merged if d is candidate)
        self.assertEqual(restored,candidate)
        self.assertEqual(report['evaluated'],1)

    def test_isoluminant_rgb_is_not_a_grayscale_second_scan(self):
        values=scene(foreground=(150,80,65),background=(80,120,40))
        merged,report=recover(values)
        self.assertIn(values[4],merged)
        self.assertTrue(report['accepted'])

    def test_current_and_retired_poses_do_not_construct_directional_evidence(self):
        values=scene();candidate=values[4]
        key=(candidate.type_id,candidate.x,candidate.y)
        with patch('scripts.source_rejected_primaries.SourceDirectionalBodyEvidence',
                   side_effect=AssertionError('No eligible candidate')):
            merged,report=recover(values,current=(*values[3],candidate))
            self.assertEqual(merged,list((*values[3],candidate)))
            self.assertEqual(report['evaluated'],0)
            merged,report=recover(values,retired=(key,))
            self.assertEqual(merged,list(values[3]))
            self.assertEqual(report['evaluated'],0)

    def test_nearby_unresolved_same_instance_is_not_duplicated(self):
        values=scene();candidate=values[4]
        existing=replace(candidate,x=candidate.x+8)
        with patch.object(values[5],'apex_support',return_value={'passed':False}):
            merged,report=recover(values,current=(*values[3],existing))
        self.assertNotIn(candidate,merged)
        self.assertEqual(merged,list((*values[3],existing)))
        self.assertTrue(report['same_instance_alternatives'])

    def test_compact_world_and_empty_queries_do_not_build_evidence(self):
        values=scene();image,room,frame,original,candidate,_=values
        extended=SourceFrame(image,room,extent=Box(-8,0,816,608),canonical=image)
        with patch('scripts.source_rejected_primaries.SourceDirectionalBodyEvidence',
                   side_effect=AssertionError('Unqualified or empty domain')):
            for grid,world,candidates in (((19,13),frame,(candidate,)),
                    ((25,19),extended,(candidate,)),((25,19),frame,())):
                merged,report=recover_rejected_primaries(original,candidates,original,
                    source_frame=world,source_filled_evidence=None,source_grid=grid)
                self.assertEqual(merged,list(original))
                self.assertEqual(report['evaluated'],0)

    def test_changed_or_other_frame_teacher_snapshot_is_rejected(self):
        values=scene()
        with self.assertRaises(ValueError):
            recover(values,original=(*values[3],values[4]))
        with self.assertRaises(ValueError):
            recover_rejected_primaries(values[3],(values[4],),values[3],
                source_frame=SourceFrame(values[0],values[1]),source_filled_evidence=values[5],source_grid=(25,19))

    def test_bad_candidate_kind_and_ambiguous_metadata_are_not_reinterpreted(self):
        values=scene();candidate=values[4]
        for candidates in ((replace(candidate,kind='spike_down' if candidate.type_id!=6 else 'spike_up'),),
                           (candidate,replace(candidate,score=.99))):
            with self.subTest(candidates=candidates),self.assertRaises(ValueError):
                recover(values,candidates=candidates)

    def test_identical_duplicate_pending_metadata_restores_only_one_instance(self):
        values=scene();candidate=values[4]
        merged,report=recover(values,candidates=(candidate,candidate))
        self.assertEqual(merged.count(candidate),1)
        self.assertEqual(len(report['accepted']),1)

    def test_unrelated_background_paint_never_retires_or_relabels_originals(self):
        values=scene();image,room,_,original,candidate,_=values
        raster=Image.frombytes('RGB',(800,608),image.data)
        ImageDraw.Draw(raster).rectangle((candidate.x,candidate.y,candidate.x+31,candidate.y+31),fill=(140,70,180))
        wrong=RGBImage(800,608,raster.tobytes());frame=SourceFrame(wrong,room)
        merged,report=recover((wrong,room,frame,original,candidate,FilledGlyphEvidence(frame,original)))
        self.assertEqual(merged,list(original))
        self.assertFalse(report['accepted'])

    def test_real_16px_shape_cannot_be_promoted_to_a_32px_original_pose(self):
        values=scene();image,room,_,original,candidate,_=values
        raster=Image.frombytes('RGB',(800,608),image.data)
        draw=ImageDraw.Draw(raster)
        draw.rectangle((candidate.x,candidate.y,candidate.x+31,candidate.y+31),fill=(140,70,180))
        vertices=VERTICES[candidate.type_id];tip=vertices[0]
        draw.polygon([(candidate.x+tip[0]+(a-tip[0])/2,
                       candidate.y+tip[1]+(b-tip[1])/2) for a,b in vertices],fill=(210,150,70))
        mini=RGBImage(800,608,raster.tobytes());frame=SourceFrame(mini,room)
        merged,report=recover((mini,room,frame,original,candidate,FilledGlyphEvidence(frame,original)))
        self.assertEqual(merged,list(original))
        self.assertFalse(report['accepted'])

    def test_unknown_edge_context_is_not_evidence_for_a_new_object(self):
        values=scene();candidate=detection(3,0,0,values[1])
        merged,report=recover(values,candidates=(candidate,))
        self.assertEqual(merged,list(values[3]))
        self.assertFalse(report['accepted'])


class RejectedPrimaryScannerBindingTests(TestCase):
    def setUp(self):
        self.values=scene()
        self.image,self.room,self.frame,self.original,self.candidate,self.filled=self.values

    def result(self):
        return scanner.ScanResult(800,608,self.room,list(self.original),source_grid=(25,19),
            infinite_jump=1,dot_kid=1,recognized_text='unchanged')

    def proposals(self,image,room,original,**kwargs):
        if kwargs.get('record_filled_source'):
            context=kwargs['source_context'];context.begin_growth(original)
            context.record_growth_sizing(original,set(),set())
            context.record_filled_source(original,kwargs['source_frame'],self.filled)
        return set(),set(),{'source_material': {}}

    def test_default_off_does_not_build_pending_context_or_invoke_recovery(self):
        self.assertIs(scanner._SOURCE_REJECTED_PRIMARY_RECOVERY_ENABLED,False)
        # Isolate the disabled primary consumer from the enabled phase caller.
        with patch.object(scanner,'_SOURCE_FULL_SPIKE_PHASE_ENABLED',False), \
             patch('scripts.source_geometry_pipeline.source_proposals',return_value=(set(),set(),{})) as producer, \
             patch('scripts.source_rejected_primaries.recover_rejected_primaries',side_effect=AssertionError('Disabled')):
            out=scanner._apply_source_geometry(self.result(),self.image,rejected_primary_spikes=(self.candidate,))
        self.assertNotIn('record_filled_source',producer.call_args.kwargs)
        self.assertNotIn('source_context',producer.call_args.kwargs)
        self.assertEqual(out.detections,list(self.original))

    def test_enabled_consumer_shares_actual_field_and_original_teachers(self):
        with patch.object(scanner,'_SOURCE_REJECTED_PRIMARY_RECOVERY_ENABLED',True), \
             patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals) as producer:
            out=scanner._apply_source_geometry(self.result(),self.image,source_frame=self.frame,
                rejected_primary_spikes=(self.candidate,))
        self.assertTrue(producer.call_args.kwargs['record_filled_source'])
        context=producer.call_args.kwargs['source_context']
        self.assertIs(context.filled_source(self.original,self.frame),self.filled)
        self.assertNotIn((self.candidate.type_id,self.candidate.x,self.candidate.y),self.filled.original_spikes)
        self.assertTrue(any(d is self.candidate for d in out.detections))
        self.assertEqual((out.infinite_jump,out.dot_kid,out.recognized_text),(1,1,'unchanged'))
        self.assertEqual(out.structural_warnings,scanner.structural_scan_warnings(out.detections))

    def test_empty_compact_extended_cases_do_not_request_or_run_new_evidence(self):
        for grid,frame,pending in (((25,19),self.frame,()),((19,13),self.frame,(self.candidate,)),
                ((25,19),SourceFrame(self.image,self.room,extent=Box(-8,0,816,608),canonical=self.image),(self.candidate,))):
            result=self.result();result.source_grid=grid
            with self.subTest(grid=grid,pending=pending), \
                 patch.object(scanner,'_SOURCE_FULL_SPIKE_PHASE_ENABLED',False), \
                 patch.object(scanner,'_SOURCE_REJECTED_PRIMARY_RECOVERY_ENABLED',True), \
                 patch('scripts.source_geometry_pipeline.source_proposals',return_value=(set(),set(),{})) as producer, \
                 patch('scripts.source_rejected_primaries.recover_rejected_primaries',side_effect=AssertionError('Unqualified')):
                scanner._apply_source_geometry(result,self.image,source_frame=frame,rejected_primary_spikes=pending)
            self.assertTrue(all('record_filled_source' not in c.kwargs for c in producer.call_args_list))

    def test_source_retirements_and_newly_emitted_keys_are_not_restored_or_replaced(self):
        key=(self.candidate.type_id,self.candidate.x,self.candidate.y)
        for proposed,retired in ((set(),{key}),({key},set())):
            def producer(*args,**kwargs):
                self.proposals(*args,**kwargs)
                return proposed,retired,{}
            with self.subTest(proposed=proposed,retired=retired), \
                 patch.object(scanner,'_SOURCE_REJECTED_PRIMARY_RECOVERY_ENABLED',True), \
                 patch('scripts.source_geometry_pipeline.source_proposals',side_effect=producer):
                out=scanner._apply_source_geometry(self.result(),self.image,source_frame=self.frame,
                    rejected_primary_spikes=(self.candidate,))
            self.assertFalse(any(d is self.candidate for d in out.detections))
            self.assertEqual(sum((d.type_id,d.x,d.y)==key for d in out.detections),int(bool(proposed)))

    def test_compound_and_primary_consumers_share_one_original_field_and_retired_set(self):
        key=(self.candidate.type_id,self.candidate.x,self.candidate.y)
        with patch.object(scanner,'_SOURCE_REJECTED_PRIMARY_RECOVERY_ENABLED',True), \
             patch.object(scanner,'_SOURCE_COMPOUND_CONFLICTS_ENABLED',True), \
             patch('scripts.source_geometry_pipeline.source_proposals',side_effect=self.proposals) as producer, \
             patch('scripts.source_compound_conflicts.source_compound_conflicts',return_value=({key},{})) as compound:
            out=scanner._apply_source_geometry(self.result(),self.image,source_frame=self.frame,
                rejected_primary_spikes=(self.candidate,))
        context=producer.call_args.kwargs['source_context']
        self.assertIs(compound.call_args.kwargs['source_context'],context)
        self.assertIs(compound.call_args.kwargs['source_filled_evidence'],self.filled)
        self.assertEqual(compound.call_args.args[2],self.original)
        self.assertEqual(out.detections,list(self.original))
