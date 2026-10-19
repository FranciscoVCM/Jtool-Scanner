"""Original pixel squares, not centre tests, padding or sprite alpha guesses."""
from dataclasses import FrozenInstanceError
import unittest
from unittest.mock import patch

from jtool_scanner.geometry import Box
from scripts.source_pixel_geometry import PolygonPixelCoverage, original_pixel_bounds
from scripts.source_sampling import SourceFrame
from tests.test_source_sampling import raster


def frame(width=800, height=608):
    return SourceFrame(raster(width,height),Box(0,0,width,height))


class SourcePixelGeometryTests(unittest.TestCase):
    def test_known_disjoint_inside_and_corner_touching_are_exact(self):
        source=frame()
        triangle=PolygonPixelCoverage(source,((0,0),(2,0),(0,2)))
        self.assertEqual(triangle.overlap(0,0),1)
        self.assertEqual(triangle.overlap(1,0),.5)
        self.assertEqual(triangle.overlap(1,1),0)
        self.assertEqual(triangle.overlap(2,0),0)
        self.assertEqual(triangle.overlap(4,4),0)

    def test_center_outside_does_not_mean_original_pixel_disjoint(self):
        polygon=((10,10),(11,10),(10,10.5))
        coverage=PolygonPixelCoverage(frame(),polygon)
        # The pixel centre (10.5,10.5) lies beyond this triangle's sloping edge.
        self.assertEqual(coverage.overlap(10,10),.25)

    def test_four_directions_winding_and_subpixel_translation(self):
        source=frame()
        base=((.1,.2),(.8,.2),(.1,.9))
        for rotation in range(4):
            def transform(p):
                x,y=p
                for _ in range(rotation):x,y=1-y,x
                return x+17,y+23
            polygon=tuple(map(transform,base))
            expected=.7*.7/2
            for vertices in (polygon,tuple(reversed(polygon))):
                self.assertAlmostEqual(PolygonPixelCoverage(source,vertices).overlap(17,23),expected)

    def test_fractional_anisotropic_physical_transform(self):
        source=frame(1000,747)
        x,y=121,217
        a,b,c,d=original_pixel_bounds(source,x,y)
        triangle=((a,b),(c,b),(a,d))
        self.assertAlmostEqual(PolygonPixelCoverage(source,triangle).overlap(x,y),.5)
        self.assertEqual(original_pixel_bounds(source,999,746)[2:],(800,608))

    def test_original_crop_offsets_and_world_offsets_are_not_reinferred(self):
        source=SourceFrame(raster(1000,800),Box(100,100,800,608),
            extent=Box(96,98,800,608),canonical=raster())
        self.assertEqual(original_pixel_bounds(source,100,100),(4,2,5,3))
        self.assertIsNone(original_pixel_bounds(source,99,100))
        self.assertIsNone(original_pixel_bounds(source,896,100))

    def test_unknown_is_none_not_zero_even_when_canonical_has_color(self):
        source=SourceFrame(raster(800,600),Box(0,0,800,600),
            extent=Box(0,0,800,608),canonical=raster())
        coverage=PolygonPixelCoverage(source,((0,576),(32,576),(0,608)))
        self.assertIsNotNone(coverage.overlap(0,599))
        self.assertIsNone(coverage.overlap(0,600))
        self.assertIsNone(coverage.overlap(-1,599))
        self.assertEqual(coverage.overlap(799,599),0)

    def test_polygon_areas_add_up_across_fractional_source_cells(self):
        source=frame(1000,760)
        coverage=PolygonPixelCoverage(source,((8,8),(16,8),(8,16)))
        physical_area=sum(coverage.overlap(x,y) for y in range(9,22) for x in range(9,22))
        self.assertAlmostEqual(physical_area*source.pitch[0]*source.pitch[1],32)

    def test_no_sampling_resizing_mutation_or_global_cache(self):
        source=frame()
        data=source.original_snapshot().data
        with patch.object(SourceFrame,'pixel',side_effect=AssertionError('No resampling')):
            coverage=PolygonPixelCoverage(source,((0,0),(2,0),(0,2)))
            self.assertEqual(coverage.overlap(1,0),.5)
        self.assertIs(source.original_snapshot().data,data)
        other=PolygonPixelCoverage(frame(400,304),((0,0),(2,0),(0,2)))
        self.assertEqual(other.overlap(0,0),.5)
        self.assertEqual(coverage.overlap(0,0),1)

    def test_immutable_copied_polygon_and_immutable_evidence(self):
        vertices=[[0,0],[1,0],[0,1]]
        coverage=PolygonPixelCoverage(frame(),vertices)
        vertices[0][0]=100
        self.assertEqual(coverage.overlap(0,0),.5)
        with self.assertRaises(FrozenInstanceError):coverage.vertices=()

    def test_invalid_pixel_identities_are_never_rounded(self):
        source=frame()
        for point in ((True,1),(1.5,1),(0,float('nan')),(None,0)):
            with self.assertRaises(ValueError):original_pixel_bounds(source,*point)

    def test_invalid_nonfinite_degenerate_or_concave_polygons_rejected(self):
        source=frame()
        for polygon in (None,(),((0,0),(1,1)),((0,0),(1,1),(2,2)),
            ((0,0),(1,0),(0,float('inf'))),((0,0),(True,0),(0,1)),
            ((0,0),(1,0),(0,1),(0,0)),((0,0),(2,0),(1,.5),(2,2),(0,2)),
            ((0,0),(1,)),((0,0),(1,1),(0,1),(1,0)),
            ((0,3),(4,3),(1,0),(2,5),(3,0)),
            ((0,0),(10**400,0),(0,1)),((0,0),(1e308,0),(0,1e308))):
            with self.subTest(polygon=polygon),self.assertRaises(ValueError):
                PolygonPixelCoverage(source,polygon)

    def test_invalid_frame_rejected_without_side_effects(self):
        with self.assertRaises(ValueError):PolygonPixelCoverage(None,((0,0),(1,0),(0,1)))
        with self.assertRaises(ValueError):original_pixel_bounds(None,0,0)


if __name__=='__main__':unittest.main()
