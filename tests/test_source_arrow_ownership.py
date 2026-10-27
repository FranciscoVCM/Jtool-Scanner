"""Portable arrow ownership, real hazard overlap and original-source boundaries."""
from copy import deepcopy
from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image, ImageDraw

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.runtime_sources import source_geometry_files
from scripts.source_arrow_ownership import (
    _arrow_models, _outside_arrow_segments,
    explain_arrow_owned_spike, prune_arrow_owned_spikes,
)
from scripts.source_contours import EdgeEvidence
from scripts.source_sampling import SourceFrame


def scene(*, down=True, stroke=1, scale=1., extra=None,
          background=(190, 165, 220), hazard_fill=(245, 240, 225),
          hazard_outline=(25, 25, 25)):
    canvas = Image.new('RGB', (800, 608), background)
    draw = ImageDraw.Draw(canvas)
    x, y = 320, 224
    color = (80, 180, 245) if down else (235, 90, 75)
    pointer = [(16, 0), (0, 18), (10, 18), (10, 31),
               (22, 31), (22, 18), (31, 18)]
    if down:
        pointer = [(a, 31-b) for a, b in pointer]
    pointer = [(x+a, y+b) for a, b in pointer]
    triangle = ((16, 32), (0, 0), (32, 0)) if down else ((16, 0), (0, 32), (32, 32))
    if extra == 'plain_triangle':
        draw.polygon([(x+a, y+b) for a, b in triangle], fill=color)
    else:
        if extra == 'coincident':
            draw.polygon([(x+a, y+b) for a, b in triangle],
                         fill=hazard_fill, outline=hazard_outline)
        if extra in ('overlap', 'adjacent'):
            hx, hy = x+(16 if extra == 'overlap' else 24), y+8
            draw.polygon(((hx+16, hy), (hx, hy+32), (hx+32, hy+32)),
                         fill=(245, 240, 225), outline=(25, 25, 25))
        draw.polygon(pointer, fill=color)
        if stroke:
            draw.line(pointer+[pointer[0]], fill=(55, 75, 90), width=stroke)
    if extra == 'textured_background':
        # Texture on observed odd-centre samples, not invisible sub-grid stripes.
        for sx in range(x+1, x+32, 4):
            draw.line((sx, y, sx, y+31), fill=(30, 35, 45), width=2)
    if scale != 1:
        canvas = canvas.resize((round(800*scale), round(608*scale)),
                               Image.Resampling.BILINEAR)
    image = RGBImage(canvas.width, canvas.height, canvas.tobytes())
    room = Box(0, 0, image.width, image.height)
    owner = scanner.Detection('gravity_down' if down else 'gravity_up',
        25 if down else 24, x, y, .9, Box(0, 0, 32, 32))
    candidate = scanner._geometry_detection('portable_candidate', 6 if down else 3,
                                            x, y, .7, image, room, 32)
    return image, room, candidate, owner


