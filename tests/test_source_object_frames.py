"""Independent framed bodies across palette, background and capture changes."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_object_frames import SourceObjectFrames
from scripts.source_sampling import SourceFrame

PALETTES = (((25,35,45),(205,225,210)), ((215,205,200),(40,30,55)), ((0,130,0),(255,0,0)))


def scene(palette=0, background=0, scale=1., count=6, flat=False):
    core, border = PALETTES[palette]
    image = Image.new('RGB', (800,608))
    draw = ImageDraw.Draw(image)
    for y in range(608):
        for x in range(0,800,8):
            delta = (0 if background == 0 else round(70*x/800+30*y/608)-50 if background == 1
                     else 45 if (x//24+y//40)%2 else -35)
            draw.rectangle((x,y,x+7,y), fill=(max(0,min(255,110+delta)),
                max(0,min(255,90-delta//2)), max(0,min(255,100+delta//3))))
    teachers = [(1,96+96*i,160) for i in range(count)]
    true = set(teachers) | {(1,672,160),(1,448,352),(1,512,352),(1,480,320),(1,480,384),(1,320,432)}
    def tile(x,y,border_only=False):
        if not border_only:
            draw.rectangle((x,y,x+31,y+31),fill=core)
        draw.rectangle((x,y,x+31,y+31),outline=border,width=2)
        if not flat and not border_only:
            rivet = tuple(round(.95*a+.05*b) for a,b in zip(core,border))
            for dx,dy in ((5,5),(25,5),(5,25),(25,25)):
                draw.rectangle((x+dx,y+dy,x+dx+1,y+dy+1),fill=rivet)
    for _,x,y in sorted(true):
        tile(x,y)
    tile(160,352,border_only=True)
    # Three cosmetic strokes over unchanged background are not a filled body.
    draw.line((320,383,320,352,351,352,351,383),fill=border,width=2)
    # Conversely, a solid tile with a missing cosmetic bottom stroke stays solid.
    draw.rectangle((323,461,348,463),fill=core)
    false = {(1,160,352),(1,320,352),(1,480,352),(1,704,416),(1,784,592)}
    raster = image.resize((round(800*scale),round(608*scale)),Image.Resampling.BILINEAR)
    frame = SourceFrame(RGBImage(raster.width,raster.height,raster.tobytes()),Box(0,0,raster.width,raster.height))
    original = [SimpleNamespace(type_id=t,x=x,y=y) for t,x,y in teachers]
    original.append(SimpleNamespace(type_id=1,x=480,y=352))
    return frame,original,true,false


class SourceObjectFrameTests(TestCase):
    def check_palette(self,palette):
        for background in (0,1,2):
            for scale in (1.,1.25,.75):
                with self.subTest(palette=palette,background=background,scale=scale):
                    frame,original,true,false = scene(palette,background,scale)
                    before = deepcopy(original)
                    source = frame.original_snapshot().data
                    evidence = SourceObjectFrames(frame,original)
                    models = deepcopy(evidence.models)
                    self.assertTrue(models)
                    for _,x,y in sorted(true):
                        proof = evidence.support(x,y)
                        self.assertTrue(proof['passed'],(x,y))
                        for row in proof['proof']:
                            self.assertEqual(len(row['original_teachers']),3)
                            self.assertFalse(any(abs(x-t[1]) < 32 and abs(y-t[2]) < 32 for t in row['original_teachers']))
                    for _,x,y in false:
                        self.assertFalse(evidence.support(x,y)['passed'],(x,y))
                    self.assertEqual(evidence.models,models)
                    self.assertEqual(original,before)
                    self.assertEqual(frame.original_snapshot().data,source)

    def test_bright_frames(self):
        self.check_palette(0)

    def test_dark_frames(self):
        self.check_palette(1)

    def test_near_isoluminant_frames(self):
        self.check_palette(2)

    def test_flat_body_requires_closed_owned_frame(self):
        frame,original,true,false = scene(0,2,1.25,flat=True)
        evidence = SourceObjectFrames(frame,original)
        for _,x,y in true:
            self.assertTrue(evidence.support(x,y)['passed'],(x,y))
        for _,x,y in false:
            self.assertFalse(evidence.support(x,y)['passed'],(x,y))

    def test_duplicate_or_two_teachers_are_insufficient(self):
        frame,original,_,_ = scene(count=2)
        evidence = SourceObjectFrames(frame,original*4)
        self.assertEqual(evidence.models,[])
        self.assertFalse(evidence.support(672,160)['passed'])

    def test_fixture_pixels_distinguish_open_decoration_and_solid_cosmetics(self):
        frame,_,true,false = scene(1)
        self.assertEqual(frame.original_pixel(336,368),(110,90,100))
        self.assertEqual(frame.original_pixel(336,463),PALETTES[1][0])
        self.assertIn((1,320,432),true)
        self.assertIn((1,320,352),false)
