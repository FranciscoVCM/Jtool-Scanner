"""Unstubbed portable RGB/source queries, not image-specific answers."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from unittest import TestCase

from PIL import Image, ImageDraw

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_compact_rectangles import SourceRectangleContext, full_spike_backings, source_backing_rectangles
from scripts.source_grid_frame import frame_from_existing_grid


def scene(*, palette=0, size=(608, 416), target='pattern', origin=(0, 0), teachers=3, locator_offset=(0, 0)):
    colors = [((40, 50, 60), (170, 185, 210), (8, 21, 35), (110, 135, 165)),
              ((220, 205, 70), (50, 70, 110), (235, 240, 250), (90, 160, 130)),
              ((55, 150, 110), (200, 70, 180), (30, 240, 210), (120, 30, 45))][palette]
    background, fill, border, ink = colors
    raster = Image.new('RGB', (608, 416), background)
    draw = ImageDraw.Draw(raster)
    witnesses = [(160, 160), (320, 160), (160, 320)][:teachers]

    def tile(x, y, patterned=True):
        x, y = x - 96, y - 96
        draw.rectangle((x, y, x + 31, y + 31), fill=fill, outline=border, width=2)
        if patterned:
            draw.rectangle((x + 5, y + 5, x + 26, y + 26), outline=ink, width=1)
            for a, b in ((7, 7), (22, 7), (7, 22), (22, 22)):
                draw.rectangle((x + a, y + b, x + a + 2, y + b + 2), fill=border)

    for point in witnesses:
        tile(*point)
    query = (96, 416) if target == 'edge' else (448, 320)
    if target != 'empty':
        tile(*query, patterned=target != 'flat')
    tx, ty = query
    draw.polygon([(tx - 96, ty - 96), (tx + 16 - 96, ty - 32 - 96),
                  (tx + 32 - 96, ty - 96)], fill=fill)
    raster = raster.resize(size, Image.Resampling.BILINEAR)
    ox, oy = origin
    whole = Image.new('RGB', (size[0] + ox + 8, size[1] + oy + 9), (245, 3, 20))
    whole.paste(raster, (ox, oy))
    image = RGBImage(whole.width, whole.height, whole.tobytes())
    room = Box(ox, oy, *size)
    norm = scanner._normalize_room_to_jtool(image.crop(room), 19, 13)
    frame = frame_from_existing_grid(image, room, (19, 13), norm)
    dx, dy = locator_offset
    locators = [(1, x + dx, y + dy) for x, y in witnesses] + [(3, tx, ty - 32)]
    originals = [scanner.Detection('synthetic_original', t, x, y, .8, frame.geometry_box(x, y, 32))
                 for t, x, y in locators]
    return image, room, originals, frame, query


class SourceCompactRectangleTests(TestCase):
    def evaluate(self, settings=None, context=None):
        image, room, originals, frame, query = settings or scene()
        found, proof = source_backing_rectangles(image, room, originals,
            source_frame=frame, source_context=context)
        return found, proof, query

    def test_direction_derived_queries_do_not_assume_minis_are_full_backings(self):
        image, room, originals, frame, _ = scene()
        poses = [scanner.Detection('test', t, 200, 200, .8, Box(0, 0, 1, 1)) for t in (3, 4, 5, 6, 7, 14)]
        self.assertEqual(full_spike_backings(poses), {(200, 232), (168, 200), (232, 200), (200, 168)})

    def test_out_of_bounds_backings_are_not_clamped_to_source(self):
        poses = [scanner.Detection('test', t, x, y, .8, Box(0, 0, 1, 1))
                 for t, x, y in ((4, 0, 200), (6, 200, 0), (3, 200, 576), (5, 768, 200))]
        self.assertFalse(full_spike_backings(poses))

    def test_real_patterned_backing_across_palette_polarity_scale_and_crop(self):
        for settings in ({}, dict(palette=1), dict(palette=2), dict(size=(777, 531)), dict(origin=(7, 11))):
            with self.subTest(settings=settings):
                found, proof, query = self.evaluate(scene(**settings))
                self.assertEqual(found, {(1, *query)})
                self.assertEqual(proof['empty_glyph_teacher_count'], 0)
                self.assertTrue(proof['no_new_query_teachers'])
                for model in proof['original_rectangle_proof']['models']:
                    self.assertNotIn(query, model['teachers'])
                self.assertTrue(all(not row['teacher'] for row in proof['query_rows']))

    def test_neighboring_independently_supported_teacher_phases_are_retained(self):
        found, proof, query = self.evaluate(scene(locator_offset=(-8, 8)))
        self.assertEqual(found, {(1, *query)})
        self.assertTrue(proof['original_rectangle_proof']['models'])

    def test_flat_framed_interior_is_not_the_learned_artwork(self):
        found, proof, query = self.evaluate(scene(target='flat'))
        self.assertFalse(found)
        self.assertFalse(proof['query_rows'][0]['passed'])
        self.assertGreaterEqual(sum(n >= 9 for n in proof['query_rows'][0]['faces']), 2)

    def test_empty_backing_does_not_make_terrain(self):
        found, _, _ = self.evaluate(scene(target='empty'))
        self.assertFalse(found)

    def test_unknown_padding_abstains_without_building_teachers(self):
        found, proof, _ = self.evaluate(scene(target='edge'))
        self.assertFalse(found)
        self.assertIn('unknown', proof['query_rows'][0]['abstained'])
        self.assertIsNone(proof['original_rectangle_proof'])

    def test_two_witnesses_cannot_use_the_query_as_a_third_teacher(self):
        image, room, originals, frame, query = scene(teachers=2)
        originals = originals[:-1] * 3 + originals[-1:]
        found, proof, _ = self.evaluate((image, room, originals, frame, query))
        self.assertFalse(found)
        self.assertFalse(proof['original_rectangle_proof']['models'])

    def test_empty_query_set_skips_model_building_without_claiming_negative_evidence(self):
        image, room, originals, frame, query = scene()
        originals = originals[:-1]
        found, proof, _ = self.evaluate((image, room, originals, frame, query))
        self.assertFalse(found)
        self.assertFalse(proof['query_rows'])
        self.assertIsNone(proof['original_rectangle_proof'])

    def test_reuse_is_exact_and_returned_proofs_cannot_poison_models(self):
        settings = scene()
        image, room, originals, frame, _ = settings
        context = SourceRectangleContext(image, room, originals, frame)
        first = self.evaluate(settings, context)
        pristine = deepcopy(first)
        first[1]['query_rows'][0]['model_comparisons'][0]['frame_correlation'] = -99
        first[1]['original_rectangle_proof']['models'][0]['teachers'] = ((0, 0),)
        self.assertEqual(self.evaluate(settings, context), pristine)

    def test_complete_original_metadata_change_or_emitted_teacher_is_rejected(self):
        settings = scene()
        image, room, originals, frame, query = settings
        context = SourceRectangleContext(image, room, originals, frame)
        original = originals[0]
        for changed in (replace(original, score=original.score + .01),
                        replace(original, kind=original.kind + '_changed'),
                        replace(original, image_box=Box(0, 0, 1, 1))):
            originals[0] = changed
            with self.assertRaisesRegex(ValueError, 'original detections changed'):
                self.evaluate(settings, context)
        originals[0] = original
        added = scanner.Detection('emitted', 1, *query, .9, frame.geometry_box(*query, 32))
        with self.assertRaisesRegex(ValueError, 'original detections changed'):
            self.evaluate((image, room, originals + [added], frame, query), context)

    def test_changed_image_wrapper_or_frame_invalidates_context(self):
        image, room, originals, frame, query = scene()
        context = SourceRectangleContext(image, room, originals, frame)
        other = RGBImage(image.width, image.height, image.data)
        with self.assertRaisesRegex(ValueError, 'image/data/room changed'):
            self.evaluate((other, room, originals, frame, query), context)
        norm = scanner._normalize_room_to_jtool(image.crop(room), 19, 13)
        other_frame = frame_from_existing_grid(image, room, (19, 13), norm)
        with self.assertRaisesRegex(ValueError, 'frame changed'):
            self.evaluate((image, room, originals, other_frame, query), context)

    def test_changed_source_data_does_not_mutate_saved_frame(self):
        image, room, originals, frame, query = scene()
        context = SourceRectangleContext(image, room, originals, frame)
        pixel = frame.pixel(160.5, 160.5)
        image.data = bytes(len(image.data))
        with self.assertRaisesRegex(ValueError, 'image/data/room changed'):
            self.evaluate((image, room, originals, frame, query), context)
        self.assertEqual(frame.pixel(160.5, 160.5), pixel)

    def test_mutable_source_buffer_is_not_accepted_as_frozen_evidence(self):
        image, room, originals, frame, _ = scene()
        image.data = bytearray(image.data)
        with self.assertRaisesRegex(ValueError, 'immutable original RGB'):
            SourceRectangleContext(image, room, originals, frame)

    def test_changed_canonical_view_invalidates_reuse(self):
        image, room, originals, frame, query = scene()
        context = SourceRectangleContext(image, room, originals, frame)
        frame._canonical.data = bytes(len(frame.canonical_rgb))
        with self.assertRaisesRegex(ValueError, 'frame changed'):
            self.evaluate((image, room, originals, frame, query), context)

    def test_parallel_sources_do_not_share_teachers_or_context(self):
        settings = [scene(palette=palette) for palette in (0, 1)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(self.evaluate, settings))
        self.assertEqual([found for found, _, query in outputs], [{(1, 448, 320)}] * 2)

    def test_no_source_answer_is_emitted_or_input_mutated(self):
        settings = scene()
        image, room, originals, frame, query = settings
        before = deepcopy(originals)
        data = image.data
        self.evaluate(settings)
        self.assertEqual(originals, before)
        self.assertIs(image.data, data)
        self.assertTrue(all(d.type_id != 1 or (d.x, d.y) != query for d in originals))
