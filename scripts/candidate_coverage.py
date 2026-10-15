"""Separate missing detector queries from queries that did not get accepted.

Read-only evaluation tooling, never a detector, teacher or accuracy certificate.
Expected poses are offline labels. A query the detector never made cannot be
classified as accepted, rejected, or negative evidence from an empty result list.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _keys(values, name):
    result = []
    for value in values:
        try:
            key = tuple(value)
        except TypeError as exc:
            raise ValueError(f"{name} needs integer type,x,y triples") from exc
        if len(key) != 3 or any(not isinstance(v, int) or isinstance(v, bool) for v in key):
            raise ValueError(f"{name} needs integer type,x,y triples")
        if key[0] <= 0:
            raise ValueError(f"{name} needs positive object type IDs")
        result.append(key)
    return result


def partition_candidate_coverage(expected, queried, accepted):
    """Account for EVERY expected typed pose, including off-lattice poses.

    ``queried`` is the explicitly enumerated query set of ONE detector stage,
    not its accepted output. Duplicate query/accepted observations are harmless;
    duplicate expected labels are rejected to protect evaluation denominators.
    A query may abstain or fail many gates: not accepted is NOT proof of absence.
    Metadata, geometry correctness and source visibility need separate checks.
    """
    labelled = _keys(expected, "expected")
    if len(set(labelled)) != len(labelled):
        raise ValueError("Duplicate expected labels would change the denominator")
    expected_keys = set(labelled)
    queried_keys = set(_keys(queried, "queried"))
    accepted_keys = set(_keys(accepted, "accepted"))
    if not accepted_keys <= queried_keys:
        raise ValueError("Accepted outputs must belong to this stage's explicit query set")

    matched = expected_keys & accepted_keys
    queried_not_accepted = (expected_keys & queried_keys) - accepted_keys
    not_queried = expected_keys - queried_keys
    assert matched | queried_not_accepted | not_queried == expected_keys
    assert not (matched & queried_not_accepted or matched & not_queried
                or queried_not_accepted & not_queried)
    return {
        "expected_total": len(expected_keys),
        "accepted_expected_count": len(matched),
        "queried_not_accepted_count": len(queried_not_accepted),
        "not_queried_count": len(not_queried),
        "accepted_expected": sorted(matched),
        "queried_not_accepted": sorted(queried_not_accepted),
        "not_queried": sorted(not_queried),
        "query_count": len(queried_keys),
        "accepted_count": len(accepted_keys),
        "not_an_accuracy_or_negative_source_certificate": True,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="JSON with expected, queried and accepted type,x,y arrays")
    args = parser.parse_args(argv)
    data = json.loads(args.input.read_bytes())
    result = partition_candidate_coverage(data["expected"], data["queried"], data["accepted"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
