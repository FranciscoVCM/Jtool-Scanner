"""Exact old-retention scheduling and BG decisions; no game/reference fixtures."""
from copy import deepcopy
from math import dist, inf, nextafter
from random import Random
from types import MethodType, SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner.spike_shape import VERTICES
from scripts.source_filled_pipeline import FilledGlyphEvidence
from scripts.source_full_spike_phase import (
    SourceFullSpikePhaseEvidence, _legacy_background_support,
    _original_background_support, refit_source_full_spike_phases,
)
from scripts.source_interior_glyphs import SourceInteriorGlyphEvidence
from tests.test_source_full_spike_phase import fixture
from tests.test_source_full_spike_phase_consumer import values


def reference_geometry(body, key):
    """Literal previous scalar equations, independent of the new phase helper."""
    kind, x, y = key
    px, py = body.frame.pitch
    phases = []
    for dx in (0, -px, px):
        for dy in (0, -py, py):
            if not body.frame.rectangle_available(x+dx, y+dy, 32, 32, margin=4):
                phases.append(dict(phase=(dx, dy), known=False, passed=False))
                continue
            poly = [(x+a+dx, y+b+dy) for a, b in VERTICES[kind]]
            triangle = [body.directed_field.directed(a, b)
                        for a, b in zip(poly, poly[1:]+poly[:1])]
            if min(triangle) < 9:
                phases.append(dict(phase=(dx, dy), known=True, passed=False, triangle=triangle))
                continue
            box = [(x+dx, y+dy), (x+32+dx, y+dy),
                   (x+32+dx, y+32+dy), (x+dx, y+32+dy)]
            rectangle = [body.directed_field.directed(a, b)
                         for a, b in zip(box, box[1:]+box[:1])]
            raw = body.field.rectangle(x+dx, y+dy, 32)
            competing = min(rectangle) >= 9 or all(e.support >= 9 and not e.unknown for e in raw)
            phases.append(dict(phase=(dx, dy), known=True, passed=not competing,
                triangle=triangle, rectangle=rectangle,
                raw_rectangle=[dict(support=e.support, unknown=e.unknown) for e in raw]))
    return dict(passed=any(p['passed'] for p in phases), phases=phases,
        common_phase_NOT_native_origin_change=True, RGB_normal_alignment=.95,
        existing_required_support=9)


def evidence(scene):
    return SourceFullSpikePhaseEvidence(FilledGlyphEvidence(scene[2], scene[3]), scene[3], source_grid=(25, 19))


class FastPhaseRetentionTests(TestCase):
    def test_full_and_nominal_phases_match_literal_previous_equations(self):
        transforms = (lambda c: c, lambda c: tuple(255-v for v in c),
                      lambda c: (c[2], c[0], c[1]), lambda c: tuple(round(.4*v) for v in c))
        for direction, transform in enumerate(transforms):
            scene = fixture(rotation=direction, scale=1.25, transform=transform)
            field = evidence(scene)
            for key in (scene[4], scene[5], (scene[4][0], 0, 0)):
                expected = reference_geometry(field.body, key)
                nominal = field.body._nominal_geometry(key)
                self.assertEqual(nominal, expected['phases'][0])
                self.assertNotIn(key, field.body.new_geometry)
                self.assertEqual(field.body.geometry(key), expected)
                self.assertEqual(len(field.body.geometry(key)['phases']), 9)

    def test_nominal_diagnostics_do_not_poison_full_result_cache(self):
        scene = fixture()
        field = evidence(scene)
        nominal = field.body._nominal_geometry(scene[4])
        nominal['passed'] = not nominal['passed']
        self.assertNotIn(scene[4], field.body.new_geometry)
        expected = reference_geometry(field.body, scene[4])
        self.assertEqual(field.body.geometry(scene[4]), expected)
        full = field.body.geometry(scene[4])
        full['phases'].clear()
        self.assertEqual(field.body.geometry(scene[4]), expected)

    def test_fast_proven_old_retention_never_requests_other_eight_phases(self):
        scene = list(fixture())
        target, old = scene[4:6]
        scene[3] = tuple(d for d in scene[3] if (d.type_id, d.x, d.y) != old) + (
            SimpleNamespace(type_id=target[0], x=target[1], y=target[2]),)
        field = evidence(scene)
        with patch.object(field.body, 'geometry', side_effect=AssertionError('Unused full geometry')):
            result = field.probe(target, scene[3], short_circuit=True)
        self.assertIsNone(result['proposed'])
        self.assertTrue(result['old_geometry']['diagnostics_deferred'])
        self.assertTrue(result['old_geometry']['phases'][0]['passed'])
        self.assertNotIn(target, field.body.new_geometry)

    def test_full_default_does_not_call_nominal_shortcut(self):
        scene = fixture()
        field = evidence(scene)
        with patch.object(field.body, '_nominal_geometry', side_effect=AssertionError('Explicit mode only')):
            result = field.probe(scene[5], scene[3])
        self.assertEqual(result['proposed'], scene[4])

    def test_failed_nominal_keeps_entire_original_repair_proof(self):
        for scale, amount in ((1, 16), (1.25, 8), (1.5, 16)):
            scene = fixture(scale=scale, amount=amount, isolated=amount == 16)
            expected = evidence(scene).probe(scene[5], scene[3])
            field = evidence(scene)
            actual = field.probe(scene[5], scene[3], short_circuit=True)
            self.assertEqual(actual, expected)
            self.assertEqual(actual['proposed'], scene[4])
            self.assertEqual(len(field.body.geometry(scene[5])['phases']), 9)

    def test_consumer_preserves_complete_repairs_registration_metadata_and_order(self):
        scene = values()
        original, filled = scene[3], scene[4]
        snapshot = deepcopy(original)
        kwargs = dict(source_frame=scene[2], source_filled_evidence=filled, source_grid=(25, 19))
        before, expected = refit_source_full_spike_phases(original, original, **kwargs)
        after, actual = refit_source_full_spike_phases(original, original, short_circuit=True, **kwargs)
        self.assertEqual(after, before)
        self.assertEqual(original, snapshot)
        self.assertEqual({k:v for k,v in actual.items() if k != 'source_proofs'},
                         {k:v for k,v in expected.items() if k != 'source_proofs'})
        for got, wanted in zip(actual['source_proofs'], expected['source_proofs'], strict=True):
            if got == wanted:
                continue
            self.assertIsNone(got['proposed'])
            self.assertEqual(got['abstained'], wanted['abstained'])
            self.assertTrue(got['old_geometry']['diagnostics_deferred'])
            self.assertEqual(got['old_geometry']['phases'], wanted['old_geometry']['phases'][:1])
            self.assertTrue(got['old_geometry']['phases'][0]['passed'])

    def test_short_circuit_requires_actual_booleans(self):
        scene = fixture()
        field = evidence(scene)
        consumer = values()
        for invalid in (0, 1, None, 'true', []):
            with self.assertRaises(ValueError):
                field.probe(scene[5], scene[3], short_circuit=invalid)
            with self.assertRaises(ValueError):
                refit_source_full_spike_phases(consumer[3], consumer[3],
                    source_frame=consumer[2], source_filled_evidence=consumer[4],
                    source_grid=(25, 19), short_circuit=invalid)


