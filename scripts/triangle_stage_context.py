"""Capture equivalent ordinary-scan inputs for cheap triangle-stage replay.

Replay measures one stage, never whole-scanner accuracy or latency. References
are not detector inputs; case names select an offline report entry only.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jtool_scanner import scanner
from jtool_scanner.corpus import implementation_identity
from jtool_scanner.geometry import Box
from jtool_scanner.image import load_png
from jtool_scanner.jmap import JMap

STAGE = '_reconcile_source_triangle_sizes'


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def local_filename(filename):
    return (isinstance(filename, str) and filename not in {'', '.', '..'}
            and Path(filename).name == filename and not Path(filename).is_absolute())


def verify_artifacts(case):
    if 'detected.jmap' not in case['artifact_hashes']:
        raise ValueError('Ordinary map must have a recorded checksum')
    directory = Path(case['directory'])
    for filename, expected in case['artifact_hashes'].items():
        if not local_filename(filename) or digest(directory / filename) != expected:
            raise ValueError('Ordinary artifact identity mismatch')


def records(detections):
    return [asdict(detection) for detection in detections]


def decode(rows):
    return [scanner.Detection(**{**row, 'image_box': Box(**row['image_box'])})
            for row in rows]


def typed(mapped):
    return Counter((o.type_id, o.x, o.y) for o in mapped.objects)


def metadata(mapped):
    return {key: value for key, value in asdict(mapped).items() if key != 'objects'}


def compatible_input(case, identity):
    """Docs-only Git commits do not invalidate identical implementation bytes."""
    for key, actual in (('code_sha256', identity['code_sha256']),
                        ('python', identity['python']), ('pillow', identity['pillow']),
                        ('platform', identity['platform'])):
        if case['inputs'][key] != actual:
            raise ValueError(f'Ordinary case does not match current {key}')


def capture(report_path: Path, case_id: str, out_dir: Path):
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    if report['implementation'].get('shadow'):
        raise ValueError('Shadow output is not an ordinary-scan certificate')
    matches = [case for case in report['cases'] if case['id'] == case_id]
    if len(matches) != 1:
        raise ValueError('Select exactly one completed case from the report')
    case = matches[0]
    identity = implementation_identity()
    compatible_input(case, identity)
    source = Path(case['source'])
    if digest(source) != case['inputs']['source_sha256']:
        raise ValueError('Source changed since ordinary scan')
    directory = Path(case['directory'])
    verify_artifacts(case)
    expected_map = JMap.from_file(directory / 'detected.jmap')
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    original = getattr(scanner, STAGE)
    contexts = []

    def observe(detections, image, room):
        before = records(detections)
        result = original(detections, image, room)
        contexts.append((image, dict(room=asdict(room), before=before,
                                    after=records(result))))
        return result

    options = dict(case['inputs']['options'])
    policy = options.pop('start_policy')
    if options['room_box'] is not None:
        options['room_box'] = Box(*options['room_box'])
    if options['source_grid'] is not None:
        options['source_grid'] = tuple(options['source_grid'])
    setattr(scanner, STAGE, observe)
    try:
        scan = scanner.scan_png(source, **options)
        actual_map = scan.to_jmap(start_policy=policy)
    finally:
        setattr(scanner, STAGE, original)
    equal = typed(actual_map) == typed(expected_map) and metadata(actual_map) == metadata(expected_map)
    if not equal or implementation_identity() != identity:
        raise ValueError('Observed full map/ALL metadata or implementation differs')
    if digest(source) != case['inputs']['source_sha256']:
        raise ValueError('Source changed during capture')
    verify_artifacts(case)
    if not contexts:
        raise ValueError('Selected ordinary scan never invoked the triangle stage')
    entries = []
    for index, (image, entry) in enumerate(contexts):
        image_path = out_dir / f'context-{index}.png'
        Image.frombytes('RGB', (image.width, image.height), image.data).save(image_path)
        entry.update(image=image_path.name, image_sha256=digest(image_path),
                     image_rgb_sha256=sha256(image.data).hexdigest())
        entries.append(entry)
    payload = dict(format='triangle-stage-context-v1', stage=STAGE,
                   implementation=identity, case_id=case_id,
                   tool_sha256=digest(Path(__file__)),
                   ordinary_map_and_all_metadata_equal=True,
                   source_sha256=case['inputs']['source_sha256'],
                   ordinary_directory=str(directory), inputs=case['inputs'],
                   contexts=entries, replay_is_stage_only=True)
    path = out_dir / 'trace.json'
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(f'Captured {len(entries)} equivalent stage context(s): {path}', flush=True)
    return payload


def replay(trace_path: Path, out_dir: Path):
    trace_path = Path(trace_path)
    trace_bytes = trace_path.read_bytes()
    trace = json.loads(trace_bytes)
    if (trace.get('format') != 'triangle-stage-context-v1' or trace.get('stage') != STAGE
            or not trace.get('ordinary_map_and_all_metadata_equal')):
        raise ValueError('Expected a verified ordinary triangle-stage context')
    if not trace['contexts']:
        raise ValueError('Expected at least one observed stage context')
    identity = implementation_identity()
    # A candidate may differ from the capture code; preserve both identities.
    # Such a replay is explicitly NOT an ordinary scan or transfer certificate.
    loaded = []
    for entry in trace['contexts']:
        filename = entry['image']
        if not local_filename(filename):
            raise ValueError('Context image must be a local filename')
        image_path = trace_path.parent / filename
        if digest(image_path) != entry['image_sha256']:
            raise ValueError('Context pixels changed')
        image = load_png(image_path)
        if sha256(image.data).hexdigest() != entry['image_rgb_sha256']:
            raise ValueError('Decoded RGB identity mismatch')
        loaded.append((entry, image, decode(entry['before'])))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=False)
    rows = []
    for index, (entry, image, detections) in enumerate(loaded):
        before = Counter((d.type_id, d.x, d.y) for d in detections)
        result = getattr(scanner, STAGE)(detections, image, Box(**entry['room']))
        after = Counter((d.type_id, d.x, d.y) for d in result)
        rows.append(dict(context=index, complete_detection_records_equal=(records(result) == entry['after']),
                         added=sorted((after - before).elements()),
                         removed=sorted((before - after).elements()), after=records(result)))
    if implementation_identity() != identity:
        raise ValueError('Implementation changed during replay')
    payload = dict(format='triangle-stage-replay-v1', ordinary=False, stage_only=True,
                   trace_sha256=sha256(trace_bytes).hexdigest(),
                   tool_sha256=digest(Path(__file__)), capture_implementation=trace['implementation'],
                   replay_implementation=identity, rows=rows)
    (out_dir / 'replay.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(f'Replayed {len(rows)} stage context(s), NOT a full scan: {out_dir}', flush=True)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    capture_parser = sub.add_parser('capture')
    capture_parser.add_argument('--report', required=True, type=Path)
    capture_parser.add_argument('--case', required=True)
    capture_parser.add_argument('--out-dir', required=True, type=Path)
    replay_parser = sub.add_parser('replay')
    replay_parser.add_argument('--trace', required=True, type=Path)
    replay_parser.add_argument('--out-dir', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'capture':
        capture(args.report, args.case, args.out_dir)
    else:
        replay(args.trace, args.out_dir)


if __name__ == '__main__':
    main()
