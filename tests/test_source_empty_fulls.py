"""Known-empty source is a contradiction, not a palette-only deletion rule."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_geometry_pipeline import source_proposals


class SourceEmptyFullTests(TestCase):
    old = (1, 160, 160)

    def scene(self, background=(0, 0, 0), foreground=(200, 200, 200), scale=1):
        raster = Image.new('RGB', (800, 608), background)
        material = dict(accepted=[], selected_clusters=[0], tip_votes={1: 3},
            background_back_votes={1: 0}, source_flat_accepted_cells=[],
            cluster_centers=[dict(zip(('r', 'g', 'b'), color))
                             for color in (foreground, background)])
        return raster, material, scale

    def run_rule(self, scene=None, extra=(), texture=False, glyphs=()):
        raster, material, scale = self.scene() if scene is None else scene
        if scale != 1:
            raster = raster.resize((round(800*scale), round(608*scale)), Image.Resampling.BILINEAR)
        image = RGBImage(raster.width, raster.height, raster.tobytes())
        room = Box(0, 0, raster.width, raster.height)
        detections = [SimpleNamespace(type_id=t, x=x, y=y) for t, x, y in (self.old, *extra)]
        spikes = [(d.type_id, d.x, d.y) for d in detections if 3 <= d.type_id <= 10]
        context = SourceEvidenceContext(image, room, spikes)
        library = context.glyph_library(image, room, spikes)
        library.anchors = list(glyphs)
        with patch('scripts.source_occupancy.pattern_cells', return_value=(set(), material)), \
             patch('scripts.source_geometry_pipeline.material_cells', return_value=(set(), material)), \
             patch('scripts.source_full_pose.SourceBlockLibrary') as blocks:
            blocks.return_value.teachers = []
            blocks.return_value.models = []
            blocks.return_value.support.return_value = dict(passed=texture)
            return source_proposals(image, room, detections, source_context=context)

    def test_complete_known_empty_original_full_is_retired_without_replacement(self):
        proposed, removed, proof = self.run_rule()
        self.assertEqual(removed, {self.old})
        self.assertEqual(proposed, set())
        self.assertEqual(proof['source_empty_full_proofs'][0]['key'], self.old)

    def test_empty_retirement_is_relative_across_palette_polarity_and_capture_scale(self):
        palettes = [((20, 30, 45), (190, 150, 90)), ((220, 230, 235), (70, 90, 110)),
                    ((0, 130, 0), (220, 10, 10)), ((35, 45, 50), (80, 105, 110))]
        for background, foreground in palettes:
            for scale in (1, 1.25):
                with self.subTest(background=background, foreground=foreground, scale=scale):
                    proposed, removed, _ = self.run_rule(self.scene(background, foreground, scale))
                    self.assertEqual(removed, {self.old})
                    self.assertFalse(proposed)

    def test_unknown_quarter_or_whole_interior_contamination_abstains(self):
        for box, color in (((176, 160, 191, 175), (100, 100, 100)),
                           ((172, 161, 179, 190), (200, 200, 200))):
            raster, material, scale = self.scene()
            ImageDraw.Draw(raster).rectangle(box, fill=color)
            # The second stripe avoids all margin4 quarter cores, but not margin1
            # whole-frame evidence: core samples alone cannot declare empty space.
            _, removed, _ = self.run_rule((raster, material, scale))
            self.assertFalse(removed)

    def test_source_foreground_water_and_all_marker_types_are_protected(self):
        for marker in (11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23):
            with self.subTest(marker=marker):
                _, removed, _ = self.run_rule(extra=((marker, 176, 160),))
                self.assertFalse(removed)
        raster, material, scale = self.scene()
        ImageDraw.Draw(raster).rectangle((160, 160, 191, 191), fill=(200, 200, 200))
        _, removed, _ = self.run_rule((raster, material, scale))
        self.assertFalse(removed)

    def test_raw_outline_and_whole_texture_are_independent_positives(self):
        raster, material, scale = self.scene()
        ImageDraw.Draw(raster).rectangle((160, 160, 191, 191), outline=(200, 200, 200))
        _, removed, _ = self.run_rule((raster, material, scale))
        self.assertFalse(removed)
        _, removed, _ = self.run_rule(texture=True)
        self.assertFalse(removed)

    def test_confirmed_glyph_pixels_protect_but_boundary_touch_is_not_overlap(self):
        _, removed, _ = self.run_rule(glyphs=[dict(key=(3, 160, 160), size=32)])
        self.assertFalse(removed)
        _, removed, _ = self.run_rule(glyphs=[dict(key=(3, 192, 160), size=32)])
        self.assertEqual(removed, {self.old})

    def test_independent_material_positive_and_original_minis_are_preserved(self):
        raster, material, scale = self.scene()
        material['accepted'] = [(160, 160)]
        _, removed, _ = self.run_rule((raster, material, scale))
        self.assertFalse(removed)
        proposed, removed, _ = self.run_rule(extra=((2, 160, 160), (7, 320, 320)))
        self.assertEqual(removed, {self.old})
        self.assertTrue(all(key[0] == 1 for key in removed))
        self.assertFalse(proposed)

    def test_no_roles_nonlattice_and_clipped_poses_never_guess_empty(self):
        raster, material, scale = self.scene()
        material['tip_votes'] = {}
        _, removed, _ = self.run_rule((raster, material, scale))
        self.assertFalse(removed)
        for key in ((1, 168, 160), (1, 784, 160), (1, 160, 592)):
            with self.subTest(key=key):
                self.old = key
                _, removed, _ = self.run_rule()
                self.assertFalse(removed)
