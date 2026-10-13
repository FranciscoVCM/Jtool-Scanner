"""Frozen full structures, closed voids and source-only hollow teachers."""
import hashlib
import unittest

from PIL import Image, ImageDraw

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_glyph_prototypes import SourceGlyphLibrary
from scripts.source_hollow_glyphs import HollowGlyphEvidence
from scripts.source_sampling import SourceFrame


PALETTES = (((40, 50, 60), (210, 220, 225)),
            ((225, 220, 215), (30, 40, 50)), ((0, 130, 0), (255, 0, 0)))


def rotate(key, turns):
    t, x, y = key
    points = [(x+u, y+v) for u, v in VERTICES[t]]
    for _ in range(turns):
        points = [(432-(py-304), 304+(px-432)) for px, py in points]
        t = {3: 4, 4: 6, 6: 5, 5: 3}[t]
    return t, min(x for x, y in points), min(y for x, y in points)


def hollow_scene(palette=0, scale=1., turns=0, *, closed_void=False):
    background, ink = PALETTES[palette]
    inner = tuple(min(255, c+3) for c in background)
    raster = Image.new('RGB', (800, 608), background)
    pen = ImageDraw.Draw(raster)
    teachers = [(3, 96, 96), (3, 192, 96), (3, 288, 96)]
    def triangle(key, fill=None, closed=True):
        t, x, y = key
        if closed_void:
            tile = Image.new('RGB', (32, 32), background)
            local = ImageDraw.Draw(tile)
            poly = list(VERTICES[t])
            local.polygon(poly, fill=inner)
            local.line(poly+[poly[0]], fill=ink, width=3)
            raster.paste(tile, (x, y))
        else:
            poly = [(x+u, y+v) for u, v in VERTICES[t]]
            if closed:
                pen.polygon(poly, fill=inner if fill is None else fill)
            pen.line([poly[1], poly[0], poly[2]]+([poly[1]] if closed else []), fill=ink, width=3)
    for key in teachers:
        triangle(key)
    if closed_void:
        actual = [rotate(key, turns) for key in ((6, 400, 272), (6, 432, 272), (6, 416, 304))]
        false = {rotate((3, 416, 272), turns)}
    else:
        actual = [rotate((5 if i%2 == 0 else 4, 416, 256+16*i), turns) for i in range(5)]
        triangle((3, 560, 96), closed=False)
        triangle((3, 560, 288), fill=ink)
        x, y = 560, 192
        pen.rectangle((x, y, x+31, y+31), outline=ink, width=3)
        pen.line((x, y, x+31, y+31), fill=ink, width=3)
        pen.line((x, y+31, x+31, y), fill=ink, width=3)
        for mx, my in ((560, 400), (576, 400)):
            poly = [(mx+u/2, my+v/2) for u, v in VERTICES[3]]
            pen.polygon(poly, fill=inner)
            pen.line(poly+[poly[0]], fill=ink, width=2)
        nearby = {(t, x+dx, y+dy) for _, x, y in actual for dx in (-8, 0, 8)
                  for dy in (-8, 0, 8) for t in VERTICES}
        false = nearby-set(actual) | {(3, 560, 96), (3, 560, 192), (3, 560, 288),
                               (3, 560, 384), (3, 560, 392), (3, 560, 400)}
    for key in actual:
        triangle(key)
    raster = raster.resize((round(800*scale), round(608*scale)), Image.Resampling.BILINEAR)
    image = RGBImage(raster.width, raster.height, raster.tobytes())
    # Locator directions are deliberately wrong: RGB must establish identity.
    locators = [(4, x, y) for _, x, y in teachers]
    return image, Box(0, 0, image.width, image.height), locators, set(actual), false


