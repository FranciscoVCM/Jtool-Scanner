from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from jtool_scanner.corpus import DEFAULTS
from jtool_scanner.geometry import Box
from jtool_scanner.jmap import JMap, JMapObject
from jtool_scanner.scanner import Detection
from scripts import triangle_stage_context as context


class TriangleStageContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.png'
        Image.new('RGB', (4, 4), (120, 70, 19)).save(self.source)
        self.image = context.load_png(self.source)
        self.room = Box(0, 0, 4, 4)
        self.before = [Detection('spike', 3, 16, 32, .937, Box(1, 2, 3, 4))] * 2
        self.after = self.before + [Detection('mini', 7, 24, 48, .86, Box(2, 1, 2, 2))]
        self.mapped = JMap(infinite_jump=1, dot_kid=1, save_type=2, border_type=1,
                           player_save_x=24, player_save_y=48, player_xscale=-1,
                           player_gravity=-1,
                           objects=[JMapObject(d.x, d.y, d.type_id) for d in self.after])
        self.directory = self.root / 'ordinary'
        self.directory.mkdir()
        self.map_path = self.directory / 'detected.jmap'
        self.mapped.to_file(self.map_path)
        self.identity = dict(code_sha256='code', git_head='new-docs-head',
                             python='python', pillow='pillow', platform='platform')
        options = {**DEFAULTS, 'room_box': [0, 0, 4, 4], 'source_grid': [25, 19]}
        self.case = dict(id='example', source=str(self.source), directory=str(self.directory),
                         inputs={**self.identity, 'source_sha256': context.digest(self.source),
                                 'git_head': 'older-docs-head', 'options': options},
                         artifact_hashes={'detected.jmap': context.digest(self.map_path)})
        self.report = self.root / 'report.json'
        self.report.write_text(json.dumps(dict(implementation=self.identity, cases=[self.case])),
                               encoding='utf-8')
        self.out = self.root / 'capture'
        self.stage_patch = patch.object(context.scanner, context.STAGE, side_effect=self.run_stage)
        self.stage = self.stage_patch.start()
        self.addCleanup(self.stage_patch.stop)
        self.identity_patch = patch.object(context, 'implementation_identity', return_value=self.identity)
        self.identity_mock = self.identity_patch.start()
        self.addCleanup(self.identity_patch.stop)

    def run_stage(self, detections, image, room):
        self.assertEqual(detections, self.before)
        self.assertEqual(image.data, self.image.data)
        self.assertEqual(room, self.room)
        return list(self.after)

    def run_scan(self, source, **options):
        self.assertEqual(source, self.source)
        self.assertEqual(options['room_box'], self.room)
        self.assertEqual(options['source_grid'], (25, 19))
        self.assertNotIn('start_policy', options)
        getattr(context.scanner, context.STAGE)(list(self.before), self.image, self.room)
        return SimpleNamespace(to_jmap=lambda start_policy: deepcopy(self.mapped))

    def capture(self, scan=None):
        with patch.object(context.scanner, 'scan_png', side_effect=scan or self.run_scan):
            return context.capture(self.report, 'example', self.out)

    def rewrite_report(self, report):
        self.report.write_text(json.dumps(report), encoding='utf-8')

    def trace_path(self):
        return self.out / 'trace.json'

    def test_full_detection_records_roundtrip_and_multisets_include_duplicates(self):
        self.assertEqual(context.decode(context.records(self.before)), self.before)
        self.assertEqual(context.typed(self.mapped)[(3, 16, 32)], 2)
        different = replace(self.before[0], score=.4, kind='other', image_box=Box(0, 0, 1, 1))
        self.assertNotEqual(context.records([different]), context.records(self.before[:1]))

    def test_capture_all_metadata_and_replay_exact_inputs_despite_docs_only_head_change(self):
        payload = self.capture()
        self.assertTrue(payload['ordinary_map_and_all_metadata_equal'])
        self.assertEqual(payload['contexts'][0]['before'], context.records(self.before))
        self.assertIs(getattr(context.scanner, context.STAGE), self.stage)
        result = context.replay(self.trace_path(), self.root / 'replay')
        self.assertTrue(result['rows'][0]['complete_detection_records_equal'])
        self.assertEqual(result['rows'][0]['added'], [(7, 24, 48)])
        self.assertEqual(result['rows'][0]['removed'], [])
        self.assertFalse(result['ordinary'])
        self.assertTrue(result['stage_only'])

    def test_replay_candidate_records_both_identities_without_claiming_full_scan(self):
        self.capture()
        self.identity_mock.return_value = {**self.identity, 'code_sha256': 'candidate'}
        result = context.replay(self.trace_path(), self.root / 'replay')
        self.assertEqual(result['capture_implementation']['code_sha256'], 'code')
        self.assertEqual(result['replay_implementation']['code_sha256'], 'candidate')
        self.assertFalse(result['ordinary'])
        self.assertTrue(result['stage_only'])

    def test_reject_shadow_runtime_source_and_artifact_mismatch_before_scanning(self):
        original = json.loads(self.report.read_text())
        changed = []
        shadow = deepcopy(original)
        shadow['implementation']['shadow'] = True
        changed.append(shadow)
        for key in ('code_sha256', 'python', 'pillow', 'platform', 'source_sha256'):
            bad = deepcopy(original)
            bad['cases'][0]['inputs'][key] = 'wrong'
            changed.append(bad)
        bad = deepcopy(original)
        bad['cases'][0]['artifact_hashes']['detected.jmap'] = 'wrong'
        changed.append(bad)
        bad = deepcopy(original)
        bad['cases'][0]['artifact_hashes'] = {}
        changed.append(bad)
        for report in changed:
            with self.subTest(report=report), patch.object(context.scanner, 'scan_png') as scan:
                self.rewrite_report(report)
                with self.assertRaises(ValueError):
                    context.capture(self.report, 'example', self.out)
                scan.assert_not_called()
                self.assertFalse(self.out.exists())

    def test_case_must_be_unique(self):
        for cases in ([], [self.case, self.case]):
            with self.subTest(cases=cases):
                self.rewrite_report(dict(implementation=self.identity, cases=cases))
                with self.assertRaises(ValueError):
                    self.capture()

    def test_observer_restored_after_scan_failure(self):
        def fail(source, **options):
            self.run_scan(source, **options)
            raise RuntimeError('scan failed')
        with self.assertRaisesRegex(RuntimeError, 'scan failed'):
            self.capture(fail)
        self.assertIs(getattr(context.scanner, context.STAGE), self.stage)
        self.assertFalse(self.trace_path().exists())

    def test_capture_rejects_typed_map_or_any_metadata_change(self):
        original = deepcopy(self.mapped)
        variants = [JMap(**{**asdict(original), 'objects': []})]
        for key in context.metadata(original):
            changed = deepcopy(original)
            setattr(changed, key, 'changed' if key == 'version' else getattr(changed, key) + 1)
            variants.append(changed)
        for index, mapped in enumerate(variants):
            with self.subTest(index=index):
                self.mapped = mapped
                self.out = self.root / f'mismatch-{index}'
                with self.assertRaisesRegex(ValueError, 'full map/ALL metadata'):
                    self.capture()
                self.assertFalse(self.trace_path().exists())
                self.assertIs(getattr(context.scanner, context.STAGE), self.stage)

    def test_capture_rejects_input_or_implementation_changed_during_scan(self):
        for index, mutation in enumerate(('source', 'artifact', 'implementation')):
            with self.subTest(mutation=mutation):
                # Restore the fixture identities, never existing project files.
                self.out = self.root / f'race-{index}'
                Image.new('RGB', (4, 4), (120, 70, 19)).save(self.source)
                self.mapped.to_file(self.map_path)
                self.identity_mock.side_effect = None
                if mutation == 'implementation':
                    self.identity_mock.side_effect = [self.identity, {**self.identity, 'code_sha256': 'new'}]
                def change(source, **options):
                    result = self.run_scan(source, **options)
                    if mutation == 'source':
                        Image.new('RGB', (4, 4), 'white').save(self.source)
                    elif mutation == 'artifact':
                        self.map_path.write_text('changed', encoding='utf-8')
                    return result
                with self.assertRaises(ValueError):
                    self.capture(change)
                self.assertFalse(self.trace_path().exists())

    def test_capture_requires_an_actual_stage_invocation(self):
        with self.assertRaisesRegex(ValueError, 'never invoked'):
            self.capture(lambda source, **options: SimpleNamespace(to_jmap=lambda **kw: self.mapped))

    def test_existing_output_is_never_overwritten(self):
        self.capture()
        saved = self.trace_path().read_bytes()
        with self.assertRaises(FileExistsError):
            self.capture()
        self.assertEqual(self.trace_path().read_bytes(), saved)
        replay_dir = self.root / 'replay'
        context.replay(self.trace_path(), replay_dir)
        saved_replay = (replay_dir / 'replay.json').read_bytes()
        with self.assertRaises(FileExistsError):
            context.replay(self.trace_path(), replay_dir)
        self.assertEqual((replay_dir / 'replay.json').read_bytes(), saved_replay)

    def test_replay_rejects_tampered_pixels_rgb_path_and_unverified_or_empty_trace(self):
        self.capture()
        trace = json.loads(self.trace_path().read_text())
        changes = [('ordinary_map_and_all_metadata_equal', False), ('stage', 'wrong'),
                   ('format', 'wrong'), ('contexts', [])]
        variants = [{**trace, key: value} for key, value in changes]
        for key, value in (('image_sha256', 'wrong'), ('image_rgb_sha256', 'wrong'),
                           ('image', '../source.png'), ('image', '..')):
            bad = deepcopy(trace)
            bad['contexts'][0][key] = value
            variants.append(bad)
        self.stage.reset_mock()
        for index, bad in enumerate(variants):
            with self.subTest(index=index):
                self.trace_path().write_text(json.dumps(bad), encoding='utf-8')
                with self.assertRaises(ValueError):
                    context.replay(self.trace_path(), self.root / f'bad-replay-{index}')
        self.stage.assert_not_called()

    def test_replay_counter_delta_is_saved_before_mutating_stage(self):
        self.capture()
        def mutate(detections, image, room):
            detections.append(self.after[-1])
            return detections
        self.stage.side_effect = mutate
        result = context.replay(self.trace_path(), self.root / 'replay')
        self.assertEqual(result['rows'][0]['added'], [(7, 24, 48)])
        self.assertTrue(result['rows'][0]['complete_detection_records_equal'])
