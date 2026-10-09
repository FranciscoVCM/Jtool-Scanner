"""Original exterior witnesses, affine illumination and safe abstention."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase

from scripts.source_local_background import SourceLocalBackground


def library(positions=((160, 160), (256, 192), (352, 224)), affine=True):
    def sample(x, y, size):
        color = (40+x/20+y/40, 50+x/30-y/80, 60+y/25) if affine else (40, 50, 60)
        return [color] * (size*size)
    return SimpleNamespace(anchors=[dict(key=(3, x, y), size=32) for x, y in positions],
                           raw=SimpleNamespace(sample=sample))


class SourceLocalBackgroundTests(TestCase):
    def test_local_affine_prediction_matches_original_rgb_illumination(self):
        bg = SourceLocalBackground(library(), lambda value: True)
        result = bg.predict(240, 320, 1e-6)
        self.assertTrue(result['valid'])
        for actual, expected in zip(result['prediction'], (40+240/20+320/40, 50+240/30-320/80, 60+320/25)):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(result['independent_source_regions'], 3)
        self.assertTrue(result['original_source_only'])

    def test_inside_triangle_corners_do_not_become_background_witnesses(self):
        bg = SourceLocalBackground(library(), lambda value: True)
        self.assertEqual(len(bg.examples), 6)
        self.assertTrue(all(r['point'][1] == r['source_anchor'][2]+4 for r in bg.examples))

    def test_fewer_than_three_independent_regions_abstain(self):
        bg = SourceLocalBackground(library(((160, 160), (176, 160), (160, 176))), lambda value: True)
        result = bg.predict(240, 320, 10)
        self.assertFalse(result['valid'])
        self.assertEqual(result['reason'], 'insufficient independent original BG')

    def test_foreground_and_unknown_patches_are_not_empty_evidence(self):
        lib = library()
        bg = SourceLocalBackground(lib, lambda value: False)
        self.assertEqual(bg.examples, [])
        self.assertFalse(bg.predict(240, 320, 10)['valid'])
        lib.raw.sample = lambda *args, **kwargs: None
        self.assertFalse(SourceLocalBackground(lib, lambda value: True).predict(240, 320, 10)['valid'])

    def test_degenerate_source_positions_abstain(self):
        bg = SourceLocalBackground(library(), lambda value: True)
        for example in bg.examples:
            example['point'] = (100., 200.)
        result = bg.predict(240, 320, 10)
        self.assertFalse(result['valid'])
        self.assertEqual(result['reason'], 'degenerate source BG positions')

    def test_cached_nested_proof_does_not_mutate_source_or_later_result(self):
        bg = SourceLocalBackground(library(), lambda value: True)
        original = deepcopy(bg.examples)
        expected = bg.predict(240, 320, 10)
        modified = bg.predict(240, 320, 10)
        modified['source_witnesses'][0]['mean'] = (255, 0, 0)
        modified['source_witnesses'].clear()
        self.assertEqual(bg.predict(240, 320, 10), expected)
        self.assertEqual(bg.examples, original)
