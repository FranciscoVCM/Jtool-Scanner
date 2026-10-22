"""Actual phase application preserves metadata, models and unrelated objects."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from PIL import Image

from jtool_scanner import scanner
from jtool_scanner.correction import CorrectionProject,render_source_blend_svg
from jtool_scanner.geometry import Box
from scripts import source_full_spike_phase as phases
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_sampling import SourceFrame
from tests.test_source_full_spike_phase import fixture
from tests.test_source_rejected_primaries import detection


def values(**kwargs):
    image,room,frame,raw,target,old=fixture(**kwargs)
    original=tuple(detection(d.type_id,d.x,d.y,room,score=.312345 if (d.type_id,d.x,d.y)==old else .72)
                   for d in raw)
    filled=FilledGlyphEvidence(frame,original)
    return image,room,frame,original,filled,target,old


def refit(scene,*,current=None,original=None,filled=None,frame=None,grid=(25,19),retired=()):
    return phases.refit_source_full_spike_phases(scene[3] if current is None else current,
        scene[3] if original is None else original,source_frame=scene[2] if frame is None else frame,
        source_filled_evidence=scene[4] if filled is None else filled,source_grid=grid,retired=retired)


class FullSpikePhaseConsumerTests(TestCase):
    def test_actual_source_correction_preserves_all_unrelated_instances_and_order(self):
        scene=values();original=scene[3];old=scene[6]
        extras=(detection(13,704,448,scene[1]),detection(1,0,0,scene[1]),detection(2,32,32,scene[1]))
        current=(*original,*extras)
        library=deepcopy((scene[4].library.anchors,scene[4].library.models))
        after,report=refit(scene,current=current)
        self.assertEqual(len(after),len(current))
        self.assertEqual(len(report['corrected']),1)
        for before,now in zip(current,after):
            if (before.type_id,before.x,before.y)==old:
                self.assertEqual((now.type_id,now.x,now.y),scene[5])
                self.assertEqual((now.kind,now.type_id,now.score),(before.kind,before.type_id,before.score))
                self.assertEqual(now.image_box,Box(round(scene[1].x+now.x*scene[1].width/800),
                    round(scene[1].y+now.y*scene[1].height/608),round(32*scene[1].width/800),round(32*scene[1].height/608)))
            else:self.assertIs(now,before)
        self.assertEqual(library,(scene[4].library.anchors,scene[4].library.models))
        self.assertEqual(tuple(original),scene[3])

    def test_all_directions_palette_brightness_and_native_fractional_capture(self):
        transforms=(lambda c:c,lambda c:tuple(255-v for v in c),
                    lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(.4*v) for v in c))
        for rotation,transform in enumerate(transforms):
            for scale,amount in ((1,16),(1.25,8)):
                scene=values(rotation=rotation,transform=transform,scale=scale,amount=amount,isolated=amount==16)
                after,report=refit(scene)
                with self.subTest(rotation=rotation,scale=scale):
                    self.assertEqual(len(report['corrected']),1)
                    self.assertIn(scene[5],{(d.type_id,d.x,d.y) for d in after})

    def test_explicit_retired_old_or_new_pose_cannot_reenter(self):
        scene=values()
        for retired in ((scene[6],),(scene[5],)):
            with self.subTest(retired=retired):
                after,report=refit(scene,retired=retired)
                self.assertEqual(after,list(scene[3]));self.assertFalse(report['corrected'])

    def test_changed_metadata_and_duplicate_current_origin_abstain(self):
        scene=values();current=list(scene[3])
        old=next(d for d in current if (d.type_id,d.x,d.y)==scene[6])
        for replacement in ((replace(old,score=.99),), (old,old)):
            test=[d for d in current if d is not old]+list(replacement)
            after,report=refit(scene,current=test)
            self.assertEqual(after,test);self.assertFalse(report['corrected'])

    def test_no_original_current_full_does_not_build_phase_evidence(self):
        scene=values()
        with patch.object(phases,'SourceFullSpikePhaseEvidence',side_effect=AssertionError('No eligible originals')):
            after,report=refit(scene,current=(detection(1,0,0,scene[1]),))
        self.assertFalse(report['corrected'])

    def test_unknown_or_compact_world_mapping_does_not_build_phase_evidence(self):
        scene=values()
        from jtool_scanner.image import RGBImage
        translated=SourceFrame(scene[0],scene[1],extent=Box(-4,0,scene[1].width+8,scene[1].height),
            canonical=RGBImage(800,608,scene[2].canonical_rgb))
        with patch.object(phases,'SourceFullSpikePhaseEvidence',side_effect=AssertionError('Unqualified')):
            for kwargs in (dict(grid=(19,13)),dict(frame=translated)):
                after,report=refit(scene,**kwargs)
                self.assertEqual(after,list(scene[3]));self.assertFalse(report['corrected'])

    def test_missing_or_foreign_original_field_is_rejected_not_reconstructed(self):
        scene=values()
        with self.assertRaises(ValueError):
            phases.refit_source_full_spike_phases(scene[3],scene[3],source_frame=scene[2],
                source_filled_evidence=None,source_grid=(25,19))
        other=values(rotation=1)
        with self.assertRaises(ValueError):refit(scene,filled=other[4])

    def test_jmap_project_and_blend_use_corrected_native_and_physical_origins(self):
        scene=values();after,report=refit(scene)
        result=scanner.ScanResult(scene[0].width,scene[0].height,scene[1],after,source_grid=(25,19))
        self.assertIn(scene[5],{(o.type_id,o.x,o.y) for o in result.to_jmap('none').objects})
        self.assertNotIn(scene[6],{(o.type_id,o.x,o.y) for o in result.to_jmap('none').objects})
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.png'
            Image.frombytes('RGB',(scene[0].width,scene[0].height),scene[0].data).save(source)
            project=CorrectionProject.from_scan(result,source)
            obj=next(o for o in project.objects if (o.type_id,o.x,o.y)==scene[5])
            corrected=next(d for d in after if (d.type_id,d.x,d.y)==scene[5])
            self.assertEqual(obj.image_box,corrected.image_box)
            self.assertIn('<svg',render_source_blend_svg(project))

    def test_conflicting_replacement_targets_keep_both_originals(self):
        scene=values();first=scene[3][-1];second=replace(first,x=first.x+8)
        original=(*scene[3],second);filled=FilledGlyphEvidence(scene[2],original)
        desired=scene[5]
        def hypotheses(field,old,current):
            return dict(old=old,proposed=desired if old in (scene[6],(second.type_id,second.x,second.y)) else None)
        with patch.object(phases.SourceFullSpikePhaseEvidence,'probe',hypotheses):
            after,report=refit(scene,current=original,original=original,filled=filled)
        self.assertEqual(after,list(original));self.assertFalse(report['corrected'])

    def test_new_positions_never_teach_subsequent_queries(self):
        scene=values();seen=[];original_probe=phases.SourceFullSpikePhaseEvidence.probe
        def observed(field,old,current):
            seen.append(tuple(current))
            return original_probe(field,old,current)
        with patch.object(phases.SourceFullSpikePhaseEvidence,'probe',observed):
            after,report=refit(scene)
        self.assertTrue(report['corrected'])
        self.assertTrue(all(value==scene[3] for value in seen))
        self.assertNotIn(scene[5],scene[4].original_spikes)
