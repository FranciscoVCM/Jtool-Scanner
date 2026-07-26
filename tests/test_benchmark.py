import json

from jtool_scanner.benchmark import compare_baseline, compare_jmaps
from jtool_scanner.constants import (
    OBJ_BLOCK,
    OBJ_PLAYER_START,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_UP,
)
from jtool_scanner.jmap import JMap, JMapObject


def _map(*objects: JMapObject, infinite_jump: int = 0) -> JMap:
    return JMap(objects=list(objects), infinite_jump=infinite_jump)


def test_compare_jmaps_uses_exact_multisets_and_ignores_player_start():
    expected = _map(
        JMapObject(32, 64, OBJ_BLOCK),
        JMapObject(32, 64, OBJ_BLOCK),
        JMapObject(80, 96, OBJ_SPIKE_UP),
        JMapObject(10, 20, OBJ_PLAYER_START),
    )
    detected = _map(
        JMapObject(32, 64, OBJ_BLOCK),
        JMapObject(80, 96, OBJ_SPIKE_UP),
        JMapObject(200, 200, OBJ_BLOCK),
        JMapObject(400, 400, OBJ_PLAYER_START),
    )

    result = compare_jmaps(detected, expected)

    assert result["summary"]["expected"] == 3
    assert result["summary"]["detected"] == 3
    assert result["summary"]["exact"] == 2
    assert result["summary"]["missed"] == 1
    assert result["summary"]["false_positive"] == 1


def test_compare_jmaps_explains_shift_and_wrong_orientation_separately():
    expected = _map(
        JMapObject(100, 100, OBJ_BLOCK),
        JMapObject(200, 200, OBJ_SPIKE_UP),
    )
    detected = _map(
        JMapObject(108, 100, OBJ_BLOCK),
        JMapObject(200, 200, OBJ_SPIKE_RIGHT),
    )

    result = compare_jmaps(detected, expected, diagnostic_tolerance=16)

    assert result["summary"]["exact"] == 0
    assert result["summary"]["shifted"] == 1
    assert result["summary"]["wrong_orientation"] == 1
    assert result["summary"]["missed"] == 0
    assert result["summary"]["false_positive"] == 0
    assert result["shifted"][0]["dx"] == 8


def test_compare_jmaps_keeps_distant_objects_as_miss_and_false_positive():
    expected = _map(JMapObject(0, 0, OBJ_BLOCK))
    detected = _map(JMapObject(64, 0, OBJ_BLOCK))

    result = compare_jmaps(detected, expected, diagnostic_tolerance=24)

    assert result["summary"]["shifted"] == 0
    assert result["summary"]["missed"] == 1
    assert result["summary"]["false_positive"] == 1


def test_compare_jmaps_includes_infinite_jump_in_exact_error_count():
    expected = _map(JMapObject(0, 0, OBJ_BLOCK), infinite_jump=1)
    detected = _map(JMapObject(0, 0, OBJ_BLOCK), infinite_jump=0)

    result = compare_jmaps(detected, expected)

    assert result["summary"]["exact"] == 1
    assert result["summary"]["metadata_error_count"] == 1
    assert result["summary"]["exact_error_count"] == 1


def test_compare_baseline_flags_more_errors_or_fewer_exact_matches(tmp_path):
    old_pair = {
        "id": "room",
        "comparison": {"summary": {"exact": 10, "exact_error_count": 2}},
    }
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text(json.dumps({"pairs": [old_pair]}), encoding="utf-8")
    report = {
        "pairs": [
            {
                "id": "room",
                "comparison": {
                    "summary": {"exact": 9, "exact_error_count": 2}
                },
            }
        ]
    }

    comparison = compare_baseline(report, baseline_path)

    assert comparison["regressions"][0]["exact_delta"] == -1
