"""Generated source-only tests; no private corpus, maps or room-specific rules."""
from copy import deepcopy
from math import ceil, dist, floor, inf, nextafter
import math
from random import Random
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_full_spike_phase import SourceFullSpikePhaseEvidence
from scripts.source_interior_glyphs import _OriginalPaintIndex
from scripts.source_sampling import SourceFrame
from scripts.source_phase_registration import (
    SourcePhaseRegistrationAmbiguity as PhaseRegistrationAmbiguity,
    _paint_within as paint_within,
)



def _flat_scene(*,scale=1,sx=1,sy=1,ox=0,oy=0,transform=lambda c:c,local=None,positions=None,size=32,squares=False):
    foreground=transform((210,150,70));background=transform((20,30,60))
    width,height=round(800*scale),round(608*scale)
    raster=Image.new('RGB',(width,height),background);draw=ImageDraw.Draw(raster)
    if positions is None:positions=[(3+(r+c)%4,48+c*112,48+r*96) for r in range(5) for c in range(6)]
    original=[]
    for kind,x,y in positions:
        dx,dy=(0,0) if local is None else local(kind,x,y)
        points=[(scale*(sx*(x+a*size/32)+ox+dx),scale*(sy*(y+b*size/32)+oy+dy)) for a,b in VERTICES[kind]]
        if squares:draw.rectangle((points[0][0],scale*(sy*y+oy+dy),scale*(sx*(x+size)+ox+dx),scale*(sy*(y+size)+oy+dy)),fill=foreground)
        else:draw.polygon(points,fill=foreground)
        original.append(SimpleNamespace(type_id=kind,x=x,y=y))
    image=RGBImage(width,height,raster.tobytes());room=Box(0,0,width,height)
    return SourceFrame(image,room),tuple(original),dict(foreground=foreground,background=background,limit=.25*math.dist(foreground,background))


def scene(**kwargs):
    options = dict(kwargs)
    if options.get('positions') is None:
        options['positions'] = ([(3+(r+c) % 4, 48+c*112, 48+r*96)
                                 for r in range(5) for c in range(6)]
                                + [(3, 104, 104), (4, 152, 104), (5, 200, 104)])
    frame, original, model = _flat_scene(**options)
    image = frame.original_snapshot()
    raster = Image.frombytes('RGB', (image.width, image.height), image.data)
    scale = options.get('scale', 1)
    sx, sy, ox, oy = (options.get(k, default) for k, default in
                     (('sx', 1), ('sy', 1), ('ox', 0), ('oy', 0)))
    transform = options.get('transform', lambda c: c)
    size = options.get('size', 32)
    local = options.get('local')
    fg = tuple(model['foreground'])
    for d in original:
        dx, dy = (0, 0) if local is None else local(d.type_id, d.x, d.y)
        left, top = scale*(sx*d.x+ox+dx), scale*(sy*d.y+oy+dy)
        right, bottom = left+scale*sx*size, top+scale*sy*size
        for y in range(max(0, floor(top)), min(image.height, ceil(bottom)+1)):
            for x in range(max(0, floor(left)), min(image.width, ceil(right)+1)):
                if raster.getpixel((x, y)) != fg:
                    continue
                a = ((x+.5)/scale-ox-dx)/sx-d.x
                b = ((y+.5)/scale-oy-dy)/sy-d.y
                u, v = ((a, b) if d.type_id == 3 else (b, 32-a) if d.type_id == 4
                        else (32-b, a) if d.type_id == 5 else (32-a, 32-b))
                delta = round(12*(u-16)/16 + 8*(v-16)/16)
                raster.putpixel((x, y), transform(tuple(c+delta for c in (210, 150, 70))))
    image = RGBImage(image.width, image.height, raster.tobytes())
    return SourceFrame(image, frame.room), original, model


def context(values, original=None):
    frame = values[0]; original = values[1] if original is None else tuple(original)
    field = SourceFullSpikePhaseEvidence(FilledGlyphEvidence(frame, original), original, source_grid=(25, 19))
    return field, original


def displaced(key, amount=8):
    kind, x, y = key
    dx, dy = {3: (0, amount), 4: (amount, 0), 5: (-amount, 0), 6: (0, -amount)}[kind]
    return kind, x+dx, y+dy


