"""Portable original-RGB frame preference, conflicts and strict bypass paths."""
from copy import deepcopy
from dataclasses import replace
from math import ceil, floor
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_frame_arbitration import _box_agrees, select_source_glyph_frame
from scripts.source_geometry_pipeline import source_proposals
from scripts.source_glyph_prototypes import SourceGlyphEvidence
from scripts.source_sampling import SourceFrame


KEYS = ((3, 128, 128), (4, 320, 144), (6, 224, 320))


def scene(keys=KEYS, *, scale=1, colors=((20, 30, 60), (210, 150, 70)), conflict=False):
    raster = Image.new('RGB', (800, 608), colors[0])
    draw = ImageDraw.Draw(raster)
    for t, x, y in keys:
        draw.polygon([(x+u, y+v) for u, v in VERTICES[t]], fill=colors[1])
    all_keys = list(keys)
    if conflict:
        all_keys.append((5, 520, 400))
        draw.polygon([(512+u, 408+v) for u, v in VERTICES[5]], fill=colors[1])
    canonical = RGBImage(800, 608, raster.tobytes())
    if scale != 1:
        raster = raster.resize((round(800*scale), round(608*scale)), Image.Resampling.BILINEAR)
    image = RGBImage(raster.width, raster.height, raster.tobytes())
    room = Box(0, 0, image.width, image.height)
    frame = SourceFrame(image, room, extent=Box(round(-8*scale), round(8*scale), room.width, room.height),
                        canonical=canonical)
    originals = [scanner.Detection('original', t, x, y, .9,
        Box(round(x*scale), round(y*scale), round(32*scale), round(32*scale))) for t, x, y in all_keys]
    return image, room, originals, frame


