"""Parallel unittest runner with an optional fast tier.

Runs exactly the tests that ``python -m unittest discover -s tests`` finds, in
worker processes. Durations are recorded locally so later runs schedule the
slowest tests first. Nothing is skipped unless ``--fast`` is given.

    python scripts/run_tests.py                 # full suite, parallel
    python scripts/run_tests.py --fast          # skip tests in tests/slow_tests.txt
    python scripts/run_tests.py -k save -j 8    # ids containing "save"
    python scripts/run_tests.py --write-slow-list 5   # refresh the slow list

The full suite (no ``--fast``) remains the gate before merging scanner
changes. The fast tier is for iteration only.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
# Match `python -m unittest discover -s tests` run from the repository root.
for _path in (str(TESTS), str(ROOT)):
    if _path not in sys.path:
        sys.path.insert(0, _path)
SLOW_LIST = TESTS / "slow_tests.txt"
DURATIONS = ROOT / ".artifacts" / "test-durations.json"  # ignored, machine-local


def _iter_ids(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_ids(item)
        else:
            yield item.id()


def discover_ids() -> list[str]:
    os.chdir(ROOT)
    loader = unittest.TestLoader()
    suite = loader.discover(str(TESTS), top_level_dir=str(TESTS))
    if loader.errors:
        raise SystemExit("Discovery errors:\n" + "\n".join(loader.errors))
    return list(_iter_ids(suite))


class _TimingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.durations_by_id: dict[str, float] = {}
        self._started: dict[str, float] = {}

    def startTest(self, test):
        self._started[test.id()] = time.perf_counter()
        super().startTest(test)

    def stopTest(self, test):
        super().stopTest(test)
        start = self._started.pop(test.id(), None)
        if start is not None:
            self.durations_by_id[test.id()] = time.perf_counter() - start


def run_worker(shard_path: str, out_path: str) -> int:
    os.chdir(ROOT)
    ids = json.loads(Path(shard_path).read_text(encoding="utf8"))
    suite = unittest.TestLoader().loadTestsFromNames(ids)
    runner = unittest.TextTestRunner(stream=sys.stderr, verbosity=0, resultclass=_TimingResult)
    result = runner.run(suite)
    payload = {
        "run": result.testsRun,
        "failures": [[t.id(), tb] for t, tb in result.failures],
        "errors": [[t.id(), tb] for t, tb in result.errors],
        "unexpected_successes": [t.id() for t in result.unexpectedSuccesses],
        "skipped": len(result.skipped),
        "durations": result.durations_by_id,
    }
    Path(out_path).write_text(json.dumps(payload), encoding="utf8")
    return 0


def _load_durations() -> dict[str, float]:
    try:
        return json.loads(DURATIONS.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return {}


def _slow_ids() -> set[str]:
    if not SLOW_LIST.exists():
        return set()
    return {line.strip() for line in SLOW_LIST.read_text(encoding="utf8").splitlines()
            if line.strip() and not line.startswith("#")}


def _shards(ids: list[str], durations: dict[str, float], jobs: int) -> list[list[str]]:
    # Longest-processing-time-first; unknown tests count as 1s.
    loads = [[0.0, []] for _ in range(jobs)]
    for test_id in sorted(ids, key=lambda i: -durations.get(i, 1.0)):
        target = min(loads, key=lambda load: load[0])
        target[0] += durations.get(test_id, 1.0)
        target[1].append(test_id)
    return [ids_ for _, ids_ in loads if ids_]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-j", "--jobs", type=int, default=max(1, min(12, (os.cpu_count() or 2) // 2)))
    parser.add_argument("--fast", action="store_true", help="skip tests listed in tests/slow_tests.txt")
    parser.add_argument("-k", dest="pattern", help="only run test ids containing this substring")
    parser.add_argument("--write-slow-list", type=float, metavar="SECONDS",
                        help="write tests/slow_tests.txt from recorded durations and exit")
    parser.add_argument("--worker", nargs=2, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.worker:
        return run_worker(*args.worker)

    durations = _load_durations()
    if args.write_slow_list is not None:
        if not durations:
            raise SystemExit(f"No recorded durations at {DURATIONS}; run the full suite first.")
        slow = sorted(i for i, s in durations.items() if s >= args.write_slow_list)
        header = (f"# Tests taking >= {args.write_slow_list:g}s in a full run; skipped by --fast.\n"
                  "# Regenerate: python scripts/run_tests.py --write-slow-list SECONDS\n")
        SLOW_LIST.write_text(header + "\n".join(slow) + "\n", encoding="utf8")
        total = sum(durations[i] for i in slow)
        print(f"{len(slow)} slow tests ({total:.0f}s serial) written to {SLOW_LIST}")
        return 0

    ids = discover_ids()
    discovered = len(ids)
    if args.pattern:
        ids = [i for i in ids if args.pattern in i]
    skipped_slow = 0
    if args.fast:
        slow = _slow_ids()
        skipped_slow = sum(i in slow for i in ids)
        ids = [i for i in ids if i not in slow]
    if not ids:
        print("No tests selected.")
        return 1

    jobs = max(1, min(args.jobs, len(ids)))
    shards = _shards(ids, durations, jobs)
    print(f"Running {len(ids)} of {discovered} tests in {len(shards)} workers"
          + (f" (fast tier: {skipped_slow} slow tests skipped)" if args.fast else ""), flush=True)
    start = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="run-tests-") as tmp:
        procs = []
        for n, shard in enumerate(shards):
            shard_path, out_path = Path(tmp, f"shard{n}.json"), Path(tmp, f"result{n}.json")
            shard_path.write_text(json.dumps(shard), encoding="utf8")
            log = open(Path(tmp, f"worker{n}.log"), "w", encoding="utf8")
            procs.append((subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "--worker", str(shard_path), str(out_path)],
                cwd=ROOT, stdout=log, stderr=subprocess.STDOUT), out_path, log, shard))
        run = skipped = 0
        failures, errors, unexpected = [], [], []
        new_durations = {}
        for proc, out_path, log, shard in procs:
            code = proc.wait()
            log.close()
            if not out_path.exists():
                errors.append((f"worker crashed (exit {code}) running {len(shard)} tests",
                               Path(log.name).read_text(encoding="utf8")[-4000:]))
                continue
            payload = json.loads(out_path.read_text(encoding="utf8"))
            run += payload["run"]
            skipped += payload["skipped"]
            failures += payload["failures"]
            errors += payload["errors"]
            unexpected += payload["unexpected_successes"]
            new_durations.update(payload["durations"])
    elapsed = time.perf_counter() - start

    if new_durations:
        merged = {**durations, **new_durations}
        try:
            DURATIONS.parent.mkdir(parents=True, exist_ok=True)
            DURATIONS.write_text(json.dumps(merged, indent=0, sort_keys=True), encoding="utf8")
        except OSError:
            pass

    for kind, items in (("FAIL", failures), ("ERROR", errors)):
        for test_id, tb in items:
            print("=" * 70 + f"\n{kind}: {test_id}\n" + "-" * 70 + f"\n{tb}")
    for test_id in unexpected:
        print(f"UNEXPECTED SUCCESS: {test_id}")
    ok = not failures and not errors and not unexpected and run == len(ids)
    print("-" * 70)
    print(f"Ran {run} tests in {elapsed:.1f}s ({len(shards)} workers); "
          f"failures={len(failures)} errors={len(errors)} skipped={skipped}"
          + ("" if run == len(ids) else f"; EXPECTED {len(ids)}"))
    print("OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
