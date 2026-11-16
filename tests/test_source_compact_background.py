from math import floor
from unittest import TestCase

from jtool_scanner.geometry import Box
from scripts.source_compact_background import compact_flat_background


class CompactBackgroundEvidenceTests(TestCase):
    viewport = Box(96, 96, 608, 416)
    brick = (120, 40, 24)
    backdrop = (168, 152, 136)

    def observe(self, size, paint):
        w, h = size
        px, py = round(3 * w / 19), round(3 * h / 13)
        frame = (-px, -py, w + 2 * px, h + 2 * py)

        def pixel(x, y):
            u = (x + .5 + px) * 800 / frame[2] - 96
            v = (y + .5 + py) * 608 / frame[3] - 96
            return paint(u, v)

        return compact_flat_background(pixel, size, frame, self.viewport)

    def test_largest_flat_role_is_independent_of_red_majority_and_scale(self):
        def scene(x, y):
            if 208 <= x < 400:
                return self.backdrop
            weave = 16 if (floor(x / 4) + floor(y / 5)) % 2 else -16
            return tuple(v + weave for v in self.brick)

        for size in ((608, 416), (863, 590)):
            with self.subTest(size=size):
                report = self.observe(size, scene)
                self.assertEqual(report['color'], self.backdrop)
                self.assertTrue(all(f['qualified'] for f in report['folds']))

    def test_red_backdrop_is_not_rejected_for_its_color(self):
        self.assertEqual(self.observe((608, 416), lambda x, y: self.brick)['color'], self.brick)

    def test_two_tied_flat_surfaces_remain_ambiguous(self):
        def paint(x, y):
            return self.brick if x < 304 else self.backdrop

        self.assertIsNone(self.observe((863, 590), paint)['color'])

    def test_tiny_or_unobserved_capture_cannot_supply_independent_pixels(self):
        def fail(*args):
            self.fail('Sampled unavailable/duplicated pixels')

        self.assertIsNone(compact_flat_background(fail, (1, 1), (0, 0, 1, 1), self.viewport)['color'])
        offscreen = (-1000, -1000, 800, 608)
        self.assertIsNone(compact_flat_background(fail, (800, 608), offscreen, self.viewport)['color'])
