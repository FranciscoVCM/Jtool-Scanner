"""Portable source SAVE-frame refinement; references and private corpora are not inputs."""
from dataclasses import asdict
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
from copy import deepcopy
from dataclasses import replace
from scripts import source_save_frames as prototype
from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_sampling import SourceFrame

observations=[]


def scene(*,scale=(1,1),transform=lambda c:c,style='canonical',side='left',origin=(160,160),
          offset=(0,0),header_delta=0,body_width=8,kind='save'):
    raster=Image.new('RGB',(800,608),(130,90,190))
    x,y=origin
    with Image.open(ROOT/'jtool_scanner/assets/jtool-pat-default/save-frame0.png') as asset:
        rgba=asset.convert('RGBA')
        raster.paste(rgba,(x,y),rgba)
    draw=ImageDraw.Draw(raster)
    if style in ('styled','blank','rail') or header_delta:
        draw.rectangle((x+2,y,x+29,y+9),fill=(130,90,190))
        top=y+1+header_delta
        if style=='rail':
            draw.line((x+3,top,x+28,top),fill=(0,0,0))
        else:
            draw.rectangle((x+3,top,x+28,top+7),fill=(0,0,0))
            if style!='blank':
                letters=(('111','100','111','001','111'),('010','101','111','101','101'),
                         ('101','101','101','101','010'),('111','100','110','100','111'))
                for i,glyph in enumerate(letters):
                    for j,row in enumerate(glyph):
                        for k,value in enumerate(row):
                            if value=='1':draw.point((x+5+i*5+k,top+1+j),fill=(255,255,255))
            else:
                draw.rectangle((x+4,top+1,x+27,top+6),fill=(255,255,255))
        # The frame is intentionally connected to the body, like the real case.
        draw.line((x+3,top+7,x+3,y+12),fill=(0,0,0))
        draw.line((x+28,top+7,x+28,y+12),fill=(0,0,0))
    if style=='flat':
        raster=Image.new('RGB',(800,608),(92,92,92))
    if style=='gradient':
        draw=ImageDraw.Draw(raster)
        for yy in range(608):draw.line((0,yy,799,yy),fill=(30+yy//8,40+yy//8,50+yy//8))
    if transform is not None:
        pixels = raster.tobytes()
        raster = Image.frombytes('RGB', raster.size, b''.join(
            bytes(transform((pixels[i], pixels[i+1], pixels[i+2])))
            for i in range(0, len(pixels), 3)))
    sx,sy=scale
    captured=raster.resize((round(800*sx),round(608*sy)),Image.Resampling.BILINEAR)
    source=Image.new('RGB',(captured.width+2*offset[0],captured.height+2*offset[1]),(17,17,17))
    source.paste(captured,offset)
    room=Box(*offset,captured.width,captured.height)
    physical=RGBImage(source.width,source.height,source.tobytes())
    frame=SourceFrame(physical,room)
    fragment_x=x+3 if side=='left' else x+21
    box=Box(offset[0]+round(fragment_x*captured.width/800),offset[1]+round((y+12)*captured.height/608),
            max(1,round(body_width*captured.width/800)),max(1,round(16*captured.height/608)))
    detection=scanner.Detection(kind,12,x+(-8 if side=='left' else 8),y,1.,box)
    return frame,detection,x


class PortableHeaderFrames(unittest.TestCase):
    def evaluate(self,**kw):
        frame,detection,expected=scene(**kw)
        before=asdict(detection)
        rows=prototype.observe_header_x(frame,[detection])
        self.assertEqual(before,asdict(detection))
        selected=rows[0]['selected'] if rows else None
        observations.append(dict(options={k:v for k,v in kw.items() if k!='transform'},selected=selected,
                                 expected=expected,rows=rows))
        return selected,expected

    def test_both_horizontal_fragment_directions(self):
        for side in ('left','right'):
            with self.subTest(side=side):
                selected,expected=self.evaluate(side=side)
                self.assertEqual(selected,expected)

    def test_font_and_header_vertical_layout_variants(self):
        for style,delta in (('styled',0),('styled',-3),('canonical',0)):
            with self.subTest(style=style,delta=delta):
                selected,expected=self.evaluate(style=style,header_delta=delta)
                self.assertEqual(selected,expected)

    def test_fractional_anisotropic_capture_and_offset(self):
        for scale in ((1.25,1.25),(.9,.9),(1.25,1.),(1.,1.25)):
            for side in ('left','right'):
                with self.subTest(scale=scale,side=side):
                    selected,expected=self.evaluate(scale=scale,side=side,offset=(17,11),style='styled')
                    self.assertEqual(selected,expected)

    def test_brightness_polarity_and_channel_order(self):
        for transform in (lambda c:tuple(round(v*.35) for v in c),lambda c:tuple(255-v for v in c),
                          lambda c:(c[2],c[0],c[1])):
            for side in ('left','right'):
                with self.subTest(transform=transform,side=side):
                    selected,expected=self.evaluate(transform=transform,side=side,style='styled')
                    self.assertEqual(selected,expected)

    def test_flat_gradient_rail_and_unlettered_panel_abstain(self):
        for style in ('flat','gradient','rail','blank'):
            with self.subTest(style=style):
                self.assertIsNone(self.evaluate(style=style)[0])

    def test_wide_body_and_specialized_marker_path_unchanged(self):
        self.assertIsNone(self.evaluate(body_width=32)[0])
        self.assertIsNone(self.evaluate(kind='save_red_body_header')[0])

    def test_extended_or_clipped_world_frame_abstains(self):
        frame,detection,_=scene()
        source=frame.original_snapshot()
        canonical=RGBImage(800,608,Image.frombytes('RGB',(source.width,source.height),source.data).resize((800,608)).tobytes())
        extended=SourceFrame(source,frame.room,extent=Box(-8,0,816,608),canonical=canonical)
        self.assertEqual(prototype.observe_header_x(extended,[detection]),[])



    def test_alignment_changes_only_x_and_preserves_order_and_input(self):
        frame, detection, expected = scene()
        other = replace(detection, kind='spike', type_id=3, x=32, y=32)
        original = [other, detection]
        before = deepcopy(original)
        output, proof = prototype.align_source_save_headers(frame, original)
        self.assertEqual(original, before)
        self.assertIs(output[0], other)
        self.assertEqual(asdict(output[1]), {**asdict(detection), 'x': expected})
        self.assertEqual(len(output), len(original))
        self.assertEqual(len(proof['changes']), 1)

    def test_existing_save_destination_is_not_merged(self):
        frame, detection, expected = scene()
        existing = replace(detection, x=expected, kind='save_red_body_header')
        original = [detection, existing]
        output, proof = prototype.align_source_save_headers(frame, original)
        self.assertEqual(output, original)
        self.assertEqual(proof['changes'], [])

    def test_noneligible_markers_and_geometric_objects_are_preserved(self):
        frame, detection, _ = scene(kind='save_red_body_header')
        objects = [detection, replace(detection, type_id=21, kind='warp'),
                   replace(detection, type_id=1, kind='block')]
        output, proof = prototype.align_source_save_headers(frame, objects)
        self.assertEqual(output, objects)
        self.assertEqual(proof['changes'], [])

    def test_two_visible_header_origins_abstain(self):
        frame, detection, _ = scene()
        source = frame.original_snapshot()
        raster = Image.frombytes('RGB', (source.width, source.height), source.data)
        with Image.open(ROOT/'jtool_scanner/assets/jtool-pat-default/save-frame0.png') as asset:
            panel = asset.convert('RGBA').crop((3,1,29,9))
            raster.paste(panel, (155,152), panel)
        ambiguous = SourceFrame(RGBImage(raster.width, raster.height, raster.tobytes()), frame.room)
        rows = prototype.observe_header_x(ambiguous, [detection])
        self.assertTrue(rows)
        self.assertGreaterEqual(len({p['x'] for p in rows[0]['panels']}), 2)
        self.assertIsNone(rows[0]['selected'])
