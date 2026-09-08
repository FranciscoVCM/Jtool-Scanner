import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from jtool_scanner.corpus import run_corpus
from jtool_scanner.geometry import Box
from jtool_scanner.jmap import JMap, JMapObject
from jtool_scanner.scanner import Detection, ScanResult


class CorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        Image.new('RGB', (800, 608), 'white').save(self.root / 'source.png')
        self.manifest = self.root / 'manifest.json'
        self.out = self.root / 'output'
        self.case = dict(id='room', source='source.png', family='test', partition='development')
        self.write_manifest([self.case])
        self.identity = dict(code_sha256='test-code', files={}, git_head='test-head',
                             python='test-python', pillow='test-pillow', platform='test-platform')
        self.identity_patch = patch('jtool_scanner.corpus.implementation_identity', return_value=self.identity)
        self.identity_patch.start()
        self.addCleanup(self.identity_patch.stop)
        self.result = ScanResult(800, 608, Box(0, 0, 800, 608), [
            Detection('block', 1, 32, 64, .9, Box(32, 64, 32, 32))])
        self.scan_patch = patch('jtool_scanner.corpus.scan_png', return_value=self.result)
        self.scan = self.scan_patch.start()
        self.addCleanup(self.scan_patch.stop)

    def write_manifest(self, cases):
        self.manifest.write_text(json.dumps(dict(cases=cases)), encoding='utf-8')

    def run_scan(self):
        return run_corpus(self.manifest, self.out, resume=True)

    def test_resume_reuses_verified_artifacts_and_retains_original_revision(self):
        first = self.run_scan()
        self.identity = dict(self.identity, git_head='documentation-only-commit')
        with patch('jtool_scanner.corpus.implementation_identity', return_value=self.identity):
            second = self.run_scan()
        self.assertEqual(self.scan.call_count, 1)
        self.assertTrue(second['complete'])
        self.assertTrue(second['cases'][0]['reused'])
        self.assertEqual(second['cases'][0]['directory'], first['cases'][0]['directory'])
        self.assertEqual(second['cases'][0]['implementation_at_scan']['git_head'], 'test-head')
        self.assertEqual(second['implementation']['git_head'], 'documentation-only-commit')
        self.assertEqual(len(list((self.out / 'runs').glob('*.json'))), 2)

    def test_visual_only_does_not_claim_exactness_or_acceptance(self):
        case = self.run_scan()['cases'][0]
        self.assertEqual(case['truth_level'], 'visual_only')
        self.assertIsNone(case['comparison'])
        self.assertEqual(case['review_status'], 'not_visually_reviewed')

    def test_reference_evaluates_after_scan_without_becoming_scanner_input(self):
        JMap(objects=[JMapObject(32, 64, 1)]).to_file(self.root / 'expected.jmap')
        self.write_manifest([dict(self.case, expected_jmap='expected.jmap')])
        case = self.run_scan()['cases'][0]
        self.assertEqual(case['truth_level'], 'exact_reference')
        self.assertEqual(case['comparison']['summary']['exact'], 1)
        self.assertNotIn('expected_jmap', self.scan.call_args.kwargs)

    def test_source_options_and_implementation_changes_invalidate_cache(self):
        self.run_scan()
        Image.new('RGB', (800, 608), 'black').save(self.root / 'source.png')
        self.assertFalse(self.run_scan()['cases'][0]['reused'])
        self.write_manifest([dict(self.case, options=dict(grid_step=16))])
        self.assertFalse(self.run_scan()['cases'][0]['reused'])
        with patch('jtool_scanner.corpus.implementation_identity',
                   return_value=dict(self.identity, code_sha256='changed')):
            self.assertFalse(self.run_scan()['cases'][0]['reused'])
        self.assertEqual(self.scan.call_count, 4)

    def test_missing_or_changed_artifact_rescans_without_erasing_old_attempt(self):
        first = self.run_scan()['cases'][0]
        damaged = Path(first['directory']) / 'blend.svg'
        damaged.write_text('broken')
        second = self.run_scan()['cases'][0]
        self.assertFalse(second['reused'])
        self.assertNotEqual(first['directory'], second['directory'])
        self.assertEqual(damaged.read_text(), 'broken')

    def test_interruption_preserves_completed_case_for_resume(self):
        Image.new('RGB', (800, 608), 'black').save(self.root / 'second.png')
        self.write_manifest([self.case, dict(self.case, id='second', source='second.png')])
        self.scan.side_effect = [self.result, RuntimeError('interrupted')]
        with self.assertRaisesRegex(RuntimeError, 'interrupted'):
            self.run_scan()
        self.scan.side_effect = None
        resumed = self.run_scan()
        self.assertTrue(resumed['cases'][0]['reused'])
        self.assertFalse(resumed['cases'][1]['reused'])
        self.assertEqual(self.scan.call_count, 3)

    def test_labels_refresh_without_rescanning(self):
        self.run_scan()
        self.write_manifest([dict(self.case, family='other', partition='evaluation')])
        case = self.run_scan()['cases'][0]
        self.assertTrue(case['reused'])
        self.assertEqual((case['family'], case['partition']), ('other', 'evaluation'))

    def test_reference_change_invalidates_evaluation(self):
        reference = self.root / 'expected.jmap'
        JMap(objects=[JMapObject(32, 64, 1)]).to_file(reference)
        self.write_manifest([dict(self.case, expected_jmap='expected.jmap')])
        self.assertEqual(self.run_scan()['cases'][0]['comparison']['summary']['exact'], 1)
        JMap(objects=[JMapObject(320, 64, 1)]).to_file(reference)
        current = self.run_scan()['cases'][0]
        self.assertFalse(current['reused'])
        self.assertEqual(current['comparison']['summary']['exact'], 0)

    def test_result_corruption_is_not_reused(self):
        first = self.run_scan()['cases'][0]
        (Path(first['directory']) / 'result.json').write_text('{}')
        self.assertFalse(self.run_scan()['cases'][0]['reused'])

    def test_relocated_output_regenerates_absolute_project_source_links(self):
        self.run_scan()
        destination = self.root / 'relocated'
        self.out.rename(destination)
        self.out = destination
        current = self.run_scan()['cases'][0]
        self.assertFalse(current['reused'])
        self.assertTrue(Path(current['directory']).is_dir())
        project = json.loads((Path(current['directory']) / 'project.jscan.json').read_text())
        self.assertTrue(Path(project['source']['image']).is_file())

    def test_implementation_change_during_scan_does_not_seal_cache(self):
        with patch('jtool_scanner.corpus.implementation_identity', side_effect=[
            self.identity, dict(self.identity, code_sha256='changed')
        ]):
            with self.assertRaisesRegex(RuntimeError, 'Implementation changed'):
                self.run_scan()
        self.assertFalse(list(self.out.rglob('latest.json')))
        self.assertFalse((self.out / 'report.json').exists())

    def test_project_preserves_scan_options(self):
        self.write_manifest([dict(self.case, options=dict(include_geometry=False,
                                                         include_color_objects=False))])
        current = self.run_scan()['cases'][0]
        project = json.loads((Path(current['directory']) / 'project.jscan.json').read_text())
        self.assertFalse(project['scanner']['include_geometry'])
        self.assertFalse(project['scanner']['include_color_objects'])

    def test_rejects_unsafe_ids_and_unknown_options_before_scanning(self):
        for changes in (dict(id='../bad'), dict(options=dict(enable_ocr=True)),
                        dict(options=dict(misspelled=True)), dict(partition='accepted')):
            with self.subTest(changes=changes):
                self.write_manifest([dict(self.case, **changes)])
                with self.assertRaises(ValueError):
                    self.run_scan()
        self.scan.assert_not_called()


if __name__ == '__main__':
    unittest.main()
