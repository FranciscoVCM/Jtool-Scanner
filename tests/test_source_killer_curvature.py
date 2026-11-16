from math import floor
import unittest

from scripts.source_killer_curvature import crossed_tile_curvature


def painted(size, mode):
    def pixel(u, v):
        x, y = (u+.5)*32/size, (v+.5)*32/size
        s1, s2 = abs(x-y), abs(x+y-32)
        gradient = (-2.1 if mode == 'reverse' else 2.1)*(y-16)+.68*(x-16)
        shade = 0
        if mode in ('cross', 'reverse', 'gray', 'clip'):
            shade = 16 if min(s1,s2) <= 1.1 else 0
        if mode == 'single':
            shade = 16 if s1 <= 1.1 else 0
        if mode == 'broad':
            shade = max(0,34-.6*min(s1,s2)**2)
        channels = (143,143,143) if mode == 'gray' else (155,84,74)
        return tuple(round(a+gradient-shade) for a in channels)

    def index(n):
        return tuple(floor((k+.5)*size/n) for k in range(n))

    axis = index(32)
    detail = [pixel(x,y) for y in axis for x in axis]
    colours = [pixel(x,y) for y in index(16) for x in index(16)]
    xaxis = axis if mode != 'clip' else axis[:-1]+(None,)
    return colours, detail, (xaxis,axis)


class SourceKillerCurvatureTests(unittest.TestCase):
    def test_true_crosses_on_affine_ramps_at_two_capture_scales(self):
        for size in (32,40):
            for mode in ('cross','reverse'):
                with self.subTest(size=size,mode=mode):
                    self.assertTrue(crossed_tile_curvature(*painted(size,mode))['passed'])

    def test_one_diagonal_broad_markup_and_ramp_do_not_prove_cross(self):
        for size in (32,40):
            for mode in ('single','broad','flat'):
                with self.subTest(size=size,mode=mode):
                    self.assertFalse(crossed_tile_curvature(*painted(size,mode))['passed'])

    def test_nonred_cross_protected(self):
        for size in (32,40):
            self.assertEqual(crossed_tile_curvature(*painted(size,'gray'))['reason'],'legacy relative-red isolation')

    def test_clipped_axes_do_not_vote(self):
        for size in (32,40):
            self.assertEqual(crossed_tile_curvature(*painted(size,'clip'))['reason'],'unknown original support')

    def test_repeated_source_values_are_not_independent_support(self):
        c, d, a = painted(16,'cross')
        self.assertFalse(crossed_tile_curvature(c,d,a)['passed'])
        d[0] = (0,0,0)
        self.assertEqual(crossed_tile_curvature(c,d,a)['reason'],'inconsistent repeated physical RGB')
