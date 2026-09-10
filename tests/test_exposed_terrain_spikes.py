import random
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage, load_png
from jtool_scanner.jmap import JMap
from jtool_scanner.scanner import Detection, _prune_terrain_covered_spike_aliases
from jtool_scanner.spike_shape import (
    SpikeShapeField, VERTICES, _block_union_area, _could_have_strong_slopes, terrain_exposed_aliases,
)


def scene(direction=3, *, triangle=False, scale=1, palette=((45,45,45),(220,220,220))):
    background, foreground = palette
    image = Image.new('RGB', (800,608), background)
    draw = ImageDraw.Draw(image)
    if triangle:
        draw.polygon([(160+px,160+py) for px,py in VERTICES[direction]], fill=foreground)
    block = {3:(160,176),4:(144,160),5:(176,160),6:(160,144)}[direction]
    bx,by = block
    draw.rectangle((bx,by,bx+31,by+31), fill=(125,110,100))
    # Texture in the predicted occluder must not stand in for exposed slopes.
    for offset in (0,8,16,24):
        draw.line((bx+offset,by,bx,by+offset),fill=(210,190,170),width=2)
    image = image.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    return RGBImage(image.width,image.height,image.tobytes()), block


class ExposedTerrainSpikeTests(unittest.TestCase):
    def reject(self, image, spikes, blocks):
        return terrain_exposed_aliases(image,Box(0,0,image.width,image.height),spikes,blocks)

    def test_absent_exposed_triangle_rejected_across_direction_and_scale(self):
        for direction in VERTICES:
            for scale in (1,1.25,1.5):
                with self.subTest(direction=direction,scale=scale):
                    image,block=scene(direction,scale=scale)
                    self.assertEqual({(direction,160,160)},self.reject(image,[(direction,160,160)],[block]))

    def test_genuine_occluded_triangles_preserved_across_palette_and_scale(self):
        palettes=(((45,45,45),(220,220,220)),
                  ((220,220,220),(45,45,45)),
                  ((90,110,180),(220,170,100)),
                  ((180,0,0),(0,92,0)))
        for direction in VERTICES:
            for scale in (1,1.25,1.5):
                for palette in palettes:
                    with self.subTest(direction=direction,scale=scale,palette=palette):
                        image,block=scene(direction,triangle=True,scale=scale,palette=palette)
                        self.assertEqual(set(),self.reject(image,[(direction,160,160)],[block]))

    def test_color_guard_is_needed_for_isoluminant_visible_triangle(self):
        image,block=scene(triangle=True,palette=((180,0,0),(0,92,0)))
        # Both colors round to L=54: a grayscale-only absence test is unsafe.
        self.assertEqual(Image.new('RGB',(1,1),(180,0,0)).convert('L').getpixel((0,0)),
                         Image.new('RGB',(1,1),(0,92,0)).convert('L').getpixel((0,0)))
        field=SpikeShapeField(image,Box(0,0,800,608))
        self.assertLess(field.score(160,160,3),.5)
        self.assertEqual(set(),self.reject(image,[(3,160,160)],[block]))

    def test_insufficient_observable_slope_is_preserved(self):
        image,_=scene()
        # A sideways occluder hides one complete side of this up hypothesis.
        self.assertEqual(set(),self.reject(image,[(3,160,160)],[(144,160)]))

    def test_no_partial_coverage_and_invalid_bounds_are_not_rejected(self):
        image,block=scene()
        for blocks in ([],[(160,184)],[(160,160)]):
            with self.subTest(blocks=blocks):
                self.assertEqual(set(),self.reject(image,[(3,160,160)],blocks))
        self.assertEqual(set(),self.reject(image,[(3,-8,160),(3,776,160)],[(0,176),(768,176)]))

    def test_block_union_matches_pixel_coverage_with_duplicates_gaps_and_offsets(self):
        rng=random.Random(43)
        for _ in range(60):
            blocks=[(rng.randrange(120,201),rng.randrange(120,201)) for _ in range(6)]
            blocks+=blocks[:2]
            expected=sum(any(bx<=x<bx+32 and by<=y<by+32 for bx,by in blocks)
                         for y in range(160,192) for x in range(160,192))
            self.assertEqual(expected,_block_union_area(160,160,blocks))

    def test_strong_single_side_and_nearby_supported_triangle_preserved(self):
        image,block=scene()
        with patch('jtool_scanner.spike_shape.SpikeShapeField') as constructor:
            field=constructor.return_value
            field.side_scores.return_value=(.8,.1)
            self.assertEqual(set(),self.reject(image,[(3,160,160)],[block]))
            field.side_scores.return_value=(.1,.1)
            field.contrast.side_effect=lambda x,y,d: .8 if (x,y)==(168,160) else 0
            field.score.side_effect=lambda x,y,d: 1 if (x,y)==(168,160) else 0
            with (patch('jtool_scanner.spike_shape._unsupported_exposed_slopes',return_value=True),
                  patch('jtool_scanner.spike_shape._could_have_strong_slopes',return_value=True)):
                self.assertEqual(set(),self.reject(image,[(3,160,160)],[block]))

    def test_cheap_slope_bound_never_excludes_a_strong_score(self):
        for direction in VERTICES:
            image=Image.new('RGB',(800,608),(35,35,35))
            ImageDraw.Draw(image).polygon([(160+x,160+y) for x,y in VERTICES[direction]],fill=(220,220,220))
            field=SpikeShapeField(RGBImage(800,608,image.tobytes()),Box(0,0,800,608))
            for dx in (-8,0,8):
                for dy in (-8,0,8):
                    bound=_could_have_strong_slopes(field,160+dx,160+dy,direction)
                    if field.score(160+dx,160+dy,direction)>=.9:
                        self.assertTrue(bound)
            self.assertTrue(_could_have_strong_slopes(field,160,160,direction))

    def test_final_arbitration_preserves_non_full_spike_objects(self):
        image,block=scene()
        detections=[Detection('spike_up',3,160,160,.8,Box(160,160,32,32)),
                    Detection('block',1,*block,.8,Box(*block,32,32)),
                    Detection('mini_spike_up',7,160,176,.8,Box(160,176,16,16)),
                    Detection('save',12,160,160,.8,Box(160,160,32,32))]
        self.assertEqual(detections[1:],_prune_terrain_covered_spike_aliases(detections,image,Box(0,0,800,608)))

    def test_exact_partial_overlap_fixture_spikes_are_preserved(self):
        fixtures=Path(__file__).resolve().parents[1]/'fixtures'/'block_spike'
        # Recorded conflicting block hypotheses, not assertions of true terrain.
        # All nine spike tuples are independently verified by committed JMaps.
        cases={
            'irkara-nr-flames': [((3,496,416),(480,416)),((5,432,32),(448,32))],
            'k3-ex-hades': [((3,256,192),(256,208)),((3,304,384),(288,384)),
                            ((4,512,304),(512,288)),((6,224,16),(224,0)),
                            ((6,256,16),(256,0)),((6,288,16),(288,0))],
            'cn2-5-jumprefresh': [((5,256,544),(272,544))],
        }
        for name,conflicts in cases.items():
            source=load_png(fixtures/f'{name}-game.png')
            truth={(o.type_id,o.x,o.y) for o in JMap.from_file(fixtures/f'{name}.jmap').objects}
            for scale in (1,1.25):
                image=source
                if scale!=1:
                    resized=Image.frombytes('RGB',(source.width,source.height),source.data)
                    resized=resized.resize((round(source.width*scale),round(source.height*scale)),Image.Resampling.BILINEAR)
                    image=RGBImage(resized.width,resized.height,resized.tobytes())
                for spike,block in conflicts:
                    with self.subTest(fixture=name,spike=spike,scale=scale):
                        self.assertIn(spike,truth)
                        self.assertEqual(set(),self.reject(image,[spike],[block]))


if __name__=='__main__':
    unittest.main()
