"""Source occupancy and joint assembly protect positive coverage and uncertainty."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_geometry_pipeline import joint_proposals, source_proposals
from scripts.source_occupancy import footprint, source_size_repair


def calibration():
    return dict(selected_clusters=[0], tip_votes={1: 3}, background_back_votes={1: 0},
                cluster_centers=[dict(r=v, g=v, b=v) for v in (200, 0)], accepted=[])


class SourceGeometryPipelineTests(TestCase):
    def setUp(self):
        raster = Image.new('RGB', (800, 608))
        ImageDraw.Draw(raster).rectangle((160, 144, 175, 207), fill=(200, 200, 200))
        self.image = RGBImage(800, 608, raster.tobytes())
        self.room = Box(0, 0, 800, 608)
        self.detections = [SimpleNamespace(type_id=1, x=160, y=160)]

    def run_size(self, image=None, detections=None):
        with patch('scripts.source_occupancy.pattern_cells', return_value=(set(), calibration())):
            return source_size_repair(self.image if image is None else image, self.room,
                                      self.detections if detections is None else detections)

    def test_bg_corridor_corrects_full_and_keeps_all_true_source_pixels(self):
        proposed, removed, diag = self.run_size()
        self.assertEqual(removed, {(1, 160, 160)})
        self.assertEqual(proposed, {(2, 160, y) for y in (144, 160, 176, 192)})
        supplied = set().union(*(footprint(k) for k in proposed))
        required = footprint((2, 160, 160)) | footprint((2, 160, 176))
        self.assertTrue(required <= supplied)
        self.assertTrue(diag['all_disproved_foreground_coverage_retained'])

    def test_unknown_source_quarter_prevents_retirement(self):
        raster = Image.frombytes('RGB', (800, 608), self.image.data)
        ImageDraw.Draw(raster).rectangle((176, 160, 191, 175), fill=(100, 100, 100))
        _, removed, _ = self.run_size(RGBImage(800, 608, raster.tobytes()))
        self.assertEqual(removed, set())

    def test_nonterrain_anchor_and_original_mini_are_not_removed(self):
        original = self.detections + [SimpleNamespace(type_id=11, x=160, y=160), SimpleNamespace(type_id=2, x=160, y=160)]
        _, removed, _ = self.run_size(detections=original)
        self.assertEqual(removed, set())

    def test_no_calibration_never_guesses_occupancy(self):
        with patch('scripts.source_occupancy.pattern_cells', return_value=(set(), {})):
            proposed, removed, proof = source_size_repair(self.image, self.room, self.detections)
        self.assertEqual(proposed, set())
        self.assertEqual(removed, set())
        self.assertEqual(proof['reason'], 'no independent source calibration')

    def test_independent_complete_source32_recovery_without_correction(self):
        raster = Image.new('RGB', (800, 608))
        ImageDraw.Draw(raster).rectangle((160, 160, 191, 191), fill=(200, 200, 200))
        proposed, removed, diag = self.run_size(RGBImage(800, 608, raster.tobytes()), detections=[])
        self.assertEqual(proposed, {(1, 160, 160)})
        self.assertEqual(removed, set())
        self.assertEqual(diag['affected_source_cells'], [])
        self.assertTrue(diag['complete_source32_recovery'])

    def test_joint_keeps_intrinsic_and_abstains_from_duplicate_supplemental(self):
        intrinsic = {(160, 160)}
        material = intrinsic | {(176, 160), (320, 320)}
        with patch('scripts.source_geometry_pipeline.source_size_repair', return_value=(set(), set(), {
            'source_calibration': {'accepted': sorted(intrinsic)}})), \
             patch('scripts.source_geometry_pipeline.material_cells', return_value=(material, {'accepted': sorted(material)})):
            proposed, removed, proof = joint_proposals(self.image, self.room, self.detections)
        self.assertEqual(proposed, {(2, 160, 160), (2, 320, 320)})
        self.assertEqual(proof['supplemental_duplicate_coverage_abstained'], [(176, 160)])
        self.assertEqual(removed, set())

    def test_flat_water_occluded_size_abstains_without_deleting_original_mini(self):
        original_mini = (2, 160, 160)
        new_mini = (2, 176, 160)
        detections = self.detections + [SimpleNamespace(type_id=14, x=160, y=160),
                                      SimpleNamespace(type_id=2, x=160, y=160)]
        material = {'accepted': [(160, 160), (176, 160)], 'source_flat_accepted_cells': [(160, 160), (176, 160)]}
        diag = {'source_material': material}
        with patch('scripts.source_geometry_pipeline.joint_proposals', return_value=({original_mini, new_mini}, set(), diag)), \
             patch('scripts.source_geometry_pipeline.refit_full_poses', side_effect=lambda i,r,d,p,x,m,**kw:(p,x,{})), \
             patch('scripts.source_geometry_pipeline.agree_new_fulls', side_effect=lambda i,r,d,p,x,c,f,**kw:(p,{})):
            proposed, removed, proof = source_proposals(self.image, self.room, iter(detections))
        self.assertEqual(proposed, {original_mini})
        self.assertEqual(removed, set())
        self.assertEqual(proof['new_flat_mini_identity_under_occluded_full_abstained'], [new_mini])

    def test_textured_water_overlap_keeps_independent_mini(self):
        key = (2, 176, 160)
        detections = self.detections + [SimpleNamespace(type_id=14, x=160, y=160)]
        diag = {'source_material': {'accepted': [(176, 160)], 'source_flat_accepted_cells': []}}
        with patch('scripts.source_geometry_pipeline.joint_proposals', return_value=({key}, set(), diag)), \
             patch('scripts.source_geometry_pipeline.refit_full_poses', side_effect=lambda i,r,d,p,x,m,**kw:(p,x,{})), \
             patch('scripts.source_geometry_pipeline.agree_new_fulls', side_effect=lambda i,r,d,p,x,c,f,**kw:(p,{})):
            proposed, removed, proof = source_proposals(self.image, self.room, detections)
        self.assertEqual(proposed, {key})
        self.assertEqual(proof['new_flat_mini_identity_under_occluded_full_abstained'], [])

    def test_source_pipeline_inputs_remain_unchanged(self):
        original = deepcopy(self.detections)
        pixels = self.image.data
        proposed, removed, _ = self.run_size()
        self.assertEqual(self.detections, original)
        self.assertIs(self.image.data, pixels)