class PhaseRegistrationAmbiguityTests(unittest.TestCase):
    def test_flat_art_is_not_self_certified_as_directional_texture(self):
        field, original = context(_flat_scene())
        d = original[24]; old = (d.type_id, d.x, d.y); new = displaced(old)
        proof = PhaseRegistrationAmbiguity(field, original, [(old, new)], source_grid=(25, 19)).probe(old, new)
        self.assertFalse(proof['ambiguous'])
        if 'old_body' in proof:
            self.assertFalse(proof['old_body']['passed'])

    def test_foreign_body_frame_and_original_snapshot_are_rejected(self):
        values = scene(); field, original = context(values)
        d = original[24]; old = (d.type_id, d.x, d.y); new = displaced(old)
        with self.assertRaises(ValueError):
            PhaseRegistrationAmbiguity(None, original, [(old, new)], source_grid=(25, 19))
        foreign = SimpleNamespace(original=original, body=field.body,
                                  frame=SourceFrame(values[0].original_snapshot(), values[0].room))
        with self.assertRaises(ValueError):
            PhaseRegistrationAmbiguity(foreign, original, [(old, new)], source_grid=(25, 19))
        with self.assertRaises(ValueError):
            PhaseRegistrationAmbiguity(field, original[:-1], [(old, new)], source_grid=(25, 19))

    def test_actual_full_squares_are_not_triangle_registration_witnesses(self):
        values = scene()
        raster = Image.new('RGB', (800, 608), (20, 30, 60))
        draw = ImageDraw.Draw(raster)
        for d in values[1]:
            draw.rectangle((d.x, d.y, d.x+31, d.y+31), fill=(210, 150, 70))
        image = RGBImage(800, 608, raster.tobytes())
        field, original = context((SourceFrame(image, Box(0, 0, 800, 608)), values[1], values[2]))
        d = original[24]; old = (d.type_id, d.x, d.y); new = displaced(old)
        proof = PhaseRegistrationAmbiguity(field, original, [(old, new)], source_grid=(25, 19)).probe(old, new)
        self.assertFalse(proof['source_proof']['available'])
        self.assertFalse(proof['ambiguous'])

    def test_positive_old_source_under_coherent_capture_drift_all_scales(self):
        for scale in (.5, 1., 1.25):
            with self.subTest(scale=scale):
                values = scene(scale=scale, sx=1.025, sy=1.025, ox=-4, oy=-3)
                field, original = context(values)
                old = (original[24].type_id, original[24].x, original[24].y)
                proof = PhaseRegistrationAmbiguity(field, original, [(old, displaced(old))],
                                                  source_grid=(25, 19)).probe(old, displaced(old))
                self.assertTrue(proof['source_proof']['available'], proof)
                self.assertTrue(proof['ambiguous'], proof)
                self.assertTrue(proof['source_proof']['mapping_NOT_certified'])

    def test_all_four_directions_palette_polarity_and_brightness(self):
        transforms = (lambda c: c, lambda c: tuple(255-v for v in c),
                      lambda c: (c[2], c[0], c[1]), lambda c: tuple(round(.4*v) for v in c))
        for index, transform in enumerate(transforms):
            with self.subTest(kind=3+index):
                values = scene(sx=1.025, sy=1.025, ox=-4, oy=-3, transform=transform)
                field, original = context(values)
                d = original[24+index]; old = (d.type_id, d.x, d.y); new = displaced(old)
                self.assertTrue(PhaseRegistrationAmbiguity(field, original, [(old, new)],
                    source_grid=(25, 19)).probe(old, new)['ambiguous'])

    def test_isolated_real_eight_and_sixteen_pixel_errors_are_not_vetoed(self):
        for index in range(4):
            for amount in (8, 16):
                with self.subTest(kind=3+index, amount=amount):
                    values = scene(); raw = list(values[1]); d = raw[24+index]
                    new = (d.type_id, d.x, d.y); old = displaced(new, amount)
                    raw[24+index] = SimpleNamespace(type_id=old[0], x=old[1], y=old[2])
                    field, original = context(values, raw)
                    proof = PhaseRegistrationAmbiguity(field, original, [(old, new)],
                                                      source_grid=(25, 19)).probe(old, new)
                    self.assertTrue(proof['source_proof']['available'], proof)
                    self.assertFalse(proof['ambiguous'], proof)
                    self.assertTrue(proof['new_body']['passed'] and proof['new_geometry']['passed'], proof)

    def test_isoluminant_original_rgb_is_preserved(self):
        fg, bg = (150, 80, 65), (80, 120, 40)
        self.assertEqual(Image.new('RGB', (1, 1), fg).convert('L').getpixel((0, 0)),
                         Image.new('RGB', (1, 1), bg).convert('L').getpixel((0, 0)))
        values = scene(transform=lambda c: bg if c == (20, 30, 60) else tuple(fg[k]+c[k]-(210,150,70)[k] for k in range(3)))
        field, original = context(values)
        d = original[24]; old = (d.type_id, d.x, d.y); new = displaced(old)
        self.assertTrue(PhaseRegistrationAmbiguity(field, original, [(old, new)],
            source_grid=(25, 19)).probe(old, new)['ambiguous'])

    def test_all_old_and_new_query_boxes_are_excluded_before_fit(self):
        values = scene(); field, original = context(values)
        pairs = [((d.type_id, d.x, d.y), displaced((d.type_id, d.x, d.y))) for d in original[24:27]]
        guard = PhaseRegistrationAmbiguity(field, original, pairs, source_grid=(25, 19))
        proof = guard.probe(*pairs[0])['source_proof']
        self.assertTrue(proof['available'], proof)
        all_queries = [key for pair in pairs for key in pair]
        for key in proof['paint_teachers'] + tuple(proof['child_original_fulls']):
            self.assertTrue(all(abs(key[1]-q[1]) >= 32 or abs(key[2]-q[2]) >= 32 for q in all_queries))
        for pair in proof['hypothesis']['pairs']:
            self.assertTrue(all(abs(pair['key'][1]-q[1]) >= 32 or abs(pair['key'][2]-q[2]) >= 32
                                for q in all_queries))

    def test_one_shared_frame_and_child_domain_for_several_queries(self):
        values = scene(); field, original = context(values)
        pairs = [((d.type_id, d.x, d.y), displaced((d.type_id, d.x, d.y))) for d in original[24:27]]
        import scripts.source_phase_registration as module
        with patch.object(module, 'FilledGlyphEvidence', wraps=FilledGlyphEvidence) as built:
            guard = PhaseRegistrationAmbiguity(field, original, pairs, source_grid=(25, 19))
            for pair in pairs:
                guard.probe(*pair)
            guard.probe(*pairs[0])
        self.assertEqual(built.call_count, 1)

    def test_no_proposals_performs_no_source_work(self):
        field, original = context(scene())
        with patch('scripts.source_phase_registration._registration_frame_hypothesis', side_effect=AssertionError('No source work')):
            proof = PhaseRegistrationAmbiguity(field, original, (), source_grid=(25, 19)).proof()
        self.assertFalse(proof['available'])
        self.assertIn('no source work', proof['reason'])

    def test_insufficient_originals_minis_and_rectangular_art_are_not_counterproof(self):
        for values in (scene(size=16), scene(squares=True)):
            field, original = context(values)
            d = original[24]; old = (d.type_id, d.x, d.y); new = displaced(old)
            proof = PhaseRegistrationAmbiguity(field, original, [(old, new)],
                                              source_grid=(25, 19)).probe(old, new)
            self.assertFalse(proof['source_proof']['available'], proof)
            self.assertFalse(proof['ambiguous'])
        values = scene(); field, original = context(values, values[1][:8])
        d = original[0]; old = (d.type_id, d.x, d.y)
        self.assertFalse(PhaseRegistrationAmbiguity(field, original, [(old, displaced(old))], source_grid=(25, 19)).probe(old, displaced(old))['ambiguous'])

    def test_nonlinear_mapping_cannot_be_cleaned_by_outlier_removal(self):
        values = scene(local=lambda k, x, y: (0, 8 if (y-48)//96 % 2 else -8))
        field, original = context(values); d = original[24]
        old = (d.type_id, d.x, d.y); new = displaced(old)
        proof = PhaseRegistrationAmbiguity(field, original, [(old, new)], source_grid=(25, 19)).probe(old, new)
        self.assertFalse(proof['source_proof']['available'], proof)
        self.assertFalse(proof['ambiguous'])

    def test_unknown_coverage_and_compact_domain_do_not_supply_counterproof(self):
        field, original = context(scene()); d = original[24]
        old = (d.type_id, d.x, d.y); new = displaced(old)
        self.assertFalse(PhaseRegistrationAmbiguity(field, original, [(old, new)], source_grid=(19, 13)).probe(old, new)['ambiguous'])
        guard = PhaseRegistrationAmbiguity(field, original, [(old, new)], source_grid=(25, 19))
        with patch.object(SourceFrame, 'rectangle_available', return_value=False):
            self.assertFalse(guard.probe(old, new)['ambiguous'])

    def test_nonoriginal_duplicate_wrong_kind_and_unbounded_queries_rejected(self):
        field, original = context(scene()); d = original[24]
        old = (d.type_id, d.x, d.y); new = displaced(old)
        for pairs in ([(new, old)], [(old, new), (old, new)], [(old, (4, old[1]+8, old[2]))],
                      [(old, (old[0], old[1]+24, old[2]))]):
            with self.assertRaises(ValueError):
                PhaseRegistrationAmbiguity(field, original, pairs, source_grid=(25, 19))
        guard = PhaseRegistrationAmbiguity(field, original, [(old, new)], source_grid=(25, 19))
        with self.assertRaises(ValueError):
            guard.probe(old, (old[0], old[1]+16, old[2]))

    def test_original_pixels_metadata_models_and_returned_proofs_are_isolated(self):
        field, original = context(scene()); d = original[24]
        old = (d.type_id, d.x, d.y); new = displaced(old)
        before = deepcopy((original, field.filled.library.anchors, field.filled.library.models))
        rgb = field.frame.original_snapshot().data
        guard = PhaseRegistrationAmbiguity(field, original, [(old, new)], source_grid=(25, 19))
        proof = guard.probe(old, new); expected = deepcopy(proof)
        proof['source_proof'].clear()
        self.assertEqual(guard.probe(old, new), expected)
        self.assertEqual(before, (original, field.filled.library.anchors, field.filled.library.models))
        self.assertEqual(rgb, field.frame.original_snapshot().data)


class OriginalPaintRadiusTests(unittest.TestCase):
    def assert_exact(self, paints, pixels, limits):
        index = _OriginalPaintIndex(paints)
        for rgb in pixels:
            expected = min(dist(rgb, p) for p in paints)
            self.assertEqual(index.distance(rgb), expected)
            for closed, strict in limits:
                self.assertEqual(paint_within(index, rgb, closed, strict),
                    expected <= closed and expected < strict, (paints, rgb, closed, strict))

    def test_random_raw_rgb_and_distinct_palette_clouds(self):
        rng = Random(50971)
        for _ in range(24):
            paints = tuple(tuple(rng.randrange(256) for _ in range(3)) for _ in range(31))
            pixels = [tuple(rng.randrange(256) for _ in range(3)) for _ in range(160)]
            self.assert_exact(paints, pixels, ((0, 1), (8, 8), (32, 16), (16, 32), (255, inf), (inf, 64)))

    def test_exact_splitting_plane_closed_and_strict_boundary_ties(self):
        paints = ((10, 10, 10), (20, 10, 10), (30, 10, 10), (40, 10, 10), (50, 10, 10))
        self.assert_exact(paints, [(x, 10, 10) for x in range(61)],
            ((5, 5), (5, nextafter(5, inf)), (nextafter(5, 0), 6), (0, 0), (0, 1), (-1, 20)))

    def test_polarity_permutation_dim_and_original_colour_queries(self):
        raw = ((20, 30, 60), (210, 150, 70), (150, 80, 65), (80, 120, 40))
        transforms = (lambda c: c, lambda c: tuple(255-v for v in c),
                      lambda c: (c[2], c[0], c[1]), lambda c: tuple(round(.4*v) for v in c))
        for transform in transforms:
            paints = tuple(transform(c) for c in raw)
            self.assert_exact(paints, paints+((0, 0, 0), (255, 255, 255)), ((0, 1), (8, 8), (32, 64)))

    def test_nonraw_rgb_and_paints_keep_exhaustive_distance_fallback(self):
        self.assert_exact(((10.5, 20., 30.), (40., 50., 60.)),
            ((10, 20, 30), (10.5, 20.5, 30.5), (-1, 270, 0)), ((.5, .5), (1, 1), (32, inf)))
        self.assert_exact(((10, 20, 30), (40, 50, 60)),
            ((10.5, 20.5, 30.5), (-1, 270, 0)), ((0, 1), (32, 32), (inf, inf)))

    def test_empty_unknown_and_zero_strict_radius_are_not_invented_paints(self):
        with self.assertRaises(ValueError):
            paint_within(_OriginalPaintIndex(()), (10, 20, 30), 8, 8)
        with self.assertRaises(TypeError):
            paint_within(_OriginalPaintIndex(((10, 20, 30),)), None, 8, 8)
        self.assertFalse(paint_within(_OriginalPaintIndex(((10, 20, 30),)), (10, 20, 30), 8, 0))
