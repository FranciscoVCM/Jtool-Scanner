"""Real-screenshot benchmark: scan every real capture that has a reference
JMap, compare exactly, and rank error kinds (the real-world counterpart of
skin_benchmark.py; same report and --compare output).

Sources: tracked fixture manifests, the Lap Around captures with local
references, and the user-reviewed Say/LapBackwards/CN3_7 references. Local
references are private evaluation labels; they are read after scanning only
and never committed. Outputs belong under an ignored directory.

    python scripts/real_benchmark.py .artifacts/real-bench/NAME -j 12 --compare .artifacts/real-bench/OLD
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import os

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
# A/B runs: JTOOL_CODE_ROOT points at an exported older revision (git archive)
# whose jtool_scanner/ and scripts/ are imported instead of this checkout's.
if os.environ.get("JTOOL_CODE_ROOT"):
    _code = Path(os.environ["JTOOL_CODE_ROOT"]).resolve()
    sys.path[:0] = [str(_code), str(_code / "scripts")]

from jtool_scanner.jmap import JMap  # noqa: E402
from skin_benchmark import _print_comparison, _print_report, report  # noqa: E402

LAP_REFS = ROOT / "local_corpus/lap-around-references-20261001/references"
LAP_SOURCES = ROOT / "fixtures/regressions/unseen-rooms/lap-around"
USER_REFS = ROOT / "local_corpus/user-reviewed-20261001/references"
USER_SOURCES = (ROOT / "local_corpus/giant-review/sources", ROOT / "local_corpus/user-reviewed-20261001/images")


def real_pairs() -> list[tuple[str, Path, Path]]:
    pairs = []
    for manifest in sorted(ROOT.glob("fixtures/**/manifest.json")):
        data = json.loads(manifest.read_text(encoding="utf8"))
        for pair in data.get("pairs", []):
            if "-warp" in pair["id"]:
                continue  # same capture as its base pair
            pairs.append((pair["id"], manifest.parent / pair["game_image"], manifest.parent / pair["jmap"]))
    for ref in sorted(LAP_REFS.glob("lapAround*.jmap")):
        number = int(ref.stem.removeprefix("lapAround"))
        source = LAP_SOURCES / f"screen-{number:02d}-source.png"
        if source.exists():
            pairs.append((f"lap-around-{number:02d}", source, ref))
    for ref in sorted(USER_REFS.glob("*.jmap")):
        for folder in USER_SOURCES:
            for name in (f"{ref.stem}.png", f"{ref.stem}_source.png"):
                if (folder / name).exists():
                    pairs.append((ref.stem, folder / name, ref))
                    break
            else:
                continue
            break
    seen, unique = set(), []
    for pair in pairs:
        if pair[1].resolve() not in seen:
            seen.add(pair[1].resolve())
            unique.append(pair)
    return unique


def run_pair(pair_id: str, image: str, reference: str, mode: str, out_dir: str) -> dict:
    from jtool_scanner.benchmark import compare_jmaps
    from jtool_scanner.scanner import scan_png

    out = Path(out_dir)
    job = f"{pair_id}@{mode}"
    record = {"job": job, "map": pair_id, "skin": "real", "mode": mode, "capture": "real"}
    try:
        start = time.perf_counter()
        result = scan_png(image, include_color_objects=True, include_geometry=True,
                          enable_ocr=False, recognized_text="", source_geometry=(mode == "source"))
        record["seconds"] = round(time.perf_counter() - start, 3)
        detected = result.to_jmap(start_policy="auto")
        (out / "scans").mkdir(parents=True, exist_ok=True)
        detected.to_file(out / "scans" / f"{job}.jmap")
        comparison = compare_jmaps(detected, JMap.from_file(reference))
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
    except Exception:
        record["error"] = traceback.format_exc()[-3000:]
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir")
    parser.add_argument("--mode", choices=("standard", "source"), default="source")
    parser.add_argument("-j", "--jobs", type=int, default=12)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--compare", metavar="OLD_DIR")
    parser.add_argument("--list", action="store_true", help="print the pairs and exit")
    args = parser.parse_args(argv)

    pairs = real_pairs()
    import jtool_scanner.scanner as _scanner
    print("scanner code:", Path(_scanner.__file__).resolve(), flush=True)
    if args.list:
        for pair_id, image, ref in pairs:
            print(pair_id, image.relative_to(ROOT).as_posix(), ref.relative_to(ROOT).as_posix())
        print(len(pairs), "pairs")
        return 0
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results_path = out / "results.jsonl"
    if not args.report_only:
        done = set()
        if results_path.exists():
            done = {json.loads(l)["job"] for l in results_path.read_text(encoding="utf8").splitlines() if l}
        todo = [p for p in pairs if f"{p[0]}@{args.mode}" not in done]
        print(f"{len(pairs)} real pairs; {len(todo)} to scan", flush=True)
        start = time.perf_counter()
        with ProcessPoolExecutor(max_workers=args.jobs) as pool, results_path.open("a", encoding="utf8") as sink:
            futures = [pool.submit(run_pair, pid, str(img), str(ref), args.mode, str(out)) for pid, img, ref in todo]
            for n, future in enumerate(as_completed(futures), 1):
                sink.write(json.dumps(future.result()) + "\n")
                sink.flush()
                if n % 10 == 0 or n == len(futures):
                    print(f"  {n}/{len(futures)} done, {time.perf_counter() - start:.0f}s", flush=True)
    results = [json.loads(l) for l in results_path.read_text(encoding="utf8").splitlines() if l]
    rep = report(results)
    (out / "report.json").write_text(json.dumps(rep, indent=1), encoding="utf8")
    _print_report(rep)
    if args.compare:
        old = [json.loads(l) for l in (Path(args.compare) / "results.jsonl").read_text(encoding="utf8").splitlines() if l]
        _print_comparison(old, results)
    return 0


if __name__ == "__main__":
    sys.exit(main())
