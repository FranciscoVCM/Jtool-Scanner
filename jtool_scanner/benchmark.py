"""Exact real-world scanner benchmarks and self-contained diagnostics."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from html import escape
import base64
import json
from pathlib import Path
import shutil
from typing import Callable

from .constants import (
    OBJ_GRAVITY_DOWN,
    OBJ_GRAVITY_UP,
    OBJ_MINI_SPIKE_DOWN,
    OBJ_MINI_SPIKE_LEFT,
    OBJ_MINI_SPIKE_RIGHT,
    OBJ_MINI_SPIKE_UP,
    OBJ_PLAYER_START,
    OBJ_SPIKE_DOWN,
    OBJ_SPIKE_LEFT,
    OBJ_SPIKE_RIGHT,
    OBJ_SPIKE_UP,
    OBJ_WALLJUMP_LEFT,
    OBJ_WALLJUMP_RIGHT,
    OBJECT_NAMES,
)
from .geometry import Box
from .jmap import JMap, JMapObject
from .render_overlay import render_detection_overlay
from .render_svg import render_svg
from .scanner import ScanResult, scan_png


ORIENTATION_FAMILIES = (
    frozenset({OBJ_SPIKE_UP, OBJ_SPIKE_RIGHT, OBJ_SPIKE_LEFT, OBJ_SPIKE_DOWN}),
    frozenset(
        {
            OBJ_MINI_SPIKE_UP,
            OBJ_MINI_SPIKE_RIGHT,
            OBJ_MINI_SPIKE_LEFT,
            OBJ_MINI_SPIKE_DOWN,
        }
    ),
    frozenset({OBJ_WALLJUMP_LEFT, OBJ_WALLJUMP_RIGHT}),
    frozenset({OBJ_GRAVITY_UP, OBJ_GRAVITY_DOWN}),
)


@dataclass(frozen=True, slots=True)
class BenchmarkOptions:
    grid_step: int = 8
    include_color_objects: bool = True
    include_geometry: bool = True
    enable_ocr: bool = False
    start_policy: str = "auto"
    diagnostic_tolerance: float = 24


def compare_jmaps(
    detected: JMap,
    expected: JMap,
    diagnostic_tolerance: float = 24,
) -> dict:
    """Compare object multisets exactly, then classify the remaining errors."""

    detected_objects = _benchmark_objects(detected)
    expected_objects = _benchmark_objects(expected)
    detected_counter = Counter(_object_key(obj) for obj in detected_objects)
    expected_counter = Counter(_object_key(obj) for obj in expected_objects)
    exact_counter = detected_counter & expected_counter

    unmatched_detected = _remove_counter(detected_objects, exact_counter)
    missed_expected = _remove_counter(expected_objects, exact_counter)
    wrong_orientation, unmatched_detected, missed_expected = _match_wrong_orientation(
        unmatched_detected,
        missed_expected,
        diagnostic_tolerance,
    )
    shifted, unmatched_detected, missed_expected = _match_shifted(
        unmatched_detected,
        missed_expected,
        diagnostic_tolerance,
    )

    groups: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "expected": 0,
            "detected": 0,
            "exact": 0,
            "false_positive": 0,
            "missed": 0,
            "shifted": 0,
            "wrong_orientation": 0,
        }
    )
    for obj in expected_objects:
        groups[_group_name(obj.type_id)]["expected"] += 1
    for obj in detected_objects:
        groups[_group_name(obj.type_id)]["detected"] += 1
    for (type_id, _, _), count in exact_counter.items():
        groups[_group_name(type_id)]["exact"] += count
    for obj in unmatched_detected:
        groups[_group_name(obj.type_id)]["false_positive"] += 1
    for obj in missed_expected:
        groups[_group_name(obj.type_id)]["missed"] += 1
    for item in shifted:
        groups[_group_name(item["expected"]["type_id"])]["shifted"] += 1
    for item in wrong_orientation:
        groups[_group_name(item["expected"]["type_id"])]["wrong_orientation"] += 1

    exact_count = sum(exact_counter.values())
    metadata_exact = expected.infinite_jump == detected.infinite_jump
    metadata_error_count = 0 if metadata_exact else 1
    return {
        "summary": {
            "expected": len(expected_objects),
            "detected": len(detected_objects),
            "exact": exact_count,
            "false_positive": len(unmatched_detected),
            "missed": len(missed_expected),
            "shifted": len(shifted),
            "wrong_orientation": len(wrong_orientation),
            "exact_error_count": (
                len(unmatched_detected)
                + len(missed_expected)
                + len(shifted)
                + len(wrong_orientation)
                + metadata_error_count
            ),
            "metadata_error_count": metadata_error_count,
            "exact_recall": round(exact_count / len(expected_objects), 6)
            if expected_objects
            else 1.0,
            "exact_precision": round(exact_count / len(detected_objects), 6)
            if detected_objects
            else (1.0 if not expected_objects else 0.0),
        },
        "groups": dict(sorted(groups.items())),
        "wrong_orientation": wrong_orientation,
        "shifted": shifted,
        "false_positives": [_object_detail(obj) for obj in unmatched_detected],
        "missed": [_object_detail(obj) for obj in missed_expected],
        "metadata": {
            "infinite_jump_expected": expected.infinite_jump,
            "infinite_jump_detected": detected.infinite_jump,
            "infinite_jump_exact": metadata_exact,
        },
    }


def run_benchmark(
    manifest_path: str | Path,
    out_dir: str | Path,
    *,
    pair_ids: list[str] | None = None,
    options: BenchmarkOptions | None = None,
    baseline_path: str | Path | None = None,
    scanner: Callable[..., ScanResult] = scan_png,
) -> tuple[dict, bool]:
    """Run a golden-room benchmark and return its report and regression status."""

    options = options or BenchmarkOptions()
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    base = manifest_file.parent
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    selected = _select_pairs(manifest.get("pairs", []), pair_ids)
    report_pairs = []

    for pair in selected:
        pair_id = pair["id"]
        source_path = base / _pair_value(pair, "source", "game_image")
        expected_path = base / _pair_value(pair, "expected_jmap", "jmap")
        pair_options = _pair_options(options, manifest.get("defaults", {}), pair)
        result = scanner(
            source_path,
            room_box=_optional_box(pair.get("room_box")),
            grid_step=pair_options.grid_step,
            include_color_objects=pair_options.include_color_objects,
            include_geometry=pair_options.include_geometry,
            source_grid=_optional_grid(pair.get("source_grid")),
            recognized_text=pair.get("ocr_text"),
            enable_ocr=pair_options.enable_ocr,
        )
        detected = result.to_jmap(start_policy=pair_options.start_policy)
        expected = JMap.from_file(expected_path)
        comparison = compare_jmaps(
            detected,
            expected,
            pair_options.diagnostic_tolerance,
        )
        pair_dir = output / pair_id
        artifacts = _write_artifacts(
            pair_dir,
            pair_id,
            source_path,
            result,
            detected,
            expected,
        )
        report_pairs.append(
            {
                "id": pair_id,
                "source": str(source_path),
                "expected_jmap": str(expected_path),
                "options": _options_dict(pair_options),
                "room_box": _box_dict(result.room_box),
                "source_grid": list(result.source_grid) if result.source_grid else None,
                "comparison": comparison,
                "artifacts": artifacts,
            }
        )

    report = {
        "format": "jtool-scanner-benchmark-v1",
        "name": manifest.get("name", manifest_file.stem),
        "manifest": str(manifest_file),
        "pairs": report_pairs,
        "totals": _aggregate(report_pairs),
    }
    regressions = compare_baseline(report, baseline_path)
    report["baseline"] = regressions
    report_path = output / "report.json"
    report["artifacts"] = {
        "report_json": str(report_path),
        "dashboard_html": str(output / "index.html"),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "index.html").write_text(
        render_dashboard(report, output),
        encoding="utf-8",
    )
    return report, bool(regressions["regressions"])


def compare_baseline(report: dict, baseline_path: str | Path | None) -> dict:
    if baseline_path is None:
        return {"path": None, "regressions": [], "improvements": []}
    baseline_file = Path(baseline_path)
    baseline = json.loads(baseline_file.read_text(encoding="utf-8"))
    old_pairs = {pair["id"]: pair for pair in baseline.get("pairs", [])}
    regressions = []
    improvements = []
    for pair in report.get("pairs", []):
        old = old_pairs.get(pair["id"])
        if old is None:
            continue
        current_summary = pair["comparison"]["summary"]
        old_summary = old["comparison"]["summary"]
        current_errors = current_summary["exact_error_count"]
        old_errors = old_summary["exact_error_count"]
        current_exact = current_summary["exact"]
        old_exact = old_summary["exact"]
        item = {
            "id": pair["id"],
            "before_errors": old_errors,
            "after_errors": current_errors,
            "delta": current_errors - old_errors,
            "before_exact": old_exact,
            "after_exact": current_exact,
            "exact_delta": current_exact - old_exact,
        }
        if current_errors > old_errors or current_exact < old_exact:
            regressions.append(item)
        elif current_errors < old_errors or current_exact > old_exact:
            improvements.append(item)
    return {
        "path": str(baseline_file),
        "regressions": regressions,
        "improvements": improvements,
    }


def render_dashboard(report: dict, output: Path) -> str:
    cards = []
    for pair in report["pairs"]:
        summary = pair["comparison"]["summary"]
        artifacts = {
            key: Path(value).relative_to(output.resolve()).as_posix()
            for key, value in pair["artifacts"].items()
        }
        cards.append(
            f"""
