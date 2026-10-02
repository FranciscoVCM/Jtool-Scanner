import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.triangle_appearance_probe import STYLES, create_scene, measure_spec, run_probe


class TriangleAppearanceProbeTests(unittest.TestCase):
    def test_geometry_labels_do_not_change_with_appearance_or_capture_scale(self):
        for style in STYLES:
            for scale in (1, 1.25):
                with self.subTest(style=style, scale=scale):
                    image, truth, hypotheses, solids = create_scene(style, scale)
                    expected = [(3, 320, 320), (3, 368, 320)]
                    if style != 'empty-gap':
                        expected.append((7, 352, 336))
                    self.assertEqual(truth, expected)
                    self.assertEqual(hypotheses, [(3, 320, 320), (3, 368, 320), (3, 336, 320)])
                    self.assertEqual(solids, [(304, 352, 112, 32)])
                    self.assertEqual((image.width, image.height),
                                     (round(800 * scale), round(608 * scale)))

    def test_render_is_deterministic_but_appearance_really_changes(self):
        images = []
        for style in STYLES:
            first = create_scene(style)[0].data
            self.assertEqual(first, create_scene(style)[0].data)
            images.append(first)
        self.assertEqual(len(set(images)), len(STYLES))

    def test_labels_score_results_without_becoming_helper_inputs(self):
        with patch('scripts.triangle_appearance_probe.contour_size_changes',
                   return_value=({(7, 352, 336)}, {(3, 336, 320)})) as detector:
            _, result = measure_spec('uniform-filled', 1)
        self.assertEqual(result['exact'], 3)
        self.assertEqual(result['misses'], [])
        self.assertEqual(result['extras'], [])
        self.assertEqual(detector.call_args.args[2],
                         [(3, 320, 320), (3, 368, 320), (3, 336, 320)])
        self.assertNotIn((7, 352, 336), detector.call_args.args[2])

    def test_new_destination_preserves_previous_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'probe'
            with patch('scripts.triangle_appearance_probe.contour_size_changes',
                       return_value=(set(), set())):
                report = run_probe(out, [('empty-gap', 1)])
            original = (out / 'results.json').read_bytes()
            self.assertTrue(report['definition']['helper_only'])
            self.assertFalse(report['definition']['ordinary'])
            self.assertEqual(json.loads(original)['rows'][0]['expected'], 2)
            with self.assertRaises(FileExistsError):
                run_probe(out)
            self.assertEqual((out / 'results.json').read_bytes(), original)

    def test_invalid_style_or_scale_is_rejected(self):
        for style, scale in (('unknown', 1), ('uniform-filled', 0)):
            with self.subTest(style=style, scale=scale), self.assertRaises(ValueError):
                create_scene(style, scale)
