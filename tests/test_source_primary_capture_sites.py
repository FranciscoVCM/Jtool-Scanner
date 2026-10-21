"""Real scan entry point carries original losses, never intermediate teachers."""
from contextlib import ExitStack
import inspect
from unittest import TestCase
from unittest.mock import patch

from jtool_scanner import scanner
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from scripts import source_rejected_primaries as recovery


class SourcePrimaryCaptureSiteTests(TestCase):
    def setUp(self):
        self.room = Box(0, 0, 800, 608)
        self.image = RGBImage(800, 608, bytes([80])*800*608*3)
        self.early = scanner.Detection('spike_up', 3, 96, 96, .61, Box(96,96,32,32))
        self.late = scanner.Detection('spike_right', 4, 160, 96, .73, Box(160,96,32,32))
        self.nonprimary = scanner.Detection('full_spike_shape_recovery', 4, 168, 104,
                                             .44, Box(168,104,32,32))

    def run_entry(self, *, enabled=True, source=True, refits=True, late=None,
                  grid=(25,19), retain_late=False):
        late = self.late if late is None else late
        with ExitStack() as stack:
            # This is a caller-wiring test, not another full recognition sweep.
            # Isolate unrelated typed list stages; the two real capture sites
            # and source-stage argument forwarding still execute in scan_image.
            for name, function in vars(scanner).copy().items():
                if not (inspect.isfunction(function) and function.__module__ == scanner.__name__):
                    continue
                signature = inspect.signature(function)
                parameters = list(signature.parameters)
                if signature.return_annotation != 'list[Detection]' or not parameters:
                    continue
                if parameters[0] == 'detections':
                    stack.enter_context(patch.object(scanner, name, side_effect=lambda d,*a,**k: d))
                elif name.startswith('_detect') and parameters[0] == 'image':
                    stack.enter_context(patch.object(scanner, name, return_value=[]))
            stack.enter_context(patch.object(scanner, '_SOURCE_REJECTED_PRIMARY_RECOVERY_ENABLED', enabled))
            stack.enter_context(patch.object(scanner, '_detect_geometry', return_value=[]))
            stack.enter_context(patch.object(scanner, '_recover_final_structural_right_mini_spikes',
                                             return_value=[self.early]))
            stack.enter_context(patch.object(scanner, '_prune_low_value_full_spike_recoveries', return_value=[]))
            stack.enter_context(patch.object(scanner, '_reconcile_common_room_geometry',
                                             return_value=[late, self.nonprimary]))
            stage = stack.enter_context(patch.object(scanner, '_reconcile_bright_filled_full_spikes',
                                                     return_value=[late] if retain_late else []))
            capture = stack.enter_context(patch.object(recovery, 'rejected_primary_candidates',
                                                       wraps=recovery.rejected_primary_candidates))
            source_stage = stack.enter_context(patch.object(scanner, '_apply_source_geometry',
                                                             side_effect=lambda result,*a,**k: result))
            result = scanner.scan_image(self.image, room_box=self.room, source_grid=grid,
                include_geometry=True, include_color_objects=False, source_geometry=source,
                _apply_shape_refits=refits)
        return result, stage, capture, source_stage

    def test_both_capture_sites_preserve_old_pending_and_exact_metadata_without_teachers(self):
        result, stage, capture, source = self.run_entry()
        stage.assert_called_once()
        self.assertEqual(capture.call_count, 2)
        pending = source.call_args.kwargs['rejected_primary_spikes']
        self.assertEqual(pending, (self.early, self.late))
        self.assertIs(pending[0], self.early)
        self.assertIs(pending[1], self.late)
        self.assertNotIn(self.nonprimary, pending)
        self.assertNotIn(self.early, source.call_args.args[0].detections)
        self.assertNotIn(self.late, source.call_args.args[0].detections)
        self.assertEqual(result.detections, [])

    def test_same_original_lost_twice_is_carried_once(self):
        _, _, capture, source = self.run_entry(late=self.early)
        self.assertEqual(capture.call_count, 2)
        self.assertEqual(source.call_args.kwargs['rejected_primary_spikes'], (self.early,))

    def test_disabled_feature_does_not_capture_or_change_source_arguments(self):
        _, _, capture, source = self.run_entry(enabled=False)
        capture.assert_not_called()
        source.assert_called_once()
        self.assertNotIn('rejected_primary_spikes', source.call_args.kwargs)

    def test_retained_late_primary_does_not_overwrite_earlier_pending(self):
        _, _, capture, source = self.run_entry(retain_late=True)
        self.assertEqual(capture.call_count, 2)
        self.assertEqual(source.call_args.kwargs['rejected_primary_spikes'], (self.early,))
        self.assertIn(self.late, source.call_args.args[0].detections)

    def test_translated_compact_route_does_not_capture_foreign_native_origins(self):
        _, _, capture, source = self.run_entry(grid=(19,13))
        capture.assert_not_called()
        source.assert_called_once()
        self.assertNotIn('rejected_primary_spikes', source.call_args.kwargs)

    def test_standard_and_inner_refit_routes_never_capture(self):
        for source_mode, refits in ((False, True), (True, False)):
            with self.subTest(source=source_mode, refits=refits):
                _, _, capture, source = self.run_entry(source=source_mode, refits=refits)
                capture.assert_not_called()
                source.assert_not_called()
