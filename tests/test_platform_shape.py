from pathlib import Path
import unittest

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.platform_shape import default_platform_shape_score
from jtool_scanner.scanner import _detect_platforms, _prune_bright_room_platform_impostors


class PlatformShapeTests(unittest.TestCase):
    def image(self, *, background=(110, 70, 160), gain=1., bias=0,
              scale=1., phase=0, invert=False):
        path = Path(__file__).resolve().parents[1] / 'jtool_scanner/assets/jtool-pat-default/detection/platform-default-frame.png'
        sprite = Image.open(path).convert('L')
        sprite = sprite.point(lambda v: max(0, min(255, int((255-v if invert else v)*gain+bias))))
        image = Image.new('RGB', (800,608), background)
        # A contiguous row at the lower boundary has no below-sprite context.
        for x in (320,352,384):
            image.paste(sprite, (x,592+phase))
        image = image.resize((round(800*scale),round(608*scale)), Image.Resampling.BILINEAR)
        return RGBImage(image.width,image.height,image.tobytes())

    def test_shape_survives_background_brightness_and_capture_scale(self):
        for background,gain,bias,scale,phase in (
            ((110,70,160),1.,0,1.,0),
            ((240,240,240),1.7,30,1.23,1),
            ((5,5,5),.7,10,1.5,0),
            ((20,160,220),1.,80,1.,2),
        ):
            with self.subTest(background=background, scale=scale,phase=phase):
                im=self.image(background=background,gain=gain,bias=bias,scale=scale,phase=phase)
                room=Box(0,0,im.width,im.height)
                for x in (320,352,384):
                    self.assertGreaterEqual(default_platform_shape_score(im,room,x,592),.8)
                self.assertLess(default_platform_shape_score(im,room,336,592),.8)

    def test_flat_and_inverted_patterns_are_not_matches(self):
        im=self.image(invert=True)
        room=Box(0,0,800,608)
        self.assertLess(default_platform_shape_score(im,room,320,592),.8)
        self.assertEqual(default_platform_shape_score(im,room,64,64),0.)
        self.assertEqual(default_platform_shape_score(im,room,784,592),0.)

    def test_detector_recovers_three_boundary_platforms_without_half_phase_alias(self):
        im=self.image()
        result=_detect_platforms(im,Box(0,0,800,608),[])
        self.assertEqual([(d.x,d.y) for d in result],[(320,592),(352,592),(384,592)])
        self.assertEqual(_prune_bright_room_platform_impostors(result,im,Box(0,0,800,608)),result)

    def test_floor_strips_grids_text_and_triangles_fail_shape_gate(self):
        im=Image.new('RGB',(800,608),(180,180,180))
        draw=ImageDraw.Draw(im)
        draw.rectangle((64,64,159,79),fill=(60,60,60),outline='black',width=2)
        for x in range(192,288,16):
            draw.rectangle((x,64,x+15,79),outline='black',width=2)
        draw.text((320,64),'93 -45',fill='black')
        draw.polygon(((384,79),(400,64),(415,79)),fill=(60,60,60),outline='black')
        source=RGBImage(800,608,im.tobytes())
        for x in range(48,432,16):
            with self.subTest(x=x):
                self.assertLess(default_platform_shape_score(source,Box(0,0,800,608),x,64),.8)


if __name__ == '__main__':
    unittest.main()
