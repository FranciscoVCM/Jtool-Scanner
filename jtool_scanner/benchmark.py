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

from PIL import Image, ImageDraw

from .constants import (
    GRID_SIZE,
    OBJ_BLOCK,
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
    ROOM_HEIGHT,
    ROOM_WIDTH,
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
    reference_warnings = _reference_warnings(expected)
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
        "reference_warnings": reference_warnings,
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
            comparison,
        )
        review_items = _review_items(comparison)
        _write_source_review_crops(
            pair_dir,
            source_path,
            result,
            review_items,
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
                "review_items": review_items,
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
    <span>{len(pair["comparison"].get("reference_warnings", []))} reference warnings</span>
  </div>
  <div class="views">
    {_view("Source", artifacts["source"])}
    {_view("Detected", artifacts["detected_svg"])}
    {_view("Expected", artifacts["expected_svg"])}
    {_view("Blend", artifacts["blend_svg"])}
    {_view("Errors", artifacts["overlay_svg"])}
    {_view("Localized review", artifacts["review_svg"], "review")}
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
.review img{{aspect-ratio:auto;max-height:760px}}
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
    comparison: dict,
) -> dict[str, str]:
    pair_dir.mkdir(parents=True, exist_ok=True)
    source_copy = pair_dir / f"source{source_path.suffix.lower() or '.png'}"
    detected_jmap = pair_dir / "detected.jmap"
    detected_svg = pair_dir / "detected.svg"
    expected_svg = pair_dir / "expected.svg"
    overlay_svg = pair_dir / "errors.svg"
    blend_svg = pair_dir / "blend.svg"
    review_svg = pair_dir / "review.svg"
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
    review_svg.write_text(
        _render_review(
            result,
            source_path,
            detected_markup,
            expected_markup,
            comparison,
            pair_id,
        ),
        encoding="utf-8",
    )
    return {
        "source": str(source_copy.resolve()),
        "detected_jmap": str(detected_jmap.resolve()),
        "detected_svg": str(detected_svg.resolve()),
        "expected_svg": str(expected_svg.resolve()),
        "overlay_svg": str(overlay_svg.resolve()),
        "blend_svg": str(blend_svg.resolve()),
        "review_svg": str(review_svg.resolve()),
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


def _review_items(comparison: dict) -> list[dict]:
    """Flatten exact comparison errors into stable, localized review items."""

    items = []
    for kind, key in (
        ("wrong_direction", "wrong_orientation"),
        ("shifted", "shifted"),
    ):
        for item in comparison[key]:
            expected = item["expected"]
            detected = item["detected"]
            items.append(
                {
                    "kind": kind,
                    "type_name": expected["type_name"],
                    "anchor_x": round((expected["x"] + detected["x"]) / 2),
                    "anchor_y": round((expected["y"] + detected["y"]) / 2),
                    "expected": expected,
                    "detected": detected,
                    "dx": item["dx"],
                    "dy": item["dy"],
                }
            )
    for kind, key, object_key in (
        ("false_positive", "false_positives", "detected"),
        ("missed", "missed", "expected"),
    ):
        for item in comparison[key]:
            items.append(
                {
                    "kind": kind,
                    "type_name": item["type_name"],
                    "anchor_x": item["x"],
                    "anchor_y": item["y"],
                    object_key: item,
                }
            )
    return sorted(
        items,
        key=lambda item: (
            item["anchor_y"],
            item["anchor_x"],
            item["kind"],
            item["type_name"],
        ),
    )


def _reference_warnings(expected: JMap) -> list[dict]:
    """Flag suspicious reference geometry without changing benchmark scoring."""

    blocks = [
        obj
        for obj in _benchmark_objects(expected)
        if obj.type_id == OBJ_BLOCK
    ]
    warnings = []
    for index, block in enumerate(blocks):
        overlaps = []
        for other_index, other in enumerate(blocks):
            if index == other_index:
                continue
            overlap_width = max(
                0,
                min(block.x + GRID_SIZE, other.x + GRID_SIZE)
                - max(block.x, other.x),
            )
            overlap_height = max(
                0,
                min(block.y + GRID_SIZE, other.y + GRID_SIZE)
                - max(block.y, other.y),
            )
            if overlap_width * overlap_height >= GRID_SIZE * GRID_SIZE // 2:
                overlaps.append(_object_detail(other))
        if len(overlaps) >= 2:
            warnings.append(
                {
                    "kind": "overlapping_reference_block",
                    "object": _object_detail(block),
                    "overlaps": overlaps,
                }
            )
    return warnings


def _write_source_review_crops(
    pair_dir: Path,
    source_path: Path,
    result: ScanResult,
    review_items: list[dict],
) -> None:
    """Attach normalized source crops to exact mismatch records."""

    if not review_items:
        return
    crop_dir = pair_dir / "review-crops"
    crop_dir.mkdir(parents=True, exist_ok=True)
    room = result.room_box
    scale_x = room.width / ROOM_WIDTH
    scale_y = room.height / ROOM_HEIGHT
    crop_size = 112
    with Image.open(source_path) as opened:
        source = opened.convert("RGB")
        for index, item in enumerate(review_items, start=1):
            map_left = min(
                max(item["anchor_x"] - crop_size // 2, 0),
                ROOM_WIDTH - crop_size,
            )
            map_top = min(
                max(item["anchor_y"] - crop_size // 2, 0),
                ROOM_HEIGHT - crop_size,
            )
            left = round(room.x + map_left * scale_x)
            top = round(room.y + map_top * scale_y)
            right = round(room.x + (map_left + crop_size) * scale_x)
            bottom = round(room.y + (map_top + crop_size) * scale_y)
            crop = source.crop((left, top, right, bottom)).resize((336, 336))
            marker_x = round((item["anchor_x"] - map_left) * 3)
            marker_y = round((item["anchor_y"] - map_top) * 3)
            draw = ImageDraw.Draw(crop)
            draw.rectangle(
                (marker_x, marker_y, marker_x + 96, marker_y + 96),
                outline=(235, 40, 55),
                width=4,
            )
            crop_path = crop_dir / f"{index:03d}-{item['kind']}.png"
            crop.save(crop_path)
            item["source_crop"] = str(crop_path.resolve())


def _render_review(
    result: ScanResult,
    source_path: Path,
    detected_svg: str,
    expected_svg: str,
    comparison: dict,
    title: str,
) -> str:
    """Render separate localized layers so blend ambiguity cannot hide errors."""

    items = _review_items(comparison)
    width = 980
    header_height = 54
    row_height = 230
    height = header_height + max(1, len(items)) * row_height
    detected_data = base64.b64encode(detected_svg.encode("utf-8")).decode("ascii")
    expected_data = base64.b64encode(expected_svg.encode("utf-8")).decode("ascii")
    source_uri = escape(source_path.resolve().as_uri())
    rows = []
    if not items:
        rows.append(
            '<text x="28" y="100" font-size="22" fill="#16734a">'
            "No exact object mismatches.</text>"
        )
    for index, item in enumerate(items):
        top = header_height + index * row_height
        crop_size = 112
        crop_x = min(
            max(item["anchor_x"] - crop_size // 2, 0),
            ROOM_WIDTH - crop_size,
        )
        crop_y = min(
            max(item["anchor_y"] - crop_size // 2, 0),
            ROOM_HEIGHT - crop_size,
        )
        issue = item["kind"].replace("_", " ")
        if item["kind"] in ("shifted", "wrong_direction"):
            issue += f" ({item['dx']:+d},{item['dy']:+d})"
        label = (
            f"{index + 1}. {issue}: {item['type_name']} "
            f"near {item['anchor_x']},{item['anchor_y']}"
        )
        rows.append(
            f'<rect x="12" y="{top + 6}" width="{width - 24}" '
            f'height="{row_height - 12}" fill="#fff" stroke="#c7cfd3"/>'
            f'<text x="28" y="{top + 34}" font-size="17" '
            f'font-weight="600">{escape(label)}</text>'
            + _review_panel(
                "Source",
                28,
                top + 48,
                crop_x,
                crop_y,
                crop_size,
                _source_image_markup(result, source_uri),
                item,
                "source",
            )
            + _review_panel(
                "Detected only",
                338,
                top + 48,
                crop_x,
                crop_y,
                crop_size,
                (
                    '<image href="data:image/svg+xml;base64,'
                    f'{detected_data}" width="{ROOM_WIDTH}" height="{ROOM_HEIGHT}"/>'
                ),
                item,
                "detected",
            )
            + _review_panel(
                "Expected JTool",
                648,
                top + 48,
                crop_x,
                crop_y,
                crop_size,
                (
                    '<image href="data:image/svg+xml;base64,'
                    f'{expected_data}" width="{ROOM_WIDTH}" height="{ROOM_HEIGHT}"/>'
                ),
                item,
                "expected",
            )
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}">'
        '<rect width="100%" height="100%" fill="#e8ecee"/>'
        f'<text x="20" y="34" font-size="22" font-weight="700">'
        f'{escape(title)} localized mismatch review</text>'
        + "".join(rows)
        + "</svg>"
    )


def _source_image_markup(result: ScanResult, source_uri: str) -> str:
    room = result.room_box
    scale_x = ROOM_WIDTH / room.width
    scale_y = ROOM_HEIGHT / room.height
    return (
        f'<image href="{source_uri}" '
        f'x="{-room.x * scale_x}" y="{-room.y * scale_y}" '
        f'width="{result.image_width * scale_x}" '
        f'height="{result.image_height * scale_y}"/>'
    )


def _review_panel(
    label: str,
    x: int,
    y: int,
    crop_x: int,
    crop_y: int,
    crop_size: int,
    image_markup: str,
    item: dict,
    layer: str,
) -> str:
    panel_width = 286
    panel_height = 150
    object_detail = item.get(layer)
    if layer == "source":
        object_detail = {
            "x": item["anchor_x"],
            "y": item["anchor_y"],
        }
    marker = ""
    if object_detail is not None:
        marker = (
            f'<rect x="{object_detail["x"]}" y="{object_detail["y"]}" '
            'width="32" height="32" fill="none" stroke="#e02b3b" '
            'stroke-width="3" vector-effect="non-scaling-stroke"/>'
        )
    return (
        f'<text x="{x}" y="{y + 16}" font-size="14">{escape(label)}</text>'
        f'<svg x="{x}" y="{y + 24}" width="{panel_width}" '
        f'height="{panel_height}" viewBox="{crop_x} {crop_y} '
        f'{crop_size} {crop_size}" preserveAspectRatio="xMidYMid meet">'
        f'<rect x="{crop_x}" y="{crop_y}" width="{crop_size}" '
        f'height="{crop_size}" fill="#d5dadd"/>'
        f"{image_markup}{marker}</svg>"
    )


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


def _view(label: str, path: str, class_name: str = "") -> str:
    class_attribute = f' class="{escape(class_name)}"' if class_name else ""
    return (
        f"<figure{class_attribute}><figcaption>{escape(label)}</figcaption>"
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
    for warning in comparison.get("reference_warnings", []):
        item = warning["object"]
        rows.append(
            "<tr><td>Reference warning</td>"
            f"<td>{escape(item['type_name'])}</td>"
            f"<td>{item['x']},{item['y']}</td><td></td>"
            f"<td>{len(warning['overlaps'])} overlaps</td></tr>"
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