class ExactOriginalBackgroundTests(TestCase):
    @staticmethod
    def body():
        body = SimpleNamespace(_paint_indices={})
        body._paint_support = MethodType(SourceInteriorGlyphEvidence._paint_support, body)
        return body

    @staticmethod
    def model(paints, background, limit):
        return dict(original_paints=paints, background=background, limit=limit, paint_distance_cache={})

    def compare(self, paints, rgb, background, limit):
        model = self.model(paints, background, limit)
        self.assertEqual(_original_background_support(self.body(), model, rgb),
                         _legacy_background_support(self.body(), model, rgb))

    def test_random_raw_queries_keep_exact_closed_and_strict_decisions(self):
        rng = Random(433)
        for _ in range(12):
            paints = tuple(tuple(rng.randrange(256) for _ in range(3)) for _ in range(23))
            background = tuple(sum(p[c] for p in paints)/len(paints) for c in range(3))
            for _ in range(32):
                rgb = tuple(rng.randrange(256) for _ in range(3))
                distance = dist(rgb, background)
                for limit in (0, -1, 16, distance, nextafter(distance, 0), nextafter(distance, inf)):
                    self.compare(paints, rgb, background, limit)

    def test_half_nearest_boundary_zero_and_nonraw_fallbacks(self):
        paints = ((10, 10, 10), (30, 10, 10))
        for offset in (5., nextafter(5., 0), nextafter(5., inf)):
            self.compare(paints, (20, 10, 10), (20+offset, 10, 10), 32)
        for limit in (0, -1, inf, -inf, float('nan'), 10**1000):
            self.compare(paints, (10, 10, 10), (10, 10, 10), limit)
            self.compare(((10.5, 10., 10.),), (10.5, 10.5, 10.5), (0, 0, 0), limit)
        for function in (_original_background_support, _legacy_background_support):
            with self.assertRaises(ValueError):
                function(self.body(), self.model((), (0, 0, 0), 32), (1, 2, 3))
            with self.assertRaises(TypeError):
                function(self.body(), self.model(paints, (0, 0, 0), 32), None)

    def test_custom_paint_oracle_keeps_legacy_model_protocol(self):
        body = SimpleNamespace(_paint_support=lambda model, values: dict(max_original_paint_distance=100.))
        for model in (dict(background=(0, 0, 0), limit=10),
                      self.model(((1, 1, 1),), (0, 0, 0), 10)):
            self.assertTrue(_legacy_background_support(body, model, (1, 1, 1)))
            self.assertEqual(_original_background_support(body, model, (1, 1, 1)),
                             _legacy_background_support(body, model, (1, 1, 1)))
