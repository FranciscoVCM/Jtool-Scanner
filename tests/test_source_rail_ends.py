import unittest

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_rail_ends import observe_rail_end


class SourceRailEndTests(unittest.TestCase):
    def scene(self, *, end="straight", scale=(800, 608), dark=False):
        width, height = scale
        bg = (225, 212, 201) if dark else (30, 75, 104)
        data = bytearray(bytes(bg) * (width * height))
        for sy in range(int(100 * height / 608), int(132 * height / 608) + 1):
            y = (sy + .5) * 608 / height
            if not 100 <= y < 132:
                continue
            if end == "slanted":
                left, right = (80 + (y - 116) / 2, 112 + (y - 116) / 2)
            elif end == "extended":
                left, right = (48, 144)
            elif end == "no_end":
                left, right = (0, 800)
            else:
                left, right = (80, 112)
            shade = (16 if dark else 128) + int(y) % 9 * 8
            color = bytes((shade + 10, shade, shade + 3))
            for sx in range(width):
                if left <= (sx + .5) * 800 / width < right:
                    i = (sy * width + sx) * 3
                    data[i:i+3] = color
        extent = Box(0, 0, width, height)
        return RGBImage(width, height, bytes(data)), extent

    def observe(self, **kwargs):
        image, extent = self.scene(**kwargs)
        return observe_rail_end(image, extent, extent, 80, 100)

    def test_end_observed_in_both_folds(self):
        r = self.observe()
        self.assertTrue(r["qualified"])
        self.assertEqual(r["flanks"][0][0]["edge"], (0, [12, 12, 11, 11]))

    def test_follow_continuation_to_adjacent_aligned_ends(self):
        r = self.observe(end="extended")
        self.assertEqual([f[0]["continuation"] for f in r["flanks"]], [23, 23])
        self.assertEqual([f[1]["boundary"] for f in r["flanks"]], [48, 144])
        self.assertTrue(r["qualified"])

    def test_slant_and_unfinished_strip_do_not_qualify(self):
        for mode in ("slanted", "no_end"):
            with self.subTest(mode=mode):
                self.assertFalse(self.observe(end=mode)["qualified"])

    def test_dark_and_fractional_end(self):
        self.assertTrue(self.observe(dark=True, scale=(982, 749))["qualified"])

    def test_clipped_end_is_unknown(self):
        image, extent = self.scene(end="extended")
        r = observe_rail_end(image, Box(70, 0, 52, 608), extent, 80, 100)
        self.assertFalse(r["qualified"])
        self.assertTrue(all("unknown" in f[-1] for f in r["flanks"]))

    def test_non_independent_rows_do_not_qualify(self):
        self.assertIn("unknown", self.observe(scale=(400, 304)))

    def test_invalid_original_capture_rejected(self):
        image, extent = self.scene()
        with self.assertRaises(ValueError):
            observe_rail_end(image, Box(-1, 0, 800, 608), extent, 80, 100)
