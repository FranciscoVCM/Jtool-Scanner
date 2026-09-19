import random
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_color_evidence import QuantizedColorSlopeField
from jtool_scanner.spike_shape import VERTICES, terrain_covered_aliases


class CoveredColorEvidenceTests(unittest.TestCase):
    room = Box(0, 0, 800, 608)

    def rgb(self, image):
        return RGBImage(image.width, image.height, image.tobytes())

    def test_flat_colors_have_no_directional_evidence(self):
        for color in ((0, 0, 0), (220, 220, 220), (180, 0, 92)):
            with self.subTest(color=color):
                field = QuantizedColorSlopeField(self.rgb(Image.new("RGB", (800, 608), color)), self.room)
                for vertices in VERTICES.values():
                    self.assertEqual((0, 0), field.possible_side_scores(160, 160, vertices))

    def test_strong_scalar_contrast_alone_is_not_a_triangle_boundary(self):
        image = self.rgb(Image.new("RGB", (800, 608), (90, 90, 90)))
        with patch("jtool_scanner.spike_shape.SpikeShapeField") as constructor:
            field = constructor.return_value
            field.side_scores.return_value = (0, 0)
            field.contrast.return_value = .8
            field.score.return_value = 0
            for direction in VERTICES:
                self.assertEqual({(direction, 160, 160)}, terrain_covered_aliases(
                    image, self.room, [(direction, 160, 160)], [(160, 160)]))

    def test_direction_uncertainty_is_not_new_positive_evidence(self):
        image = self.rgb(Image.new("RGB", (800, 608), (90, 90, 90)))
        with patch("jtool_scanner.spike_shape.SpikeShapeField") as constructor, patch(
            "jtool_scanner.spike_shape.QuantizedColorSlopeField"
        ) as color:
            field = constructor.return_value
            field.side_scores.return_value = (0, 0)
            field.contrast.return_value = 0
            field.score.return_value = 0
            color.return_value.possible_side_scores.return_value = (1, 1)
            self.assertEqual({(3, 160, 160)}, terrain_covered_aliases(
                image, self.room, [(3, 160, 160)], [(160, 160)]))
            color.assert_not_called()

    def test_possible_short_color_boundary_preserves_contrast_candidate(self):
        image = self.rgb(Image.new("RGB", (800, 608), (90, 90, 90)))
        with patch("jtool_scanner.spike_shape.SpikeShapeField") as constructor, patch(
            "jtool_scanner.spike_shape.QuantizedColorSlopeField"
        ) as color:
            field = constructor.return_value
            field.side_scores.return_value = (0, 0)
            field.contrast.return_value = .8
            field.score.return_value = 0
            color.return_value.possible_side_scores.return_value = (4/12, 0)
            self.assertEqual(set(), terrain_covered_aliases(
                image, self.room, [(3, 160, 160)], [(160, 160)]))

    def test_actual_filled_triangles_across_contrast_polarity_and_scale(self):
        palettes = (((35,35,35),(230,230,230)), ((230,230,230),(35,35,35)),
                    ((220,230,240),(150,35,60)), ((90,90,90),(96,96,96)))
        for background, foreground in palettes:
            for scale in (1, 1.25, 1.5):
                image = Image.new("RGB", (800,608), background)
                draw = ImageDraw.Draw(image)
                spikes = []
                for index, (direction, vertices) in enumerate(VERTICES.items()):
                    x, y = 96 + index*160, 160
                    draw.polygon([(x+dx,y+dy) for dx,dy in vertices], fill=foreground)
                    spikes.append((direction,x,y))
                image = image.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
                with self.subTest(background=background,foreground=foreground,scale=scale):
                    self.assertEqual(set(), terrain_covered_aliases(
                        self.rgb(image), Box(0,0,image.width,image.height), spikes,
                        [(x,y) for _,x,y in spikes]))

    def test_quantization_compatibility_preserves_low_contrast_directions(self):
        image = Image.new("RGB", (800,608), (90,90,90))
        draw = ImageDraw.Draw(image)
        draw.polygon([(160+x,160+y) for x,y in VERTICES[3]],fill=(96,96,96))
        field = QuantizedColorSlopeField(self.rgb(image),self.room)
        self.assertGreater(max(field.possible_side_scores(160,160,VERTICES[3])),.25)
        # Repeated reads reuse evidence; they cannot change a result.
        self.assertEqual(field.possible_side_scores(160,160,VERTICES[3]),
                         field.possible_side_scores(160,160,VERTICES[3]))

    def test_uncertain_noise_does_not_override_absent_scalar_contrast(self):
        rng = random.Random(947)
        image = Image.new("RGB", (800,608), (90,90,90))
        draw = ImageDraw.Draw(image)
        for y in range(144,240):
            for x in range(144,240):
                if rng.random() < .5:
                    draw.point((x,y),fill=(96,96,96))
        spikes = [(direction,160,160) for direction in VERTICES]
        blocks = [(x,y) for x in range(144,240,32) for y in range(144,240,32)]
        self.assertEqual(set(spikes), terrain_covered_aliases(self.rgb(image),self.room,spikes,blocks))


if __name__ == "__main__":
    unittest.main()
