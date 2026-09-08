"""Versioned, resumable corpus scans for exact and visual-only evidence."""

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
from time import perf_counter
from uuid import uuid4

from PIL import __version__ as pillow_version

from .benchmark import compare_jmaps
from .correction import render_correction_svg, render_source_blend_svg
from .geometry import Box
from .jmap import JMap
from .scanner import scan_png


DEFAULTS = dict(grid_step=8, include_color_objects=True, include_geometry=True,
                enable_ocr=False, recognized_text=None, room_box=None,
                source_grid=None, start_policy="auto")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, indent=2).encode("utf-8")


def _atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    temporary.write_bytes(_json_bytes(value))
    temporary.replace(path)


def implementation_identity() -> dict:
    """Fingerprint working code/assets, including uncommitted implementation."""
    package = Path(__file__).resolve().parent
    files = {
        path.relative_to(package).as_posix(): _digest(path.read_bytes())
        for path in sorted(package.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
        and path.suffix in {".py", ".png", ".js", ".css", ".html"}
    }
    try:
        head = subprocess.check_output(
            ["git", "-c", f"safe.directory={package.parent.as_posix()}",
             "rev-parse", "HEAD"], cwd=package.parent, stderr=subprocess.DEVNULL,
            text=True, timeout=5,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        head = None
    return dict(code_sha256=_digest(_json_bytes(files)), files=files, git_head=head,
                python=platform.python_version(), pillow=pillow_version,
                platform=platform.platform())


def _load_cached(folder: Path, key: str) -> dict | None:
    try:
        marker = json.loads((folder / "latest.json").read_text())
        attempt = marker["attempt"]
        if not re.fullmatch(r"[0-9a-f]{32}", attempt) or marker["key"] != key:
            return None
        directory = folder / attempt
        payload = (directory / "result.json").read_bytes()
        if _digest(payload) != marker["result_sha256"]:
            return None
        result = json.loads(payload)
        if result["key"] != key or result["directory"] != str(directory):
            return None
        for filename, expected_hash in result["artifact_hashes"].items():
            if Path(filename).name != filename:
                return None
            if _digest((directory / filename).read_bytes()) != expected_hash:
                return None
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return None


def run_corpus(manifest_path: str | Path, out_dir: str | Path, *, resume=False) -> dict:
    """Scan manifest cases; save each completed case before proceeding.

    Geometry is never inferred from reference JMaps. They are used only for
    post-scan evaluation. OCR execution is deliberately disabled for replayability;
    a supplied recognized_text string is included in the input fingerprint.
    """
    manifest_path = Path(manifest_path).resolve()
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    cases = manifest["cases"]
    ids = [case["id"] for case in cases]
    if not ids or len(set(ids)) != len(ids) or any(
        not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", name)
        for name in ids
    ):
        raise ValueError("Corpus requires unique, nonempty safe case IDs")
    identity = implementation_identity()
    output = Path(out_dir).resolve()
    report = dict(format="jtool-scanner-corpus-v1", run_id=uuid4().hex,
                  created_at=datetime.now(timezone.utc).isoformat(),
                  manifest=str(manifest_path), manifest_sha256=_digest(manifest_bytes),
                  implementation=identity, cases=[])
    for case in cases:
        if not isinstance(case.get("family"), str) or not case["family"].strip():
            raise ValueError("Each case needs a nonempty visual family")
        if case.get("partition") not in {"development", "evaluation", "control"}:
            raise ValueError("Partition must be development, evaluation or control")
        options = {**DEFAULTS, **manifest.get("defaults", {}), **case.get("options", {})}
        if set(options) != set(DEFAULTS) or options["enable_ocr"] is not False:
            raise ValueError("Unknown corpus option or nondeterministic OCR enabled")
        source = (manifest_path.parent / case["source"]).resolve()
        source_bytes = source.read_bytes()
        expected_path = case.get("expected_jmap")
        expected_bytes = ((manifest_path.parent / expected_path).read_bytes()
                          if expected_path else None)
        inputs = dict(source_sha256=_digest(source_bytes), options=options,
                      expected_sha256=_digest(expected_bytes) if expected_bytes else None,
                      code_sha256=identity["code_sha256"], python=identity["python"],
                      pillow=identity["pillow"], platform=identity["platform"])
        key = _digest(_json_bytes(inputs))
        folder = output / "cache" / key
        # Metadata is not part of scan identity; refresh family/partition labels
        # when assembling the current report, including on cache hits.
        result = _load_cached(folder, key) if resume else None
        reused = result is not None
        if result is None:
            attempt = uuid4().hex
            directory = folder / attempt
            directory.mkdir(parents=True)
            snapshot = directory / "source.png"
            snapshot.write_bytes(source_bytes)
            scan_options = dict(options)
            start_policy = scan_options.pop("start_policy")
            if scan_options["room_box"] is not None:
                scan_options["room_box"] = Box(*scan_options["room_box"])
            if scan_options["source_grid"] is not None:
                scan_options["source_grid"] = tuple(scan_options["source_grid"])
            started = perf_counter()
            scan = scan_png(snapshot, **scan_options)
            scan_seconds = perf_counter() - started
            project = scan.to_correction_project(snapshot, grid_step=options["grid_step"],
                                                 include_color_objects=options["include_color_objects"],
                                                 include_geometry=options["include_geometry"],
                                                 start_policy=start_policy)
            project.to_file(directory / "project.jscan.json")
            detected = scan.to_jmap(start_policy=start_policy)
            detected.to_file(directory / "detected.jmap")
            (directory / "jtool.svg").write_text(render_correction_svg(project), encoding="utf-8")
            (directory / "blend.svg").write_text(render_source_blend_svg(project), encoding="utf-8")
            comparison = None
            if expected_bytes is not None:
                reference = directory / "expected.jmap"
                reference.write_bytes(expected_bytes)
                comparison = compare_jmaps(detected, JMap.from_file(reference))
            result = dict(key=key, inputs=inputs, directory=str(directory),
                          implementation_at_scan=identity, scan_seconds=scan_seconds,
                          room_box=asdict(scan.room_box), source_grid=scan.source_grid,
                          detections=[asdict(d) for d in scan.detections],
                          object_counts=dict(Counter(d.type_id for d in scan.detections)),
                          warnings=scan.structural_warnings, comparison=comparison,
                          truth_level="exact_reference" if comparison is not None else "visual_only",
                          review_status="not_visually_reviewed")
            result["artifact_hashes"] = {
                path.name: _digest(path.read_bytes()) for path in directory.iterdir()
                if path.is_file()
            }
            # Do not seal a result under a code identity changed during its scan.
            if implementation_identity() != identity:
                raise RuntimeError("Implementation changed during corpus scan; result not cached")
            _atomic_json(directory / "result.json", result)
            _atomic_json(folder / "latest.json", dict(
                key=key, attempt=attempt,
                result_sha256=_digest((directory / "result.json").read_bytes()),
            ))
        report["cases"].append(dict(result, id=case["id"], source=str(source),
                                    family=case["family"], partition=case["partition"], reused=reused))
        _atomic_json(output / "runs" / (report["run_id"] + ".json"), report)
        print(f"{case['id']}: {'reused' if reused else 'scanned'}; {result['truth_level']}", flush=True)
    if implementation_identity() != identity:
        raise RuntimeError("Implementation changed during corpus run")
    report["complete"] = True
    _atomic_json(output / "runs" / (report["run_id"] + ".json"), report)
    _atomic_json(output / "report.json", report)
    return report