class SourceFrameArbitrationTests(TestCase):
    def select(self, values, **kwargs):
        return select_source_glyph_frame(*values, source_grid=(25, 19), **kwargs)

    def test_physical_dominance_across_rgb_polarity_brightness_and_fractional_scales(self):
        for colors in (((20,30,60),(210,150,70)), ((235,225,195),(45,105,185)),
                       ((80,120,40),(150,80,65)), ((20,30,10),(38,20,16))):
            for scale in (.75, 1, 1.25):
                with self.subTest(colors=colors, scale=scale):
                    values = scene(colors=colors, scale=scale)
                    original = deepcopy(values[2])
                    frame, field, proof = self.select(values)
                    self.assertTrue(proof['selected_physical'], proof)
                    self.assertEqual(frame.extent, values[1])
                    self.assertTrue(frame.matches_source(field.image, values[1]))
                    self.assertEqual(values[2], original)
                    self.assertEqual(proof['disjoint_witnesses'], sorted(KEYS))

    def test_one_offered_owner_vetoes_three_physical_witnesses(self):
        values = scene(conflict=True)
        frame, field, proof = self.select(values)
        self.assertIs(frame, values[3])
        self.assertIs(field.source_frame, frame)
        self.assertFalse(proof['selected_physical'])
        self.assertEqual(proof['conflict'], (5, 520, 400))

    def test_two_examples_or_one_line_cannot_establish_two_dimensional_mapping(self):
        for keys in (KEYS[:2], ((3,128,128),(4,320,128),(6,512,128)),
                     ((3,128,128),(4,128,320),(6,128,512))):
            with self.subTest(keys=keys):
                values = scene(keys)
                frame, _, proof = self.select(values)
                self.assertIs(frame, values[3])
                self.assertFalse(proof['selected_physical'])

    def test_original_image_box_is_not_a_fitted_halo(self):
        values = scene()
        d = values[2][-1]
        values[2][-1] = replace(d,image_box=Box(d.image_box.x+2, d.image_box.y, 32, 32))
        self.assertFalse(self.select(values)[2]['selected_physical'])

    def test_floor_and_ceil_quantization_are_accepted(self):
        room = Box(3,5,981,747)
        key = (3,128,128)
        expected = (3+128*981/800,5+128*747/608,32*981/800,32*747/608)
        for rounding in (floor,ceil):
            box = Box(*(rounding(v) for v in expected))
            self.assertTrue(_box_agrees(box,key,room))
        box = Box(*(ceil(v)+1 for v in expected))
        self.assertFalse(_box_agrees(box,key,room))

    def test_duplicate_locators_do_not_supply_extra_witnesses(self):
        values = scene(KEYS[:2])
        values[2].extend(deepcopy(values[2]))
        self.assertFalse(self.select(values)[2]['selected_physical'])

    def test_clipped_or_padded_third_witness_cannot_establish_a_frame(self):
        values = scene(KEYS[:2]+((6,224,0),))
        self.assertFalse(self.select(values)[2]['selected_physical'])

    def test_compact_and_direct_paths_do_not_build_raw_evidence(self):
        image, room, original, offered = scene()
        with patch('scripts.source_evidence_context.SourceEvidenceContext.glyph_field',
                   side_effect=AssertionError('Bypass must remain lazy')):
            frame, raw, proof = select_source_glyph_frame(image, room, original, offered,
                                                         source_grid=(19,13))
            self.assertIs(frame, offered)
            self.assertIsNone(raw)
            direct = SourceFrame(image, room)
            frame, raw, _ = self.select((image,room,original,direct))
            self.assertIs(frame, direct)
            self.assertIsNone(raw)

    def test_changed_source_and_new_teacher_reuse_are_rejected(self):
        image, room, original, offered = scene()
        context = SourceEvidenceContext(image, room, [(d.type_id,d.x,d.y) for d in original])
        with self.assertRaisesRegex(ValueError, 'locators changed'):
            self.select((image,room,original+[SimpleNamespace(type_id=7,x=640,y=320)],offered), source_context=context)
        changed = RGBImage(image.width,image.height,bytes(len(image.data)))
        with self.assertRaisesRegex(ValueError, 'Offered source frame'):
            self.select((changed,room,original,offered))

    def test_witness_order_and_duplicate_input_cannot_change_the_result(self):
        values = scene()
        first = self.select(values)[2]
        second = self.select((values[0],values[1],list(reversed(values[2]))*2,values[3]))[2]
        self.assertEqual(first,second)

    def test_shared_raw_context_uses_one_contour_field_without_building_prototypes(self):
        image, room, original, offered = scene()
        spikes = [(d.type_id,d.x,d.y) for d in original]
        context = SourceEvidenceContext(image, room, spikes)
        raw = context.glyph_field(image, room, spikes)
        self.assertIs(raw, context.glyph_field(image, room, spikes))
        self.assertIs(raw.raw.field, context.contours())
        frame, selected, proof = self.select((image,room,original,offered), source_context=context)
        self.assertTrue(proof['selected_physical'])
        self.assertIs(selected, raw)
        self.assertEqual(context.statistics()['glyph_builds'], 0)

    def test_mismatched_shared_raw_field_fails_before_material_work(self):
        image, room, original, offered = scene()
        direct_raw = SourceGlyphEvidence(image, room)
        with patch('scripts.source_geometry_pipeline.joint_proposals',
                   side_effect=AssertionError('Validate before material work')):
            with self.assertRaisesRegex(ValueError, 'Shared glyph field'):
                source_proposals(image,room,original,source_frame=offered,source_glyph_field=direct_raw)

    def test_source_hook_selects_once_and_forwards_frozen_originals(self):
        image, room, original, offered = scene()
        result = scanner.ScanResult(image_width=image.width,image_height=image.height,
            room_box=room,detections=original,source_grid=(25,19))
        snapshot = deepcopy(original)
        with patch.object(scanner,'_SOURCE_FRAME_ARBITRATION_ENABLED',True), \
                patch('scripts.source_geometry_pipeline.source_proposals',
                      return_value=(set(),set(),{})) as proposals:
            scanner._apply_source_geometry(result,image,source_frame=offered)
        self.assertEqual(proposals.call_count,1)
        self.assertEqual(proposals.call_args.args[2],snapshot)
        self.assertEqual(proposals.call_args.kwargs['source_frame'].extent,room)
        self.assertIsNotNone(proposals.call_args.kwargs['source_glyph_field'])
        self.assertIsNone(result.source_extent)
        self.assertEqual(result.detections,snapshot)
