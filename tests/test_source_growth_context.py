"""Explicit per-source growth plumbing; no application/global instrumentation."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from jtool_scanner.geometry import Box
from scripts.source_evidence_context import SourceEvidenceContext
from scripts.source_geometry_pipeline import joint_proposals, source_proposals
from scripts.source_growth_confidence import qualify_independent_growth
from scripts.source_material_evidence import native_cells
from tests.test_source_growth_confidence import POINTS, field, role_proof


def setup_context(*, cache_limit=4, flat=False, originals=()):
    source = field((20, 40, 70), (20, 40, 70)) if flat else field()
    context = SourceEvidenceContext(source.image, source.room, (), material_cache_limit=cache_limit)
    raw = dict(labels={p: 1 for p in POINTS}, centers=[(60, 120, 140), (80, 170, 210), (20, 40, 70)],
               selected={0}, expanded_proof=role_proof(), tips={2: 5}, backs={})
    context.record_material_calibration(**raw)
    context.begin_growth(originals)
    context.record_growth_sizing(originals, {(2, *POINTS[0])}, set())
    return source, context, raw


def select(context, originals=()):
    evidence = context.growth_evidence(originals)
    evidence.pop('observations')
    return qualify_independent_growth({(2, *POINTS[0])}, set(), room=context._room,
        joint_cells=(), phase_positive=(), **evidence)


class SourceGrowthContextTests(TestCase):
    def test_calibration_before_binding_survives_cache_hit_zero_and_saturation(self):
        answers = []
        for capacity in (0, 1, 4):
            source, context, _ = setup_context(cache_limit=capacity)
            for stage in ('eligible', 'intrinsic', 'local', 'distributed', 'intrinsic'):
                context.material_result(source.image, source.room, (), stage, (), lambda: (set(), {}))
            answers.append(select(context))
        self.assertTrue(all(answer == answers[0] for answer in answers))
        self.assertEqual(answers[0][0], {(2, *POINTS[0])})

    def test_calibration_and_returned_proofs_are_copy_isolated(self):
        _, context, raw = setup_context()
        expected = select(context)
        raw['labels'].clear()
        raw['centers'][1] = (0, 0, 0)
        raw['selected'].clear()
        raw['expanded_proof'].clear()
        evidence = context.growth_evidence(())
        evidence['calibrations'][0]['labels'].clear()
        evidence['calibrations'][0]['approved'].clear()
        evidence['observations'].clear()
        self.assertEqual(select(context), expected)

    def test_duplicate_native_calibration_is_deduplicated_not_new_teachers(self):
        _, context, raw = setup_context()
        before = context.growth_evidence(())
        context.record_material_calibration(**raw)
        after = context.growth_evidence(())
        self.assertEqual(before, after)
        self.assertEqual(len(after['calibrations']), 1)

    def test_conflicting_calibration_is_rejected_without_poisoning_old_result(self):
        _, context, raw = setup_context()
        expected = select(context)
        raw['labels'][POINTS[0]] = 2
        with self.assertRaisesRegex(ValueError, 'calibration changed'):
            context.record_material_calibration(**raw)
        self.assertEqual(select(context), expected)

    def test_complete_nonterrain_identity_validated_even_after_cached_qualification(self):
        original = [SimpleNamespace(type_id=12, x=640, y=480, kind='save', score=.9,
                                    image_box=Box(640, 480, 32, 32))]
        _, context, _ = setup_context(originals=original)
        select(context, original)
        for attribute, value in (('x', 624), ('image_box', Box(160, 128, 32, 32)), ('score', .8)):
            changed = deepcopy(original)
            setattr(changed[0], attribute, value)
            with self.assertRaisesRegex(ValueError, 'original detections changed'):
                context.growth_evidence(changed)
        with self.assertRaisesRegex(ValueError, 'original detections changed'):
            context.begin_growth(original + [SimpleNamespace(type_id=1, x=32, y=32)])

    def test_original_anchor_exclusion_is_not_reused_from_another_source_context(self):
        _, clean, _ = setup_context()
        anchor = SimpleNamespace(type_id=12, x=160, y=128, image_box=Box(160, 128, 16, 16))
        _, marked, _ = setup_context(originals=(anchor,))
        self.assertEqual(clean.growth_evidence(())['calibrations'][0]['approved'], {0, 1})
        self.assertEqual(marked.growth_evidence((anchor,))['calibrations'][0]['approved'], {0})

    def test_source_frame_and_rgb_mutation_rejected_even_after_warm_cache(self):
        for attribute in ('data', 'width'):
            source, context, _ = setup_context()
            select(context)
            if attribute == 'data':
                source.image.data = bytes(len(source.image.data))
            elif attribute == 'width':
                source.image.width -= 1
            with self.assertRaises(ValueError):
                select(context)
        source, context, _ = setup_context()
        select(context)
        with self.assertRaises(ValueError):
            source_proposals(source.image, Box(0, 0, 768, 608), (), source_context=context,
                             include_growth_confidence=True)

    def test_missing_calibration_is_unknown_not_positive_and_missing_provenance_fails(self):
        source = field()
        context = SourceEvidenceContext(source.image, source.room, ())
        context.begin_growth(())
        with self.assertRaisesRegex(ValueError, 'sizing provenance'):
            context.growth_evidence(())
        context.record_growth_sizing((), {(2, *POINTS[0])}, set())
        evidence = context.growth_evidence(())
        self.assertEqual(evidence['calibrations'], ())
        self.assertEqual(evidence['original_foreground_queries'], ())
        self.assertEqual(select(context)[0], set())

    def test_existing_texture_is_shared_without_constructing_another_or_extending_teachers(self):
        _, context, _ = setup_context()
        library = SimpleNamespace(teachers=[(64, 64)], support=Mock(return_value={'passed': True}))
        context.record_growth_texture((), library)
        self.assertIs(context.growth_evidence(())['original_texture_libraries'][0], library)
        select(context)
        self.assertEqual(library.teachers, [(64, 64)])
        library.support.assert_not_called()  # qualified role already sufficient
        context.begin_growth(())
        context.record_growth_sizing((), set(), set())
        self.assertEqual(context.growth_evidence(())['original_texture_libraries'], ())

    def test_independent_simultaneous_contexts_match_serial_source_proofs(self):
        cases = [setup_context(flat=flat)[1] for flat in (False, True)]
        expected = [select(context) for context in cases]
        # Fresh contexts exercise cold qualification in both threads.
        cases = [setup_context(flat=flat)[1] for flat in (False, True)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(select, cases)), expected)
        self.assertNotEqual(expected[0][0], expected[1][0])

    def test_native_cells_records_calibration_before_cached_material_return(self):
        source = field()
        context = SourceEvidenceContext(source.image, source.room, ())
        expected = native_cells(source.image, source.room, ())
        actual = context.material_result(source.image, source.room, (), 'intrinsic', (),
            lambda: native_cells(source.image, source.room, (), source_context=context))
        self.assertEqual(actual, expected)
        context.begin_growth(())
        context.record_growth_sizing((), set(), set())
        evidence = context.growth_evidence(())
        self.assertEqual(len(evidence['calibrations']), 1)
        self.assertEqual(evidence['calibrations'][0]['approved'], set())

    def test_sizing_provenance_is_explicit_not_inferred_from_detection_kind(self):
        source, context, _ = setup_context()
        full = (1, 320, 320)
        with patch('scripts.source_geometry_pipeline.source_size_repair', return_value=({full}, set(), {})), \
             patch('scripts.source_geometry_pipeline.material_cells', return_value=(set(), {})):
            joint_proposals(source.image, source.room, (), source_context=context, include_growth_confidence=True)
        self.assertEqual(context.growth_evidence(())['sizing'], frozenset({full}))

    def test_explicit_switch_requires_boolean_and_default_never_qualifies_growth(self):
        source = field()
        with self.assertRaisesRegex(ValueError, 'Growth confidence flag'):
            source_proposals(source.image, source.room, (), include_growth_confidence=1)
        with patch.object(SourceEvidenceContext, 'growth_evidence', side_effect=AssertionError('Default remains off')):
            _, _, diagnostic = source_proposals(source.image, source.room, (), include_hollow_glyphs=False)
        self.assertNotIn('source_growth_confidence', diagnostic)
