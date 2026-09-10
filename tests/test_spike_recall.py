import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage, load_png
from jtool_scanner.jmap import JMap
from jtool_scanner.scanner import Detection, _recover_directed_material_spikes
from jtool_scanner.spike_shape import corroborated_proposals, VERTICES


SEEDS = [(3, 240, 256), (3, 320, 224), (3, 400, 256), (3, 432, 336)]


def scene(objects, foreground=(220, 220, 220), background=(35, 35, 35), scale=1):
    image = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(image)
    for direction, x, y in objects:
        draw.polygon([(x + px, y + py) for px, py in VERTICES[direction]], fill=foreground)
    image = image.resize((round(800 * scale), round(608 * scale)), Image.Resampling.BILINEAR)
    return RGBImage(image.width, image.height, image.tobytes())


def recover(image, spikes):
    return corroborated_proposals(image, Box(0, 0, image.width, image.height), spikes)


class SpikeRecallTests(unittest.TestCase):
    def test_missing_triangle_has_independent_geometry_across_directions_scales_and_polarities(self):
        for foreground, background in (((220,220,220),(35,35,35)),
                                       ((35,35,35),(220,220,220)),
                                       ((90,90,90),(150,150,150)),
                                       ((210,170,95),(65,35,90))):
            for scale in (1, 1.25, 1.5):
                for direction in VERTICES:
                    with self.subTest(direction=direction, scale=scale, foreground=foreground):
                        target = (direction, 320, 320)
                        image = scene([*SEEDS, target], foreground, background, scale)
                        self.assertEqual([target], recover(image, SEEDS))

    def test_existing_or_nearby_geometry_is_not_duplicated_or_retyped(self):
        target = (3,320,320)
        image = scene([*SEEDS,target])
        for occupied in (target, (3,328,320), (6,320,320)):
            with self.subTest(occupied=occupied):
                self.assertEqual([], recover(image, [*SEEDS,occupied]))

    def test_duplicate_or_too_few_witnesses_do_not_bootstrap_a_recovery(self):
        image = scene([*SEEDS,(3,320,320)])
        for seeds in ([],SEEDS[:2],SEEDS[:1]*5):
            with self.subTest(seeds=seeds):
                self.assertEqual([],recover(image,seeds))

    def test_shifted_hypotheses_of_two_objects_are_not_four_independent_witnesses(self):
        seeds=[(3,240,256),(3,400,256)]
        image=scene([*seeds,(3,320,320)])
        aliases=[*seeds,(3,240,248),(3,400,248)]
        self.assertEqual([],recover(image,aliases))

    def test_background_triangle_gap_is_not_a_new_spike(self):
        image = scene([*SEEDS,(3,304,320),(3,336,320)])
        self.assertNotIn((6,320,320),recover(image,SEEDS))

    def test_small_triangles_and_brick_texture_do_not_make_a_full_spike(self):
        image = scene(SEEDS)
        pil = Image.frombytes('RGB',(image.width,image.height),image.data)
        draw = ImageDraw.Draw(pil)
        for x in (320,336):
            draw.polygon([(x+px//2,320+py//2) for px,py in VERTICES[3]],fill=(220,220,220))
        for y in range(360,401,8):
            draw.line((280,y,400,y),fill=(180,180,180))
            for x in range(280+(y%16),401,16):
                draw.line((x,y,x,y+8),fill=(180,180,180))
        self.assertEqual([],recover(RGBImage(800,608,pil.tobytes()),SEEDS))

    def test_ambiguous_origin_or_direction_abstains(self):
        image = scene([*SEEDS,(3,320,320)])
        with patch('jtool_scanner.spike_shape._could_have_strong_slopes',return_value=True), \
                patch('jtool_scanner.spike_shape.SpikeShapeField') as constructor:
            field=constructor.return_value
            field.score.return_value=1
            field.localized_score.return_value=1
            field.contrast.return_value=.8
            self.assertEqual([],recover(image,SEEDS))

    def test_conflicting_seed_polarities_cannot_be_resolved_by_the_last_duplicate(self):
        image=scene([*SEEDS,(3,320,320)])
        conflicting=[item for _,x,y in SEEDS for item in ((3,x,y),(6,x,y),(3,x,y))]
        with patch('jtool_scanner.spike_shape.SpikeShapeField') as constructor:
            field=constructor.return_value
            field.score.return_value=1
            field.contrast.side_effect=lambda x,y,d: .8 if d==3 else -.8
            self.assertEqual([],recover(image,conflicting))

    def test_incomplete_localized_contour_cannot_add_an_object(self):
        image=scene([*SEEDS,(3,320,320)])
        with patch('jtool_scanner.spike_shape.SpikeShapeField') as constructor, \
                patch('jtool_scanner.spike_shape._could_have_strong_slopes',return_value=True):
            field=constructor.return_value
            field.score.return_value=1
            field.contrast.return_value=.8
            field.localized_score.return_value=11/12
            self.assertEqual([],recover(image,SEEDS))

    def test_isoluminant_geometry_is_not_invented_from_luminance_evidence(self):
        image=scene([*SEEDS,(3,320,320)],(180,0,0),(0,92,0))
        self.assertEqual([],recover(image,SEEDS))

    def test_recovery_retains_every_existing_object_and_uses_source_box(self):
        image=scene([])
        detection=Detection('save',12,40,48,.8,Box(40,48,32,32))
        with patch('jtool_scanner.scanner.corroborated_proposals',return_value=[(3,320,320)]):
            result=_recover_directed_material_spikes([detection],image,Box(16,8,400,304))
        self.assertIs(result[0],detection)
        self.assertEqual((3,320,320),(result[1].type_id,result[1].x,result[1].y))
        self.assertEqual(Box(176,168,16,16),result[1].image_box)

    def test_committed_flames_reference_missing_spikes_are_recoverable(self):
        fixtures=Path(__file__).resolve().parents[1]/'fixtures/block_spike'
        image=load_png(fixtures/'irkara-nr-flames-game.png')
        truth={(o.type_id,o.x,o.y) for o in JMap.from_file(fixtures/'irkara-nr-flames.jmap').objects}
        missing={(3,288,368),(3,320,368)}
        self.assertLessEqual(missing,truth)
        spikes=sorted(obj for obj in truth-missing if obj[0] in VERTICES)
        for scale in (1,1.25):
            with self.subTest(scale=scale):
                pil=Image.frombytes('RGB',(image.width,image.height),image.data)
                pil=pil.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.BILINEAR)
                actual=set(recover(RGBImage(pil.width,pil.height,pil.tobytes()),spikes))
                self.assertLessEqual(missing,actual)
                self.assertLessEqual(actual,truth)


if __name__ == '__main__':
    unittest.main()
