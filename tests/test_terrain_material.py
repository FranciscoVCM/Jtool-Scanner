"""Portable phase, texture, occupancy and background terrain regressions."""
import unittest
from collections import Counter
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner import scanner
from jtool_scanner.terrain_material import (
    cell_quad as quad, pack_textured_rectangles as pack_rectangles,
    learn_complementary_terrain,
    distributed_cell_edges,
)
from jtool_scanner.scanner import _repeated_terrain_blocks_form_dense_field


def scene(dx=0,dy=0,swap=False):
    blocks={(64+dx+x,80+dy) for x in range(0,320,32)}
    blocks|={(64+dx,80+dy+y) for y in range(0,256,32)}
    blocks|={(320+dx,240+dy+y) for y in range(0,128,32)}
    cells={c for b in blocks for c in quad(b)}
    labels={(x,y):0 for y in range(0,608,16) for x in range(0,800,16)}
    for x,y in cells:
        labels[(x,y)]=1+(((x-dx)//16+(y-dy)//16+int(swap))%2)
    return blocks,cells,labels


def choose(labels,edges=None,votes=None):
    return learn_complementary_terrain(labels,edges or {0:0,1:.22,2:.28},
        votes if votes is not None else Counter({1:20,2:20}),lambda p:.5,
        _repeated_terrain_blocks_form_dense_field,lambda p:.25)


class TerrainMaterialTests(unittest.TestCase):
    def test_distributed_weak_texture_rejects_lines_and_one_noise_pixel(self):
        for transpose in (False, True):
            for reverse in (False, True):
                def mask(points):
                    transformed = {(15-x if reverse else x, y) for x,y in points}
                    if transpose:
                        transformed = {(y,x) for x,y in transformed}
                    return tuple((i%16,i//16) in transformed for i in range(256))
                line = {(x,1) for x in range(16)}
                with self.subTest(transpose=transpose,reverse=reverse):
                    self.assertFalse(distributed_cell_edges(mask(line)))
                    self.assertFalse(distributed_cell_edges(mask(line|{(0,14)})))
                    self.assertTrue(distributed_cell_edges(mask(line|{(0,14),(14,13)})))

    def test_one_weak_quadrant_requires_three_strong_neighbors_no_bootstrap(self):
        _, cells, labels = scene()
        for weak in ({(64,80)}, {(64,80),(80,80)}):
            with self.subTest(weak=weak):
                result = learn_complementary_terrain(
                    labels, {0:0,1:.22,2:.28}, Counter({1:20,2:20}), lambda p:.5,
                    _repeated_terrain_blocks_form_dense_field,
                    lambda p:.065 if p in weak else .25,
                    weak_cell_texture=lambda p:p in weak,
                )
                self.assertIsNotNone(result)
                covered = {c for p in result.full_blocks for c in quad(p)}
                if len(weak)==1:
                    self.assertEqual(covered,cells)
                else:
                    # The right cell has three ORIGINAL strong neighbors in
                    # another rectangle; it may pass. The left cell must not
                    # then borrow that newly admitted cell as its third vote.
                    self.assertIn((80,80),covered)
                    self.assertNotIn((64,80),covered)

    def test_shifted_complementary_lattices(self):
        for dx in (0,16,32):
            for dy in (0,16,32):
                for swap in (False,True):
                    with self.subTest(dx=dx,dy=dy,swap=swap):
                        _,cells,labels=scene(dx,dy,swap)
                        result=choose(labels)
                        self.assertIsNotNone(result)
                        covered={c for p in result.full_blocks for c in quad(p)}
                        self.assertEqual(covered,cells)

    def test_exact_rectangle_support_no_outward_growth(self):
        for dx,dy in ((0,0),(16,0),(0,16),(16,16)):
            with self.subTest(phase=(dx,dy)):
                cells={(x+dx,y+dy) for x in range(0,304,16) for y in (0,16)}
                packed=pack_rectangles(cells)
                self.assertEqual(len(packed),10)
                self.assertEqual({c for p in packed for c in quad(p)},cells)

    def test_one_mini_corner_is_not_a_full_block(self):
        cells=set(quad((0,0)))|{(32,0)}
        packed=pack_rectangles(cells)
        self.assertEqual(packed,frozenset({(0,0)}))

    def test_missing_quadrant_does_not_get_filled(self):
        self.assertEqual(pack_rectangles({(0,0),(16,0),(0,16)}),frozenset())

    def test_smooth_complement_is_rejected(self):
        _,_,labels=scene()
        self.assertIsNone(choose(labels,edges={0:0,1:.30,2:0}))

    def test_independent_support_required(self):
        _,_,labels=scene()
        self.assertIsNone(choose(labels,votes=Counter({1:40})))

    def test_independently_complete_adjacent_materials_are_not_merged(self):
        blocks,_,labels=scene()
        for index,p in enumerate(sorted(blocks)):
            for cell in quad(p):labels[cell]=1+index%2
        self.assertIsNone(choose(labels))

    def test_textured_rectangle_field_is_not_gameplay_terrain(self):
        labels={(x,y):0 for y in range(0,608,16) for x in range(0,800,16)}
        for y in range(64,448,16):
            for x in range(64,448,16):labels[(x,y)]=1+(x//16+y//16)%2
        self.assertIsNone(choose(labels))

    def test_small_checker_object_is_not_a_room_material(self):
        labels={(x,y):0 for y in range(0,608,16) for x in range(0,800,16)}
        for x,y in quad((64,64)):labels[(x,y)]=1+(x//16+y//16)%2
        self.assertIsNone(choose(labels))

    def test_same_color_boundary_fringe_cannot_supply_missing_texture(self):
        _,cells,labels=scene()
        fringe={(96,64),(112,64)}
        for x,y in fringe:labels[(x,y)]=1+(x//16+y//16)%2
        result=learn_complementary_terrain(labels,{0:0,1:.22,2:.28},Counter({1:20,2:20}),
            lambda p:.5,_repeated_terrain_blocks_form_dense_field,
            cell_edge=lambda p:.0625 if p in fringe else .25)
        self.assertIsNotNone(result)
        self.assertEqual({c for p in result.full_blocks for c in quad(p)},cells)

    def test_actual_color_clustering_and_texture_at_capture_scales(self):
        """Exercise pixels, sampling, clustering and fallback, not given labels.

        Support hypotheses are supplied to this isolated learner; this is not
        an end-to-end test of finding those hypotheses or every object class.
        """
        _, cells, labels = scene(16, 0)
        palettes = (
            ((225, 225, 225), (65, 95, 125), (170, 110, 60)),
            ((25, 25, 25), (160, 120, 180), (75, 170, 110)),
        )
        for background, first, second in palettes:
            native = Image.new('RGB', (800, 608), background)
            draw = ImageDraw.Draw(native)
            for x, y in cells:
                color = first if labels[(x, y)] == 1 else second
                for dy in range(0, 16, 4):
                    for dx in range(0, 16, 4):
                        delta = 30 if (dx // 4 + dy // 4) % 2 else -30
                        shade = tuple(c + delta for c in color)
                        draw.rectangle((x+dx, y+dy, x+dx+3, y+dy+3), fill=shade)
            supports = [
                scanner.Detection('mini_spike_up', 7, x-4, y-16, .9, Box(0, 0, 1, 1))
                for x, y in sorted(cells) if y == 80
            ]
            for scale in (1, 1.25, 2):
                with self.subTest(background=background, scale=scale):
                    capture = native.resize(
                        (int(800*scale), int(608*scale)), Image.Resampling.NEAREST
                    )
                    image = RGBImage(capture.width, capture.height, capture.tobytes())
                    result = scanner._learn_repeated_terrain_profile(
                        image, Box(0, 0, capture.width, capture.height), supports
                    )
                    self.assertIsNotNone(result)
                    self.assertTrue(result.complementary_texture)
                    self.assertEqual({c for p in result.full_blocks for c in quad(p)}, cells)

    def test_complementary_replacement_uses_both_agreement_directions(self):
        blocks = frozenset((x, 64) for x in range(0, 640, 32))
        profile = scanner._RepeatedTerrainProfile(
            frozenset(c for p in blocks for c in quad(p)), blocks, 1, 20, 1.0,
            complementary_texture=True,
        )
        image = RGBImage(800, 608, bytes(800*608*3))
        room = Box(0, 0, 800, 608)
        matches = [scanner.Detection('block', 1, x, y, .7, room)
                   for x, y in sorted(blocks)[:8]]
        aliases = [scanner.Detection('block', 1, x, 128, .4, room)
                   for x in range(0, 640, 32)]
        with patch.object(scanner, '_learn_repeated_terrain_profile', return_value=profile):
            result, applied = scanner._replace_repeated_terrain_geometry(
                matches+aliases, image, room
            )
        self.assertTrue(applied)
        self.assertEqual({(d.x, d.y) for d in result if d.type_id == 1}, blocks)

    def test_complementary_replacement_preserves_good_or_uncontradicted_outputs(self):
        blocks = frozenset((x, 64) for x in range(0, 640, 32))
        image = RGBImage(800, 608, bytes(800*608*3))
        room = Box(0, 0, 800, 608)
        for complementary, count, aliases in ((True, 16, 20), (True, 8, 0), (False, 8, 20)):
            with self.subTest(complementary=complementary, count=count, aliases=aliases):
                profile = scanner._RepeatedTerrainProfile(
                    frozenset(c for p in blocks for c in quad(p)), blocks, 1, 20, 1.0,
                    complementary_texture=complementary,
                )
                existing = [scanner.Detection('block', 1, x, y, .7, room)
                            for x, y in sorted(blocks)[:count]]
                existing += [scanner.Detection('block', 1, x, 128, .4, room)
                             for x in range(0, aliases*32, 32)]
                with patch.object(scanner, '_learn_repeated_terrain_profile', return_value=profile):
                    result, applied = scanner._replace_repeated_terrain_geometry(
                        existing, image, room
                    )
                self.assertFalse(applied)
                self.assertEqual(result, existing)


if __name__=='__main__':unittest.main(verbosity=2)
