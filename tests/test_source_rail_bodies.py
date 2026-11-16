from unittest import TestCase

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_rail_bodies import survey_rail_bodies


def _scene(*, vertical=False, invert=False, size=(800, 608), phase_mode="aligned", rail="full",
           phase_offset=0):
    canvas = Image.new("RGB", (800, 608), (91, 96, 106))
    draw = ImageDraw.Draw(canvas)
    u_max, v_max = (608, 800) if vertical else (800, 608)

    def line(u, v, length, color):
        coords = (v, u, v, u + length - 1) if vertical else (u, v, u + length - 1, v)
        draw.line(coords, fill=color)

    # Independent orthogonal edges, far from the body, in both folds.
    if phase_mode != "absent":
        for v in range(256, v_max - 32):
            offset = phase_offset + (8 if phase_mode == "different" and (v // 32) % 2 else 0)
            for u in range(32 + offset, u_max - 32, 64):
                line(u, v, 32, (31, 61, 143))
    levels = (167, 173, 182, 195, 209, 218, 220, 211, 197, 184, 158, 143, 137, 139, 146, 157)
    for v in range({"full": 32, "short": 8, "flat": 32}[rail]):
        level = 190 if rail == "flat" else levels[v % len(levels)]
        line(96 + phase_offset, 96 + v, 32, (level, level, level))
    if invert:
        canvas = canvas.point(lambda c: 255 - c)
    if size != canvas.size:
        canvas = canvas.resize(size, Image.Resampling.BILINEAR)
    image = RGBImage(*size, canvas.tobytes())
    return image, Box(0, 0, *size)


class SourceRailBodyTests(TestCase):
    def test_periodic_full_body_both_axes_and_polarities(self):
        for vertical in (False, True):
            for invert in (False, True):
                with self.subTest(vertical=vertical, invert=invert):
                    image, room = _scene(vertical=vertical, invert=invert)
                    result = survey_rail_bodies(image, room, room, vertical=vertical)
                    self.assertEqual(result.positions, ((96, 96),))
                    self.assertEqual(result.phase, 0)
                    self.assertEqual(result.scores[96, 96].edges, (5, 5))

    def test_fractional_original_not_resampled_by_survey(self):
        for vertical in (False, True):
            image, room = _scene(vertical=vertical, size=(982, 751))
            result = survey_rail_bodies(image, room, room, vertical=vertical)
            self.assertEqual(result.positions, ((96, 96),))

    def test_short_platform_and_flat_full_art_are_not_periodic_bodies(self):
        for rail in ("short", "flat"):
            image, room = _scene(rail=rail)
            result = survey_rail_bodies(image, room, room)
            self.assertNotIn((96, 96), result.scores)
            self.assertEqual(result.positions, ())

    def test_no_phase_without_agreement_between_independent_bands(self):
        for mode in ("absent", "different"):
            image, room = _scene(phase_mode=mode)
            result = survey_rail_bodies(image, room, room)
            self.assertIn((96, 96), result.scores)
            self.assertIsNone(result.phase)
            self.assertEqual(result.positions, ())

    def test_phase_comes_from_independent_evidence_not_default_grid_origin(self):
        for vertical, origin in ((False, (104, 96)), (True, (96, 104))):
            image, room = _scene(vertical=vertical, phase_offset=8)
            result = survey_rail_bodies(image, room, room, vertical=vertical)
            self.assertEqual(result.phase, 8)
            self.assertEqual(result.positions, (origin,))

    def test_body_rejected_when_capture_lacks_original_support(self):
        image, room = _scene()
        for crop in (Box(0, 98, 800, 510), Box(97, 0, 703, 608)):
            self.assertNotIn((96, 96), survey_rail_bodies(image, crop, room).scores)

    def test_invalid_camera_rejected(self):
        image, room = _scene()
        with self.assertRaises(ValueError):
            survey_rail_bodies(image, Box(-1, 0, 800, 608), room)