<section>
  <h2>{escape(pair["id"])}</h2>
  <div class="metrics">
    <strong>{summary["exact"]}/{summary["expected"]} exact</strong>
    <span>{summary["false_positive"]} false positives</span>
    <span>{summary["missed"]} missed</span>
    <span>{summary["shifted"]} shifted</span>
    <span>{summary["wrong_orientation"]} wrong direction</span>
    <span>{summary["metadata_error_count"]} setting errors</span>
  </div>
  <div class="views">
    {_view("Source", artifacts["source"])}
    {_view("Detected", artifacts["detected_svg"])}
    {_view("Expected", artifacts["expected_svg"])}
    {_view("Blend", artifacts["blend_svg"])}
    {_view("Errors", artifacts["overlay_svg"])}
  </div>
  <details><summary>Object diagnostics</summary>{_diagnostic_rows(pair["comparison"])}</details>
</section>"""
        )
    totals = report["totals"]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{escape(report["name"])}</title>
<style>
body{{font:14px system-ui;margin:0;background:#eef1f3;color:#172027}}
header{{padding:16px 24px;background:#17242b;color:white;position:sticky;top:0;z-index:2}}
header span,.metrics span{{margin-left:16px}} main{{padding:20px}}
section{{background:white;border:1px solid #ccd3d7;margin:0 0 20px;padding:16px}}
h1,h2{{margin:0 0 10px}} .metrics{{margin-bottom:12px}}
.views{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:10px}}
figure{{margin:0;border:1px solid #ccd3d7;background:#dfe4e7}} figcaption{{padding:6px 8px}}
img{{display:block;width:100%;aspect-ratio:25/19;object-fit:contain;background:#d4d9dc}}
table{{border-collapse:collapse;margin-top:10px;width:100%}}td,th{{padding:5px;border:1px solid #ccd3d7;text-align:left}}
</style></head><body>
<header><h1>{escape(report["name"])}</h1>
<strong>{totals["exact"]}/{totals["expected"]} exact</strong>
<span>{totals["exact_error_count"]} exact errors across {totals["pairs"]} rooms</span>
</header><main>{''.join(cards)}</main></body></html>
"""


