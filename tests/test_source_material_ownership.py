"""Source identity, context samples and no new-object-as-teacher guards."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts.source_material_evidence import SourceRectangles
from scripts.source_material_ownership import ContextGlyphEvidence, qualify_growth, strict_glyph_ownership
from scripts.source_material_patterns import eligible_primitives
from tests.test_source_glyph_prototypes import scene


class SourceMaterialOwnershipTests(TestCase):
    def setUp(self):
        self.image = RGBImage(800, 608, bytes(800*608*3))
        self.room = Box(0, 0, 800, 608)

    def test_positive_glyph_teacher_exclusion_competes_all_directions(self):
        primitive = {(160, 160), (176, 160), (160, 176), (176, 176), (320, 320)}
        spikes = [(4, 160, 160)]
        before = deepcopy(spikes)
        library = SimpleNamespace(support=lambda t, x, y: dict(passed=(t, x, y) == (3, 160, 160)))
        with patch('scripts.source_material_patterns.boundary_primitives', return_value=(primitive, {'accepted': sorted(primitive)})), \
             patch('scripts.source_material_patterns.SourceGlyphLibrary', return_value=library) as build:
            cells, diag = eligible_primitives(self.image, self.room, spikes)
            self.assertEqual(build.call_args.args[2], spikes)
        self.assertEqual(cells, {(320, 320)})
        self.assertEqual(len(diag['source_pattern_teacher_exclusions']), 4)
        self.assertTrue(diag['teaching_only_no_existing_geometry_removal'])
        self.assertEqual(spikes, before)
        self.assertEqual(len(primitive), 5)

    def test_unknown_glyph_identity_does_not_exclude_original_rectangles(self):
        primitive = {(160, 160), (176, 160)}
        library = SimpleNamespace(support=lambda *args: dict(passed=False))
        with patch('scripts.source_material_patterns.boundary_primitives', return_value=(primitive, {})), \
             patch('scripts.source_material_patterns.SourceGlyphLibrary', return_value=library):
            cells, diag = eligible_primitives(self.image, self.room, [(3, 160, 160)])
        self.assertEqual(cells, primitive)
        self.assertEqual(diag['source_pattern_teacher_exclusions'], [])

    def test_context_coverage_without_real_body_cannot_invent_a_glyph(self):
        raw = SourceRectangles(self.image, self.room)
        field = ContextGlyphEvidence(raw, [(0, 0, 800, 608)], [])
        self.assertIsNone(field.owner(3, 160, 160))
        self.assertTrue(field.proofs)
        self.assertTrue(all(p['original'][0] == 0 for p in field.proofs.values()))
        self.assertTrue(any(p['covered_sites'] > 0 for p in field.proofs.values()))

    def test_clipped_context_edge_is_unknown_not_supported(self):
        field = ContextGlyphEvidence(SourceRectangles(self.image, self.room), [(0, 0, 800, 608)], [])
        support, unknown = field.edge((0, 160), (0, 192))
        self.assertEqual(support, 0)
        self.assertTrue(unknown)

    def test_context_rectangles_require_independent_raw_closure(self):
        cells = {(160, 160)}
        rejected, diag = qualify_growth(self.image, self.room, [(3, 160, 160)], cells,
                                       {'closed_cells': [(160, 160)]})
        self.assertEqual(diag['source_context_rectangles'], [])
        self.assertEqual(rejected, set())
        self.assertTrue(diag['competing_rectangle_evidence_raw'])
        self.assertEqual(diag['closure_threshold_unchanged'], 9)

    def test_real_raw_source_glyph_owns_core_without_generated_box_veto(self):
        image, room, _, _, _ = scene(size=32)
        cells = {(176, 176), (544, 448)}
        rejected, diag = strict_glyph_ownership(image, room, [(4, 160, 160)], cells)
        self.assertEqual(rejected, {(176, 176)})
        self.assertGreater(len(diag['source_local_glyph_owners']), 0)
        self.assertTrue(diag['existing_objects_not_deleted_from_locator_overlap'])
        self.assertEqual(cells, {(176, 176), (544, 448)})
