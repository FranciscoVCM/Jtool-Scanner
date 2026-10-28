"""Read-only, fail-closed comparison of two completed scan-corpus cases.

Object deltas are changes, NOT accuracy. Legacy artifacts alone cannot prove
entire raw-scan or process-local selector equality. No scanner runs or writes.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, fields
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jtool_scanner.jmap import JMap
from jtool_scanner.correction import PROJECT_FORMAT, PROJECT_VERSION
from jtool_scanner.scanner import ScanResult
from scripts.scanner_feature_profiles import validate_feature_comparison


ARTIFACTS = ('source.png', 'detected.jmap', 'jtool.svg', 'blend.svg', 'project.jscan.json')
BYTE_ARTIFACTS = ARTIFACTS[:-1]
SCAN_FIELDS = ('detections', 'room_box', 'source_grid', 'warnings', 'object_counts')


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _local_name(name):
    return (isinstance(name, str) and name not in ('', '.', '..')
            and PurePosixPath(name).name == PureWindowsPath(name).name == name
            and not PurePosixPath(name).is_absolute() and not PureWindowsPath(name).is_absolute()
            and ':' not in name)


def _case(directory):
    directory = Path(directory).resolve()
    result_bytes = (directory/'result.json').read_bytes()
    case = json.loads(result_bytes)
    if Path(case['directory']).resolve() != directory:
        raise ValueError('Case directory does not match the completed result')
    hashes = case['artifact_hashes']
    if not isinstance(hashes, dict) or not set(ARTIFACTS) <= hashes.keys():
        raise ValueError('Complete source, map, views and project checksums required')
    buffers = {}
    for name, expected in hashes.items():
        if not _local_name(name):
            raise ValueError('Recorded artifact checksum or local filename is invalid')
        buffers[name] = (directory/name).read_bytes()
        if _digest(buffers[name]) != expected:
            raise ValueError('Recorded artifact checksum or local filename is invalid')
    if hashes['source.png'] != case['inputs']['source_sha256']:
        raise ValueError('Source artifact does not match the scan input')
    if not all(k in case for k in SCAN_FIELDS):
        raise ValueError('Complete recorded scan fields required')
    if case['inputs'].get('expected_sha256') is not None and (
            hashes.get('expected.jmap') != case['inputs']['expected_sha256']):
        raise ValueError('Reference artifact does not match the evaluation input')
    counts = Counter(str(d['type_id']) for d in case['detections'])
    if dict(counts) != case['object_counts']:
        raise ValueError('Recorded object counts do not match detections')
    project = json.loads(buffers['project.jscan.json'])
    if project.get('format') != PROJECT_FORMAT or project.get('version') != PROJECT_VERSION:
        raise ValueError('Explicit current project schema required')
    source = project['source']
    if Path(source['image']).resolve() != directory/'source.png':
        raise ValueError('Project must refer to the authenticated source snapshot')
    if source['room_box'] != case['room_box']:
        raise ValueError('Project and scan room boxes differ')
    normalized_project = deepcopy(project)
    # Normalize exactly this authenticated path, never arbitrary history/text.
    normalized_project['source']['image'] = 'AUTHENTICATED_SOURCE_SNAPSHOT'
    evidence = {str(directory/name): value for name, value in hashes.items()}
    evidence[str(directory/'result.json')] = _digest(result_bytes)
    return (directory, case, normalized_project,
            JMap.from_text(buffers['detected.jmap'].decode('utf-8')), evidence)


def _json_value(value):
    return json.loads(json.dumps(value))


def _raw_checked(raw, case, project, mapped):
    if raw is None:
        return None
    value = _json_value(raw)
    if not isinstance(value, dict) or set(value) != {f.name for f in fields(ScanResult)}:
        raise ValueError('Entire current ScanResult record required; missing fields are unknown')
    if (any(type(value[k]) is not bool for k in ('source_geometry', 'dense_miniblock_room'))
            or any(type(value[k]) is not int for k in ('image_width', 'image_height', 'infinite_jump', 'dot_kid'))
            or not isinstance(value['recognized_text'], str)):
        raise ValueError('Raw scanner metadata requires its actual declared value types')
    for key, recorded in (('detections', 'detections'), ('room_box', 'room_box'),
                          ('source_grid', 'source_grid'), ('structural_warnings', 'warnings')):
        if value[key] != case[recorded]:
            raise ValueError('Raw scan record does not match the completed case')
    if any(value[k] != project['source'][k] for k in ('image_width', 'image_height')):
        raise ValueError('Raw image dimensions differ from the authenticated project')
    if ('recognized_text' not in project['scanner']
            or value['recognized_text'] != project['scanner']['recognized_text']):
        raise ValueError('Raw scanner metadata differs from the project')
    # The verified project schema explicitly omits False/None here (see
    # CorrectionProject.to_dict/from_dict). This is NOT an absent process profile.
    if (value['source_geometry'] != project['scanner'].get('source_geometry', False)
            or value['source_extent'] != project['source'].get('world_extent')
            or value['source_geometry'] != case['inputs']['options'].get('source_geometry', False)):
        raise ValueError('Raw source frame/mode differs from the project')
    if any(value[k] != getattr(mapped, k) for k in ('infinite_jump', 'dot_kid')):
        raise ValueError('Raw map flags differ from the exported map')
    return value


def _typed(objects):
    return Counter((o.type_id, o.x, o.y) for o in objects)


def _delta(counter):
    return [dict(key=list(key), count=count) for key, count in sorted(counter.items())]


def _detection_groups(detections):
    grouped = defaultdict(list)
    for d in detections:
        grouped[(d['type_id'], d['x'], d['y'])].append(d)
    return grouped


def _ordered_retained(before, after):
    remaining = iter(after)
    return all(any(item == original for item in remaining) for original in before)


def compare_cases(before_directory, after_directory, *, before_raw=None, after_raw=None,
                  before_profile=None, after_profile=None):
    """Verify both snapshots; return evidence without changing them or scanning.

    Full raw records and complete recorded selector profiles are optional for
    diagnosis, but BOTH are necessary for review_carry_eligible. Supplying only
    one side is an error. A carry flag never means an image was source-approved.
    """
    bd, before, bp, bm, be = _case(before_directory)
    ad, after, ap, am, ae = _case(after_directory)
    for left, right in ((before_raw, after_raw), (before_profile, after_profile)):
        if (left is None) != (right is None):
            raise ValueError('Provide both sides of raw/profile evidence, or neither')
    br = _raw_checked(before_raw, before, bp, bm)
    ar = _raw_checked(after_raw, after, ap, am)
    profile_equal = None
    if before_profile is not None:
        try:
            validate_feature_comparison(before_profile, after_profile, expected_changes={})
            profile_equal = True
        except ValueError:
            # Invalid/incomplete records are NOT a comparison of two profiles.
            validate_feature_comparison(before_profile, before_profile, expected_changes={})
            validate_feature_comparison(after_profile, after_profile, expected_changes={})
            profile_equal = False
    stable_inputs = lambda c: {k: v for k, v in c['inputs'].items() if k != 'code_sha256'}
    bt, at = _typed(bm.objects), _typed(am.objects)
    bg, ag = _detection_groups(before['detections']), _detection_groups(after['detections'])
    metadata_changed = sorted(key for key in bg.keys() & ag.keys() if bg[key] != ag[key])
    equality = dict(stable_inputs=stable_inputs(before) == stable_inputs(after),
        code_sha256=before['inputs']['code_sha256'] == after['inputs']['code_sha256'],
        recorded_scan_fields={k: before[k] == after[k] for k in SCAN_FIELDS},
        jmap_typed_multiset=bt == at,
        jmap_metadata={k: v for k, v in asdict(bm).items() if k != 'objects'} ==
                      {k: v for k, v in asdict(am).items() if k != 'objects'},
        project_except_authenticated_source_path=bp == ap,
        artifact_bytes={name: before['artifact_hashes'][name] == after['artifact_hashes'][name]
                        for name in BYTE_ARTIFACTS},
        entire_raw_scan=None if br is None else br == ar,
        recorded_feature_profile=profile_equal)
    carry = (equality['stable_inputs'] and all(equality['recorded_scan_fields'].values())
             and equality['jmap_typed_multiset'] and equality['jmap_metadata']
             and equality['project_except_authenticated_source_path']
             and all(equality['artifact_bytes'].values())
             and equality['entire_raw_scan'] is True and profile_equal is True)
    return dict(format='jtool-scanner-case-comparison-v1', complete=True, read_only=True,
        before=str(bd), after=str(ad), artifact_checksums_verified=True,
        equality=equality, added=_delta(at-bt), removed=_delta(bt-at),
        evidence_sha256={**be, **ae},
        existing_detection_metadata_changed_keys=[list(key) for key in metadata_changed],
        all_original_ordered_detections_retained=_ordered_retained(before['detections'], after['detections']),
        review_carry_eligible=carry, source_accuracy_certified=False,
        object_deltas_are_NOT_accuracy=True, legacy_missing_raw_OR_profile_is_unknown=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    parser.add_argument('--before-raw', type=Path, help='Entire ScanResult JSON, not a case summary')
    parser.add_argument('--after-raw', type=Path)
    parser.add_argument('--before-profile', type=Path, help='Complete recorded selector profile JSON')
    parser.add_argument('--after-profile', type=Path)
    args = parser.parse_args(argv)
    try:
        value = compare_cases(args.before, args.after,
            before_raw=_read(args.before_raw) if args.before_raw else None,
            after_raw=_read(args.after_raw) if args.after_raw else None,
            before_profile=_read(args.before_profile) if args.before_profile else None,
            after_profile=_read(args.after_profile) if args.after_profile else None)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(json.dumps(value, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
