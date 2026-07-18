"""Command line helpers for the JTool scanner prototype."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from .constants import OBJ_PLAYER_START, OBJ_SAVE, OBJECT_NAMES
from .evaluation import (
    PairEvaluation,
    aggregate_evaluations,
    build_match_details,
    evaluate_scan,
)
from .geometry import Box
from .jmap import JMap
from .report_analysis import analyze_report
from .render_overlay import render_detection_overlay
from .render_svg import render_svg
from .save_picker import choose_save, move_start_to_save
from .scanner import ScanResult, scan_png


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jtool-scanner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summary_parser = subparsers.add_parser("summary", help="print a .jmap summary")
    summary_parser.add_argument("input")
    summary_parser.add_argument("--start-policy", default="auto")

    normalize_parser = subparsers.add_parser("normalize-start", help="write a copy with player start moved to a save")
    normalize_parser.add_argument("input")
    normalize_parser.add_argument("output")
    normalize_parser.add_argument("--start-policy", default="auto")

    render_parser = subparsers.add_parser("render", help="render a .jmap to SVG")
    render_parser.add_argument("input")
    render_parser.add_argument("output")
    render_parser.add_argument("--title", default=None)
    render_parser.add_argument("--start-policy", default="none")

    dataset_parser = subparsers.add_parser("dataset-summary", help="summarize a fixture manifest")
    dataset_parser.add_argument("manifest")
    dataset_parser.add_argument("--start-policy", default=None)

    analyze_report_parser = subparsers.add_parser("analyze-report", help="summarize scan report diagnostics")
    analyze_report_parser.add_argument("report")
    analyze_report_parser.add_argument(
        "--group",
        action="append",
        default=None,
        dest="groups",
        help="diagnostic group to show; may be passed more than once",
    )
    analyze_report_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="maximum examples or pair/type rows to show per section",
    )

    inspect_parser = subparsers.add_parser("inspect-image", help="detect room and high-confidence objects in a PNG")
    inspect_parser.add_argument("input")
    inspect_parser.add_argument("--room-box", default=None, help="optional x,y,width,height crop")
    inspect_parser.add_argument("--grid-step", type=int, default=16)
    inspect_parser.add_argument("--include-color-objects", action="store_true")
    inspect_parser.add_argument("--include-geometry", action="store_true")
    inspect_parser.add_argument(
        "--overlay",
        default=None,
        help="optional source-image detection overlay SVG path",
    )
    inspect_parser.add_argument(
        "--overlay-labels",
        action="store_true",
        help="show labels in detection overlays",
    )

    scan_parser = subparsers.add_parser("scan-image", help="scan a PNG and write a partial .jmap")
    scan_parser.add_argument("input")
    scan_parser.add_argument("output")
    scan_parser.add_argument("--preview", default=None, help="optional SVG preview path")
    scan_parser.add_argument("--room-box", default=None, help="optional x,y,width,height crop")
    scan_parser.add_argument("--grid-step", type=int, default=16)
    scan_parser.add_argument("--include-color-objects", action="store_true")
    scan_parser.add_argument("--include-geometry", action="store_true")
    scan_parser.add_argument("--start-policy", default="auto")
    scan_parser.add_argument(
        "--overlay",
        default=None,
        help="optional source-image detection overlay SVG path",
    )
    scan_parser.add_argument(
        "--overlay-labels",
        action="store_true",
        help="show labels in detection overlays",
    )

    scan_fixtures_parser = subparsers.add_parser("scan-fixtures", help="scan every game image in a fixture manifest")
    scan_fixtures_parser.add_argument("manifest")
    scan_fixtures_parser.add_argument("--out-dir", default=None)
    scan_fixtures_parser.add_argument("--room-box", default=None, help="optional x,y,width,height crop")
    scan_fixtures_parser.add_argument("--grid-step", type=int, default=16)
    scan_fixtures_parser.add_argument("--include-color-objects", action="store_true")
    scan_fixtures_parser.add_argument("--include-geometry", action="store_true")
    scan_fixtures_parser.add_argument("--start-policy", default="auto")
    scan_fixtures_parser.add_argument("--tolerance", type=float, default=64)
    scan_fixtures_parser.add_argument(
        "--pair",
        action="append",
        default=None,
        dest="pair_ids",
        help="scan only this fixture id; may be passed more than once",
    )
    scan_fixtures_parser.add_argument(
        "--summary",
        action="store_true",
        help="print aggregate match totals after per-fixture rows",
    )
    scan_fixtures_parser.add_argument(
        "--report-json",
        default=None,
        help="write per-fixture metrics, totals, settings, and artifact paths as JSON",
    )
    scan_fixtures_parser.add_argument(
        "--overlays",
        action="store_true",
        help="write source-image detection overlays when --out-dir is set",
    )
    scan_fixtures_parser.add_argument(
        "--overlay-labels",
        action="store_true",
        help="show labels in detection overlays",
    )

    args = parser.parse_args(argv)

    if args.command == "summary":
        return _summary(args.input, args.start_policy)
    if args.command == "normalize-start":
        return _normalize_start(args.input, args.output, args.start_policy)
    if args.command == "render":
        return _render(args.input, args.output, args.title, args.start_policy)
    if args.command == "dataset-summary":
        return _dataset_summary(args.manifest, args.start_policy)
    if args.command == "analyze-report":
        return _analyze_report(args.report, args.groups, args.limit)
    if args.command == "inspect-image":
        return _inspect_image(
            args.input,
            args.room_box,
            args.grid_step,
            args.include_color_objects,
            args.include_geometry,
            args.overlay,
            args.overlay_labels,
        )
    if args.command == "scan-image":
        return _scan_image(
            args.input,
            args.output,
            args.preview,
            args.room_box,
            args.grid_step,
            args.include_color_objects,
            args.include_geometry,
            args.start_policy,
            args.overlay,
            args.overlay_labels,
        )
    if args.command == "scan-fixtures":
        return _scan_fixtures(
            args.manifest,
            args.out_dir,
            args.room_box,
            args.grid_step,
            args.include_color_objects,
            args.include_geometry,
            args.start_policy,
            args.tolerance,
            args.overlays,
            args.overlay_labels,
            args.pair_ids,
            args.summary,
            args.report_json,
        )
    raise AssertionError(args.command)


def _summary(input_path: str, start_policy: str) -> int:
    jmap = JMap.from_file(input_path)
    print(f"version: {jmap.version}")
    print(f"objects: {len(jmap.objects)}")
    print("counts:")
    for type_id, count in sorted(jmap.object_counts().items()):
        print(f"  {type_id:>2} {OBJECT_NAMES.get(type_id, 'unknown')}: {count}")
    print(f"saves: {_format_objects(jmap.objects_of_type(OBJ_SAVE))}")
    print(f"starts: {_format_objects(jmap.objects_of_type(OBJ_PLAYER_START))}")
    choice = choose_save(jmap, start_policy)
    if choice:
        print(
            f"chosen save ({start_policy}): ({choice.save.x}, {choice.save.y}) "
            f"[{choice.reason}]"
        )
    else:
        print(f"chosen save ({start_policy}): none")
    return 0


def _normalize_start(input_path: str, output_path: str, start_policy: str) -> int:
    jmap = JMap.from_file(input_path)
    choice = move_start_to_save(jmap, start_policy)
    jmap.to_file(output_path)
    if choice:
        print(f"wrote {output_path}")
        print(f"moved start to save at ({choice.save.x}, {choice.save.y}) [{choice.reason}]")
    else:
        print(f"wrote {output_path}")
        print("start unchanged")
    return 0


def _render(input_path: str, output_path: str, title: str | None, start_policy: str) -> int:
    jmap = JMap.from_file(input_path)
    if start_policy != "none":
        move_start_to_save(jmap, start_policy)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_svg(jmap, title or Path(input_path).name), encoding="utf-8")
    print(f"wrote {out}")
    return 0


def _dataset_summary(manifest_path: str, start_policy: str | None) -> int:
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    policy = start_policy or manifest.get("default_start_policy", "auto")
    base = manifest_file.parent

    print(manifest.get("name", manifest_file.name))
    print(f"pairs: {len(manifest.get('pairs', []))}")
    print(f"start policy: {policy}")
    for pair in manifest.get("pairs", []):
        jmap_path = base / pair["jmap"]
        jmap = JMap.from_file(jmap_path)
        counts: Counter[int] = jmap.object_counts()
        choice = choose_save(jmap, policy)
        chosen = f"({choice.save.x}, {choice.save.y})" if choice else "none"
        print(
            f"{pair['id']}: objects={len(jmap.objects)} "
            f"blocks={counts.get(1, 0)} spikes={_spike_count(counts)} "
            f"saves={counts.get(OBJ_SAVE, 0)} start={chosen}"
        )
    return 0


def _analyze_report(report_path: str, groups: list[str] | None, limit: int) -> int:
    report_file = Path(report_path)
    report = json.loads(report_file.read_text(encoding="utf-8"))
    for line in analyze_report(report, groups=groups, limit=max(1, limit)):
        print(line)
    return 0


def _inspect_image(
    input_path: str,
    room_box_text: str | None,
    grid_step: int,
    include_color_objects: bool,
    include_geometry: bool,
    overlay_path: str | None,
    overlay_labels: bool,
) -> int:
    result = scan_png(
        input_path,
        room_box=_parse_box(room_box_text),
        grid_step=grid_step,
        include_color_objects=include_color_objects,
        include_geometry=include_geometry,
    )
    print(f"image: {result.image_width}x{result.image_height}")
    print(
        f"room: {result.room_box.x},{result.room_box.y},"
        f"{result.room_box.width},{result.room_box.height}"
    )
    if overlay_path:
        _write_detection_overlay(result, input_path, overlay_path, overlay_labels)
    if not result.detections:
        print("detections: none")
        return 0
    print("detections:")
    for detection in result.detections:
        print(
            f"  {detection.kind:>4} map=({detection.x}, {detection.y}) "
            f"score={detection.score:.2f} image_box="
            f"{detection.image_box.x},{detection.image_box.y},"
            f"{detection.image_box.width},{detection.image_box.height}"
        )
    return 0


def _scan_image(
    input_path: str,
    output_path: str,
    preview_path: str | None,
    room_box_text: str | None,
    grid_step: int,
    include_color_objects: bool,
    include_geometry: bool,
    start_policy: str,
    overlay_path: str | None,
    overlay_labels: bool,
) -> int:
    result = scan_png(
        input_path,
        room_box=_parse_box(room_box_text),
        grid_step=grid_step,
        include_color_objects=include_color_objects,
        include_geometry=include_geometry,
    )
    jmap = result.to_jmap(start_policy=start_policy)
    jmap.to_file(output_path)
    print(f"wrote {output_path}")
    print(f"detections: {len(result.detections)}")
    if preview_path:
        out = Path(preview_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_svg(jmap, Path(input_path).name), encoding="utf-8")
        print(f"wrote {out}")
    if overlay_path:
        _write_detection_overlay(result, input_path, overlay_path, overlay_labels)
    return 0


def _scan_fixtures(
    manifest_path: str,
    out_dir: str | None,
    room_box_text: str | None,
    grid_step: int,
    include_color_objects: bool,
    include_geometry: bool,
    start_policy: str,
    tolerance: float,
    write_overlays: bool,
    overlay_labels: bool,
    pair_ids: list[str] | None,
    print_summary: bool,
    report_json_path: str | None,
) -> int:
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    base = manifest_file.parent
    box = _parse_box(room_box_text)
    all_pairs = manifest.get("pairs", [])
    pairs, missing_pairs = _select_pairs(all_pairs, pair_ids)
    if missing_pairs:
        print(f"unknown fixture pair(s): {', '.join(missing_pairs)}")
        return 2

    if out_dir:
        out_base = Path(out_dir)
        out_base.mkdir(parents=True, exist_ok=True)
    else:
        out_base = None
        if write_overlays:
            print("overlays skipped: pass --out-dir to choose an output folder")

    print(f"scanning {len(pairs)} fixture pairs")
    if pair_ids:
        print(f"selected: {', '.join(pair['id'] for pair in pairs)}")
    print(f"tolerance: {tolerance:g} map px")
    evaluations = []
    report_pairs = []
    for pair in pairs:
        result = scan_png(
            base / pair["game_image"],
            room_box=box,
            grid_step=grid_step,
            include_color_objects=include_color_objects,
            include_geometry=include_geometry,
        )
        truth = JMap.from_file(base / pair["jmap"])
        evaluation = evaluate_scan(pair["id"], result.detections, truth, tolerance)
        evaluations.append(evaluation)
        jmap = result.to_jmap(start_policy=start_policy)
        artifact_paths: dict[str, str] = {}
        if out_base:
            jmap_path = out_base / f"{pair['id']}-scan.jmap"
            svg_path = out_base / f"{pair['id']}-scan.svg"
            jmap.to_file(jmap_path)
            svg_path.write_text(render_svg(jmap, pair["id"]), encoding="utf-8")
            artifact_paths["scan_jmap"] = str(jmap_path)
            artifact_paths["scan_svg"] = str(svg_path)
            if write_overlays:
                overlay_path = out_base / f"{pair['id']}-overlay.svg"
                _write_detection_overlay(
                    result,
                    base / pair["game_image"],
                    overlay_path,
                    overlay_labels,
                    truth,
                    tolerance,
                )
                artifact_paths["overlay_svg"] = str(overlay_path)
        if report_json_path:
            report_pairs.append(
                {
                    "id": pair["id"],
                    "game_image": str(base / pair["game_image"]),
                    "truth_jmap": str(base / pair["jmap"]),
                    "artifacts": artifact_paths,
                    "metrics": asdict(evaluation),
                    "details": build_match_details(
                        result.detections,
                        truth,
                        tolerance,
                    ),
                }
            )
        print(
            f"{pair['id']}: saves {evaluation.matched_saves}/"
            f"{evaluation.truth_saves} matched ({evaluation.detected_saves} detected), "
            f"warps {evaluation.matched_warps}/{evaluation.truth_warps} matched "
            f"({evaluation.detected_warps} detected)"
        )
        if include_color_objects:
            print(
                f"  color: apples {evaluation.matched_apples}/"
                f"{evaluation.truth_apples} matched ({evaluation.detected_apples} detected), "
                f"water {evaluation.matched_water}/"
                f"{evaluation.truth_water} matched ({evaluation.detected_water} detected), "
                f"walljumps {evaluation.matched_walljumps}/"
                f"{evaluation.truth_walljumps} matched "
                f"({evaluation.detected_walljumps} detected), "
                f"gravity {evaluation.matched_gravity}/"
                f"{evaluation.truth_gravity} matched "
                f"({evaluation.detected_gravity} detected)"
            )
        if include_geometry:
            print(
                f"  geometry: platforms {evaluation.matched_platforms}/"
                f"{evaluation.truth_platforms} matched "
                f"({evaluation.detected_platforms} detected), "
                f"mini blocks {evaluation.matched_mini_blocks}/"
                f"{evaluation.truth_mini_blocks} matched "
                f"({evaluation.detected_mini_blocks} detected), "
                f"blocks {evaluation.matched_blocks}/"
                f"{evaluation.truth_blocks} matched ({evaluation.detected_blocks} detected), "
                f"full spikes {evaluation.matched_full_spikes}/"
                f"{evaluation.truth_full_spikes} matched "
                f"({evaluation.detected_full_spikes} detected), "
                f"mini spikes {evaluation.matched_mini_spikes}/"
                f"{evaluation.truth_mini_spikes} matched "
                f"({evaluation.detected_mini_spikes} detected)"
            )
    if out_base:
        print(f"wrote scans to {out_base}")
    if report_json_path:
        report_path = Path(report_json_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "manifest": str(manifest_file),
            "settings": {
                "room_box": room_box_text,
                "grid_step": grid_step,
                "include_color_objects": include_color_objects,
                "include_geometry": include_geometry,
                "start_policy": start_policy,
                "tolerance": tolerance,
                "pair_ids": pair_ids or [],
                "out_dir": str(out_base) if out_base else None,
                "overlays": write_overlays and out_base is not None,
                "overlay_labels": overlay_labels,
            },
            "totals": aggregate_evaluations(evaluations),
            "pairs": report_pairs,
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote report to {report_path}")
    if print_summary:
        _print_evaluation_summary(evaluations, include_color_objects, include_geometry)
    return 0


def _spike_count(counts: Counter[int]) -> int:
    return sum(counts.get(type_id, 0) for type_id in range(3, 11))


def _select_pairs(pairs: list[dict], pair_ids: list[str] | None) -> tuple[list[dict], list[str]]:
    if not pair_ids:
        return pairs, []
    known_ids = {pair["id"] for pair in pairs}
    requested_ids = set(pair_ids)
    selected = [pair for pair in pairs if pair["id"] in requested_ids]
    missing = [pair_id for pair_id in pair_ids if pair_id not in known_ids]
    return selected, missing


def _print_evaluation_summary(
    evaluations: list[PairEvaluation],
    include_color_objects: bool,
    include_geometry: bool,
) -> None:
    totals = aggregate_evaluations(evaluations)
    print("summary:")
    print(f"  pairs: {totals['pairs']}")
    _print_metric_summary(
        "saves",
        totals["matched_saves"],
        totals["truth_saves"],
        totals["detected_saves"],
    )
    _print_metric_summary(
        "warps",
        totals["matched_warps"],
        totals["truth_warps"],
        totals["detected_warps"],
    )
    if include_color_objects:
        _print_metric_summary(
            "apples",
            totals["matched_apples"],
            totals["truth_apples"],
            totals["detected_apples"],
        )
        _print_metric_summary(
            "water",
            totals["matched_water"],
            totals["truth_water"],
            totals["detected_water"],
        )
        _print_metric_summary(
            "walljumps",
            totals["matched_walljumps"],
            totals["truth_walljumps"],
            totals["detected_walljumps"],
        )
        _print_metric_summary(
            "gravity",
            totals["matched_gravity"],
            totals["truth_gravity"],
            totals["detected_gravity"],
        )
    if include_geometry:
        _print_metric_summary(
            "platforms",
            totals["matched_platforms"],
            totals["truth_platforms"],
            totals["detected_platforms"],
        )
        _print_metric_summary(
            "mini blocks",
            totals["matched_mini_blocks"],
            totals["truth_mini_blocks"],
            totals["detected_mini_blocks"],
        )
        _print_metric_summary(
            "blocks",
            totals["matched_blocks"],
            totals["truth_blocks"],
            totals["detected_blocks"],
        )
        _print_metric_summary(
            "full spikes",
            totals["matched_full_spikes"],
            totals["truth_full_spikes"],
            totals["detected_full_spikes"],
        )
        _print_metric_summary(
            "mini spikes",
            totals["matched_mini_spikes"],
            totals["truth_mini_spikes"],
            totals["detected_mini_spikes"],
        )


def _print_metric_summary(label: str, matched: int, truth: int, detected: int) -> None:
    print(
        f"  {label}: {matched}/{truth} matched ({detected} detected, "
        f"recall {_format_rate(matched, truth)}, precision {_format_rate(matched, detected)})"
    )


def _format_rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    return f"{numerator / denominator:.1%}"


def _write_detection_overlay(
    result: ScanResult,
    image_path: str | Path,
    output_path: str | Path,
    overlay_labels: bool,
    truth: JMap | None = None,
    tolerance: float = 24,
) -> None:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_detection_overlay(
            result,
            image_path,
            Path(image_path).name,
            overlay_labels,
            truth,
            tolerance,
        ),
        encoding="utf-8",
    )
    print(f"wrote {out}")


def _parse_box(value: str | None) -> Box | None:
    return Box.from_text(value) if value else None


def _format_objects(objects: list) -> str:
    if not objects:
        return "none"
    return " ".join(f"({obj.x}, {obj.y})" for obj in objects)


if __name__ == "__main__":
    raise SystemExit(main())
