"""Opt-in composition is conservative and leaves the default path intact."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts import source_compound_conflicts as compound
from scripts.source_calibrated_conflicts import CalibratedConflictQuery
from scripts.source_filled_pipeline import FilledGlyphEvidence
from tests.test_source_compound_conflicts import scene


def run(values,enabled=True):
    image,room,frame,original,material=values
    return compound.source_compound_conflicts(image,room,original,source_grid=(25,19),source_frame=frame,
        source_material=material,source_filled_evidence=FilledGlyphEvidence(frame,original),calibrated_background=enabled)


class SourceCalibratedConflictTests(TestCase):
    def test_default_and_false_preserve_entire_legacy_proof(self):
        image,room,frame,original,material=values=scene()
        expected=compound.source_compound_conflicts(image,room,original,source_grid=(25,19),source_frame=frame,source_material=material)
        # Reuse fields are deliberately compared under the same explicit inputs.
        explicit=compound.source_compound_conflicts(image,room,original,source_grid=(25,19),source_frame=frame,
            source_material=material,calibrated_background=False)
        self.assertEqual(explicit,expected)
        self.assertEqual(run(values)[0],run(values,False)[0])

    def test_legacy_positive_wins_without_constructing_backdrop(self):
        with patch('scripts.source_calibrated_conflicts.SourceGlyphBackdrop',side_effect=AssertionError('Legacy positive needs no new model')):
            self.assertEqual(run(scene())[0],{(1,224,240)})

    def test_real_rectangle_and_partial_occlusion_are_kept(self):
        self.assertNotIn((1,224,240),run(scene(paint_candidate=True))[0])

    def test_original_nongeometry_is_still_veto(self):
        values=scene();values[3].append(SimpleNamespace(type_id=12,x=224,y=240))
        self.assertFalse(run(values)[0])

    def test_consumer_unit_model_can_explain_known_wrong_terrain_bg_label(self):
        values=scene();values[4]['cluster_centers'][1]=dict(r=80,g=100,b=140)
        self.assertFalse(run(values,False)[0])
        # Isolated consumer contract, NOT a substitute for real source teachers.
        model=SimpleNamespace(model=lambda *args:dict(valid=True,unit_prediction_only=True),predict=lambda *args:(20,30,60))
        with patch.object(CalibratedConflictQuery,'background_evidence',return_value=model):
            retired,proof=run(values)
        self.assertEqual(retired,{(1,224,240)})
        row=next(r for r in proof['rows'] if tuple(r['key'])==(1,224,240))
        self.assertTrue(row['original_BG_model_expert']);self.assertEqual(row['mean_bg_error'],0)
        self.assertFalse(row['counts'].get('unknown',0))

    def test_unexplained_rgb_cannot_become_empty_through_averaging(self):
        values=scene();values[4]['cluster_centers'][1]=dict(r=80,g=100,b=140)
        model=SimpleNamespace(model=lambda *args:dict(valid=True),predict=lambda *args:(0,0,0))
        with patch.object(CalibratedConflictQuery,'background_evidence',return_value=model):
            self.assertFalse(run(values)[0])

    def test_model_failure_retains_entire_legacy_decision(self):
        values=scene();values[4]['cluster_centers'][1]=dict(r=80,g=100,b=140)
        expected=run(values,False)[1]
        model=SimpleNamespace(model=lambda *args:dict(valid=False,reason='insufficient independent source'))
        with patch.object(CalibratedConflictQuery,'background_evidence',return_value=model):actual=run(values)[1]
        for old,new in zip(expected['rows'],actual['rows']):
            self.assertEqual({k:v for k,v in new.items() if k!='backdrop_model'},old)

    def test_original_source_detections_material_unchanged(self):
        values=scene();before=deepcopy(values[3:]);data=values[0].data
        run(values);self.assertEqual(values[3:],before);self.assertEqual(values[0].data,data)

    def test_portable_directions_polarity_hue_brightness_and_fractional_scale(self):
        transforms=(lambda c:c,lambda c:tuple(255-v for v in c),lambda c:(c[2],c[0],c[1]),lambda c:tuple(round(v*.25) for v in c))
        for direction,transform in enumerate(transforms):
            for scale in (1,1.25):
                with self.subTest(direction=direction,scale=scale):
                    self.assertEqual(run(scene(direction=direction,transform=transform,scale=scale))[0],{(1,224,240)})

    def test_option_requires_boolean(self):
        values=scene()
        for value in (0,1,None,'true',[]):
            with self.assertRaisesRegex(ValueError,'boolean'):run(values,value)

    def test_cropped_query_remains_unknown(self):
        image,room,frame,original,material=scene()
        from scripts.source_evidence_context import SourceEvidenceContext
        query=CalibratedConflictQuery(frame,SourceEvidenceContext(image,room,[]),original,material,None,None,None)
        with patch.object(query,'background_evidence',side_effect=AssertionError('Unknown cannot teach')):
            proof=query.query(SimpleNamespace(type_id=1,x=0,y=0))
        self.assertEqual(proof['abstained'],'incomplete original source footprint')
