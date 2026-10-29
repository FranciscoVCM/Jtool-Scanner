"""Portable RGB-arrow geometry, physical coverage and preserved counterexamples."""
from math import dist
from pathlib import Path
import unittest
from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.gravity_shape import (
    arrow_mask_proof, head_share_supported, original_rgb_patch, patch_arrow_proofs,
)

ROOT = Path(__file__).resolve().parents[1]


def original_mask(image, room, x, y, predicate, **kwargs):
    raw = original_rgb_patch(image, room, x, y, **kwargs)
    if raw is None:
        return None
    return frozenset((i % 16, i // 16) for i in range(256)
                     if predicate(*raw[i * 3:i * 3 + 3]))


def glyph(kind='arrow',*,head_y=18,head_left=3,shaft_width=10,down=False):
    result=Image.new('L',(32,32));draw=ImageDraw.Draw(result)
    if kind=='arrow':
        draw.polygon(((16,1),(head_left,head_y),(31-head_left,head_y)),fill=255)
        draw.rectangle((16-shaft_width//2,head_y-1,15+(shaft_width+1)//2,30),fill=255)
    elif kind=='triangle':draw.polygon(((16,1),(2,30),(29,30)),fill=255)
    elif kind=='diamond':draw.polygon(((16,1),(30,16),(16,30),(1,16)),fill=255)
    elif kind=='circle':draw.ellipse((2,2,29,29),fill=255)
    elif kind=='star':draw.polygon(((16,1),(20,11),(30,16),(20,20),(16,30),(11,20),(1,16),(11,11)),fill=255)
    elif kind=='block':draw.rectangle((1,1,30,30),fill=255)
    elif kind=='stripes':
        for y in range(2,31,6):draw.rectangle((2,y,29,y+2),fill=255)
    elif kind=='T':draw.rectangle((2,2,29,8),fill=255);draw.rectangle((12,8,19,30),fill=255)
    elif kind=='plus':draw.rectangle((12,1,19,30),fill=255);draw.rectangle((2,12,29,19),fill=255)
    elif kind=='head_only':draw.polygon(((16,1),(3,18),(28,18)),fill=255)
    elif kind=='side':return glyph().transpose(Image.Transpose.ROTATE_90)
    if down:result=result.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return result

def raster_mask(g,*,scale=1,foreground=(235,100,130),background=(35,55,75),origin=(32,32)):
    raster=Image.new('RGB',(128,128),background);raster.paste(foreground,origin,g)
    if scale!=1:raster=raster.resize((round(128*scale),round(128*scale)),Image.Resampling.BILINEAR)
    image=RGBImage(raster.width,raster.height,raster.tobytes())
    predicate=lambda r,g,b:dist((r,g,b),foreground)<dist((r,g,b),background)
    mask=original_mask(image,Box(0,0,image.width,image.height),*origin,predicate,native_size=(128,128))
    return image,mask,predicate

def centred_rows(widths):
    return frozenset(
        (x, y)
        for y, width in enumerate(widths)
        for x in range((16 - width) // 2, (16 - width) // 2 + width)
    )


def gradient_patch(step,offset=0):
    shape=centred_rows([1,3,5,7,9,11,13,15]+[4]*8)
    return bytes(c+offset for y in range(16) for x in range(16) for c in ((60+step*y,)*3 if (x,y) in shape else (180,130,30)))


class GravityShapeTests(unittest.TestCase):
    def test_up_and_down_have_two_shoulders_and_straight_shaft(self):
        for down in (False,True):
            with self.subTest(down=down):
                _,mask,_=raster_mask(glyph(down=down));proof=arrow_mask_proof(mask,down)
                self.assertIsNotNone(proof);self.assertTrue(proof['complete_head_shoulders_shaft'])
                self.assertIsNone(arrow_mask_proof(mask,not down))

    def test_head_and_shaft_variants(self):
        for head_y,left,shaft in ((16,2,8),(18,3,10),(16,4,6)):
            for down in (False,True):
                with self.subTest(head_y=head_y,left=left,shaft=shaft,down=down):
                    _,mask,_=raster_mask(glyph(head_y=head_y,head_left=left,shaft_width=shaft,down=down))
                    self.assertIsNotNone(arrow_mask_proof(mask,down))

    def test_actual_default_asset_alpha_silhouette(self):
        for direction,down in (('up',False),('down',True)):
            with self.subTest(direction=direction):
                asset=Image.open(ROOT/f'jtool_scanner/assets/jtool-pat-default/gravity-{direction}.png').convert('RGBA')
                self.assertEqual(asset.size,(32,32))
                _,mask,_=raster_mask(asset.getchannel('A'))
                self.assertIsNotNone(arrow_mask_proof(mask,down))

    def test_fractional_and_double_captures(self):
        for scale in (.75,1,1.23,2):
            for down in (False,True):
                with self.subTest(scale=scale,down=down):
                    _,mask,_=raster_mask(glyph(down=down),scale=scale)
                    self.assertIsNotNone(arrow_mask_proof(mask,down))

    def test_colour_brightness_polarity_and_near_isoluminance(self):
        for fg,bg in (((235,100,130),(35,55,75)),((40,100,180),(180,110,90)),((30,70,90),(18,25,30)),((180,40,20),(40,80,40)),((30,30,30),(220,220,220))):
            with self.subTest(fg=fg,bg=bg):
                _,mask,_=raster_mask(glyph(),foreground=fg,background=bg)
                self.assertIsNotNone(arrow_mask_proof(mask))

    def test_nonarrow_shapes_rejected_in_both_directions(self):
        for kind in ('triangle','diamond','circle','star','block','stripes','T','plus','head_only','side'):
            for down in (False,True):
                with self.subTest(kind=kind,down=down):
                    _,mask,_=raster_mask(glyph(kind))
                    self.assertIsNone(arrow_mask_proof(mask,down))

    def test_low_source_resolution_is_unknown(self):
        _,mask,_=raster_mask(glyph(),scale=.3);self.assertIsNone(mask)

    def test_outside_or_clipped_original_frame_is_unknown(self):
        image,_,predicate=raster_mask(glyph())
        self.assertIsNone(original_mask(image,Box(-1,0,128,128),32,32,predicate,native_size=(128,128)))
        self.assertIsNone(original_mask(image,Box(0,0,128,128),112,32,predicate,native_size=(128,128)))
        self.assertIsNone(original_mask(image,Box(0,0,128,128),-8,32,predicate,native_size=(128,128)))

    def test_compact_registration_uses_original_offset_not_padding(self):
        image,mask,predicate=raster_mask(glyph())
        self.assertEqual(original_mask(image,Box(0,0,128,128),96,128,predicate,native_size=(128,128),native_offset=(64,96)),mask)
        self.assertIsNone(original_mask(image,Box(0,0,128,128),32,32,predicate,native_size=(128,128),native_offset=(64,96)))

    def test_disconnected_foreground_cannot_supply_shape(self):
        a={(x,y) for y in range(12) for x in range(6) if x<=y//2}
        b={(x+10,y+3) for x,y in a};self.assertIsNone(arrow_mask_proof(a|b))

    def test_input_mask_immutable_and_wrong_bounds_rejected(self):
        _,mask,_=raster_mask(glyph());before=set(mask);arrow_mask_proof(mask)
        self.assertEqual(mask,before);self.assertIsNone(arrow_mask_proof(mask|{(-1,4)}))

    def test_adversarial_head_and_internal_cutoffs_rejected(self):
        ordinary=centred_rows([1,3,5,7,9,11,13,15]+[4]*8)
        masks=[centred_rows([6,3,5,7,9,11,13,15]+[4]*8),centred_rows([1,3,5,7,9,15,13,13]+[4]*8),
               frozenset((x,y) for x,y in ordinary if y<12),frozenset((x,y) for x,y in ordinary if x>=4)]
        for mask in masks:
            for down in (False,True):
                with self.subTest(mask=sorted(mask),down=down):
                    oriented=frozenset((x,15-y) for x,y in mask) if down else mask
                    self.assertIsNone(arrow_mask_proof(oriented,down))

    def test_negative_virtual_extent_accepts_known_interior_not_edge(self):
        full=Image.new('RGB',(128,128),(35,55,75));full.paste((235,100,130),(32,32),glyph())
        clipped=full.crop((4,0,128,128));image=RGBImage(clipped.width,clipped.height,clipped.tobytes())
        physical=Box(0,0,124,128);extent=Box(-4,0,128,128)
        raw=original_rgb_patch(image,physical,32,32,native_size=(128,128),world_extent=extent)
        self.assertIn(24,patch_arrow_proofs(raw))
        self.assertIsNone(original_rgb_patch(image,physical,0,32,native_size=(128,128),world_extent=extent))

    def test_nonpositive_extents_and_native_sizes_rejected(self):
        image,_,_=raster_mask(glyph())
        for physical,extent,size in ((Box(100,100,-800,-608),None,(800,608)),(Box(0,0,128,0),None,(128,128)),
                (Box(0,0,128,128),Box(0,0,-128,-128),(128,128)),(Box(0,0,128,128),None,(0,128))):
            with self.subTest(physical=physical,extent=extent,size=size):
                self.assertIsNone(original_rgb_patch(image,physical,32,32,native_size=size,world_extent=extent))

    def test_rgb_segmentation_keeps_neariso_and_competing_warm_colours(self):
        for fg,bg in (((250,150,130),(245,125,60)),((180,40,20),(40,80,40)),((30,70,90),(18,25,30)),((30,30,30),(220,220,220))):
            for down in (False,True):
                with self.subTest(fg=fg,bg=bg,down=down):
                    image,_,_=raster_mask(glyph(down=down),foreground=fg,background=bg)
                    raw=original_rgb_patch(image,Box(0,0,image.width,image.height),32,32,native_size=(128,128))
                    self.assertEqual(set(patch_arrow_proofs(raw)),{25 if down else 24})

    def test_rgb_segmentation_fractional_sources(self):
        for scale in (.75,1,1.23,2):
            for down in (False,True):
                with self.subTest(scale=scale,down=down):
                    image,_,_=raster_mask(glyph(down=down),scale=scale)
                    raw=original_rgb_patch(image,Box(0,0,image.width,image.height),32,32,native_size=(128,128))
                    self.assertEqual(set(patch_arrow_proofs(raw)),{25 if down else 24})

    def test_shaded_default_sprites_on_three_backgrounds(self):
        for direction,type_id in (('up',24),('down',25)):
            for bg in ((45,25,5),(230,120,60),(70,140,190)):
                with self.subTest(direction=direction,bg=bg):
                    sprite=Image.open(ROOT/f'jtool_scanner/assets/jtool-pat-default/gravity-{direction}.png').convert('RGBA')
                    scene=Image.new('RGBA',(128,128),(*bg,255));scene.alpha_composite(sprite,(32,32));raster=scene.convert('RGB')
                    image=RGBImage(128,128,raster.tobytes())
                    raw=original_rgb_patch(image,Box(0,0,128,128),32,32,native_size=(128,128))
                    self.assertEqual(set(patch_arrow_proofs(raw)),{type_id})

    def test_segmented_nonarrow_sources_do_not_create_arrows(self):
        for kind in ('triangle','diamond','circle','star','block','stripes','T','plus','head_only','side'):
            with self.subTest(kind=kind):
                image,_,_=raster_mask(glyph(kind))
                raw=original_rgb_patch(image,Box(0,0,128,128),32,32,native_size=(128,128))
                self.assertEqual(patch_arrow_proofs(raw),{})

    def test_uniform_or_incomplete_raw_packet_abstains(self):
        self.assertEqual(patch_arrow_proofs(bytes((150,70,90))*256),{})
        self.assertEqual(patch_arrow_proofs(bytes(767)),{})
        self.assertEqual(patch_arrow_proofs(None),{})

    def test_global_brightness_translation_preserves_arrow(self):
        before=patch_arrow_proofs(gradient_patch(3,0));after=patch_arrow_proofs(gradient_patch(3,1))
        self.assertEqual(set(before),{24});self.assertEqual(set(after),set(before))

    def test_continuously_shaded_arrow_keeps_complete_body(self):
        self.assertEqual(set(patch_arrow_proofs(gradient_patch(4))),{24})

    def test_complete_brightness_translation_matrix(self):
        for step in (0,1,3,4):
            for offset in (0,1,2,8,16,27):
                with self.subTest(step=step,offset=offset):
                    self.assertEqual(set(patch_arrow_proofs(gradient_patch(step,offset))),{24})

    def test_row_count_boundaries_not_index_ratio(self):
        for head,total,expected in ((5,14,True),(4,14,False),(7,10,True),(8,10,False),(0,14,False),(15,14,False),(0,0,False)):
            with self.subTest(head=head,total=total):self.assertEqual(head_share_supported(head,total),expected)

    def test_five_of_fourteen_actual_head_rows_both_directions(self):
        mask=centred_rows([1,3,5,7,9]+[4]*9)
        for down in (False,True):
            oriented=frozenset((x,15-y) for x,y in mask) if down else mask
            proof=arrow_mask_proof(oriented,down)
            self.assertIsNotNone(proof);self.assertEqual(proof['head_rows'],5);self.assertEqual(proof['height'],14)

    def test_four_of_fourteen_is_still_too_short(self):
        mask=centred_rows([1,3,5,9]+[4]*10)
        for down in (False,True):
            oriented=frozenset((x,15-y) for x,y in mask) if down else mask
            self.assertIsNone(arrow_mask_proof(oriented,down))

