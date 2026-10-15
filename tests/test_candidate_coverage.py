import unittest
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.candidate_coverage import main, partition_candidate_coverage


class CandidateCoverageTests(unittest.TestCase):
    def test_every_label_has_exactly_one_disposition(self):
        result = partition_candidate_coverage(
            [(1, 32, 32), (1, 64, 32), (1, 48, 32)],
            [(1, 32, 32), (1, 64, 32)], [(1, 32, 32)])
        self.assertEqual(result["expected_total"], 3)
        self.assertEqual(result["accepted_expected"], [(1, 32, 32)])
        self.assertEqual(result["queried_not_accepted"], [(1, 64, 32)])
        self.assertEqual(result["not_queried"], [(1, 48, 32)])

    def test_empty_queried_rejections_do_not_hide_half_phase_misses(self):
        expected = [(1, 32, 32), (1, 48, 32), (1, 64, 48)]
        result = partition_candidate_coverage(expected, [(1, 32, 32)], [(1, 32, 32)])
        self.assertEqual(result["queried_not_accepted_count"], 0)
        self.assertEqual(result["not_queried_count"], 2)
        self.assertEqual(result["accepted_expected_count"], 1)
        self.assertEqual(result["expected_total"], 3)

    def test_type_size_direction_are_not_interchangeable(self):
        result = partition_candidate_coverage([(7, 16, 16)], [(3, 16, 16)], [(3, 16, 16)])
        self.assertEqual(result["not_queried"], [(7, 16, 16)])

    def test_negative_capture_origins_are_valid_labels(self):
        result = partition_candidate_coverage([(4, -8, 8)], [(4, -8, 8)], [])
        self.assertEqual(result["queried_not_accepted"], [(4, -8, 8)])

    def test_accepted_without_query_is_an_evidence_error(self):
        with self.assertRaisesRegex(ValueError, "explicit query set"):
            partition_candidate_coverage([], [], [(1, 0, 0)])

    def test_duplicate_expected_labels_do_not_silently_reduce_denominator(self):
        with self.assertRaisesRegex(ValueError, "denominator"):
            partition_candidate_coverage([(1, 0, 0), (1, 0, 0)], [], [])

    def test_repeated_observations_do_not_inflate_coverage(self):
        result = partition_candidate_coverage([(1, 0, 0)], [(1, 0, 0)] * 2, [(1, 0, 0)] * 3)
        self.assertEqual(result["query_count"], 1)
        self.assertEqual(result["accepted_count"], 1)
        self.assertEqual(result["expected_total"], 1)

    def test_lists_and_tuples_have_the_same_meaning(self):
        self.assertEqual(partition_candidate_coverage([[1, 0, 0]], [[1, 0, 0]], [[1, 0, 0]]),
                         partition_candidate_coverage([(1, 0, 0)], [(1, 0, 0)], [(1, 0, 0)]))

    def test_inputs_are_not_mutated(self):
        expected, queried, accepted = [[1, 0, 0]], [[1, 0, 0]], [[1, 0, 0]]
        partition_candidate_coverage(expected, queried, accepted)
        self.assertEqual((expected, queried, accepted), ([[1, 0, 0]], [[1, 0, 0]], [[1, 0, 0]]))

    def test_empty_stage_is_not_a_successful_accuracy_claim(self):
        result = partition_candidate_coverage([], [], [])
        self.assertEqual(result["expected_total"], 0)
        self.assertTrue(result["not_an_accuracy_or_negative_source_certificate"])

    def test_input_order_does_not_change_partitions(self):
        labels = [(1, 64, 0), (1, 0, 0), (1, 32, 0)]
        first = partition_candidate_coverage(labels, labels[:2], labels[:1])
        second = partition_candidate_coverage(labels[::-1], labels[:2][::-1], labels[:1])
        self.assertEqual(first, second)

    def test_noninteger_bool_or_invalid_type_is_rejected(self):
        for bad in [(1, True, 0), (1, 0.5, 0), (0, 0, 0), (-1, 0, 0), (1, 0), 123, None]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                partition_candidate_coverage([bad], [], [])

    def test_generated_full_lattice_keeps_all_half_phase_labels_in_denominator(self):
        grid = [(1, x, y) for y in range(0, 128, 32) for x in range(0, 128, 32)]
        half = [(1, 16, 32), (1, 64, 48)]
        result = partition_candidate_coverage(grid + half, grid, grid)
        self.assertEqual(result["expected_total"], 18)
        self.assertEqual(result["accepted_expected_count"], 16)
        self.assertEqual(result["not_queried_count"], 2)

    def test_cli_reads_only_supplied_evaluation_data(self):
        payload = json.dumps(dict(expected=[[1, 16, 0]], queried=[[1, 0, 0]], accepted=[])).encode()
        output = io.StringIO()
        with patch.object(Path, "read_bytes", return_value=payload), redirect_stdout(output):
            main(["--input", "unused-evaluation.json"])
        result = json.loads(output.getvalue())
        self.assertEqual(result["not_queried"], [[1, 16, 0]])
        self.assertTrue(result["not_an_accuracy_or_negative_source_certificate"])


if __name__ == "__main__":
    unittest.main()
