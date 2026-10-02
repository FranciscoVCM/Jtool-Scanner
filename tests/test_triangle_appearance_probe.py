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

    def test_explicit_original_widths_preserve_default_pixels(self):
        for style in STYLES:
            for scale in (1, 1.25):
                width = 2 if style == 'shaded-thick' else 1
                with self.subTest(style=style, scale=scale):
                    original = create_scene(style, scale)
                    explicit = create_scene(style, scale, full_outline_width=width,
                                            mini_outline_width=width)
                    self.assertEqual(original[0].data, explicit[0].data)
                    self.assertEqual(original[1:], explicit[1:])

    def test_native_size_width_change_alters_pixels_not_labels_or_inputs(self):
        for scale in (1, 1.25):
            first = create_scene('shaded-thick', scale)
            second = create_scene('shaded-thick', scale, full_outline_width=2,
                                  mini_outline_width=1)
            self.assertNotEqual(first[0].data, second[0].data)
            self.assertEqual(first[1:], second[1:])

    def test_palette_variants_preserve_known_geometry(self):
        for scale in (1, 1.25):
            original = create_scene('shaded-thick', scale)
            for transform in ('invert', 'dim', 'bright', 'channel-permutation'):
                with self.subTest(scale=scale, transform=transform):
                    changed = create_scene('shaded-thick', scale, palette_transform=transform)
                    self.assertNotEqual(original[0].data, changed[0].data)
                    self.assertEqual(original[1:], changed[1:])
                    self.assertEqual(changed[0].data, create_scene(
                        'shaded-thick', scale, palette_transform=transform)[0].data)

    def test_variant_configuration_is_preserved_without_supplying_answers(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('scripts.triangle_appearance_probe.contour_size_changes',
                       return_value=(set(), set())) as detector:
                report = run_probe(Path(folder) / 'variant', [('shaded-thick', 1)],
                                   full_outline_width=2, mini_outline_width=1,
                                   palette_transform='invert')
            options = dict(full_outline_width=2, mini_outline_width=1,
                           palette_transform='invert')
            self.assertEqual(report['definition']['render_options'], options)
            self.assertEqual(report['rows'][0]['render_options'], options)
            self.assertNotIn((7, 352, 336), detector.call_args.args[2])

    def test_invalid_variant_is_rejected_before_creating_an_evidence_folder(self):
        for options in (dict(full_outline_width=0), dict(mini_outline_width=5),
                        dict(mini_outline_width=True), dict(full_outline_width=1.5),
                        dict(palette_transform='unknown')):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as folder:
                output = Path(folder) / 'invalid'
                with self.assertRaises(ValueError):
                    run_probe(output, **options)
                self.assertFalse(output.exists())
