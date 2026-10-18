"""Portable censored-base positives and explicit unknown/impostor protections."""
from copy import deepcopy
from unittest import TestCase

from PIL import Image, ImageDraw
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.spike_shape import VERTICES
from scripts.source_capture_base import CaptureBaseEvidence, capture_base_hypotheses
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_glyph_prototypes import _contains
from scripts.source_sampling import SourceFrame
from tests.test_source_filled_pipeline import TEACHERS, scene

TARGETS = ((3, 224, 576), (6, 224, 0), (4, 0, 288), (5, 768, 288))


def edge_scene(target, *, scale=1., transform=lambda c: c,
               background=(20, 30, 60), foreground=(210, 150, 70), shape='triangle'):
    frame, original = scene(background=background, foreground=foreground, transform=transform)
    image = frame.original_snapshot()
    raster = Image.frombytes('RGB', (800, 608), image.data)
    t, x, y = target
    poly = [(x+u, y+v) for u, v in VERTICES[t]]
    draw = ImageDraw.Draw(raster)
    if shape == 'triangle':
        for py in range(y, y+32):
            for px in range(x, x+32):
                if _contains(poly, px+.5, py+.5):
                    draw.point((px, py), fill=transform(foreground))
    elif shape == 'rectangle':
        draw.rectangle((x, y, x+31, y+31), fill=transform(foreground))
    elif shape == 'outline':
        draw.line(poly+[poly[0]], fill=transform(foreground), width=2)
    elif shape == 'text':
        draw.text((x+8, y+8), '8', fill=transform(foreground))
    elif shape == 'line':
        draw.line((x, y, x+31, y+31), fill=transform(foreground), width=2)
    if scale != 1:
        raster = raster.resize((round(800*scale), round(608*scale)), Image.Resampling.BILINEAR)
    image = RGBImage(raster.width, raster.height, raster.tobytes())
    return SourceFrame(image, Box(0, 0, image.width, image.height)), original


