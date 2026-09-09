import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import terrain_covered_aliases


class TerrainSpikeArbitrationTests(unittest.TestCase):
    room = Box(0, 0, 800, 608)

    def image(self, triangle=False):
        image = Image.new('RGB', (800,608), (80,80,80))
        if triangle:
            ImageDraw.Draw(image).polygon([(176,160),(160,191),(191,191)], fill=(240,240,240))
        return RGBImage(800,608,image.tobytes())

    def test_flat_fully_covered_candidate_rejected(self):
        self.assertEqual({(3,160,160)}, terrain_covered_aliases(self.image(),self.room,[(3,160,160)],[(160,160)]))

    def test_real_triangle_survives_false_block_hypothesis(self):
        self.assertEqual(set(), terrain_covered_aliases(self.image(True),self.room,[(3,160,160)],[(160,160)]))

    def test_offset_union_and_gap(self):
        spike=[(3,176,160)]
        self.assertEqual(set(spike),terrain_covered_aliases(self.image(),self.room,spike,[(160,160),(192,160)]))
        self.assertEqual(set(),terrain_covered_aliases(self.image(),self.room,spike,[(160,160),(193,160)]))

    def test_partial_or_duplicate_coverage_is_not_complete(self):
        self.assertEqual(set(),terrain_covered_aliases(self.image(),self.room,[(3,176,160)],[(160,160)]*3))

    def test_strong_single_slope_survives(self):
        with patch('jtool_scanner.spike_shape.SpikeShapeField') as field:
            field.return_value.side_scores.return_value=(1,.1)
            self.assertEqual(set(),terrain_covered_aliases(self.image(),self.room,[(3,160,160)],[(160,160)]))

    def test_nearby_same_direction_triangle_preserves_uncertain_origin(self):
        with patch('jtool_scanner.spike_shape.SpikeShapeField') as field:
            field.return_value.side_scores.return_value=(.1,.2)
            field.return_value.score.side_effect=lambda x,y,d: 1 if (x,y)==(168,144) else 0
            field.return_value.contrast.side_effect=lambda x,y,d: .8 if (x,y)==(168,144) else 0
            self.assertEqual(set(),terrain_covered_aliases(self.image(),self.room,[(3,160,160)],[(160,160)]))

    def test_cropped_boundaries_are_preserved(self):
        self.assertEqual(set(),terrain_covered_aliases(self.image(),self.room,[(3,-8,160)],[(-8,160)]))

    def test_real_triangles_preserved_across_polarity_color_and_scale(self):
        palettes = (((30,30,30),(230,230,230)),
                    ((230,230,230),(30,30,30)),
                    ((220,230,240),(150,35,60)))
        vertices = (((16,0),(0,31),(31,31)),
                    ((31,16),(0,0),(0,31)),
                    ((0,16),(31,0),(31,31)),
                    ((16,31),(0,0),(31,0)))
        for background, foreground in palettes:
            for scale in (1, 1.5):
                with self.subTest(background=background, scale=scale):
                    image = Image.new('RGB',(800,608),background)
                    draw = ImageDraw.Draw(image)
                    spikes = []
                    blocks = []
                    for index, points in enumerate(vertices):
                        x,y = 160+index*96,160
                        draw.polygon([(x+px,y+py) for px,py in points],fill=foreground)
                        spikes.append((3+index,x,y))
                        blocks.append((x,y))
                    image = image.resize((int(800*scale),int(608*scale)),Image.Resampling.BILINEAR)
                    rgb = RGBImage(image.width,image.height,image.tobytes())
                    self.assertEqual(set(),terrain_covered_aliases(
                        rgb,Box(0,0,image.width,image.height),spikes,blocks))
