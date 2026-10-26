"""An independently source-proved pose retains exact discarded metadata.

These tests do not feed pending objects into the source model. The binding
tests isolate metadata selection from later, independently tested recovery.
"""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_interior_glyphs import SourceInteriorGlyphEvidence
from scripts.source_rejected_primaries import source_proved_primary_metadata
from scripts.source_sampling import SourceFrame
from tests.test_source_directional_texture import textured_scene
from tests.test_source_rejected_primaries import detection, scene


REQUIRED = ('passed', 'interior_appearance_recovery', 'complete_physical_source',
            'original_source_only', 'original_teachers_only', 'no_new_teachers',
            'no_retirement', 'native_hypothesis_unchanged')


class SourceProvedPrimaryMetadataTests(TestCase):
    def test_all_directions_retain_original_object_score_kind_and_image_box(self):
        room = Box(0, 0, 800, 608)
        candidates = tuple(replace(detection(t, 64*t, 128, room), score=.123456+t/100,
                                   image_box=Box(11*t, 17*t, 33, 31)) for t in (3, 4, 5, 6))
        keys = {(d.type_id, d.x, d.y) for d in candidates}
        selected = source_proved_primary_metadata(candidates, keys)
        self.assertEqual(set(selected), keys)
        for d in candidates:
            self.assertIs(selected[(d.type_id, d.x, d.y)], d)
        self.assertEqual(candidates, tuple(selected[(d.type_id, d.x, d.y)] for d in candidates))

    def test_identical_duplicates_select_one_original_not_new_geometry(self):
        candidate = scene()[4]
        key = (candidate.type_id, candidate.x, candidate.y)
        selected = source_proved_primary_metadata((candidate, candidate), (key, key))
        self.assertEqual(len(selected), 1)
        self.assertIs(selected[key], candidate)

    def test_ambiguous_original_metadata_is_rejected(self):
        candidate = scene()[4];key = (candidate.type_id, candidate.x, candidate.y)
        for other in (replace(candidate, score=.999), replace(candidate, image_box=Box(1, 2, 31, 33))):
            with self.subTest(other=other), self.assertRaisesRegex(ValueError, 'Ambiguous'):
                source_proved_primary_metadata((candidate, other), (key,))

    def test_bad_kind_nonprimary_and_wrong_candidate_type_are_rejected(self):
        candidate = scene()[4];key = (candidate.type_id, candidate.x, candidate.y)
        for invalid in (replace(candidate, kind='source_filled_glyph'),
                        replace(candidate, type_id=7),
                        SimpleNamespace(type_id=candidate.type_id, x=candidate.x, y=candidate.y)):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                source_proved_primary_metadata((invalid,), (key,))

    def test_keys_require_integer_full_spike_origins(self):
        candidate = scene()[4]
        for invalid in ((1, 64, 64), (7, 64, 64), (3, 64., 64), (3, True, 64),
                        (True, 64, 64), (3, 64), (3, 64, 64, 64)):
            with self.subTest(key=invalid), self.assertRaisesRegex(ValueError, 'integer full-spike'):
                source_proved_primary_metadata((candidate,), (invalid,))

    def test_mixed_equal_qualified_keys_are_validated_before_deduplication(self):
        for keys in (((3,64,64),(3,64.,64)), ((3,0,64),(3,False,64)),
                     ((3,64,1),(3,64,True)), ((3,64,64),(3.,64,64))):
            with self.subTest(keys=keys), self.assertRaisesRegex(ValueError, 'integer full-spike'):
                source_proved_primary_metadata((),keys)

    def test_candidate_native_components_cannot_be_float_or_boolean_aliases(self):
        candidate=scene()[4];key=(candidate.type_id,candidate.x,candidate.y)
        for changed in (dict(type_id=float(candidate.type_id)),dict(x=float(candidate.x)),
                        dict(y=float(candidate.y)),dict(type_id=True),dict(x=False),dict(y=True)):
            with self.subTest(changed=changed),self.assertRaisesRegex(ValueError, 'integer full-spike'):
                source_proved_primary_metadata((replace(candidate,**changed),),(key,))

    def test_empty_qualified_domain_does_not_inspect_candidates_or_emit(self):
        self.assertEqual(source_proved_primary_metadata((object(),), ()), {})
        self.assertEqual(source_proved_primary_metadata((), ((3, 64, 64),)), {})
        candidate = scene()[4]
        self.assertEqual(source_proved_primary_metadata((candidate,), ((3, 704, 512),)), {})