class SourceCaptureBaseTests(TestCase):
    def test_four_directions_with_original_source_models(self):
        for key in TARGETS:
            with self.subTest(key=key):
                frame, original = edge_scene(key)
                evidence = FilledGlyphEvidence(frame, original)
                self.assertFalse(evidence.support(key)['passed'])
                proof = CaptureBaseEvidence(evidence).support(key)
                self.assertTrue(proof['passed'], proof)
                self.assertEqual(len(proof['best']['independent_filled_teachers']), 3)

    def test_hue_polarity_brightness_and_fractional_capture_scales(self):
        transforms = (lambda c: c, lambda c: tuple(255-v for v in c),
                      lambda c: (c[2], c[0], c[1]), lambda c: tuple(round(.25*v) for v in c))
        for transform in transforms:
            for scale in (.75, 1., 1.25):
                frame, original = edge_scene(TARGETS[0], scale=scale, transform=transform)
                proof = CaptureBaseEvidence(FilledGlyphEvidence(frame, original)).support(TARGETS[0])
                self.assertTrue(proof['passed'], (scale, proof))

    def test_isoluminant_original_rgb_is_not_erased(self):
        bg, fg = (80, 120, 40), (150, 80, 65)
        self.assertEqual(Image.new('RGB', (1, 1), bg).convert('L').getpixel((0, 0)),
                         Image.new('RGB', (1, 1), fg).convert('L').getpixel((0, 0)))
        frame, original = edge_scene(TARGETS[3], background=bg, foreground=fg)
        self.assertTrue(CaptureBaseEvidence(FilledGlyphEvidence(frame, original)).support(TARGETS[3])['passed'])

    def test_rectangles_lines_text_outline_and_empty_are_not_filled_glyphs(self):
        for shape in ('rectangle', 'line', 'text', 'outline', 'empty'):
            frame, original = edge_scene(TARGETS[0], shape=shape)
            evidence = CaptureBaseEvidence(FilledGlyphEvidence(frame, original))
            for key in ((3, 224, 576), (3, 216, 576), (3, 232, 576)):
                self.assertFalse(evidence.support(key)['passed'], (shape, key))

    def test_interior_weak_or_attached_base_is_not_this_channel(self):
        frame, original = scene()
        evidence = CaptureBaseEvidence(FilledGlyphEvidence(frame, original))
        self.assertFalse(evidence.support((5, 224, 288))['passed'])
        self.assertIn('boundary', evidence.support((5, 224, 288))['reason'])

    def test_two_or_duplicate_witnesses_cannot_teach(self):
        frame, original = edge_scene(TARGETS[0])
        for witnesses in (original[:2], original[:1]*3):
            self.assertFalse(CaptureBaseEvidence(FilledGlyphEvidence(frame, witnesses)).support(TARGETS[0])['passed'])

    def test_unknown_side_context_is_not_silently_censored_as_base_context(self):
        key = (3, 0, 576)
        frame, original = edge_scene(key)
        proof = CaptureBaseEvidence(FilledGlyphEvidence(frame, original)).support(key)
        self.assertFalse(proof['passed'])

    def test_physical_crop_not_surrounding_pixels_defines_capture_boundary(self):
        frame, original = edge_scene(TARGETS[0])
        source = frame.original_snapshot()
        raster = Image.new('RGB', (820, 628), (210, 150, 70))
        raster.paste(Image.frombytes('RGB', (800, 608), source.data), (10, 10))
        image = RGBImage(raster.width, raster.height, raster.tobytes())
        cropped = SourceFrame(image, Box(10, 10, 800, 608))
        evidence = CaptureBaseEvidence(FilledGlyphEvidence(cropped, original))
        self.assertTrue(evidence.support(TARGETS[0])['passed'])
        self.assertEqual(capture_base_hypotheses(cropped), capture_base_hypotheses(frame))

    def test_affine_rgb_background_gradient_does_not_change_object_identity(self):
        frame, original = edge_scene(TARGETS[0])
        source = frame.original_snapshot()
        raster = Image.frombytes('RGB', (800, 608), source.data)
        for y in range(608):
            for x in range(800):
                delta = round(8*x/800+8*y/608)
                raster.putpixel((x, y), tuple(v+delta for v in raster.getpixel((x, y))))
        changed = RGBImage(800, 608, raster.tobytes())
        evidence = CaptureBaseEvidence(FilledGlyphEvidence(SourceFrame(changed, frame.room), original))
        self.assertTrue(evidence.support(TARGETS[0])['passed'])

    def test_output_mutation_does_not_change_proof_or_teacher_model(self):
        frame, original = edge_scene(TARGETS[0])
        source = FilledGlyphEvidence(frame, original)
        models = deepcopy(source.library.models)
        evidence = CaptureBaseEvidence(source)
        answer = evidence.support(TARGETS[0])
        pristine = deepcopy(answer)
        answer['mask'].clear()
        answer['best']['original_source_witnesses'].clear()
        self.assertEqual(evidence.support(TARGETS[0]), pristine)
        self.assertEqual(source.library.models, models)

    def test_query_pool_is_finite_directional_and_contains_no_answer_input(self):
        frame, _ = edge_scene(TARGETS[0])
        queries = capture_base_hypotheses(frame)
        self.assertEqual(len(queries), 340)
        self.assertTrue(set(TARGETS) <= queries)
        evidence = CaptureBaseEvidence(FilledGlyphEvidence(frame, scene()[1]))
        self.assertTrue(all(evidence.boundary(key) for key in queries))
        self.assertNotIn((3, 224, 568), queries)

    def test_invalid_lattice_and_key_inputs_fail_closed(self):
        frame, original = edge_scene(TARGETS[0])
        for step in (0, -1, True, 8.5):
            with self.assertRaises(ValueError):
                capture_base_hypotheses(frame, step=step)
        evidence = CaptureBaseEvidence(FilledGlyphEvidence(frame, original))
        for key in ((7, 224, 576), (3, -8, 576), (3, 224, 608), (True, 224, 576), (3, 224., 576)):
            with self.assertRaises(ValueError):
                evidence.support(key)
        with self.assertRaises(ValueError):
            CaptureBaseEvidence(object())

    def test_clipped_body_is_not_unknown_background(self):
        frame, original = edge_scene(TARGETS[0])
        image = frame.original_snapshot()
        # Remove eight actual source rows, retaining the original world extent.
        cropped = RGBImage(800, 600, image.data[:800*600*3])
        partial = SourceFrame(cropped, Box(0, 0, 800, 600), extent=Box(0, 0, 800, 608),
                              canonical=image)
        proof = CaptureBaseEvidence(FilledGlyphEvidence(partial, original)).support(TARGETS[0])
        self.assertFalse(proof['passed'])
        self.assertNotIn(TARGETS[0], capture_base_hypotheses(partial))

    def test_additive_scene_observation_preserves_original_locators(self):
        frame, original = edge_scene(TARGETS[0])
        saved = deepcopy(original)
        evidence = CaptureBaseEvidence(FilledGlyphEvidence(frame, original))
        accepted = {key for key in capture_base_hypotheses(frame) if evidence.support(key)['passed']}
        self.assertEqual(accepted, {TARGETS[0]})
        self.assertEqual(original, saved)
