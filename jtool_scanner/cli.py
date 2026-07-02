"""Command line helpers for the JTool scanner prototype."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from .constants import OBJ_PLAYER_START, OBJ_SAVE, OBJECT_NAMES
from .jmap import JMap
from .render_svg import render_svg
from .save_picker import choose_save, move_start_to_save


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

    args = parser.parse_args(argv)

    if args.command == "summary":
        return _summary(args.input, args.start_policy)
    if args.command == "normalize-start":
        return _normalize_start(args.input, args.output, args.start_policy)
    if args.command == "render":
        return _render(args.input, args.output, args.title, args.start_policy)
    if args.command == "dataset-summary":
        return _dataset_summary(args.manifest, args.start_policy)
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


def _spike_count(counts: Counter[int]) -> int:
    return sum(counts.get(type_id, 0) for type_id in range(3, 11))


def _format_objects(objects: list) -> str:
    if not objects:
        return "none"
    return " ".join(f"({obj.x}, {obj.y})" for obj in objects)


if __name__ == "__main__":
    raise SystemExit(main())
