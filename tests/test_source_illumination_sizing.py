"""Local RGB corroboration retains known-empty and unknown/real-object boundaries."""
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw
from types import SimpleNamespace

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_geometry_pipeline import source_proposals


class SourceIlluminationSizingTests(TestCase):
    old = (1,160,160)

    def run_scene(self, palette=0, scale=1., anchors=((128,96),(320,160),(448,320)),
                  extra=(), feature=None, shift_scale=1):
        foreground,background,shift = [
            ((180,150,100),(20,30,40),(45,35,18)),
            ((255,255,255),(100,100,100),(41,41,41)),
            ((0,0,0),(155,155,155),(-41,-41,-41)),
            ((0,130,0),(255,0,0),(-69,35,0))][palette]
        raster = Image.new('RGB',(800,608));pixels = raster.load()
        for y in range(608):
            for x in range(800):
                delta = (.004*x+.003*y,.006*x+.002*y,.002*x+.005*y)
                pixels[x,y] = tuple(max(0,min(255,round(b+shift_scale*s+d)))
                                    for b,s,d in zip(background,shift,delta))
        draw = ImageDraw.Draw(raster)
        for x,y in anchors:
            draw.polygon([(x,y+31),(x+16,y),(x+31,y+31)],fill=foreground)
        if feature=='solid':draw.rectangle((160,160,191,191),fill=foreground)
        if feature=='outline':draw.rectangle((160,160,191,191),outline=foreground)
        if feature=='contaminated':draw.rectangle((172,161,174,190),fill=foreground)
        if feature=='unknown':draw.rectangle((160,160,191,191),fill=tuple(
            round((a+b)/2) for a,b in zip(foreground,background)))
        raster = raster.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
        image = RGBImage(raster.width,raster.height,raster.tobytes())
        room = Box(0,0,image.width,image.height)
        detections = [SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in
                      (self.old,*[(3,x,y) for x,y in anchors],*extra)]
        # Isolate the mean-colour reconciliation from upstream role voting.
        # The independent local witnesses themselves use real source contours,
        # bodies and exterior samples, not pre-supplied predictor answers.
        material = dict(accepted=[],selected_clusters=[0],tip_votes={1:3},
            background_back_votes={1:0},source_flat_accepted_cells=[],
            cluster_centers=[dict(zip(('r','g','b'),c)) for c in (foreground,background)])
        with patch('scripts.source_occupancy.pattern_cells',return_value=(set(),material)), \
             patch('scripts.source_geometry_pipeline.material_cells',return_value=(set(),material)), \
             patch('scripts.source_full_pose.SourceBlockLibrary') as texture:
            texture.return_value.teachers=[];texture.return_value.models=[]
            texture.return_value.support.return_value=dict(passed=False)
            return source_proposals(image,room,detections)

    def test_affine_bg_corroboration_across_rgb_polarity_capture_scale(self):
        for palette in range(4):
            for scale in (1.,1.25):
                with self.subTest(palette=palette,scale=scale):
                    _,removed,proof = self.run_scene(palette,scale)
                    self.assertIn(self.old,removed)
                    self.assertTrue(any(p['passed'] for p in
                        proof['source_sizing']['local_sizing_background_proofs']))

    def test_fewer_than_three_independent_source_regions_abstain(self):
        _,removed,_ = self.run_scene(anchors=((128,96),(320,160)))
        self.assertNotIn(self.old,removed)

    def test_degenerate_original_source_positions_abstain(self):
        _,removed,_ = self.run_scene(anchors=((128,96),(320,96),(448,96)))
        self.assertNotIn(self.old,removed)

    def test_real_solid_outline_contamination_unknown_are_not_empty(self):
        for feature in ('solid','outline','contaminated','unknown'):
            with self.subTest(feature=feature):
                _,removed,_ = self.run_scene(feature=feature)
                self.assertNotIn(self.old,removed)

    def test_marker_water_and_original_mini_protections_remain(self):
        for marker in (12,13,14):
            with self.subTest(marker=marker):
                _,removed,_ = self.run_scene(extra=((marker,176,160),))
                self.assertNotIn(self.old,removed)
        _,removed,_ = self.run_scene(extra=((2,160,160),))
        self.assertNotIn((2,160,160),removed)

    def test_global_mean_already_valid_does_not_build_extra_local_model(self):
        with patch('scripts.source_occupancy.SourceLocalBackground',create=True) as model:
            _,removed,_ = self.run_scene(shift_scale=0)
            self.assertIn(self.old,removed)
            model.assert_not_called()

    def test_valid_but_wrong_local_prediction_does_not_prove_empty(self):
        with patch('scripts.source_occupancy.SourceLocalBackground',create=True) as model:
            model.return_value.predict.return_value=dict(valid=True,prediction=(255,0,255))
            _,removed,_ = self.run_scene()
            self.assertNotIn(self.old,removed)

    def test_bg_pixel_membership_is_not_relaxed_by_local_prediction(self):
        with patch('scripts.source_occupancy.SourceLocalBackground',create=True) as model:
            model.return_value.predict.return_value=dict(valid=True,prediction=(75,75,75))
            _,removed,_ = self.run_scene(feature='unknown')
            self.assertNotIn(self.old,removed)
            # Other lattice cells may consult the model; the contaminated frame
            # itself still cannot enter the known-empty retirement path.
