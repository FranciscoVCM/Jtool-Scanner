"""Phase-free single-material recovery must retain source-backed occupancy."""
import unittest
from collections import Counter
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.terrain_material import cell_quad, learn_single_rectangular_terrain


def scene(dx=0, dy=0, label=1):
    blocks = {(64+dx+x, 80+dy) for x in range(0,320,32)}
    blocks |= {(64+dx, 80+dy+y) for y in range(0,256,32)}
    blocks |= {(320+dx, 240+dy+y) for y in range(0,128,32)}
    cells = {c for p in blocks for c in cell_quad(p)}
    labels = {(x,y):label if (x,y) in cells else 0
              for y in range(0,608,16) for x in range(0,800,16)}
    return blocks, cells, labels


def choose(labels, *, edges=None, votes=None, cell_edge=None):
    return learn_single_rectangular_terrain(
        labels, edges or {0:0,1:.22}, votes if votes is not None else {1:20},
        lambda p:.5, scanner._repeated_terrain_blocks_form_dense_field,
        cell_edge or (lambda p:.25),
    )


class SingleMaterialTerrainTests(unittest.TestCase):
    def test_translated_mixed_phase_material_is_not_snapped_or_expanded(self):
        for dx in (0,16,32):
            for dy in (0,16,32):
                for label in (1,7):
                    with self.subTest(dx=dx,dy=dy,label=label):
                        _, cells, labels = scene(dx,dy,label)
                        result = choose(labels, edges={0:0,label:.22}, votes={label:20})
                        self.assertIsNotNone(result)
                        self.assertEqual({c for p in result.full_blocks for c in cell_quad(p)}, cells)

    def test_sparse_markers_triangular_material_and_backgrounds_abstain(self):
        labels = {(x,y):0 for y in range(0,608,16) for x in range(0,800,16)}
        masks = {
            'small_marker': set(cell_quad((64,64))),
            'triangle_quadrants': {(x+dx,y+dy) for x in range(64,704,64)
                for y in (64,160) for dx,dy in ((0,16),(16,16),(16,0))},
            'dense_tiled_panel': {(x,y) for x in range(64,448,16) for y in range(64,448,16)},
            'whole_room_background': set(labels),
        }
        for name,cells in masks.items():
            with self.subTest(name=name):
                self.assertIsNone(choose({p:int(p in cells) for p in labels}))

    def test_texture_and_independent_support_are_required(self):
        _,_,labels=scene()
        for options in ({'edges':{0:0,1:.08}}, {'votes':{1:2}},
                        {'votes':{1:3,0:20}}, {'cell_edge':lambda p:0}):
            with self.subTest(options=options):
                self.assertIsNone(choose(labels,**options))

    def test_weak_border_cells_cannot_expand_material(self):
        _,cells,labels=scene()
        fringe={(96,64),(112,64)}
        for p in fringe:labels[p]=1
        result=choose(labels,cell_edge=lambda p:.0625 if p in fringe else .25)
        self.assertIsNotNone(result)
        self.assertEqual({c for p in result.full_blocks for c in cell_quad(p)},cells)

    def test_ambiguous_independently_supported_materials_abstain(self):
        _,_,labels=scene()
        _,second,_=scene(400,0)
        for p in second:labels[p]=2
        self.assertIsNone(choose(labels,edges={0:0,1:.22,2:.22},votes={1:20,2:20}))

    def test_pixels_relative_palette_polarity_and_capture_scale(self):
        _,cells,_=scene()
        for background,color in (((225,225,225),(65,95,125)),
                                 ((25,25,25),(160,120,180))):
            native=Image.new('RGB',(800,608),background)
            draw=ImageDraw.Draw(native)
            for x,y in cells:
                for dy in range(0,16,4):
                    for dx in range(0,16,4):
                        delta=30 if (dx//4+dy//4)%2 else -30
                        draw.rectangle((x+dx,y+dy,x+dx+3,y+dy+3),
                                       fill=tuple(c+delta for c in color))
            supports=[scanner.Detection('mini_spike_up',7,x-4,y-16,.9,Box(0,0,1,1))
                      for x,y in sorted(cells) if y==80]
            for scale in (1,1.25,2):
                with self.subTest(background=background,scale=scale):
                    capture=native.resize((int(800*scale),int(608*scale)),Image.Resampling.NEAREST)
                    image=RGBImage(capture.width,capture.height,capture.tobytes())
                    result=scanner._learn_repeated_terrain_profile(
                        image,Box(0,0,image.width,image.height),supports)
                    self.assertIsNotNone(result)
                    self.assertTrue(result.phase_free_texture)
                    self.assertFalse(result.complementary_texture)
                    self.assertEqual({c for p in result.full_blocks for c in cell_quad(p)},cells)
                    # Duplicating one support must not fabricate independent
                    # witnesses, even when the pixel mask is rectangular.
                    self.assertIsNone(scanner._learn_repeated_terrain_profile(
                        image,Box(0,0,image.width,image.height),[supports[0]]*20))

    def test_phase_free_replacement_and_high_recall_veto(self):
        blocks=frozenset((x,80) for x in range(64,704,32))
        room=Box(0,0,800,608)
        image=RGBImage(800,608,bytes(800*608*3))
        for count,aliases,applies in ((8,20,True),(16,20,False),(8,0,False)):
            with self.subTest(count=count,aliases=aliases):
                profile=scanner._RepeatedTerrainProfile(
                    frozenset(c for p in blocks for c in cell_quad(p)),blocks,1,20,1.,
                    phase_free_texture=True)
                existing=[scanner.Detection('block',1,x,y,.7,room) for x,y in sorted(blocks)[:count]]
                existing += [scanner.Detection('block',1,32*i,128,.4,room) for i in range(aliases)]
                marker=scanner.Detection('save',12,480,256,.9,room)
                with patch.object(scanner,'_learn_repeated_terrain_profile',return_value=profile):
                    result,changed=scanner._replace_repeated_terrain_geometry(existing+[marker],image,room)
                self.assertEqual(changed,applies)
                self.assertIn(marker,result)
                if applies:
                    self.assertEqual({(d.x,d.y) for d in result if d.type_id==1},blocks)
                else:
                    self.assertEqual(result,existing+[marker])

    def test_late_block_only_replacement_preserves_decided_objects(self):
        blocks=frozenset((x,80) for x in range(64,704,32))
        profile=scanner._RepeatedTerrainProfile(
            frozenset(c for p in blocks for c in cell_quad(p)),blocks,1,20,1.,
            phase_free_texture=True)
        room=Box(0,0,800,608)
        image=RGBImage(800,608,bytes(800*608*3))
        original_blocks=[scanner.Detection('block',1,x,64,.5,room)
                         for x in range(0,640,32)]
        real_spike=scanner.Detection('spike_up',3,240,48,.8,room)
        marker=scanner.Detection('save',12,416,256,.9,room)
        mini=scanner.Detection('mini_spike_up',7,304,64,.75,room)
        objects=[*original_blocks,real_spike,marker,mini]
        with patch.object(scanner,'_learn_repeated_terrain_profile',
                          side_effect=AssertionError('already learned')):
            result,applied=scanner._replace_repeated_terrain_geometry(
                objects,image,room,profile=profile,already_learned=True,
                blocks_only=True)
        self.assertTrue(applied)
        self.assertEqual({(d.x,d.y) for d in result if d.type_id==1},blocks)
        self.assertEqual([d for d in result if d.type_id!=1],
                         [real_spike,marker,mini])


if __name__=='__main__':unittest.main(verbosity=2)
