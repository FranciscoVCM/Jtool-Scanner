"""A control-profile mismatch must fail before an expensive scan begins."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from scripts.scanner_feature_profiles import (
    SOURCE_FEATURE_SWITCHES, recorded_feature_profile, snapshot_feature_profile,
    validate_feature_comparison,
)


NEW = '_SOURCE_REJECTED_PRIMARY_RECOVERY_ENABLED'
OLD = ('_SOURCE_FRAME_ARBITRATION_ENABLED', '_SOURCE_INTERIOR_GLYPHS_ENABLED',
       '_SOURCE_COMPOUND_CONFLICTS_ENABLED')


class ScannerFeatureProfileTests(TestCase):
    def setUp(self):
        self.before = snapshot_feature_profile(scanner)

    def test_snapshot_records_all_seven_actual_values_without_mutating_runtime(self):
        self.assertEqual(set(self.before['switches']), SOURCE_FEATURE_SWITCHES)
        self.assertEqual(len(self.before['switches']), 7)
        with patch.object(scanner, NEW, True):
            after = snapshot_feature_profile(scanner)
            self.assertIs(after['switches'][NEW], True)
        self.assertEqual(snapshot_feature_profile(scanner), self.before)
        self.assertIs(self.before['switches'][NEW], False)

    def test_same_profile_single_new_selector_passes(self):
        after = deepcopy(self.before);after['switches'][NEW] = True
        report = validate_feature_comparison(self.before, after, expected_changes={NEW: (False, True)})
        self.assertEqual(report['declared_changes'], {NEW: [False, True]})
        self.assertTrue(report['untested_switches_identical'])

    def test_exact_Flames_mixed_profile_failure_is_detected_before_scan(self):
        baseline = deepcopy(self.before)
        for name in OLD:baseline['switches'][name] = True
        candidate = deepcopy(self.before);candidate['switches'][NEW] = True
        with self.assertRaisesRegex(ValueError, 'Confounded'):
            validate_feature_comparison(baseline, candidate, expected_changes={NEW: (False, True)})

    def test_corrected_original_profile_plus_new_selector_passes(self):
        baseline = deepcopy(self.before)
        for name in OLD:baseline['switches'][name] = True
        candidate = deepcopy(baseline);candidate['switches'][NEW] = True
        report = validate_feature_comparison(baseline, candidate, expected_changes={NEW: (False, True)})
        self.assertEqual(report['declared_changes'], {NEW: [False, True]})

    def test_unknown_missing_extra_and_nonboolean_metadata_fail_closed(self):
        for values in ({}, {**self.before['switches'], 'unknown': False},
                       {k:v for k,v in self.before['switches'].items() if k != NEW},
                       {**self.before['switches'], NEW: 0}, {**self.before['switches'], NEW: None}):
            with self.subTest(values=values),self.assertRaises(ValueError):
                recorded_feature_profile(values)

    def test_unknown_new_runtime_selector_requires_inventory_update(self):
        namespace = dict(self.before['switches']);namespace['_UNKNOWN_EXPERIMENT_ENABLED'] = False
        with self.assertRaises(ValueError):
            snapshot_feature_profile(SimpleNamespace(**namespace))

    def test_profile_schema_is_strict_and_never_defaults_unknown_to_false(self):
        for profile in ({}, {'schema_version': True, 'switches': self.before['switches']},
                        {'schema_version': 2, 'switches': self.before['switches']},
                        {**self.before, 'extra': None}):
            with self.subTest(profile=profile),self.assertRaises(ValueError):
                validate_feature_comparison(profile, self.before, expected_changes={})

    def test_no_mutation_and_round_trip_for_explicit_code_only_comparison(self):
        original = deepcopy(self.before)
        loaded = json.loads(json.dumps(self.before))
        result = validate_feature_comparison(self.before, loaded, expected_changes={})
        self.assertEqual(result['declared_changes'], {})
        self.assertEqual(original, self.before)

    def test_undeclared_missing_reversed_and_invalid_expectations_fail(self):
        after = deepcopy(self.before);after['switches'][NEW] = True
        for changes in ({}, {NEW: (True, False)}, {NEW: (False, False)},
                        {NEW: (0, 1)}, {'unknown': (False, True)}, None):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                validate_feature_comparison(self.before, after, expected_changes=changes)
        with self.assertRaises(ValueError):
            validate_feature_comparison(self.before, self.before, expected_changes={NEW: (False, True)})
