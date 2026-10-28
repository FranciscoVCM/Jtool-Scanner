from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from jtool_scanner import corpus, scanner
from jtool_scanner.geometry import Box
from jtool_scanner.jmap import JMap, JMapObject
from scripts.corpus_case_comparison import compare_cases, main
from scripts.scanner_feature_profiles import snapshot_feature_profile


class CorpusCaseComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        Image.new('RGB', (800, 608), 'white').save(self.root/'source.png')
        self.manifest = self.root/'manifest.json'
        self.manifest.write_text(json.dumps(dict(cases=[dict(id='room', source='source.png',
            family='portable', partition='development')])), encoding='utf-8')
        self.identity = dict(code_sha256='test-code', files={}, git_head='test-head',
                             python='test-python', pillow='test-pillow', platform='test-platform')
        self.scan = scanner.ScanResult(800, 608, Box(0, 0, 800, 608), [
            scanner.Detection('original', 1, 32, 64, .9, Box(32, 64, 32, 32))])
        self.profile = snapshot_feature_profile(scanner)
        self.before, self.after = self.make_case('before'), self.make_case('after')

    def make_case(self, name, scan=None):
        with patch.object(corpus, 'implementation_identity', return_value=self.identity), \
             patch.object(corpus, 'scan_png', return_value=scan or self.scan), \
             redirect_stdout(io.StringIO()):
            report = corpus.run_corpus(self.manifest, self.root/name)
        return Path(report['cases'][0]['directory'])

    def result(self, folder):
        return json.loads((folder/'result.json').read_bytes())

    def write_result(self, folder, value):
        (folder/'result.json').write_text(json.dumps(value), encoding='utf-8')

    def rehash(self, folder, name):
        value = self.result(folder)
        value['artifact_hashes'][name] = hashlib.sha256((folder/name).read_bytes()).hexdigest()
        self.write_result(folder, value)

    def full(self, **kwargs):
        return compare_cases(self.before, self.after,
            before_raw=asdict(self.scan), after_raw=asdict(self.scan),
            before_profile=self.profile, after_profile=self.profile, **kwargs)

    def test_full_equality_permits_carry_but_never_accuracy_approval(self):
        result = self.full()
        self.assertTrue(result['review_carry_eligible'])
        self.assertFalse(result['source_accuracy_certified'])
        self.assertEqual(result['added'], [])
        self.assertEqual(result['removed'], [])
        self.assertEqual(len(result['evidence_sha256']), 12)

    def test_legacy_missing_raw_and_profile_are_unknown_not_equal(self):
        result = compare_cases(self.before, self.after)
        self.assertIsNone(result['equality']['entire_raw_scan'])
        self.assertIsNone(result['equality']['recorded_feature_profile'])
        self.assertFalse(result['review_carry_eligible'])

    def test_documentation_or_code_identity_alone_does_not_block_equal_outputs(self):
        case = self.result(self.after)
        case['inputs']['code_sha256'] = 'other-implementation'
        self.write_result(self.after, case)
        result = self.full()
        self.assertFalse(result['equality']['code_sha256'])
        self.assertTrue(result['review_carry_eligible'])

    def test_changed_options_or_environment_block_carry(self):
        for key in ('python', 'pillow', 'platform', 'options'):
            with self.subTest(key=key):
                original = self.result(self.after); case = deepcopy(original)
                case['inputs'][key] = {} if key == 'options' else 'other'
                self.write_result(self.after, case)
                self.assertFalse(self.full()['review_carry_eligible'])
                self.write_result(self.after, original)

    def test_duplicate_object_changes_are_not_hidden_by_set_comparison(self):
        mapped = JMap.from_file(self.after/'detected.jmap')
        mapped.objects.append(JMapObject(32, 64, 1))
        mapped.to_file(self.after/'detected.jmap'); self.rehash(self.after, 'detected.jmap')
        result = compare_cases(self.before, self.after)
        self.assertEqual(result['added'], [dict(key=[1, 32, 64], count=1)])
        self.assertFalse(result['equality']['jmap_typed_multiset'])

    def test_same_count_shift_has_both_added_and_removed_origins(self):
        mapped = JMap.from_file(self.after/'detected.jmap')
        mapped.objects[0].x += 8
        mapped.to_file(self.after/'detected.jmap'); self.rehash(self.after, 'detected.jmap')
        result = compare_cases(self.before, self.after)
        self.assertEqual(result['added'], [dict(key=[1, 40, 64], count=1)])
        self.assertEqual(result['removed'], [dict(key=[1, 32, 64], count=1)])

    def test_score_provenance_and_imagebox_changes_are_not_hidden(self):
        case = self.result(self.after)
        case['detections'][0]['score'] = .7
        case['detections'][0]['kind'] = 'other'
        case['detections'][0]['image_box']['x'] += 1
        self.write_result(self.after, case)
        result = compare_cases(self.before, self.after)
        self.assertEqual(result['existing_detection_metadata_changed_keys'], [[1, 32, 64]])
        self.assertFalse(result['equality']['recorded_scan_fields']['detections'])

    def test_detection_order_is_not_set_equality(self):
        scan = deepcopy(self.scan)
        scan.detections.append(scanner.Detection('other', 1, 64, 64, .8, Box(64, 64, 32, 32)))
        before, after = self.make_case('ordered-a', scan), self.make_case('ordered-b', scan)
        case = self.result(after); case['detections'].reverse(); self.write_result(after, case)
        result = compare_cases(before, after)
        self.assertTrue(result['equality']['jmap_typed_multiset'])
        self.assertFalse(result['equality']['recorded_scan_fields']['detections'])

    def test_jmap_metadata_change_is_separate_from_object_changes(self):
        mapped = JMap.from_file(self.after/'detected.jmap'); mapped.player_gravity = -1
        mapped.to_file(self.after/'detected.jmap'); self.rehash(self.after, 'detected.jmap')
        result = compare_cases(self.before, self.after)
        self.assertEqual(result['added'], [])
        self.assertFalse(result['equality']['jmap_metadata'])

    def test_project_path_normalization_does_not_erase_history_text(self):
        project = json.loads((self.after/'project.jscan.json').read_bytes())
        project['history'].append(dict(note=project['source']['image']))
        (self.after/'project.jscan.json').write_text(json.dumps(project), encoding='utf-8')
        self.rehash(self.after, 'project.jscan.json')
        self.assertFalse(compare_cases(self.before, self.after)['equality']['project_except_authenticated_source_path'])

    def test_forged_project_source_is_not_an_authenticated_relocation(self):
        project = json.loads((self.after/'project.jscan.json').read_bytes())
        project['source']['image'] = str(self.before/'source.png')
        (self.after/'project.jscan.json').write_text(json.dumps(project), encoding='utf-8')
        self.rehash(self.after, 'project.jscan.json')
        with self.assertRaisesRegex(ValueError, 'authenticated source'):
            compare_cases(self.before, self.after)

    def test_missing_or_tampered_artifact_is_rejected(self):
        (self.after/'blend.svg').write_text('changed', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            compare_cases(self.before, self.after)

    def test_missing_checksum_is_rejected(self):
        case = self.result(self.after); del case['artifact_hashes']['blend.svg']; self.write_result(self.after, case)
        with self.assertRaisesRegex(ValueError, 'checksums required'):
            compare_cases(self.before, self.after)

    def test_unsafe_artifact_names_are_rejected_on_both_path_dialects(self):
        original = self.result(self.after)
        for name in ('../outside', '..\\outside', '/absolute', 'C:\\outside', 'source.png:stream'):
            with self.subTest(name=name):
                case = deepcopy(original); case['artifact_hashes'][name] = 'unused'
                self.write_result(self.after, case)
                with self.assertRaisesRegex(ValueError, 'filename'):
                    compare_cases(self.before, self.after)
        self.write_result(self.after, original)

    def test_source_and_reference_input_hashes_are_verified(self):
        original = self.result(self.after)
        for key in ('source_sha256', 'expected_sha256'):
            with self.subTest(key=key):
                case = deepcopy(original); case['inputs'][key] = 'wrong'; self.write_result(self.after, case)
                with self.assertRaises(ValueError): compare_cases(self.before, self.after)
        self.write_result(self.after, original)

    def test_raw_records_must_be_complete_and_bound_to_the_case(self):
        for change in ('missing', 'detections', 'image_width', 'recognized_text', 'dot_kid'):
            with self.subTest(change=change):
                raw = asdict(self.scan)
                if change == 'missing': del raw['dense_miniblock_room']
                elif change == 'detections': raw['detections'] = []
                elif change == 'recognized_text': raw[change] = 'different'
                else: raw[change] += 1
                with self.assertRaises(ValueError):
                    compare_cases(self.before, self.after, before_raw=asdict(self.scan), after_raw=raw)

    def test_hidden_raw_flag_difference_blocks_carry(self):
        raw = asdict(self.scan); raw['dense_miniblock_room'] = True
        result = compare_cases(self.before, self.after, before_raw=asdict(self.scan), after_raw=raw,
            before_profile=self.profile, after_profile=self.profile)
        self.assertFalse(result['equality']['entire_raw_scan'])
        self.assertFalse(result['review_carry_eligible'])

    def test_source_extent_and_mode_mismatch_are_rejected(self):
        for key, value in (('source_geometry', True), ('source_extent', dict(x=0, y=0, width=799, height=608))):
            with self.subTest(key=key):
                raw = asdict(self.scan); raw[key] = value
                with self.assertRaisesRegex(ValueError, 'source frame/mode'):
                    compare_cases(self.before, self.after, before_raw=asdict(self.scan), after_raw=raw)

    def test_unknown_project_schema_is_not_given_missing_field_defaults(self):
        project = json.loads((self.after/'project.jscan.json').read_bytes()); project['version'] = 999
        (self.after/'project.jscan.json').write_text(json.dumps(project), encoding='utf-8')
        self.rehash(self.after, 'project.jscan.json')
        with self.assertRaisesRegex(ValueError, 'project schema'):
            compare_cases(self.before, self.after)

    def test_recorded_count_inconsistency_is_rejected(self):
        case = self.result(self.after); case['object_counts']['1'] += 1; self.write_result(self.after, case)
        with self.assertRaisesRegex(ValueError, 'counts'):
            compare_cases(self.before, self.after)

    def test_changed_or_incomplete_selector_profiles_are_not_assumed_equal(self):
        other = deepcopy(self.profile)
        name = next(iter(other['switches'])); other['switches'][name] = not other['switches'][name]
        result = compare_cases(self.before, self.after, before_raw=asdict(self.scan), after_raw=asdict(self.scan),
            before_profile=self.profile, after_profile=other)
        self.assertFalse(result['equality']['recorded_feature_profile'])
        del other['switches'][name]
        with self.assertRaises(ValueError):
            compare_cases(self.before, self.after, before_profile=self.profile, after_profile=other)

    def test_one_sided_raw_or_profile_evidence_is_an_error(self):
        for kwargs in (dict(before_raw=asdict(self.scan)), dict(after_profile=self.profile)):
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, 'both sides'):
                    compare_cases(self.before, self.after, **kwargs)

    def test_read_only_comparison_never_scans_or_changes_snapshot_bytes(self):
        paths = [p for folder in (self.before, self.after) for p in folder.iterdir() if p.is_file()]
        before = {p: p.read_bytes() for p in paths}
        with patch.object(scanner, 'scan_png', side_effect=AssertionError('No scan allowed')), \
             patch.object(corpus, 'scan_png', side_effect=AssertionError('No scan allowed')):
            self.full()
        self.assertEqual(before, {p: p.read_bytes() for p in paths})

    def test_additions_can_retain_the_entire_old_ordered_detection_sequence(self):
        scan = deepcopy(self.scan)
        scan.detections.append(scanner.Detection('extra', 1, 64, 64, .8, Box(64, 64, 32, 32)))
        after = self.make_case('extra', scan)
        result = compare_cases(self.before, after)
        self.assertTrue(result['all_original_ordered_detections_retained'])
        self.assertEqual(result['added'], [dict(key=[1, 64, 64], count=1)])

    def test_an_old_duplicate_cannot_be_retained_by_one_remaining_detection(self):
        scan = deepcopy(self.scan); scan.detections.append(deepcopy(scan.detections[0]))
        before = self.make_case('duplicate-original', scan)
        self.assertFalse(compare_cases(before, self.after)['all_original_ordered_detections_retained'])

    def test_explicit_source_mode_and_extent_are_validated_without_erasing_them(self):
        scan = deepcopy(self.scan); scan.source_geometry = True
        scan.source_grid = (25, 19)
        scan.source_extent = Box(-1, -2, 802, 612)
        manifest = json.loads(self.manifest.read_bytes()); manifest['defaults'] = dict(source_geometry=True)
        self.manifest.write_text(json.dumps(manifest), encoding='utf-8')
        before, after = self.make_case('extended-before', scan), self.make_case('extended-after', scan)
        result = compare_cases(before, after, before_raw=asdict(scan), after_raw=asdict(scan),
            before_profile=self.profile, after_profile=self.profile)
        self.assertTrue(result['review_carry_eligible'])

    def test_raw_bool_and_integer_types_are_not_silently_interchangeable(self):
        for key, value in (('dense_miniblock_room', 0), ('source_geometry', 0), ('image_width', True)):
            with self.subTest(key=key):
                raw = asdict(self.scan); raw[key] = value
                with self.assertRaisesRegex(ValueError, 'actual declared value types'):
                    compare_cases(self.before, self.after, before_raw=asdict(self.scan), after_raw=raw)

    def test_completed_result_cannot_silently_point_to_a_different_directory(self):
        case = self.result(self.after); case['directory'] = str(self.before); self.write_result(self.after, case)
        with self.assertRaisesRegex(ValueError, 'directory'):
            compare_cases(self.before, self.after)

    def test_cli_prints_comparison_without_writing_or_claiming_accuracy(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([str(self.before), str(self.after)]), 0)
        result = json.loads(output.getvalue())
        self.assertTrue(result['read_only'])
        self.assertFalse(result['review_carry_eligible'])
        self.assertFalse(result['source_accuracy_certified'])


if __name__ == '__main__':
    unittest.main()