class QualifiedInteriorPrimaryMetadataBindingTests(TestCase):
    def setUp(self):
        self.set_scene()

    def set_scene(self, *, rotation=0, scale=1):
        image, room, frame, raw, key = textured_scene(rotation=rotation, scale=scale)
        original = tuple(detection(d.type_id, d.x, d.y, room) for d in raw)
        candidate = replace(detection(*key, room), score=.312345,
                            image_box=Box(447, 351, 33, 33))
        self.image, self.room, self.frame = image, room, frame
        self.original, self.candidate = original, candidate
        self.filled = FilledGlyphEvidence(frame, original)
        self.key = key
        # Actual original-source proof, not a handcrafted positive. The three
        # wrapper flags are exactly those added by recover_source_filled_glyphs.
        proof = SourceInteriorGlyphEvidence(self.filled, original, source_grid=(25, 19),
            require_directional_texture=True).support(key)
        self.assertTrue(proof['passed'], proof)
        self.proof = {**proof, 'interior_appearance_recovery': True,
                      'complete_physical_source': True, 'original_teachers_only': True}
        self.assertTrue(all(self.proof.get(flag) is True for flag in REQUIRED))

    def result(self, *, original=None, grid=(25, 19)):
        return scanner.ScanResult(self.image.width, self.image.height, self.room,
            list(self.original if original is None else original), source_grid=grid,
            infinite_jump=1, dot_kid=1, recognized_text='unchanged')

    def apply(self, *, proof=None, proposed=None, retired=(), original=None,
              primary=True, interior=True, frame=None, grid=(25, 19), accepted=None):
        proof = deepcopy(self.proof if proof is None else proof)
        proposed = {self.key} if proposed is None else set(proposed)
        retired = set(retired)
        original = self.original if original is None else tuple(original)
        frame = self.frame if frame is None else frame
        entries = [dict(key=self.key, evidence=proof)] if accepted is None else accepted

        def proposals(image, room, teachers, **options):
            self.assertEqual(tuple(teachers), original)
            self.assertNotIn(self.candidate, teachers)
            if options.get('record_filled_source'):
                context = options['source_context'];context.begin_growth(teachers)
                context.record_growth_sizing(teachers, set(), set())
                context.record_filled_source(teachers, options['source_frame'], self.filled)
            return proposed, retired, dict(source_filled=dict(accepted=entries), source_material={})

        # Later primary recovery is intentionally inert. Otherwise a valid later
        # proof could restore metadata and conceal a failed early guard test.
        def later(current, *args, **options):
            return list(current), dict(accepted=[])

        with patch.object(scanner, '_SOURCE_INTERIOR_GLYPHS_ENABLED', interior), \
             patch.object(scanner, '_SOURCE_REJECTED_PRIMARY_RECOVERY_ENABLED', primary), \
             patch.object(scanner, '_SOURCE_FULL_SPIKE_PHASE_ENABLED', False), \
             patch.object(scanner, '_SOURCE_COMPOUND_CONFLICTS_ENABLED', False), \
             patch.object(scanner, '_SOURCE_FRAME_ARBITRATION_ENABLED', False), \
             patch('scripts.source_geometry_pipeline.source_proposals', side_effect=proposals) as producer, \
             patch('scripts.source_rejected_primaries.recover_rejected_primaries', side_effect=later):
            result = scanner._apply_source_geometry(self.result(original=original, grid=grid), self.image,
                source_frame=frame, rejected_primary_spikes=(self.candidate,))
        return result, producer

    def test_complete_real_interior_proof_restores_exact_metadata_all_directions_scales(self):
        for rotation in range(4):
            for scale in (1, 1.25):
                with self.subTest(rotation=rotation, scale=scale):
                    self.set_scene(rotation=rotation, scale=scale)
                    frozen = deepcopy((self.original, self.filled.library.anchors, self.filled.library.models))
                    out, producer = self.apply()
                    self.assertTrue(any(d is self.candidate for d in out.detections))
                    self.assertEqual(len(out.detections), len(self.original)+1)
                    self.assertTrue(all(any(d is old for d in out.detections) for old in self.original))
                    self.assertEqual((self.original, self.filled.library.anchors, self.filled.library.models), frozen)
                    self.assertNotIn(self.key, self.filled.original_spikes)
                    context = producer.call_args.kwargs['source_context']
                    self.assertIs(context.filled_source(self.original, self.frame), self.filled)
                    self.assertEqual((out.infinite_jump, out.dot_kid, out.recognized_text), (1, 1, 'unchanged'))
                    self.assertEqual(out.structural_warnings, scanner.structural_scan_warnings(out.detections))

    def test_each_missing_false_or_nonboolean_required_flag_cannot_restore_early(self):
        for flag in REQUIRED:
            for value in ('missing', False, None, 1, 'true'):
                proof = deepcopy(self.proof)
                if value == 'missing':proof.pop(flag)
                else:proof[flag] = value
                with self.subTest(flag=flag, value=value):
                    out, _ = self.apply(proof=proof)
                    self.assertFalse(any(d is self.candidate for d in out.detections))
                    emitted = next(d for d in out.detections if (d.type_id, d.x, d.y) == self.key)
                    self.assertEqual((emitted.kind, emitted.score), ('source_filled_glyph', .9))

    def test_unknown_complete_proof_cannot_restore_early(self):
        for unknown in ('missing', True, 1, 'unknown', None, 0, ''):
            with self.subTest(unknown=unknown):
                proof={**self.proof,'unknown':unknown}
                if unknown=='missing':proof.pop('unknown')
                out, _ = self.apply(proof=proof)
                self.assertFalse(any(d is self.candidate for d in out.detections))
                self.assertEqual(next(d for d in out.detections if (d.type_id,d.x,d.y)==self.key).score, .9)

    def test_empty_or_unrelated_proof_cannot_select_original_metadata(self):
        for proof, accepted in (({}, None), (None, []),
                (None, [dict(key=(3,704,512), evidence=self.proof)])):
            with self.subTest(proof=proof, accepted=accepted):
                out, _ = self.apply(proof=proof, accepted=accepted)
                self.assertFalse(any(d is self.candidate for d in out.detections))

    def test_accepted_proof_without_new_proposal_cannot_emit(self):
        out, _ = self.apply(proposed=())
        self.assertEqual(out.detections, list(self.original))
        self.assertFalse(any(d is self.candidate for d in out.detections))

    def test_retired_pose_is_not_resurrected(self):
        out, _ = self.apply(retired=(self.key,))
        self.assertEqual(out.detections, sorted(self.original,key=lambda d:(d.type_id,d.y,d.x)))
        self.assertFalse(any((d.type_id, d.x, d.y) == self.key for d in out.detections))

    def test_existing_pose_metadata_is_never_replaced(self):
        existing = replace(self.candidate, kind='retained_source_object', score=.87654)
        original = (*self.original, existing)
        # The already-surviving pose legitimately belongs to this input's
        # ORIGINAL teacher set. Record that exact set, not the earlier fixture.
        def proposals(image,room,teachers,**options):
            self.assertEqual(tuple(teachers),original)
            context=options['source_context'];context.begin_growth(teachers)
            context.record_growth_sizing(teachers,set(),set())
            context.record_filled_source(teachers,options['source_frame'],
                FilledGlyphEvidence(options['source_frame'],teachers))
            return {self.key},set(),dict(source_filled=dict(accepted=[dict(key=self.key,evidence=self.proof)]))
        with patch.object(scanner, '_SOURCE_FULL_SPIKE_PHASE_ENABLED', False), \
             patch.object(scanner, '_SOURCE_COMPOUND_CONFLICTS_ENABLED', False), \
             patch.object(scanner, '_SOURCE_INTERIOR_GLYPHS_ENABLED', True), \
             patch.object(scanner, '_SOURCE_REJECTED_PRIMARY_RECOVERY_ENABLED', True), \
             patch('scripts.source_geometry_pipeline.source_proposals',side_effect=proposals), \
             patch('scripts.source_rejected_primaries.recover_rejected_primaries',
                 side_effect=lambda current,*a,**k:(list(current),dict(accepted=[]))), \
             patch('scripts.source_rejected_primaries.source_proved_primary_metadata',
                 side_effect=AssertionError('A surviving key cannot select discarded metadata')):
            out = scanner._apply_source_geometry(self.result(original=original), self.image,
                source_frame=self.frame, rejected_primary_spikes=(self.candidate,))
        self.assertTrue(any(d is existing for d in out.detections))
        self.assertFalse(any(d is self.candidate for d in out.detections))

    def test_primary_off_interior_off_and_unqualified_mapping_keep_old_metadata(self):
        extended = SourceFrame(self.image,self.room,extent=Box(-8,0,816,608),canonical=self.image)
        for options in (dict(primary=False),dict(interior=False),dict(frame=extended)):
            with self.subTest(options=options):
                out, _ = self.apply(**options)
                self.assertFalse(any(d is self.candidate for d in out.detections))
                self.assertEqual(next(d for d in out.detections if (d.type_id,d.x,d.y)==self.key).kind,
                    'source_filled_glyph')
        out, producer = self.apply(grid=(19,13))
        self.assertEqual(out.detections,list(self.original));producer.assert_not_called()