def _write_artifacts(
    pair_dir: Path,
    pair_id: str,
    source_path: Path,
    result: ScanResult,
    detected: JMap,
    expected: JMap,
) -> dict[str, str]:
    pair_dir.mkdir(parents=True, exist_ok=True)
    source_copy = pair_dir / f"source{source_path.suffix.lower() or '.png'}"
    detected_jmap = pair_dir / "detected.jmap"
    detected_svg = pair_dir / "detected.svg"
    expected_svg = pair_dir / "expected.svg"
    overlay_svg = pair_dir / "errors.svg"
    blend_svg = pair_dir / "blend.svg"
    shutil.copyfile(source_path, source_copy)
    detected.to_file(detected_jmap)
    detected_markup = render_svg(detected, f"{pair_id} detected")
    expected_markup = render_svg(expected, f"{pair_id} expected")
    detected_svg.write_text(detected_markup, encoding="utf-8")
    expected_svg.write_text(expected_markup, encoding="utf-8")
    overlay_svg.write_text(
        render_detection_overlay(
            result,
            source_path,
            title=f"{pair_id} exact-error overlay",
            truth=expected,
            tolerance=0,
            strict_types=True,
        ),
        encoding="utf-8",
    )
    blend_svg.write_text(
        _render_blend(result, source_path, detected_markup, pair_id),
        encoding="utf-8",
    )
    return {
        "source": str(source_copy.resolve()),
        "detected_jmap": str(detected_jmap.resolve()),
        "detected_svg": str(detected_svg.resolve()),
        "expected_svg": str(expected_svg.resolve()),
        "overlay_svg": str(overlay_svg.resolve()),
        "blend_svg": str(blend_svg.resolve()),
    }


