"""Raw RGB cells are neither colour-range boxes nor new object teachers."""
from math import dist
from unittest import TestCase

from PIL import Image
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_calibrated_conflicts import CalibratedConflictQuery
from scripts.source_raster_cells import closest_rgb, source_cell
from scripts.source_sampling import SourceFrame


def artwork_query(teachers=((3,200,200),(3,300,300),(3,400,400)), palettes=None):
    raster = Image.new('RGB', (800,608), (0,0,0))
    palettes = palettes or [[(0,0,0),(255,255,255)]*2]*len(teachers)
    for (_,x,y), colours in zip(teachers, palettes):
        for i,(dx,dy) in enumerate(((-1,-1),(0,-1),(-1,0),(0,0))):
            if 0 <= x+dx < 800 and 0 <= y+dy < 608:
                raster.putpixel((x+dx,y+dy), colours[i])
    image = RGBImage(800,608,raster.tobytes())
    query = object.__new__(CalibratedConflictQuery)
    query.frame = SourceFrame(image,Box(0,0,800,608))
    query.separation = 100
    query.artwork = {(3,100,100):dict(phase=(0,0),teachers=teachers)}
    query.art_cache, query.cells, query.cell_queries, query.new_art_witnesses = {}, {}, {}, []
    return query


class SourceRasterCellTests(TestCase):
    def test_segment_not_rgb_box(self):
        colours=[(0,0,0),(100,100,100)]
        self.assertLess(dist((30,30,30),closest_rgb((30,30,30),colours)),1e-8)
        self.assertGreater(dist((100,0,100),closest_rgb((100,0,100),colours)),70)

    def test_triangle_interior_and_outside_plane(self):
        colours=[(0,0,0),(100,0,0),(0,100,0)]
        self.assertEqual(closest_rgb((25,25,30),colours),(25,25,0))
        self.assertGreater(dist((90,90,0),closest_rgb((90,90,0),colours)),50)

    def test_tetrahedron_is_not_axis_aligned_box(self):
        colours=[(0,0,0),(100,0,0),(0,100,0),(0,0,100)]
        self.assertEqual(closest_rgb((20,20,20),colours),(20,20,20))
        self.assertGreater(dist((90,90,90),closest_rgb((90,90,90),colours)),90)

    def test_degenerate_cells_and_palette_permutation(self):
        colours=[(0,0,0),(100,0,0),(0,100,0),(100,100,0)]
        point=(70,80,20)
        swap=lambda v:(255-v[2],255-v[0],255-v[1])
        self.assertEqual(closest_rgb(point,colours),(70,80,0))
        self.assertAlmostEqual(dist(point,closest_rgb(point,colours)),
            dist(swap(point),closest_rgb(swap(point),list(map(swap,colours)))))
        self.assertEqual(closest_rgb(point,[(1,2,3)]*4),(1,2,3))

    def test_only_nonzero_bilinear_taps_and_known_source(self):
        frame=artwork_query().frame
        self.assertEqual(source_cell(frame,.5,.5)['positions'],[(0,0)])
        self.assertEqual(source_cell(frame,1,1)['positions'],[(0,0),(1,0),(0,1),(1,1)])
        self.assertIsNone(source_cell(frame,0,0))
        self.assertIsNone(source_cell(frame,-.1,10))

    def test_fractional_scale_does_not_resample_or_mutate_rgb(self):
        image=RGBImage(1000,760,bytes((60,70,80))*1000*760)
        frame=SourceFrame(image,Box(0,0,1000,760))
        before=image.data
        result=source_cell(frame,100.5,100.5)
        self.assertEqual(len(result['positions']),4)
        self.assertEqual(closest_rgb((60,70,80),result['RGB']),(60,70,80))
        self.assertEqual(image.data,before)

    def test_partial_physical_square_at_fractional_crop_border_is_unknown(self):
        image=RGBImage(800,608,bytes((20,30,40))*800*608)
        frame=SourceFrame(image,Box(.25,0,799.5,608),extent=Box(0,0,800,608),canonical=image)
        self.assertIsNotNone(frame.original_position(799.5,500.5))
        self.assertIsNone(source_cell(frame,799.5,500.5))
        self.assertIsNotNone(source_cell(frame,798.5,500.5))

    def test_more_than_four_colours_or_no_known_cell_is_invalid(self):
        for colours in ([],[(v,v,v) for v in range(5)]):
            with self.assertRaises(ValueError):closest_rgb((1,2,3),colours)


class SourceRasterWitnessTests(TestCase):
    def test_three_other_disjoint_cells_explain_observed_mixture(self):
        query=artwork_query()
        self.assertEqual(query.art_owner(100,100,(128,128,128)),(3,100,100))
        self.assertEqual(len(query.new_art_witnesses[0]['witnesses']),3)

    def test_two_teachers_cannot_supply_three_witnesses(self):
        self.assertIsNone(artwork_query(teachers=((3,200,200),(3,300,300))).art_owner(100,100,(128,128,128)))

    def test_duplicate_source_pixels_do_not_supply_independence(self):
        self.assertIsNone(artwork_query(teachers=((3,200,200),)*3).art_owner(100,100,(128,128,128)))

    def test_unknown_crop_cannot_supply_third_cell(self):
        self.assertIsNone(artwork_query(teachers=((3,0,0),(3,300,300),(3,400,400))).art_owner(100,100,(128,128,128)))

    def test_pairwise_corroboration_required(self):
        query=artwork_query(palettes=[[(120,120,120)]*4,[(136,136,136)]*4,[(136,136,136)]*4])
        self.assertIsNone(query.art_owner(100,100,(128,128,128)))

    def test_colour_hull_rejects_unrelated_chroma(self):
        self.assertIsNone(artwork_query().art_owner(100,100,(128,0,128)))

    def test_no_context_expansion_or_source_mutation(self):
        query=artwork_query();before=query.frame.original_snapshot().data
        self.assertIsNone(query.art_owner(140,140,(128,128,128)))
        self.assertEqual(query.frame.original_snapshot().data,before)

    def test_old_exact_point_positive_wins_first(self):
        query=artwork_query(palettes=[[(220,220,220)]*4]*3)
        self.assertEqual(query.art_owner(100,100,(220,220,220)),(3,100,100))
        self.assertFalse(query.new_art_witnesses)
