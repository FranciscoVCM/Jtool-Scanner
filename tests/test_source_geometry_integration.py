"""Real scanner-mode wiring, final coordinates, survivor metadata and identity."""
from copy import deepcopy
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
import tempfile
from unittest import TestCase
from unittest.mock import patch

from PIL import Image
from jtool_scanner import app, scanner
from jtool_scanner.cli import main
from jtool_scanner.correction import CorrectionProject
from jtool_scanner.geometry import Box
from jtool_scanner.image import RGBImage
from jtool_scanner.runtime_sources import source_geometry_files
from scripts.source_sampling import SourceFrame


class SourceGeometryIntegrationTests(TestCase):
    def setUp(self):
        self.image = RGBImage(800, 608, bytes(800*608*3))
        self.room = Box(0, 0, 800, 608)
        self.old = scanner.Detection('old_block', 1, 160, 160, .67, Box(160, 160, 32, 32))
        self.mini = scanner.Detection('real_mini', 2, 176, 160, .74, Box(176, 160, 16, 16))
        self.save = scanner.Detection('real_save', 11, 320, 352, .88, Box(320, 352, 32, 32))

    def result(self):
        return scanner.ScanResult(800, 608, self.room, [self.old, self.mini, self.save],
            infinite_jump=1, dot_kid=1, recognized_text='infinity', source_grid=(25, 19))

    def test_final_merge_preserves_survivors_and_retired_key_cannot_reenter(self):
        result = self.result()
        initial = deepcopy(result)
        proposed = {(1, 160, 160), (1, 176, 160), (2, 176, 160)}
        with patch('scripts.source_geometry_pipeline.source_proposals', return_value=(proposed, {(1, 160, 160)}, {})) as proposal:
            out = scanner._apply_source_geometry(result, self.image)
        self.assertEqual(proposal.call_count, 1)
        self.assertEqual(proposal.call_args.args, (self.image, self.room, initial.detections))
        self.assertTrue(proposal.call_args.kwargs['source_frame'].matches_source(self.image, self.room))
        self.assertIs(proposal.call_args.kwargs['include_growth_confidence'], True)
        self.assertIs(out, result)
        self.assertNotIn(self.old, out.detections)
        self.assertTrue(any(d is self.mini for d in out.detections))
        self.assertTrue(any(d is self.save for d in out.detections))
        self.assertEqual(sum((d.type_id,d.x,d.y)==(2,176,160) for d in out.detections), 1)
        self.assertEqual(out.infinite_jump, initial.infinite_jump)
        self.assertEqual(out.dot_kid, initial.dot_kid)
        self.assertEqual(out.recognized_text, initial.recognized_text)
        self.assertTrue(out.source_geometry)

    def test_hollow_emission_and_project_blend_use_capture_world_not_physical_crop(self):
        result = self.result()
        extent = Box(-5, -1, 810, 610)
        frame = SourceFrame(self.image, self.room, extent=extent, canonical=self.image)
        key = (4, 240, 368)
        with patch('scripts.source_geometry_pipeline.source_proposals',
                   return_value=({key}, set(), {'source_hollow': {'accepted': [{'key': key}]}})):
            out = scanner._apply_source_geometry(result, self.image, source_frame=frame)
        added = next(d for d in out.detections if (d.type_id, d.x, d.y) == key)
        self.assertEqual(added.kind, 'source_hollow_glyph')
        self.assertEqual(added.image_box, Box(238, 368, 32, 32))
        self.assertEqual(out.source_extent, extent)
        project = CorrectionProject.from_scan(out)
        self.assertEqual(project.source_extent, extent)
        self.assertEqual(CorrectionProject.from_dict(project.to_dict()).source_extent, extent)

    def test_compact_mapping_abstains_and_records_requested_mode(self):
        result = self.result()
        result.source_grid = (19, 13)
        before = deepcopy(result.detections)
        with patch('scripts.source_geometry_pipeline.source_proposals', side_effect=AssertionError('Unqualified frame')):
            out = scanner._apply_source_geometry(result, self.image)
        self.assertEqual(out.detections, before)
        self.assertTrue(out.source_geometry)

    def test_compact_normalized_shape_stage_keeps_source_seed_recovery(self):
        # Compact originals are padded to canonical working pixels BEFORE the
        # shape stage. The later original-source material stage must still abstain.
        image = RGBImage(608, 416, bytes(608*416*3))
        with patch.object(scanner, '_reconcile_source_triangle_sizes', side_effect=lambda d,*a,**k:d) as size, \
             patch('scripts.source_geometry_pipeline.source_proposals', side_effect=AssertionError('Compact source is not full-frame qualified')):
            result = scanner.scan_image(image, room_box=Box(0,0,608,416), source_grid=(19,13),
                include_geometry=True, include_color_objects=False, source_geometry=True)
        size.assert_called_once()
        self.assertTrue(size.call_args.kwargs.get('source_seed', False))
        self.assertEqual((size.call_args.args[1].width,size.call_args.args[1].height),(800,608))
        self.assertEqual(size.call_args.args[2], Box(0,0,800,608))
        self.assertEqual(result.source_grid,(19,13))
        self.assertTrue(result.source_geometry)

    def test_compact_standard_shape_stage_does_not_enable_source_seed(self):
        image = RGBImage(608, 416, bytes(608*416*3))
        with patch.object(scanner, '_reconcile_source_triangle_sizes', side_effect=lambda d,*a,**k:d) as size:
            result = scanner.scan_image(image, room_box=Box(0,0,608,416), source_grid=(19,13),
                include_geometry=True, include_color_objects=False)
        size.assert_called_once()
        self.assertFalse(size.call_args.kwargs.get('source_seed', False))
        self.assertEqual(result.source_grid,(19,13))
        self.assertFalse(result.source_geometry)

    def test_standard_no_geometry_never_calls_source_pipeline(self):
        with patch.object(scanner, '_apply_source_geometry', side_effect=AssertionError('Not requested')):
            result = scanner.scan_image(self.image, room_box=self.room, source_grid=(25, 19))
        self.assertFalse(result.source_geometry)

    def test_mode_without_geometry_or_nonboolean_rejected(self):
        for options in ({'source_geometry': True}, {'source_geometry': 'true'}, {'source_geometry': 1}):
            with self.assertRaises(ValueError):
                scanner.scan_image(self.image, room_box=self.room, **options)

    def test_png_forwards_opt_in_but_default_call_remains_compatible(self):
        with patch.object(scanner, 'load_png', return_value=self.image), patch.object(scanner, 'scan_image', return_value=self.result()) as scan:
            scanner.scan_png('unused.png', enable_ocr=False)
            self.assertNotIn('source_geometry', scan.call_args.kwargs)
            scanner.scan_png('unused.png', enable_ocr=False, include_geometry=True, source_geometry=True)
            self.assertTrue(scan.call_args.kwargs['source_geometry'])

    def test_seed_switch_is_explicit_and_standard_uses_existing_algorithm(self):
        with patch('jtool_scanner.scanner.contour_size_changes', return_value=(set(),set())) as standard, \
             patch('jtool_scanner.spike_size.source_seed_size_changes', return_value=(set(),set())) as seeded:
            scanner._reconcile_source_triangle_sizes([self.old],self.image,self.room)
            self.assertEqual(standard.call_count,1)
            seeded.assert_not_called()
            scanner._reconcile_source_triangle_sizes([self.old],self.image,self.room,source_seed=True)
            self.assertEqual(seeded.call_count,1)

    def test_capture_inner_scans_do_not_get_source_mode_and_outer_applies_once(self):
        normalization = scanner._CaptureLatticeNormalization(self.room,
            scanner._CaptureLatticeAxis(0,800,1,1), scanner._CaptureLatticeAxis(0,608,1,1))
        empty = scanner.ScanResult(800,608,self.room,[],source_grid=(25,19))
        with patch.object(scanner,'scan_image',side_effect=[deepcopy(empty),deepcopy(empty)]) as scans, \
             patch.object(scanner,'_capture_lattice_consensus_enabled',return_value=False), \
             patch.object(scanner,'_resample_capture_lattice_room',return_value=self.image), \
             patch.object(scanner,'_reconcile_source_triangle_sizes',side_effect=lambda d,*a,**k:d) as size, \
             patch.object(scanner,'_apply_source_geometry',side_effect=lambda r,i,**kwargs:r) as source:
            scanner._scan_lattice_normalized_room(self.image,normalization,grid_step=8,
                include_color_objects=False,recognized_text=None,source_geometry=True)
        self.assertEqual(scans.call_count,2)
        self.assertTrue(all(c.kwargs['_apply_shape_refits'] is False for c in scans.call_args_list))
        self.assertTrue(all('source_geometry' not in c.kwargs for c in scans.call_args_list))
        source.assert_called_once()
        self.assertIsInstance(source.call_args.kwargs['source_frame'], SourceFrame)
        self.assertEqual(source.call_args.kwargs['source_frame'].canonical_rgb, self.image.data)
        self.assertTrue(size.call_args.kwargs['source_seed'])

    def test_project_mode_round_trip_does_not_change_jmap_header_or_objects(self):
        result = self.result()
        original = CorrectionProject.from_scan(result)
        result.source_geometry = True
        experimental = CorrectionProject.from_scan(result)
        self.assertNotIn('source_geometry', original.to_dict()['scanner'])
        self.assertTrue(experimental.to_dict()['scanner']['source_geometry'])
        restored = CorrectionProject.from_dict(experimental.to_dict())
        self.assertTrue(restored.source_geometry)
        self.assertEqual(original.to_jmap().to_text(), restored.to_jmap().to_text())

    def test_app_upload_passes_mode_without_extra_default_kwarg(self):
        buffer = BytesIO(); Image.new('RGB',(800,608)).save(buffer,format='PNG')
        result = self.result(); result.source_geometry=True
        with patch('jtool_scanner.app.scan_png',return_value=result) as scan:
            project = app.scan_image_bytes(buffer.getvalue(),use_ocr=False,source_geometry=True)
            self.assertTrue(scan.call_args.kwargs['source_geometry'])
            self.assertTrue(project.source_geometry)
            app.scan_image_bytes(buffer.getvalue(),use_ocr=False)
            self.assertNotIn('source_geometry',scan.call_args.kwargs)

    def test_cli_scan_mode_is_forwarded_to_real_entry_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'out.jmap'
            with patch('jtool_scanner.cli.scan_png',return_value=self.result()) as scan, redirect_stdout(StringIO()):
                self.assertEqual(main(['scan-image','unused.png',str(output),'--include-geometry','--source-geometry','--no-ocr']),0)
            self.assertTrue(scan.call_args.kwargs['source_geometry'])
            self.assertTrue(output.is_file())

    def test_fingerprint_includes_transitive_source_dependency_bytes(self):
        paths=source_geometry_files()
        self.assertEqual(len(paths),18)
        rectangle = next(p for p in paths if p.name == 'source_rectangle_prototypes.py')
        self.assertTrue(all(p.is_file() for p in paths))
        original=app._source_fingerprint()
        read_bytes=Path.read_bytes
        for path in (paths[0], rectangle, *(p for p in paths if p.name in
                    ('source_sampling.py', 'source_hollow_glyphs.py', 'source_hollow_pipeline.py',
                     'source_hollow_phase.py', 'source_growth_confidence.py'))):
            with self.subTest(dependency=path.name), \
                 patch.object(Path,'read_bytes',lambda p:read_bytes(p)+(b'\n# changed test dependency\n' if p==path else b'')):
                self.assertNotEqual(app._source_fingerprint(),original)
