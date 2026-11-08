"""Late source SAVE caller: true evidence, provenance, bypasses and metadata."""
from copy import deepcopy
from dataclasses import asdict, replace
import inspect
import unittest
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.runtime_sources import source_geometry_files
from tests.test_source_save_frames import scene


def saved(frame, detections):
    image = frame.original_snapshot()
    return scanner.ScanResult(
        image.width, image.height, frame.room, list(detections),
        infinite_jump=1, dot_kid=1, recognized_text='preserve',
        source_grid=(25, 19), source_geometry=True,
        structural_warnings=['earlier'], dense_miniblock_room=True,
    )


class LateSaveFrameTests(unittest.TestCase):
    def test_real_source_evidence_changes_only_x_and_regenerates_warnings(self):
        for side in ('left', 'right'):
            with self.subTest(side=side):
                frame, detection, expected = scene(side=side)
                other = replace(detection, type_id=3, kind='real_nested_spike', x=32, y=32)
                before = saved(frame, [other, detection])
                frozen = asdict(before)
                after = scanner._align_source_save_headers(before, frame.original_snapshot())
                self.assertEqual(asdict(before), frozen)
                self.assertIs(after.detections[0], other)
                self.assertEqual(asdict(after.detections[1]), {**asdict(detection), 'x': expected})
                for key in frozen.keys() - {'detections', 'structural_warnings'}:
                    self.assertEqual(getattr(after, key), getattr(before, key))
                self.assertEqual(after.structural_warnings,
                                 scanner.structural_scan_warnings(after.detections))

    def test_unqualified_modes_and_frames_never_construct_source_frame(self):
        frame, detection, _ = scene()
        before = saved(frame, [detection])
        for changes in ({'source_geometry': False}, {'source_grid': None},
                        {'source_grid': (19, 13)},
                        {'source_extent': Box(-8, 0, 816, 608)}):
            with self.subTest(changes=changes), patch('scripts.source_sampling.SourceFrame',
                    side_effect=AssertionError('Unqualified source')):
                candidate = replace(before, **changes)
                self.assertIs(scanner._align_source_save_headers(candidate, frame.original_snapshot()), candidate)
        with patch('scripts.source_sampling.SourceFrame', side_effect=AssertionError('Extended original')):
            self.assertIs(scanner._align_source_save_headers(before, frame.original_snapshot(),
                source_extent=Box(-8, 0, 816, 608)), before)
            extended = replace(before, source_extent=Box(-8, 0, 816, 608))
            self.assertIs(scanner._align_source_save_headers(extended, frame.original_snapshot(),
                source_extent=before.room_box), extended)

    def test_no_eligible_save_bypasses_source_construction(self):
        frame, detection, _ = scene()
        for entries in ([], [replace(detection, type_id=3, kind='spike')],
                        [replace(detection, kind='save_red_body_header')],
                        [replace(detection, image_box=Box(160, 172, 16, 16))]):
            before = saved(frame, entries)
            with self.subTest(entries=entries), patch('scripts.source_sampling.SourceFrame',
                    side_effect=AssertionError('No eligible body')):
                self.assertIs(scanner._align_source_save_headers(before, frame.original_snapshot()), before)

    def test_no_proof_or_existing_correct_anchor_preserves_entire_result_instance(self):
        for style in ('flat', 'gradient', 'blank', 'rail'):
            frame, detection, _ = scene(style=style)
            before = saved(frame, [detection])
            with self.subTest(style=style), patch.object(scanner, 'structural_scan_warnings',
                    side_effect=AssertionError('No changed positions')):
                self.assertIs(scanner._align_source_save_headers(before, frame.original_snapshot()), before)
        frame, detection, expected = scene()
        before = saved(frame, [replace(detection, x=expected)])
        self.assertIs(scanner._align_source_save_headers(before, frame.original_snapshot()), before)

    def test_collision_is_not_a_new_warning_or_object_merge(self):
        frame, detection, expected = scene()
        before = saved(frame, [detection, replace(detection, x=expected)])
        self.assertIs(scanner._align_source_save_headers(before, frame.original_snapshot()), before)

    def test_existing_auto_start_policy_follows_corrected_save_not_a_third_detection(self):
        frame, detection, expected = scene()
        before = saved(frame, [detection])
        after = scanner._align_source_save_headers(before, frame.original_snapshot())
        self.assertEqual(len(before.detections), len(after.detections))
        for policy in ('none', 'auto'):
            old_map, new_map = before.to_jmap(policy), after.to_jmap(policy)
            old_saves = [o for o in old_map.objects if o.type_id == 12]
            new_saves = [o for o in new_map.objects if o.type_id == 12]
            self.assertEqual([(o.x, o.y) for o in old_saves], [(detection.x, detection.y)])
            self.assertEqual([(o.x, o.y) for o in new_saves], [(expected, detection.y)])
            starts = [o for o in new_map.objects if o.type_id == 20]
            if policy == 'auto':
                self.assertEqual([(o.x, o.y) for o in starts], [(expected, detection.y)])
                self.assertEqual(new_map.player_save_x-old_map.player_save_x, expected-detection.x)
                self.assertEqual(new_map.player_save_y, old_map.player_save_y)
            else:
                self.assertEqual(starts, [])

    def test_call_sites_are_after_geometry_killers_and_arrows(self):
        direct = inspect.getsource(scanner.scan_image)
        lattice = inspect.getsource(scanner._scan_lattice_normalized_room)
        for code in (direct, lattice):
            self.assertEqual(code.count('result = _align_source_save_headers('), 1)
            self.assertGreater(code.index('result = _align_source_save_headers('),
                               code.index('result = _recover_source_gravity_arrows('))
            self.assertGreater(code.index('result = _align_source_save_headers('),
                               code.index('result = _apply_source_geometry('))
            self.assertIn('source_geometry and _apply_shape_refits and _SOURCE_SAVE_FRAME_ALIGNMENT_ENABLED', code)
        self.assertGreater(direct.index('result = _align_source_save_headers('),
                           direct.index('result = _recover_source_registered_killers('))
        self.assertIn('source_extent=normalization.source_extent', lattice)

    def test_actual_direct_scan_calls_once_last_and_default_or_inner_bypass(self):
        frame, _, _ = scene(style='flat')
        image = frame.original_snapshot()
        for enabled, source, refits in ((True, True, True), (False, True, True),
                                        (True, False, True), (True, True, False)):
            events = []
            def event(name):
                def call(result, original, *args, **kwargs):
                    self.assertIs(original, image)
                    events.append(name)
                    if name == 'geometry': result.source_geometry = True
                    return result
                return call
            with self.subTest(enabled=enabled, source=source, refits=refits), \
                 patch.object(scanner, '_SOURCE_SAVE_FRAME_ALIGNMENT_ENABLED', enabled), \
                 patch.object(scanner, '_detect_geometry', return_value=[]), \
                 patch.object(scanner, '_apply_source_geometry', side_effect=event('geometry')), \
                 patch.object(scanner, '_recover_source_registered_killers', side_effect=event('killers')), \
                 patch.object(scanner, '_recover_source_gravity_arrows', side_effect=event('arrows')), \
                 patch.object(scanner, '_align_source_save_headers', side_effect=event('save')):
                scanner.scan_image(image, room_box=frame.room, source_grid=(25, 19),
                    include_geometry=True, include_color_objects=True,
                    source_geometry=source, _apply_shape_refits=refits)
            self.assertEqual(events.count('save'), int(enabled and source and refits))
            if enabled and source and refits:
                self.assertEqual(events, ['geometry', 'killers', 'arrows', 'save'])

    def test_lattice_caller_passes_original_extent_once_not_canonical_source(self):
        frame, _, _ = scene(style='flat')
        image = frame.original_snapshot()
        normalization = scanner._CaptureLatticeNormalization(frame.room,
            scanner._CaptureLatticeAxis(0, 800, 1, 1), scanner._CaptureLatticeAxis(0, 608, 1, 1))
        empty = saved(frame, [])
        with patch.object(scanner, '_SOURCE_SAVE_FRAME_ALIGNMENT_ENABLED', True), \
             patch.object(scanner, 'scan_image', side_effect=[deepcopy(empty), deepcopy(empty)]), \
             patch.object(scanner, '_capture_lattice_consensus_enabled', return_value=False), \
             patch.object(scanner, '_resample_capture_lattice_room', return_value=image), \
             patch.object(scanner, '_apply_source_geometry', side_effect=lambda r,i,**k:r), \
             patch.object(scanner, '_align_source_save_headers', side_effect=lambda r,i,**k:r) as late:
            scanner._scan_lattice_normalized_room(image, normalization, grid_step=8,
                include_color_objects=False, recognized_text=None, source_geometry=True)
        late.assert_called_once()
        self.assertIs(late.call_args.args[1], image)
        self.assertEqual(late.call_args.kwargs['source_extent'], normalization.source_extent)

    def test_qualified_caller_is_registered_and_enabled(self):
        self.assertIs(scanner._SOURCE_SAVE_FRAME_ALIGNMENT_ENABLED, True)
        self.assertIn('source_save_frames.py', {p.name for p in source_geometry_files()})
