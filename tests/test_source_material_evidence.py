"""Backing/shadow/background and original-source field-sharing safeguards."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from PIL import Image
from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_material_evidence import BackingCoreRoles, MaterialBoundary, SourceRectangles, add_boundary_primitives, expand_shadows, native_cells
from scripts.source_material_patterns import pattern_cells
from scripts.source_material_ownership import material_cells
from tests.test_source_glyph_prototypes import scene


class SourceMaterialEvidenceTests(TestCase):
    def setUp(self):
        self.image = RGBImage(800, 608, bytes(800*608*3))
        self.room = Box(0, 0, 800, 608)

    def test_constant_source_without_roles_emits_no_material(self):
        context = SourceEvidenceContext(self.image, self.room, [])
        cells, diag = material_cells(self.image, self.room, [], source_context=context)
        self.assertEqual(cells, set())
        self.assertEqual(diag['source_glyph_models'], [])
        self.assertEqual(diag['intrinsic_geometry_appearance_evidence_retained'], [])

    def test_material_field_and_normalized_rgb_are_context_local_exact_reuses(self):
        context = SourceEvidenceContext(self.image, self.room, [])
        first = context.rectangles(self.image, self.room, [])
        self.assertIs(first, context.rectangles(self.image, self.room, []))
        raw = context.native_pixels(self.image, self.room)
        self.assertIs(raw, context.native_pixels(self.image, self.room))
        self.assertEqual(raw, self.image.data)
        self.assertTrue(first.contours._squared_norm)
        self.assertFalse(context.contours()._squared_norm)
        with self.assertRaises(ValueError):
            context.rectangles(self.image, Box(0, 0, 768, 608), [])

    def test_backing_rectangle_priority_does_not_invent_glyph_exclusion(self):
        roles = BackingCoreRoles(SourceRectangles(self.image, self.room))
        with patch.object(roles.field.raw, 'box_faces', return_value=[12]*4), \
             patch.object(roles.field, 'owner', side_effect=AssertionError('Rectangle already qualified')):
            self.assertTrue(roles.eligible(160, 160))
        self.assertEqual(roles.rejected, [])

    def test_actual_original_glyph_can_exclude_hazard_painted_backing(self):
        image, room, _, _, _ = scene(size=32)
        roles = BackingCoreRoles(SourceRectangles(image, room))
        owner = roles.glyph_owner(176, 176)
        self.assertIsNotNone(owner)
        self.assertEqual(owner['source_owner'], [3, 160, 160])
        self.assertGreaterEqual(owner['core_owned_pixels'], 48)
        self.assertIs(owner, roles.glyph_owner(176, 176))
        self.assertEqual(len(roles.rejected), 1)

    def test_shadow_needs_independent_geometry_and_relative_rgb_axis(self):
        centers = [scanner._ColorProfile(v, v, v, 0.) for v in (200, 0, 120)]
        for faces, expected in (([12]*4, {0, 2}), ([8]*4, {0})):
            with self.subTest(faces=faces):
                field = SimpleNamespace(box_faces=lambda *args: faces)
                accepted, proof = expand_shadows(field, {(64, 64): 2}, centers, {0}, {1: 3}, {1: 0})
                self.assertEqual(accepted, expected)
                if proof:
                    self.assertAlmostEqual(proof[0]['independent_color_roles'][0]['attenuation'], .6)

    def test_original_tips_survive_rejected_foreground_backing(self):
        spikes = [(3, x, 128) for x in (160, 256, 352)]
        labels = {(x+dx, 160): 0 for _, x, _ in spikes for dx in (0, 16)}
        centers = [scanner._ColorProfile(v, v, v, 0.) for v in (200, 0)]
        field = SimpleNamespace(color=lambda *args: centers[1], triangle_closed=lambda *args: True,
                                box_faces=lambda *args: [12]*4)
        with patch('scripts.source_material_evidence.rectangle_field', return_value=field), \
             patch('scripts.source_material_evidence.BackingCoreRoles') as roles, \
             patch('scripts.source_material_evidence.scanner._cluster_repeated_terrain_cells', return_value=(labels, centers)):
            roles.return_value.eligible.return_value = False
            roles.return_value.rejected = []
            cells, diag = native_cells(self.image, self.room, spikes)
        self.assertEqual(cells, set())
        self.assertEqual(diag['back_votes'], {})
        self.assertEqual(diag['tip_votes'], {1: 3})
        self.assertEqual(diag['background_back_votes'], {0: 3})
        self.assertEqual(len(diag['background_anchors']), 3)

    def test_unwitnessed_background_is_unknown_not_empty(self):
        field = MaterialBoundary(self.image, self.room, [], {})
        self.assertIsNone(field.patch_background(160, 160))
        support, unknown = field.face_background((160, 160), (192, 160), (0, -1))
        self.assertEqual(support, 0)
        self.assertTrue(unknown)

    def test_clipped_source_samples_do_not_become_background(self):
        field = MaterialBoundary(self.image, self.room, [], {})
        self.assertIsNone(field.values(-1, 0, 2, 2))
        self.assertIsNone(field.patch_background(0, 0))

    def test_invalid_pattern_mode_rejected_before_source_work(self):
        with self.assertRaisesRegex(ValueError, 'Pattern mode'):
            pattern_cells(self.image, self.room, [], mode='room-specific')

    def test_shared_normalization_equals_existing_raster_at_capture_scale(self):
        image, room, _, _, _ = scene(size=32, palette=2, scale=1.25)
        context = SourceEvidenceContext(image, room, [])
        raster = Image.frombytes('RGB', (image.width, image.height), image.data).crop(
            (room.x, room.y, room.right, room.bottom)).resize((800, 608), Image.Resampling.BILINEAR)
        self.assertEqual(context.native_pixels(image, room), raster.tobytes())

    def test_background_patch_cannot_mix_distinct_witness_distributions(self):
        raster = Image.new('RGB', (800, 608))
        raster.putpixel((160, 160), (255, 255, 255))
        field = MaterialBoundary(RGBImage(800, 608, raster.tobytes()), self.room, [], {})
        field.models = [dict(bounds=((v, v),)*3) for v in (0, 255)]
        self.assertTrue(field.is_bg((0, 0, 0)))
        self.assertTrue(field.is_bg((255, 255, 255)))
        self.assertFalse(field.patch_background(161, 161, 2))

    def test_unknown_boundary_faces_do_not_fill_new_containers(self):
        cells = {(160, 160), (176, 160), (160, 176), (176, 176)}
        original = {(160, 160)}
        diag = dict(rectangle_faces=[dict(native=p) for p in sorted(cells)], native16_primitive=sorted(original))
        with patch('scripts.source_material_evidence.MaterialBoundary') as boundary, \
             patch('scripts.source_material_evidence.rectangle_field') as raw:
            boundary.return_value.face_background.return_value = (12, True)
            boundary.return_value.models = []
            raw.return_value.triangle_closed.return_value = False
            result, proof = add_boundary_primitives(self.image, self.room, [], original, diag)
        self.assertEqual(result, original)
        self.assertEqual(proof['material_boundary_containers'], [])

    def test_isolated_glyphs_are_not_terrain_across_palette_and_scale(self):
        for palette in range(4):
            for scale in (1., 1.25):
                with self.subTest(palette=palette, scale=scale):
                    image, room, spikes, _, _ = scene(size=32, palette=palette, scale=scale)
                    context = SourceEvidenceContext(image, room, spikes)
                    cells, diag = material_cells(image, room, spikes, source_context=context)
                    self.assertEqual(cells, set())
                    self.assertEqual(diag['intrinsic_geometry_appearance_evidence_retained'], [])