class HollowGlyphTests(unittest.TestCase):
    def evidence(self, image, room, locators, *, framed=False):
        frame = SourceFrame(image, room) if framed else None
        library = SourceGlyphLibrary(image, room, locators, source_frame=frame)
        return HollowGlyphEvidence(library, locators)

    def test_180_true_and_4788_false_across_palette_scale_rotation(self):
        positives = negatives = 0
        for palette in range(3):
            for scale in (1., 1.25, .75):
                for turn in range(4):
                    with self.subTest(palette=palette, scale=scale, turn=turn):
                        image, room, locators, true, false = hollow_scene(palette, scale, turn)
                        before = hashlib.sha256(image.data).hexdigest()
                        evidence = self.evidence(image, room, locators)
                        for key in sorted(true):
                            self.assertTrue(evidence.support(key)['passed'], key)
                        for key in sorted(false):
                            self.assertFalse(evidence.support(key)['passed'], key)
                        self.assertEqual(before, hashlib.sha256(image.data).hexdigest())
                        positives += len(true)
                        negatives += len(false)
        self.assertEqual((positives, negatives), (180, 4788))

    def test_108_true_and_36_closed_voids_with_original_ink_fallback(self):
        for palette in range(3):
            for scale in (1., 1.25, .75):
                for turn in range(4):
                    with self.subTest(palette=palette, scale=scale, turn=turn):
                        image, room, locators, true, false = hollow_scene(palette, scale, turn, closed_void=True)
                        evidence = self.evidence(image, room, locators, framed=True)
                        for key in sorted(true):
                            self.assertTrue(evidence.support(key)['passed'], key)
                        for key in false:
                            answer = evidence.support(key)
                            self.assertFalse(answer['passed'], key)
                            self.assertTrue(answer['source_neighbor_explained_proof'])

    def test_signed_edge_cache_is_query_order_independent(self):
        image, room, locators, true, false = hollow_scene(closed_void=True)
        keys = sorted(true | false)
        first = self.evidence(image, room, locators)
        second = self.evidence(image, room, locators)
        forward = {key: first.support(key) for key in keys}
        reverse = {key: second.support(key) for key in reversed(keys)}
        self.assertEqual(forward, reverse)
        self.assertTrue(all(len(key) == 5 for key in first.owned_edges))

    def test_two_teachers_do_not_learn_or_use_queries_to_teach(self):
        image, room, locators, true, _ = hollow_scene()
        evidence = self.evidence(image, room, locators[:2])
        self.assertEqual(evidence.models, [])
        for key in true:
            self.assertFalse(evidence.support(key)['passed'])
        self.assertEqual(evidence.models, [])

    def test_returned_proofs_are_independent_and_models_stay_frozen(self):
        image, room, locators, true, _ = hollow_scene()
        evidence = self.evidence(image, room, locators)
        key = sorted(true)[0]
        expected = evidence.support(key)
        actual = evidence.support(key)
        actual['proof'].clear()
        self.assertEqual(expected, evidence.support(key))
        self.assertTrue(all(k in {tuple(t) for t in evidence.original_spikes}
                            or k[1:] in {tuple(t[1:]) for t in evidence.original_spikes}
                            for m in evidence.models for k in m['independent_teachers']))

    def test_mini_and_invalid_direction_cannot_borrow_full_identity(self):
        image, room, locators, _, _ = hollow_scene()
        evidence = self.evidence(image, room, locators)
        with self.assertRaises(ValueError):
            evidence.support((7, 416, 256))
        self.assertFalse(evidence.support((3, -8, 256))['passed'])

    def test_frame_factory_preserves_complete_teacher_and_query_proofs(self):
        image, room, locators, true, false = hollow_scene(closed_void=True)
        frame = SourceFrame(image, room)
        original = HollowGlyphEvidence(SourceGlyphLibrary(image, room, locators, source_frame=frame), locators)
        direct = HollowGlyphEvidence.from_frame(frame, locators, pixel_cache_limit=17)
        self.assertEqual(original.models, direct.models)
        self.assertEqual(original.inset_original_owners, direct.inset_original_owners)
        for key in sorted(true | false):
            self.assertEqual(original.support(key), direct.support(key))
        self.assertLessEqual(len(direct.library._pixels), 17)

    def test_out_of_snapshot_library_anchors_cannot_become_teachers(self):
        image, room, locators, true, _ = hollow_scene()
        library = SourceGlyphLibrary(image, room, locators)
        evidence = HollowGlyphEvidence(library, locators[:2])
        self.assertEqual(evidence.models, [])
        self.assertFalse(evidence.support(sorted(true)[0])['passed'])

    def test_band_is_lazy_so_impossible_ink_stops_sampling(self):
        image, room, locators, _, _ = hollow_scene()
        evidence = self.evidence(image, room, locators)
        from unittest.mock import patch
        with patch.object(evidence.library, 'pixel', wraps=evidence.library.pixel) as pixel:
            rows = evidence.band((416, 256), (432, 288), 2)
            self.assertEqual(pixel.call_count, 0)
            next(rows)
            self.assertEqual(pixel.call_count, 5)

    def test_frame_factory_rejects_invalid_locators_or_cache(self):
        image, room, locators, _, _ = hollow_scene()
        frame = SourceFrame(image, room)
        for keys, cache in (([(12, 96, 96)], 4), ([(3, 96)], 4), (locators, -1), (locators, True)):
            with self.assertRaises(ValueError):
                HollowGlyphEvidence.from_frame(frame, keys, pixel_cache_limit=cache)


if __name__ == '__main__':
    unittest.main()