class SourceArrowOwnershipTests(TestCase):
    def proof(self, **kwargs):
        image, room, candidate, owner = scene(**kwargs)
        return explain_arrow_owned_spike(image, room, candidate, owner,
                                         source_grid=(25, 19))

    def test_up_down_and_filled_outlined_source_styles(self):
        for down in (False, True):
            for stroke in (0, 1, 2):
                with self.subTest(down=down, stroke=stroke):
                    proof = self.proof(down=down, stroke=stroke)
                    self.assertTrue(proof['passed'], proof)
                    self.assertFalse(proof['unowned_candidate_edge_sites'])
                    self.assertGreaterEqual(proof['arrow_shape_precision'], .90)
                    self.assertGreaterEqual(proof['arrow_shape_recall'], .90)

    def test_background_and_fractional_source_capture(self):
        for scale, background in ((1.25, (35, 45, 65)),
                                  (1.5, (230, 225, 210)), (1., (160, 190, 130))):
            with self.subTest(scale=scale, background=background):
                self.assertTrue(self.proof(scale=scale, background=background)['passed'])

    def test_local_rgb_background_gradient_is_not_a_palette_identity(self):
        image, room, candidate, owner = scene()
        canvas = Image.frombytes('RGB', (image.width, image.height), image.data)
        for dy in range(32):
            for dx in range(32):
                point = owner.x+dx, owner.y+dy
                if canvas.getpixel(point) == (190, 165, 220):
                    canvas.putpixel(point, (160+dx, 140+dy, 200+(dx+dy)//4))
        gradient = RGBImage(image.width, image.height, canvas.tobytes())
        self.assertTrue(explain_arrow_owned_spike(gradient, room, candidate, owner,
                                                 source_grid=(25, 19))['passed'])

    def test_same_colour_triangle_does_not_verify_a_marker(self):
        for down in (False, True):
            with self.subTest(down=down):
                self.assertFalse(self.proof(down=down, extra='plain_triangle')['passed'])

    def test_actual_visible_overlapping_and_adjacent_hazards_survive(self):
        for extra, dx in (('overlap', 16), ('adjacent', 24)):
            with self.subTest(extra=extra):
                image, room, alias, owner = scene(extra=extra)
                actual = scanner._geometry_detection('real_drawn_hazard', 3,
                    owner.x+dx, owner.y+8, .7, image, room, 32)
                self.assertFalse(explain_arrow_owned_spike(image, room, actual, owner,
                                                          source_grid=(25, 19))['passed'])

    def test_coincident_visible_hazard_under_marker_survives(self):
        for down in (False, True):
            with self.subTest(down=down):
                self.assertFalse(self.proof(down=down, extra='coincident')['passed'])

    def test_faint_coincident_hazard_is_not_erased_by_bright_marker(self):
        for down in (False, True):
            for scale in (1., 1.25, 1.5):
                with self.subTest(down=down, scale=scale):
                    proof = self.proof(down=down, scale=scale, extra='coincident',
                        hazard_fill=(185, 160, 211), hazard_outline=(185, 160, 211))
                    self.assertFalse(proof['passed'], proof)

    def test_nearly_isoluminant_hazard_keeps_rgb_contour_evidence(self):
        # ~0.012 luminance difference, but a genuine original RGB boundary.
        for down in (False, True):
            with self.subTest(down=down):
                proof = self.proof(down=down, extra='coincident',
                    hazard_fill=(201, 160, 217), hazard_outline=(201, 160, 217))
                self.assertFalse(proof['passed'], proof)
                self.assertTrue(proof['rgb_coexistence']['retain'])

    def test_unknown_rgb_slope_never_authorizes_retirement(self):
        with patch('scripts.source_arrow_ownership.SourceContours.edge',
                   return_value=EdgeEvidence(0, True, ())):
            proof = self.proof()
        self.assertFalse(proof['passed'])
        self.assertTrue(proof['rgb_coexistence']['retain'])
        self.assertTrue(all(r['unknown'] for r in proof['rgb_coexistence']['rows']))

    def test_slope_clipping_preserves_original_lines_not_mask_boundaries(self):
        self.assertEqual(_outside_arrow_segments((0, 0), (10, 10),
            [(2, 2, 5, 5), (4, 4, 8, 8), (1, 8, 2, 9)]),
            [((0., 0.), (2., 2.)), ((8., 8.), (10., 10.))])
        self.assertEqual(_outside_arrow_segments((10, 10), (0, 0), [(2, 2, 8, 8)]),
            [((10., 10.), (8., 8.)), ((2., 2.), (0., 0.))])
        self.assertEqual(_outside_arrow_segments((1, 1), (1, 9), [(0, 0, 2, 10)]), [])

    def test_observed_texture_cannot_teach_local_background(self):
        self.assertFalse(self.proof(extra='textured_background')['passed'])

    def test_only_full_geometry_and_existing_arrow_types_qualify(self):
        image, room, candidate, owner = scene()
        for other in (1, 2, 7, 8, 9, 10, 18, 21, 22):
            with self.subTest(other=other):
                self.assertFalse(explain_arrow_owned_spike(image, room,
                    replace(candidate, type_id=other), owner, source_grid=(25, 19))['passed'])
        self.assertFalse(explain_arrow_owned_spike(image, room, candidate,
            replace(owner, type_id=18), source_grid=(25, 19))['passed'])

    def test_unknown_grid_crop_and_source_frame_abstain(self):
        image, room, candidate, owner = scene()
        wrong = SourceFrame(image, Box(0, 0, 768, 608))
        for options in (dict(source_grid=(19, 13)),
                        dict(source_grid=(25, 19), source_frame=wrong)):
            with self.subTest(options=options):
                proof = explain_arrow_owned_spike(image, room, candidate, owner, **options)
                self.assertFalse(proof['passed'])
                self.assertTrue(proof['unknown'])
        self.assertFalse(explain_arrow_owned_spike(image, room,
            replace(candidate, x=-8), owner, source_grid=(25, 19))['passed'])

    def test_native_hypotheses_are_not_shifted_to_fit_sprite(self):
        image, room, candidate, owner = scene()
        before = deepcopy((candidate, owner))
        explain_arrow_owned_spike(image, room, candidate, owner, source_grid=(25, 19))
        self.assertEqual((candidate, owner), before)

    def test_returned_proof_is_independent_of_immutable_geometry_cache(self):
        image, room, candidate, owner = scene()
        first = explain_arrow_owned_spike(image, room, candidate, owner, source_grid=(25, 19))
        expected = deepcopy(first)
        first['foreground_ink_cells'].clear()
        first['arrow_source_shape'].clear()
        self.assertEqual(explain_arrow_owned_spike(image, room, candidate, owner,
                                                 source_grid=(25, 19)), expected)
        for parameters, mask in _arrow_models(True):
            self.assertIsInstance(parameters, tuple)
            self.assertIsInstance(mask, frozenset)

    def test_pruning_preserves_actual_instances_order_and_non_geometry(self):
        image, room, alias, owner = scene()
        real = scanner._geometry_detection('far_real_spike', 3, 64, 64, .88,
                                           image, room, 32)
        mini = replace(alias, type_id=7, x=384)
        block = replace(alias, type_id=1, x=416)
        detections = [real, owner, mini, alias, block]
        original = deepcopy(detections)
        kept, proof = prune_arrow_owned_spikes(detections, image, room,
                                               source_grid=(25, 19))
        self.assertEqual(detections, original)
        self.assertEqual(kept, [real, owner, mini, block])
        self.assertEqual(proof['retired'], [(alias.type_id, alias.x, alias.y)])
        self.assertTrue(all(a is b for a, b in zip(kept, [real, owner, mini, block])))

    def test_no_owner_fast_path_does_not_query_image_or_models(self):
        image, room, candidate, owner = scene()
        detections = [candidate]
        with patch('scripts.source_arrow_ownership.explain_arrow_owned_spike') as measure:
            kept, proof = prune_arrow_owned_spikes(detections, image, room,
                                                   source_grid=(25, 19))
        self.assertIs(kept, detections)
        self.assertEqual(proof['retired'], [])
        measure.assert_not_called()

    def test_public_runtime_identity_includes_the_source_helper(self):
        self.assertIn('source_arrow_ownership.py', {p.name for p in source_geometry_files()})

    def ambiguous_source_models(self):
        image, room, candidate, owner = scene()
        proof = explain_arrow_owned_spike(image, room, candidate, owner, source_grid=(25, 19))
        self.assertTrue(proof['passed'])
        foreground = frozenset(map(tuple, proof['foreground_ink_cells']))
        patch_features = scanner._patch_features(image, room, candidate.x, candidate.y, 32)
        edges = [(candidate.x+i % 16*2+1, candidate.y+i // 16*2+1)
                 for i, hit in enumerate(patch_features.edge_mask) if hit]
        for x, y in edges:
            nearby = {p for p in foreground
                      if owner.x+2*p[0]-2 <= x < owner.x+2*p[0]+4
                      and owner.y+2*p[1]-2 <= y < owner.y+2*p[1]+4}
            if nearby and len(nearby) <= .1*len(foreground):
                reduced = foreground-nearby
                self.assertGreaterEqual(len(reduced)/len(foreground), .90)
                return image, room, candidate, owner, foreground, reduced, (x, y)
        self.fail('Adversarial scene must include an admissible independent edge')

    def test_unmodelled_foreground_cannot_explain_geometry(self):
        image, room, candidate, owner, foreground, reduced, edge = self.ambiguous_source_models()
        models = (((16, 32, 12, 1, (0, 0)), reduced),)
        with patch('scripts.source_arrow_ownership._arrow_models', return_value=models):
            proof = explain_arrow_owned_spike(image, room, candidate, owner, source_grid=(25, 19))
        self.assertFalse(proof['passed'])
        self.assertIn(edge, proof['unowned_candidate_edge_sites'])

    def test_best_fit_cannot_hide_other_admissible_shape_uncertainty(self):
        image, room, candidate, owner, foreground, reduced, edge = self.ambiguous_source_models()
        # Two equally supported source fits, not a perfect fit versus an
        # inferior one. The first preserves all observed edges; the second
        # leaves this independent edge unexplained at the same fit rank.
        patch_features = scanner._patch_features(image, room, candidate.x, candidate.y, 32)
        edges = [(candidate.x+i % 16*2+1, candidate.y+i // 16*2+1)
                 for i, hit in enumerate(patch_features.edge_mask) if hit]
        omitted = foreground-reduced
        first = set(foreground)
        count = 0
        for point in sorted(reduced, key=lambda p: (abs(p[0]-8)+abs(p[1]-8), p)):
            proposed = first-{point}
            if all(any(owner.x+2*x-2 <= ex < owner.x+2*x+4
                       and owner.y+2*y-2 <= ey < owner.y+2*y+4
                       for x, y in proposed) for ex, ey in edges):
                first = proposed
                count += 1
                if count == len(omitted):
                    break
        self.assertEqual(count, len(omitted))
        self.assertEqual(len(first), len(reduced))
        models = (((16, 32, 12, 1, (0, 0)), frozenset(first)),
                  ((18, 32, 12, 1, (0, 0)), reduced))
        with patch('scripts.source_arrow_ownership._arrow_models', return_value=models):
            proof = explain_arrow_owned_spike(image, room, candidate, owner, source_grid=(25, 19))
        self.assertFalse(proof['passed'])
        self.assertEqual(proof['admissible_arrow_shapes'], 2)
        self.assertIn(edge, proof['unowned_candidate_edge_sites'])
