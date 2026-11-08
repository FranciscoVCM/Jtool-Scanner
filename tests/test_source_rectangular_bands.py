"""Portable shared-band evidence; no private art, maps, or scanner binding."""

from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_rectangular_bands import SourceBandEvidence, horizontal_bands


def source(*, width=800, height=608, offset=(0, 0), ink=(176, 182, 200), background=(45, 49, 53),
           origin=(200, 240), damaged=False, mismatch=False):
    ox, oy = offset
    extent = Box(ox, oy, width, height)
    im = Image.new('RGB', (width + ox + 7, height + oy + 5), background)
    draw = ImageDraw.Draw(im)

    def paint(rect, rgb):
        x, y, right, bottom = rect
        draw.rectangle((ox + round(x * width / 800), oy + round(y * height / 608),
                        ox + round(right * width / 800) - 1, oy + round(bottom * height / 608) - 1), fill=rgb)

    x, y = origin
    for i in range(3):
        a = x + 32 * i
        c = (65, 166, 48) if mismatch and i == 2 else ink
        paint((a, y, a+32, y+32), c)
        paint((a+8, y+9, a+23, y+23), tuple(max(0, q-13) for q in c))
    if damaged:
        paint((x+32, y, x+64, y+9), background)
    return RGBImage(im.width, im.height, im.tobytes()), extent


class RectangularBandTests(TestCase):
    def test_finds_maximal_runs_but_never_subdivides_long_rows(self):
        items = {(x, 64) for x in range(0, 224, 32)} | {(x, 96) for x in (32,64,96,160,192)}
        self.assertEqual(list(horizontal_bands(items)), [(32, 96, 3)])

    def test_native_and_fractional_capture_recover_both_axes(self):
        for width, height, offset in ((800,608,(0,0)), (983,746,(5,9)), (1000,760,(2,3))):
            with self.subTest(width=width, height=height, offset=offset):
                im, box = source(width=width, height=height, offset=offset)
                p = SourceBandEvidence(im,box).phase(192,224,3)
                self.assertIsNotNone(p)
                self.assertEqual((p.dx,p.dy),(8,16))
                self.assertGreaterEqual(min(p.top+p.bottom+p.ends),8)
                self.assertLessEqual(max(p.body_distances),18)

    def test_original_chroma_not_global_dark_or_bright_direction(self):
        for ink, background in (((185,43,90),(43,109,90)), ((27,30,38),(210,215,205))):
            with self.subTest(ink=ink):
                im, box = source(ink=ink,background=background)
                p = SourceBandEvidence(im,box).phase(192,224,3)
                self.assertIsNotNone(p)
                self.assertEqual((p.dx,p.dy),(8,16))

    def test_existing_exact_rail_is_not_moved(self):
        im, box = source()
        self.assertIsNone(SourceBandEvidence(im,box).phase(200,240,3))

    def test_missing_segment_and_inconsistent_tile_abstain(self):
        for options in ({'damaged': True}, {'mismatch': True}):
            im, box = source(**options)
            self.assertIsNone(SourceBandEvidence(im,box).phase(192,224,3))

    def test_explicit_world_extent_retains_unclipped_physical_evidence(self):
        im, extent = source(width=986,height=751,offset=(3,7))
        crop = Box(7,10,975,744)
        p = SourceBandEvidence(im,crop,extent=extent).phase(192,224,3)
        self.assertIsNotNone(p)
        self.assertEqual((p.dx,p.dy),(8,16))

    def test_pixels_outside_physical_crop_cannot_prove_ends(self):
        im, extent = source()
        crop = Box(202,0,598,608)
        self.assertIsNone(SourceBandEvidence(im,crop,extent=extent).phase(192,224,3))

    def test_unknown_competing_phase_cannot_be_excluded_by_missing_pixels(self):
        im, box = source()
        observer = SourceBandEvidence(im,box)

        def proof(a, b):
            if a[0] == b[0] and a[0] == 192 and a[1] == 240:
                return None
            if a[0] == b[0] and a[0] == 288 and a[1] == 240:
                return 12
            if a[0] != b[0] and a[1] in (240,272):
                return 12
            return original(a,b)

        original = observer._measure_face
        with patch.object(observer,'_measure_face',side_effect=proof):
            self.assertIsNone(observer.phase(192,224,3))

    def test_invalid_images_or_native_bands_are_rejected(self):
        im, box = source()
        with self.assertRaises(ValueError):
            SourceBandEvidence(im,Box(-1,0,800,608))
        with self.assertRaises(ValueError):
            SourceBandEvidence(im,box,extent=Box(900,0,10,10))
        with self.assertRaises(ValueError):
            SourceBandEvidence(im,box).phase(192,224,7)