def _render_blend(
    result: ScanResult,
    source_path: Path,
    detected_svg: str,
    title: str,
) -> str:
    encoded_svg = base64.b64encode(detected_svg.encode("utf-8")).decode("ascii")
    room = result.room_box
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{result.image_width}" height="{result.image_height}" viewBox="0 0 {result.image_width} {result.image_height}">
<title>{escape(title)} source and detected blend</title>
<image href="{escape(source_path.resolve().as_uri())}" width="{result.image_width}" height="{result.image_height}"/>
<image href="data:image/svg+xml;base64,{encoded_svg}" x="{room.x}" y="{room.y}" width="{room.width}" height="{room.height}" opacity=".58"/>
</svg>
"""


def _match_wrong_orientation(
    detected: list[JMapObject],
    expected: list[JMapObject],
    tolerance: float,
) -> tuple[list[dict], list[JMapObject], list[JMapObject]]:
    candidates = []
    for detected_index, detected_obj in enumerate(detected):
        family = _orientation_family(detected_obj.type_id)
        if family is None:
            continue
        for expected_index, expected_obj in enumerate(expected):
            if expected_obj.type_id not in family or expected_obj.type_id == detected_obj.type_id:
                continue
            distance = _distance(detected_obj, expected_obj)
            if distance <= tolerance:
                candidates.append((distance, detected_index, expected_index))
    return _consume_pairs(detected, expected, candidates)


def _match_shifted(
    detected: list[JMapObject],
    expected: list[JMapObject],
    tolerance: float,
) -> tuple[list[dict], list[JMapObject], list[JMapObject]]:
    candidates = []
    for detected_index, detected_obj in enumerate(detected):
        for expected_index, expected_obj in enumerate(expected):
            if expected_obj.type_id != detected_obj.type_id:
                continue
            distance = _distance(detected_obj, expected_obj)
            if 0 < distance <= tolerance:
                candidates.append((distance, detected_index, expected_index))
    return _consume_pairs(detected, expected, candidates)


def _consume_pairs(
    detected: list[JMapObject],
    expected: list[JMapObject],
    candidates: list[tuple[float, int, int]],
) -> tuple[list[dict], list[JMapObject], list[JMapObject]]:
    pairs = []
    used_detected: set[int] = set()
    used_expected: set[int] = set()
    for distance, detected_index, expected_index in sorted(candidates):
        if detected_index in used_detected or expected_index in used_expected:
            continue
        used_detected.add(detected_index)
        used_expected.add(expected_index)
        pairs.append(
            _pair_detail(detected[detected_index], expected[expected_index], distance)
        )
    return (
        pairs,
        [obj for index, obj in enumerate(detected) if index not in used_detected],
        [obj for index, obj in enumerate(expected) if index not in used_expected],
    )


def _aggregate(pairs: list[dict]) -> dict:
    keys = (
        "expected",
        "detected",
        "exact",
        "false_positive",
        "missed",
        "shifted",
        "wrong_orientation",
        "exact_error_count",
    )
    totals = {"pairs": len(pairs)}
    for key in keys:
        totals[key] = sum(pair["comparison"]["summary"][key] for pair in pairs)
    totals["exact_recall"] = (
        round(totals["exact"] / totals["expected"], 6) if totals["expected"] else 1.0
    )
    totals["exact_precision"] = (
        round(totals["exact"] / totals["detected"], 6)
        if totals["detected"]
        else (1.0 if not totals["expected"] else 0.0)
    )
    return totals


def _benchmark_objects(jmap: JMap) -> list[JMapObject]:
    return [obj for obj in jmap.objects if obj.type_id != OBJ_PLAYER_START]


def _remove_counter(
    objects: list[JMapObject],
    remove: Counter[tuple[int, int, int]],
) -> list[JMapObject]:
    remaining = remove.copy()
    output = []
    for obj in objects:
        key = _object_key(obj)
        if remaining[key]:
            remaining[key] -= 1
        else:
            output.append(obj)
    return output


def _object_key(obj: JMapObject) -> tuple[int, int, int]:
    return obj.type_id, obj.x, obj.y


def _object_detail(obj: JMapObject) -> dict:
    return {
        "type_id": obj.type_id,
        "type_name": OBJECT_NAMES.get(obj.type_id, f"unknown_{obj.type_id}"),
        "x": obj.x,
        "y": obj.y,
    }


def _pair_detail(detected: JMapObject, expected: JMapObject, distance: float) -> dict:
    return {
        "detected": _object_detail(detected),
        "expected": _object_detail(expected),
        "dx": detected.x - expected.x,
        "dy": detected.y - expected.y,
        "distance": round(distance, 3),
    }


def _distance(first: JMapObject, second: JMapObject) -> float:
    return ((first.x - second.x) ** 2 + (first.y - second.y) ** 2) ** 0.5


def _orientation_family(type_id: int) -> frozenset[int] | None:
    return next((family for family in ORIENTATION_FAMILIES if type_id in family), None)


def _group_name(type_id: int) -> str:
    family = _orientation_family(type_id)
    if family == ORIENTATION_FAMILIES[0]:
        return "full_spikes"
    if family == ORIENTATION_FAMILIES[1]:
        return "mini_spikes"
    if family == ORIENTATION_FAMILIES[2]:
        return "walljumps"
    if family == ORIENTATION_FAMILIES[3]:
        return "gravity"
    return OBJECT_NAMES.get(type_id, f"unknown_{type_id}").replace(" ", "_")


def _select_pairs(pairs: list[dict], pair_ids: list[str] | None) -> list[dict]:
    if not pair_ids:
        return pairs
    by_id = {pair["id"]: pair for pair in pairs}
    missing = sorted(set(pair_ids) - set(by_id))
    if missing:
        raise ValueError(f"unknown benchmark pair(s): {', '.join(missing)}")
    return [by_id[pair_id] for pair_id in pair_ids]


def _pair_value(pair: dict, preferred: str, legacy: str) -> str:
    value = pair.get(preferred, pair.get(legacy))
    if not value:
        raise ValueError(f"pair {pair.get('id', '<unknown>')} is missing {preferred}")
    return value


def _pair_options(
    options: BenchmarkOptions,
    defaults: dict,
    pair: dict,
) -> BenchmarkOptions:
    values = _options_dict(options)
    for source in (defaults, pair.get("options", {})):
        for key in values:
            if key in source:
                values[key] = source[key]
    return BenchmarkOptions(**values)


def _options_dict(options: BenchmarkOptions) -> dict:
    return {
        "grid_step": options.grid_step,
        "include_color_objects": options.include_color_objects,
        "include_geometry": options.include_geometry,
        "enable_ocr": options.enable_ocr,
        "start_policy": options.start_policy,
        "diagnostic_tolerance": options.diagnostic_tolerance,
    }


def _optional_box(value) -> Box | None:
    if value is None:
        return None
    values = [int(part) for part in value.split(",")] if isinstance(value, str) else list(value)
    if len(values) != 4:
        raise ValueError("room_box must contain x,y,width,height")
    return Box(*values)


def _optional_grid(value) -> tuple[int, int] | None:
    if value is None:
        return None
    if isinstance(value, str):
        left, right = value.lower().split("x", 1)
        return int(left), int(right)
    return int(value[0]), int(value[1])


def _box_dict(box: Box) -> dict[str, int]:
    return {"x": box.x, "y": box.y, "width": box.width, "height": box.height}


def _view(label: str, path: str) -> str:
    return (
        f'<figure><figcaption>{escape(label)}</figcaption>'
        f'<a href="{escape(path)}"><img loading="lazy" src="{escape(path)}" '
        f'alt="{escape(label)}"></a></figure>'
    )


def _diagnostic_rows(comparison: dict) -> str:
    rows = []
    metadata = comparison["metadata"]
    if not metadata["infinite_jump_exact"]:
        rows.append(
            "<tr><td>Setting</td><td>infinite jump</td>"
            f"<td>{metadata['infinite_jump_expected']}</td>"
            f"<td>{metadata['infinite_jump_detected']}</td><td></td></tr>"
        )
    for kind, items in (
        ("Wrong direction", comparison["wrong_orientation"]),
        ("Shifted", comparison["shifted"]),
    ):
        for item in items:
            rows.append(
                f"<tr><td>{kind}</td><td>{escape(item['expected']['type_name'])}</td>"
                f"<td>{item['expected']['x']},{item['expected']['y']}</td>"
                f"<td>{item['detected']['x']},{item['detected']['y']}</td>"
                f"<td>{item['dx']},{item['dy']}</td></tr>"
            )
    for kind, key in (("False positive", "false_positives"), ("Missed", "missed")):
        for item in comparison[key]:
            rows.append(
                f"<tr><td>{kind}</td><td>{escape(item['type_name'])}</td>"
                f"<td>{item['x']},{item['y']}</td><td></td><td></td></tr>"
            )
    if not rows:
        return "<p>No object errors.</p>"
    return (
        "<table><thead><tr><th>Issue</th><th>Type</th><th>Expected</th>"
        "<th>Detected</th><th>Offset</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
