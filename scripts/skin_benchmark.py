"""Synthetic cross-skin benchmark: render reference maps with many skins, scan,
compare exactly, and rank the most frequent error kinds.

Offline evaluation tooling. Renders and reports go under an ignored output
directory; skins and local reference maps are private and never committed.
Synthetic renders find and rank errors quickly; real screenshots still decide
adoption (see PERFORMANCE_POLICY.md and MODEL_HANDOFF.md).

    python scripts/skin_benchmark.py OUT_DIR --maps 12 --skins 8 --mode source -j 12
    python scripts/skin_benchmark.py OUT_DIR --report-only

The same --seed, map list, skin list and mode give the same jobs, so two
scanner revisions can be compared on identical inputs (--compare OLD_DIR).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from jtool_scanner.constants import OBJECT_NAMES  # noqa: E402
from jtool_scanner.jmap import JMap  # noqa: E402

REFERENCE_GLOBS = (
    "fixtures/**/*.jmap",
    "local_corpus/lap-around-references-20261001/references/*.jmap",
    "local_corpus/user-reviewed-20261001/references/*.jmap",
)
EXCLUDE_PARTS = ("-warp",)  # variant duplicates of another layout


def reference_maps() -> list[Path]:
    seen, maps = set(), []
    for pattern in REFERENCE_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if any(part in path.stem for part in EXCLUDE_PARTS):
                continue
            key = path.resolve()
            if key not in seen:
                seen.add(key)
                maps.append(path)
    return maps


CAPTURE_SIZES = {"native": None, "scaled": (981, 746)}  # scaled: typical windowed capture


def _job_id(map_path: Path, skin: Path, mode: str, capture: str = "native") -> str:
    rel = map_path.relative_to(ROOT).as_posix().replace("/", "__").removesuffix(".jmap")
    return f"{rel}@{skin.name}@{mode}" + ("" if capture == "native" else f"@{capture}")


def run_job(map_path: str, skin: str, mode: str, out_dir: str, capture: str = "native") -> dict:
    from skin_render import render, visible_objects
    from jtool_scanner.benchmark import compare_jmaps
    from jtool_scanner.scanner import scan_png

    map_path, skin, out = (ROOT / map_path).resolve(), Path(skin), Path(out_dir)
    job = _job_id(map_path, skin, mode, capture)
    record = {"job": job, "map": map_path.relative_to(ROOT).as_posix(), "skin": skin.name,
              "mode": mode, "capture": capture}
    try:
        expected = JMap.from_file(map_path)
        suffix = "" if capture == "native" else f"@{capture}"
        png = out / "renders" / f"{job.split('@')[0]}@{skin.name}{suffix}.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        if not png.exists():
            image = render(expected, skin)
            if CAPTURE_SIZES[capture]:
                from PIL import Image
                image = image.resize(CAPTURE_SIZES[capture], Image.Resampling.BILINEAR)
            image.save(png)
        start = time.perf_counter()
        result = scan_png(png, include_color_objects=True, include_geometry=True,
                          enable_ocr=False, recognized_text="", source_geometry=(mode == "source"))
        record["seconds"] = round(time.perf_counter() - start, 3)
        detected = result.to_jmap(start_policy="auto")
        (out / "scans").mkdir(parents=True, exist_ok=True)
        detected.to_file(out / "scans" / f"{job}.jmap")
        visible = JMap.from_file(map_path)
        visible.objects = visible_objects(visible)  # off-room objects are not scannable
        comparison = compare_jmaps(detected, visible)
        record.update(
            summary=comparison["summary"],
            groups=comparison["groups"],
            wrong_orientation=[[w["expected"]["type_id"], w["detected"]["type_id"]] for w in comparison["wrong_orientation"]],
            shifted=[[s["expected"]["type_id"], s["detected"]["type_id"],
                      s["detected"]["x"] - s["expected"]["x"], s["detected"]["y"] - s["expected"]["y"]]
                     for s in comparison["shifted"]],
            false_positives=[[f["type_id"], f["x"], f["y"]] for f in comparison["false_positives"]],
            missed=[[m["type_id"], m["x"], m["y"]] for m in comparison["missed"]],
        )
    except Exception:  # keep the failure as a result; never drop a job silently
        record["error"] = traceback.format_exc()[-3000:]
    return record


def _name(type_id: int) -> str:
    return OBJECT_NAMES.get(type_id, str(type_id))


def report(results: list[dict]) -> dict:
    ok = [r for r in results if "summary" in r]
    totals = Counter()
    kinds = Counter()
    per_skin = defaultdict(Counter)
    per_map = defaultdict(Counter)
    for r in ok:
        s = r["summary"]
        for key in ("expected", "exact", "false_positive", "missed", "shifted", "wrong_orientation"):
            totals[key] += s[key]
        for exp, det in r["wrong_orientation"]:
            kinds[f"wrong direction: {_name(exp)} -> {_name(det)}"] += 1
        for exp, det, dx, dy in r["shifted"]:
            label = _name(exp) if exp == det else f"{_name(exp)} -> {_name(det)}"
            kinds[f"shifted ({dx:+d},{dy:+d}): {label}"] += 1
        for type_id, _, _ in r["false_positives"]:
            kinds[f"extra: {_name(type_id)}"] += 1
        for type_id, _, _ in r["missed"]:
            kinds[f"missed: {_name(type_id)}"] += 1
        errors = s["false_positive"] + s["missed"] + s["shifted"] + s["wrong_orientation"]
        per_skin[r["skin"]].update(expected=s["expected"], exact=s["exact"], errors=errors)
        per_map[r["map"]].update(expected=s["expected"], exact=s["exact"], errors=errors)
    seconds = [r["seconds"] for r in ok if "seconds" in r]
    jobs_with = Counter()
    for r in ok:
        seen = set()
        for exp, det in r["wrong_orientation"]:
            seen.add(f"wrong direction: {_name(exp)} -> {_name(det)}")
        for type_id, *_ in r["false_positives"]:
            seen.add(f"extra: {_name(type_id)}")
        for type_id, *_ in r["missed"]:
            seen.add(f"missed: {_name(type_id)}")
        jobs_with.update(seen)

    def rate(c):
        return round(c["exact"] / c["expected"], 4) if c["expected"] else None

    return {
        "jobs": len(results),
        "failed_jobs": [r["job"] for r in results if "error" in r],
        "totals": dict(totals),
        "exact_recall": round(totals["exact"] / totals["expected"], 4) if totals["expected"] else None,
        "scan_seconds": {"mean": round(sum(seconds) / len(seconds), 2), "max": max(seconds)} if seconds else None,
        "top_error_kinds": [[k, n, jobs_with.get(k, 0)] for k, n in kinds.most_common(40)],
        "worst_skins": sorted(([k, rate(v), v["errors"]] for k, v in per_skin.items()), key=lambda x: x[1] or 0)[:15],
        "per_map": {k: [rate(v), v["errors"]] for k, v in sorted(per_map.items())},
    }


def _print_report(rep: dict) -> None:
    print(f"jobs={rep['jobs']} failed={len(rep['failed_jobs'])} exact_recall={rep['exact_recall']} "
          f"totals={rep['totals']} scan_seconds={rep['scan_seconds']}")
    print("\nMost frequent error kinds (count, jobs affected):")
    for kind, count, jobs in rep["top_error_kinds"][:25]:
        print(f"  {count:6d}  {jobs:4d}  {kind}")
    print("\nWorst skins (exact recall, errors):")
    for skin, r, e in rep["worst_skins"][:10]:
        print(f"  {r}  {e:5d}  {skin}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir")
    parser.add_argument("--maps", type=int, default=0, help="number of reference maps (0 = all)")
    parser.add_argument("--map-filter", default="", help="only maps whose path contains this text")
    parser.add_argument("--skins", type=int, default=8, help="skins sampled per run")
    parser.add_argument("--seed", type=int, default=20261121)
    parser.add_argument("--mode", choices=("standard", "source", "both"), default="source")
    parser.add_argument("--capture", choices=("native", "scaled", "both"), default="native",
                        help="native 800x608 render, a bilinear 981x746 capture-like scale, or both")
    parser.add_argument("-j", "--jobs", type=int, default=12)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results_path = out / "results.jsonl"

    if not args.report_only:
        from skin_render import extract_skins
        rng = random.Random(args.seed)
        maps = [m for m in reference_maps() if args.map_filter in m.as_posix()]
        if args.maps:
            maps = sorted(rng.sample(maps, min(args.maps, len(maps))))
        skins = sorted(rng.sample(extract_skins(), args.skins))
        modes = ("standard", "source") if args.mode == "both" else (args.mode,)
        captures = ("native", "scaled") if args.capture == "both" else (args.capture,)
        done = set()
        if results_path.exists():
            done = {json.loads(line)["job"] for line in results_path.read_text(encoding="utf8").splitlines() if line}
        todo = [(m, s, mode, c) for m in maps for s in skins for mode in modes for c in captures
                if _job_id(m, s, mode, c) not in done]
        (out / "config.json").write_text(json.dumps({
            "seed": args.seed, "mode": args.mode, "capture": args.capture, "maps": [m.relative_to(ROOT).as_posix() for m in maps],
            "skins": [s.name for s in skins]}, indent=1), encoding="utf8")
        print(f"{len(maps)} maps x {len(skins)} skins x {len(modes)} modes; {len(todo)} jobs to run "
              f"({len(done)} already done)", flush=True)
        start = time.perf_counter()
        with ProcessPoolExecutor(max_workers=args.jobs) as pool, results_path.open("a", encoding="utf8") as sink:
            futures = [pool.submit(run_job, str(m), str(s), mode, str(out), c) for m, s, mode, c in todo]
            for n, future in enumerate(as_completed(futures), 1):
                record = future.result()
                sink.write(json.dumps(record) + "\n")
                sink.flush()
                if n % 10 == 0 or n == len(futures):
                    print(f"  {n}/{len(futures)} done, {time.perf_counter() - start:.0f}s", flush=True)

    results = [json.loads(line) for line in results_path.read_text(encoding="utf8").splitlines() if line]
    rep = report(results)
    (out / "report.json").write_text(json.dumps(rep, indent=1), encoding="utf8")
    _print_report(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
